-- Annual inflation per expenditure group. Two common measures:
--   avg_inflation_pct: change in the 12-month average index (needs two full years)
--   dec_on_dec_pct:    change from December of last year to December
-- Years with fewer than 12 months of data get NULL changes.

with yearly as (
    select
        year,
        group_code,
        any_value(group_name_en) as group_name_en,
        any_value(group_short_name_en) as group_short_name_en,
        any_value(group_name_ar) as group_name_ar,
        bool_or(is_general_index) as is_general_index,
        count(*) as months_reported,
        avg(cpi_index) as avg_index,
        max(cpi_index) filter (where month = 12) as december_index
    from {{ ref('fct_cpi_monthly') }}
    group by year, group_code
)

select
    cur.year,
    cur.group_code,
    cur.group_name_en,
    cur.group_short_name_en,
    cur.group_name_ar,
    cur.is_general_index,
    cur.months_reported,
    cur.avg_index,
    cur.december_index,
    case
        when cur.months_reported = 12 and prev.months_reported = 12
            then 100.0 * (cur.avg_index / prev.avg_index - 1)
    end as avg_inflation_pct,
    100.0 * (cur.december_index / prev.december_index - 1) as dec_on_dec_pct
from yearly as cur
left join yearly as prev
    on prev.group_code = cur.group_code
    and prev.year = cur.year - 1
