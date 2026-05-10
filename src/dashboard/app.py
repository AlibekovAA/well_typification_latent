from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Literal, TypedDict, cast

import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html, no_update

from config import (
    CLUSTER_COLORS,
    CLUSTER_LABELS,
    FAST_EMULATOR_SLEEP_SECONDS,
    FEATURE_COLUMNS,
    STREAM_SLEEP_SECONDS,
    WELL_CONFIGS,
)
from dashboard.components import layout_root
from streaming import fetch_history, get_connection, init_db, run_emulator_background
from utils import load_thresholds

logger = logging.getLogger(__name__)


THRESHOLDS: dict[str, dict[int, dict[str, float]]] = {
    "ecn": load_thresholds("ecn"),
    "shgn": load_thresholds("shgn"),
}


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


def _row_to_well_record(row: Any) -> WellRecord:
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
    for w in WELL_CONFIGS:
        if w.well_id == well_id:
            return w.pump_type
    raise KeyError(f"Unknown well_id {well_id}")


def _empty_figure(*, height: int = 140) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        margin={"t": 8, "b": 8, "l": 8, "r": 8},
        height=height,
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
                "font": {"size": 13, "color": "#95a5a6"},
            }
        ],
    )
    return fig


def _get_cluster_thresholds(pump_type: str, cluster: int) -> dict[str, float] | None:
    return THRESHOLDS.get(pump_type, {}).get(cluster)


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
    if not rows_asc:
        return _empty_figure()

    timestamps = [r["timestamp"] for r in rows_asc]
    clusters = [r["cluster"] for r in rows_asc]
    deviations = [r["deviation"] for r in rows_asc]

    fig = go.Figure()

    seen: set[int] = set()
    for c in clusters:
        if c in seen:
            continue
        seen.add(c)
        color = CLUSTER_COLORS.get(pump_type, {}).get(c, "#7f8c8d")
        label = CLUSTER_LABELS.get(pump_type, {}).get(c, str(c))
        xs: list[str] = []
        devs_c: list[float] = []
        for idx, cl in enumerate(clusters):
            if cl == c:
                xs.append(timestamps[idx])
                devs_c.append(deviations[idx])

        fig.add_trace(
            go.Bar(
                x=xs,
                y=[1] * len(xs),
                name=label,
                marker_color=color,
                text=[f"{label}<br>Откл. {d:.3f}" for d in devs_c],
                hovertemplate="%{x}<br>%{text}<extra></extra>",
                width=11_000,
            )
        )

    fig.update_layout(
        barmode="stack",
        margin={"t": 8, "b": 36, "l": 8, "r": 8},
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        height=130,
        showlegend=True,
        bargap=0,
        yaxis={"visible": False, "range": [0, 1]},
        xaxis={
            "showgrid": False,
            "tickformat": "%H:%M",
            "tickfont": {"size": 10},
        },
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.28,
            "xanchor": "center",
            "x": 0.5,
            "font": {"size": 11},
        },
    )
    return fig


def _build_feature_figure(rows: Sequence[WellRecord], feature_col: FeatureCol) -> go.Figure:
    if not rows:
        return _empty_figure(height=130)

    rows_asc = list(reversed(rows))
    timestamps = [r["timestamp"] for r in rows_asc]
    raw_values = [r[feature_col] for r in rows_asc]

    pairs = [(t, v) for t, v in zip(timestamps, raw_values, strict=False) if v is not None]
    if not pairs:
        return _empty_figure(height=130)

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
        tickformat="%H:%M",
        showgrid=True,
        gridcolor="rgba(0,0,0,0.05)",
        tickfont={"size": 10},
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(0,0,0,0.05)",
        tickfont={"size": 10},
    )
    fig.update_layout(
        margin={"t": 6, "b": 24, "l": 44, "r": 8},
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        height=130,
        showlegend=False,
    )
    return fig


def create_app(*, update_interval_ms: int = 10_000) -> Dash:
    app = Dash(__name__)
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
    )
    def update_modes(_: int) -> tuple[Any, ...]:
        result: list[Any] = []

        with get_connection() as conn:
            for w in WELL_CONFIGS:
                rows_raw = fetch_history(conn, w.well_id, limit=8640)
                rows = [_row_to_well_record(r) for r in rows_raw]

                if not rows:
                    result.append(_empty_status())
                    result.append(_empty_figure())
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
    ) -> tuple[Any, ...]:
        if tab_value != "features":
            return tuple(no_update for _ in FEATURE_COLUMNS)

        if not well_value:
            return tuple(_empty_figure(height=130) for _ in FEATURE_COLUMNS)

        with get_connection() as conn:
            rows_raw = fetch_history(conn, well_value, limit=8640)

        rows = [_row_to_well_record(r) for r in rows_raw]

        if not rows:
            return tuple(_empty_figure(height=130) for _ in FEATURE_COLUMNS)

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
