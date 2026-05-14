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
APPEALS_COL = "Количество обращений"


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
    has_obshee = "общее" in text
    if has_obshee or (has_kb and has_rb):
        return "Общее"
    if has_kb:
        return "КБ"
    if has_rb:
        return "РБ"
    return "Не указано"


def extract_justai(labels):
    return "justai" in str(labels).lower()


@st.cache_data(ttl=300)
def load_data() -> tuple:
    import re as _re
    sheet_date = None
    try:
        import openpyxl
        import io
        import urllib.request
        raw = urllib.request.urlopen(SHEET_URL).read()
        wb = openpyxl.load_workbook(io.BytesIO(raw))
        sheet_name = wb.sheetnames[0]
        # Парсим дату из названия листа вида "... 2026-05-09T23_08_52+0300"
        match = _re.search(r"(\d{4}-\d{2}-\d{2})T(\d{2})_(\d{2})", sheet_name)
        if match:
            sheet_date = f"{match.group(1)} {match.group(2)}:{match.group(3)}"
    except Exception:
        pass

    try:
        df = pd.read_excel(SHEET_URL, header=3)
    except Exception as e:
        st.error(f"Не удалось загрузить данные из Google Sheets: {e}")
        return pd.DataFrame(), sheet_date

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

    return df, sheet_date


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

if st.sidebar.button("🔄 Обновить данные"):
    st.cache_data.clear()

df, sheet_date = load_data()

if df.empty:
    st.error("Нет данных. Проверьте доступ к Google Sheets.")
    st.stop()

updated_at = pd.Timestamp.now().strftime("%d.%m.%Y %H:%M")
sheet_date_str = f"📅 Данные на: **{sheet_date}**  · " if sheet_date else ""
st.caption(f"{sheet_date_str}🔄 Последнее обновление: **{updated_at}**")

st.sidebar.header("Фильтры")

DEFAULT_STATUSES = ["Беклог продукта", "Новый", "В Работе", "На исправление", "Принят к исправлению"]

def multiselect_filter(label, column, default=None, source=None):
    src = source if source is not None else df
    if column not in src.columns:
        return []
    values = sorted([v for v in src[column].dropna().unique() if str(v) != "nan"])
    pre = [v for v in (default or []) if v in values]
    return st.sidebar.multiselect(label, values, default=pre)


