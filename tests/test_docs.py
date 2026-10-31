import pytest

from pipeline.config import PROJECT_ROOT, load_catalogue
from pipeline.docs import DocsError, lineage_mermaid, render_catalog
from pipeline.transform import discover


def test_lineage_has_an_edge_for_every_dependency(fixture_settings):
    models = discover(fixture_settings.models_dir)
    chart = lineage_mermaid(models)
    assert chart.startswith("flowchart LR")
    assert "raw_cpi_monthly --> staging_stg_cpi_monthly" in chart
    assert "seeds_months --> staging_stg_cpi_monthly" in chart
    assert "audit_source_manifest --> intermediate_int_utilities_zone_annual" in chart
    assert "marts_dim_month --> marts_fct_travel_monthly" in chart
    edges = sum(len(m.refs) + len(m.sources) + len(m.seeds) for m in models.values())
    assert chart.count("-->") == edges


def test_catalog_lists_sources_models_columns_and_tests(fixture_settings, warehouse):
    catalogue = load_catalogue(fixture_settings.sources_file)
    text = render_catalog(fixture_settings, catalogue)

    assert "## Sources" in text and "## Lineage" in text
    assert "https://www.data.gov.qa/explore/dataset/consumer-price-index" in text
    assert "### marts.fct_utilities_national_annual" in text
    assert "| `electricity_kwh_per_capita` | DOUBLE | Electricity kWh per resident" in text
    assert "`expression: no_per_capita_for_partial_years`" in text
    assert "| `cpi_index` | DOUBLE | Index value, base year 2018 = 100. | anomaly |" in text
    # one section per model
    assert text.count("\n### staging.") == 7
    assert text.count("\n### marts.") == 9


def test_catalog_needs_a_built_warehouse(settings):
    with pytest.raises(DocsError, match="run `python -m pipeline run` first"):
        render_catalog(settings, load_catalogue(PROJECT_ROOT / "config" / "sources.yml"))
