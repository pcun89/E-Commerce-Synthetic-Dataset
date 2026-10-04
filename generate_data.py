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
