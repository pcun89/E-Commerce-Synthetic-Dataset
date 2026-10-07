#!/usr/bin/env python3
"""
Synthetic e-commerce dataset generator.

Produces two linked CSV files for SQL practice, analytics and dashboards:

    data/customers.csv  - 1,000 customers (~100 never order)
    data/orders.csv     - 5,000 orders (customer_id is a FK to customers)

Usage:
    python generate_data.py                 # defaults, seed=42
    python generate_data.py --seed 7        # different random dataset
    python generate_data.py --out my_dir    # custom output folder

The script is deterministic for a given seed and validates its own output
(key integrity, financial consistency, date logic) before exiting.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
N_CUSTOMERS = 1_000
N_ORDERS = 5_000
N_INACTIVE = 100                      # customers with zero orders
ORDER_START = pd.Timestamp("2024-10-01")
ORDER_END = pd.Timestamp("2026-09-30")  # two-year window
SIGNUP_START = pd.Timestamp("2023-01-01")

# Relative order volume by calendar month (holiday peak, summer sale bump, Jan dip)
MONTH_WEIGHT = {1: 0.75, 2: 0.80, 3: 0.90, 4: 0.95, 5: 1.00, 6: 0.95,
                7: 1.15, 8: 1.00, 9: 0.95, 10: 1.05, 11: 1.60, 12: 1.75}
# Relative order volume by weekday (Mon=0 ... Sun=6)
DOW_WEIGHT = [1.00, 0.95, 0.95, 1.00, 1.05, 1.15, 1.20]

# (state/province code, country, sales-tax rate, [cities], sampling weight)
LOCATIONS = [
    ("CA", "USA", 0.0725, ["Los Angeles", "San Diego",
     "San Jose", "Sacramento", "Fresno"], 12),
    ("TX", "USA", 0.0625, ["Houston", "Dallas", "Austin", "San Antonio"], 9),
    ("NY", "USA", 0.0400, ["New York", "Buffalo", "Rochester", "Albany"], 8),
    ("FL", "USA", 0.0600, ["Miami", "Orlando", "Tampa", "Jacksonville"], 8),
    ("IL", "USA", 0.0625, ["Chicago", "Naperville", "Springfield"], 5),
    ("PA", "USA", 0.0600, ["Philadelphia", "Pittsburgh", "Allentown"], 5),
    ("OH", "USA", 0.0575, ["Columbus", "Cleveland", "Cincinnati"], 4),
    ("WA", "USA", 0.0650, ["Seattle", "Spokane", "Tacoma"], 4),
    ("GA", "USA", 0.0400, ["Atlanta", "Savannah", "Augusta"], 4),
    ("NC", "USA", 0.0475, ["Charlotte", "Raleigh", "Durham"], 4),
    ("MA", "USA", 0.0625, ["Boston", "Worcester", "Cambridge"], 3),
    ("CO", "USA", 0.0290, ["Denver", "Boulder", "Colorado Springs"], 3),
    ("AZ", "USA", 0.0560, ["Phoenix", "Tucson", "Mesa"], 3),
    ("IA", "USA", 0.0600, ["Des Moines", "Cedar Rapids", "Ames"], 2),
    ("OR", "USA", 0.0000, ["Portland", "Eugene", "Salem"], 2),   # no sales tax
    ("MT", "USA", 0.0000, ["Billings", "Missoula"], 1),          # no sales tax
    ("ON", "Canada", 0.1300, ["Toronto", "Ottawa", "Mississauga"], 3),
    ("BC", "Canada", 0.1200, ["Vancouver", "Victoria", "Surrey"], 2),
    ("QC", "Canada", 0.1498, ["Montreal", "Quebec City", "Laval"], 2),
    ("AB", "Canada", 0.0500, ["Calgary", "Edmonton"], 1),
]
TAX_BY_STATE = {loc[0]: loc[2] for loc in LOCATIONS}

FIRST_F = ["Olivia", "Emma", "Ava", "Sophia", "Isabella", "Mia", "Charlotte", "Amelia", "Harper",
           "Evelyn", "Abigail", "Emily", "Ella", "Scarlett", "Grace", "Chloe", "Lily", "Hannah",
           "Zoe", "Priya", "Maria", "Fatima", "Mei", "Aisha", "Sofia", "Nora", "Layla", "Camila"]
FIRST_M = ["Liam", "Noah", "Oliver", "Elijah", "James", "William", "Benjamin", "Lucas", "Henry",
           "Theodore", "Jack", "Levi", "Alexander", "Daniel", "Michael", "Owen", "Samuel", "Ethan",
           "Carlos", "Wei", "Arjun", "Mohammed", "Diego", "Kenji", "Omar", "Mateo", "Jamal", "Ravi"]
FIRST_N = ["Riley", "Jordan", "Taylor", "Casey",
           "Alex", "Morgan", "Avery", "Quinn", "Sam", "Rowan"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez",
              "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor",
              "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez",
              "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King", "Wright",
              "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green", "Adams", "Nelson", "Baker",
              "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts", "Patel", "Kim", "Chen",
              "Singh", "Khan", "Cohen", "Murphy", "Kowalski", "Okafor", "Tanaka", "Silva"]
EMAIL_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com",
                 "icloud.com", "hotmail.com", "proton.me"]
EMAIL_WEIGHTS = [0.52, 0.16, 0.14, 0.10, 0.05, 0.03]
CHANNELS = ["Organic Search", "Paid Social",
            "Email Campaign", "Referral", "Direct", "Affiliate"]
CHANNEL_WEIGHTS = [0.30, 0.22, 0.14, 0.14, 0.12, 0.08]

# category -> (sampling weight, units-per-order bias, [(product, base_price), ...])
CATALOG = {
    "Electronics": (0.17, 0.2, [("Wireless Earbuds", 59.99), ("Bluetooth Speaker", 44.99),
                                ("USB-C Charger 65W", 29.99), ("Smart Watch", 189.99),
                                ("4K Webcam", 79.99), ("Portable Power Bank", 34.99),
                                ("Noise Cancelling Headphones", 229.99), ("Mechanical Keyboard", 99.99)]),
    "Clothing": (0.20, 0.8, [("Classic Cotton T-Shirt", 19.99), ("Slim Fit Jeans", 54.99),
                             ("Fleece Hoodie", 44.99), ("Running Shorts", 27.99),
                             ("Winter Parka",
                              149.99), ("Merino Wool Socks (3-pack)", 24.99),
                             ("Linen Button-Down Shirt", 49.99), ("Yoga Leggings", 39.99)]),
    "Home & Kitchen": (0.15, 0.5, [("Nonstick Frying Pan", 34.99), ("Chef's Knife", 49.99),
                                   ("Memory Foam Pillow",
                                    39.99), ("Air Fryer 5qt", 99.99),
                                   ("Cotton Bath Towel Set",
                                    42.99), ("Pour-Over Coffee Maker", 36.99),
                                   ("Glass Food Storage Set", 29.99), ("Scented Soy Candle", 18.99)]),
    "Beauty & Personal Care": (0.11, 0.9, [("Vitamin C Serum", 28.99), ("Daily Moisturizer SPF 30", 22.99),
                                           ("Electric Toothbrush",
                                            59.99), ("Argan Oil Shampoo", 16.99),
                                           ("Lip Balm Set",
                                            9.99), ("Hair Dryer Pro", 79.99),
                                           ("Beard Grooming Kit", 31.99)]),
    "Sports & Outdoors": (0.10, 0.4, [("Yoga Mat", 29.99), ("Adjustable Dumbbells", 149.99),
                                      ("Insulated Water Bottle",
                                       24.99), ("Camping Tent 4-Person", 129.99),
                                      ("Resistance Bands Set",
                                       19.99), ("Hiking Backpack 40L", 84.99),
                                      ("Trail Running Shoes", 94.99)]),
    "Books & Media": (0.09, 0.9, [("Hardcover Bestseller Novel", 24.99), ("Cookbook Collection", 29.99),
                                  ("Self-Help Paperback",
                                   15.99), ("Kids Picture Book", 12.99),
                                  ("Board Game Classic", 34.99), ("1000-Piece Jigsaw Puzzle", 19.99)]),
    "Toys & Games": (0.08, 0.7, [("Building Blocks Set", 39.99), ("Remote Control Car", 44.99),
                                 ("Plush Teddy Bear",
                                  17.99), ("Educational STEM Kit", 34.99),
                                 ("Art & Craft Bundle", 22.99), ("Card Game Party Pack", 14.99)]),
    "Pet Supplies": (0.06, 0.7, [("Premium Dog Food 15lb", 49.99), ("Cat Scratching Post", 32.99),
                                 ("Orthopedic Pet Bed",
                                  54.99), ("Interactive Dog Toy", 14.99),
                                 ("Automatic Pet Feeder", 69.99)]),
    "Office Supplies": (0.04, 0.9, [("Ergonomic Desk Chair", 179.99), ("Gel Pen 24-Pack", 11.99),
                                    ("Hardcover Notebook 3-Pack",
                                     17.99), ("Desk Organizer", 24.99),
                                    ("Standing Desk Mat", 39.99)]),
}

SHIPPING_METHODS = ["Standard", "Express", "Next-Day", "Store Pickup"]
SHIPPING_FEES = {"Standard": 5.99, "Express": 12.99,
                 "Next-Day": 24.99, "Store Pickup": 0.0}
SHIPPING_DAYS = {"Standard": (4, 8), "Express": (
    2, 4), "Next-Day": (1, 2), "Store Pickup": (1, 3)}
FREE_SHIPPING_THRESHOLD = 75.00


def unique_random_ids(rng, n, low, high):
    """Random, unique, numeric-only IDs."""
    return rng.choice(np.arange(low, high), size=n, replace=False)
# ----------------------------------------------------------------------------
# Customers (part 1: everything except loyalty tier, which depends on orders)
# ----------------------------------------------------------------------------


def build_customers(rng):
    n = N_CUSTOMERS
    ids = unique_random_ids(rng, n, 100_000, 1_000_000)  # 6-digit

    gender = rng.choice(["Female", "Male", "Non-binary"],
                        size=n, p=[0.50, 0.47, 0.03])
    first = np.array([
        rng.choice(FIRST_F if g == "Female" else FIRST_M if g == "Male" else FIRST_N) for g in gender
    ])
    last = rng.choice(LAST_NAMES, size=n)

    age = np.clip(rng.normal(38, 12, n).round(), 18, 80).astype(float)

    # Sign-ups spread across ~3.7 years (steady acquisition)
    days_span = (ORDER_END - SIGNUP_START).days
    signup_offset = (days_span * rng.beta(1.0, 1.0, n)).astype(int)
    signup = SIGNUP_START + pd.to_timedelta(signup_offset, unit="D")

    weights = np.array([l[4] for l in LOCATIONS], dtype=float)
    loc_idx = rng.choice(len(LOCATIONS), size=n, p=weights / weights.sum())
    state = np.array([LOCATIONS[i][0] for i in loc_idx])
    country = np.array([LOCATIONS[i][1] for i in loc_idx])
    city = np.array([rng.choice(LOCATIONS[i][3]) for i in loc_idx])

    domains = rng.choice(EMAIL_DOMAINS, size=n, p=EMAIL_WEIGHTS)
    suffix = rng.integers(1, 999, n)
    email = np.array([f"{f.lower()}.{l.lower()}{s}@{d}"
                      for f, l, s, d in zip(first, last, suffix, domains)], dtype=object)

    df = pd.DataFrame({
        "customer_id": ids,
        "first_name": first,
        "last_name": last,
        "email": email,
        "age": age,
        "gender": gender,
        "signup_date": signup.normalize(),
        "city": city,
        "state": state,
        "country": country,
        "acquisition_channel": rng.choice(CHANNELS, size=n, p=CHANNEL_WEIGHTS),
        "marketing_opt_in": rng.random(n) < 0.62,
    })
    return df


# ----------------------------------------------------------------------------
# Orders-per-customer allocation (repeat customers, ~100 inactive)
# ----------------------------------------------------------------------------
def allocate_orders(rng, customers):
    n = len(customers)
    signup = customers["signup_date"]

    # Slightly favour recent sign-ups as inactive (they haven't had time to buy)
    recency = (signup - SIGNUP_START).dt.days.to_numpy() + 1.0
    p_inactive = recency / recency.sum()
    inactive_idx = rng.choice(n, size=N_INACTIVE, replace=False, p=p_inactive)
    is_inactive = np.zeros(n, dtype=bool)
    is_inactive[inactive_idx] = True

    # Active customers: 1 guaranteed order + heavy-tailed share of the rest
    active = np.where(~is_inactive)[0]
    # More tenure => more orders; gamma noise gives a long tail of power buyers
    tenure_days = (
        ORDER_END - signup.iloc[active]).dt.days.clip(lower=1).to_numpy()
    w = rng.gamma(0.7, 1.0, len(active)) * np.sqrt(tenure_days)
    extra = rng.multinomial(N_ORDERS - len(active), w / w.sum())
    counts = np.zeros(n, dtype=int)
    counts[active] = 1 + extra
    return counts


def assign_tiers(rng, counts):
    """Loyalty tier correlates with order count (with noise); inactive => Bronze."""
    n = len(counts)
    tiers = np.array(["Bronze"] * n, dtype=object)
    active = np.where(counts > 0)[0]
    score = counts[active] + rng.normal(0, 1.2, len(active))
    ranks = pd.Series(score).rank(pct=True).to_numpy()
    t = np.where(ranks > 0.93, "Platinum",
                 np.where(ranks > 0.75, "Gold",
                          np.where(ranks > 0.45, "Silver", "Bronze")))
    tiers[active] = t
    return tiers
# ----------------------------------------------------------------------------
# Orders
# ----------------------------------------------------------------------------


def build_orders(rng, customers, counts):
    # One row per order, repeating each customer id by its order count
    cust_rep = customers.loc[customers.index.repeat(
        counts)].reset_index(drop=True)
    n = len(cust_rep)
    assert n == N_ORDERS

    # --- dates: seasonal + weekday weights, never before the customer's sign-up
    days = pd.date_range(ORDER_START, ORDER_END, freq="D")
    day_w = np.array(
        [MONTH_WEIGHT[d.month] * DOW_WEIGHT[d.dayofweek] for d in days])
    # Black Friday / Cyber Monday spikes, plus a mid-July sale
    for d, mult in [("2024-11-29", 3.0), ("2024-12-02", 2.2), ("2025-07-15", 2.0), ("2025-07-16", 2.0),
                    ("2025-11-28", 3.2), ("2025-12-01", 2.4), ("2026-07-14", 2.0), ("2026-07-15", 2.0)]:
        ts = pd.Timestamp(d)
        if ts in days:
            day_w[(days == ts).argmax()] *= mult
    cum = np.cumsum(day_w)

    first_ok = np.searchsorted(
        days.values, cust_rep["signup_date"].values, side="left")
    first_ok = np.clip(first_ok, 0, len(days) - 1)
    lo = np.where(first_ok > 0, cum[first_ok - 1], 0.0)
    u = lo + rng.random(n) * (cum[-1] - lo)
    day_idx = np.clip(np.searchsorted(cum, u), first_ok, len(days) - 1)
    order_date = days[day_idx]
    order_ts = order_date + \
        pd.to_timedelta(rng.integers(0, 86_400, n), unit="s")

    # --- product: customers have a favourite category (40% of the time)
    cats = list(CATALOG)
    cat_w = np.array([CATALOG[c][0] for c in cats])
    cat_w = cat_w / cat_w.sum()
    fav = rng.choice(cats, size=len(customers), p=cat_w)
    fav_map = dict(zip(customers["customer_id"], fav))
    category = np.empty(n, dtype=object)
    use_fav = rng.random(n) < 0.40
    random_cat = rng.choice(cats, size=n, p=cat_w)
    category[:] = random_cat
    category[use_fav] = cust_rep.loc[use_fav,
                                     "customer_id"].map(fav_map).to_numpy()

    # Seasonal tilt: more Toys/Electronics in Nov-Dec, Sports/Outdoors in summer
    month = order_date.month.to_numpy()
    holiday = np.isin(month, [11, 12]) & (rng.random(n) < 0.18)
    category[holiday] = rng.choice(
        ["Toys & Games", "Electronics", "Clothing"], size=holiday.sum(), p=[0.4, 0.35, 0.25])
    summer = np.isin(month, [5, 6, 7, 8]) & (rng.random(n) < 0.10)
    category[summer] = "Sports & Outdoors"

    # Beauty skews female, Electronics skews male (mild, not absolute)
    g = cust_rep["gender"].to_numpy()
    flip_b = (g == "Female") & (rng.random(n) < 0.06)
    category[flip_b] = "Beauty & Personal Care"
    flip_e = (g == "Male") & (rng.random(n) < 0.06)
    category[flip_e] = "Electronics"

    product_name = np.empty(n, dtype=object)
    base_price = np.empty(n)
    for c in cats:
        mask = category == c
        items = CATALOG[c][2]
        # popular products get more sales (Zipf-ish)
        pw = 1.0 / np.arange(1, len(items) + 1) ** 0.8
        pick = rng.choice(len(items), size=mask.sum(), p=pw / pw.sum())
        product_name[mask] = [items[i][0] for i in pick]
        base_price[mask] = [items[i][1] for i in pick]

    # --- quantity: mostly 1; cheaper items & "bulk-friendly" categories sell more units
    bulk_bias = np.array([CATALOG[c][1] for c in category])
    p_multi = np.clip(0.10 + 0.25 * bulk_bias - base_price / 600, 0.03, 0.40)
    quantity = np.ones(n, dtype=int)
    multi = rng.random(n) < p_multi
    quantity[multi] = 1 + rng.geometric(0.55, multi.sum())
    quantity = np.clip(quantity, 1, 8)

    # --- unit price: base price + mild drift (inflation) + small noise, nice .99 endings
    years = (order_date - ORDER_START).days.to_numpy() / 365.0
    drift = 1 + 0.025 * years
    noise = rng.normal(1.0, 0.04, n)
    unit_price = np.round(base_price * drift * noise).astype(float) - 0.01
    unit_price = np.round(np.maximum(unit_price, 1.99), 2)

    # --- discounts: more in Nov/Dec/Jul, bigger for loyal tiers
    tier = cust_rep["loyalty_tier"].to_numpy()
    tier_boost = pd.Series(tier).map(
        {"Bronze": 0.0, "Silver": 0.03, "Gold": 0.06, "Platinum": 0.10}).to_numpy()
    p_disc = 0.28 + tier_boost + \
        np.where(np.isin(month, [11, 12]), 0.30, 0) + \
        np.where(month == 7, 0.15, 0)
    p_disc = np.clip(p_disc, 0, 0.9)
    has_disc = rng.random(n) < p_disc
    disc_levels = np.array([5, 10, 15, 20, 25, 30, 40])
    base_p = np.array([0.22, 0.30, 0.20, 0.12, 0.08, 0.06, 0.02])
    discount = np.zeros(n)
    discount[has_disc] = rng.choice(disc_levels, size=has_disc.sum(), p=base_p)
    big_sale = np.isin(order_date.strftime("%m-%d"),
                       ["11-28", "11-29", "12-01", "12-02"]) & has_disc
    discount[big_sale] = np.maximum(discount[big_sale], 25)

    # --- shipping method
    ship_method = rng.choice(SHIPPING_METHODS, size=n,
                             p=[0.62, 0.20, 0.07, 0.11])
    # Platinum/Gold members upgrade to faster options more often
    upgrade = np.isin(tier, ["Gold", "Platinum"]) & (
        ship_method == "Standard") & (rng.random(n) < 0.20)
    ship_method[upgrade] = "Express"

    # --- money (all rounded at each step so the row is internally consistent)
    subtotal = np.round(quantity * unit_price * (1 - discount / 100), 2)
    base_ship = pd.Series(ship_method).map(SHIPPING_FEES).to_numpy()
    free_ship = (ship_method == "Standard") & (
        (subtotal >= FREE_SHIPPING_THRESHOLD) | np.isin(tier, ["Gold", "Platinum"]))
    shipping_cost = np.where(free_ship, 0.0, base_ship)
    tax_rate = cust_rep["state"].map(TAX_BY_STATE).to_numpy()
    tax_amount = np.round(subtotal * tax_rate, 2)
    total = np.round(subtotal + shipping_cost + tax_amount, 2)

    # --- payment method (younger => more Apple Pay / BNPL)
    age = cust_rep["age"].fillna(38).to_numpy()
    payment = np.empty(n, dtype=object)
    young = age < 30
    mid = (age >= 30) & (age < 50)
    old = age >= 50
    methods = ["Credit Card", "Debit Card", "PayPal",
               "Apple Pay", "Buy Now Pay Later", "Gift Card"]
    payment[young] = rng.choice(methods, size=young.sum(), p=[
                                0.26, 0.20, 0.12, 0.24, 0.15, 0.03])
    payment[mid] = rng.choice(methods, size=mid.sum(), p=[
                              0.42, 0.20, 0.16, 0.13, 0.07, 0.02])
    payment[old] = rng.choice(methods, size=old.sum(), p=[
                              0.48, 0.22, 0.20, 0.04, 0.02, 0.04])

    # --- status / shipping & delivery timelines (aware of "today" = ORDER_END)
    lead = {m: SHIPPING_DAYS[m] for m in SHIPPING_METHODS}
    transit = np.array([rng.integers(lead[m][0], lead[m][1] + 1)
                       for m in ship_method])
    ship_lag = rng.choice([0, 1, 1, 2, 3], size=n)
    ship_date = order_date + pd.to_timedelta(ship_lag, unit="D")
    delivery_date = ship_date + pd.to_timedelta(transit, unit="D")

    status = rng.choice(["Delivered", "Cancelled", "Returned"], size=n, p=[
                        0.90, 0.04, 0.06]).astype(object)
    # Returns are rarer for Books and common for Clothing
    ret_adj = (category == "Clothing") & (
        status == "Delivered") & (rng.random(n) < 0.04)
    status[ret_adj] = "Returned"
    # Recent orders can't be delivered yet
    in_flight = delivery_date > ORDER_END
    status[in_flight & (status != "Cancelled")] = "Shipped"
    status[(ship_date > ORDER_END) & (status != "Cancelled")] = "Processing"

    ship_date = pd.Series(ship_date)
    delivery_date = pd.Series(delivery_date)
    cancelled = status == "Cancelled"
    ship_date[cancelled | (status == "Processing")] = pd.NaT
    delivery_date[cancelled | np.isin(
        status, ["Processing", "Shipped"])] = pd.NaT

    # --- extras
    channel = rng.choice(
        ["Website", "Mobile App", "Marketplace"], size=n, p=[0.55, 0.35, 0.10])
    coupon = np.full(n, None, dtype=object)
    coupon_mask = has_disc & (rng.random(n) < 0.55)
    coupon_pick = np.where(discount[coupon_mask] >= 30, "VIP30",
                           np.where(discount[coupon_mask] >= 25, "HOLIDAY25",
                           np.where(discount[coupon_mask] >= 20, "SUMMER20",
                                    np.where(discount[coupon_mask] >= 15, "SAVE15", "WELCOME10"))))
    coupon[coupon_mask] = coupon_pick
    is_gift = rng.random(n) < np.where(np.isin(month, [11, 12]), 0.22, 0.05)

    # --- order IDs: unique, random, numeric-only (8 digits)
    order_id = unique_random_ids(rng, n, 10_000_000, 100_000_000)

    orders = pd.DataFrame({
        "order_id": order_id,
        "customer_id": cust_rep["customer_id"].to_numpy(),
        "order_date": order_date.normalize(),
        "order_timestamp": order_ts,
        "product_category": category,
        "product_name": product_name,
        "quantity": quantity,
        "unit_price": unit_price,
        "discount_percent": discount.astype(int),
        "subtotal": subtotal,
        "shipping_cost": np.round(shipping_cost, 2),
        "tax_amount": tax_amount,
        "total_amount": total,
        "payment_method": payment,
        "order_status": status,
        "shipping_method": ship_method,
        "ship_date": ship_date.to_numpy(),
        "delivery_date": delivery_date.to_numpy(),
        "sales_channel": channel,
        "coupon_code": coupon,
        "is_gift": is_gift,
    })

    # --- occasional missing values (only on non-financial, non-key fields)
    for col, rate in [("payment_method", 0.006), ("sales_channel", 0.012)]:
        orders.loc[rng.random(n) < rate, col] = None

    return orders.sort_values(["order_date", "order_timestamp"]).reset_index(drop=True)
# ----------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------


def validate(customers, orders):
    assert len(customers) == N_CUSTOMERS, "customer row count"
    assert len(orders) == N_ORDERS, "order row count"
    assert customers["customer_id"].is_unique and orders["order_id"].is_unique, "PK uniqueness"
    assert orders["customer_id"].isin(
        customers["customer_id"]).all(), "FK integrity"
    inactive = (~customers["customer_id"].isin(orders["customer_id"])).sum()
    assert inactive == N_INACTIVE, f"inactive customers = {inactive}"

    # financial consistency
    sub = (orders["quantity"] * orders["unit_price"] *
           (1 - orders["discount_percent"] / 100)).round(2)
    assert np.allclose(sub, orders["subtotal"], atol=0.011), "subtotal"
    tot = (orders["subtotal"] + orders["shipping_cost"] +
           orders["tax_amount"]).round(2)
    assert np.allclose(tot, orders["total_amount"], atol=0.011), "total_amount"

    # date logic
    merged = orders.merge(
        customers[["customer_id", "signup_date"]], on="customer_id")
    assert (merged["order_date"] >= merged["signup_date"]
            ).all(), "order before signup"
    assert orders["order_date"].min(
    ) >= ORDER_START and orders["order_date"].max() <= ORDER_END
    shipped = orders.dropna(subset=["ship_date"])
    assert (shipped["ship_date"] >= shipped["order_date"]
            ).all(), "ship before order"
    deliv = orders.dropna(subset=["delivery_date"])
    assert (deliv["delivery_date"] >= deliv["ship_date"]
            ).all(), "delivery before ship"
    return inactive


def main():
    ap = argparse.ArgumentParser(
        description="Generate synthetic e-commerce CSVs")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "data")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)

    customers = build_customers(rng)
    counts = allocate_orders(rng, customers)
    customers["loyalty_tier"] = assign_tiers(rng, counts)
    orders = build_orders(rng, customers, counts)

    # Occasional missing values in customers
    n = len(customers)
    customers.loc[rng.random(n) < 0.025, "age"] = np.nan
    customers.loc[rng.random(n) < 0.030, "gender"] = None
    customers.loc[rng.random(n) < 0.015, "email"] = None
    customers["age"] = customers["age"].astype("Int64")

    inactive = validate(customers, orders)

    cols = ["customer_id", "first_name", "last_name", "email", "age", "gender", "signup_date",
            "loyalty_tier", "city", "state", "country", "acquisition_channel", "marketing_opt_in"]
    customers = customers[cols].sort_values(
        "signup_date").reset_index(drop=True)

    args.out.mkdir(parents=True, exist_ok=True)
    customers.to_csv(args.out / "customers.csv",
                     index=False, date_format="%Y-%m-%d")
    orders["order_timestamp"] = orders["order_timestamp"].dt.strftime(
        "%Y-%m-%d %H:%M:%S")
    orders.to_csv(args.out / "orders.csv", index=False, date_format="%Y-%m-%d")

    print(
        f"customers.csv: {len(customers):,} rows ({inactive} with no orders)")
    print(f"orders.csv:    {len(orders):,} rows, "
          f"{orders['order_date'].min()} -> {orders['order_date'].max()}")
    print(
        f"total revenue: ${orders.loc[orders['order_status'] != 'Cancelled', 'total_amount'].sum():,.2f}")
    print("All validation checks passed.")


if __name__ == "__main__":
    main()
