# Contributing

Thanks for taking the time to help. Bug reports, data issues you spotted on the
portal, new datasets and dashboard ideas are all welcome.

## Set up

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS / Linux: source .venv/bin/activate
python tasks.py setup
python -m pipeline run            # builds data/warehouse.duckdb
python tasks.py test              # unit tests, no network needed
python tasks.py lint              # ruff check and format check
```

Before opening a pull request, please make sure `python tasks.py test`,
`python tasks.py lint` and `python -m pipeline run` all pass, and run
`python tasks.py docs` if you changed a model or `models/schema.yml`.

## Adding a new dataset

The example below adds a made-up monthly dataset with the key `vehicles`.
Replace the names with your own.

### 1. Find the dataset and look at it

Search [data.gov.qa](https://www.data.gov.qa) and copy the dataset id from the
URL (`/explore/dataset/<dataset-id>/`). Check the metadata and a few rows:

```bash
curl "https://www.data.gov.qa/api/explore/v2.1/catalog/datasets/<dataset-id>"
curl "https://www.data.gov.qa/api/explore/v2.1/catalog/datasets/<dataset-id>/records?limit=5"
```

Note the licence, the update frequency, the period it covers, and how the
period columns are written. Please keep requests to a minimum.

### 2. Register it

Add an entry to [`config/sources.yml`](config/sources.yml):

```yaml
  - key: vehicles
    dataset_id: <dataset-id>
    title: New vehicle registrations by month
    publisher: National Planning Council
    description: >
      One or two sentences on what the data is and the period it covers.
    expected_columns: [year, month, type, total]
    min_rows: 100
```

`key` becomes the raw table name (`raw.vehicles`), so keep it lower snake case.
`expected_columns` is the contract: if the portal drops or renames one of these
columns the extract stops instead of loading a broken file.

### 3. Download it

```bash
python -m pipeline extract --only vehicles
```

Look at `data/raw/vehicles.csv` and `data/raw/vehicles.meta.json`. The meta file
has the portal's English and Arabic label for each column, which helps with
transliterated names such as `lmw_shr`.

### 4. Write the staging model

Create `models/staging/stg_vehicles.sql`. Start with a short comment that says
what one row is; the docs generator uses it as the description.

```sql
-- Monthly new vehicle registrations by vehicle type. One row per month and type.

with source as (
    select * from {{ source('vehicles') }}
),

months as (
    select cast(month_number as integer) as month, lower(month_abbr) as month_abbr
    from {{ seed('months') }}
)

select
    make_date(try_cast(trim(source.year) as integer), months.month, 1) as month_start,
    lower(trim(source.type)) as vehicle_type,
    try_cast(trim(source.total) as bigint) as registrations
from source
left join months on lower(left(trim(source.month), 3)) = months.month_abbr
```

Staging rules: cast every column with `try_cast` (raw tables are all text),
turn free-text labels into stable codes, keep Arabic labels when the source
has them, and do not filter or aggregate yet.

### 5. Add data tests

Describe the model in [`models/schema.yml`](models/schema.yml). At minimum: a
unique key, `not_null` on the key columns, accepted values for codes, a range
for numbers and a row count.

```yaml
  - name: stg_vehicles
    tests:
      - unique: [month_start, vehicle_type]
      - row_count: {min: 100}
    columns:
      - name: month_start
        tests: [not_null]
      - name: registrations
        tests: [not_null, {range: {min: 0}}]
```

Use `severity: warn` for known problems in the source that should stay
visible without stopping the pipeline, and leave a comment explaining why.

For a monthly series, add `anomaly` to the tests of its value column to get a
warning about sudden month-on-month jumps. Add `by: <column>` if one table holds
several series. The limits are in [`config/quality.yml`](config/quality.yml);
add an entry there if the defaults do not suit the series.

### 6. Model it for analysis

Add intermediate models for reshaping or calculations and a mart (or extend
an existing one) for the dashboard. Join monthly data to `dim_month` and zone
data to `dim_zone`. A model can only use models from its own layer or an
earlier one; the runner stops with an error otherwise.

### 7. Add test fixtures and unit tests

Add a filter for the new key to `KEEP` in
[`scripts/make_fixtures.py`](scripts/make_fixtures.py), then run
`python scripts/make_fixtures.py` to write a small excerpt of the real file to
`tests/fixtures/raw/`. Keep it to a few dozen rows. Then add tests:

- `tests/test_staging.py`: parsing problems specific to this file
- `tests/test_marts.py`: values recomputed in Python from the fixture

Fixtures are cut down on purpose, so volume checks such as `row_count` fail on
them. `tests/test_quality.py::test_fixture_data_only_fails_volume_checks` lists
the checks expected to fail; add the new `row_count` check there.

### 8. Run everything

```bash
python -m pipeline run
python tasks.py test
python tasks.py lint
python tasks.py docs
```

### 9. Show it (optional)

Add a page in `dashboard/views/`, register it in `dashboard/app.py`, and put any
written findings in `dashboard/insights.py` so they are computed from the data
and covered by `tests/test_dashboard.py`. Charts use the helpers in
`dashboard/charts.py`: at most three series per chart, one y axis, and a table
view under every chart.

## Style

- Python is formatted and linted with ruff (`python tasks.py format`).
- SQL: lower case keywords, one CTE per step, trailing commas avoided, and a
  comment at the top of every model.
- Commit messages: short and in the imperative ("Add vehicle registrations").
