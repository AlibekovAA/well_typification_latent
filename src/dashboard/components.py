from __future__ import annotations

from dash import dcc, html

from config import FEATURE_COLUMNS, FEATURE_LABELS, FEATURE_UNITS, PUMP_TYPE_LABEL, WELL_CONFIGS

_CARD_STYLE: dict[str, str] = {
    "flex": "1",
    "minWidth": "300px",
    "background": "#ffffff",
    "borderRadius": "16px",
    "padding": "20px",
    "boxShadow": "0 2px 12px rgba(0,0,0,0.07)",
    "border": "1px solid #e8ecef",
    "display": "flex",
    "flexDirection": "column",
    "gap": "4px",
}


def _well_card(well_id: str, pump_type: str) -> html.Div:
    pump_label = PUMP_TYPE_LABEL.get(pump_type, pump_type.upper())
    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        f"Скважина {well_id}",
                        style={"fontWeight": "700", "fontSize": "15px", "color": "#1a252f"},
                    ),
                    html.Span(
                        pump_label,
                        style={
                            "fontSize": "12px",
                            "fontWeight": "600",
                            "color": "#7f8c8d",
                            "background": "#f0f3f5",
                            "borderRadius": "5px",
                            "padding": "2px 8px",
                            "marginLeft": "8px",
                        },
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "marginBottom": "10px"},
            ),
            html.Div(id=f"status-{well_id}"),
            dcc.Graph(
                id=f"graph-{well_id}",
                config={"displayModeBar": False},
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
                        "fontSize": "12px",
                        "color": "#5d6d7e",
                        "marginBottom": "2px",
                        "textTransform": "uppercase",
                        "letterSpacing": "0.04em",
                    },
                ),
                dcc.Graph(
                    id=f"feature-graph-{col}",
                    config={"displayModeBar": False},
                ),
            ],
            style={
                "background": "#ffffff",
                "borderRadius": "12px",
                "padding": "14px",
                "boxShadow": "0 2px 8px rgba(0,0,0,0.06)",
                "border": "1px solid #e8ecef",
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
                    "marginBottom": "16px",
                    "display": "flex",
                    "alignItems": "center",
                    "background": "#ffffff",
                    "borderRadius": "10px",
                    "padding": "10px 16px",
                    "boxShadow": "0 2px 8px rgba(0,0,0,0.05)",
                    "border": "1px solid #e8ecef",
                    "width": "fit-content",
                },
            ),
            html.Div(
                graphs,
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(3, 1fr)",
                    "gap": "14px",
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
                                    "color": "#1a252f",
                                    "fontWeight": "700",
                                    "fontSize": "22px",
                                },
                            ),
                            html.Span(
                                f"Обновление каждые {update_interval_seconds} секунд",
                                style={"color": "#95a5a6", "fontSize": "12px"},
                            ),
                        ]
                    ),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "marginBottom": "20px",
                },
            ),
            dcc.Tabs(
                id="dashboard-tabs",
                value="modes",
                children=[
                    dcc.Tab(
                        label="По режимам",
                        value="modes",
                        children=html.Div(
                            cards,
                            style={
                                "display": "flex",
                                "gap": "16px",
                                "flexWrap": "wrap",
                                "paddingTop": "16px",
                            },
                        ),
                    ),
                    dcc.Tab(
                        label="По признакам",
                        value="features",
                        children=html.Div(
                            _features_tab_content(),
                            style={"paddingTop": "16px"},
                        ),
                    ),
                ],
                style={"fontFamily": "inherit"},
            ),
        ],
        style={
            "padding": "28px",
            "fontFamily": "'Segoe UI', Arial, sans-serif",
            "background": "#f0f3f7",
            "minHeight": "100vh",
            "boxSizing": "border-box",
        },
    )
