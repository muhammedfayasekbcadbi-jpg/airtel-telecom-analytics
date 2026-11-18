DROP VIEW IF EXISTS v_usage_customer;

CREATE VIEW v_usage_customer AS
WITH usage_totals AS (
    SELECT
        customer_id,
        COUNT(DISTINCT usage_date) AS usage_days,
        SUM(data_mb) AS total_data_mb,
        SUM(voice_minutes) AS total_voice_min,
        SUM(sms_count) AS total_sms,
        SUM(is_roaming) AS roaming_days,
        MAX(usage_date) AS last_usage_date
    FROM usage_daily
    WHERE usage_date >= '2025-01-01'
      AND usage_date < '2025-07-01'
    GROUP BY customer_id
)
SELECT
    c.customer_id,
    COALESCE(u.usage_days, 0) AS usage_days,
    COALESCE(u.total_data_mb, 0) AS total_data_mb,
    COALESCE(u.total_voice_min, 0) AS total_voice_min,
    COALESCE(u.total_sms, 0) AS total_sms,
    COALESCE(u.roaming_days, 0) AS roaming_days,
    ROUND(u.total_data_mb / NULLIF(u.usage_days, 0), 2) AS mb_per_active_day,
    ROUND(COALESCE(u.total_data_mb, 0) / 181.0, 2) AS mb_per_observed_day,
    u.last_usage_date,
    CAST(julianday('2025-06-30') - julianday(u.last_usage_date) AS INTEGER)
        AS recency_days
FROM customers AS c
LEFT JOIN usage_totals AS u
    ON u.customer_id = c.customer_id;
