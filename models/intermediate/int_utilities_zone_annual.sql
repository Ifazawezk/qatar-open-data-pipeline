-- Electricity and water consumption per zone and year in one row.
-- A year is complete only if the file was downloaded after that year ended:
-- KAHRAMAA publishes the running year as a partial total (January to August
-- for 2026), and comparing it with full years would look like a collapse.

with electricity as (
    select * from {{ ref('stg_electricity_by_zone') }}
),

water as (
    select * from {{ ref('stg_water_by_zone') }}
),

fetched as (
    select
        min(year(fetched_at)) as first_incomplete_year
    from {{ source('audit', 'source_manifest') }}
    where source_key in ('electricity_by_zone', 'water_by_zone')
)

select
    coalesce(electricity.year, water.year) as year,
    coalesce(electricity.zone_number, water.zone_number) as zone_number,
    electricity.electricity_kwh,
    water.water_m3,
    coalesce(electricity.year, water.year) < fetched.first_incomplete_year as is_complete_year
from electricity
full outer join water
    on electricity.year = water.year
    and electricity.zone_number = water.zone_number
cross join fetched
