-- Quarterly population and labour force counts by sex from the Labour Force
-- Survey. One row per quarter, sex and indicator. Free-text labels are mapped
-- to stable codes; the Arabic labels from the source are kept.

with source as (
    select * from {{ source('population_labour_force') }}
),

typed as (
    select
        try_cast(trim(year) as integer) as year,
        try_cast(regexp_extract(quarter, '[1-4]') as integer) as quarter,
        lower(trim(gender)) as gender_raw,
        trim(ljns) as sex_ar,
        trim(indicator) as indicator_en,
        trim(lmw_shr) as indicator_ar,
        try_cast(trim(number) as bigint) as persons
    from source
)

select
    year,
    quarter,
    make_date(year, (quarter - 1) * 3 + 1, 1) as quarter_start,
    year || '-Q' || quarter as quarter_label,
    case gender_raw
        when 'males' then 'male'
        when 'females' then 'female'
    end as sex,
    sex_ar,
    case indicator_en
        when 'Population' then 'population'
        when 'Population (15 Years & above)' then 'population_15_plus'
        when 'Economically Active' then 'economically_active'
        when 'Economically Inactive' then 'economically_inactive'
        when 'Employed' then 'employed'
    end as indicator,
    indicator_en,
    indicator_ar,
    persons
from typed
