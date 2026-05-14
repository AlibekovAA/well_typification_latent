from __future__ import annotations

import logging
import sqlite3
from collections.abc import Sequence
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Literal, TypedDict, cast

import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html, no_update

from config import (
    CLUSTER_COLORS,
    CLUSTER_LABELS,
    DASH_MODE_CHART_HEIGHT_PX,
    DASH_MODE_CHART_MARGIN_BOTTOM_PX,
    DASH_MODE_VISIBLE_POINTS,
    FAST_EMULATOR_SLEEP_SECONDS,
    FEATURE_COLUMNS,
    STREAM_SLEEP_SECONDS,
    WELL_CONFIGS,
)
from dashboard.components import layout_root
from streaming import fetch_history, fetch_history_since, get_connection, init_db, run_emulator_background
from utils import load_thresholds

logger = logging.getLogger(__name__)


WELL_PUMP_TYPES: dict[str, str] = {w.well_id: w.pump_type for w in WELL_CONFIGS}

_HISTORY_LIMIT = 8_640
_INITIAL_LOAD_LIMIT = 8_640
_INCREMENTAL_LOAD_LIMIT = 1_024
_HISTORY_CACHE: dict[str, list[WellRecord]] = {w.well_id: [] for w in WELL_CONFIGS}
_HISTORY_LAST_TS: dict[str, str | None] = {w.well_id: None for w in WELL_CONFIGS}
_HISTORY_LOCK = Lock()


class WellRecord(TypedDict):
    timestamp: str
    cluster: int
    deviation: float
    pump_type: str
    us_center: float | None
    us_periph: float | None
    gas_center: float | None
    gas_periph: float | None
    temp: float | None
    water_center: float | None
    water_periph: float | None
    gas_integral: float | None
    water_integral: float | None


FeatureCol = Literal[
    "us_center",
    "us_periph",
    "gas_center",
    "gas_periph",
    "temp",
    "water_center",
    "water_periph",
    "gas_integral",
    "water_integral",
]


def _row_to_well_record(row: sqlite3.Row) -> WellRecord:
    return WellRecord(
        timestamp=row["timestamp"],
        cluster=row["cluster"],
        deviation=row["deviation"],
        pump_type=row["pump_type"],
        us_center=row["us_center"],
        us_periph=row["us_periph"],
        gas_center=row["gas_center"],
        gas_periph=row["gas_periph"],
        temp=row["temp"],
        water_center=row["water_center"],
        water_periph=row["water_periph"],
        gas_integral=row["gas_integral"],
        water_integral=row["water_integral"],
    )


def _get_pump_type(well_id: str) -> str:
    pump_type = WELL_PUMP_TYPES.get(well_id)
    if pump_type is None:
        raise KeyError(f"Unknown well_id {well_id}")
    return pump_type


@lru_cache(maxsize=1)
def _load_all_thresholds() -> dict[str, dict[int, dict[str, float]]]:
    thresholds: dict[str, dict[int, dict[str, float]]] = {}
    for pump_type in ("ecn", "shgn"):
        try:
            thresholds[pump_type] = load_thresholds(pump_type)
        except FileNotFoundError:
            logger.warning("Пороги не найдены для pump_type=%s, используются значения по умолчанию", pump_type)
    return thresholds


def _mode_chart_margins() -> dict[str, int]:
    return {
        "t": 12,
        "b": DASH_MODE_CHART_MARGIN_BOTTOM_PX,
        "l": 12,
        "r": 12,
    }


_FEATURE_CHART_HEIGHT = 220


def _time_tickformat(timestamps: Sequence[str]) -> str:
    if len(timestamps) < 2:
        return "%H:%M"
    unique_timestamps = set(timestamps)
    unique_minutes = {ts[:16] for ts in timestamps}
    if len(unique_timestamps) > len(unique_minutes):
        return "%H:%M:%S"
    return "%H:%M"


def _bar_width_ms(timestamps: Sequence[str]) -> int:
    if len(timestamps) < 2:
        return 10_000
    parsed = [datetime.fromisoformat(ts) for ts in timestamps]
    deltas_ms = [(b - a).total_seconds() * 1000.0 for a, b in zip(parsed, parsed[1:], strict=False)]
    positive = [d for d in deltas_ms if d > 0]
    if not positive:
        return 10_000
    step_ms = min(positive)
    width = int(step_ms * 0.8)
    return max(500, min(width, 30_000))


