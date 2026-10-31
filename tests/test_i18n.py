"""Arabic mode: translations, labels from the marts, right-to-left layout, the switch."""

import ast
import json
import re
import string
import threading
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from dashboard import charts, i18n, insights, ui
from dashboard.i18n import AR, tr

DASHBOARD = Path(__file__).resolve().parent.parent / "dashboard"
APP = str(DASHBOARD / "app.py")
ARABIC = re.compile(r"[؀-ۿ]")
PAGES = [
    "views/population.py",
    "views/prices.py",
    "views/travel.py",
    "views/utilities.py",
    "views/pipeline_health.py",
]


@pytest.fixture
def arabic():
    i18n.set_language("ar")
    yield
    i18n.set_language("en")


def literal(node):
    """The value of a string literal, including adjacent strings Python has joined."""
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def strings_passed_to_tr():
    found = {}
    for path in DASHBOARD.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "tr":
                value = literal(node.args[0])
                assert value is not None, f"{path.name}:{node.lineno} tr() needs a plain string"
                found[value] = f"{path.name}:{node.lineno}"
    return found


def placeholders(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_every_string_in_the_dashboard_has_an_arabic_translation():
    used = strings_passed_to_tr()
    assert len(used) > 100
    assert {text: where for text, where in used.items() if text not in AR} == {}


def test_no_translation_is_left_over():
    assert set(AR) - set(strings_passed_to_tr()) == set()


@pytest.mark.parametrize("english", sorted(AR))
def test_translation_is_arabic_and_keeps_the_placeholders(english):
    assert ARABIC.search(AR[english])
    assert placeholders(english) == placeholders(AR[english])


def test_tr_is_plain_english_by_default():
    assert tr("Prices") == "Prices"
    assert tr("{value} million", value="3.27") == "3.27 million"
    assert tr("Not in the table") == "Not in the table"


def test_tr_uses_arabic_when_it_is_on(arabic):
    assert tr("Prices") == "الأسعار"
    assert tr("{value} million", value="3.27") == "3.27 مليون"
    assert tr("Not in the table") == "Not in the table"


def test_language_is_separate_for_each_session_thread():
    seen = []

    def session():
        i18n.set_language("ar")
        seen.append(i18n.is_arabic())

    thread = threading.Thread(target=session)
    thread.start()
    thread.join()
    assert seen == [True]
    assert not i18n.is_arabic()


def zone(label, name_ar, number=70):
    return pd.Series({"zone_label": label, "zone_name_ar": name_ar, "zone_number": number})


def test_zone_label_is_unchanged_in_english():
    assert i18n.zone_label(zone("Zone 70: Leabaib and others", "لعبيب / العب")) == (
        "Zone 70: Leabaib and others"
    )


@pytest.mark.parametrize(
    "name_ar, expected",
    [
        ("لعبيب / العب / الخيسة", "المنطقة 70: لعبيب وغيرها"),
        ("الجسرة", "المنطقة 70: الجسرة"),
        ("الذخيرة/راس لفان/ام بركة", "المنطقة 70: الذخيرة/راس لفان/ام بركة"),
    ],
)
def test_zone_label_is_built_from_the_arabic_name(arabic, name_ar, expected):
    assert i18n.zone_label(zone("Zone 70: x", name_ar)) == expected


@pytest.mark.parametrize("missing", [None, float("nan"), pd.NA])
def test_zone_without_an_arabic_name_keeps_the_english_label(arabic, missing):
    assert i18n.zone_label(zone("Zone 99: unnamed", missing, 99)) == "Zone 99: unnamed"


def test_findings_use_arabic_sentences_and_labels_from_the_marts(arabic):
    monthly = pd.DataFrame(
        {
            "year": [2023],
            "month_name_en": ["February"],
            "month_name_ar": ["فبراير"],
            "airport_passengers": [3.1e6],
            "hotel_guests": [None],
            "hotel_nights": [None],
        }
    )
    annual = pd.DataFrame({"year": [2023], "airport_passengers": [30e6]})
    assert insights.travel(monthly, annual) == [
        "أكثر الأشهر ازدحاما في البيانات هو فبراير 2023 بعدد 3.10 مليون مسافر."
    ]


def test_price_findings_name_groups_in_arabic(arabic):
    inflation = pd.DataFrame(
        {
            "year": [2025, 2025, 2025],
            "is_general_index": [True, False, False],
            "group_short_name_en": ["General index", "Food", "Tobacco"],
            "group_name_ar": ["الرقم القياسي العام", "الغذاء والمشروبات", "التبغ"],
            "avg_inflation_pct": [1.0, 4.0, -2.0],
            "avg_index": [110.0, 120.0, 246.0],
        }
    )
    text = " ".join(insights.prices(inflation))
    assert "الغذاء والمشروبات" in text and "التبغ" in text
    assert "Food" not in text and "Tobacco" not in text


def test_utility_sentences_keep_their_order_of_words(arabic):
    assert insights.change(33.6) == "ارتفع بنسبة 33.6%"
    assert insights.change(-4.6) == "انخفض بنسبة 4.6%"


def test_tables_translate_headers_and_read_from_the_right(arabic):
    out = ui.tidy(pd.DataFrame({"year": [2024], "cpi_index": [108.123]}))
    assert list(out.columns) == ["الرقم القياسي", "السنة"]
    assert out.iloc[0, 0] == 108.12


def line_chart(x):
    df = pd.DataFrame({"x": x, "a": [1, 2], "b": [2, 3]})
    return charts.lines(df, "x", {"A": "a", "B": "b"}, "title")


def test_english_charts_stay_left_to_right():
    fig = line_chart(pd.to_datetime(["2024-01-01", "2024-02-01"]))
    assert (fig.layout.title.x, fig.layout.title.xanchor) == (0, "left")
    assert fig.layout.legend.xanchor is None or fig.layout.legend.x == 0
    assert fig.layout.xaxis.tickformat is None
    assert fig.layout.margin.r == 72


def test_arabic_charts_put_titles_and_legends_on_the_right(arabic):
    fig = line_chart([2024, 2025])
    assert (fig.layout.title.x, fig.layout.title.xanchor) == (1, "right")
    assert (fig.layout.legend.x, fig.layout.legend.xanchor) == (1, "right")


def test_arabic_dates_use_digits_so_no_english_month_names_appear(arabic):
    fig = line_chart(pd.to_datetime(["2024-01-01", "2024-02-01"]))
    assert fig.layout.xaxis.tickformat == "%Y"
    assert fig.layout.xaxis.hoverformat == "%Y-%m"


def test_numeric_axes_are_left_alone(arabic):
    assert line_chart([2024, 2025]).layout.xaxis.tickformat is None


def test_arabic_ranked_bars_grow_from_the_right(arabic):
    df = pd.DataFrame({"label": ["a", "b"], "value": [1, 2]})
    fig = charts.hbars(df, "label", "value", "title")
    assert fig.layout.xaxis.autorange == "reversed"
    assert fig.layout.yaxis.side == "right"


def test_english_ranked_bars_are_unchanged():
    fig = charts.hbars(pd.DataFrame({"label": ["a"], "value": [1]}), "label", "value", "title")
    assert fig.layout.xaxis.autorange is None
    assert fig.layout.yaxis.side is None


def test_arabic_bars_avoid_latin_si_suffixes(arabic):
    df = pd.DataFrame({"year": ["2021"], "value": [5e7]})
    assert charts.bars(df, "year", "value", "title", y_format="~s").layout.yaxis.tickformat == ","


def test_rtl_css_keeps_the_fixes_found_in_a_browser():
    """AppTest cannot see CSS, so these came from checking real pages in Edge."""
    for rule in (
        '[data-testid="stSelectboxVirtualDropdown"]',  # dropdowns live outside .stApp
        "text-align: start !important",  # Streamlit sets text-align: left on every element
        '[data-collapsed="true"] { display: none; }',  # or it covers the page on phones
    ):
        assert rule in ui.RTL_CSS


@pytest.fixture
def app(fixture_settings, warehouse, monkeypatch):
    monkeypatch.setenv("QODP_WAREHOUSE", str(fixture_settings.warehouse_path))
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    return at


def in_arabic(at):
    at.sidebar.radio[0].set_value("ar").run()
    return at


def has_rtl_css(at):
    return any("direction: rtl" in str(element.proto) for element in at.get("html"))


def texts(at):
    """Everything the page wrote itself, leaving out the Streamlit widgets."""
    found = [e.value for e in [*at.title, *at.subheader, *at.caption, *at.info]]
    found += [m.label for m in at.metric]
    found += [e.label for e in at.expander]
    return found


def figures(at):
    return [json.loads(element.proto.spec) for element in at.get("plotly_chart")]


def test_dashboard_starts_in_english_without_any_rtl_css(app):
    assert app.sidebar.radio[0].value == "en"
    assert app.title[0].value == "Qatar in numbers"
    assert not has_rtl_css(app)
    assert "lang" not in app.query_params


def test_the_switch_changes_language_and_direction(app):
    in_arabic(app)
    assert not app.exception
    assert app.title[0].value == "قطر بالأرقام"
    assert has_rtl_css(app)
    assert app.query_params["lang"] == "ar"


def test_the_switch_goes_back_to_english(app):
    in_arabic(app)
    app.sidebar.radio[0].set_value("en").run()
    assert app.title[0].value == "Qatar in numbers"
    assert not has_rtl_css(app)
    assert "lang" not in app.query_params


def test_language_survives_changing_page(app):
    in_arabic(app)
    app.switch_page("views/prices.py").run()
    assert app.title[0].value == "الأسعار"
    assert has_rtl_css(app)


def test_url_can_open_the_dashboard_in_arabic(fixture_settings, warehouse, monkeypatch):
    monkeypatch.setenv("QODP_WAREHOUSE", str(fixture_settings.warehouse_path))
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params["lang"] = "ar"
    at.run()
    assert at.title[0].value == "قطر بالأرقام"
    assert at.sidebar.radio[0].value == "ar"


def test_unknown_language_in_the_url_means_english(fixture_settings, warehouse, monkeypatch):
    monkeypatch.setenv("QODP_WAREHOUSE", str(fixture_settings.warehouse_path))
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params["lang"] = "fr"
    at.run()
    assert not at.exception
    assert at.title[0].value == "Qatar in numbers"


def test_missing_warehouse_message_is_translated(tmp_path, monkeypatch):
    monkeypatch.setenv("QODP_WAREHOUSE", str(tmp_path / "nothing.duckdb"))
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params["lang"] = "ar"
    at.run()
    assert ARABIC.search(at.error[0].value)
    assert "python -m pipeline run" in at.error[0].value


def test_overview_is_written_in_arabic(app):
    in_arabic(app)
    missing = [text for text in texts(app) if not ARABIC.search(text)]
    assert missing == []
    assert "السكان (2025)" in [m.label for m in app.metric]


@pytest.mark.parametrize("page", PAGES)
def test_every_page_is_written_in_arabic(app, page):
    in_arabic(app)
    app.switch_page(page).run()
    assert not app.exception, [e.message for e in app.exception]
    assert [text for text in texts(app) if not ARABIC.search(text)] == []


@pytest.mark.parametrize("page", PAGES[:-1])
def test_every_chart_title_is_in_arabic(app, page):
    in_arabic(app)
    app.switch_page(page).run()
    titles = [fig["layout"]["title"]["text"] for fig in figures(app)]
    assert titles
    assert [title for title in titles if not ARABIC.search(title)] == []


@pytest.mark.parametrize("page", PAGES[:-1])
def test_data_tables_have_arabic_headers(app, page):
    in_arabic(app)
    app.switch_page(page).run()
    raw = [
        column
        for frame in app.dataframe
        for column in frame.value.columns
        if re.fullmatch(r"[a-z][a-z0-9_]*", str(column))
    ]
    assert raw == []


def test_population_chart_uses_the_sex_labels_from_the_mart(app):
    in_arabic(app)
    app.switch_page("views/population.py").run()
    names = {trace.get("name") for fig in figures(app) for trace in fig["data"]}
    assert {"ذكور", "إناث", "الإجمالي"} <= names


def test_changing_a_control_works_in_arabic(app):
    in_arabic(app)
    app.switch_page("views/prices.py").run()
    app.selectbox[0].select("002").run()
    assert not app.exception
    assert any("التبغ" in fig["layout"]["title"]["text"] for fig in figures(app))
