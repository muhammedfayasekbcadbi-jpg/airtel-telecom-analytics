DROP VIEW IF EXISTS v_plans_clean;

CREATE VIEW v_plans_clean AS
SELECT
    plan_id,
    plan_name,
    plan_type,
    price_inr,
    validity_days,
    data_quota,
    CASE
        WHEN plan_type = 'Prepaid' THEN 'per day'
        ELSE 'per month'
    END AS quota_basis,
    CAST(data_quota AS REAL) AS quota_gb,
    CASE
        WHEN plan_type = 'Prepaid' THEN CAST(data_quota AS REAL) * 30
        ELSE CAST(data_quota AS REAL)
    END AS monthly_gb,
    ott_benefit,
    is_5g
FROM plans;
