-- Calendar of months covering every monthly dataset, with English and
-- Arabic month names. Monthly facts join to it on month_start.

with bounds as (
    select min(month_start) as first_month, max(month_start) as last_month
    from (
        select month_start from {{ ref('stg_cpi_monthly') }}
        union all
        select month_start from {{ ref('stg_hia_passengers') }}
        union all
        select month_start from {{ ref('stg_hotel_guests_nights') }}
    )
),

spine as (
    select cast(unnest(generate_series(first_month, last_month, interval 1 month)) as date)
        as month_start
    from bounds
)

select
    spine.month_start,
    year(spine.month_start) as year,
    quarter(spine.month_start) as quarter,
    month(spine.month_start) as month,
    strftime(spine.month_start, '%Y-%m') as year_month,
    months.month_abbr,
    months.month_name_en,
    months.month_name_ar
from spine
join {{ seed('months') }} as months
    on month(spine.month_start) = cast(months.month_number as integer)
