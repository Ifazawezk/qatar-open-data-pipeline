# Qatar Open Data Pipeline

A batch data pipeline that pulls public statistics from the
[Qatar Open Data Portal](https://www.data.gov.qa) and builds a small analytical
warehouse in DuckDB.

Work in progress. The plan:

1. Extract a handful of related datasets (population and labour force, prices,
   air passengers, hotels, electricity and water) with retries and caching.
2. Load them into DuckDB and model them in layers (staging, intermediate, marts).
3. Test the data on every run.
4. Put a Streamlit dashboard on top of the marts.

## Getting started

```bash
python -m pip install -r requirements-dev.txt
python -m pipeline sources
python tasks.py test
```

## Licence

Code: MIT, see [LICENSE](LICENSE). Data: Qatar Open Data Portal, CC BY 4.0.
