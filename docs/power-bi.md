# Loading the exports into Power BI

**This guide has not been tested in Power BI.** Power BI was not available when
it was written. The files were checked by reading them back with DuckDB and
Python, and the table and column names below are checked by a unit test, but
the steps and the DAX have never been run. If something does not work, please
open an issue. The [expected values](#check-your-model) let you check your own
model.

## 1. Create the files

```bash
python -m pipeline run            # or: python -m pipeline run --skip-extract
python -m pipeline export
```

`exports/` then holds one `.parquet` and one `.csv` file per mart. The folder is
not in git. Run the export again whenever the warehouse changes, then press
Refresh in Power BI. Close any export open in Excel or Power BI first, because
Windows does not let the export replace a file that is open.

## 2. Load the tables

Use the Parquet files if you can: they keep dates, whole numbers and true/false
columns, so there is nothing to convert.

In Power BI Desktop choose **Get data**, then **Parquet**, and enter the path of
a file. Or paste this into **Transform data > New Source > Blank Query >
Advanced Editor**, once per table:

```m
let
    Folder = "C:\path\to\qatar-open-data-pipeline\exports\",
    Source = Parquet.Document(File.Contents(Folder & "fct_cpi_monthly.parquet"))
in
    Source
```

For the CSV files, set the encoding so Arabic loads correctly. Parquet does not
need this.

```m
let
    Folder = "C:\path\to\qatar-open-data-pipeline\exports\",
    Source = Csv.Document(
        File.Contents(Folder & "fct_cpi_monthly.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
in
    Promoted
```

Load all nine tables and name each one after its file.

## 3. Add a year table

The annual tables do not all cover the same years. For example, 2026 is in the
utility tables but not in `mart_annual_indicators`, so relating them to each
other directly would lose it. Add a calculated table with **Modeling > New
table**:

```dax
dim_year =
DISTINCT (
    UNION (
        DISTINCT ( mart_annual_indicators[year] ),
        DISTINCT ( fct_inflation_annual[year] ),
        DISTINCT ( fct_utilities_national_annual[year] )
    )
)
```

## 4. Suggested relationships

Turn off auto-detected relationships and create these. All are one to many with
a single filter direction. Where both columns are unique, Power BI may offer one
to one; change it to one to many.

| One side | Many side | Notes |
| --- | --- | --- |
| `dim_month[month_start]` | `fct_cpi_monthly[month_start]` | |
| `dim_month[month_start]` | `fct_travel_monthly[month_start]` | |
| `dim_month[month_start]` | `fct_labour_market_quarterly[quarter_start]` | Quarters match their first month only, so slice this table by year or quarter, not by month. |
| `dim_zone[zone_number]` | `fct_utilities_zone_annual[zone_number]` | |
| `dim_year[year]` | `dim_month[year]` | One year slicer then filters the monthly tables too. |
| `dim_year[year]` | `fct_inflation_annual[year]` | |
| `dim_year[year]` | `fct_utilities_national_annual[year]` | |
| `dim_year[year]` | `fct_utilities_zone_annual[year]` | |
| `dim_year[year]` | `mart_annual_indicators[year]` | |

Use **Sort by column** so months appear in calendar order instead of A to Z: sort
`dim_month[month_name_en]` and `dim_month[month_name_ar]` by `dim_month[month]`.

## 5. Suggested measures

Add these with **Modeling > New measure**.

```dax
Airport passengers = SUM ( fct_travel_monthly[airport_passengers] )

Hotel guests = SUM ( fct_travel_monthly[hotel_guests] )

Hotel nights = SUM ( fct_travel_monthly[hotel_nights] )

Nights per guest = DIVIDE ( [Hotel nights], [Hotel guests] )

General CPI =
CALCULATE (
    AVERAGE ( fct_cpi_monthly[cpi_index] ),
    fct_cpi_monthly[is_general_index] = TRUE ()
)

Inflation % =
CALCULATE (
    AVERAGE ( fct_inflation_annual[avg_inflation_pct] ),
    fct_inflation_annual[is_general_index] = TRUE ()
)

Population =
CALCULATE (
    AVERAGE ( fct_labour_market_quarterly[population] ),
    fct_labour_market_quarterly[sex] = "total"
)

Female participation % =
VAR Active =
    CALCULATE (
        SUM ( fct_labour_market_quarterly[economically_active] ),
        fct_labour_market_quarterly[sex] = "female"
    )
VAR Adults =
    CALCULATE (
        SUM ( fct_labour_market_quarterly[population_15_plus] ),
        fct_labour_market_quarterly[sex] = "female"
    )
RETURN
    100 * DIVIDE ( Active, Adults )

Electricity GWh (complete years) =
CALCULATE (
    SUM ( fct_utilities_national_annual[electricity_gwh] ),
    fct_utilities_national_annual[is_complete_year] = TRUE ()
)
```

Three things in the data make simple sums wrong, and the measures above allow
for them:

- `fct_labour_market_quarterly` has a row each for male, female and total, so
  adding up every row counts people twice. Filter on `sex`.
- `fct_cpi_monthly` has one row per expenditure group, and index values should
  never be added. Filter on `is_general_index` or `group_code`.
- The latest utility year is a partial total. Filter on `is_complete_year`
  before comparing years.

Some source problems stay in the data, such as hotel nights below guests from
January 2019 to January 2020. The README lists them under
[Known issues](../README.md#known-issues-in-the-source-data).

## 6. Arabic labels

These columns hold Arabic text for slicers, axes and tables:

| Table | Column |
| --- | --- |
| `dim_month` | `month_name_ar` |
| `dim_zone` | `zone_name_ar`, `zone_short_name_ar` |
| `fct_cpi_monthly` | `group_name_ar` |
| `fct_inflation_annual` | `group_name_ar` |
| `fct_labour_market_quarterly` | `sex_ar` |
| `fct_utilities_zone_annual` | `zone_name_ar` |

## Check your model

With a year slicer set to the year shown, the measures should give these values.
They come from the warehouse built on 31 October 2026, using SQL queries that
do the same sums, and they will change when the portal publishes new data.

| Measure | Year | Expected |
| --- | --- | --- |
| Airport passengers | 2019 | 38,804,046 |
| Nights per guest | 2023 | 1.82 |
| General CPI | 2025 | 108.75 |
| Inflation % | 2025 | 0.50 |
| Population | 2025 | 3,267,039 |
| Female participation % | 2025 | 65.02 |
| Electricity GWh (complete years) | 2025 | 55,828 |
| Electricity GWh (complete years) | 2026 | blank (partial year) |

If you publish a report, credit the source: Qatar Open Data Portal, National
Planning Council and KAHRAMAA, under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
