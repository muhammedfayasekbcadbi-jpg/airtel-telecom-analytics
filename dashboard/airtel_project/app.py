"""Airtel Telecom Analytics - two dashboards (Streamlit), same format as the PDFs
  1) Retention & Circle Analysis   (Overview | Circle Analysis)
  2) Domain B: Revenue             (1. Overview | 2. Detail)
Run:  pip install -r requirements.txt   ->   streamlit run airtel_streamlit_app.py
Keep airtel.db in the same folder as this file."""
import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

st.set_page_config(page_title="Airtel Telecom Analytics", page_icon="📶", layout="wide", initial_sidebar_state="expanded")
RED, PINK, DARK = "#d90f1f", "#f2a6ad", "#1d1517"
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
MC = [f"m{i}" for i in range(1, 7)]

OFF1, OFF2, OFF3 = 292, 372, 382   # pixels used by header, tabs, filters row, cards
st.markdown(f"""<style>
header[data-testid="stHeader"], footer, #MainMenu{{display:none !important}}
.block-container{{padding:.5rem 1rem 0 1rem !important;max-width:100%}}
div[data-testid="stVerticalBlock"]{{gap:.35rem}}
.hdr{{background:linear-gradient(100deg,#a70a16,#e5101f);color:#fff;padding:7px 18px;border-radius:10px;margin-bottom:2px;display:flex;align-items:center;gap:14px}}
.hdr .logo{{font-size:22px;font-weight:800;padding-right:14px;border-right:1px solid #fff7}}
.hdr h1{{margin:0;font-size:17px;color:#fff;padding:0;line-height:1.1}} .hdr span{{opacity:.88;font-size:11.5px}}
.kpi{{background:#fdf1f2;border:1px solid #e8dfe0;border-radius:10px;padding:6px 12px;color:#22181a;line-height:1.15}}
.kpi .l{{font-size:11px;color:#74666a}} .kpi .v{{font-size:22px;font-weight:700}} .kpi .s{{font-size:10.5px;color:#74666a}}
.bar{{background:{DARK};color:#fff;border-radius:8px;padding:6px 14px;font-size:12.5px}}
.banner{{background:#fff;border:1px solid #e8dfe0;border-radius:8px;padding:5px 12px;color:#74666a;font-size:12.5px}}
[class*="st-key-one_"] [data-testid="stFullScreenFrame"],[class*="st-key-two_"] [data-testid="stFullScreenFrame"],[class*="st-key-det_"] [data-testid="stFullScreenFrame"]{{height:auto !important}}
[class*="st-key-one_"] [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"]),[class*="st-key-two_"] [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"]),[class*="st-key-det_"] [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"]){{height:auto !important;min-height:0 !important;flex:0 0 auto !important}}
[data-testid="stMain"] [data-testid="stElementContainer"],[data-testid="stMain"] [data-testid="stMarkdownContainer"],[data-testid="stMain"] [data-testid="stSelectbox"]{{flex-shrink:0 !important}}
[data-testid="stMain"] [data-testid="stMarkdown"],[data-testid="stMain"] [data-testid="stElementContainer"]:has(.kpi),[data-testid="stMain"] [data-testid="stElementContainer"]:has(.banner),[data-testid="stMain"] [data-testid="stElementContainer"]:has(.bar){{height:auto !important;min-height:0 !important;flex:0 0 auto !important}}
.kpi,.banner,.bar,.hdr{{margin-bottom:0 !important}}
[data-testid="stMarkdownContainer"],[data-testid="stMarkdownContainer"] > div{{margin-bottom:0 !important}}
/* every chart row is sized from the browser height, so nothing needs scrolling */
[class*="st-key-one_"] [data-testid="stPlotlyChart"]{{height:calc(100vh - {OFF1}px) !important}}
[class*="st-key-two_"] [data-testid="stPlotlyChart"]{{height:calc((100vh - {OFF2}px) / 2) !important}}
[class*="st-key-det_"] [data-testid="stPlotlyChart"]{{height:calc(100vh - {OFF3}px) !important}}
.st-key-two_tk{{height:calc((100vh - {OFF2}px) / 2) !important;overflow:auto}}
.st-key-one_tk{{height:calc(100vh - {OFF1}px) !important;overflow:auto}}
button[data-baseweb="tab"]{{padding:4px 14px;height:32px}} div[data-baseweb="tab-list"]{{gap:4px}}
</style>""", unsafe_allow_html=True)