business_filter = multiselect_filter("Бизнес-линия", "Бизнес-линия")
classification_filter = multiselect_filter("Классификация", "Классификация")
status_filter = multiselect_filter("Статус", "Статус", default=DEFAULT_STATUSES)
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
        # Закрытые: берём баги у которых дата релиза (из VERSION_COL) попадает в диапазон недели
        def get_release_date(text):
            import re as _re2
            s = str(text).strip()
            m = _re2.search(r"(\d{2})\.(\d{2})\.(\d{4})", s)
            if m:
                try:
                    return pd.Timestamp(f"{m.group(3)}-{m.group(2)}-{m.group(1)}")
                except Exception:
                    pass
            m2 = _re2.search(r"(\d{2})\.(\d{2})\.(\d{2})\b", s)
            if m2:
                try:
                    year = int(m2.group(3))
                    full_year = 2000 + year if year < 50 else 1900 + year
                    return pd.Timestamp(f"{full_year}-{m2.group(2)}-{m2.group(1)}")
                except Exception:
                    pass
            return pd.NaT

        if VERSION_COL in df.columns:
            df_with_rel = df.copy()
            df_with_rel["_rel_date"] = df_with_rel[VERSION_COL].apply(get_release_date)
            w_closed = df_with_rel[
                (df_with_rel["_rel_date"] >= w_start)
                & (df_with_rel["_rel_date"] <= w_end + timedelta(days=1))
                & (df_with_rel["_rel_date"].notna())
            ]
        else:
            w_closed = df.iloc[0:0]

        def parse_appeals(frame):
            col = APPEALS_COL
            if col not in frame.columns:
                return frame.assign(**{col: 0})
            f = frame.copy()
            f[col] = (
                f[col].astype(str).str.strip()
                .str.replace(",", ".", regex=False).str.replace(" ", "", regex=False)
                .pipe(pd.to_numeric, errors="coerce").fillna(0).astype(int)
            )
            return f

        w_new = parse_appeals(w_new)
        w_closed = parse_appeals(w_closed)

        w_new_with = w_new[w_new[APPEALS_COL] > 0]
        w_closed_with = w_closed[w_closed[APPEALS_COL] > 0]

        wk1, wk2 = st.columns(2)
        with wk1:
            st.markdown(f"""
            <div style="background:#161b22;border-radius:12px;padding:1rem 1.25rem;border:1px solid #30363d;">
                <div style="font-size:13px;color:#9da7b3;margin-bottom:4px;">Открыто за неделю</div>
                <div style="font-size:28px;font-weight:500;color:#e6edf3;margin-bottom:12px;">{len(w_new)}</div>
                <div style="height:1px;background:#30363d;margin-bottom:12px;"></div>
                <div style="display:flex;justify-content:space-between;align-items:flex-end;">
                    <div>
                        <div style="font-size:12px;color:#9da7b3;margin-bottom:4px;">из них с обращениями</div>
                        <div style="font-size:20px;font-weight:500;color:#f85149;">{len(w_new_with)} дефекта</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:12px;color:#9da7b3;margin-bottom:4px;">всего обращений</div>
                        <div style="font-size:20px;font-weight:500;color:#f85149;">{int(w_new_with[APPEALS_COL].sum()) if not w_new_with.empty else 0}</div>
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)

        with wk2:
            st.markdown(f"""
            <div style="background:#161b22;border-radius:12px;padding:1rem 1.25rem;border:1px solid #30363d;">
                <div style="font-size:13px;color:#9da7b3;margin-bottom:4px;">Закрыто за неделю</div>
                <div style="font-size:28px;font-weight:500;color:#e6edf3;margin-bottom:12px;">{len(w_closed)}</div>
                <div style="height:1px;background:#30363d;margin-bottom:12px;"></div>
                <div style="display:flex;justify-content:space-between;align-items:flex-end;">
                    <div>
                        <div style="font-size:12px;color:#9da7b3;margin-bottom:4px;">из них с обращениями</div>
                        <div style="font-size:20px;font-weight:500;color:#3fb950;">{len(w_closed_with)} дефекта</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:12px;color:#9da7b3;margin-bottom:4px;">всего обращений</div>
                        <div style="font-size:20px;font-weight:500;color:#3fb950;">{int(w_closed_with[APPEALS_COL].sum()) if not w_closed_with.empty else 0}</div>
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)

        if not w_new.empty:
            wc1, wc2, wc3 = st.columns(3)

            def stacked_bar(frame, group_col, orient="v", height=350):
                acol = APPEALS_COL
                with_appeals = frame[frame[acol] > 0].groupby(group_col).size().reset_index(name="С обращениями")
                without_appeals = frame[frame[acol] == 0].groupby(group_col).size().reset_index(name="Без обращений")
                merged = pd.merge(without_appeals, with_appeals, on=group_col, how="outer").fillna(0)
                merged["С обращениями"] = merged["С обращениями"].astype(int)
                merged["Без обращений"] = merged["Без обращений"].astype(int)
                merged["Всего"] = merged["С обращениями"] + merged["Без обращений"]
                merged = merged.sort_values("Всего", ascending=(orient == "h"))
                fig = px.bar(
                    merged, x="Всего" if orient == "h" else group_col,
                    y=group_col if orient == "h" else "Всего",
                    orientation=orient,
                    color_discrete_sequence=["#378ADD"],
                )
                if not merged[merged["С обращениями"] > 0].empty:
                    fig2 = px.bar(
                        merged, x="С обращениями" if orient == "h" else group_col,
                        y=group_col if orient == "h" else "С обращениями",
                        orientation=orient,
                        color_discrete_sequence=["#f85149"],
                    )
                    fig.add_traces(fig2.data)
                fig.update_layout(
                    height=height,
                    barmode="overlay",
                    margin=dict(l=10, r=10, t=10, b=10),
                    xaxis_title=None, yaxis_title=None,
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5,
                                itemsizing="constant", font=dict(size=11)),
                )
                fig.data[0].name = "Без обращений"
                if len(fig.data) > 1:
                    fig.data[1].name = "С обращениями"
                return fig

            with wc1:
                st.subheader("По категориям")
                st.plotly_chart(stacked_bar(w_new, "Классификация", orient="h"), use_container_width=True, key=f"chart_cat_{label}")

            with wc2:
                st.subheader("По приоритетам")
                st.plotly_chart(stacked_bar(w_new, "Приоритет", orient="v"), use_container_width=True, key=f"chart_pri_{label}")

            with wc3:
                st.subheader("По бизнес-линиям")
                st.plotly_chart(stacked_bar(w_new, "Бизнес-линия", orient="v"), use_container_width=True, key=f"chart_bl_{label}")
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
        st.plotly_chart(fig, use_container_width=True, key="chart_1")
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
        st.plotly_chart(fig, use_container_width=True, key="chart_2")
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
        st.plotly_chart(fig, use_container_width=True, key="chart_3")

