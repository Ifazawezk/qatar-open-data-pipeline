"""Render docs/images/banner.png for the README.

Builds a small HTML page with the project name, a one-line pitch, counts read
from the warehouse and a real chart (monthly airport passengers), then takes
a screenshot of it with a headless browser. Run after `python -m pipeline run`:

    python scripts/make_banner.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402
import pandas as pd  # noqa: E402

from dashboard import charts  # noqa: E402
from pipeline.config import Settings  # noqa: E402
from scripts.screenshots import launch_browser  # noqa: E402

OUT = ROOT / "docs" / "images" / "banner.png"
WIDTH, HEIGHT = 1280, 420

PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<style>
  body {{ margin: 0; background: #f9f9f7; font-family: {font}; color: #0b0b0b; }}
  .wrap {{ display: flex; height: {height}px; box-sizing: border-box;
           border-left: 10px solid #8a1538; }}
  .text {{ width: 470px; padding: 52px 24px 40px 44px; box-sizing: border-box; }}
  h1 {{ font-size: 40px; line-height: 1.1; margin: 0 0 18px; letter-spacing: -0.5px; }}
  p {{ font-size: 18px; line-height: 1.45; color: #52514e; margin: 0 0 26px; }}
  .chips span {{ display: inline-block; font-size: 14px; color: #0b0b0b;
                 border: 1px solid #c3c2b7; border-radius: 14px; padding: 5px 12px;
                 margin: 0 6px 8px 0; background: #fcfcfb; }}
  .chart {{ flex: 1; padding: 22px 28px 16px 0; }}
  .note {{ font-size: 12px; color: #898781; margin: 4px 0 0 8px; }}
</style></head>
<body><div class="wrap">
  <div class="text">
    <h1>Qatar Open Data Pipeline</h1>
    <p>Public statistics from data.gov.qa, turned into a tested DuckDB warehouse
       and a Streamlit dashboard.</p>
    <div class="chips">{chips}</div>
  </div>
  <div class="chart">{chart}
    <div class="note">Source: Qatar Open Data Portal (CC BY 4.0). Arrivals plus departures.</div>
  </div>
</div></body></html>
"""


def main() -> int:
    from playwright.sync_api import sync_playwright

    path = Settings.from_env().warehouse_path
    con = duckdb.connect(str(path), read_only=True)
    try:
        travel = con.execute(
            "select month_start, airport_passengers from marts.fct_travel_monthly "
            "where airport_passengers is not null order by month_start"
        ).df()
        datasets = con.execute("select count(*) from audit.source_manifest").fetchone()[0]
        models = con.execute(
            "select count(*) from information_schema.tables "
            "where table_schema in ('staging', 'intermediate', 'marts')"
        ).fetchone()[0]
        tests = con.execute(
            "select count(*) from audit.check_results where run_id = "
            "(select arg_max(run_id, checked_at) from audit.check_results)"
        ).fetchone()[0]
    finally:
        con.close()

    fig = charts.lines(
        travel,
        "month_start",
        {"Passengers": "airport_passengers"},
        "Monthly passengers at Hamad International Airport",
        y_format="~s",
    )
    charts.mark_month(fig, pd.Timestamp("2022-11-01"), "World Cup")
    fig.update_layout(height=HEIGHT - 60, margin={"l": 8, "r": 16, "t": 48, "b": 8})
    chart = fig.to_html(
        full_html=False,
        include_plotlyjs=True,
        config={"staticPlot": True, "displayModeBar": False},
    )
    chips = "".join(
        f"<span>{text}</span>"
        for text in (
            f"{datasets} datasets",
            f"{models} SQL models",
            f"{tests} data tests",
            "English and Arabic labels",
        )
    )
    html = PAGE.format(font=charts.FONT, height=HEIGHT, chips=chips, chart=chart)

    with tempfile.TemporaryDirectory() as tmp:
        page_path = Path(tmp) / "banner.html"
        page_path.write_text(html, encoding="utf-8")
        with sync_playwright() as p:
            browser = launch_browser(p)
            page = browser.new_page(
                viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=2
            )
            page.goto(page_path.as_uri())
            page.wait_for_selector(".main-svg")
            page.wait_for_timeout(500)
            OUT.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(OUT))
            browser.close()
    print(f"saved {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
