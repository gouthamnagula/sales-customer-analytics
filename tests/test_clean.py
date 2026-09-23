import pandas as pd

from sca import clean


def test_parse_dates_mixed_formats():
    s = pd.Series(["2026-03-14", "14/03/2026", "14-Mar-2026", " 2026-03-14 ", "not a date", None])
    out = clean.parse_dates(s)
    assert (out.iloc[:4] == pd.Timestamp("2026-03-14")).all()
    assert out.iloc[4:].isna().all()


def test_parse_dates_day_first():
    # 03/04/2026 is 3rd April (Indian format), not March 4th
    assert clean.parse_dates(pd.Series(["03/04/2026"])).iloc[0] == pd.Timestamp("2026-04-03")


def test_parse_price():
    s = pd.Series(["₹1,299.00", "1299", 1299.0, "Rs. 1,299", "Rs.50", "abc", None])
    out = clean.parse_price(s)
    assert list(out.iloc[:4]) == [1299.0] * 4
    assert out.iloc[4] == 50.0
    assert out.iloc[5:].isna().all()


def test_city_and_channel_normalised():
    cities = clean.map_values(pd.Series(["Bangalore", " BLR", "bengaluru ", "Bombay", "Warangal"]),
                              clean.CITY_MAP)
    assert list(cities) == ["Bengaluru", "Bengaluru", "Bengaluru", "Mumbai", "Warangal"]
    channels = clean.map_values(pd.Series(["ONLINE ", "store", "MarketPlace"]), clean.CHANNEL_MAP)
    assert list(channels) == ["Online", "Store", "Marketplace"]


def test_segment_keeps_smb_upper_case():
    out = clean.map_values(pd.Series(["smb", "SMB", "retail"]), clean.SEGMENT_MAP)
    assert list(out) == ["SMB", "SMB", "Retail"]


def test_clean_customers_dedup():
    raw = pd.DataFrame({
        "customer_id": ["CUST-1", "cust-1 ", "CUST-2"],
        "customer_name": ["ravi kumar", "ravi kumar", "priya rao"],
        "email": [" RAVI@X.COM", "ravi@x.com", None],
        "city": ["bangalore", "bangalore", "HYD"],
        "segment": ["retail", "retail", "SMB"],
        "signup_date": ["2025-01-01", "2025-01-01", "05/06/2025"],
    })
    out, info = clean.clean_customers(raw)
    assert len(out) == 2
    assert info["customers_duplicate_ids"] == 1
    assert out.loc[0, "email"] == "ravi@x.com"
    assert list(out["region"]) == ["South", "South"]
    assert out.loc[1, "signup_date"] == pd.Timestamp("2025-06-05")


def _orders():
    return pd.DataFrame({
        "order_id": ["SO1", "SO1", "SO2", "SO3", "SO4", "SO5", "SO6", "SO7"],
        "order_date": ["2026-01-01", "2026-01-01", "02/01/2026", "2026-01-03",
                       "2026-01-04", "bad", "2026-01-06", "2026-01-07"],
        "customer_id": ["C1", "C1", "C2", None, "C1", "C1", "C9", "C2"],
        "product_id": ["P1", "P1", "P2", "P1", "P9", "P1", "P1", "P2"],
        "quantity": [2, 2, -1, 1, 1, 1, 1, 0],
        "unit_price": ["₹1,000.00", "₹1,000.00", "500", "100", "100", "100", "100", "100"],
        "discount_pct": [10, 10, 0, 0, 0, 0, 0, 0],
        "channel": ["online", "online", "Store ", "Online", "Online", "Online", "Online", "Online"],
    })


def test_clean_orders_rejects_with_reason():
    clean_df, rejects, dq = clean.clean_orders(_orders(), {"C1", "C2"}, {"P1", "P2"})
    assert dq["exact_duplicates"] == 1
    assert dict(zip(rejects["order_id"], rejects["reject_reason"])) == {
        "SO3": "missing_customer_id",
        "SO4": "unknown_product",
        "SO5": "bad_date",
        "SO6": "unknown_customer",
        "SO7": "zero_or_bad_quantity",
    }
    assert list(clean_df["order_id"]) == ["SO1", "SO2"]
    assert dq["rows_raw"] == dq["exact_duplicates"] + dq["rows_rejected"] + dq["rows_clean"]


def test_line_amount_and_returns():
    clean_df, _, _ = clean.clean_orders(_orders(), {"C1", "C2"}, {"P1", "P2"})
    so1 = clean_df[clean_df["order_id"] == "SO1"].iloc[0]
    assert so1["line_amount"] == 1800.0  # 2 x 1000 less 10%
    so2 = clean_df[clean_df["order_id"] == "SO2"].iloc[0]
    assert so2["is_return"] and so2["line_amount"] == -500.0