with col4:
    st.subheader("Баги по бизнес-линиям")
    business = (
        filtered.groupby("Бизнес-линия").size()
        .reset_index(name="Количество")
        .sort_values("Количество", ascending=False)
    )
    fig = bar_with_pct(business, "Бизнес-линия", "Количество", "")
    if fig:
        st.plotly_chart(fig, use_container_width=True, key="chart_4")

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
        st.plotly_chart(fig, use_container_width=True, key="chart_5")

with col6:
    st.subheader("Классификация × Бизнес-линия")
    matrix = (
        filtered.groupby(["Классификация", "Бизнес-линия"]).size()
        .reset_index(name="Количество")
    )
    if not matrix.empty:
        fig = px.density_heatmap(matrix, x="Бизнес-линия", y="Классификация", z="Количество", text_auto=True)
        fig.update_layout(height=470, margin=dict(l=10, r=10, t=30, b=10), xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True, key="chart_6")
    else:
        st.info("Нет данных для матрицы.")

# ── JUSTAI ──────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🤖 Баги на стороне вендора (JustAI)</div>', unsafe_allow_html=True)

justai_df = filtered[filtered["JustAI"] == True]

if justai_df.empty:
    st.info("Нет активных багов с меткой JustAI.")
else:
    jc1, jc2, jc5 = st.columns(3)
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
            st.plotly_chart(fig, use_container_width=True, key="chart_7")

    with jc5:
        st.subheader("По приоритетам")
        jpri = (
            justai_df.groupby("Приоритет").size()
            .reset_index(name="Количество")
            .sort_values("Количество", ascending=False)
        )
        fig = bar_with_pct(jpri, "Приоритет", "Количество", "", height=390)
        if fig:
            st.plotly_chart(fig, use_container_width=True, key="chart_justai_pri")

    with jc2:
        st.subheader("По категориям")
        jcat = (
            justai_df.groupby("Классификация").size()
            .reset_index(name="Количество")
            .sort_values("Количество", ascending=True)
        )
        fig = bar_with_pct(jcat, "Количество", "Классификация", "", orientation="h", height=390)
        if fig:
            st.plotly_chart(fig, use_container_width=True, key="chart_8")

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
            st.plotly_chart(fig, use_container_width=True, key="chart_9")

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
            st.plotly_chart(fig, use_container_width=True, key="chart_10")
        else:
            st.info("Нет закрытых багов JustAI.")

# ── ВЛИЯНИЕ НА ПОЛЬЗОВАТЕЛЕЙ ────────────────────────────────────────────────
st.markdown('<div class="section-title">🔥 Влияние дефектов на пользователей</div>', unsafe_allow_html=True)

if APPEALS_COL not in filtered.columns:
    st.info(f"Колонка «{APPEALS_COL}» не найдена в данных.")
