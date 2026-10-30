-- Qatar at a glance: one row per year with a headline figure from every
-- dataset. Each figure is only filled for years its source covers in full,
-- so an annual total is never built from part of a year.

with population as (
    select
        cur.year,
        cur.avg_population,
        100.0 * (cur.avg_population / prev.avg_population - 1) as population_growth_pct
    from {{ ref('int_population_annual') }} as cur
    left join {{ ref('int_population_annual') }} as prev
        on prev.year = cur.year - 1
        and prev.is_complete_year
    where cur.is_complete_year
),

labour as (
    select
        year,
        100.0 * sum(economically_active) filter (where sex = 'total')
            / sum(population_15_plus) filter (where sex = 'total') as participation_rate_pct,
        100.0 * sum(economically_active) filter (where sex = 'female')
            / sum(population_15_plus) filter (where sex = 'female')
            as female_participation_rate_pct,
        100.0 * sum(unemployed) filter (where sex = 'total')
            / sum(economically_active) filter (where sex = 'total') as unemployment_rate_pct
    from {{ ref('fct_labour_market_quarterly') }}
    group by year
    having count(*) filter (where sex = 'total') = 4
),

prices as (
    select
        year,
        avg_index as cpi_avg_index,
        avg_inflation_pct as cpi_inflation_pct
    from {{ ref('fct_inflation_annual') }}
    where is_general_index and months_reported = 12
),

travel as (
    select
        year,
        case when count(airport_passengers) = 12 then sum(airport_passengers) end
            as airport_passengers,
        case when count(hotel_guests) = 12 then sum(hotel_guests) end as hotel_guests,
        case when count(hotel_nights) = 12 then sum(hotel_nights) end as hotel_nights
    from {{ ref('fct_travel_monthly') }}
    group by year
),

utilities as (
    select
        year,
        electricity_gwh,
        electricity_kwh_per_capita,
        water_million_m3,
        water_litres_per_capita_per_day
    from {{ ref('fct_utilities_national_annual') }}
    where is_complete_year
),

years as (
    select year from population
    union select year from labour
    union select year from prices
    union select year from travel
    union select year from utilities
)

select
    years.year,
    population.avg_population,
    population.population_growth_pct,
    labour.participation_rate_pct,
    labour.female_participation_rate_pct,
    labour.unemployment_rate_pct,
    prices.cpi_avg_index,
    prices.cpi_inflation_pct,
    travel.airport_passengers,
    travel.hotel_guests,
    travel.hotel_nights,
    utilities.electricity_gwh,
    utilities.electricity_kwh_per_capita,
    utilities.water_million_m3,
    utilities.water_litres_per_capita_per_day
from years
left join population on years.year = population.year
left join labour on years.year = labour.year
left join prices on years.year = prices.year
left join travel on years.year = travel.year
left join utilities on years.year = utilities.year
