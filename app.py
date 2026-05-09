import re
from pathlib import Path
from datetime import timedelta
import io

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="Панель управления ошибками",
    layout="wide"
)

BUSINESS_LINES = ["КБ", "РБ"]

CLASSIFICATION_MAP = {
    "Автоответы": ["АвтоОтветы", "Автоответы"],
    "Коммерческое предложение": ["Коммерческое_предложение", "Коммерческое предложение"],
    "Конфиг-файлы": ["Конфиг-файлы", "Конфиг_файлы"],
    "Массовые рассылки": ["Массовые_рассылки", "Массовые рассылки"],
    "Отправка / получение сообщений": [
        "Отправка/получение_сообщений",
        "Отправка / получение сообщений",
    ],
    "Отчеты": ["Отчеты", "Отчёты"],
    "Пользовательский интерфейс": [
        "Пользовательский_интерфейс",
        "Пользовательский интерфейс",
    ],
    "Портфели / MDM": ["Портфели/MDM", "Портфели / MDM"],
    "Счетчик": ["Счетчик", "Счётчик"],
    "Уведомления / push": ["Уведомления/push", "Уведомления / push"],
    "Файлы": ["Файлы"],
    "Чаты": ["Чаты"],
}

CLOSED_STATUSES = ["Закрыт", "В релизе"]

DATE_CREATED_COL = "Дата создания"
DATE_RESOLUTION_COL = "Дата резолюции"
DUE_DATE_COL = "Срок исполнения"
VERSION_COL = "Исправить в версиях"


