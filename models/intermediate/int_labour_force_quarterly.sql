-- Labour force indicators pivoted to one row per quarter and sex, plus a
-- 'total' row per quarter that adds males and females together.
-- Unemployed persons are derived as economically active minus employed.

with by_sex as (
    select
        year,
        quarter,
        quarter_start,
        quarter_label,
        sex,
        any_value(sex_ar) as sex_ar,
        sum(persons) filter (where indicator = 'population') as population,
        sum(persons) filter (where indicator = 'population_15_plus') as population_15_plus,
        sum(persons) filter (where indicator = 'economically_active') as economically_active,
        sum(persons) filter (where indicator = 'economically_inactive') as economically_inactive,
        sum(persons) filter (where indicator = 'employed') as employed
    from {{ ref('stg_population_labour_force') }}
    group by year, quarter, quarter_start, quarter_label, sex
),

total as (
    select
        year,
        quarter,
        quarter_start,
        quarter_label,
        'total' as sex,
        'الإجمالي' as sex_ar,
        sum(population) as population,
        sum(population_15_plus) as population_15_plus,
        sum(economically_active) as economically_active,
        sum(economically_inactive) as economically_inactive,
        sum(employed) as employed
    from by_sex
    group by year, quarter, quarter_start, quarter_label
),

combined as (
    select * from by_sex
    union all by name
    select * from total
)

select
    year,
    quarter,
    quarter_start,
    quarter_label,
    sex,
    case sex when 'male' then 'Male' when 'female' then 'Female' else 'Total' end as sex_en,
    sex_ar,
    cast(population as bigint) as population,
    cast(population_15_plus as bigint) as population_15_plus,
    cast(economically_active as bigint) as economically_active,
    cast(economically_inactive as bigint) as economically_inactive,
    cast(employed as bigint) as employed,
    cast(economically_active - employed as bigint) as unemployed
from combined