else:
    impact_df = filtered.copy()
    impact_df[APPEALS_COL] = (
        impact_df[APPEALS_COL]
        .astype(str)
        .str.strip()
        .str.replace(",", ".", regex=False)
        .str.replace(" ", "", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
        .astype(int)
    )
    impact_df = impact_df[impact_df[APPEALS_COL] > 0]

    if impact_df.empty:
        st.info("Нет дефектов с заполненным полем обращений.")
    else:
        total_appeals = int(impact_df[APPEALS_COL].sum())
        bugs_with_appeals = len(impact_df)
        avg_appeals = total_appeals / bugs_with_appeals if bugs_with_appeals else 0
        top_cat_appeals = (
            impact_df.groupby("Классификация")[APPEALS_COL].sum().idxmax()
            if not impact_df.empty else "—"
        )

        im1, im2, im3, im4 = st.columns(4)
        im1.metric("Всего обращений", total_appeals)
        im2.metric("Багов с обращениями", bugs_with_appeals)
        im3.metric("Топ категория", top_cat_appeals)
        im4.metric("Среднее на баг", f"{avg_appeals:.1f}")

        ic1, ic2 = st.columns(2)

        with ic1:
            st.subheader("Обращения по бизнес-линиям")
            bl_appeals = (
                impact_df.groupby("Бизнес-линия")[APPEALS_COL].sum()
                .reset_index()
                .sort_values(APPEALS_COL, ascending=True)
            )
            total_bl = bl_appeals[APPEALS_COL].sum()
            bl_appeals["label"] = bl_appeals[APPEALS_COL].apply(
                lambda v: f"{v} ({v/total_bl*100:.1f}%)" if total_bl else str(v)
            )
            bl_color_map = {"КБ": "#378ADD", "РБ": "#1D9E75", "Общее": "#EF9F27", "Не указано": "#888780"}
            fig = px.bar(
                bl_appeals,
                x=APPEALS_COL,
                y="Бизнес-линия",
                orientation="h",
                text="label",
                color="Бизнес-линия",
                color_discrete_map=bl_color_map,
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                height=420,
                margin=dict(l=10, r=120, t=30, b=10),
                xaxis_title="Обращений",
                yaxis_title=None,
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True, key="chart_11")

        with ic2:
            st.subheader("Обращения по категориям")
            cat_appeals = (
                impact_df.groupby("Классификация")[APPEALS_COL].sum()
                .reset_index()
                .sort_values(APPEALS_COL, ascending=True)
            )
            total_cat = cat_appeals[APPEALS_COL].sum()
            cat_appeals["label"] = cat_appeals[APPEALS_COL].apply(
                lambda v: f"{v} ({v/total_cat*100:.1f}%)" if total_cat else str(v)
            )
            fig = px.bar(
                cat_appeals,
                x=APPEALS_COL,
                y="Классификация",
                orientation="h",
                text="label",
                color_discrete_sequence=["#378ADD"],
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                height=420,
                margin=dict(l=10, r=120, t=30, b=10),
                xaxis_title="Обращений",
                yaxis_title=None,
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True, key="chart_12")

        # Динамика открытия и закрытия багов с обращениями
        id1, id2 = st.columns(2)

        with id1:
            st.subheader("Динамика открытия (с обращениями)")
            if DATE_CREATED_COL in impact_df.columns and impact_df[DATE_CREATED_COL].notna().any():
                open_dyn = (
                    impact_df.dropna(subset=[DATE_CREATED_COL])
                    .assign(week=lambda x: x[DATE_CREATED_COL].dt.to_period("W").dt.start_time)
                    .groupby("week").agg(
                        Багов=("Код", "count"),
                        Обращений=(APPEALS_COL, "sum")
                    )
                    .reset_index()
                )
                fig = px.bar(
                    open_dyn, x="week", y="Обращений",
                    text="Обращений",
                    color_discrete_sequence=["#f85149"],
                    hover_data={"Багов": True},
                )
                fig.update_traces(textposition="outside")
                fig.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=10), xaxis_title=None, showlegend=False)
                st.plotly_chart(fig, use_container_width=True, key="chart_13")
            else:
                st.info("Нет данных по дате создания.")

        with id2:
            st.subheader("Динамика закрытия (с обращениями)")
            # Берём все закрытые баги с обращениями из полного df
            impact_all = df.copy()
            impact_all[APPEALS_COL] = (
                impact_all[APPEALS_COL].astype(str).str.strip()
                .str.replace(",", ".", regex=False).str.replace(" ", "", regex=False)
                .pipe(pd.to_numeric, errors="coerce").fillna(0).astype(int)
            )
            impact_closed = impact_all[
                (impact_all[APPEALS_COL] > 0)
                & (impact_all["Статус"].astype(str).isin(CLOSED_STATUSES))
            ]
            if DATE_RESOLUTION_COL in impact_closed.columns and impact_closed[DATE_RESOLUTION_COL].notna().any():
                close_dyn = (
                    impact_closed.dropna(subset=[DATE_RESOLUTION_COL])
                    .assign(week=lambda x: x[DATE_RESOLUTION_COL].dt.to_period("W").dt.start_time)
                    .groupby("week").agg(
                        Багов=("Код", "count"),
                        Обращений=(APPEALS_COL, "sum")
                    )
                    .reset_index()
                )
                fig = px.bar(
                    close_dyn, x="week", y="Обращений",
                    text="Обращений",
                    color_discrete_sequence=["#238636"],
                    hover_data={"Багов": True},
                )
                fig.update_traces(textposition="outside")
                fig.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=10), xaxis_title=None, showlegend=False)
                st.plotly_chart(fig, use_container_width=True, key="chart_14")
            else:
                st.info("Нет закрытых багов с обращениями.")

        st.subheader("Топ дефектов по количеству обращений")
        top_bugs = impact_df.sort_values(APPEALS_COL, ascending=False).head(20)
        show_impact_cols = ["Тема", APPEALS_COL, "Приоритет", "Классификация", "Бизнес-линия"]
        show_impact_cols = [c for c in show_impact_cols if c in top_bugs.columns]
        st.dataframe(
            top_bugs[show_impact_cols].reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Тема": st.column_config.TextColumn("Название бага", width="large"),
                APPEALS_COL: st.column_config.NumberColumn("Кол-во обращений", format="%d"),
                "Приоритет": st.column_config.TextColumn("Приоритет"),
                "Классификация": st.column_config.TextColumn("Категория"),
                "Бизнес-линия": st.column_config.TextColumn("Бизнес-линия"),
            },
        )

