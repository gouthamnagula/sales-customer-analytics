"""
Sales & customer dashboard.

    streamlit run dashboard/app.py

needs the warehouse to exist first -> python run_pipeline.py
"""
import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sca import kpis, rfm, warehouse  # noqa: E402

DB_PATH = ROOT / "data" / "processed" / "warehouse.db"
DQ_PATH = ROOT / "reports" / "data_quality.json"

st.set_page_config(page_title="Sales & Customer Analytics", page_icon="📊", layout="wide")


@st.cache_data
def load_data():
    engine = warehouse.get_engine(DB_PATH)
    sales = warehouse.read_sales(engine)
    rfm_df = pd.read_sql("SELECT * FROM customer_rfm", engine)
    return sales, rfm_df


def rupees(x):
    """indian style short format - 1.2 Cr / 45.3 L"""
    if abs(x) >= 1e7:
        return f"₹{x / 1e7:.2f} Cr"
    if abs(x) >= 1e5:
        return f"₹{x / 1e5:.2f} L"
    return f"₹{x:,.0f}"


if not DB_PATH.exists():
    st.error("Warehouse not found. Run `python run_pipeline.py` first.")
    st.stop()

sales, rfm_all = load_data()

# ---------------- sidebar filters ----------------
st.sidebar.header("Filters")
min_d, max_d = sales["order_date"].min().date(), sales["order_date"].max().date()
date_range = st.sidebar.date_input("Order date", (min_d, max_d), min_value=min_d, max_value=max_d)
regions = st.sidebar.multiselect("Region", sorted(sales["region"].unique()))
channels = st.sidebar.multiselect("Channel", sorted(sales["channel"].unique()))
categories = st.sidebar.multiselect("Category", sorted(sales["category"].unique()))
segments_f = st.sidebar.multiselect("Customer type", sorted(sales["segment"].unique()))

df = sales
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    df = df[(df["order_date"] >= start) & (df["order_date"] <= end)]
for col, chosen in [("region", regions), ("channel", channels),
                    ("category", categories), ("segment", segments_f)]:
    if chosen:
        df = df[df[col].isin(chosen)]

st.title("Sales & Customer Analytics")
st.caption(f"{len(df):,} order lines  |  {df['order_date'].min():%d %b %Y} - "
           f"{df['order_date'].max():%d %b %Y}" if len(df) else "no data for the selected filters")

if df.empty:
    st.warning("No rows match the filters.")
    st.stop()

s = kpis.summary(df)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Net revenue", rupees(s["net_revenue"]))
c2.metric("Orders", f"{s['orders']:,}")
c3.metric("Avg order value", rupees(s["avg_order_value"]))
c4.metric("Customers", f"{s['customers']:,}")
c5.metric("Return rate", f"{s['return_rate_pct']}%")

tab_overview, tab_products, tab_customers, tab_dq = st.tabs(
    ["Overview", "Products", "Customers (RFM)", "Data quality"])

# ---------------- overview ----------------
with tab_overview:
    monthly = kpis.monthly_trend(df)
    fig = px.line(monthly, x="month", y="net_revenue", markers=True,
                  labels={"net_revenue": "Net revenue (₹)", "month": ""},
                  title="Monthly net revenue")
    st.plotly_chart(fig, width="stretch")

    left, right = st.columns(2)
    reg = kpis.by_dimension(df, "region")
    left.plotly_chart(px.bar(reg, x="region", y="net_revenue", text="share_pct",
                             labels={"net_revenue": "Net revenue (₹)", "region": ""},
                             title="Revenue by region (% share)"), width="stretch")
    ch = kpis.by_dimension(df, "channel")
    right.plotly_chart(px.pie(ch, names="channel", values="net_revenue", hole=0.45,
                              title="Revenue by channel"), width="stretch")

    st.subheader("Month on month")
    st.dataframe(monthly.sort_values("month", ascending=False), hide_index=True,
                 width="stretch")

# ---------------- products ----------------
with tab_products:
    cat = kpis.by_dimension(df, "category")
    st.plotly_chart(px.bar(cat, y="category", x="net_revenue", orientation="h",
                           labels={"net_revenue": "Net revenue (₹)", "category": ""},
                           title="Revenue by category").update_yaxes(autorange="reversed"),
                    width="stretch")
    n = st.slider("Top N products", 5, 30, 10)
    st.dataframe(kpis.top_products(df, n), hide_index=True, width="stretch")

# ---------------- customers ----------------
with tab_customers:
    st.caption("RFM is calculated on the full history (not affected by the date filter); "
               "region / customer type filters are applied.")
    cust_ids = df["customer_id"].unique()
    rfm_view = rfm_all[rfm_all["customer_id"].isin(cust_ids)]
    seg = rfm.segment_summary(rfm_view)

    left, right = st.columns([3, 2])
    left.plotly_chart(px.bar(seg, x="segment", y="customers", color="revenue_pct",
                             color_continuous_scale="Blues",
                             labels={"customers": "Customers", "segment": "",
                                     "revenue_pct": "Revenue %"},
                             title="Customers per segment"), width="stretch")
    right.plotly_chart(px.scatter(rfm_view.sample(min(1500, len(rfm_view)), random_state=1),
                                  x="recency_days", y="monetary", color="segment",
                                  size="frequency", log_y=True, opacity=0.7,
                                  labels={"recency_days": "Days since last purchase",
                                          "monetary": "Net revenue (₹, log)"},
                                  title="Recency vs value"), width="stretch")
    st.dataframe(seg, hide_index=True, width="stretch")

    pick = st.selectbox("Download customer list for segment", seg["segment"])
    out = rfm_view[rfm_view["segment"] == pick]
    st.download_button(f"Download {pick} ({len(out)} customers)", out.to_csv(index=False),
                       file_name=f"{pick.lower().replace(' ', '_')}.csv", mime="text/csv")

# ---------------- data quality ----------------
with tab_dq:
    if DQ_PATH.exists():
        dq = json.loads(DQ_PATH.read_text())
        a, b, c = st.columns(3)
        a.metric("Raw order lines", f"{dq['rows_raw']:,}")
        b.metric("Loaded", f"{dq['rows_clean']:,}")
        c.metric("Rejected", f"{dq['rows_rejected']:,}")
        issues = {k: v for k, v in dq.items()
                  if k in ("exact_duplicates", "missing_customer_id", "unknown_customer",
                           "unknown_product", "zero_or_bad_quantity", "bad_date", "bad_price")}
        st.plotly_chart(px.bar(x=list(issues.keys()), y=list(issues.values()),
                               labels={"x": "", "y": "rows"}, title="Rows removed per check"),
                        width="stretch")
        st.json(dq, expanded=False)
    else:
        st.info("data_quality.json not found - run the pipeline.")
