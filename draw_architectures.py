from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.patches import FancyBboxPatch

OUT_DIR = Path("architecture_figures")
OUT_DIR.mkdir(exist_ok=True)


Box = dict[str, float]


COLORS = {
    "input": "#F4F6F6",
    "encoder": "#D6EAF8",
    "latent": "#E8DAEF",
    "norm": "#EAF2F8",
    "bridge": "#D5F5E3",
    "decoder_input": "#FCF3CF",
    "decoder": "#FAD7A0",
    "output": "#F4F6F6",
    "edge": "#2C3E50",
    "arrow": "#34495E",
}


def add_box(
    ax: Axes,
    xy: tuple[float, float],
    width: float,
    height: float,
    text: str,
    *,
    fc: str,
    ec: str = COLORS["edge"],
    fontsize: int = 11,
) -> Box:
    x, y = xy
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.02,rounding_size=0.03",
        linewidth=1.5,
        edgecolor=ec,
        facecolor=fc,
    )
    ax.add_patch(patch)
    ax.text(x + width / 2, y + height / 2, text, ha="center", va="center", fontsize=fontsize)
    return {"x": x, "y": y, "w": width, "h": height}


def right_center(box: Box) -> tuple[float, float]:
    return (box["x"] + box["w"], box["y"] + box["h"] / 2)


def left_center(box: Box) -> tuple[float, float]:
    return (box["x"], box["y"] + box["h"] / 2)


def top_center(box: Box) -> tuple[float, float]:
    return (box["x"] + box["w"] / 2, box["y"] + box["h"])


def bottom_center(box: Box) -> tuple[float, float]:
    return (box["x"] + box["w"] / 2, box["y"])


def add_arrow(ax: Axes, start: tuple[float, float], end: tuple[float, float]) -> None:
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={
            "arrowstyle": "->",
            "lw": 1.8,
            "color": COLORS["arrow"],
            "shrinkA": 0,
            "shrinkB": 0,
        },
    )


def init_canvas(
    figsize: tuple[float, float],
    xlim: tuple[float, float],
    ylim: tuple[float, float],
) -> tuple[Any, Axes]:
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")
    return fig, ax


def save_figure(fig: Any, filename: str) -> None:
    fig.tight_layout()
    fig.savefig(OUT_DIR / filename, dpi=300, bbox_inches="tight")
    plt.close(fig)


def draw_gru_autoencoder() -> None:
    fig, ax = init_canvas(figsize=(17.0, 8.5), xlim=(0, 22.0), ylim=(0.0, 9.5))

    b1 = add_box(ax, (0.6, 3.8), 2.9, 1.0, r"$X \in \mathbb{R}^{T \times D}$", fc=COLORS["input"])
    b2 = add_box(ax, (4.1, 3.8), 3.7, 1.0, "Bidirectional GRU\nEncoder", fc=COLORS["encoder"])
    b3 = add_box(ax, (8.4, 3.8), 2.2, 1.0, "Attention\nPooling", fc=COLORS["encoder"])
    b4 = add_box(ax, (11.2, 3.8), 2.2, 1.0, "Fully Connected\n(Encoder)", fc=COLORS["latent"], fontsize=10)
    b5 = add_box(ax, (14.0, 3.8), 2.3, 1.0, r"Latent Vector $z$", fc=COLORS["latent"])

    b6 = add_box(
        ax,
        (13.7, 6.1),
        3.6,
        1.15,
        r"FC $\rightarrow h_0$",
        fc=COLORS["bridge"],
        fontsize=11,
    )
    b7 = add_box(
        ax, (13.7, 1.4), 3.6, 1.0, r"$X_{\mathrm{shifted}}$ (Teacher Forcing)", fc=COLORS["decoder_input"], fontsize=9
    )
    b8 = add_box(ax, (18.0, 3.8), 2.5, 1.0, "GRU\nDecoder", fc=COLORS["decoder"])
    b9 = add_box(ax, (18.0, 6.0), 2.5, 1.0, "Fully Connected\n(Output)", fc=COLORS["decoder"], fontsize=10)
    b10 = add_box(ax, (17.8, 8.0), 2.9, 1.0, r"$\hat{X} \in \mathbb{R}^{T \times D}$", fc=COLORS["output"])

    add_arrow(ax, right_center(b1), left_center(b2))
    add_arrow(ax, right_center(b2), left_center(b3))
    add_arrow(ax, right_center(b3), left_center(b4))
    add_arrow(ax, right_center(b4), left_center(b5))

    add_arrow(ax, top_center(b5), bottom_center(b6))
    add_arrow(ax, right_center(b6), top_center(b8))
    add_arrow(ax, top_center(b7), bottom_center(b8))
    add_arrow(ax, top_center(b8), bottom_center(b9))
    add_arrow(ax, top_center(b9), bottom_center(b10))

    ax.set_title(
        "Архитектура GRU-автоэнкодера с механизмом внимания и декодером teacher forcing",
        fontsize=15,
        fontweight="bold",
    )
    save_figure(fig, "gru_autoencoder.png")


