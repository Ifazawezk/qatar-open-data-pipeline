-- National electricity and water consumption per year, with per-capita
-- figures based on the average quarterly population. Per-capita values and
-- growth rates are left NULL for partial years, which would otherwise look
-- like a sharp drop.

with totals as (
    select
        year,
        bool_and(is_complete_year) as is_complete_year,
        count(*) as zones_reported,
        sum(electricity_kwh) as electricity_kwh,
        sum(water_m3) as water_m3
    from {{ ref('int_utilities_zone_annual') }}
    group by year
),

joined as (
    select
        totals.*,
        population.avg_population,
        datediff('day', make_date(totals.year, 1, 1), make_date(totals.year + 1, 1, 1))
            as days_in_year
    from totals
    left join {{ ref('int_population_annual') }} as population
        on totals.year = population.year
        and population.is_complete_year
)

select
    cur.year,
    cur.is_complete_year,
    cur.zones_reported,
    cur.electricity_kwh,
    cur.electricity_kwh / 1e6 as electricity_gwh,
    cur.water_m3,
    cur.water_m3 / 1e6 as water_million_m3,
    cur.avg_population,
    case when cur.is_complete_year then cur.electricity_kwh / cur.avg_population end
        as electricity_kwh_per_capita,
    case when cur.is_complete_year then cur.water_m3 / cur.avg_population end
        as water_m3_per_capita,
    case
        when cur.is_complete_year
            then 1000.0 * cur.water_m3 / cur.avg_population / cur.days_in_year
    end as water_litres_per_capita_per_day,
    case
        when cur.is_complete_year and prev.is_complete_year
            then 100.0 * (cur.electricity_kwh / prev.electricity_kwh - 1)
    end as electricity_yoy_pct,
    case
        when cur.is_complete_year and prev.is_complete_year
            then 100.0 * (cur.water_m3 / prev.water_m3 - 1)
    end as water_yoy_pct
from joined as cur
left join joined as prev
    on prev.year = cur.year - 1
