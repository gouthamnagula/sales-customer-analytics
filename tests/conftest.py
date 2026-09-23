import pandas as pd
import pytest


@pytest.fixture
def small_sales():
    """tiny hand made sales table - numbers easy to check by hand"""
    rows = [
        # order_id, date, customer, product, category, region, channel, qty, price, disc, return
        ("SO1", "2026-01-05", "C1", "P1", "Electronics", "South", "Online", 2, 500.0, 0, False),
        ("SO1", "2026-01-05", "C1", "P2", "Fashion", "South", "Online", 1, 1000.0, 10, False),
        ("SO2", "2026-01-20", "C2", "P1", "Electronics", "North", "Store", 1, 500.0, 0, False),
        ("SO3", "2026-02-10", "C1", "P3", "Sports", "South", "Online", 4, 250.0, 0, False),
        ("SO3", "2026-02-15", "C1", "P3", "Sports", "South", "Online", -1, 250.0, 0, True),
        ("SO4", "2026-02-28", "C3", "P2", "Fashion", "West", "Marketplace", 3, 1000.0, 20, False),
    ]
    df = pd.DataFrame(rows, columns=["order_id", "order_date", "customer_id", "product_id",
                                     "category", "region", "channel", "quantity", "unit_price",
                                     "discount_pct", "is_return"])
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["product_name"] = df["product_id"] + " name"
    df["line_amount"] = df["quantity"] * df["unit_price"] * (1 - df["discount_pct"] / 100)
    return df
