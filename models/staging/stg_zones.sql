-- One row per official zone with its English and Arabic name. The source
-- repeats each zone for several years, so the name from the latest year
-- wins. Population columns are ignored: they stop in 2019 and are mostly
-- empty.

with source as (
    select
        try_cast(trim(number_of_zone) as integer) as zone_number,
        try_cast(trim(year) as integer) as year,
        regexp_replace(trim(zone), '\s+', ' ', 'g') as zone_name_en,
        regexp_replace(trim(lmntq), '\s+', ' ', 'g') as zone_name_ar
    from {{ source('zones') }}
    where nullif(trim(zone), '') is not null
)

select
    zone_number,
    arg_max(zone_name_en, year) as zone_name_en,
    arg_max(zone_name_ar, year) as zone_name_ar
from source
group by zone_number
