from __future__ import annotations

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.patches import FancyBboxPatch

OUT_DIR = Path("architecture_figures")
OUT_DIR.mkdir(exist_ok=True)

COLORS: dict[str, str] = {
    "well": "#D6EAF8",
    "stream": "#D5F5E3",
    "process": "#EAF2F8",
    "latent": "#E8DAEF",
    "storage": "#FCF3CF",
    "dashboard": "#FAD7A0",
    "alert": "#FADBD8",
    "edge": "#2C3E50",
    "arrow": "#34495E",
}


def add_box(
    ax: Axes,
    xy: tuple[float, float],
    w: float,
    h: float,
    text: str,
    fc: str,
    fontsize: int | float = 10,
    bold: bool = False,
    ec: str = "#2C3E50",
) -> dict[str, float]:
    x, y = xy
    p = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.05",
        linewidth=1.5,
        edgecolor=ec,
        facecolor=fc,
        zorder=3,
    )
    ax.add_patch(p)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        fontweight="bold" if bold else "normal",
        zorder=4,
        linespacing=1.35,
        multialignment="center",
    )
    return {"x": x, "y": y, "w": w, "h": h}


def add_section(
    ax: Axes,
    xy: tuple[float, float],
    w: float,
    h: float,
    label: str,
    fc: str = "#F8F9FA",
) -> None:
    x, y = xy
    p = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.2,
        edgecolor="#BDC3C7",
        facecolor=fc,
        zorder=1,
        alpha=0.75,
    )
    ax.add_patch(p)
    ax.text(
        x + w / 2,
        y + h - 0.2,
        label,
        ha="center",
        va="top",
        fontsize=9.5,
        color="#566573",
        fontweight="bold",
        zorder=2,
    )


def arrow(
    ax: Axes,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    color: str = "#34495E",
    lw: float = 1.8,
    style: str = "arc3,rad=0.0",
) -> None:
    ax.annotate(
        "",
        xy=(x1, y1),
        xytext=(x0, y0),
        arrowprops=dict(
            arrowstyle="->",
            lw=lw,
            color=color,
            shrinkA=0,
            shrinkB=0,
            connectionstyle=style,
        ),
        zorder=5,
    )


def label_arrow(
    ax: Axes,
    x: float,
    y: float,
    text: str,
    color: str = "#34495E",
    fontsize: float = 8.5,
) -> None:
    ax.text(
        x,
        y,
        text,
        ha="center",
        va="bottom",
        fontsize=fontsize,
        color=color,
        zorder=6,
        bbox=dict(
            boxstyle="round,pad=0.25",
            facecolor="white",
            alpha=0.9,
            edgecolor="none",
        ),
    )


