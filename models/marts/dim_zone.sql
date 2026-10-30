-- Zone dimension with English and Arabic names. Many zones group several
-- districts ("Leabaib / Al Ebb / ..."), so a short name (first district) is
-- added for charts. Zones that appear in the utility files but not in the
-- names table still get a row so joins never drop consumption.

with named as (
    select * from {{ ref('stg_zones') }}
),

used as (
    select zone_number from {{ ref('stg_electricity_by_zone') }}
    union
    select zone_number from {{ ref('stg_water_by_zone') }}
),

all_zones as (
    select zone_number from named
    union
    select zone_number from used
)

select
    all_zones.zone_number,
    coalesce(named.zone_name_en, 'Zone ' || all_zones.zone_number) as zone_name_en,
    named.zone_name_ar,
    coalesce(split_part(named.zone_name_en, ' / ', 1), 'Zone ' || all_zones.zone_number)
        as zone_short_name_en,
    split_part(named.zone_name_ar, ' / ', 1) as zone_short_name_ar,
    'Zone ' || all_zones.zone_number || ': '
        || coalesce(split_part(named.zone_name_en, ' / ', 1), 'unnamed')
        || case when named.zone_name_en like '% / %' then ' and others' else '' end
        as zone_label,
    named.zone_number is not null as has_name
from all_zones
left join named on all_zones.zone_number = named.zone_number
