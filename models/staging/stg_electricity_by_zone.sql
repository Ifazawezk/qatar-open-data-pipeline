-- Annual electricity consumption (kWh) per official zone, as published by
-- KAHRAMAA. The most recent year is partial; completeness is decided later
-- in the intermediate layer.

select
    try_cast(trim(year) as integer) as year,
    try_cast(trim(zone_number) as integer) as zone_number,
    try_cast(trim(value) as bigint) as electricity_kwh
from {{ source('electricity_by_zone') }}
