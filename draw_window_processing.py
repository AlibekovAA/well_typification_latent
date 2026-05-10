from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.patches import FancyBboxPatch

OUT_DIR = Path("architecture_figures")
OUT_DIR.mkdir(exist_ok=True)


COLORS: dict[str, str] = {
    "buffer": "#EAF2F8",
    "process": "#EAF2F8",
    "latent": "#E8DAEF",
    "result": "#FADBD8",
    "section": "#F8F9FA",
    "edge": "#2C3E50",
    "arrow": "#34495E",
    "accent": "#2E86C1",
    "note": "#FBF6F6",
}


def add_box(
    ax: Axes,
    xy: tuple[float, float],
    width: float,
    height: float,
    text: str,
    face_color: str,
    *,
    font_size: float = 11,
    bold: bool = False,
    edge_color: str = "#2C3E50",
) -> dict[str, float]:
    x, y = xy
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.02,rounding_size=0.06",
        linewidth=1.5,
        edgecolor=edge_color,
        facecolor=face_color,
        zorder=3,
    )
    ax.add_patch(patch)
    ax.text(
        x + width / 2,
        y + height / 2,
        text,
        ha="center",
        va="center",
        fontsize=font_size,
        fontweight="bold" if bold else "normal",
        linespacing=1.35,
        multialignment="center",
        zorder=4,
    )
    return {"x": x, "y": y, "w": width, "h": height}


def add_section(
    ax: Axes,
    xy: tuple[float, float],
    width: float,
    height: float,
    label: str,
    *,
    face_color: str = "#F8F9FA",
) -> None:
    x, y = xy
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.2,
        edgecolor="#BDC3C7",
        facecolor=face_color,
        alpha=0.85,
        zorder=1,
    )
    ax.add_patch(patch)
    ax.text(
        x + width / 2,
        y + height - 0.25,
        label,
        ha="center",
        va="top",
        fontsize=10,
        color="#566573",
        fontweight="bold",
        zorder=2,
    )


def add_arrow(
    ax: Axes,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    *,
    color: str = "#34495E",
    line_width: float = 2.0,
) -> None:
    ax.annotate(
        "",
        xy=(end_x, end_y),
        xytext=(start_x, start_y),
        arrowprops={
            "arrowstyle": "->",
            "lw": line_width,
            "color": color,
            "shrinkA": 0,
            "shrinkB": 0,
            "connectionstyle": "arc3,rad=0.0",
        },
        zorder=5,
    )


def add_label(
    ax: Axes,
    x: float,
    y: float,
    text: str,
    *,
    color: str = "#34495E",
    font_size: float = 9,
) -> None:
    ax.text(
        x,
        y,
        text,
        ha="center",
        va="bottom",
        fontsize=font_size,
        color=color,
        zorder=6,
        bbox={
            "boxstyle": "round,pad=0.25",
            "facecolor": "white",
            "alpha": 0.95,
            "edgecolor": "none",
        },
    )


def draw_window_processing_pipeline() -> None:
    fig, ax = plt.subplots(figsize=(18, 6.5))
    ax.set_xlim(0, 22)
    ax.set_ylim(0, 8)
    ax.axis("off")

    add_section(
        ax,
        (0.4, 0.8),
        21.2,
        6.7,
        "ОБРАБОТКА СКОЛЬЗЯЩЕГО ОКНА",
        face_color=COLORS["section"],
    )

    y = 3.2
    height = 1.8
    gap = 0.28
    width = 2.45
    start_x = 1.1

    box_buffer = add_box(
        ax,
        (start_x, y),
        width,
        height,
        "Буфер\n(deque)\n120 / 100 строк",
        COLORS["buffer"],
        bold=True,
    )
    box_scaler = add_box(
        ax,
        (start_x + 1 * (width + gap), y),
        width,
        height,
        "StandardScaler\n\nНормализация\nпризнаков",
        COLORS["process"],
        bold=True,
    )
    box_encoder = add_box(
        ax,
        (start_x + 2 * (width + gap), y),
        width,
        height,
        "Автоэнкодер\n\nencode(x)",
        COLORS["latent"],
        bold=True,
    )
    box_latent = add_box(
        ax,
        (start_x + 3 * (width + gap), y),
        width,
        height,
        "Латентный\nвектор z",
        COLORS["latent"],
        bold=True,
    )
    box_kmeans = add_box(
        ax,
        (start_x + 4 * (width + gap), y),
        width,
        height,
        "K-Means\n\npredict(z)",
        COLORS["latent"],
        bold=True,
    )
    box_result = add_box(
        ax,
        (start_x + 5 * (width + gap), y),
        width,
        height,
        "Кластер\n+\nDeviation",
        COLORS["result"],
        bold=True,
    )

    boxes = [
        box_buffer,
        box_scaler,
        box_encoder,
        box_latent,
        box_kmeans,
        box_result,
    ]

    for left_box, right_box in zip(boxes, boxes[1:], strict=False):
        add_arrow(
            ax,
            left_box["x"] + left_box["w"],
            left_box["y"] + left_box["h"] / 2,
            right_box["x"],
            right_box["y"] + right_box["h"] / 2,
            color=COLORS["arrow"],
        )

    add_label(ax, 2.3, 5.45, "каждая новая строка\nсдвигает окно на 1", color=COLORS["accent"])
    add_label(ax, 8.45, 5.45, "вход: окно признаков", color=COLORS["accent"])
    add_label(ax, 14.15, 5.45, "поиск ближайшего\nтипового режима", color="#8E44AD")

    add_box(
        ax,
        (2.0, 1.45),
        8.0,
        1.0,
        "Для ЭЦН используется окно 120 строк, для ШГН — 100 строк",
        COLORS["note"],
        font_size=10,
    )
    add_box(
        ax,
        (10.35, 1.45),
        6.0,
        1.0,
        "Deviation = расстояние от z до центра найденного кластера",
        COLORS["note"],
        font_size=10,
    )
    add_box(
        ax,
        (16.65, 1.45),
        3.6,
        1.0,
        "Результат:\nрежим + степень отклонения",
        COLORS["note"],
        font_size=10,
    )

    ax.set_title(
        "Схема обработки скользящего окна в прототипе системы потокового мониторинга",
        fontsize=15,
        fontweight="bold",
        pad=14,
    )

    fig.tight_layout()

    base_path = OUT_DIR / "window_processing_pipeline"
    fig.savefig(f"{base_path}.png", dpi=300, bbox_inches="tight")
    fig.savefig(f"{base_path}.svg", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    draw_window_processing_pipeline()
