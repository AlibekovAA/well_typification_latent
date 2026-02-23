from __future__ import annotations

from dash import dcc, html

from config import FEATURE_COLUMNS, FEATURE_LABELS, PUMP_TYPE_LABEL, WELL_CONFIGS


def _well_card(well_id: str, pump_type: str) -> html.Div:
    pump_label = PUMP_TYPE_LABEL.get(pump_type, pump_type.upper())
    return html.Div(
        [
            html.Div(
                f"Скважина {well_id} · {pump_label}",
                style={
                    "fontWeight": "700",
                    "fontSize": "16px",
                    "marginBottom": "10px",
                    "color": "#1a252f",
                    "letterSpacing": "0.02em",
                },
            ),
            html.Div(id=f"status-{well_id}", style={"marginBottom": "10px"}),
            dcc.Graph(
                id=f"graph-{well_id}",
                config={"displayModeBar": False},
                style={"height": "180px"},
            ),
        ],
        style={
            "flex": "1",
            "minWidth": "280px",
            "background": "#ffffff",
            "borderRadius": "14px",
            "padding": "18px",
            "boxShadow": "0 4px 14px rgba(0,0,0,0.06)",
            "border": "1px solid #e8ecef",
        },
    )


def _features_tab_content() -> html.Div:
    well_options = [
        {"label": f"Скважина {w.well_id} · {PUMP_TYPE_LABEL.get(w.pump_type, w.pump_type)}", "value": w.well_id}
        for w in WELL_CONFIGS
    ]
    default_well = WELL_CONFIGS[0].well_id
    graphs = [
        html.Div(
            [
                html.Div(
                    FEATURE_LABELS.get(col, col),
                    style={
                        "fontWeight": "600",
                        "fontSize": "13px",
                        "color": "#2c3e50",
                        "marginBottom": "4px",
                    },
                ),
                dcc.Graph(
                    id=f"feature-graph-{col}",
                    config={"displayModeBar": False},
                    style={"height": "120px"},
                ),
            ],
            style={
                "background": "#ffffff",
                "borderRadius": "12px",
                "padding": "12px",
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
                    html.Label("Скважина: ", style={"fontWeight": "600", "marginRight": "8px"}),
                    dcc.Dropdown(
                        id="well-selector",
                        options=well_options,
                        value=default_well,
                        clearable=False,
                        style={"minWidth": "200px"},
                    ),
                ],
                style={"marginBottom": "16px", "display": "flex", "alignItems": "center"},
            ),
            html.Div(
                graphs,
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(3, 1fr)",
                    "gap": "12px",
                },
            ),
        ],
    )


def layout_root() -> html.Div:
    cards = [_well_card(w.well_id, w.pump_type) for w in WELL_CONFIGS]
    return html.Div(
        [
            html.Div(
                [
                    html.H2(
                        "Мониторинг режимов скважин",
                        style={"margin": "0", "color": "#2c3e50", "fontWeight": "700"},
                    ),
                    html.Span(
                        "Обновление каждые 10 секунд",
                        style={"color": "#95a5a6", "fontSize": "13px"},
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
                        children=html.Div(
                            cards,
                            style={"display": "flex", "gap": "16px", "flexWrap": "wrap"},
                        ),
                    ),
                    dcc.Tab(
                        label="По признакам",
                        value="features",
                        children=html.Div(_features_tab_content(), style={"paddingTop": "8px"}),
                    ),
                ],
                style={"fontFamily": "inherit"},
            ),
            dcc.Interval(id="update-interval", interval=10_000, n_intervals=0),
        ],
        style={
            "padding": "28px",
            "fontFamily": "'Segoe UI', Arial, sans-serif",
            "background": "#f4f6f9",
            "height": "100vh",
            "overflow": "hidden",
            "boxSizing": "border-box",
        },
    )
