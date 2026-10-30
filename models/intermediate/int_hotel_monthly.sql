-- Hotel guests and nights of stay per month side by side.

select
    month_start,
    sum(value) filter (where measure = 'guests') as guests,
    sum(value) filter (where measure = 'nights') as nights
from {{ ref('stg_hotel_guests_nights') }}
group by month_start
