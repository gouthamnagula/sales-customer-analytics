"""
RFM customer segmentation.

  R (recency)   - days since the customer's last purchase (lower is better)
  F (frequency) - number of distinct orders
  M (monetary)  - net revenue from the customer (returns subtracted)

Each one is scored 1-5 by quintile, then customers are put into segments
using the R and F scores (the usual RFM segment grid).
"""
import numpy as np
import pandas as pd

SEGMENT_ORDER = [
    "Champions", "Loyal Customers", "Potential Loyalists", "New Customers",
    "Promising", "Need Attention", "At Risk", "Can't Lose Them",
    "Hibernating", "Lost",
]

SEGMENT_ACTION = {
    "Champions": "Reward them, early access to new products, ask for reviews",
    "Loyal Customers": "Upsell higher value products, loyalty programme",
    "Potential Loyalists": "Membership / loyalty offers, recommend related products",
    "New Customers": "Good onboarding, follow-up on first purchase",
    "Promising": "Create brand awareness, small free-shipping offers",
    "Need Attention": "Limited time offers based on past purchases",
    "At Risk": "Personalised win-back emails, renewal offers",
    "Can't Lose Them": "Win them back - direct contact, best offers",
    "Hibernating": "Re-engage with relevant offers, else low priority",
    "Lost": "Only include in large re-activation campaigns",
}


def quintile_score(values, higher_is_better=True):
    """
    1-5 score by quintile. rank(method='first') is used so that ties
    (lots of customers with frequency 1 or 2) still split into 5 groups.
    """
    labels = [1, 2, 3, 4, 5] if higher_is_better else [5, 4, 3, 2, 1]
    ranked = values.rank(method="first")
    n_bins = min(5, ranked.nunique())
    if n_bins < 5:  # very small data (tests) - fall back to fewer groups
        labels = labels[:n_bins] if higher_is_better else labels[-n_bins:]
    return pd.qcut(ranked, n_bins, labels=labels).astype(int)


def assign_segment(r, f):
    r = np.asarray(r)
    f = np.asarray(f)
    conditions = [
        (r >= 4) & (f >= 4),
        (r == 3) & (f >= 4),
        (r >= 4) & (f >= 2),
        (r >= 4) & (f == 1),
        (r == 3) & (f <= 2),
        (r == 3) & (f == 3),
        (r == 1) & (f >= 4),
        (r <= 2) & (f >= 3),
        (r == 2) & (f <= 2),
    ]
    choices = ["Champions", "Loyal Customers", "Potential Loyalists", "New Customers",
               "Promising", "Need Attention", "Can't Lose Them", "At Risk", "Hibernating"]
    return np.select(conditions, choices, default="Lost")


def rfm_table(sales, snapshot_date=None):
    """
    snapshot_date = the 'today' for recency. default is the day after the
    last date in the data.
    """
    if snapshot_date is None:
        snapshot_date = sales["order_date"].max() + pd.Timedelta(days=1)
    snapshot_date = pd.Timestamp(snapshot_date)

    sold = sales[~sales["is_return"]]
    rfm = pd.DataFrame({
        "last_purchase": sold.groupby("customer_id")["order_date"].max(),
        "frequency": sold.groupby("customer_id")["order_id"].nunique(),
    })
    # monetary includes returns (net), only for customers who bought something
    rfm["monetary"] = sales.groupby("customer_id")["line_amount"].sum().reindex(rfm.index).round(2)
    rfm["recency_days"] = (snapshot_date - rfm["last_purchase"]).dt.days

    rfm["r_score"] = quintile_score(rfm["recency_days"], higher_is_better=False)
    rfm["f_score"] = quintile_score(rfm["frequency"])
    rfm["m_score"] = quintile_score(rfm["monetary"])
    rfm["rfm_score"] = (rfm["r_score"].astype(str) + rfm["f_score"].astype(str)
                        + rfm["m_score"].astype(str))
    rfm["segment"] = assign_segment(rfm["r_score"], rfm["f_score"])

    cols = ["recency_days", "frequency", "monetary", "r_score", "f_score", "m_score",
            "rfm_score", "segment"]
    return rfm[cols].rename_axis("customer_id").reset_index()


def segment_summary(rfm):
    g = rfm.groupby("segment")
    out = pd.DataFrame({
        "customers": g.size(),
        "avg_recency_days": g["recency_days"].mean().round(0),
        "avg_frequency": g["frequency"].mean().round(1),
        "avg_monetary": g["monetary"].mean().round(0),
        "total_revenue": g["monetary"].sum().round(2),
    })
    out["customer_pct"] = (100 * out["customers"] / out["customers"].sum()).round(1)
    out["revenue_pct"] = (100 * out["total_revenue"] / out["total_revenue"].sum()).round(1)
    out = out.reindex([s for s in SEGMENT_ORDER if s in out.index])
    out["suggested_action"] = out.index.map(SEGMENT_ACTION)
    return out.rename_axis("segment").reset_index()
