DROP VIEW IF EXISTS v_revenue_customer;

CREATE VIEW v_revenue_customer AS
WITH recharge_totals AS (
    SELECT
        customer_id,
        COUNT(*) AS recharge_count,
        SUM(amount_inr) AS recharge_total_6m
    FROM recharges
    WHERE recharge_date >= '2025-01-01'
      AND recharge_date < '2025-07-01'
    GROUP BY customer_id
)
SELECT
    c.customer_id,
    COALESCE(r.recharge_count, 0) AS recharge_count,
    COALESCE(r.recharge_total_6m, 0) AS recharge_total_6m,
    ROUND(COALESCE(r.recharge_total_6m, 0) / 6.0, 2) AS actual_arpu_6m,
    c.arpu_inr AS stated_arpu,
    ROUND(c.arpu_inr - COALESCE(r.recharge_total_6m, 0) / 6.0, 2) AS arpu_gap
FROM customers AS c
LEFT JOIN recharge_totals AS r
    ON r.customer_id = c.customer_id;