# ── ПЛАНЫ ПО РЕЛИЗАМ ────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🚀 Планы исправления по релизам</div>', unsafe_allow_html=True)

if VERSION_COL not in filtered.columns:
    st.info(f"Колонка «{VERSION_COL}» не найдена в данных.")
else:
    import re as _re

    def parse_release(text):
        """Возвращает (дата или None, исходный текст)"""
        s = str(text).strip()
        if not s or s.lower() in ("nan", "none", ""):
            return None, None
        # Пробуем ДД.ММ.ГГГГ (4-значный год)
        m = _re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
        if m:
            try:
                dt = pd.Timestamp(f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}")
                return dt, s
            except Exception:
                pass
        # Пробуем ДД.ММ.ГГ (2-значный год) — только если явно написано как дата
        m2 = _re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2})\b", s)
        if m2:
            try:
                year = int(m2.group(3))
                full_year = 2000 + year if year < 50 else 1900 + year
                dt = pd.Timestamp(f"{full_year}-{m2.group(2).zfill(2)}-{m2.group(1).zfill(2)}")
                return dt, s
            except Exception:
                pass
        return None, s

    rel_df = df[df[VERSION_COL].notna()].copy()
    rel_df["_rel_label"] = rel_df[VERSION_COL].astype(str).str.strip()
    rel_df = rel_df[rel_df["_rel_label"].str.lower() != "nan"]

    if rel_df.empty:
        st.info("Нет дефектов с заполненным полем версии.")
    else:
        # Собираем уникальные релизы
        releases = []
        for label in rel_df["_rel_label"].unique():
            dt, display = parse_release(label)
            if display:
                releases.append({"label": label, "display": display, "date": dt})

        # Сортируем: сначала с датой по возрастанию, потом без даты
        releases.sort(key=lambda r: (r["date"] is None, r["date"] or pd.Timestamp.max))

        # Убираем релизы старше 2 недель (без даты показываем всегда)
        two_weeks_ago = today - timedelta(weeks=2)
        releases = [r for r in releases if r["date"] is None or r["date"] >= two_weeks_ago]

        # Цвета шапок карточек
        header_colors = [
            ("#0c447c", "#85b7eb", "#e6f1fb"),
            ("#27500a", "#97c459", "#eaf3de"),
            ("#3c3489", "#afa9ec", "#eeedfe"),
            ("#633806", "#ef9f27", "#faeeda"),
            ("#791f1f", "#f09595", "#fcebeb"),
        ]

        priority_colors = {
            "Блокирующий": "#e24b4a",
            "Критичный":   "#ef9f27",
            "Средний":     "#378add",
            "Низкий":      "#888780",
            "Незначительный": "#b4b2a9",
        }
        bl_styles = {
            "КБ":         "background:#e6f1fb;color:#0c447c;",
            "РБ":         "background:#eaf3de;color:#27500a;",
            "Общее":      "background:#faeeda;color:#633806;",
            "Не указано": "background:#f1efe8;color:#5f5e5a;",
        }

        cols = st.columns(min(len(releases), 3))

        for idx, rel in enumerate(releases):
            col = cols[idx % 3]
            bg, sub_c, title_c = header_colors[idx % len(header_colors)]

            r_bugs = rel_df[rel_df["_rel_label"] == rel["label"]]

            # Обращения
            if APPEALS_COL in r_bugs.columns:
                appeals_vals = (
                    r_bugs[APPEALS_COL].astype(str).str.strip()
                    .str.replace(",", ".", regex=False).str.replace(" ", "", regex=False)
                    .pipe(pd.to_numeric, errors="coerce").fillna(0)
                )
                total_appeals = int(appeals_vals.sum())
            else:
                total_appeals = 0

            total_bugs = len(r_bugs)

            # Приоритеты
            pri_counts = r_bugs["Приоритет"].value_counts() if "Приоритет" in r_bugs.columns else pd.Series(dtype=int)
            pri_max = pri_counts.max() if not pri_counts.empty else 1

            pri_html = ""
            for pri_name in ["Блокирующий", "Критичный", "Средний", "Низкий", "Незначительный"]:
                cnt = int(pri_counts.get(pri_name, 0))
                if cnt == 0:
                    continue
                pct = int(cnt / pri_max * 100)
                clr = priority_colors.get(pri_name, "#888780")
                pri_html += f"""
                <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
                  <span style="font-size:11px;color:#9da7b3;width:90px;flex-shrink:0;">{pri_name}</span>
                  <div style="flex:1;height:10px;background:#21262d;border-radius:4px;overflow:hidden;">
                    <div style="width:{pct}%;height:100%;background:{clr};border-radius:4px;"></div>
                  </div>
                  <span style="font-size:11px;color:#9da7b3;width:18px;text-align:right;">{cnt}</span>
                </div>"""

            # Бизнес-линии
            bl_counts = r_bugs["Бизнес-линия"].value_counts() if "Бизнес-линия" in r_bugs.columns else pd.Series(dtype=int)
            bl_html = ""
            for bl_name, cnt in bl_counts.items():
                sty = bl_styles.get(bl_name, "background:#f1efe8;color:#5f5e5a;")
                bl_html += f'<span style="{sty}font-size:11px;padding:3px 8px;border-radius:6px;">{bl_name}: {cnt}</span>'

            # Топ категорий
            cat_counts = r_bugs["Классификация"].value_counts().head(3) if "Классификация" in r_bugs.columns else pd.Series(dtype=int)
            cat_html = ""
            for cat_name, cnt in cat_counts.items():
                cat_html += f"""
                <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px;">
                  <span style="color:#e6edf3;">{cat_name}</span>
                  <span style="color:#9da7b3;">{cnt}</span>
                </div>"""

            date_str = rel["date"].strftime("%d.%m.%Y") if rel["date"] else ""
            display_label = rel["display"]

            with col:
                st.markdown(f"""
                <div style="background:#161b22;border:1px solid #30363d;border-radius:12px;overflow:hidden;margin-bottom:16px;">
                  <div style="background:{bg};padding:12px 16px;display:flex;justify-content:space-between;align-items:center;">
                    <div>
                      <div style="font-size:11px;color:{sub_c};margin-bottom:2px;">Версия</div>
                      <div style="font-size:15px;font-weight:500;color:{title_c};">{display_label}</div>
                    </div>
                    {"<div style='text-align:right;'><div style='font-size:11px;color:" + sub_c + ";margin-bottom:2px;'>Дата</div><div style='font-size:13px;font-weight:500;color:" + title_c + ";'>" + date_str + "</div></div>" if date_str else ""}
                  </div>
                  <div style="padding:12px 16px;">
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px;">
                      <div style="background:#21262d;border-radius:8px;padding:8px 10px;text-align:center;">
                        <div style="font-size:11px;color:#9da7b3;">Всего багов</div>
                        <div style="font-size:22px;font-weight:500;color:#e6edf3;">{total_bugs}</div>
                      </div>
                      <div style="background:#21262d;border-radius:8px;padding:8px 10px;text-align:center;">
                        <div style="font-size:11px;color:#9da7b3;">Обращений</div>
                        <div style="font-size:22px;font-weight:500;color:#e6edf3;">{total_appeals}</div>
                      </div>
                    </div>
                    <div style="font-size:12px;color:#9da7b3;margin-bottom:6px;">По приоритетам</div>
                    {pri_html}
                    <div style="font-size:12px;color:#9da7b3;margin:10px 0 6px;">По бизнес-линиям</div>
                    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px;">{bl_html}</div>
                    <div style="font-size:12px;color:#9da7b3;margin-bottom:6px;">Топ категорий</div>
                    {cat_html}
                  </div>
                </div>
                """, unsafe_allow_html=True)

# ── ДЕТАЛИЗАЦИЯ ─────────────────────────────────────────────────────────────
with st.expander("Детализация дефектов"):
    show_cols = [
        "Код", "Тема", "Статус", "Приоритет", "Исполнитель",
        DATE_CREATED_COL, DATE_RESOLUTION_COL, "Возраст бага, дней",
        "Бизнес-линия", "Классификация", "JustAI", VERSION_COL, "Метки",
    ]
    show_cols = [c for c in show_cols if c in filtered.columns]
    st.dataframe(filtered[show_cols], use_container_width=True, hide_index=True)
