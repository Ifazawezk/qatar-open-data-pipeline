-- Electricity and water consumption per zone and year, with each zone's
-- share of the national total, its rank, and growth on the previous year.
-- Growth is only filled when both years are complete.

with zone_year as (
    select * from {{ ref('int_utilities_zone_annual') }}
),

with_totals as (
    select
        *,
        sum(electricity_kwh) over (partition by year) as national_electricity_kwh,
        sum(water_m3) over (partition by year) as national_water_m3
    from zone_year
)

select
    cur.year,
    cur.zone_number,
    zones.zone_label,
    zones.zone_name_en,
    zones.zone_name_ar,
    cur.is_complete_year,
    cur.electricity_kwh,
    cur.water_m3,
    100.0 * cur.electricity_kwh / nullif(cur.national_electricity_kwh, 0)
        as electricity_share_pct,
    100.0 * cur.water_m3 / nullif(cur.national_water_m3, 0) as water_share_pct,
    rank() over (partition by cur.year order by cur.electricity_kwh desc nulls last)
        as electricity_rank,
    case
        when cur.is_complete_year and prev.is_complete_year
            then 100.0 * (cur.electricity_kwh / nullif(prev.electricity_kwh, 0) - 1)
    end as electricity_yoy_pct,
    case
        when cur.is_complete_year and prev.is_complete_year
            then 100.0 * (cur.water_m3 / nullif(prev.water_m3, 0) - 1)
    end as water_yoy_pct
from with_totals as cur
left join zone_year as prev
    on prev.zone_number = cur.zone_number
    and prev.year = cur.year - 1
left join {{ ref('dim_zone') }} as zones
    on cur.zone_number = zones.zone_number
