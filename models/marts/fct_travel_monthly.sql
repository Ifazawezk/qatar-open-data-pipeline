-- Monthly travel and tourism activity: Hamad International Airport
-- passengers and hotel guests / nights on one calendar. The two sources
-- cover different periods (airport 2017-2022, hotels 2019-2023), so a
-- column is NULL where its source has no data for that month.

with calendar as (
    select * from {{ ref('dim_month') }}
),

airport as (
    select * from {{ ref('int_airport_monthly') }}
),

hotel as (
    select * from {{ ref('int_hotel_monthly') }}
),

joined as (
    select
        calendar.month_start,
        calendar.year,
        calendar.month,
        calendar.year_month,
        calendar.month_name_en,
        calendar.month_name_ar,
        airport.arrivals as airport_arrivals,
        airport.departures as airport_departures,
        airport.passengers as airport_passengers,
        hotel.guests as hotel_guests,
        hotel.nights as hotel_nights
    from calendar
    left join airport on calendar.month_start = airport.month_start
    left join hotel on calendar.month_start = hotel.month_start
    where airport.month_start is not null or hotel.month_start is not null
)

select
    cur.*,
    cur.hotel_nights / nullif(cur.hotel_guests, 0) as nights_per_guest,
    100.0 * (cur.airport_passengers / prev.airport_passengers - 1) as airport_passengers_yoy_pct,
    100.0 * (cur.hotel_guests / prev.hotel_guests - 1) as hotel_guests_yoy_pct
from joined as cur
left join joined as prev
    on prev.month_start = cur.month_start - interval 1 year