def _empty_figure(*, height: int | None = None, modes_well_graph: bool = False) -> go.Figure:
    if modes_well_graph:
        h = DASH_MODE_CHART_HEIGHT_PX
        margin = _mode_chart_margins()
    else:
        h = height if height is not None else DASH_MODE_CHART_HEIGHT_PX
        margin = {"t": 8, "b": 8, "l": 8, "r": 8}
    fig = go.Figure()
    fig.update_layout(
        margin=margin,
        height=h,
        xaxis={"visible": False},
        yaxis={"visible": False},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        annotations=[
            {
                "text": "Данных пока нет",
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"size": 14, "color": "#8fa3b8"},
            }
        ],
    )
    return fig


def _get_cluster_thresholds(pump_type: str, cluster: int) -> dict[str, float] | None:
    return _load_all_thresholds().get(pump_type, {}).get(cluster)


def _refresh_history_cache(conn: sqlite3.Connection, well_id: str) -> list[WellRecord]:
    with _HISTORY_LOCK:
        last_timestamp = _HISTORY_LAST_TS[well_id]
        if last_timestamp is None:
            rows_raw = fetch_history(conn, well_id, limit=_INITIAL_LOAD_LIMIT)
            _HISTORY_CACHE[well_id] = [_row_to_well_record(r) for r in rows_raw]
            if _HISTORY_CACHE[well_id]:
                _HISTORY_LAST_TS[well_id] = _HISTORY_CACHE[well_id][0]["timestamp"]
            return _HISTORY_CACHE[well_id]

        new_rows = fetch_history_since(
            conn,
            well_id,
            since_exclusive=last_timestamp,
            limit=_INCREMENTAL_LOAD_LIMIT,
        )
        if not new_rows:
            return _HISTORY_CACHE[well_id]

        new_records = [_row_to_well_record(r) for r in new_rows]
        new_records_desc = list(reversed(new_records))
        _HISTORY_CACHE[well_id] = (new_records_desc + _HISTORY_CACHE[well_id])[:_HISTORY_LIMIT]
        _HISTORY_LAST_TS[well_id] = new_records[-1]["timestamp"]
        return _HISTORY_CACHE[well_id]


def _deviation_color(pump_type: str, cluster: int, deviation: float) -> str:
    thresholds = _get_cluster_thresholds(pump_type, cluster)
    if thresholds is not None:
        warn = thresholds["warn"]
        alert = thresholds["alert"]
    else:
        warn = 5.0
        alert = 5.5

    if deviation < warn:
        return "#2ecc71"
    if deviation < alert:
        return "#f39c12"
    return "#e74c3c"


def _deviation_label(pump_type: str, cluster: int, deviation: float) -> str:
    thresholds = _get_cluster_thresholds(pump_type, cluster)
    if thresholds is not None:
        warn = thresholds["warn"]
        alert = thresholds["alert"]
    else:
        warn = 5.0
        alert = 5.5

    if deviation < warn:
        return "● Норма"
    if deviation < alert:
        return "● Внимание"
    return "● Аномалия"


def _build_status(well_id: str, cluster: int, deviation: float) -> html.Div:
    pump_type = _get_pump_type(well_id)
    cluster_name = CLUSTER_LABELS.get(pump_type, {}).get(cluster, str(cluster))
    cluster_color = CLUSTER_COLORS.get(pump_type, {}).get(cluster, "#7f8c8d")
    dev_color = _deviation_color(pump_type, cluster, deviation)
    dev_label = _deviation_label(pump_type, cluster, deviation)

    return html.Div(
        [
            html.Span(
                cluster_name,
                style={
                    "background": cluster_color,
                    "color": "white",
                    "borderRadius": "6px",
                    "padding": "3px 10px",
                    "fontWeight": "600",
                    "fontSize": "13px",
                    "marginRight": "10px",
                },
            ),
            html.Span(
                f"{dev_label}  {deviation:.3f}",
                style={
                    "color": dev_color,
                    "fontWeight": "600",
                    "fontSize": "13px",
                    "background": f"{dev_color}18",
                    "borderRadius": "6px",
                    "padding": "3px 10px",
                },
            ),
        ],
        style={"marginBottom": "8px", "display": "flex", "alignItems": "center", "flexWrap": "wrap", "gap": "6px"},
    )


