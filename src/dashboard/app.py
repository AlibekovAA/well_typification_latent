from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, html, no_update

from config import (
    CLUSTER_COLORS,
    CLUSTER_LABELS,
    DB_PATH,
    DEVIATION_ALERT_THRESHOLD,
    DEVIATION_WARN_THRESHOLD,
    FAST_EMULATOR_SLEEP_SECONDS,
    FEATURE_COLUMNS,
    STREAM_SLEEP_SECONDS,
    WELL_CONFIGS,
)
from dashboard.components import layout_root
from streaming import fetch_history, get_connection, init_db, run_emulator_background

logger = logging.getLogger(__name__)

_WELL_PUMP: dict[str, str] = {w.well_id: w.pump_type for w in WELL_CONFIGS}


def _empty_figure() -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        margin={"t": 8, "b": 8, "l": 8, "r": 8},
        height=140,
        xaxis={"visible": False, "showticklabels": False},
        yaxis={"visible": False, "showticklabels": False},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return fig


def _deviation_color(deviation: float) -> str:
    if deviation < DEVIATION_WARN_THRESHOLD:
        return "#2ecc71"
    if deviation < DEVIATION_ALERT_THRESHOLD:
        return "#f39c12"
    return "#e74c3c"


def _deviation_label(deviation: float) -> str:
    if deviation < DEVIATION_WARN_THRESHOLD:
        return "● Норма"
    if deviation < DEVIATION_ALERT_THRESHOLD:
        return "● Внимание"
    return "● Аномалия"


def _build_status(well_id: str, cluster: int, deviation: float) -> html.Div:
    pump_type = _WELL_PUMP[well_id]
    cluster_name = CLUSTER_LABELS.get(pump_type, {}).get(cluster, str(cluster))
    cluster_color = CLUSTER_COLORS.get(pump_type, {}).get(cluster, "#7f8c8d")
    dev_color = _deviation_color(deviation)

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
                    "fontSize": "14px",
                    "marginRight": "10px",
                },
            ),
            html.Span(
                f"{_deviation_label(deviation)}  {deviation:.3f}",
                style={"color": dev_color, "fontWeight": "600", "fontSize": "14px"},
            ),
        ],
        style={"marginBottom": "6px"},
    )


def _build_figure(well_id: str, rows: Sequence[Any]) -> go.Figure:
    pump_type = _WELL_PUMP[well_id]
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
        xs = [t for t, cl in zip(timestamps, clusters, strict=False) if cl == c]
        devs_c = [d for d, cl in zip(deviations, clusters, strict=False) if cl == c]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=[0] * len(xs),
                mode="markers",
                marker={"size": 14, "symbol": "square", "color": color},
                name=label,
                text=[f"{label}<br>откл. {d:.3f}" for d in devs_c],
                hovertemplate="%{x}<br>%{text}<extra></extra>",
            )
        )

    fig.update_yaxes(visible=False, showgrid=False, zeroline=False)
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(0,0,0,0.06)",
        zeroline=False,
        tickformat="%H:%M",
    )
    fig.update_layout(
        margin={"t": 8, "b": 36, "l": 8, "r": 8},
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        height=160,
        showlegend=True,
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.22,
            "xanchor": "center",
            "x": 0.5,
            "font": {"size": 11},
        },
    )
    return fig


def _build_feature_figure(rows: Sequence[Any], feature_col: str) -> go.Figure:
    if not rows:
        return _empty_figure()
    rows_asc = list(reversed(rows))
    timestamps = [r["timestamp"] for r in rows_asc]
    values = [r[feature_col] for r in rows_asc]
    if any(v is None for v in values):
        return _empty_figure()
    fig = go.Figure(
        go.Scatter(
            x=timestamps,
            y=values,
            mode="lines+markers",
            line={"width": 2, "color": "#3498db"},
            marker={"size": 4},
        )
    )
    fig.update_xaxes(tickformat="%H:%M", showgrid=True, gridcolor="rgba(0,0,0,0.06)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.06)")
    fig.update_layout(
        margin={"t": 6, "b": 24, "l": 40, "r": 8},
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        height=120,
        showlegend=False,
    )
    return fig


def create_app() -> Dash:
    app = Dash(__name__)
    app.layout = layout_root()

    outputs: list[Output] = []
    for w in WELL_CONFIGS:
        outputs += [
            Output(f"status-{w.well_id}", "children"),
            Output(f"graph-{w.well_id}", "figure"),
        ]
    for col in FEATURE_COLUMNS:
        outputs.append(Output(f"feature-graph-{col}", "figure"))

    @app.callback(
        outputs,
        Input("update-interval", "n_intervals"),
        Input("dashboard-tabs", "value"),
        Input("well-selector", "value"),
    )
    def update_all(_: int, tab_value: str | None, well_value: str | None) -> tuple[Any, ...]:
        n_mode = 2 * len(WELL_CONFIGS)
        n_feature = len(FEATURE_COLUMNS)
        result: list[Any] = [no_update] * (n_mode + n_feature)

        if tab_value == "features" and well_value:
            with get_connection(DB_PATH) as conn:
                rows = fetch_history(conn, well_value, limit=8640)
            if rows:
                try:
                    latest_dt = datetime.fromisoformat(rows[0]["timestamp"])
                    since_dt = latest_dt - timedelta(hours=24)
                    rows = [r for r in rows if datetime.fromisoformat(r["timestamp"]) >= since_dt]
                except ValueError:
                    pass
            for i, col in enumerate(FEATURE_COLUMNS):
                result[n_mode + i] = _build_feature_figure(rows or [], col)
            return tuple(result)

        for idx, w in enumerate(WELL_CONFIGS):
            with get_connection(DB_PATH) as conn:
                rows = fetch_history(conn, w.well_id, limit=8640)

            if rows:
                try:
                    latest_dt = datetime.fromisoformat(rows[0]["timestamp"])
                    since_dt = latest_dt - timedelta(hours=24)
                    rows = [r for r in rows if datetime.fromisoformat(r["timestamp"]) >= since_dt]
                except ValueError:
                    pass

            if not rows:
                result[2 * idx] = html.Span("Данных пока нет…", style={"color": "#95a5a6"})
                result[2 * idx + 1] = _empty_figure()
            else:
                last = rows[0]
                result[2 * idx] = _build_status(w.well_id, last["cluster"], last["deviation"])
                result[2 * idx + 1] = _build_figure(w.well_id, rows)

        return tuple(result)

    return app


def run_app(*, fast: bool = False) -> None:
    sleep_seconds = FAST_EMULATOR_SLEEP_SECONDS if fast else STREAM_SLEEP_SECONDS
    if fast:
        logger.info("Режим быстрого эмулятора: пауза %.2f с между строками", sleep_seconds)
    logger.info("Инициализация БД и запуск эмулятора")
    init_db(DB_PATH)
    run_emulator_background(sleep_seconds=sleep_seconds)
    logger.info("Dash запускается на http://127.0.0.1:8050")
    app = create_app()
    app.run(debug=False, use_reloader=False)


if __name__ == "__main__":
    run_app()
