-- Annual water consumption (cubic metres) per official zone, as published
-- by KAHRAMAA. Same layout and coverage as the electricity file.

select
    try_cast(trim(year) as integer) as year,
    try_cast(trim(zone_number) as integer) as zone_number,
    try_cast(trim(value) as bigint) as water_m3
from {{ source('water_by_zone') }}
