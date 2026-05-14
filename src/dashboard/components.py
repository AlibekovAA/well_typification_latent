from __future__ import annotations

from dash import dcc, html

from config import (
    DASH_MODE_CHART_HEIGHT_PX,
    FEATURE_COLUMNS,
    FEATURE_LABELS,
    FEATURE_UNITS,
    PUMP_TYPE_LABEL,
    WELL_CONFIGS,
)

_CARD_STYLE: dict[str, str] = {
    "flex": "1",
    "minWidth": "320px",
    "background": "#ffffff",
    "borderRadius": "18px",
    "padding": "18px 18px 14px 18px",
    "boxShadow": "0 8px 28px rgba(15,23,42,0.06)",
    "border": "1px solid #e2e8f0",
    "display": "flex",
    "flexDirection": "column",
    "gap": "6px",
}


def _well_card(well_id: str, pump_type: str) -> html.Div:
    pump_label = PUMP_TYPE_LABEL.get(pump_type, pump_type.upper())
    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        f"Скважина {well_id}",
                        style={"fontWeight": "700", "fontSize": "23px", "color": "#0f172a", "lineHeight": "1.1"},
                    ),
                    html.Span(
                        pump_label,
                        style={
                            "fontSize": "13px",
                            "fontWeight": "600",
                            "color": "#64748b",
                            "background": "#f1f5f9",
                            "borderRadius": "999px",
                            "padding": "3px 10px",
                            "marginLeft": "8px",
                        },
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
            ),
            html.Div(id=f"status-{well_id}"),
            dcc.Graph(
                id=f"graph-{well_id}",
                config={"displayModeBar": False, "showTips": False},
                style={
                    "height": f"{DASH_MODE_CHART_HEIGHT_PX}px",
                    "minHeight": f"{DASH_MODE_CHART_HEIGHT_PX}px",
                },
            ),
        ],
        style=_CARD_STYLE,
    )


def _features_tab_content() -> html.Div:
    well_options = [
        {
            "label": f"Скважина {w.well_id} · {PUMP_TYPE_LABEL.get(w.pump_type, w.pump_type)}",
            "value": w.well_id,
        }
        for w in WELL_CONFIGS
    ]
    default_well = WELL_CONFIGS[0].well_id
    graphs = [
        html.Div(
            [
                html.Div(
                    f"{FEATURE_LABELS.get(col, col)} ({FEATURE_UNITS.get(col, '')})",
                    style={
                        "fontWeight": "600",
                        "fontSize": "11px",
                        "color": "#64748b",
                        "marginBottom": "4px",
                        "textTransform": "uppercase",
                        "letterSpacing": "0.06em",
                    },
                ),
                dcc.Graph(
                    id=f"feature-graph-{col}",
                    config={"displayModeBar": False, "responsive": True, "showTips": False},
                    style={
                        "height": "220px",
                        "minHeight": "220px",
                    },
                ),
            ],
            style={
                "background": "#ffffff",
                "borderRadius": "14px",
                "padding": "10px 12px 6px 12px",
                "boxShadow": "0 4px 18px rgba(15,23,42,0.06)",
                "border": "1px solid #e2e8f0",
                "display": "flex",
                "flexDirection": "column",
                "minHeight": 0,
            },
        )
        for col in FEATURE_COLUMNS
    ]
    return html.Div(
        [
            html.Div(
                [
                    html.Label(
                        "Скважина",
                        style={
                            "fontWeight": "600",
                            "fontSize": "13px",
                            "color": "#2c3e50",
                            "marginRight": "10px",
                        },
                    ),
                    dcc.Dropdown(
                        id="well-selector",
                        options=well_options,
                        value=default_well,
                        clearable=False,
                        style={"minWidth": "220px", "fontSize": "13px"},
                    ),
                ],
                style={
                    "marginBottom": "12px",
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "10px",
                    "background": "#ffffff",
                    "borderRadius": "14px",
                    "padding": "10px 14px",
                    "boxShadow": "0 4px 18px rgba(15,23,42,0.05)",
                    "border": "1px solid #e2e8f0",
                    "width": "fit-content",
                    "flexWrap": "wrap",
                },
            ),
            html.Div(
                graphs,
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fit, minmax(320px, 1fr))",
                    "gridAutoRows": "minmax(220px, auto)",
                    "gap": "12px",
                    "height": "auto",
                    "minHeight": "560px",
                },
            ),
        ],
    )


def layout_root(*, update_interval_seconds: int) -> html.Div:
    cards = [_well_card(w.well_id, w.pump_type) for w in WELL_CONFIGS]
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H2(
                                "Мониторинг скважин",
                                style={
                                    "margin": "0 0 2px 0",
                                    "color": "#0f172a",
                                    "fontWeight": "700",
                                    "fontSize": "26px",
                                },
                            ),
                            html.Span(
                                f"Обновление каждые {update_interval_seconds} секунд",
                                style={"color": "#64748b", "fontSize": "13px"},
                            ),
                        ]
                    ),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "marginBottom": "16px",
                },
            ),
            dcc.Tabs(
                id="dashboard-tabs",
                value="modes",
                children=[
                    dcc.Tab(
                        label="По режимам",
                        value="modes",
                        className="dash-tab",
                        selected_className="dash-tab--selected",
                        children=html.Div(
                            cards,
                            style={
                                "display": "flex",
                                "gap": "16px",
                                "flexWrap": "wrap",
                                "paddingTop": "14px",
                            },
                        ),
                    ),
                    dcc.Tab(
                        label="По признакам",
                        value="features",
                        className="dash-tab",
                        selected_className="dash-tab--selected",
                        children=html.Div(
                            _features_tab_content(),
                            style={"paddingTop": "14px"},
                        ),
                    ),
                ],
                style={"fontFamily": "inherit"},
                className="dash-tabs",
            ),
        ],
        className="dash-root",
        style={
            "padding": "20px",
            "fontFamily": "'Segoe UI', Arial, sans-serif",
            "background": "#eef3f9",
            "minHeight": "100vh",
            "boxSizing": "border-box",
        },
    )
