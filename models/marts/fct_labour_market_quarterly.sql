-- Quarterly labour market indicators by sex (male, female, total) with the
-- standard rates:
--   participation rate     = economically active / population 15+
--   unemployment rate      = unemployed / economically active
--   employment-to-pop rate = employed / population 15+
-- Population growth compares with the same quarter one year earlier.

with lf as (
    select * from {{ ref('int_labour_force_quarterly') }}
)

select
    cur.quarter_start,
    cur.year,
    cur.quarter,
    cur.quarter_label,
    cur.sex,
    cur.sex_en,
    cur.sex_ar,
    cur.population,
    cur.population_15_plus,
    cur.economically_active,
    cur.economically_inactive,
    cur.employed,
    cur.unemployed,
    100.0 * cur.economically_active / cur.population_15_plus as participation_rate_pct,
    100.0 * cur.unemployed / cur.economically_active as unemployment_rate_pct,
    100.0 * cur.employed / cur.population_15_plus as employment_to_population_pct,
    100.0 * (cur.population / prev.population - 1) as population_yoy_pct
from lf as cur
left join lf as prev
    on prev.sex = cur.sex
    and prev.year = cur.year - 1
    and prev.quarter = cur.quarter
