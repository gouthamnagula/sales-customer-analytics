"""
Builds the star schema tables from the cleaned data and loads them into the
database (SQLite file by default, any SQLAlchemy url works).
"""
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

SCHEMA_SQL = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"

SALES_QUERY = """
SELECT f.order_id,
       d.full_date      AS order_date,
       c.customer_id, c.customer_name, c.city, c.region, c.segment,
       p.product_id, p.product_name, p.category,
       f.channel, f.quantity, f.unit_price, f.discount_pct, f.line_amount, f.is_return
FROM fact_sales f
JOIN dim_date d     ON d.date_key = f.date_key
JOIN dim_customer c ON c.customer_key = f.customer_key
JOIN dim_product p  ON p.product_key = f.product_key
"""


def get_engine(db):
    """db can be a file path or a full sqlalchemy url"""
    url = db if "://" in str(db) else f"sqlite:///{db}"
    return create_engine(url)


def build_dim_date(start, end):
    dates = pd.date_range(start, end, freq="D")
    return pd.DataFrame({
        "date_key": dates.strftime("%Y%m%d").astype(int),
        "full_date": dates.date,
        "day": dates.day,
        "month": dates.month,
        "month_name": dates.strftime("%b"),
        "quarter": dates.quarter,
        "year": dates.year,
        "weekday": dates.strftime("%A"),
        "is_weekend": (dates.dayofweek >= 5).astype(int),
    })


def build_star(orders, customers, products):
    dim_customer = customers.copy()
    dim_customer.insert(0, "customer_key", range(1, len(dim_customer) + 1))
    dim_customer["signup_date"] = dim_customer["signup_date"].dt.date

    dim_product = products[["product_id", "product_name", "category", "list_price"]].copy()
    dim_product.insert(0, "product_key", range(1, len(dim_product) + 1))

    start = orders["order_date"].min().replace(month=1, day=1)
    end = orders["order_date"].max().replace(month=12, day=31)
    dim_date = build_dim_date(start, end)

    fact = orders.merge(dim_customer[["customer_id", "customer_key"]], on="customer_id", how="left")
    fact = fact.merge(dim_product[["product_id", "product_key"]], on="product_id", how="left")
    if fact["customer_key"].isna().any() or fact["product_key"].isna().any():
        raise ValueError("fact rows without a matching dimension key - check cleaning step")

    fact["date_key"] = fact["order_date"].dt.strftime("%Y%m%d").astype(int)
    fact["is_return"] = fact["is_return"].astype(int)
    fact.insert(0, "sales_id", range(1, len(fact) + 1))
    fact = fact[["sales_id", "order_id", "date_key", "customer_key", "product_key", "channel",
                 "quantity", "unit_price", "discount_pct", "line_amount", "is_return"]]

    return {
        "dim_customer": dim_customer,
        "dim_product": dim_product,
        "dim_date": dim_date,
        "fact_sales": fact,
    }


def create_schema(engine):
    ddl = SCHEMA_SQL.read_text()
    with engine.begin() as conn:
        for stmt in ddl.split(";"):
            # drop comment lines so a chunk that is only comments is skipped
            lines = [l for l in stmt.splitlines() if not l.strip().startswith("--")]
            stmt = "\n".join(lines).strip()
            if stmt:
                conn.execute(text(stmt))


def load_star(engine, tables):
    create_schema(engine)
    # dims first because of the foreign keys
    for name in ["dim_customer", "dim_product", "dim_date", "fact_sales"]:
        tables[name].to_sql(name, engine, if_exists="append", index=False, chunksize=5000)
    with engine.connect() as conn:
        return {name: conn.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar() for name in tables}


def read_sales(engine):
    sales = pd.read_sql(SALES_QUERY, engine, parse_dates=["order_date"])
    sales["is_return"] = sales["is_return"].astype(bool)
    return sales
