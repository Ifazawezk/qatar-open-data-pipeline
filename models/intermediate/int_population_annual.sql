-- Annual population used as the denominator for per-capita figures: the
-- average of the quarterly survey estimates in each year. A year only counts
-- as complete when all four quarters are published.

select
    year,
    count(*) as quarters_reported,
    count(*) = 4 as is_complete_year,
    avg(population) as avg_population,
    arg_max(population, quarter) as latest_quarter_population,
    avg(population_15_plus) as avg_population_15_plus
from {{ ref('int_labour_force_quarterly') }}
where sex = 'total'
group by year
