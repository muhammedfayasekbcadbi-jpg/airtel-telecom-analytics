DROP VIEW IF EXISTS v_complaint_customer;

CREATE VIEW v_complaint_customer AS
WITH complaint_totals AS (
    SELECT
        customer_id,
        COUNT(*) AS complaint_count,
        SUM(CASE WHEN is_resolved = 0 THEN 1 ELSE 0 END) AS unresolved_count,
        SUM(CASE WHEN is_resolved = 1 THEN 1 ELSE 0 END) AS resolved_count,
        AVG(CASE WHEN is_resolved = 1 THEN resolution_days END)
            AS avg_resolution_days
    FROM complaints
    WHERE complaint_date >= '2025-01-01'
      AND complaint_date < '2025-07-01'
    GROUP BY customer_id
)
SELECT
    c.customer_id,
    COALESCE(t.complaint_count, 0) AS complaint_count,
    COALESCE(t.unresolved_count, 0) AS unresolved_count,
    COALESCE(t.resolved_count, 0) AS resolved_count,
    ROUND(t.avg_resolution_days, 2) AS avg_resolution_days
FROM customers AS c
LEFT JOIN complaint_totals AS t
    ON t.customer_id = c.customer_id;
