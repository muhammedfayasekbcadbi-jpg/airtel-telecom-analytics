DROP VIEW IF EXISTS v_usage_month;

CREATE VIEW v_usage_month AS
SELECT
    customer_id,
    strftime('%Y-%m', usage_date) AS month,
    COUNT(DISTINCT usage_date) AS usage_days,
    SUM(data_mb) AS total_mb,
    SUM(voice_minutes) AS total_voice,
    SUM(is_roaming) AS roaming_days
FROM usage_daily
WHERE usage_date >= '2025-01-01'
  AND usage_date < '2025-07-01'
GROUP BY customer_id, strftime('%Y-%m', usage_date);