st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1500px;
    }

    div[data-testid="stMetric"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 18px;
        border-radius: 16px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.18);
    }

    div[data-testid="stMetricLabel"] {
        font-size: 15px;
        color: #9da7b3;
    }

    div[data-testid="stMetricValue"] {
        font-size: 30px;
        font-weight: 800;
    }

    .insight-box {
        background: linear-gradient(135deg, #161b22 0%, #1f2937 100%);
        border: 1px solid #30363d;
        border-radius: 18px;
        padding: 20px 24px;
        margin: 12px 0 24px 0;
    }

    .insight-title {
        font-size: 20px;
        font-weight: 800;
        margin-bottom: 10px;
    }

    .insight-item {
        font-size: 16px;
        margin: 7px 0;
        color: #d1d5db;
    }

    .section-title {
        font-size: 24px;
        font-weight: 800;
        margin: 20px 0 8px 0;
    }
    </style>
    """,
    unsafe_allow_html=True
)


def read_jira_file(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith(".xls"):
        tables = pd.read_html(uploaded_file)
        return tables[1]
    return pd.read_excel(uploaded_file)


def extract_classification(labels):
    text = str(labels).lower()
    found = []

    for display_name, aliases in CLASSIFICATION_MAP.items():
        for alias in aliases:
            if alias.lower() in text:
                found.append(display_name)
                break

    return ", ".join(found) if found else "Не указано"


def extract_business_line(labels):
    text = str(labels).lower()

    if "кб" in text:
        return "КБ"

    if "рб" in text:
        return "РБ"

    return "Не указано"


@st.cache_data
def load_data(files_data: list) -> pd.DataFrame:
    if not files_data:
        return pd.DataFrame()

    frames = []

    for name, data in files_data:
        try:
            file_like = io.BytesIO(data)
            file_like.name = name
            df = read_jira_file(file_like)
            df["snapshot_file"] = name
            frames.append(df)
        except Exception as e:
            st.warning(f"Не удалось прочитать файл {name}: {e}")

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df.columns = [str(c).strip() for c in df.columns]

    if "Метки" not in df.columns:
        df["Метки"] = ""

    df["Бизнес-линия"] = df["Метки"].apply(extract_business_line)
    df["Классификация"] = df["Метки"].apply(extract_classification)

    for col in [DATE_CREATED_COL, "Обновлен", DATE_RESOLUTION_COL, DUE_DATE_COL]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

    today = pd.Timestamp.today().normalize()

    if DATE_CREATED_COL in df.columns:
        df["Возраст бага, дней"] = (today - df[DATE_CREATED_COL]).dt.days
    else:
        df["Возраст бага, дней"] = None

    if DUE_DATE_COL in df.columns and "Статус" in df.columns:
        df["Просрочен"] = (
            (df[DUE_DATE_COL] < today)
            & (~df["Статус"].astype(str).isin(CLOSED_STATUSES))
        )
    else:
        df["Просрочен"] = False

    return df


st.title("🐞 Панель управления ошибками")
st.caption("Активный backlog: учитываются только дефекты не в статусах «Закрыт» и «В релизе».")

# --- Загрузка файла ---
uploaded_files = st.sidebar.file_uploader(
    "📂 Загрузите файл(ы) выгрузки из Jira",
    type=["xls", "xlsx"],
    accept_multiple_files=True,
)

if not uploaded_files:
    st.info("👈 Загрузите файл выгрузки из Jira в боковой панели слева, чтобы увидеть дашборд.")
    st.stop()

# Кешируем по содержимому файлов
files_data = [(f.name, f.read()) for f in uploaded_files]
df = load_data(files_data)

if df.empty:
    st.error("Не удалось прочитать данные из загруженных файлов.")
    st.stop()


st.sidebar.header("Фильтры")


def multiselect_filter(label, column):
    if column not in df.columns:
        return []

    values = sorted([v for v in df[column].dropna().unique() if str(v) != "nan"])

    return st.sidebar.multiselect(label, values)


business_filter = multiselect_filter("Бизнес-линия", "Бизнес-линия")
classification_filter = multiselect_filter("Классификация", "Классификация")
status_filter = multiselect_filter("Статус", "Статус")
priority_filter = multiselect_filter("Приоритет", "Приоритет")
assignee_filter = multiselect_filter("Исполнитель", "Исполнитель")
version_filter = multiselect_filter("Версия", VERSION_COL)


filtered = df.copy()

filtered = filtered[
    ~filtered["Статус"].astype(str).isin(CLOSED_STATUSES)
]

if business_filter:
    filtered = filtered[filtered["Бизнес-линия"].isin(business_filter)]

if classification_filter:
    filtered = filtered[filtered["Классификация"].isin(classification_filter)]

if status_filter:
    filtered = filtered[filtered["Статус"].isin(status_filter)]

if priority_filter:
    filtered = filtered[filtered["Приоритет"].isin(priority_filter)]

if assignee_filter:
    filtered = filtered[filtered["Исполнитель"].isin(assignee_filter)]

if version_filter and VERSION_COL in filtered.columns:
    filtered = filtered[filtered[VERSION_COL].isin(version_filter)]


if DATE_CREATED_COL in filtered.columns and filtered[DATE_CREATED_COL].notna().any():
    min_date = filtered[DATE_CREATED_COL].min().date()
    max_date = filtered[DATE_CREATED_COL].max().date()

    date_range = st.sidebar.date_input(
        "Дата создания",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range

        filtered = filtered[
            (filtered[DATE_CREATED_COL].dt.date >= start_date)
            & (filtered[DATE_CREATED_COL].dt.date <= end_date)
        ]


today = pd.Timestamp.today().normalize()
week_ago = today - timedelta(days=7)

critical_df = filtered[
    filtered["Приоритет"]
    .astype(str)
    .str.contains("Блокирующий|Критичный|Critical|Blocker", case=False, na=False)
]

new_week = (
    filtered[filtered[DATE_CREATED_COL] >= week_ago]
    if DATE_CREATED_COL in filtered.columns
    else filtered.iloc[0:0]
)

closed_week = (
    df[
        (df[DATE_RESOLUTION_COL] >= week_ago)
        & (df["Статус"].astype(str).isin(CLOSED_STATUSES))
    ]
    if DATE_RESOLUTION_COL in df.columns
    else df.iloc[0:0]
)

avg_age = filtered["Возраст бага, дней"].mean()
overdue_count = int(filtered["Просрочен"].sum()) if "Просрочен" in filtered.columns else 0
no_bl_count = len(filtered[filtered["Бизнес-линия"] == "Не указано"])
no_bl_share = (no_bl_count / len(filtered) * 100) if len(filtered) else 0

top_priority = (
    filtered["Приоритет"].value_counts().idxmax()
    if "Приоритет" in filtered.columns and not filtered.empty
    else "—"
)

top_category = (
    filtered["Классификация"].value_counts().idxmax()
    if "Классификация" in filtered.columns and not filtered.empty
    else "—"
)


k1, k2, k3, k4, k5, k6 = st.columns(6)

k1.metric("Открытые баги", len(filtered))
k2.metric("Critical / Blocker", len(critical_df))
k3.metric("Просроченные", overdue_count)
k4.metric("Новые за неделю", len(new_week))
k5.metric("Закрытые за неделю", len(closed_week))
k6.metric("Средний возраст", f"{avg_age:.0f} дн." if pd.notna(avg_age) else "—")


st.markdown(
    f"""
    <div class="insight-box">
        <div class="insight-title">Ключевые выводы</div>
        <div class="insight-item">• Основной приоритет в активном backlog: <b>{top_priority}</b></div>
        <div class="insight-item">• Самая частая категория дефектов: <b>{top_category}</b></div>
        <div class="insight-item">• Дефекты без бизнес-линии: <b>{no_bl_count}</b> ({no_bl_share:.1f}%)</div>
    </div>
    """,
    unsafe_allow_html=True
)


st.markdown('<div class="section-title">Динамика качества</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Динамика активного backlog")

    if DATE_CREATED_COL in filtered.columns and filtered[DATE_CREATED_COL].notna().any():
        backlog = (
            filtered
            .dropna(subset=[DATE_CREATED_COL])
            .assign(week=lambda x: x[DATE_CREATED_COL].dt.to_period("W").dt.start_time)
            .groupby("week")
            .size()
            .reset_index(name="Количество открытых багов")
        )

        fig = px.line(
            backlog,
            x="week",
            y="Количество открытых багов",
            markers=True,
        )

        fig.update_layout(
            height=390,
            margin=dict(l=10, r=10, t=20, b=10),
            xaxis_title=None,
            yaxis_title="Открытые баги",
            showlegend=False,
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Нет данных по дате создания.")


with col2:
    st.subheader("Тренд новых дефектов")

    if DATE_CREATED_COL in filtered.columns and filtered[DATE_CREATED_COL].notna().any():
        new_trend = (
            filtered
            .dropna(subset=[DATE_CREATED_COL])
            .assign(week=lambda x: x[DATE_CREATED_COL].dt.to_period("W").dt.start_time)
            .groupby("week")
            .size()
            .reset_index(name="Новые баги")
        )

        fig = px.bar(
            new_trend,
            x="week",
            y="Новые баги",
        )

        fig.update_layout(
            height=390,
            margin=dict(l=10, r=10, t=20, b=10),
            xaxis_title=None,
            yaxis_title="Новые баги",
            showlegend=False,
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Нет данных по дате создания.")


st.markdown('<div class="section-title">Структура активного backlog</div>', unsafe_allow_html=True)

col3, col4 = st.columns(2)

with col3:
    st.subheader("Баги по приоритетам")

    priority = (
        filtered
        .groupby("Приоритет")
        .size()
        .reset_index(name="Количество")
        .sort_values("Количество", ascending=False)
    )

    fig = px.bar(
        priority,
        x="Приоритет",
        y="Количество",
        text="Количество",
    )

    fig.update_traces(textposition="outside")

    fig.update_layout(
        height=390,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis_title=None,
        yaxis_title="Количество",
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)


with col4:
    st.subheader("Баги по бизнес-линиям")

    business = (
        filtered
        .groupby("Бизнес-линия")
        .size()
        .reset_index(name="Количество")
        .sort_values("Количество", ascending=False)
    )

    fig = px.bar(
        business,
        x="Бизнес-линия",
        y="Количество",
        text="Количество",
    )

    fig.update_traces(textposition="outside")

    fig.update_layout(
        height=390,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis_title=None,
        yaxis_title="Количество",
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)


col5, col6 = st.columns(2)

with col5:
    st.subheader("Топ категорий дефектов")

    classification = (
        filtered
        .groupby("Классификация")
        .size()
        .reset_index(name="Количество")
        .sort_values("Количество", ascending=True)
        .tail(10)
    )

    fig = px.bar(
        classification,
        x="Количество",
        y="Классификация",
        orientation="h",
        text="Количество",
    )

    fig.update_traces(textposition="outside")

    fig.update_layout(
        height=470,
        margin=dict(l=10, r=40, t=20, b=10),
        xaxis_title="Количество",
        yaxis_title=None,
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)


with col6:
    st.subheader("Классификация × Бизнес-линия")

    matrix = (
        filtered
        .groupby(["Классификация", "Бизнес-линия"])
        .size()
        .reset_index(name="Количество")
    )

    if not matrix.empty:
        fig = px.density_heatmap(
            matrix,
            x="Бизнес-линия",
            y="Классификация",
            z="Количество",
            text_auto=True,
        )

        fig.update_layout(
            height=470,
            margin=dict(l=10, r=10, t=20, b=10),
            xaxis_title=None,
            yaxis_title=None,
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Нет данных для матрицы.")


st.markdown('<div class="section-title">Пропускная способность</div>', unsafe_allow_html=True)

if DATE_RESOLUTION_COL in df.columns and df[DATE_RESOLUTION_COL].notna().any():
    throughput = (
        df[
            df["Статус"]
            .astype(str)
            .isin(CLOSED_STATUSES)
        ]
        .dropna(subset=[DATE_RESOLUTION_COL])
        .assign(week=lambda x: x[DATE_RESOLUTION_COL].dt.to_period("W").dt.start_time)
        .groupby("week")
        .size()
        .reset_index(name="Закрытые баги")
    )

    fig = px.bar(
        throughput,
        x="week",
        y="Закрытые баги",
        text="Закрытые баги",
    )

    fig.update_traces(textposition="outside")

    fig.update_layout(
        height=390,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis_title=None,
        yaxis_title="Закрытые баги",
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Нет данных по дате резолюции.")


with st.expander("Детализация дефектов"):
    show_cols = [
        "Код",
        "Тема",
        "Статус",
        "Приоритет",
        "Исполнитель",
        DATE_CREATED_COL,
        DATE_RESOLUTION_COL,
        "Возраст бага, дней",
        "Бизнес-линия",
        "Классификация",
        VERSION_COL,
        "Метки",
    ]

    show_cols = [c for c in show_cols if c in filtered.columns]

    st.dataframe(
        filtered[show_cols],
        use_container_width=True,
        hide_index=True,
    )