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

