-- Monthly hotel guests and nights of stay. In the source the year and the
-- measure share one text column ("2021  Guests", "2021 Nights", with uneven
-- spacing), so both are parsed out here. Values arrive as "499407.0".

with source as (
    select * from {{ source('hotel_guests_nights') }}
),

months as (
    select cast(month_number as integer) as month, lower(month_abbr) as month_abbr
    from {{ seed('months') }}
),

parsed as (
    select
        try_cast(regexp_extract(source.year, '(\d{4})', 1) as integer) as year,
        months.month,
        case
            when source.year ilike '%guest%' then 'guests'
            when source.year ilike '%night%' then 'nights'
        end as measure,
        trim(regexp_replace(source.sn, '^\s*\d{4}\s*', '')) as measure_ar,
        try_cast(trim(source.value) as double) as value
    from source
    left join months on lower(left(trim(source.month), 3)) = months.month_abbr
)

select
    make_date(year, month, 1) as month_start,
    year,
    month,
    measure,
    measure_ar,
    cast(round(value) as bigint) as value
from parsed
