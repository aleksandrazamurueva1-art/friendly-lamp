from datetime import timedelta

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="Панель управления ошибками",
    layout="wide"
)

SHEET_ID = "1dEJWQqajA2LsCJQddGPXq9Q1vUbkU3wy2XlV23GInwo"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"

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
    div[data-testid="stMetricLabel"] { font-size: 15px; color: #9da7b3; }
    div[data-testid="stMetricValue"] { font-size: 30px; font-weight: 800; }
    .insight-box {
        background: linear-gradient(135deg, #161b22 0%, #1f2937 100%);
        border: 1px solid #30363d;
        border-radius: 18px;
        padding: 20px 24px;
        margin: 12px 0 24px 0;
    }
    .insight-title { font-size: 20px; font-weight: 800; margin-bottom: 10px; }
    .insight-item { font-size: 16px; margin: 7px 0; color: #d1d5db; }
    .section-title { font-size: 24px; font-weight: 800; margin: 28px 0 8px 0; border-top: 1px solid #30363d; padding-top: 20px; }
    .week-box {
        background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
        border: 1px solid #238636;
        border-radius: 18px;
        padding: 20px 24px;
        margin: 12px 0 24px 0;
    }
    .week-title { font-size: 18px; font-weight: 800; margin-bottom: 12px; color: #3fb950; }
    .week-item { font-size: 15px; margin: 5px 0; color: #d1d5db; }
    </style>
    """,
    unsafe_allow_html=True
)


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
    has_kb = "кб" in text
    has_rb = "рб" in text
    if has_kb and has_rb:
        return "Общее"
    if has_kb:
        return "КБ"
    if has_rb:
        return "РБ"
    return "Не указано"


def extract_justai(labels):
    return "justai" in str(labels).lower()


@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    try:
        df = pd.read_excel(SHEET_URL, header=3)
    except Exception as e:
        st.error(f"Не удалось загрузить данные из Google Sheets: {e}")
        return pd.DataFrame()

    df.columns = [str(c).strip() for c in df.columns]

    if "Метки" not in df.columns:
        df["Метки"] = ""

    df["Бизнес-линия"] = df["Метки"].apply(extract_business_line)
    df["Классификация"] = df["Метки"].apply(extract_classification)
    df["JustAI"] = df["Метки"].apply(extract_justai)

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


def bar_with_pct(data, x, y, title, orientation="v", height=390):
    """Строит bar chart с подписями 'N (X%)' от общей суммы."""
    total = data[y].sum() if orientation == "v" else data[x].sum()
    if total == 0:
        return None
    if orientation == "v":
        data = data.copy()
        data["label"] = data[y].apply(lambda v: f"{v}<br>({v/total*100:.1f}%)")
        fig = px.bar(data, x=x, y=y, text="label")
        fig.update_traces(textposition="outside")
    else:
        data = data.copy()
        data["label"] = data[x].apply(lambda v: f"{v} ({v/total*100:.1f}%)")
        fig = px.bar(data, x=x, y=y, orientation="h", text="label")
        fig.update_traces(textposition="outside")
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=60, t=30, b=10),
        xaxis_title=None,
        yaxis_title=None,
        showlegend=False,
        uniformtext_minsize=9,
    )
    return fig


def get_week_bounds(today):
    """Возвращает границы прошлой (пн-вс) и текущей (пн-сегодня) недели."""
    weekday = today.weekday()  # 0=пн
    current_week_start = today - timedelta(days=weekday)
    prev_week_start = current_week_start - timedelta(days=7)
    prev_week_end = current_week_start - timedelta(days=1)
    return prev_week_start, prev_week_end, current_week_start, today


# ── Заголовок ──────────────────────────────────────────────────────────────
st.title("🐞 Панель управления ошибками")
st.caption("Активный backlog: учитываются только дефекты не в статусах «Закрыт» и «В релизе».")

if st.sidebar.button("🔄 Обновить данные"):
    st.cache_data.clear()

df = load_data()

if df.empty:
    st.error("Нет данных. Проверьте доступ к Google Sheets.")
    st.stop()

st.sidebar.header("Фильтры")


def multiselect_filter(label, column, source=None):
    src = source if source is not None else df
    if column not in src.columns:
        return []
    values = sorted([v for v in src[column].dropna().unique() if str(v) != "nan"])
    return st.sidebar.multiselect(label, values)


business_filter = multiselect_filter("Бизнес-линия", "Бизнес-линия")
classification_filter = multiselect_filter("Классификация", "Классификация")
status_filter = multiselect_filter("Статус", "Статус")
priority_filter = multiselect_filter("Приоритет", "Приоритет")
assignee_filter = multiselect_filter("Исполнитель", "Исполнитель")
version_filter = multiselect_filter("Версия", VERSION_COL)

filtered = df.copy()
filtered = filtered[~filtered["Статус"].astype(str).isin(CLOSED_STATUSES)]

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
prev_w_start, prev_w_end, cur_w_start, cur_w_end = get_week_bounds(today)

critical_df = filtered[
    filtered["Приоритет"].astype(str)
    .str.contains("Блокирующий|Критичный|Critical|Blocker", case=False, na=False)
]

new_cur_week = (
    filtered[
        (filtered[DATE_CREATED_COL] >= cur_w_start)
        & (filtered[DATE_CREATED_COL] <= cur_w_end)
    ]
    if DATE_CREATED_COL in filtered.columns else filtered.iloc[0:0]
)

closed_cur_week = (
    df[
        (df[DATE_RESOLUTION_COL] >= cur_w_start)
        & (df[DATE_RESOLUTION_COL] <= cur_w_end)
        & (df["Статус"].astype(str).isin(CLOSED_STATUSES))
    ]
    if DATE_RESOLUTION_COL in df.columns else df.iloc[0:0]
)

avg_age = filtered["Возраст бага, дней"].mean()
overdue_count = int(filtered["Просрочен"].sum()) if "Просрочен" in filtered.columns else 0

top_priority = (
    filtered["Приоритет"].value_counts().idxmax()
    if "Приоритет" in filtered.columns and not filtered.empty else "—"
)
top_category = (
    filtered["Классификация"].value_counts().idxmax()
    if "Классификация" in filtered.columns and not filtered.empty else "—"
)
no_bl_count = len(filtered[filtered["Бизнес-линия"] == "Не указано"])
no_bl_share = (no_bl_count / len(filtered) * 100) if len(filtered) else 0
justai_count = int(filtered["JustAI"].sum())
justai_share = (justai_count / len(filtered) * 100) if len(filtered) else 0

# ── KPI ────────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Открытые баги", len(filtered))
k2.metric("Critical / Blocker", len(critical_df))
k3.metric("Просроченные", overdue_count)
k4.metric("JustAI (вендор)", f"{justai_count} ({justai_share:.0f}%)")
k5.metric("Новые (тек. неделя)", len(new_cur_week))
k6.metric("Средний возраст", f"{avg_age:.0f} дн." if pd.notna(avg_age) else "—")

st.markdown(
    f"""
    <div class="insight-box">
        <div class="insight-title">Ключевые выводы</div>
        <div class="insight-item">• Основной приоритет в активном backlog: <b>{top_priority}</b></div>
        <div class="insight-item">• Самая частая категория дефектов: <b>{top_category}</b></div>
        <div class="insight-item">• Дефекты без бизнес-линии: <b>{no_bl_count}</b> ({no_bl_share:.1f}%)</div>
        <div class="insight-item">• Баги на стороне вендора (JustAI): <b>{justai_count}</b> ({justai_share:.1f}%)</div>
    </div>
    """,
    unsafe_allow_html=True
)

# ── ИТОГИ НЕДЕЛЬ ───────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📅 Итоги недель</div>', unsafe_allow_html=True)

tab_prev, tab_cur = st.tabs([
    f"Прошлая неделя ({prev_w_start.strftime('%d.%m')} – {prev_w_end.strftime('%d.%m')})",
    f"Текущая неделя ({cur_w_start.strftime('%d.%m')} – {today.strftime('%d.%m')})",
])

for tab, w_start, w_end, label in [
    (tab_prev, prev_w_start, prev_w_end, "прошлой"),
    (tab_cur, cur_w_start, cur_w_end, "текущей"),
]:
    with tab:
        w_new = (
            df[
                (df[DATE_CREATED_COL] >= w_start)
                & (df[DATE_CREATED_COL] <= w_end + timedelta(days=1))
            ]
            if DATE_CREATED_COL in df.columns else df.iloc[0:0]
        )
        w_closed = (
            df[
                (df[DATE_RESOLUTION_COL] >= w_start)
                & (df[DATE_RESOLUTION_COL] <= w_end + timedelta(days=1))
                & (df["Статус"].astype(str).isin(CLOSED_STATUSES))
            ]
            if DATE_RESOLUTION_COL in df.columns else df.iloc[0:0]
        )

        wk1, wk2 = st.columns(2)
        wk1.metric("Открыто за неделю", len(w_new))
        wk2.metric("Закрыто за неделю", len(w_closed))

        if not w_new.empty:
            wc1, wc2, wc3 = st.columns(3)

            with wc1:
                st.subheader("По категориям")
                wcat = (
                    w_new.groupby("Классификация").size()
                    .reset_index(name="Количество")
                    .sort_values("Количество", ascending=True)
                )
                fig = bar_with_pct(wcat, "Количество", "Классификация", "", orientation="h", height=350)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)

            with wc2:
                st.subheader("По приоритетам")
                wpri = (
                    w_new.groupby("Приоритет").size()
                    .reset_index(name="Количество")
                    .sort_values("Количество", ascending=False)
                )
                fig = bar_with_pct(wpri, "Приоритет", "Количество", "", height=350)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)

            with wc3:
                st.subheader("По бизнес-линиям")
                wbl = (
                    w_new.groupby("Бизнес-линия").size()
                    .reset_index(name="Количество")
                    .sort_values("Количество", ascending=False)
                )
                fig = bar_with_pct(wbl, "Бизнес-линия", "Количество", "", height=350)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"Нет новых багов за {label} неделю.")

# ── ДИНАМИКА ───────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📈 Динамика качества</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Тренд новых дефектов (по неделям)")
    if DATE_CREATED_COL in filtered.columns and filtered[DATE_CREATED_COL].notna().any():
        new_trend = (
            filtered.dropna(subset=[DATE_CREATED_COL])
            .assign(week=lambda x: x[DATE_CREATED_COL].dt.to_period("W").dt.start_time)
            .groupby("week").size()
            .reset_index(name="Новые баги")
        )
        total = new_trend["Новые баги"].sum()
        new_trend["label"] = new_trend["Новые баги"].apply(
            lambda v: f"{v}<br>({v/total*100:.1f}%)" if total else str(v)
        )
        fig = px.bar(new_trend, x="week", y="Новые баги", text="label")
        fig.update_traces(textposition="outside")
        fig.update_layout(height=390, margin=dict(l=10, r=10, t=30, b=10), xaxis_title=None, yaxis_title="Новые баги", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Нет данных по дате создания.")

with col2:
    st.subheader("Тренд закрытия дефектов (по неделям)")
    if DATE_RESOLUTION_COL in df.columns and df[DATE_RESOLUTION_COL].notna().any():
        closed_trend = (
            df[df["Статус"].astype(str).isin(CLOSED_STATUSES)]
            .dropna(subset=[DATE_RESOLUTION_COL])
            .assign(week=lambda x: x[DATE_RESOLUTION_COL].dt.to_period("W").dt.start_time)
            .groupby("week").size()
            .reset_index(name="Закрытые баги")
        )
        total = closed_trend["Закрытые баги"].sum()
        closed_trend["label"] = closed_trend["Закрытые баги"].apply(
            lambda v: f"{v}<br>({v/total*100:.1f}%)" if total else str(v)
        )
        fig = px.bar(closed_trend, x="week", y="Закрытые баги", text="label", color_discrete_sequence=["#238636"])
        fig.update_traces(textposition="outside")
        fig.update_layout(height=390, margin=dict(l=10, r=10, t=30, b=10), xaxis_title=None, yaxis_title="Закрытые баги", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Нет данных по дате резолюции.")

# ── СТРУКТУРА BACKLOG ───────────────────────────────────────────────────────
st.markdown('<div class="section-title">🗂 Структура активного backlog</div>', unsafe_allow_html=True)

col3, col4 = st.columns(2)

with col3:
    st.subheader("Баги по приоритетам")
    priority = (
        filtered.groupby("Приоритет").size()
        .reset_index(name="Количество")
        .sort_values("Количество", ascending=False)
    )
    fig = bar_with_pct(priority, "Приоритет", "Количество", "")
    if fig:
        st.plotly_chart(fig, use_container_width=True)

with col4:
    st.subheader("Баги по бизнес-линиям")
    business = (
        filtered.groupby("Бизнес-линия").size()
        .reset_index(name="Количество")
        .sort_values("Количество", ascending=False)
    )
    fig = bar_with_pct(business, "Бизнес-линия", "Количество", "")
    if fig:
        st.plotly_chart(fig, use_container_width=True)

col5, col6 = st.columns(2)

with col5:
    st.subheader("Топ категорий дефектов")
    classification = (
        filtered.groupby("Классификация").size()
        .reset_index(name="Количество")
        .sort_values("Количество", ascending=True)
        .tail(12)
    )
    fig = bar_with_pct(classification, "Количество", "Классификация", "", orientation="h", height=470)
    if fig:
        st.plotly_chart(fig, use_container_width=True)

with col6:
    st.subheader("Классификация × Бизнес-линия")
    matrix = (
        filtered.groupby(["Классификация", "Бизнес-линия"]).size()
        .reset_index(name="Количество")
    )
    if not matrix.empty:
        fig = px.density_heatmap(matrix, x="Бизнес-линия", y="Классификация", z="Количество", text_auto=True)
        fig.update_layout(height=470, margin=dict(l=10, r=10, t=30, b=10), xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Нет данных для матрицы.")

# ── JUSTAI ──────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🤖 Баги на стороне вендора (JustAI)</div>', unsafe_allow_html=True)

justai_df = filtered[filtered["JustAI"] == True]

if justai_df.empty:
    st.info("Нет активных багов с меткой JustAI.")
else:
    jc1, jc2 = st.columns(2)
    jc3, jc4 = st.columns(2)

    with jc1:
        st.subheader("По бизнес-линиям")
        jbl = (
            justai_df.groupby("Бизнес-линия").size()
            .reset_index(name="Количество")
            .sort_values("Количество", ascending=False)
        )
        fig = bar_with_pct(jbl, "Бизнес-линия", "Количество", "")
        if fig:
            st.plotly_chart(fig, use_container_width=True)

    with jc2:
        st.subheader("По категориям")
        jcat = (
            justai_df.groupby("Классификация").size()
            .reset_index(name="Количество")
            .sort_values("Количество", ascending=True)
        )
        fig = bar_with_pct(jcat, "Количество", "Классификация", "", orientation="h", height=390)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

    with jc3:
        st.subheader("Динамика открытия (JustAI)")
        if DATE_CREATED_COL in justai_df.columns and justai_df[DATE_CREATED_COL].notna().any():
            jopen = (
                justai_df.dropna(subset=[DATE_CREATED_COL])
                .assign(week=lambda x: x[DATE_CREATED_COL].dt.to_period("W").dt.start_time)
                .groupby("week").size()
                .reset_index(name="Новые баги JustAI")
            )
            total = jopen["Новые баги JustAI"].sum()
            jopen["label"] = jopen["Новые баги JustAI"].apply(
                lambda v: f"{v}<br>({v/total*100:.1f}%)" if total else str(v)
            )
            fig = px.bar(jopen, x="week", y="Новые баги JustAI", text="label", color_discrete_sequence=["#f85149"])
            fig.update_traces(textposition="outside")
            fig.update_layout(height=390, margin=dict(l=10, r=10, t=30, b=10), xaxis_title=None, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with jc4:
        st.subheader("Динамика закрытия (JustAI)")
        justai_all = df[df["JustAI"] == True]
        if DATE_RESOLUTION_COL in justai_all.columns and justai_all[DATE_RESOLUTION_COL].notna().any():
            jclosed = (
                justai_all[justai_all["Статус"].astype(str).isin(CLOSED_STATUSES)]
                .dropna(subset=[DATE_RESOLUTION_COL])
                .assign(week=lambda x: x[DATE_RESOLUTION_COL].dt.to_period("W").dt.start_time)
                .groupby("week").size()
                .reset_index(name="Закрытые баги JustAI")
            )
            total = jclosed["Закрытые баги JustAI"].sum()
            jclosed["label"] = jclosed["Закрытые баги JustAI"].apply(
                lambda v: f"{v}<br>({v/total*100:.1f}%)" if total else str(v)
            )
            fig = px.bar(jclosed, x="week", y="Закрытые баги JustAI", text="label", color_discrete_sequence=["#238636"])
            fig.update_traces(textposition="outside")
            fig.update_layout(height=390, margin=dict(l=10, r=10, t=30, b=10), xaxis_title=None, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Нет закрытых багов JustAI.")

# ── ДЕТАЛИЗАЦИЯ ─────────────────────────────────────────────────────────────
with st.expander("Детализация дефектов"):
    show_cols = [
        "Код", "Тема", "Статус", "Приоритет", "Исполнитель",
        DATE_CREATED_COL, DATE_RESOLUTION_COL, "Возраст бага, дней",
        "Бизнес-линия", "Классификация", "JustAI", VERSION_COL, "Метки",
    ]
    show_cols = [c for c in show_cols if c in filtered.columns]
    st.dataframe(filtered[show_cols], use_container_width=True, hide_index=True)
