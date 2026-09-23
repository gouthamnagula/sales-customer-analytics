import numpy as np
import pandas as pd

from sca import rfm


def test_segment_rules():
    r = [5, 3, 5, 4, 3, 3, 1, 2, 2, 1]
    f = [5, 4, 2, 1, 1, 3, 5, 3, 1, 1]
    expected = ["Champions", "Loyal Customers", "Potential Loyalists", "New Customers",
                "Promising", "Need Attention", "Can't Lose Them", "At Risk",
                "Hibernating", "Lost"]
    assert list(rfm.assign_segment(r, f)) == expected


def test_quintile_score_direction():
    values = pd.Series(range(1, 101))
    high = rfm.quintile_score(values)
    low = rfm.quintile_score(values, higher_is_better=False)
    assert high.iloc[0] == 1 and high.iloc[-1] == 5
    assert low.iloc[0] == 5 and low.iloc[-1] == 1
    assert sorted(high.value_counts()) == [20] * 5


def test_rfm_table(small_sales):
    out = rfm.rfm_table(small_sales, snapshot_date="2026-03-01").set_index("customer_id")
    assert out.loc["C1", "frequency"] == 2
    assert out.loc["C1", "recency_days"] == 19  # last purchase 10 Feb
    assert out.loc["C1", "monetary"] == 2650.0  # 1000 + 900 + 1000 - 250
    assert out.loc["C3", "recency_days"] == 1
    assert out[["r_score", "f_score", "m_score"]].isin(range(1, 6)).all().all()


def test_segment_summary_totals(small_sales):
    table = rfm.rfm_table(small_sales)
    summ = rfm.segment_summary(table)
    assert summ["customers"].sum() == len(table)
    assert np.isclose(summ["customer_pct"].sum(), 100, atol=0.2)
