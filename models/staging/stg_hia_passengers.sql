-- Monthly passengers through Hamad International Airport. One row per month
-- and direction (arrivals or departures). Transit passengers are not part of
-- this dataset.

with source as (
    select * from {{ source('hia_passengers') }}
),

months as (
    select cast(month_number as integer) as month, lower(month_abbr) as month_abbr
    from {{ seed('months') }}
)

select
    make_date(try_cast(trim(source.year) as integer), months.month, 1) as month_start,
    try_cast(trim(source.year) as integer) as year,
    months.month,
    lower(trim(source.type)) as direction,
    trim(source.nw) as direction_ar,
    try_cast(trim(source.total) as bigint) as passengers
from source
left join months on lower(left(trim(source.month), 3)) = months.month_abbr
