-- Practice queries (SQLite syntax; PostgreSQL notes where it differs).
-- Revenue below excludes cancelled orders.
-- ============================== JOINS ======================================
-- 1. Inactive customers (never ordered): anti-join with LEFT JOIN
SELECT   c.customer_id,
         c.first_name,
         c.last_name,
         c.signup_date
FROM     customers AS c
         LEFT OUTER JOIN
         orders AS o
         ON o.customer_id = c.customer_id
WHERE    o.order_id IS NULL
ORDER BY c.signup_date;

-- 2. Revenue and order count by loyalty tier
SELECT   c.loyalty_tier,
         COUNT(DISTINCT c.customer_id) AS customers,
         COUNT(o.order_id) AS orders,
         ROUND(COALESCE (SUM(o.total_amount), 0), 2) AS revenue
FROM     customers AS c
         LEFT OUTER JOIN
         orders AS o
         ON o.customer_id = c.customer_id
            AND o.order_status <> 'Cancelled'
GROUP BY c.loyalty_tier
ORDER BY revenue DESC;

-- ============================ AGGREGATIONS =================================

-- 3. Monthly revenue, orders and average order value
SELECT SUBSTR(order_date, 1, 7)    AS month,
       COUNT(*)                    AS orders,
       ROUND(SUM(total_amount), 2) AS revenue,
       ROUND(AVG(total_amount), 2) AS avg_order_value
FROM orders
WHERE order_status <> 'Cancelled'
GROUP BY SUBSTR(order_date, 1, 7)
ORDER BY month;

-- 4. Return rate by product category
SELECT product_category,
       COUNT(*) AS orders,
       ROUND(100.0 * SUM(CASE WHEN order_status = 'Returned' THEN 1 ELSE 0 END) / COUNT(*), 1) AS return_rate_pct
FROM orders
GROUP BY product_category
ORDER BY return_rate_pct DESC;

-- 5. Discount impact: does discounting change basket size?
SELECT discount_percent,
       COUNT(*)                    AS orders,
       ROUND(AVG(quantity), 2)     AS avg_units,
       ROUND(AVG(total_amount), 2) AS avg_total
FROM orders
GROUP BY discount_percent
ORDER BY discount_percent;

-- ========================== WINDOW FUNCTIONS ===============================

-- 6. Month-over-month revenue growth (LAG)
WITH monthly AS (
    SELECT SUBSTR(order_date, 1, 7) AS month, SUM(total_amount) AS revenue
    FROM orders WHERE order_status <> 'Cancelled'
    GROUP BY SUBSTR(order_date, 1, 7)
)
SELECT month,
       ROUND(revenue, 2) AS revenue,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
             / LAG(revenue) OVER (ORDER BY month), 1) AS mom_growth_pct
FROM monthly
ORDER BY month;

-- 7. Top 3 products per category by revenue (RANK + PARTITION BY)
WITH product_rev AS (
    SELECT product_category, product_name, SUM(total_amount) AS revenue
    FROM orders WHERE order_status <> 'Cancelled'
    GROUP BY product_category, product_name
)
SELECT *
FROM (
    SELECT product_category, product_name, ROUND(revenue, 2) AS revenue,
           RANK() OVER (PARTITION BY product_category ORDER BY revenue DESC) AS rnk
    FROM product_rev
) t
WHERE rnk <= 3
ORDER BY product_category, rnk;

-- 8. Order sequence number and running lifetime spend per customer
SELECT customer_id, order_date, total_amount,
       ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_timestamp) AS order_number,
       ROUND(SUM(total_amount) OVER (PARTITION BY customer_id
                                     ORDER BY order_timestamp
                                     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 2) AS lifetime_spend
FROM orders
WHERE order_status <> 'Cancelled'
ORDER BY customer_id, order_timestamp
LIMIT 50;

-- 9. Days between a customer's consecutive orders (repeat-purchase cadence)
--    PostgreSQL: use (order_date - LAG(order_date) OVER (...)) instead of JULIANDAY.
SELECT customer_id, order_date,
       CAST(JULIANDAY(order_date)
            - JULIANDAY(LAG(order_date) OVER (PARTITION BY customer_id ORDER BY order_timestamp)) AS INTEGER)
         AS days_since_prev_order
FROM orders
ORDER BY customer_id, order_timestamp
LIMIT 50;

-- 10. 3-month moving average of revenue
WITH monthly AS (
    SELECT SUBSTR(order_date, 1, 7) AS month, SUM(total_amount) AS revenue
    FROM orders WHERE order_status <> 'Cancelled'
    GROUP BY SUBSTR(order_date, 1, 7)
)
SELECT month, ROUND(revenue, 2) AS revenue,
       ROUND(AVG(revenue) OVER (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS moving_avg_3m
FROM monthly
ORDER BY month;
-- ============================ DASHBOARD-STYLE ==============================

-- 11. RFM segmentation (recency / frequency / monetary quartiles with NTILE)
WITH rfm AS (
    SELECT customer_id,
           CAST(JULIANDAY('2026-09-30') - JULIANDAY(MAX(order_date)) AS INTEGER) AS recency_days,
           COUNT(*)          AS frequency,
           SUM(total_amount) AS monetary
    FROM orders WHERE order_status <> 'Cancelled'
    GROUP BY customer_id
)
SELECT customer_id, recency_days, frequency, ROUND(monetary, 2) AS monetary,
       NTILE(4) OVER (ORDER BY recency_days DESC) AS r_score,   -- 4 = most recent
       NTILE(4) OVER (ORDER BY frequency)         AS f_score,
       NTILE(4) OVER (ORDER BY monetary)          AS m_score
FROM rfm
ORDER BY monetary DESC
LIMIT 25;

-- 12. Signup-cohort retention: share of each signup-year cohort that ordered in each order-year
WITH cohort AS (
    SELECT customer_id, SUBSTR(signup_date, 1, 4) AS signup_year FROM customers
),
activity AS (
    SELECT DISTINCT customer_id, SUBSTR(order_date, 1, 4) AS order_year FROM orders
)
SELECT c.signup_year, a.order_year,
       COUNT(DISTINCT a.customer_id) AS active_customers,
       ROUND(100.0 * COUNT(DISTINCT a.customer_id)
             / (SELECT COUNT(*) FROM cohort c2 WHERE c2.signup_year = c.signup_year), 1) AS pct_of_cohort
FROM cohort c
JOIN activity a ON a.customer_id = c.customer_id
GROUP BY c.signup_year, a.order_year
ORDER BY c.signup_year, a.order_year;

-- 13. Revenue by state with share of total (window over an aggregate)
SELECT c.state,
       ROUND(SUM(o.total_amount), 2) AS revenue,
       ROUND(100.0 * SUM(o.total_amount) / SUM(SUM(o.total_amount)) OVER (), 1) AS pct_of_total
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.order_status <> 'Cancelled'
GROUP BY c.state
ORDER BY revenue DESC;

-- 14. Data-quality check: financial identity must hold (should return 0 rows)
SELECT order_id
FROM orders
WHERE ABS(total_amount - (subtotal + shipping_cost + tax_amount)) > 0.011;
