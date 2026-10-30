"""Short written findings computed from the marts.

Every sentence is built from the data at render time, so the text stays
right when the portal publishes new figures. A function returns fewer
sentences (or none) when the data it needs is missing.
"""

from __future__ import annotations

import pandas as pd


def pct(value: float, signed: bool = True) -> str:
    return f"{value:+.1f}%" if signed else f"{value:.1f}%"


def change(value: float) -> str:
    """'grew 4.2%' or 'fell 4.2%'."""
    return f"{'grew' if value >= 0 else 'fell'} {abs(value):.1f}%"


def millions(value: float, digits: int = 2) -> str:
    return f"{value / 1e6:,.{digits}f} million"


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
    text = f"Qatar's average population was {millions(pop.avg_population.iloc[-1])} in {year}"
    growth = pop.population_growth_pct.iloc[-1]
    if pd.notna(growth):
        text += f", {pct(growth)} on {year - 1}"
    out.append(text + ".")
    drops = pop[pop.population_growth_pct < 0]
    if len(drops) == 1:
        out.append(
            f"The only year-on-year fall in the series was {int(drops.year.iloc[0])} "
            f"({pct(drops.population_growth_pct.iloc[0])})."
        )
    return out


def labour(annual: pd.DataFrame, quarterly: pd.DataFrame) -> list[str]:
    out: list[str] = []
    female = _by_year(annual, "female_participation_rate_pct")
    if len(female) >= 2:
        first = female.female_participation_rate_pct.iloc[0]
        last = female.female_participation_rate_pct.iloc[-1]
        out.append(
            f"Female labour force participation went from {pct(first, False)} in "
            f"{female.year.iloc[0]} to {pct(last, False)} in {female.year.iloc[-1]} "
            f"({last - first:+.1f} points)."
        )
    unemployment = _by_year(annual, "unemployment_rate_pct")
    if not unemployment.empty:
        low = unemployment.unemployment_rate_pct.min()
        high = unemployment.unemployment_rate_pct.max()
        out.append(
            f"Unemployment stayed between {low:.2f}% and {high:.2f}% in every full year "
            "of the survey."
        )
    if not quarterly.empty:
        last_q = quarterly[quarterly.quarter_start == quarterly.quarter_start.max()]
        by_sex = last_q.set_index("sex")["population"]
        if {"male", "total"} <= set(by_sex.index):
            share = 100 * by_sex["male"] / by_sex["total"]
            out.append(f"Men are {share:.0f}% of the population ({last_q.quarter_label.iloc[0]}).")
    return out


def prices(inflation: pd.DataFrame) -> list[str]:
    out: list[str] = []
    general = _by_year(inflation[inflation.is_general_index], "avg_inflation_pct")
    if not general.empty:
        peak = general.loc[general.avg_inflation_pct.idxmax()]
        latest_year = int(general.year.iloc[-1])
        text = f"Inflation peaked at {pct(peak.avg_inflation_pct, False)} in {int(peak.year)}"
        if latest_year != int(peak.year):
            text += f" and was {pct(general.avg_inflation_pct.iloc[-1], False)} in {latest_year}"
        out.append(text + ".")
        groups = _by_year(
            inflation[(inflation.year == latest_year) & ~inflation.is_general_index],
            "avg_inflation_pct",
        )
        if len(groups) >= 2:
            top = groups.loc[groups.avg_inflation_pct.idxmax()]
            low = groups.loc[groups.avg_inflation_pct.idxmin()]
            out.append(
                f"In {latest_year} the fastest rise was {top.group_short_name_en} "
                f"({pct(top.avg_inflation_pct)}) and the biggest fall was "
                f"{low.group_short_name_en} ({pct(low.avg_inflation_pct)})."
            )
    levels = _by_year(inflation, "avg_index")
    if not levels.empty:
        newest = levels[levels.year == levels.year.max()]
        top = newest.loc[newest.avg_index.idxmax()]
        out.append(
            f"{top.group_short_name_en} has the highest index: {top.avg_index:.0f} in "
            f"{int(top.year)} against 100 in 2018."
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
                f"Airport traffic fell from {millions(best.airport_passengers, 1)} passengers "
                f"in {int(best.year)} to {millions(worst.airport_passengers, 1)} in "
                f"{int(worst.year)} ({pct(fall)})."
            )
            if airport.year.iloc[-1] > worst.year:
                share = 100 * airport.airport_passengers.iloc[-1] / best.airport_passengers
                out.append(
                    f"By {airport.year.iloc[-1]} it was back to {share:.0f}% of the "
                    f"{int(best.year)} level."
                )
    months = monthly.dropna(subset=["airport_passengers"])
    if not months.empty:
        busiest = months.loc[months.airport_passengers.idxmax()]
        out.append(
            f"The busiest month in the data is {busiest.month_name_en} {int(busiest.year)} "
            f"with {millions(busiest.airport_passengers)} passengers."
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
                f"Hotel guests stayed longer: nights per guest rose from "
                f"{plausible.iloc[0]:.2f} in {int(plausible.index[0])} to "
                f"{plausible.iloc[-1]:.2f} in {int(plausible.index[-1])}."
            )
        if (ratio < 1).any():
            years = ", ".join(str(int(y)) for y in ratio[ratio < 1].index)
            out.append(
                f"The source reports fewer nights than guests for {years}, which cannot be "
                "right; those months are flagged by a data test."
            )
    return out


def utilities(national: pd.DataFrame, zones: pd.DataFrame) -> list[str]:
    out: list[str] = []
    full = _by_year(national[national.is_complete_year], "electricity_kwh")
    if len(full) >= 2:
        first, last = full.iloc[0], full.iloc[-1]
        growth = 100 * (last.electricity_kwh / first.electricity_kwh - 1)
        text = (
            f"Electricity use {change(growth)} from {int(first.year)} to {int(last.year)} "
            f"({first.electricity_gwh / 1000:,.1f} to {last.electricity_gwh / 1000:,.1f} TWh)"
        )
        if pd.notna(first.avg_population) and pd.notna(last.avg_population):
            pop_growth = 100 * (last.avg_population / first.avg_population - 1)
            text += f", while the population {change(pop_growth)}"
        out.append(text + ".")
    if not full.empty and pd.notna(full.electricity_kwh_per_capita.iloc[-1]):
        last = full.iloc[-1]
        out.append(
            f"In {int(last.year)} each resident used about "
            f"{last.electricity_kwh_per_capita:,.0f} kWh of electricity and "
            f"{last.water_litres_per_capita_per_day:,.0f} litres of water a day."
        )
    if not full.empty and not zones.empty:
        year = int(full.year.iloc[-1])
        z = zones[zones.year == year].sort_values("electricity_kwh", ascending=False)
        if len(z) > 10:
            share = z.head(10).electricity_share_pct.sum()
            out.append(
                f"The ten largest of {len(z)} zones used {share:.0f}% of the electricity in {year}."
            )
        if not z.empty and "zone_label" in z:
            first = z.iloc[0]
            out.append(
                f"The biggest user was {first.zone_label} with "
                f"{first.electricity_share_pct:.1f}% of the national total."
            )
    partial = national[~national.is_complete_year]
    if not partial.empty:
        years = ", ".join(str(int(y)) for y in partial.year)
        out.append(
            f"{years} is a partial year on the portal, so it is left out of growth and "
            "per-person figures."
        )
    return out
