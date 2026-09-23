"""
Cleaning and validation of the raw exports.

Nothing is silently dropped - every rejected order line goes into a rejects
table with the reason, so it can be checked / sent back to the source team.
"""
import pandas as pd

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y")

CITY_MAP = {
    "bengaluru": "Bengaluru", "bangalore": "Bengaluru", "blr": "Bengaluru",
    "hyderabad": "Hyderabad", "hyd": "Hyderabad",
    "chennai": "Chennai", "madras": "Chennai",
    "mumbai": "Mumbai", "bombay": "Mumbai",
    "pune": "Pune",
    "delhi": "Delhi", "new delhi": "Delhi", "ncr": "Delhi",
    "kolkata": "Kolkata", "calcutta": "Kolkata",
}

REGION_MAP = {
    "Bengaluru": "South", "Hyderabad": "South", "Chennai": "South",
    "Mumbai": "West", "Pune": "West",
    "Delhi": "North",
    "Kolkata": "East",
}

CHANNEL_MAP = {"online": "Online", "store": "Store", "marketplace": "Marketplace"}
SEGMENT_MAP = {"retail": "Retail", "smb": "SMB", "corporate": "Corporate"}

# order matters - a row gets the first reason it fails
REJECT_RULES = (
    "bad_date",
    "missing_customer_id",
    "unknown_customer",
    "unknown_product",
    "zero_or_bad_quantity",
    "bad_price",
)


def clean_text(s, upper=False):
    """strip spaces, optional upper case, empty string -> NA"""
    out = s.astype("string").str.strip()
    if upper:
        out = out.str.upper()
    return out.replace("", pd.NA)


def parse_dates(s):
    """the export has 3 date formats mixed in one column, try each one"""
    s = clean_text(pd.Series(s))
    out = pd.to_datetime(s, format=DATE_FORMATS[0], errors="coerce")
    for fmt in DATE_FORMATS[1:]:
        out = out.fillna(pd.to_datetime(s, format=fmt, errors="coerce"))
    return out


def parse_price(s):
    """'₹1,299.00' / 'Rs. 1299' / 1299.0 -> 1299.0"""
    s = pd.Series(s).astype("string").str.replace(r"(?i)rs\.?|[₹,\s]", "", regex=True)
    return pd.to_numeric(s, errors="coerce").astype("float64")


def map_values(s, mapping, title_unknown=True):
    """lookup on the lower-cased value, keep the original (title case) if not in the map"""
    s = clean_text(pd.Series(s))
    mapped = s.str.lower().map(mapping)
    if title_unknown:
        mapped = mapped.fillna(s.str.title())
    return mapped.astype("string")


def clean_customers(raw):
    df = raw.copy()
    info = {"customers_raw": len(df)}

    df["customer_id"] = clean_text(df["customer_id"], upper=True)
    df = df.dropna(subset=["customer_id"]).drop_duplicates(subset="customer_id", keep="first")
    info["customers_duplicate_ids"] = info["customers_raw"] - len(df)

    df["customer_name"] = clean_text(df["customer_name"]).str.title()
    df["email"] = clean_text(df["email"]).str.lower()
    df["city"] = map_values(df["city"], CITY_MAP)
    df["region"] = df["city"].map(REGION_MAP).fillna("Unknown").astype("string")
    df["segment"] = map_values(df["segment"], SEGMENT_MAP)
    df["signup_date"] = parse_dates(df["signup_date"])

    info["customers_missing_email"] = int(df["email"].isna().sum())
    info["customers_clean"] = len(df)
    cols = ["customer_id", "customer_name", "email", "city", "region", "segment", "signup_date"]
    return df[cols].reset_index(drop=True), info


def clean_products(raw):
    df = raw.copy()
    df["product_id"] = clean_text(df["product_id"], upper=True)
    df = df.dropna(subset=["product_id"]).drop_duplicates(subset="product_id")
    df["product_name"] = clean_text(df["product_name"])
    df["category"] = clean_text(df["category"])
    df["list_price"] = parse_price(df["list_price"])
    return df.reset_index(drop=True), {"products_clean": len(df)}


def clean_orders(raw, customer_ids, product_ids):
    """
    returns (clean, rejects, dq) where dq is a dict of counts for the
    data quality sheet
    """
    df = raw.copy()
    dq = {"rows_raw": len(df)}

    n = len(df)
    df = df.drop_duplicates()
    dq["exact_duplicates"] = n - len(df)

    df["order_id"] = clean_text(df["order_id"], upper=True)
    df["customer_id"] = clean_text(df["customer_id"], upper=True)
    df["product_id"] = clean_text(df["product_id"], upper=True)
    df["order_date"] = parse_dates(df["order_date"])
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price"] = parse_price(df["unit_price"])
    df["discount_pct"] = pd.to_numeric(df["discount_pct"], errors="coerce").fillna(0).clip(0, 100)
    df["channel"] = map_values(df["channel"], CHANNEL_MAP)

    checks = {
        "bad_date": df["order_date"].isna(),
        "missing_customer_id": df["customer_id"].isna(),
        "unknown_customer": df["customer_id"].notna() & ~df["customer_id"].isin(customer_ids),
        "unknown_product": ~df["product_id"].isin(product_ids),
        "zero_or_bad_quantity": df["quantity"].isna() | (df["quantity"] == 0),
        "bad_price": df["unit_price"].isna() | (df["unit_price"] <= 0),
    }
    reason = pd.Series(pd.NA, index=df.index, dtype="string")
    for rule in REJECT_RULES:
        mask = checks[rule].fillna(False).astype(bool)
        reason = reason.mask(reason.isna() & mask, rule)

    counts = reason.value_counts()
    for rule in REJECT_RULES:
        dq[rule] = int(counts.get(rule, 0))

    rejects = df[reason.notna()].copy()
    rejects["reject_reason"] = reason[reason.notna()]

    clean = df[reason.isna()].copy()
    clean["quantity"] = clean["quantity"].astype(int)
    clean["is_return"] = clean["quantity"] < 0
    clean["line_amount"] = (
        clean["quantity"] * clean["unit_price"] * (1 - clean["discount_pct"] / 100)
    ).round(2)

    dq["rows_rejected"] = len(rejects)
    dq["rows_clean"] = len(clean)
    dq["return_lines"] = int(clean["is_return"].sum())
    return clean.reset_index(drop=True), rejects.reset_index(drop=True), dq
