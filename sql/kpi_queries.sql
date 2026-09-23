-- KPI queries on the star schema.
-- Same definitions as sca/kpis.py, used to cross check the pandas numbers.

-- 1. overall summary
SELECT
    ROUND(SUM(CASE WHEN is_return = 0 THEN line_amount ELSE 0 END), 2)  AS gross_revenue,
    ROUND(-SUM(CASE WHEN is_return = 1 THEN line_amount ELSE 0 END), 2) AS returns_value,
    ROUND(SUM(line_amount), 2)                                          AS net_revenue,
    COUNT(DISTINCT CASE WHEN is_return = 0 THEN order_id END)           AS orders
FROM fact_sales;

-- 2. monthly net revenue and orders
SELECT d.year, d.month,
       ROUND(SUM(f.line_amount), 2)                                       AS net_revenue,
       COUNT(DISTINCT CASE WHEN f.is_return = 0 THEN f.order_id END)      AS orders
FROM fact_sales f
JOIN dim_date d ON d.date_key = f.date_key
GROUP BY d.year, d.month
ORDER BY d.year, d.month;

-- 3. revenue by region
SELECT c.region,
       ROUND(SUM(f.line_amount), 2) AS net_revenue
FROM fact_sales f
JOIN dim_customer c ON c.customer_key = f.customer_key
GROUP BY c.region
ORDER BY net_revenue DESC;

-- 4. top 10 products by revenue (normal lines only)
SELECT p.product_id, p.product_name, p.category,
       SUM(f.quantity)               AS units,
       ROUND(SUM(f.line_amount), 2)  AS revenue
FROM fact_sales f
JOIN dim_product p ON p.product_key = f.product_key
WHERE f.is_return = 0
GROUP BY p.product_id, p.product_name, p.category
ORDER BY revenue DESC
LIMIT 10;

-- 5. category x channel
SELECT p.category, f.channel,
       ROUND(SUM(f.line_amount), 2) AS net_revenue
FROM fact_sales f
JOIN dim_product p ON p.product_key = f.product_key
GROUP BY p.category, f.channel
ORDER BY p.category, net_revenue DESC;

-- 6. repeat customers (more than one order)
SELECT ROUND(100.0 * SUM(CASE WHEN n_orders > 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS repeat_customer_pct
FROM (
    SELECT customer_key, COUNT(DISTINCT order_id) AS n_orders
    FROM fact_sales
    WHERE is_return = 0
    GROUP BY customer_key
) t;
