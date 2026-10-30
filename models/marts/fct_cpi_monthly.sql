-- Monthly CPI per expenditure group with month-on-month and year-on-year
-- changes (base 2018 = 100). One row per month and group.

select
    month_start,
    year,
    month,
    group_code,
    group_name_en,
    group_short_name_en,
    group_name_ar,
    is_general_index,
    cpi_index,
    mom_change_pct,
    yoy_change_pct
from {{ ref('int_cpi_monthly_changes') }}
