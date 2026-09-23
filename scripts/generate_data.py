"""
Generate a synthetic retail sales dataset (customers, products, orders).

The files look like typical raw exports from a POS / e-commerce system and
contain the usual data quality problems on purpose, so the cleaning step has
something real to do:
  - exact duplicate rows
  - three different date formats in the same column
  - prices saved as text with the rupee sign and commas
  - different spellings of the same city / sales channel
  - missing customer ids, zero quantities, product ids that don't exist
  - returns recorded as negative quantity lines

usage:
    python scripts/generate_data.py --out data/raw
    python scripts/generate_data.py --out data/raw --orders 40000 --seed 7
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

START = pd.Timestamp("2024-01-01")
END = pd.Timestamp("2026-09-30")

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Arjun", "Sai", "Rohit", "Karthik", "Rahul",
    "Varun", "Nikhil", "Pranav", "Harsha", "Manoj", "Suresh", "Ravi", "Kiran",
    "Ananya", "Diya", "Sneha", "Priya", "Divya", "Kavya", "Meghana", "Pooja",
    "Lakshmi", "Swathi", "Keerthi", "Harika", "Bhavana", "Nandini", "Ishita",
    "Riya", "Shreya", "Neha", "Tanvi", "Sanjay", "Vikram", "Abhishek", "Teja", "Ajay",
]
LAST_NAMES = [
    "Reddy", "Rao", "Sharma", "Kumar", "Naidu", "Patel", "Iyer", "Nair", "Gupta",
    "Verma", "Chowdary", "Goud", "Yadav", "Singh", "Menon", "Joshi", "Kulkarni",
    "Das", "Mishra", "Pillai", "Varma", "Shetty", "Jain", "Agarwal", "Bhat",
]

# canonical city -> spellings seen in the source system
CITY_SPELLINGS = {
    "Bengaluru": ["Bengaluru", "Bangalore", "bangalore", "BLR", " Bengaluru"],
    "Hyderabad": ["Hyderabad", "hyderabad", "HYD", "Hyderabad "],
    "Chennai": ["Chennai", "chennai", "Madras"],
    "Mumbai": ["Mumbai", "mumbai", "Bombay"],
    "Pune": ["Pune", "pune", "PUNE"],
    "Delhi": ["Delhi", "New Delhi", "delhi", "NCR"],
    "Kolkata": ["Kolkata", "kolkata", "Calcutta"],
}
CITY_WEIGHTS = [0.26, 0.20, 0.14, 0.14, 0.10, 0.11, 0.05]

CATALOG = {
    "Electronics": (["Wireless Mouse", "Keyboard", "USB-C Charger", "Bluetooth Speaker",
                     "Earbuds", "Power Bank", "Smart Watch", "HDMI Cable", "Webcam",
                     "Pen Drive 64GB"], (299, 4999)),
    "Home & Kitchen": (["Steel Bottle", "Lunch Box", "Non-stick Pan", "Mixer Jar",
                        "Bedsheet Set", "Table Lamp", "Storage Box", "Wall Clock",
                        "Pressure Cooker", "Dinner Set"], (199, 3499)),
    "Fashion": (["Cotton T-Shirt", "Denim Jeans", "Kurta", "Running Shoes", "Backpack",
                 "Wallet", "Sunglasses", "Formal Shirt", "Saree", "Cap"], (249, 2999)),
    "Personal Care": (["Face Wash", "Shampoo", "Trimmer", "Hair Dryer", "Body Lotion",
                       "Sunscreen", "Perfume", "Toothbrush Pack", "Beard Oil",
                       "Sanitizer Pack"], (99, 2499)),
    "Stationery": (["A4 Notebook", "Gel Pen Pack", "Desk Organizer", "Sticky Notes",
                    "Whiteboard Marker", "Chair Cushion", "File Folder", "Calculator",
                    "Printer Paper Ream", "Highlighter Set"], (49, 1499)),
    "Sports": (["Yoga Mat", "Dumbbell Pair", "Cricket Bat", "Football", "Skipping Rope",
                "Badminton Racket", "Gym Gloves", "Cycling Helmet", "Water Sipper",
                "Resistance Band"], (149, 3999)),
}

# rough seasonality - festive months (Oct/Nov) are the peak
MONTH_WEIGHT = {1: 0.90, 2: 0.85, 3: 1.05, 4: 0.90, 5: 0.90, 6: 0.95,
                7: 0.95, 8: 1.00, 9: 1.00, 10: 1.35, 11: 1.40, 12: 1.15}


def make_products(rng):
    rows = []
    n = 1
    for category, (items, (lo, hi)) in CATALOG.items():
        for item in items:
            for variant in rng.choice(["Basic", "Plus", "Pro"], size=2, replace=False):
                price = rng.uniform(lo, hi)
                price = max(49, round(price / 50) * 50 - 1)  # 299, 349, 1499 ...
                rows.append((f"PRD-{n:04d}", f"{item} {variant}", category, price))
                n += 1
    df = pd.DataFrame(rows, columns=["product_id", "product_name", "category", "list_price"])
    # popularity: a few products sell a lot more than the rest
    popularity = rng.zipf(1.6, len(df)).astype(float)
    popularity = np.minimum(popularity, 30)
    return df, popularity / popularity.sum()


def make_customers(rng, n):
    first = rng.choice(FIRST_NAMES, n)
    last = rng.choice(LAST_NAMES, n)
    num = rng.integers(1, 999, n)
    domain = rng.choice(["gmail.com", "yahoo.com", "outlook.com", "rediffmail.com"], n,
                        p=[0.7, 0.12, 0.13, 0.05])
    email = [f"{f.lower()}.{l.lower()}{x}@{d}" for f, l, x, d in zip(first, last, num, domain)]

    cities = list(CITY_SPELLINGS)
    city = rng.choice(cities, n, p=CITY_WEIGHTS)
    city_raw = [c if rng.random() < 0.7 else rng.choice(CITY_SPELLINGS[c]) for c in city]

    segment = rng.choice(["Retail", "SMB", "Corporate"], n, p=[0.72, 0.19, 0.09])

    first_day = START - pd.Timedelta(days=210)
    span = (END - pd.Timedelta(days=20) - first_day).days
    signup = first_day + pd.to_timedelta(rng.integers(0, span, n), unit="D")

    # some customers stop buying at some point - needed for the churn / RFM part
    churned = rng.random(n) < 0.32
    days_left = (END - signup).days.to_numpy()
    last_active = np.where(
        churned,
        signup + pd.to_timedelta((rng.random(n) * days_left).astype(int), unit="D"),
        END,
    )
    weight = rng.lognormal(0, 0.9, n) * np.where(segment == "Corporate", 2.0, 1.0)

    df = pd.DataFrame({
        "customer_id": [f"CUST-{i:05d}" for i in range(1, n + 1)],
        "customer_name": np.char.add(np.char.add(first, " "), last),
        "email": email,
        "city": city_raw,
        "segment": segment,
        "signup_date": signup,
    })
    hidden = pd.DataFrame({"signup": signup, "last_active": pd.to_datetime(last_active),
                           "weight": weight})
    return df, hidden


def make_orders(rng, customers, hidden, products, popularity, n_orders, growth=0.15):
    # month by month: decide how many orders the month gets (seasonality + yearly
    # growth), then pick them only from customers active in that month.
    # (first version picked customer first and the volume kept piling up with
    # signups - gave >100% yoy growth, not realistic)
    signup = hidden["signup"].to_numpy()
    last_active = hidden["last_active"].to_numpy()
    weight = hidden["weight"].to_numpy()

    months = pd.period_range(START, END, freq="M")
    years = np.array([(m.start_time - START).days / 365.0 for m in months])
    month_w = np.array([MONTH_WEIGHT[m.month] for m in months]) * (1 + growth) ** years
    per_month = np.round(n_orders * month_w / month_w.sum()).astype(int)

    idx_all, dates_all = [], []
    for m, k in zip(months, per_month):
        ms, me = m.start_time.to_datetime64(), m.end_time.normalize().to_datetime64()
        active = np.flatnonzero((signup <= me) & (last_active >= ms))
        idx = rng.choice(active, k, p=weight[active] / weight[active].sum())
        lo = np.maximum(signup[idx], ms)
        hi = np.minimum(last_active[idx], me)
        span = ((hi - lo) / np.timedelta64(1, "D")).astype(int) + 1
        days = (rng.random(k) * span).astype(int)
        idx_all.append(idx)
        dates_all.append(lo + days.astype("timedelta64[D]"))

    orders = pd.DataFrame({"customer_idx": np.concatenate(idx_all),
                           "order_date": pd.to_datetime(np.concatenate(dates_all))})
    orders = orders.sort_values("order_date", kind="stable").reset_index(drop=True)
    orders["order_id"] = [f"SO{i:06d}" for i in range(100001, 100001 + len(orders))]
    orders["channel"] = rng.choice(["Online", "Store", "Marketplace"], len(orders), p=[0.5, 0.3, 0.2])

    # 1-4 lines per order
    n_lines = rng.choice([1, 2, 3, 4], len(orders), p=[0.55, 0.27, 0.12, 0.06])
    lines = orders.loc[orders.index.repeat(n_lines)].reset_index(drop=True)
    p_idx = rng.choice(len(products), len(lines), p=popularity)
    lines["product_id"] = products["product_id"].to_numpy()[p_idx]
    lines["unit_price"] = products["list_price"].to_numpy()[p_idx].astype(float)

    seg = customers["segment"].to_numpy()[lines["customer_idx"]]
    qty = np.where(seg == "Corporate", rng.integers(2, 16, len(lines)),
                   np.where(seg == "SMB", rng.integers(1, 7, len(lines)), rng.integers(1, 4, len(lines))))
    lines["quantity"] = qty
    lines["discount_pct"] = rng.choice([0, 5, 10, 15, 20], len(lines), p=[0.55, 0.2, 0.12, 0.08, 0.05])
    lines["customer_id"] = customers["customer_id"].to_numpy()[lines["customer_idx"]]

    # returns: ~2.5% of lines come back a few days later as a negative line
    ret = lines.sample(frac=0.025, random_state=int(rng.integers(1e9))).copy()
    ret["quantity"] = -np.ceil(ret["quantity"] * rng.uniform(0.3, 1.0, len(ret))).astype(int)
    ret["order_date"] = (ret["order_date"] + pd.to_timedelta(rng.integers(2, 21, len(ret)), unit="D")).clip(upper=END)
    lines = pd.concat([lines, ret]).sort_values(["order_date", "order_id"]).reset_index(drop=True)

    cols = ["order_id", "order_date", "customer_id", "product_id", "quantity",
            "unit_price", "discount_pct", "channel"]
    return lines[cols]


def mess_up_dates(rng, dates):
    dates = pd.Series(pd.to_datetime(np.asarray(dates)))
    fmt = rng.choice(["%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y"], len(dates), p=[0.7, 0.2, 0.1])
    out = dates.dt.strftime("%Y-%m-%d").astype(object)
    for f in ["%d/%m/%Y", "%d-%b-%Y"]:
        mask = fmt == f
        out[mask] = dates[mask].dt.strftime(f)
    return out.to_numpy()


def mess_up_orders(rng, df):
    df = df.copy()
    n = len(df)
    df["order_date"] = mess_up_dates(rng, df["order_date"])

    price = df["unit_price"].astype(object)
    as_text = rng.random(n) < 0.15
    price[as_text] = [f"₹{p:,.2f}" for p in df.loc[as_text, "unit_price"]]
    df["unit_price"] = price

    spellings = {"Online": ["online", "ONLINE ", "Online"], "Store": ["store", "Store "],
                 "Marketplace": ["marketplace ", "MarketPlace"]}
    change = rng.random(n) < 0.25
    df.loc[change, "channel"] = [rng.choice(spellings[c]) for c in df.loc[change, "channel"]]

    df["customer_id"] = df["customer_id"].astype(object)
    df.loc[rng.random(n) < 0.008, "customer_id"] = None
    df.loc[rng.random(n) < 0.003, "quantity"] = 0
    df.loc[rng.random(n) < 0.0025, "product_id"] = "PRD-9999"
    df.loc[rng.random(n) < 0.002, "customer_id"] = "cust-99999 "  # not in master

    # duplicate rows (export ran twice for some batches)
    dups = df.sample(frac=0.015, random_state=int(rng.integers(1e9)))
    df = pd.concat([df, dups]).sort_index(kind="stable")
    return df.reset_index(drop=True)


def mess_up_customers(rng, df):
    df = df.copy()
    n = len(df)
    df["signup_date"] = mess_up_dates(rng, df["signup_date"])
    email = df["email"].astype(object)
    upper = rng.random(n) < 0.05
    email[upper] = [" " + e.upper() for e in email[upper]]
    email[rng.random(n) < 0.03] = None
    df["email"] = email
    df["segment"] = [s.lower() if rng.random() < 0.1 else s for s in df["segment"]]
    dups = df.sample(frac=0.006, random_state=int(rng.integers(1e9)))
    return pd.concat([df, dups]).sort_index(kind="stable").reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/raw")
    ap.add_argument("--customers", type=int, default=4000)
    ap.add_argument("--orders", type=int, default=26000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    products, popularity = make_products(rng)
    customers, hidden = make_customers(rng, args.customers)
    orders = make_orders(rng, customers, hidden, products, popularity, args.orders)

    mess_up_customers(rng, customers).to_csv(out / "customers.csv", index=False)
    products.to_csv(out / "products.csv", index=False)
    mess_up_orders(rng, orders).to_csv(out / "orders.csv", index=False)

    print(f"customers: {len(customers)}  products: {len(products)}  order lines: {len(orders)}")
    print(f"written to {out.resolve()}")


if __name__ == "__main__":
    main()
