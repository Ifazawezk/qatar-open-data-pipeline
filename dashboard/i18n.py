"""English and Arabic text for the dashboard.

English is written directly in the code and tr() looks it up in AR when the
dashboard is in Arabic, so English output does not depend on this table.

Labels that belong to the data (months, expenditure groups, zones, sex) are not
translated here. The marts already carry them in Arabic and localised() picks
the right column.

The language lives in a ContextVar because Streamlit runs each session's script
in its own thread, and insights.py stays free of Streamlit this way.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

import pandas as pd

LANGUAGES = {"en": "English", "ar": "العربية"}

_language: ContextVar[str] = ContextVar("language", default="en")


def set_language(code: str) -> None:
    _language.set(code)


def is_arabic() -> bool:
    return _language.get() == "ar"


def tr(text: str, **values: object) -> str:
    """`text` in the current language, with its {placeholders} filled in."""
    template = AR.get(text, text) if is_arabic() else text
    return template.format(**values)


def localised(english: str, arabic: str) -> str:
    """The name of the column to show: English, or its Arabic twin in Arabic mode."""
    return arabic if is_arabic() else english


def zone_label(row: Any) -> str:
    """A short zone name: the mart's zone_label, or the same thing from zone_name_ar."""
    if not is_arabic() or pd.isna(row.zone_name_ar):
        return row.zone_label
    first, _, others = row.zone_name_ar.partition(" / ")
    label = tr("Zone {number}: {name}", number=row.zone_number, name=first)
    return label + tr(" and others") if others else label


# Column headers in the "Show the numbers" tables. English mode shows the raw names.
COLUMNS = {
    "airport_arrivals": "القادمون",
    "airport_departures": "المغادرون",
    "airport_passengers": "المسافرون",
    "airport_passengers_yoy_pct": "التغير السنوي للمسافرين %",
    "avg_population": "متوسط عدد السكان",
    "cpi_index": "الرقم القياسي",
    "electricity_gwh": "الكهرباء (جيجاواط ساعة)",
    "electricity_kwh_per_capita": "الكهرباء للفرد (كيلوواط ساعة)",
    "electricity_rank": "الترتيب في الكهرباء",
    "electricity_share_pct": "الحصة من الكهرباء %",
    "electricity_yoy_pct": "التغير السنوي للكهرباء %",
    "female": "إناث",
    "hotel_guests": "نزلاء الفنادق",
    "hotel_nights": "ليالي الإقامة",
    "is_complete_year": "سنة كاملة",
    "male": "ذكور",
    "mom_change_pct": "التغير الشهري %",
    "month_start": "الشهر",
    "nights_per_guest": "الليالي لكل نزيل",
    "population_growth_pct": "نمو السكان %",
    "quarter_label": "الربع",
    "total": "الإجمالي",
    "unemployed": "المتعطلون",
    "unemployment_rate_pct": "معدل البطالة %",
    "water_litres_per_capita_per_day": "المياه للفرد يوميا (لتر)",
    "water_m3": "المياه (م³)",
    "water_million_m3": "المياه (مليون م³)",
    "water_share_pct": "الحصة من المياه %",
    "water_yoy_pct": "التغير السنوي للمياه %",
    "year": "السنة",
    "yoy_change_pct": "التغير السنوي %",
    "zone_label": "المنطقة",
    "zone_name_ar": "الاسم الكامل للمنطقة",
}

