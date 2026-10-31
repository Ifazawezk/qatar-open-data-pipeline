"""Plotly figures with one consistent look.

Colour rules used throughout:
- categorical series take slots in a fixed order (blue, orange, aqua) and a
  chart never shows more than three, so colour-blind readers can tell them
  apart; every chart with two or more series has a legend
- magnitude uses a single blue, partial periods are shown in muted grey
- inflation uses a diverging blue / grey / red scale centred on zero
- text stays in ink colours, never in a series colour
- one y axis per chart; two measures with different units get two charts

In Arabic mode titles, legends and ranked bars move to the right, and dates show
digits only because Plotly would print English month names. Time still runs
left to right.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from dashboard.i18n import is_arabic

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'
SERIES = ("#2a78d6", "#eb6834", "#1baf7a")
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
PARTIAL = "#c3c2b7"
DIVERGING = [[0.0, "#2a78d6"], [0.5, "#f0efec"], [1.0, "#e34948"]]


def style(
    fig: go.Figure,
    title: str,
    y_title: str = "",
    height: int = 340,
    hovermode: str | bool = "x unified",
    y_format: str = ",",
    from_zero: bool = True,
) -> go.Figure:
    fig.update_layout(
        title={"text": title, "x": 0, "xanchor": "left", "font": {"size": 15, "color": INK}},
        height=height,
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font={"family": FONT, "size": 12, "color": INK_SECONDARY},
        margin={"l": 8, "r": 16, "t": 64, "b": 8},
        hovermode=hovermode,
        hoverlabel={"bgcolor": "#ffffff", "font": {"family": FONT, "color": INK}},
        legend={
            "orientation": "h",
            "x": 0,
            "y": 1.02,
            "yanchor": "bottom",
            "font": {"color": INK_SECONDARY},
        },
        bargap=0.25,
        barcornerradius=4,
    )
    fig.update_xaxes(
        automargin=True,
        showgrid=False,
        linecolor=AXIS,
        ticks="outside",
        tickcolor=AXIS,
        tickfont={"color": MUTED},
        title=None,
    )
    fig.update_yaxes(
        automargin=True,
        gridcolor=GRID,
        gridwidth=1,
        zeroline=True,
        zerolinecolor=AXIS,
        tickfont={"color": MUTED},
        tickformat=y_format,
        title={"text": y_title, "font": {"color": MUTED}},
        rangemode="tozero" if from_zero else "normal",
    )
    if is_arabic():
        fig.update_layout(
            title={"x": 1, "xanchor": "right", "pad": {"r": 16}},
            legend={"x": 1, "xanchor": "right"},
            hoverlabel={"align": "right"},
        )
    return fig


def _digits_only_dates(fig: go.Figure, values: pd.Series) -> None:
    if is_arabic() and pd.api.types.is_datetime64_any_dtype(values):
        fig.update_xaxes(tickformat="%Y", dtick="M12", hoverformat="%Y-%m")


def lines(
    df: pd.DataFrame,
    x: str,
    series: dict[str, str],
    title: str,
    y_title: str = "",
    value_format: str = ",.0f",
    y_format: str = ",",
    label_ends: bool = True,
    from_zero: bool = True,
) -> go.Figure:
    """One line per entry in series ({legend label: column})."""
    if len(series) > len(SERIES):
        raise ValueError("at most three series per chart")
    fig = go.Figure()
    for (label, column), color in zip(series.items(), SERIES, strict=False):
        data = df[[x, column]].dropna()
        fig.add_trace(
            go.Scatter(
                x=data[x],
                y=data[column],
                name=label,
                mode="lines",
                line={"width": 2, "color": color},
                hovertemplate=f"{label}: %{{y:{value_format}}}<extra></extra>",
            )
        )
        if label_ends and len(series) > 1 and not data.empty:
            last = data.iloc[-1]
            fig.add_annotation(
                x=last[x],
                y=last[column],
                text=label,
                showarrow=False,
                xanchor="left",
                xshift=6,
                font={"color": INK_SECONDARY, "size": 11},
            )
    style(fig, title, y_title, y_format=y_format, from_zero=from_zero)
    if label_ends and len(series) > 1:
        fig.update_layout(margin={"r": 124 if is_arabic() else 72})
    _digits_only_dates(fig, df[x])
    return fig


def bars(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    y_title: str = "",
    value_format: str = ",.0f",
    y_format: str = ",",
    muted: pd.Series | None = None,
    name: str = "",
) -> go.Figure:
    """Single-series bars; rows flagged in `muted` (for example partial years) are grey."""
    if is_arabic() and y_format == "~s":
        y_format = ","  # SI suffixes such as M are Latin letters
    flags = list(muted) if muted is not None else [False] * len(df)
    colors = [PARTIAL if flag else SERIES[0] for flag in flags]
    fig = go.Figure(
        go.Bar(
            x=df[x],
            y=df[y],
            name=name or y_title,
            marker={"color": colors},
            hovertemplate=f"%{{x}}: %{{y:{value_format}}}<extra></extra>",
        )
    )
    style(fig, title, y_title, hovermode="closest", y_format=y_format)
    if df[x].dtype == object:  # labels such as years as text: show every one
        fig.update_xaxes(type="category")
        fig.update_layout(bargap=0.4)
    _digits_only_dates(fig, df[x])
    return fig


def hbars(
    df: pd.DataFrame,
    label: str,
    value: str,
    title: str,
    x_title: str = "",
    value_format: str = ",.0f",
    height: int = 460,
) -> go.Figure:
    """Ranked horizontal bars, largest at the top."""
    data = df.sort_values(value)
    fig = go.Figure(
        go.Bar(
            x=data[value],
            y=data[label],
            orientation="h",
            marker={"color": SERIES[0]},
            hovertemplate=f"%{{y}}: %{{x:{value_format}}}<extra></extra>",
        )
    )
    style(fig, title, height=height, hovermode="closest")
    fig.update_xaxes(
        showgrid=True, gridcolor=GRID, title={"text": x_title, "font": {"color": MUTED}}
    )
    fig.update_yaxes(showgrid=False, tickfont={"color": INK_SECONDARY}, title=None)
    fig.update_layout(bargap=0.3)
    if is_arabic():  # bars grow from the labels on the right
        fig.update_xaxes(autorange="reversed")
        fig.update_yaxes(side="right")
    return fig


def diverging_heatmap(
    pivot: pd.DataFrame, title: str, value_label: str, value_format: str = "+.1f"
) -> go.Figure:
    """Rows x columns grid coloured on a scale centred on zero."""
    limit = float(pivot.abs().max().max() or 1)
    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=[str(c) for c in pivot.columns],
            y=list(pivot.index),
            colorscale=DIVERGING,
            zmid=0,
            zmin=-limit,
            zmax=limit,
            xgap=2,
            ygap=2,
            colorbar={"title": {"text": value_label, "font": {"color": MUTED}}, "ticksuffix": "%"},
            hovertemplate=f"%{{y}}, %{{x}}: %{{z:{value_format}}}%<extra></extra>",
        )
    )
    style(fig, title, height=40 + 34 * len(pivot.index), hovermode="closest")
    fig.update_yaxes(
        autorange="reversed", showgrid=False, ticks="", tickfont={"color": INK_SECONDARY}
    )
    fig.update_xaxes(type="category", ticks="")
    if is_arabic():
        fig.update_yaxes(side="right")
        fig.update_traces(colorbar={"x": -0.02, "xanchor": "right"})
    return fig


def mark_month(fig: go.Figure, when, text: str) -> go.Figure:
    """A thin vertical guide with a short label, for events such as a tournament."""
    fig.add_vline(x=when, line={"color": AXIS, "width": 1})
    fig.add_annotation(
        x=when,
        y=1,
        yref="paper",
        text=text,
        showarrow=False,
        xanchor="right",
        xshift=-4,
        font={"color": INK_SECONDARY, "size": 11},
    )
    return fig
