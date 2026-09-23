"""
Excel report - one workbook with a sheet per view, so it can be shared with
people who don't open the dashboard.
"""
import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(color="FFFFFF", bold=True)

LABELS = {
    "gross_revenue": "Gross revenue (Rs.)",
    "returns_value": "Returns (Rs.)",
    "net_revenue": "Net revenue (Rs.)",
    "orders": "Orders",
    "customers": "Customers who purchased",
    "units_sold": "Units sold",
    "avg_order_value": "Average order value (Rs.)",
    "return_rate_pct": "Return rate (%)",
    "repeat_customer_pct": "Repeat customers (%)",
}


def _format_sheet(ws):
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
    for i, col in enumerate(ws.columns, start=1):
        width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
        ws.column_dimensions[get_column_letter(i)].width = min(max(10, width + 2), 60)
        for c in col[1:]:
            if isinstance(c.value, float):
                c.number_format = "#,##0.00"
    ws.freeze_panes = "A2"


def write_excel(path, summary, comparison, monthly, by_region, by_category, by_channel,
                top_products, segments, rfm, dq):
    summary_rows = [(LABELS.get(k, k), v) for k, v in summary.items()]
    summary_rows += [
        (f"Net revenue {comparison['period']} {comparison['current_year']}",
         comparison["current_net_revenue"]),
        (f"Net revenue {comparison['period']} {comparison['current_year'] - 1}",
         comparison["previous_net_revenue"]),
        ("Growth vs same period last year (%)", comparison["growth_pct"]),
    ]
    sheets = {
        "Summary": pd.DataFrame(summary_rows, columns=["KPI", "Value"]),
        "Monthly Trend": monthly,
        "By Region": by_region,
        "By Category": by_category,
        "By Channel": by_channel,
        "Top Products": top_products,
        "RFM Segments": segments,
        "Customer RFM": rfm,
        "Data Quality": pd.DataFrame(list(dq.items()), columns=["Check", "Rows"]),
    }
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name, index=False)
            _format_sheet(xw.sheets[name])
    return path
