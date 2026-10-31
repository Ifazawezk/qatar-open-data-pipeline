"""Short written findings computed from the marts.

Every sentence is built from the data at render time, so the text stays
right when the portal publishes new figures. A function returns fewer
sentences (or none) when the data it needs is missing.
"""

from __future__ import annotations

import pandas as pd

from dashboard.i18n import localised, tr, zone_label


def pct(value: float, signed: bool = True) -> str:
    return f"{value:+.1f}%" if signed else f"{value:.1f}%"


def change(value: float) -> str:
    """'grew 4.2%' or 'fell 4.2%'."""
    size = f"{abs(value):.1f}"
    return tr("grew {value}%", value=size) if value >= 0 else tr("fell {value}%", value=size)


def millions(value: float, digits: int = 2) -> str:
    return tr("{value} million", value=f"{value / 1e6:,.{digits}f}")


def _by_year(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Rows with a value in `column`, sorted by year, with year as int."""
    out = df.dropna(subset=[column]).sort_values("year").copy()
    out["year"] = out["year"].astype(int)
    return out.reset_index(drop=True)


def population(annual: pd.DataFrame) -> list[str]:
    out: list[str] = []
    pop = _by_year(annual, "avg_population")
    if pop.empty:
        return out
    year = int(pop.year.iloc[-1])
    text = tr(
        "Qatar's average population was {value} in {year}",
        value=millions(pop.avg_population.iloc[-1]),
        year=year,
    )
    growth = pop.population_growth_pct.iloc[-1]
    if pd.notna(growth):
        text += tr(", {change} on {year}", change=pct(growth), year=year - 1)
    out.append(text + ".")
    drops = pop[pop.population_growth_pct < 0]
    if len(drops) == 1:
        out.append(
            tr(
                "The only year-on-year fall in the series was {year} ({change}).",
                year=int(drops.year.iloc[0]),
                change=pct(drops.population_growth_pct.iloc[0]),
            )
        )
    return out


def labour(annual: pd.DataFrame, quarterly: pd.DataFrame) -> list[str]:
    out: list[str] = []
    female = _by_year(annual, "female_participation_rate_pct")
    if len(female) >= 2:
        first = female.female_participation_rate_pct.iloc[0]
        last = female.female_participation_rate_pct.iloc[-1]
        out.append(
            tr(
                "Female labour force participation went from {first} in {first_year} to {last} "
                "in {last_year} ({change} points).",
                first=pct(first, False),
                first_year=female.year.iloc[0],
                last=pct(last, False),
                last_year=female.year.iloc[-1],
                change=f"{last - first:+.1f}",
            )
        )
    unemployment = _by_year(annual, "unemployment_rate_pct")
    if not unemployment.empty:
        low = unemployment.unemployment_rate_pct.min()
        high = unemployment.unemployment_rate_pct.max()
        out.append(
            tr(
                "Unemployment stayed between {low}% and {high}% in every full year of the survey.",
                low=f"{low:.2f}",
                high=f"{high:.2f}",
            )
        )
    if not quarterly.empty:
        last_q = quarterly[quarterly.quarter_start == quarterly.quarter_start.max()]
        by_sex = last_q.set_index("sex")["population"]
        if {"male", "total"} <= set(by_sex.index):
            share = 100 * by_sex["male"] / by_sex["total"]
            out.append(
                tr(
                    "Men are {share}% of the population ({quarter}).",
                    share=f"{share:.0f}",
                    quarter=last_q.quarter_label.iloc[0],
                )
            )
    return out


def prices(inflation: pd.DataFrame) -> list[str]:
    out: list[str] = []
    group_name = localised("group_short_name_en", "group_name_ar")
    general = _by_year(inflation[inflation.is_general_index], "avg_inflation_pct")
    if not general.empty:
        peak = general.loc[general.avg_inflation_pct.idxmax()]
        latest_year = int(general.year.iloc[-1])
        text = tr(
            "Inflation peaked at {value} in {year}",
            value=pct(peak.avg_inflation_pct, False),
            year=int(peak.year),
        )
        if latest_year != int(peak.year):
            text += tr(
                " and was {value} in {year}",
                value=pct(general.avg_inflation_pct.iloc[-1], False),
                year=latest_year,
            )
        out.append(text + ".")
        groups = _by_year(
            inflation[(inflation.year == latest_year) & ~inflation.is_general_index],
            "avg_inflation_pct",
        )
        if len(groups) >= 2:
            top = groups.loc[groups.avg_inflation_pct.idxmax()]
            low = groups.loc[groups.avg_inflation_pct.idxmin()]
            out.append(
                tr(
                    "In {year} the fastest rise was {top} ({top_change}) and the biggest fall "
                    "was {low} ({low_change}).",
                    year=latest_year,
                    top=top[group_name],
                    top_change=pct(top.avg_inflation_pct),
                    low=low[group_name],
                    low_change=pct(low.avg_inflation_pct),
                )
            )
    levels = _by_year(inflation, "avg_index")
    if not levels.empty:
        newest = levels[levels.year == levels.year.max()]
        top = newest.loc[newest.avg_index.idxmax()]
        out.append(
            tr(
                "{group} has the highest index: {value} in {year} against 100 in 2018.",
                group=top[group_name],
                value=f"{top.avg_index:.0f}",
                year=int(top.year),
            )
        )
    return out


def travel(monthly: pd.DataFrame, annual: pd.DataFrame) -> list[str]:
    out: list[str] = []
    airport = _by_year(annual, "airport_passengers")
    if len(airport) >= 2:
        best = airport.loc[airport.airport_passengers.idxmax()]
        after = airport[airport.year > best.year]
        if not after.empty:
            worst = after.loc[after.airport_passengers.idxmin()]
            fall = 100 * (worst.airport_passengers / best.airport_passengers - 1)
            out.append(
                tr(
                    "Airport traffic fell from {high} passengers in {high_year} to {low} in "
                    "{low_year} ({change}).",
                    high=millions(best.airport_passengers, 1),
                    high_year=int(best.year),
                    low=millions(worst.airport_passengers, 1),
                    low_year=int(worst.year),
                    change=pct(fall),
                )
            )
            if airport.year.iloc[-1] > worst.year:
                share = 100 * airport.airport_passengers.iloc[-1] / best.airport_passengers
                out.append(
                    tr(
                        "By {year} it was back to {share}% of the {base_year} level.",
                        year=airport.year.iloc[-1],
                        share=f"{share:.0f}",
                        base_year=int(best.year),
                    )
                )
    months = monthly.dropna(subset=["airport_passengers"])
    if not months.empty:
        busiest = months.loc[months.airport_passengers.idxmax()]
        out.append(
            tr(
                "The busiest month in the data is {month} {year} with {value} passengers.",
                month=busiest[localised("month_name_en", "month_name_ar")],
                year=int(busiest.year),
                value=millions(busiest.airport_passengers),
            )
        )
    hotels = monthly.dropna(subset=["hotel_guests", "hotel_nights"])
    if not hotels.empty:
        counts = hotels.groupby("year").size()
        full_years = counts[counts == 12].index
        yearly = (
            hotels[hotels.year.isin(full_years)]
            .groupby("year")[["hotel_guests", "hotel_nights"]]
            .sum()
        )
        ratio = yearly.hotel_nights / yearly.hotel_guests
        plausible = ratio[ratio >= 1]
        if len(plausible) >= 2:
            out.append(
                tr(
                    "Hotel guests stayed longer: nights per guest rose from {first} in "
                    "{first_year} to {last} in {last_year}.",
                    first=f"{plausible.iloc[0]:.2f}",
                    first_year=int(plausible.index[0]),
                    last=f"{plausible.iloc[-1]:.2f}",
                    last_year=int(plausible.index[-1]),
                )
            )
        if (ratio < 1).any():
            years = ", ".join(str(int(y)) for y in ratio[ratio < 1].index)
            out.append(
                tr(
                    "The source reports fewer nights than guests for {years}, which cannot be "
                    "right; those months are flagged by a data test.",
                    years=years,
                )
            )
    return out


def utilities(national: pd.DataFrame, zones: pd.DataFrame) -> list[str]:
    out: list[str] = []
    full = _by_year(national[national.is_complete_year], "electricity_kwh")
    if len(full) >= 2:
        first, last = full.iloc[0], full.iloc[-1]
        growth = 100 * (last.electricity_kwh / first.electricity_kwh - 1)
        text = tr(
            "Electricity use {change} from {first_year} to {last_year} ({first} to {last} TWh)",
            change=change(growth),
            first_year=int(first.year),
            last_year=int(last.year),
            first=f"{first.electricity_gwh / 1000:,.1f}",
            last=f"{last.electricity_gwh / 1000:,.1f}",
        )
        if pd.notna(first.avg_population) and pd.notna(last.avg_population):
            pop_growth = 100 * (last.avg_population / first.avg_population - 1)
            text += tr(", while the population {change}", change=change(pop_growth))
        out.append(text + ".")
    if not full.empty and pd.notna(full.electricity_kwh_per_capita.iloc[-1]):
        last = full.iloc[-1]
        out.append(
            tr(
                "In {year} each resident used about {kwh} kWh of electricity and {litres} "
                "litres of water a day.",
                year=int(last.year),
                kwh=f"{last.electricity_kwh_per_capita:,.0f}",
                litres=f"{last.water_litres_per_capita_per_day:,.0f}",
            )
        )
    if not full.empty and not zones.empty:
        year = int(full.year.iloc[-1])
        z = zones[zones.year == year].sort_values("electricity_kwh", ascending=False)
        if len(z) > 10:
            share = z.head(10).electricity_share_pct.sum()
            out.append(
                tr(
                    "The ten largest of {count} zones used {share}% of the electricity in {year}.",
                    count=len(z),
                    share=f"{share:.0f}",
                    year=year,
                )
            )
        if not z.empty and "zone_label" in z:
            first = z.iloc[0]
            out.append(
                tr(
                    "The biggest user was {zone} with {share}% of the national total.",
                    zone=zone_label(first),
                    share=f"{first.electricity_share_pct:.1f}",
                )
            )
    partial = national[~national.is_complete_year]
    if not partial.empty:
        years = ", ".join(str(int(y)) for y in partial.year)
        out.append(
            tr(
                "{years} is a partial year on the portal, so it is left out of growth and "
                "per-person figures.",
                years=years,
            )
        )
    return out
