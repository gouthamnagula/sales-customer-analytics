import pytest

from sca import kpis


def test_summary(small_sales):
    s = kpis.summary(small_sales)
    # gross = 1000 + 900 + 500 + 1000 + 2400 = 5800, return = 250
    assert s["gross_revenue"] == 5800.0
    assert s["returns_value"] == 250.0
    assert s["net_revenue"] == 5550.0
    assert s["orders"] == 4
    assert s["customers"] == 3
    assert s["avg_order_value"] == 1450.0
    assert s["return_rate_pct"] == pytest.approx(4.31, abs=0.01)


def test_monthly_trend(small_sales):
    m = kpis.monthly_trend(small_sales).set_index("month")
    assert list(m.index) == ["2026-01", "2026-02"]
    assert m.loc["2026-01", "net_revenue"] == 2400.0
    assert m.loc["2026-02", "net_revenue"] == 3150.0  # 1000 - 250 + 2400
    assert m.loc["2026-02", "mom_growth_pct"] == 31.25


def test_by_dimension_share_adds_to_100(small_sales):
    out = kpis.by_dimension(small_sales, "region")
    assert out["share_pct"].sum() == pytest.approx(100, abs=0.05)
    assert out.iloc[0]["region"] == "South"  # 1000 + 900 + 1000 - 250 = 2650


def test_top_products_ignores_returns(small_sales):
    top = kpis.top_products(small_sales, 3).set_index("product_id")
    assert top.loc["P3", "units"] == 4


def test_repeat_customer_rate(small_sales):
    # C1 has 2 orders, C2 and C3 have 1 -> 1 of 3
    assert kpis.repeat_customer_rate(small_sales) == 33.33