AR = {
    # Navigation and shared text
    "Qatar Open Data": "بيانات قطر المفتوحة",
    "Overview": "نظرة عامة",
    "Population and jobs": "السكان والوظائف",
    "Prices": "الأسعار",
    "Travel and hotels": "السفر والفنادق",
    "Electricity and water": "الكهرباء والمياه",
    "Pipeline health": "حالة خط البيانات",
    "Data from the [Qatar Open Data Portal](https://www.data.gov.qa) (CC BY 4.0), "
    "refreshed with `python -m pipeline run`.": "البيانات من [بوابة قطر للبيانات المفتوحة]"
    "(https://www.data.gov.qa) (CC BY 4.0)، ويتم تحديثها بالأمر `python -m pipeline run`.",
    "No warehouse found at `{path}`. Build it first with `python -m pipeline run`.": "لم يتم العثور"
    " على مستودع البيانات في `{path}`. أنشئه أولا بالأمر `python -m pipeline run`.",
    "Show the numbers": "عرض الأرقام",
    "Not enough data in the warehouse for written findings yet.": "لا توجد بيانات كافية بعد"
    " لكتابة النتائج.",
    "What the data says": "ما تقوله البيانات",
    "Source: Qatar Open Data Portal, {links}. Licence CC BY 4.0.": "المصدر: بوابة قطر للبيانات"
    " المفتوحة، {links}. الترخيص CC BY 4.0.",
    "{value} million": "{value} مليون",
    "{value}M": "{value} مليون",
    "{value} pts": "{value} نقطة",
    "{change} on {year}": "{change} عن {year}",
    "grew {value}%": "ارتفع بنسبة {value}%",
    "fell {value}%": "انخفض بنسبة {value}%",
    "Zone {number}: {name}": "المنطقة {number}: {name}",
    " and others": " وغيرها",
    # Dataset titles, as the portal publishes them in Arabic
    "Population and Labor Force by Sex": "السكان والقوى العاملة حسب الجنس",
    "Consumer Price Index by Expenditure Group, monthly": "الرقم القياسي لأسعار المستهلك حسب"
    " مجموعة الإنفاق - شهري",
    "Arrivals and departures via Hamad International Airport by month": "حركة القدوم والمغادرة"
    " عبر مطار حمد الدولي حسب الشهر والسنة",
    "Number of hotel guests and nights of stay by month": "عدد النزلاء وليالي الإقامة في الفنادق"
    " حسب الشهر",
    "Electricity total consumption by zone number": "إجمالي استهلاك الكهرباء حسب رقم المنطقة",
    "Water total consumption by zone number": "إجمالي استهلاك المياه حسب رقم المنطقة",
    "Population, area and population density by zone": "عدد السكان والمساحة والكثافة السكانية حسب"
    " المناطق الإدارية",
    # Written findings
    "Qatar's average population was {value} in {year}": "بلغ متوسط عدد سكان قطر {value} في {year}",
    ", {change} on {year}": "، بتغير {change} مقارنة بعام {year}",
    "The only year-on-year fall in the series was {year} ({change}).": "كان عام {year} الوحيد الذي"
    " شهد انخفاضا سنويا في السلسلة ({change}).",
    "Female labour force participation went from {first} in {first_year} to {last} in "
    "{last_year} ({change} points).": "تغيرت مشاركة الإناث في القوى العاملة من {first} في"
    " {first_year} إلى {last} في {last_year} ({change} نقطة).",
    "Unemployment stayed between {low}% and {high}% in every full year of the survey.": "بقيت"
    " البطالة بين {low}% و{high}% في كل سنة كاملة من المسح.",
    "Men are {share}% of the population ({quarter}).": "يشكل الرجال {share}% من السكان"
    " ({quarter}).",
    "Inflation peaked at {value} in {year}": "بلغ التضخم ذروته عند {value} في {year}",
    " and was {value} in {year}": " وسجل {value} في {year}",
    "In {year} the fastest rise was {top} ({top_change}) and the biggest fall was {low} "
    "({low_change}).": "في {year} كان أسرع ارتفاع في {top} ({top_change}) وأكبر انخفاض في {low}"
    " ({low_change}).",
    "{group} has the highest index: {value} in {year} against 100 in 2018.": "أعلى رقم قياسي هو"
    " {group}: {value} في {year} مقابل 100 في 2018.",
    "Airport traffic fell from {high} passengers in {high_year} to {low} in {low_year} "
    "({change}).": "تراجعت حركة المطار من {high} مسافر في {high_year} إلى {low} في {low_year}"
    " ({change}).",
    "By {year} it was back to {share}% of the {base_year} level.": "وبحلول {year} عادت إلى {share}%"
    " من مستوى {base_year}.",
    "The busiest month in the data is {month} {year} with {value} passengers.": "أكثر الأشهر"
    " ازدحاما في البيانات هو {month} {year} بعدد {value} مسافر.",
    "Hotel guests stayed longer: nights per guest rose from {first} in {first_year} to {last} in "
    "{last_year}.": "طالت إقامة نزلاء الفنادق: ارتفع عدد الليالي لكل نزيل من {first} في"
    " {first_year} إلى {last} في {last_year}.",
    "The source reports fewer nights than guests for {years}, which cannot be right; those "
    "months are flagged by a data test.": "يذكر المصدر عدد ليال أقل من عدد النزلاء في {years}،"
    " وهذا غير ممكن؛ ويشير اختبار بيانات إلى تلك الأشهر.",
    "Electricity use {change} from {first_year} to {last_year} ({first} to {last} TWh)": "استهلاك"
    " الكهرباء {change} من {first_year} إلى {last_year} (من {first} إلى {last} تيراواط ساعة)",
    ", while the population {change}": "، بينما عدد السكان {change}",
    "In {year} each resident used about {kwh} kWh of electricity and {litres} litres of water a "
    "day.": "في {year} استخدم كل مقيم نحو {kwh} كيلوواط ساعة من الكهرباء و{litres} لترا من المياه"
    " يوميا.",
    "The ten largest of {count} zones used {share}% of the electricity in {year}.": "استخدمت أكبر"
    " عشر مناطق من أصل {count} منطقة {share}% من الكهرباء في {year}.",
    "The biggest user was {zone} with {share}% of the national total.": "كان أكبر مستهلك {zone}"
    " بنسبة {share}% من الإجمالي الوطني.",
    "{years} is a partial year on the portal, so it is left out of growth and per-person "
    "figures.": "{years} سنة جزئية في البوابة، لذلك لا تدخل في أرقام النمو وحصة الفرد.",
    # Overview
    "Qatar in numbers": "قطر بالأرقام",
    "Population, prices, travel and utilities from the Qatar Open Data Portal, cleaned and "
    "tested by this project's pipeline.": "السكان والأسعار والسفر والمرافق من بوابة قطر للبيانات"
    " المفتوحة، بعد تنظيفها واختبارها في خط البيانات الخاص بهذا المشروع.",
    "Population": "السكان",
    "Inflation": "التضخم",
    "Female LFPR": "مشاركة الإناث",
    "kWh per person": "كهرباء الفرد",
    "Air passengers": "مسافرو المطار",
    "Female LFPR: labour force participation rate, the share of women aged 15+ who work or look "
    "for work. kWh per person: electricity use divided by the average population. Air "
    "passengers: arrivals plus departures at Hamad International Airport.": "مشاركة الإناث: معدل"
    " المشاركة في القوى العاملة، أي نسبة النساء في سن 15 سنة فأكثر اللواتي يعملن أو يبحثن عن عمل."
    " كهرباء الفرد: استهلاك الكهرباء بالكيلوواط ساعة مقسوما على متوسط عدد السكان. مسافرو المطار:"
    " القادمون والمغادرون عبر مطار حمد الدولي.",
    "Electricity use": "استهلاك الكهرباء",
    "Water use": "استهلاك المياه",
    "Utility use and population, indexed to {year} = 100": "استهلاك المرافق والسكان، مؤشر {year} ="
    " 100",
    "When the electricity line is above the population line, use per person is rising.": "عندما"
    " يكون خط الكهرباء فوق خط السكان، فهذا يعني أن استهلاك الفرد يرتفع.",
    "Year by year": "سنة بعد سنة",
    "Indicator": "المؤشر",
    "Population, average (millions)": "متوسط عدد السكان (مليون)",
    "Population growth": "نمو السكان",
    "Labour force participation": "المشاركة في القوى العاملة",
    "Female participation": "مشاركة الإناث",
    "Unemployment rate": "معدل البطالة",
    "CPI, average (2018 = 100)": "متوسط الرقم القياسي (2018 = 100)",
    "Airport passengers (millions)": "مسافرو المطار (مليون)",
    "Hotel guests (millions)": "نزلاء الفنادق (مليون)",
    "Hotel nights (millions)": "ليالي الإقامة في الفنادق (مليون)",
    "Electricity (GWh)": "الكهرباء (جيجاواط ساعة)",
    "Electricity per person (kWh)": "الكهرباء للفرد (كيلوواط ساعة)",
    "Water (million m3)": "المياه (مليون م³)",
    "Water per person per day (litres)": "المياه للفرد يوميا (لتر)",
    "An empty cell means the source does not cover that whole year.": "الخلية الفارغة تعني أن"
    " المصدر لا يغطي تلك السنة كاملة.",
    # Population and jobs
    "Quarterly Labour Force Survey estimates by sex.": "تقديرات مسح القوى العاملة الفصلي حسب"
    " الجنس.",
    "Population by sex": "السكان حسب الجنس",
    "People": "أفراد",
    "Labour force participation, age 15+": "المشاركة في القوى العاملة، 15 سنة فأكثر",
    "% of population 15+": "% من السكان 15 سنة فأكثر",
    "Population growth on the previous year": "نمو السكان مقارنة بالسنة السابقة",
    "% of labour force": "% من القوى العاملة",
    # Prices
    "Consumer price index by expenditure group, base year 2018 = 100.": "الرقم القياسي لأسعار"
    " المستهلك حسب مجموعة الإنفاق، سنة الأساس 2018 = 100.",
    "General consumer price index": "الرقم القياسي العام لأسعار المستهلك",
    "General index": "الرقم القياسي العام",
    "Index (2018 = 100)": "الرقم القياسي (2018 = 100)",
    "Inflation: change on the same month a year earlier": "التضخم: التغير مقارنة بالشهر نفسه من"
    " السنة السابقة",
    "Annual inflation by expenditure group (average index change)": "التضخم السنوي حسب مجموعة"
    " الإنفاق (تغير متوسط الرقم القياسي)",
    "Change": "التغير",
    "Group": "المجموعة",
    "Red is a price rise, blue a fall. Groups are sorted by the latest year.": "الأحمر ارتفاع في"
    " الأسعار والأزرق انخفاض. المجموعات مرتبة حسب أحدث سنة.",
    "Compare a group with the general index": "قارن مجموعة بالرقم القياسي العام",
    "Expenditure group": "مجموعة الإنفاق",
    "{name} against the general index": "{name} مقارنة بالرقم القياسي العام",
    # Travel and hotels
    "Passengers at Hamad International Airport (2017 to 2022) and hotel guests and nights (2019 "
    "to 2023). The portal has not published newer months for either series.": "المسافرون عبر مطار"
    " حمد الدولي (2017 إلى 2022) ونزلاء الفنادق وليالي الإقامة (2019 إلى 2023). لم تنشر البوابة"
    " أشهرا أحدث لأي من السلسلتين.",
    "Passengers": "المسافرون",
    "Monthly passengers at Hamad International Airport (arrivals plus departures)": "المسافرون"
    " شهريا عبر مطار حمد الدولي (القادمون والمغادرون)",
    "World Cup": "كأس العالم",
    "The FIFA World Cup ran from 20 November to 18 December 2022.": "أقيمت بطولة كأس العالم لكرة"
    " القدم من 20 نوفمبر إلى 18 ديسمبر 2022.",
    "Airport passengers per year": "مسافرو المطار سنويا",
    "Nights of stay": "ليالي الإقامة",
    "Guests": "النزلاء",
    "Hotel guests and nights of stay": "نزلاء الفنادق وليالي الإقامة",
    "Per month": "شهريا",
    "From January 2019 to January 2020 the source has fewer nights than guests, which is not "
    "possible; a data test flags those months.": "من يناير 2019 إلى يناير 2020 يذكر المصدر عدد ليال"
    " أقل من عدد النزلاء، وهذا غير ممكن؛ ويشير اختبار بيانات إلى تلك الأشهر.",
    # Electricity and water
    "KAHRAMAA consumption by official zone. Per-person figures use the average quarterly "
    "population from the Labour Force Survey.": "استهلاك كهرماء حسب المناطق الرسمية. تعتمد أرقام"
    " الفرد على متوسط عدد السكان الفصلي من مسح القوى العاملة.",
    "Electricity consumption": "استهلاك الكهرباء",
    "GWh": "جيجاواط ساعة",
    "Grey bars are partial years.": "الأعمدة الرمادية سنوات جزئية.",
    "Water consumption": "استهلاك المياه",
    "Million m3": "مليون م³",
    "Electricity per person": "الكهرباء للفرد",
    "kWh per year": "كيلوواط ساعة في السنة",
    "Water per person": "المياه للفرد",
    "Litres per day": "لتر في اليوم",
    "Zones": "المناطق",
    "Year": "السنة",
    "Top 15 zones by electricity use, {year}": "أكبر 15 منطقة في استهلاك الكهرباء، {year}",
    "These 15 zones used {share}% of the electricity in {year}.": "استخدمت هذه المناطق الخمس عشرة"
    " {share}% من الكهرباء في {year}.",
    "One zone over time": "منطقة واحدة عبر الزمن",
    "Zone": "المنطقة",
    "Electricity": "الكهرباء",
    "Water": "المياه",
    "m3": "م³",
    # Pipeline health
    "Where the data came from, when it was fetched, and how the latest data tests went. The "
    "full data catalog with lineage is in docs/data_catalog.md.": "مصدر البيانات ووقت جلبها ونتائج"
    " أحدث اختبارات البيانات. يوجد فهرس البيانات الكامل في docs/data_catalog.md.",
    "Datasets": "مجموعات البيانات",
    "Raw rows": "الصفوف الخام",
    "Models built": "النماذج المبنية",
    "Data tests": "اختبارات البيانات",
    "not run yet": "لم تعمل بعد",
    "Data tests passed": "الاختبارات الناجحة",
    "{passed} of {total}": "{passed} من {total}",
    "{warnings} warnings, {failed} failed": "{warnings} تحذيرات، {failed} فشل",
    "Sources": "المصادر",
    "Key": "المفتاح",
    "Dataset": "مجموعة البيانات",
    "Rows": "الصفوف",
    "Fetched": "وقت الجلب",
    "Changed on portal": "آخر تغيير في البوابة",
    "SHA-256 (start)": "SHA-256 (البداية)",
    "Portal page": "صفحة البوابة",
    "open": "فتح",
    "Latest data tests": "أحدث اختبارات البيانات",
    "No data test results yet. Run `python -m pipeline run` or `python -m pipeline test`.": "لا"
    " توجد نتائج اختبارات بعد. شغل `python -m pipeline run` أو `python -m pipeline test`.",
    "Every data test passed.": "نجحت جميع اختبارات البيانات.",
    "Warnings are known issues in the source data, or sudden month-on-month jumps that are worth "
    "a look and may be real events. They are reported on every run but do not stop the "
    "pipeline; a failed test does.": "التحذيرات مشكلات معروفة في البيانات المصدر، أو قفزات مفاجئة"
    " من شهر إلى آخر تستحق النظر وقد تكون أحداثا حقيقية. تظهر في كل تشغيل لكنها لا توقف خط"
    " البيانات، أما الاختبار الفاشل فيوقفه. نص نتائج الاختبارات بالإنجليزية كما هو مخزن.",
    "Status": "الحالة",
    "Test": "الاختبار",
    "Result": "النتيجة",
    "All {count} tests": "جميع الاختبارات ({count})",
    "Models in the latest build": "النماذج في أحدث بناء",
}