def draw_system_architecture() -> None:
    fig, ax = plt.subplots(figsize=(24, 8.5))
    ax.set_xlim(0, 32)
    ax.set_ylim(0, 10)
    ax.axis("off")

    add_section(ax, (0.4, 1.0), 5.0, 8.2, "① ИСТОЧНИКИ ДАННЫХ", fc="#EBF5FB")
    add_section(ax, (5.9, 1.0), 4.4, 8.2, "② ЭМУЛЯТОР ПОТОКА", fc="#EAFAF1")
    add_section(ax, (10.8, 1.0), 11.8, 8.2, "③ АНАЛИТИЧЕСКИЙ КОНВЕЙЕР", fc="#F4ECF7")
    add_section(ax, (23.1, 1.0), 3.2, 8.2, "④ SQLITE", fc="#FEFBD8")
    add_section(ax, (26.8, 1.0), 4.8, 8.2, "⑤ DASH", fc="#FEF5E7")

    w_w, w_h = 4.2, 0.9
    w133 = add_box(
        ax,
        (0.8, 7.25),
        w_w,
        w_h,
        "Скважина 133\nЭЦН • .dat.txt",
        fc=COLORS["well"],
        bold=True,
    )
    w134 = add_box(
        ax,
        (0.8, 5.95),
        w_w,
        w_h,
        "Скважина 134\nШГН • .dat.txt",
        fc=COLORS["well"],
        bold=True,
    )
    w135 = add_box(
        ax,
        (0.8, 4.65),
        w_w,
        w_h,
        "Скважина 135\nШГН • .dat.txt",
        fc=COLORS["well"],
        bold=True,
    )

    add_box(
        ax,
        (1.0, 2.05),
        3.8,
        1.4,
        "Каждый файл:\nхронологические замеры\n9 физических параметров",
        fc="#F8FBFD",
        fontsize=10,
    )

    emulator = add_box(
        ax,
        (6.35, 2.40),
        3.50,
        5.40,
        "Эмулятор потока\n\n• читает .dat.txt построчно\n• имитирует real-time поток\n• 3 независимых фоновых потока",
        fc=COLORS["stream"],
        fontsize=10,
    )

    for w in (w133, w134, w135):
        y = w["y"] + w["h"] / 2
        arrow(ax, w["x"] + w["w"], y, emulator["x"], y, color="#27AE60", lw=1.7)

    label_arrow(ax, 5.55, 8.25, ".dat.txt строки", color="#27AE60")

    y0 = 4.15
    h = 1.9
    gap = 0.22
    x = 11.10
    w = 1.68

    p1 = add_box(
        ax,
        (x + 0 * (w + gap), y0),
        w,
        h,
        "Окно\n120 / 100\nстрок",
        fc=COLORS["process"],
        bold=True,
    )
    p2 = add_box(
        ax,
        (x + 1 * (w + gap), y0),
        w,
        h,
        "Нормали-\nзация",
        fc=COLORS["process"],
        bold=True,
    )
    p3 = add_box(
        ax,
        (x + 2 * (w + gap), y0),
        w,
        h,
        "Авто-\nэнкодер",
        fc=COLORS["latent"],
        bold=True,
    )
    p4 = add_box(
        ax,
        (x + 3 * (w + gap), y0),
        w,
        h,
        "Латентный\nвектор z",
        fc=COLORS["latent"],
        bold=True,
    )
    p5 = add_box(
        ax,
        (x + 4 * (w + gap), y0),
        w,
        h,
        "K-Means\nкластер",
        fc=COLORS["latent"],
        bold=True,
    )
    p6 = add_box(
        ax,
        (x + 5 * (w + gap), y0),
        w,
        h,
        "Отклонение\nи статус",
        fc=COLORS["alert"],
        bold=True,
    )

    add_box(
        ax,
        (11.35, 2.10),
        10.3,
        1.15,
        "Статус: норма / внимание / аномалия\n    Пороги: warn = p90, alert = p97",
        fc="#FBF6F6",
        fontsize=9.7,
    )

    ey = emulator["y"] + emulator["h"] / 2
    arrow(
        ax,
        emulator["x"] + emulator["w"],
        ey,
        p1["x"],
        p1["y"] + p1["h"] / 2,
        color="#2E86C1",
        lw=2.0,
    )
    for a, b in ((p1, p2), (p2, p3), (p3, p4), (p4, p5), (p5, p6)):
        arrow(
            ax,
            a["x"] + a["w"],
            a["y"] + a["h"] / 2,
            b["x"],
            b["y"] + b["h"] / 2,
            color=COLORS["arrow"],
            lw=2.0,
        )

    label_arrow(ax, 10.45, 5.55, "скользящее окно", color="#2E86C1")

    db = add_box(
        ax,
        (23.45, 3.60),
        2.50,
        3.00,
        "streaming.db\n\nЕдиное\nхранилище\nсостояний\n\ntimestamp\nwell\ncluster\nstatus\n9 признаков",
        fc=COLORS["storage"],
        fontsize=9.6,
        bold=True,
    )

    arrow(
        ax,
        p6["x"] + p6["w"],
        p6["y"] + p6["h"] / 2,
        db["x"],
        db["y"] + db["h"] / 2,
        color="#E67E22",
        lw=2.1,
    )
    label_arrow(ax, 22.75, 5.55, "результаты анализа", color="#E67E22")

    dash_head = add_box(
        ax,
        (27.10, 7.10),
        4.00,
        1.00,
        "Dash дашборд\n",
        fc=COLORS["dashboard"],
        fontsize=9.6,
        bold=True,
    )
    dash_modes = add_box(
        ax,
        (27.10, 4.90),
        4.00,
        1.90,
        "Мониторинг режимов работы\n\n"
        "• текущий кластер\n"
        "• цветной статус (норма /\n"
        "  внимание / аномалия)\n"
        "• временная шкала смены\n"
        "  режимов (барчарт)",
        fc="#FEF9E7",
        fontsize=9.2,
    )
    dash_feats = add_box(
        ax,
        (27.10, 2.20),
        4.00,
        2.40,
        "Анализ динамики\nтехнологических признаков\n\n"
        "• выбор скважины\n"
        "• 9 временных графиков:\n"
        "  us_center, us_periph,\n"
        "  gas_center, gas_periph,\n"
        "  temp, water_center,\n"
        "  water_periph,\n"
        "  gas_integral, water_integral",
        fc="#FEF9E7",
        fontsize=9.2,
    )

    arrow(
        ax,
        db["x"] + db["w"],
        db["y"] + db["h"] / 2,
        dash_head["x"],
        dash_head["y"] + dash_head["h"] / 2,
        color="#8E44AD",
        lw=2.2,
    )
    label_arrow(ax, 26.55, 5.55, "SQL чтение", color="#8E44AD")

    arrow(
        ax,
        dash_head["x"] + dash_head["w"] / 2,
        dash_head["y"],
        dash_modes["x"] + dash_modes["w"] / 2,
        dash_modes["y"] + dash_modes["h"],
        color="#8E44AD",
        lw=1.5,
    )
    arrow(
        ax,
        dash_modes["x"] + dash_modes["w"] / 2,
        dash_modes["y"],
        dash_feats["x"] + dash_feats["w"] / 2,
        dash_feats["y"] + dash_feats["h"],
        color="#8E44AD",
        lw=1.5,
    )

    legend_items = [
        mpatches.Patch(facecolor=COLORS["well"], edgecolor="#2C3E50", label="Источники данных"),
        mpatches.Patch(facecolor=COLORS["stream"], edgecolor="#2C3E50", label="Эмулятор потока"),
        mpatches.Patch(facecolor=COLORS["process"], edgecolor="#2C3E50", label="Предобработка"),
        mpatches.Patch(facecolor=COLORS["latent"], edgecolor="#2C3E50", label="Латентное пространство"),
        mpatches.Patch(facecolor=COLORS["alert"], edgecolor="#2C3E50", label="Статус и пороги"),
        mpatches.Patch(facecolor=COLORS["storage"], edgecolor="#2C3E50", label="SQLite"),
        mpatches.Patch(facecolor=COLORS["dashboard"], edgecolor="#2C3E50", label="Dash дашборд"),
    ]
    ax.legend(
        handles=legend_items,
        loc="lower center",
        fontsize=9,
        framealpha=0.95,
        ncol=4,
        bbox_to_anchor=(0.5, -0.02),
        edgecolor="#BDC3C7",
    )

    ax.set_title(
        "Высокоуровневая архитектура системы потокового мониторинга скважин",
        fontsize=16,
        fontweight="bold",
        pad=14,
    )

    fig.tight_layout()

    base_name = OUT_DIR / "system_architecture"
    fig.savefig(f"{base_name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(f"{base_name}.svg", bbox_inches="tight")
    plt.close(fig)
    print("Сохранено:", base_name.with_suffix(".{png,svg}"))


if __name__ == "__main__":
    draw_system_architecture()