FEATURES_SQL = """SELECT customer_id, circle_name, region, connection_type AS k, plan_name, age_band,
                  churn_date, recency_days, unresolved_count, stated_arpu FROM customer_features"""
# used automatically when the database has no customer_features table (built from the raw tables instead)
RAW_SQL = """SELECT c.customer_id, ci.circle_name, ci.region, c.connection_type AS k, p.plan_name, c.age_band,
       c.churn_date, c.arpu_inr AS stated_arpu,
       COALESCE(q.n_open, 0) AS unresolved_count,
       CAST(julianday('2025-06-30') - julianday(u.last_usage) AS INT) AS recency_days
FROM customers c
JOIN circles ci ON ci.circle_id = c.circle_id
JOIN plans p ON p.plan_id = c.current_plan_id
LEFT JOIN (SELECT customer_id, COUNT(*) AS n_open FROM complaints WHERE is_resolved = 0 GROUP BY customer_id) q
       ON q.customer_id = c.customer_id
LEFT JOIN (SELECT customer_id, MAX(usage_date) AS last_usage FROM usage_daily GROUP BY customer_id) u
       ON u.customer_id = c.customer_id"""


@st.cache_data
def load(path=None):
    app_dir = Path(__file__).resolve().parent
    candidates = [
        Path(path) if path else app_dir / "airtel.db",
        app_dir.parent.parent / "data" / "raw" / "airtel.db",
        app_dir.parent / "airtel.db",
    ]
    path = next((candidate for candidate in candidates
                 if candidate.exists() and candidate.stat().st_size >= 1_000_000), None)
    if path is None:
        st.error("Database not found (or empty).\n\n"
                 "Place the real airtel.db (about 120 MB) in data/raw or beside app.py, then rerun.")
        st.stop()
    con = sqlite3.connect(path)
    tables = {x[0] for x in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    need = {"customers", "circles", "plans", "recharges"}
    if not need <= tables:
        st.error(f"This airtel.db is missing tables {sorted(need - tables)}. Found: {sorted(tables)}")
        st.stop()
    df = pd.read_sql(FEATURES_SQL if "customer_features" in tables else RAW_SQL, con)
    r = pd.read_sql("""SELECT customer_id, CAST(substr(recharge_date,6,2) AS INT) AS m, SUM(amount_inr) AS a
                       FROM recharges WHERE recharge_date BETWEEN '2025-01-01' AND '2025-06-30'
                       GROUP BY 1,2""", con)
    con.close()
    pv = r.pivot(index="customer_id", columns="m", values="a").reindex(columns=range(1, 7)).fillna(0)
    pv.columns = MC
    df = df.join(pv, on="customer_id")
    df["recency_days"] = df["recency_days"].fillna(999)
    df["cm"] = pd.to_datetime(df["churn_date"]).dt.month          # churn month (NaN = retained)
    df["rev"] = df[MC].sum(axis=1)
    df["risk"] = ((df.unresolved_count > 0) | (df.recency_days > 30)).astype(int)
    for column in ("circle_name", "region", "k", "plan_name", "age_band"):
        df[column] = df[column].astype("category")
    return df


def kpi(col, label, val, sub="", color="#22181a"):
    col.markdown(f'<div class="kpi"><div class="l">{label}</div><div class="v" style="color:{color}">{val}</div>'
                 f'<div class="s">{sub}</div></div>', unsafe_allow_html=True)


def churn(d, f=1, t=6):
    """base = customers still subscribed at the start of month f; churned = churn month in [f, t]."""
    b = d[d.cm.isna() | (d.cm >= f)]
    c = int(((b.cm >= f) & (b.cm <= t)).sum())
    return len(b), c, (c / len(b) if len(b) else 0.0)


def header(title, sub):
    st.markdown(f'<div class="hdr"><div class="logo">airtel</div><div><h1>{title}</h1><span>{sub}</span></div></div>',
                unsafe_allow_html=True)


mm = lambda v: f"₹{v / 1e6:.2f}M"
df = load()
page = "Domain B: Revenue"
st.sidebar.markdown("## **airtel**")
st.sidebar.header("Filters")
circle = st.sidebar.selectbox("Circle", ["All Circles"] + sorted(df.circle_name.unique()), key="filter_circle")
region = st.sidebar.selectbox("Region", ["All Regions"] + sorted(df.region.unique()), key="filter_region")
conn = st.sidebar.selectbox("Connection Type", ["All", "Prepaid", "Postpaid"], key="filter_connection")
seg = st.sidebar.selectbox("Customer segment (age)", ["All Segments"] + sorted(df.age_band.unique()), key="filter_segment")
plan = st.sidebar.selectbox("Plan", ["All Plans"] + sorted(df.plan_name.unique()), key="filter_plan")
f_m, t_m = st.sidebar.select_slider("Month range (2025)", MON, value=("Jan", "Jun"), key="filter_month")
f, t = MON.index(f_m) + 1, MON.index(t_m) + 1
MS = MON[f - 1:t]                                   # selected months

if st.sidebar.button("Reset all filters", width="stretch"):
    st.session_state["filter_circle"] = "All Circles"
    st.session_state["filter_region"] = "All Regions"
    st.session_state["filter_connection"] = "All"
    st.session_state["filter_segment"] = "All Segments"
    st.session_state["filter_plan"] = "All Plans"
    st.session_state["filter_month"] = ("Jan", "Jun")
    st.rerun()
base = df
@st.cache_data(show_spinner=False)
def apply_filters(data, circle, region, conn, seg, plan, f, t):
    filtered = data
    if region != "All Regions":
        filtered = filtered[filtered.region == region]
    if conn != "All":
        filtered = filtered[filtered.k == conn]
    if seg != "All Segments":
        filtered = filtered[filtered.age_band == seg]
    if plan != "All Plans":
        filtered = filtered[filtered.plan_name == plan]
    if circle != "All Circles":
        filtered = filtered[filtered.circle_name == circle]
    filtered = filtered.assign(r=filtered[MC[f - 1:t]].sum(axis=1))
    return filtered

sel = apply_filters(df, circle, region, conn, seg, plan, f, t)
if sel.empty:
    st.warning("No customers for this filter combination - change a filter."); st.stop()
M, NM = 1e6, t - f + 1
TYPES = [x for x in ["Prepaid", "Postpaid"] if (sel.k == x).any()]


def tidy(fig, title=None, **kw):
    fig.update_layout(autosize=True, height=None, margin=dict(t=30 if title else 6, b=6, l=8, r=8), font=dict(size=11),
                      title=dict(text=title, font=dict(size=13), x=0.01, y=.97) if title else None,
                      legend=dict(orientation="h", y=.99, yanchor="top", x=.99, xanchor="right", title=None, bgcolor="rgba(255,255,255,.7)"), **kw)
    return fig


def show(col, fig):
    col.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


# =====================================================================
# 1) RETENTION & CIRCLE ANALYSIS
# =====================================================================
if page == "Retention & Circle Analysis":
    header("Airtel Telecom Analytics", f"Retention & Circle Analysis Dashboard · {f_m}–{t_m} 2025")
    n, ch, rate = churn(sel, f, t)
    ret = sel[sel.cm.isna() | (sel.cm > t)]
    risk, tickets = int(ret.risk.sum()), int(ret.unresolved_count.sum())
    k = st.columns(4)
    kpi(k[0], "Total Subscribers", f"{n:,}", "At start of period")
    kpi(k[1], "Churn Rate", f"{rate:.1%}", f"{ch:,} churned in {f_m}–{t_m}", RED)
    kpi(k[2], "Retained Subscribers", f"{n - ch:,}", f"{1 - rate:.1%} retention")
    kpi(k[3], "Open Tickets", f"{tickets:,}", "Unresolved complaints (retained)")

    cb = base                                              # circle comparison ignores only the Circle filter
    rows = []
    for c, g in cb.groupby("circle_name"):
        rows.append({"Circle": c, "Overall": churn(g, f, t)[2] * 100,
                     **{x: churn(g[g.k == x], f, t)[2] * 100 for x in TYPES},
                     **{m: churn(g, i + 1, i + 1)[2] * 100 for i, m in enumerate(MON)}})
    circ = pd.DataFrame(rows).sort_values("Overall", ascending=False).reset_index(drop=True)
    view = circ if circle == "All Circles" else circ[circ.Circle == circle]
    top, low = circ.iloc[0], circ.iloc[-1]
    pre, post = churn(sel[sel.k == "Prepaid"], f, t)[2], churn(sel[sel.k == "Postpaid"], f, t)[2]
    pk = MON[int(sel.cm.value_counts().idxmax()) - 1] if sel.cm.notna().any() else "-"
    tks = [f"**{top.Circle}** has the highest churn at {top.Overall:.1f}%; lowest is {low.Circle} at {low.Overall:.1f}%."]
    if len(TYPES) == 2:
        tks.append(f"Prepaid churn is {abs(pre - post) * 100:.1f} pp {'higher' if pre >= post else 'lower'} than postpaid "
                   f"({pre:.1%} vs {post:.1%}).")
    tks += [f"Churn peaks in **{pk}** 2025 for the selected filters.",
            f"**{risk:,}** retained subscribers are at risk and need retention focus."]

    def takeaways(key):
        with st.container(key=key, border=True):
            st.markdown("**🎯 Key Takeaways**")
            for i, x in enumerate(tks, 1): st.markdown(f"{i}. {x}")

    tab1, tab2 = st.tabs(["Overview", "Circle Analysis"])
    with tab1:
        with st.container(key="two_a"):
            a, b = st.columns([3, 2])
            mon = pd.DataFrame([{"Month": MON[i - 1], "Type": kt, "Churn %": churn(sel[sel.k == kt], i, i)[2] * 100}
                                for kt in TYPES for i in range(f, t + 1)])
            show(a, tidy(px.line(mon, x="Month", y="Churn %", color="Type", markers=True,
                                 color_discrete_map={"Prepaid": RED, "Postpaid": PINK}),
                         "Monthly churn rate – Prepaid vs Postpaid", yaxis_ticksuffix="%"))
            fn = go.Figure(go.Funnel(y=["Total", "Retained", "At-Risk", "Churned"], x=[n, n - ch, risk, ch],
                                     marker=dict(color=["#a70a16", RED, "#ee5560", PINK]), textinfo="value+percent initial"))
            show(b, tidy(fn, "Retention Funnel"))
        with st.container(key="two_b"):
            a, b = st.columns([3, 2])
            sg = pd.DataFrame([{"Segment": s_, "Churn %": churn(g, f, t)[2] * 100} for s_, g in sel.groupby("age_band")])
            show(a, tidy(px.bar(sg, x="Segment", y="Churn %", text_auto=".1f", color_discrete_sequence=[RED]),
                         "Churn rate by customer segment", yaxis_ticksuffix="%"))
            with b: takeaways("two_tk")
    with tab2:
        with st.container(key="one_c"):
            a, b, c3 = st.columns([5, 4, 3])
            lg = view.melt(id_vars="Circle", value_vars=TYPES, var_name="Type", value_name="Churn %")
            show(a, tidy(px.bar(lg, x="Circle", y="Churn %", color="Type", barmode="group",
                                color_discrete_map={"Prepaid": RED, "Postpaid": PINK}),
                         "Churn rate by connection type across circles", yaxis_ticksuffix="%", xaxis_tickangle=-60,
                         xaxis_title=None))
            show(b, tidy(px.imshow(view.set_index("Circle")[MON], text_auto=".0f", aspect="auto",
                                   color_continuous_scale=["#fde4e6", PINK, RED, "#8a0610"]),
                         "Churn heatmap (Circle × Month, %)", coloraxis_showscale=False))
            with c3: takeaways("one_tk")
    st.markdown(f'<div class="bar"><b>Overall Insight:</b> {rate:.1%} of subscribers churned in {f_m}–{t_m} 2025, '
                f'with {top.Circle} the key focus area for retention initiatives.</div>', unsafe_allow_html=True)

# =====================================================================
# 2) DOMAIN B: REVENUE
# =====================================================================
else:
    ref = float(round(sel.stated_arpu.mean(), 2))
    header("Airtel Telecom Analytics – Domain B: Revenue", "Member 1 – Dashboard Structure")
    tab1, tab2 = st.tabs(["1. Overview", "2. Detail"])

    def trend_fig(d, title):
        y = d[MC[f - 1:t]].sum().values / M
        g = go.Figure(go.Scatter(x=MS, y=y, mode="lines+markers+text", text=[f"{v:.2f}" for v in y],
                                 textposition="top center", line=dict(color=RED, width=3), marker=dict(size=7)))
        return tidy(g, title, yaxis_title="Revenue (₹M)", yaxis_range=[0, max(y.max() * 1.25, .1)])

    @st.cache_data(show_spinner=False)
    def overview_metrics(data, ref_value, start_month, end_month):
        arpu_values = data["r"] / (end_month - start_month + 1)
        mu = float(arpu_values.mean())
        p2 = stats.ttest_1samp(arpu_values, ref_value)[1] if len(arpu_values) > 2 else 1
        p = p2 / 2
        up = mu >= ref_value
        return mu, p, up

    with tab1:
        st.markdown('<div class="banner">This dashboard helps the Head of Finance understand <b>received revenue</b>, '
                    'revenue patterns and revenue comparisons.</div>', unsafe_allow_html=True)
        mu, p, up = overview_metrics(sel, ref, f, t)
        k = st.columns(3)
        kpi(k[0], f"👥 Total Revenue ({f_m}–{t_m} 2025)", mm(sel.r.sum()), "Selected period")
        kpi(k[1], "🧪 T-Test Result", f"P = {'<0.001' if p < .001 else f'{p:.2f}'}",
            f"(one-tailed) {'↑ Increase' if up else '↓ Decrease'}", "#14935b" if up else RED)
        kpi(k[2], "📈 ARPU (per month)", f"₹{mu:,.2f}", f"vs ₹{ref:,.2f} (ref)")
        byk = sel.groupby("k").agg(S=("r", "size"), R=("r", "sum")).reindex(TYPES).reset_index()
        byk["RM"] = byk.R / M
        with st.container(key="one_r"):
            a, b, c3 = st.columns([5, 3.5, 3.5])
            show(a, trend_fig(sel, f"Revenue Trend ({f_m}–{t_m} 2025)"))
            show(b, tidy(px.bar(byk, x="k", y="RM", color="k", text=byk.RM.map(lambda v: f"₹{v:.1f}M"),
                                color_discrete_map={"Prepaid": RED, "Postpaid": PINK}, labels={"k": "", "RM": "Revenue (₹M)"}),
                         "Revenue by Plan", showlegend=False))
            sh = pd.DataFrame({"Type": byk.k, "Subscriber share": 100 * byk.S / byk.S.sum(),
                               "Revenue share": 100 * byk.R / byk.R.sum()}).melt("Type", var_name="Metric", value_name="%")
            show(c3, tidy(px.bar(sh, x="Type", y="%", color="Metric", barmode="group", text_auto=".0f",
                                 color_discrete_map={"Subscriber share": RED, "Revenue share": PINK}),
                          "Subscriber Share vs Revenue Share",
                          yaxis_ticksuffix="%", yaxis_range=[0, 100]))

    with tab2:
        c1, c2 = st.columns([3, 1])
        c1.markdown('<div class="banner" style="font-size:16px;color:#22181a;padding:9px 14px"><b>Explore performance by Plan</b></div>',
                    unsafe_allow_html=True)
        pick = c2.selectbox("Plan Selector", ["Postpaid", "Prepaid", "All plans"] + sorted(sel.plan_name.unique()),
                            label_visibility="collapsed", key="detail_plan_selector")
        d2 = sel if pick == "All plans" else sel[sel.k == pick] if pick in ("Prepaid", "Postpaid") else sel[sel.plan_name == pick]
        if d2.empty:
            st.info("No customers for this plan under the current filters."); st.stop()
        n2, r2 = len(d2), d2.r.sum()
        k = st.columns(3)
        kpi(k[0], f"👥 Subscribers ({pick})", f"{n2:,}", "(Selected Plan)")
        kpi(k[1], "🧾 Received Revenue", mm(r2), f"({f_m}–{t_m})")
        kpi(k[2], f"🧮 ARPU ({pick})", f"₹{r2 / n2 / NM:,.2f}", "Per subscriber per month")
        with st.container(key="det_c"):
            a, b = st.columns(2)
            rr = d2.groupby("region").r.sum().reset_index()
            rr["RM"] = rr.r / M
            show(a, tidy(px.bar(rr, x="region", y="RM", text=rr.RM.map(lambda v: f"₹{v:.2f}M"), color_discrete_sequence=[RED],
                                labels={"region": "", "RM": "Revenue (₹M)"}), f"Revenue by Region ({pick})"))
            show(b, trend_fig(d2, f"Revenue Trend – {pick}"))
        def row(name, g):
            return {"Plan": name, "Subscribers": len(g), "Revenue (₹M)": g.r.sum() / M,
                    "ARPU / month (₹)": g.r.sum() / len(g) / NM}
        fmt = {"Subscribers": "{:,}", "Revenue (₹M)": "{:.2f}", "ARPU / month (₹)": "{:,.2f}"}
        if pick == "All plans":
            two = pd.DataFrame([row(x, d2[d2.k == x]) for x in TYPES if not d2[d2.k == x].empty])
        else:
            two = pd.DataFrame([row(pick, d2)])
        table_html = "<table style='width:100%;border-collapse:collapse;font-size:13px'>"
        table_html += "<thead><tr>" + "".join(
            f"<th style='text-align:left;padding:8px;border-bottom:1px solid #ddd'>{column}</th>"
            for column in two.columns
        ) + "</tr></thead><tbody>"
        for _, row_values in two.iterrows():
            cells = []
            for column in two.columns:
                value = row_values[column]
                if column == "Subscribers":
                    displayed = f"{int(value):,}"
                elif column == "Revenue (₹M)":
                    displayed = f"{float(value):.2f}"
                elif column == "ARPU / month (₹)":
                    displayed = f"{float(value):,.2f}"
                else:
                    displayed = str(value)
                cells.append(f"<td style='padding:8px;border-bottom:1px solid #eee'>{displayed}</td>")
            table_html += "<tr>" + "".join(cells) + "</tr>"
        table_html += "</tbody></table>"
        st.markdown(table_html, unsafe_allow_html=True)