def draw_tcn_autoencoder() -> None:
    fig, ax = init_canvas(figsize=(18.0, 8.5), xlim=(0, 28.0), ylim=(0.0, 10.8))

    b1 = add_box(ax, (0.7, 4.8), 3.1, 1.0, r"$X \in \mathbb{R}^{T \times D}$", fc=COLORS["input"])
    b2 = add_box(
        ax,
        (4.4, 4.8),
        5.2,
        1.0,
        "TCN Encoder\n(Causal Dilated Residual Blocks\n+ Batch Normalization)",
        fc=COLORS["encoder"],
        fontsize=9,
    )
    b3 = add_box(ax, (10.2, 4.8), 2.5, 1.0, "Attention\nPooling", fc=COLORS["encoder"])
    b4 = add_box(ax, (13.3, 4.8), 2.4, 1.0, "Fully Connected\n(Bottleneck)", fc=COLORS["latent"], fontsize=10)
    b5 = add_box(ax, (16.3, 4.8), 2.5, 1.0, r"Latent Vector $z$", fc=COLORS["latent"])

    b6 = add_box(ax, (19.6, 8.5), 3.3, 1.0, "FC + GELU", fc=COLORS["bridge"], fontsize=11)
    b7 = add_box(ax, (19.6, 7.0), 3.3, 1.0, "Broadcast\n(Time-wise)", fc=COLORS["bridge"], fontsize=10)

    b8 = add_box(
        ax, (19.6, 1.3), 3.3, 1.0, r"$X_{\mathrm{shifted}}$ (Teacher Forcing)", fc=COLORS["decoder_input"], fontsize=9
    )
    b9 = add_box(ax, (19.6, 2.8), 3.3, 1.0, r"Conv1d $1 \times 1$", fc=COLORS["bridge"], fontsize=10)
    b10 = add_box(ax, (19.6, 4.3), 3.3, 1.0, r"$h + x_{\mathrm{proj}}$", fc=COLORS["bridge"], fontsize=11)

    b11 = add_box(
        ax,
        (23.7, 4.3),
        3.2,
        1.0,
        "TCN Decoder\n(Residual Blocks\n+ Batch Normalization)",
        fc=COLORS["decoder"],
        fontsize=9,
    )
    b12 = add_box(ax, (23.7, 6.0), 3.2, 1.0, r"Conv1d $1 \times 1$", fc=COLORS["decoder"], fontsize=10)
    b13 = add_box(ax, (23.7, 8.0), 3.2, 1.0, r"$\hat{X} \in \mathbb{R}^{T \times D}$", fc=COLORS["output"])

    add_arrow(ax, right_center(b1), left_center(b2))
    add_arrow(ax, right_center(b2), left_center(b3))
    add_arrow(ax, right_center(b3), left_center(b4))
    add_arrow(ax, right_center(b4), left_center(b5))

    add_arrow(ax, top_center(b5), bottom_center(b6))
    add_arrow(ax, bottom_center(b6), top_center(b7))
    add_arrow(ax, bottom_center(b7), top_center(b10))

    add_arrow(ax, top_center(b8), bottom_center(b9))
    add_arrow(ax, top_center(b9), bottom_center(b10))

    add_arrow(ax, right_center(b10), left_center(b11))
    add_arrow(ax, top_center(b11), bottom_center(b12))
    add_arrow(ax, top_center(b12), bottom_center(b13))

    ax.set_title(
        "Архитектура TCN-автоэнкодера с Batch Normalization и условным декодированием",
        fontsize=15,
        fontweight="bold",
    )
    save_figure(fig, "tcn_autoencoder.png")


