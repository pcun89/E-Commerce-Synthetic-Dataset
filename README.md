# E-Commerce Synthetic Dataset

A reproducible generator for a realistic, relational e-commerce dataset for **SQL practice, analytics, dashboards, and data-engineering projects**.

| Table | Rows | Key |
|---|---|---|
| `customers` | 1,000 (about 100 have never ordered) | `customer_id` (PK) |
| `orders` | 5,000 | `order_id` (PK), `customer_id` (FK to customers) |

## Quick start

```bash
pip install -r requirements.txt
python generate_data.py        # writes data/customers.csv and data/orders.csv
```

No local setup needed: go to the **Actions** tab, run **Generate dataset**, and the CSVs are committed to `data/`.

Options: `python generate_data.py --seed 7 --out my_folder` (same seed gives identical data).

## What makes the data realistic

- Random numeric IDs (6-digit customers, 8-digit orders)
- Two-year order window: 2024-10-01 to 2026-09-30
- Seasonality: Nov/Dec peaks, January dip, July sale bump, Black Friday spikes
- Repeat customers with a heavy-tailed orders-per-customer distribution
- Exactly 100 inactive customers (no orders)
- No order before a customer's signup date; ship and delivery dates are in order
- Loyalty tier follows order count and drives discounts and free shipping
- Payment method correlates with age; discounts deepen in holiday months
- Consistent financials: `subtotal = qty x unit_price x (1 - discount%)`, `total = subtotal + shipping + tax`
- Intentional missing values in non-key, non-financial columns

The script validates row counts, keys, financial math, and date logic before writing any file.

## Practice queries

`sql/example_queries.sql` has 14 queries covering joins, aggregations, window functions (LAG, RANK, NTILE, running totals), cohort retention, and RFM segmentation.

## License

MIT. All data is fictional and randomly generated.