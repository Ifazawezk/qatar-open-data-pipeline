-- CPI with month-on-month and year-on-year changes per expenditure group.
-- Changes come from joins on the calendar month rather than lag(), so a
-- missing month gives NULL instead of comparing against the wrong month.

with cpi as (
    select * from {{ ref('stg_cpi_monthly') }}
)

select
    cur.month_start,
    cur.year,
    cur.month,
    cur.group_code,
    cur.group_name_en,
    cur.group_short_name_en,
    cur.group_name_ar,
    cur.is_general_index,
    cur.cpi_index,
    (cur.cpi_index / prev_month.cpi_index - 1) * 100 as mom_change_pct,
    (cur.cpi_index / prev_year.cpi_index - 1) * 100 as yoy_change_pct
from cpi as cur
left join cpi as prev_month
    on prev_month.group_code = cur.group_code
    and prev_month.month_start = cur.month_start - interval 1 month
left join cpi as prev_year
    on prev_year.group_code = cur.group_code
    and prev_year.month_start = cur.month_start - interval 1 year
