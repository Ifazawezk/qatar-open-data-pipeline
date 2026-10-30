-- Monthly consumer price index by expenditure group (base 2018 = 100).
-- The source mixes month abbreviations, writes the general index code as "0"
-- and has typos in the English group names, so codes are padded to three
-- digits and English names come from the cpi_groups seed.

with source as (
    select * from {{ source('cpi_monthly') }}
),

months as (
    select cast(month_number as integer) as month, lower(month_abbr) as month_abbr
    from {{ seed('months') }}
),

groups as (
    select group_code, group_name_en, short_name_en
    from {{ seed('cpi_groups') }}
),

typed as (
    select
        try_cast(trim(source.year) as integer) as year,
        months.month,
        lpad(trim(source.group_code), 3, '0') as group_code,
        regexp_replace(trim(source.lmjmw), '\s+', ' ', 'g') as group_name_ar,
        try_cast(trim(source.cpi_index) as double) as cpi_index
    from source
    left join months on lower(left(trim(source.month), 3)) = months.month_abbr
)

select
    make_date(typed.year, typed.month, 1) as month_start,
    typed.year,
    typed.month,
    typed.group_code,
    groups.group_name_en,
    groups.short_name_en as group_short_name_en,
    typed.group_name_ar,
    typed.group_code = '000' as is_general_index,
    typed.cpi_index
from typed
left join groups on typed.group_code = groups.group_code
