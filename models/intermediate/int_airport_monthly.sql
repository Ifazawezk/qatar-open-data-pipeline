-- Hamad International Airport passengers per month with arrivals and
-- departures side by side. Total passengers = arrivals + departures
-- (transit passengers are not in this dataset).

select
    month_start,
    sum(passengers) filter (where direction = 'arrivals') as arrivals,
    sum(passengers) filter (where direction = 'departures') as departures,
    sum(passengers) as passengers
from {{ ref('stg_hia_passengers') }}
group by month_start
