"""
Runs the whole thing end to end:
    raw csv -> clean/validate -> star schema (sqlite) -> KPIs + RFM -> excel report

    python run_pipeline.py
    python run_pipeline.py --raw data/raw --db data/processed/warehouse.db --out reports
"""
import argparse
import json
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from sca import clean, kpis, report, rfm, warehouse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--db", default="data/processed/warehouse.db",
                    help="sqlite file path or a sqlalchemy url")
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    raw, out = Path(args.raw), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if "://" not in args.db:
        Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    print("[1/5] reading raw files")
    customers_raw = pd.read_csv(raw / "customers.csv")
    products_raw = pd.read_csv(raw / "products.csv")
    orders_raw = pd.read_csv(raw / "orders.csv")

    print("[2/5] cleaning + validation")
    customers, c_info = clean.clean_customers(customers_raw)
    products, p_info = clean.clean_products(products_raw)
    orders, rejects, dq = clean.clean_orders(
        orders_raw, set(customers["customer_id"]), set(products["product_id"])
    )
    dq = {**c_info, **p_info, **dq}
    rejects.to_csv(out / "rejected_rows.csv", index=False)
    for k, v in dq.items():
        print(f"      {k:<26}{v:>8}")

    print("[3/5] loading star schema")
    engine = warehouse.get_engine(args.db)
    counts = warehouse.load_star(engine, warehouse.build_star(orders, customers, products))
    for k, v in counts.items():
        print(f"      {k:<26}{v:>8}")

    print("[4/5] KPIs and RFM")
    sales = warehouse.read_sales(engine)
    summary = kpis.summary(sales)
    summary["repeat_customer_pct"] = kpis.repeat_customer_rate(sales)
    comparison = kpis.same_period_comparison(sales)

    # sanity check - pandas and sql should give the same net revenue
    with engine.connect() as conn:
        sql_net = conn.execute(text("SELECT ROUND(SUM(line_amount), 2) FROM fact_sales")).scalar()
    assert abs(float(sql_net) - summary["net_revenue"]) < 0.01, "pandas / sql mismatch"

    rfm_df = rfm.rfm_table(sales)
    segments = rfm.segment_summary(rfm_df)
    rfm_df.to_sql("customer_rfm", engine, if_exists="append", index=False)  # table made by schema.sql

    for k, v in summary.items():
        print(f"      {k:<26}{v:>16,}")
    print(f"      {comparison['period']} {comparison['current_year']} vs last year: "
          f"{comparison['growth_pct']}%")

    print("[5/5] writing report")
    xlsx = report.write_excel(
        out / "sales_customer_report.xlsx", summary, comparison,
        kpis.monthly_trend(sales),
        kpis.by_dimension(sales, "region"),
        kpis.by_dimension(sales, "category"),
        kpis.by_dimension(sales, "channel"),
        kpis.top_products(sales, 10),
        segments, rfm_df, dq,
    )
    (out / "data_quality.json").write_text(json.dumps(dq, indent=2))
    print(f"      {xlsx}")
    print(f"done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