def draw_hybrid_autoencoder() -> None:
    fig, ax = init_canvas(figsize=(17.0, 8.5), xlim=(0, 22.5), ylim=(0.0, 8.8))

    b1 = add_box(ax, (0.6, 3.0), 2.9, 1.0, r"$X \in \mathbb{R}^{T \times D}$", fc=COLORS["input"])
    b2 = add_box(
        ax,
        (4.1, 3.0),
        4.4,
        1.0,
        "TCN Encoder\n(Residual Blocks\n+ Batch Normalization)",
        fc=COLORS["encoder"],
        fontsize=9,
    )
    b3 = add_box(ax, (9.0, 3.0), 2.2, 1.0, "Attention\nPooling", fc=COLORS["encoder"])
    b4 = add_box(ax, (11.8, 3.0), 2.2, 1.0, "Fully Connected\n(Bottleneck)", fc=COLORS["latent"], fontsize=10)
    b5 = add_box(ax, (14.6, 3.0), 2.1, 1.0, r"Latent Vector $z$", fc=COLORS["latent"])

    b6 = add_box(
        ax,
        (14.3, 5.3),
        3.4,
        1.05,
        r"FC $\rightarrow h_0$",
        fc=COLORS["bridge"],
        fontsize=11,
    )
    b7 = add_box(
        ax, (14.3, 1.0), 3.4, 1.0, r"$X_{\mathrm{shifted}}$ (Teacher Forcing)", fc=COLORS["decoder_input"], fontsize=9
    )
    b8 = add_box(ax, (18.3, 3.0), 2.4, 1.0, "GRU\nDecoder", fc=COLORS["decoder"])
    b9 = add_box(ax, (18.3, 5.4), 2.4, 1.0, "Fully Connected\n(Output)", fc=COLORS["decoder"], fontsize=10)
    b10 = add_box(ax, (18.1, 7.4), 2.8, 0.95, r"$\hat{X} \in \mathbb{R}^{T \times D}$", fc=COLORS["output"])

    add_arrow(ax, right_center(b1), left_center(b2))
    add_arrow(ax, right_center(b2), left_center(b3))
    add_arrow(ax, right_center(b3), left_center(b4))
    add_arrow(ax, right_center(b4), left_center(b5))

    add_arrow(ax, top_center(b5), bottom_center(b6))
    add_arrow(ax, right_center(b6), top_center(b8))
    add_arrow(ax, top_center(b7), bottom_center(b8))
    add_arrow(ax, top_center(b8), bottom_center(b9))
    add_arrow(ax, top_center(b9), bottom_center(b10))

    ax.set_title(
        "Архитектура гибридного TCN-GRU автоэнкодера",
        fontsize=15,
        fontweight="bold",
    )
    save_figure(fig, "hybrid_autoencoder.png")


def main() -> None:
    draw_gru_autoencoder()
    draw_tcn_autoencoder()
    draw_hybrid_autoencoder()
    print("Рисунки сохранены в папке architecture_figures")


if __name__ == "__main__":
    main()
