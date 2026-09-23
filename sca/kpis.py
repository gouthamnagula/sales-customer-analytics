"""
KPI calculations on the denormalised sales table (warehouse.read_sales()).

Definitions used everywhere (dashboard + excel report):
  gross revenue  = sum of line_amount for normal (non return) lines
  returns value  = absolute value of the return lines
  net revenue    = gross - returns
  orders         = distinct order ids that have at least one normal line
  AOV            = gross revenue / orders
  return rate %  = returns value / gross revenue * 100
"""
import pandas as pd


def _split(sales):
    return sales[~sales["is_return"]], sales[sales["is_return"]]


def summary(sales):
    sold, returned = _split(sales)
    gross = float(sold["line_amount"].sum())
    returns = float(-returned["line_amount"].sum())
    orders = int(sold["order_id"].nunique())
    return {
        "gross_revenue": round(gross, 2),
        "returns_value": round(returns, 2),
        "net_revenue": round(gross - returns, 2),
        "orders": orders,
        "customers": int(sold["customer_id"].nunique()),
        "units_sold": int(sold["quantity"].sum()),
        "avg_order_value": round(gross / orders, 2) if orders else 0.0,
        "return_rate_pct": round(100 * returns / gross, 2) if gross else 0.0,
    }


def monthly_trend(sales):
    s = sales.assign(month=sales["order_date"].dt.to_period("M"))
    sold = s[~s["is_return"]]
    out = pd.DataFrame({
        "net_revenue": s.groupby("month")["line_amount"].sum(),
        "gross_revenue": sold.groupby("month")["line_amount"].sum(),
        "orders": sold.groupby("month")["order_id"].nunique(),
        "customers": sold.groupby("month")["customer_id"].nunique(),
    }).fillna(0)
    out["avg_order_value"] = (out["gross_revenue"] / out["orders"]).round(2)
    out["mom_growth_pct"] = (out["net_revenue"].pct_change() * 100).round(2)
    out["net_revenue"] = out["net_revenue"].round(2)
    out["gross_revenue"] = out["gross_revenue"].round(2)
    out.index = out.index.astype(str)
    return out.rename_axis("month").reset_index()


def by_dimension(sales, col):
    sold = sales[~sales["is_return"]]
    out = pd.DataFrame({
        "net_revenue": sales.groupby(col)["line_amount"].sum(),
        "orders": sold.groupby(col)["order_id"].nunique(),
        "units": sold.groupby(col)["quantity"].sum(),
    }).fillna(0)
    out["share_pct"] = (100 * out["net_revenue"] / out["net_revenue"].sum()).round(2)
    out["net_revenue"] = out["net_revenue"].round(2)
    return out.sort_values("net_revenue", ascending=False).reset_index()


def top_products(sales, n=10):
    sold = sales[~sales["is_return"]]
    out = (sold.groupby(["product_id", "product_name", "category"])
               .agg(units=("quantity", "sum"), revenue=("line_amount", "sum"),
                    orders=("order_id", "nunique"))
               .sort_values("revenue", ascending=False)
               .head(n)
               .reset_index())
    out["revenue"] = out["revenue"].round(2)
    return out


def same_period_comparison(sales):
    """
    current year till the last month in the data vs same months last year
    (e.g. Jan-Sep 2026 vs Jan-Sep 2025)
    """
    last = sales["order_date"].max()
    year, month = last.year, last.month
    d = sales["order_date"]

    def net(y):
        mask = (d.dt.year == y) & (d.dt.month <= month)
        return float(sales.loc[mask, "line_amount"].sum())

    cur, prev = net(year), net(year - 1)
    return {
        "period": f"Jan-{last.strftime('%b')}",
        "current_year": year,
        "current_net_revenue": round(cur, 2),
        "previous_net_revenue": round(prev, 2),
        "growth_pct": round(100 * (cur - prev) / prev, 2) if prev else None,
    }


def repeat_customer_rate(sales):
    sold = sales[~sales["is_return"]]
    orders_per_cust = sold.groupby("customer_id")["order_id"].nunique()
    return round(100 * (orders_per_cust > 1).mean(), 2) if len(orders_per_cust) else 0.0
