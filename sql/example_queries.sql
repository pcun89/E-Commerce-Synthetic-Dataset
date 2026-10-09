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