def _empty_status() -> html.Div:
    return html.Div(
        html.Span("Данных пока нет…", style={"color": "#95a5a6", "fontSize": "13px"}),
        style={"marginBottom": "8px"},
    )


def _build_figure(well_id: str, rows: Sequence[WellRecord]) -> go.Figure:
    pump_type = _get_pump_type(well_id)
    rows_asc = list(reversed(rows))
    rows_asc = rows_asc[-DASH_MODE_VISIBLE_POINTS:]
    if not rows_asc:
        return _empty_figure(modes_well_graph=True)

    timestamps = [r["timestamp"] for r in rows_asc]
    tick_format = _time_tickformat(timestamps)
    bar_width = _bar_width_ms(timestamps)
    clusters = [r["cluster"] for r in rows_asc]
    deviations = [r["deviation"] for r in rows_asc]

    fig = go.Figure()

    cluster_ids = sorted(CLUSTER_LABELS.get(pump_type, {}).keys())
    for c in sorted(set(clusters) - set(cluster_ids)):
        cluster_ids.append(c)
    if not cluster_ids:
        cluster_ids = sorted(set(clusters))

    for c in cluster_ids:
        color = CLUSTER_COLORS.get(pump_type, {}).get(c, "#7f8c8d")
        label = CLUSTER_LABELS.get(pump_type, {}).get(c, str(c))
        xs: list[str] = []
        devs_c: list[float] = []
        for idx, cl in enumerate(clusters):
            if cl == c:
                xs.append(timestamps[idx])
                devs_c.append(deviations[idx])

        if xs:
            fig.add_trace(
                go.Bar(
                    x=xs,
                    y=[1] * len(xs),
                    name=label,
                    marker_color=color,
                    text=[f"{label}<br>Откл. {d:.3f}" for d in devs_c],
                    textposition="none",
                    hovertemplate="%{x}<br>%{text}<extra></extra>",
                    width=bar_width,
                )
            )
        else:
            fig.add_trace(
                go.Bar(
                    x=[timestamps[len(timestamps) // 2]],
                    y=[1],
                    name=label,
                    marker_color=color,
                    width=1,
                    visible="legendonly",
                    hoverinfo="skip",
                    showlegend=True,
                )
            )

    legend_font = 11

    fig.update_layout(
        barmode="stack",
        margin=_mode_chart_margins(),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        height=DASH_MODE_CHART_HEIGHT_PX,
        showlegend=True,
        bargap=0.06,
        hovermode="x unified",
        hoverlabel={"bgcolor": "#0f172a", "font": {"size": 12, "color": "#f8fafc"}},
        yaxis={"visible": False, "range": [0, 1]},
        xaxis={
            "showgrid": False,
            "tickformat": tick_format,
            "tickangle": -25,
            "tickfont": {"size": 12, "color": "#334155"},
            "automargin": False,
            "ticklabelstandoff": 10,
            "nticks": 8,
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 0.02,
            "yref": "container",
            "xanchor": "center",
            "x": 0.5,
            "xref": "container",
            "font": {"size": legend_font, "color": "#334155"},
            "itemwidth": 30,
            "tracegroupgap": 16,
        },
    )
    return fig


def _build_feature_figure(rows: Sequence[WellRecord], feature_col: FeatureCol) -> go.Figure:
    if not rows:
        return _empty_figure(height=_FEATURE_CHART_HEIGHT)

    rows_asc = list(reversed(rows))
    timestamps = [r["timestamp"] for r in rows_asc]
    tick_format = _time_tickformat(timestamps)
    raw_values = [r[feature_col] for r in rows_asc]

    pairs = [(t, v) for t, v in zip(timestamps, raw_values, strict=False) if v is not None]
    if not pairs:
        return _empty_figure(height=_FEATURE_CHART_HEIGHT)

    ts_filtered, values_filtered = zip(*pairs, strict=False)

    fig = go.Figure(
        go.Scatter(
            x=list(ts_filtered),
            y=list(values_filtered),
            mode="lines",
            line={"width": 2, "color": "#3498db"},
            fill="tozeroy",
            fillcolor="rgba(52,152,219,0.08)",
        )
    )
    fig.update_xaxes(
        tickformat=tick_format,
        tickangle=-25,
        showgrid=True,
        gridcolor="rgba(148,163,184,0.25)",
        tickfont={"size": 11, "color": "#334155"},
        nticks=8,
        zeroline=False,
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(148,163,184,0.25)",
        tickfont={"size": 11, "color": "#334155"},
        zeroline=False,
    )
    fig.update_layout(
        margin={"t": 8, "b": 32, "l": 52, "r": 12},
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        autosize=True,
        hovermode="x unified",
        hoverlabel={"bgcolor": "#0f172a", "font": {"size": 12, "color": "#f8fafc"}},
        showlegend=False,
    )
    return fig


def create_app(*, update_interval_ms: int = 10_000) -> Dash:
    assets = Path(__file__).resolve().parent / "assets"
    app = Dash(__name__, assets_folder=str(assets))
    app.layout = html.Div(
        [
            layout_root(update_interval_seconds=update_interval_ms // 1000),
            dcc.Interval(id="update-interval", interval=update_interval_ms, n_intervals=0),
        ]
    )

    status_outputs: list[Output] = []
    for w in WELL_CONFIGS:
        status_outputs.append(Output(f"status-{w.well_id}", "children"))
        status_outputs.append(Output(f"graph-{w.well_id}", "figure"))

    feature_outputs = [Output(f"feature-graph-{col}", "figure") for col in FEATURE_COLUMNS]

    @app.callback(
        status_outputs,
        Input("update-interval", "n_intervals"),
        Input("dashboard-tabs", "value"),
    )
    def update_modes(_: int, tab_value: str | None) -> tuple[object, ...]:
        if tab_value != "modes":
            return tuple(no_update for _ in status_outputs)

        result: list[object] = []

        with get_connection() as conn:
            for w in WELL_CONFIGS:
                rows = _refresh_history_cache(conn, w.well_id)

                if not rows:
                    result.append(_empty_status())
                    result.append(_empty_figure(modes_well_graph=True))
                    continue

                last = rows[0]
                result.append(_build_status(w.well_id, last["cluster"], last["deviation"]))
                result.append(_build_figure(w.well_id, rows))

        return tuple(result)

    @app.callback(
        feature_outputs,
        Input("update-interval", "n_intervals"),
        Input("dashboard-tabs", "value"),
        Input("well-selector", "value"),
    )
    def update_features(
        _: int,
        tab_value: str | None,
        well_value: str | None,
    ) -> tuple[object, ...]:
        if tab_value != "features":
            return tuple(no_update for _ in FEATURE_COLUMNS)

        if not well_value:
            return tuple(_empty_figure(height=_FEATURE_CHART_HEIGHT) for _ in FEATURE_COLUMNS)

        with get_connection() as conn:
            rows = _refresh_history_cache(conn, well_value)

        if not rows:
            return tuple(_empty_figure(height=_FEATURE_CHART_HEIGHT) for _ in FEATURE_COLUMNS)

        return tuple(_build_feature_figure(rows, cast(FeatureCol, col)) for col in FEATURE_COLUMNS)

    return app


def run_app(*, fast: bool = False) -> None:
    sleep_seconds = FAST_EMULATOR_SLEEP_SECONDS if fast else STREAM_SLEEP_SECONDS
    if fast:
        logger.info("Режим быстрого эмулятора: пауза %.2f с между строками", sleep_seconds)
    logger.info("Инициализация БД и запуск эмулятора")
    init_db()
    run_emulator_background(sleep_seconds=sleep_seconds)
    logger.info("Dash запускается на http://127.0.0.1:8050")
    update_interval_ms = 1_000 if fast else 10_000
    app = create_app(update_interval_ms=update_interval_ms)
    app.run(debug=False, use_reloader=False)


if __name__ == "__main__":
    run_app()
