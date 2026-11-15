"""Draws the sketched data flow (sensor, rain, satellite, field history -> drops per crop) marking what exists today. Needs matplotlib.

Usage: python scripts/draw_architecture.py [out.png]
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

STATUS = {"ok": ("#d6ecd9", "#3f8f56", "Funciona hoy"), "part": ("#fbe9c2", "#c78a12", "Parcial"), "no": ("#eceff1", "#7b8794", "No existe todavia")}
BOXES = {  # key: (x, y, w, h, title, detail, status)
    "sensor": (0.3, 8.0, 3.4, 1.5, "Sensor", "Hoy: 1 lectura simulada\nFalta: serie de 1 año", "no"),
    "rain": (8.4, 8.0, 3.8, 1.5, "Lluvia ?", "POWER vs IMERG comparados\n(no se eligio una)", "part"),
    "year": (4.6, 6.1, 3.6, 1.3, "Dataset de 1 año", "del sensor (enviar 1 año)", "no"),
    "sat": (0.3, 4.2, 3.4, 1.5, "Satelite 10 años", "SMAP L4 2015-2026\ncalibra el suelo", "ok"),
    "fix": (4.6, 4.2, 3.6, 1.5, "Satelite corregido", "Falta: corregir SMAP con\nel sensor (hoy no se hace)", "no"),
    "hist": (0.3, 1.6, 3.4, 1.5, "Historico del campo", "zafras del productor: se\nmuestran y validan, no ajustan", "part"),
    "model": (4.6, 1.4, 4.2, 1.9, "Modelo de balance hidrico", "39 zafras de clima POWER\nFalta: ajustar con sensor", "ok"),
    "soy": (9.8, 2.6, 3.8, 1.3, "Soja", "gotas ok / tight / out", "ok"),
    "sor": (9.8, 0.9, 3.8, 1.3, "Sorgo", "gotas ok / tight / out", "ok"),
}
ARROWS = (("sensor", "year"), ("rain", "year"), ("year", "fix"), ("sat", "fix"), ("fix", "model"), ("hist", "model"), ("model", "soy"), ("model", "sor"))


def draw(path):
    fig, ax = plt.subplots(figsize=(14, 10), dpi=130)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10.4)
    ax.axis("off")
    for key, (x, y, w, h, title, detail, status) in BOXES.items():
        fill, edge, _ = STATUS[status]
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.15", facecolor=fill, edgecolor=edge,
                                    linewidth=1.8, linestyle="-" if status != "no" else "--"))
        ax.text(x + w / 2, y + h - 0.35, title, ha="center", va="center", fontsize=12, fontweight="bold", color="#1f2933")
        ax.text(x + w / 2, y + h / 2 - 0.2, detail, ha="center", va="center", fontsize=9.5, color="#3e4c59")

    def edge_point(key, toward):
        x, y, w, h = BOXES[key][:4]
        tx, ty = BOXES[toward][0] + BOXES[toward][2] / 2, BOXES[toward][1] + BOXES[toward][3] / 2
        cx, cy = x + w / 2, y + h / 2
        if abs(tx - cx) / w > abs(ty - cy) / h:
            return (x + w if tx > cx else x, cy)
        return (cx, y + h if ty > cy else y)

    for a, b in ARROWS:
        missing = "no" in (BOXES[a][6], BOXES[b][6]) or a == "hist"  # the field history does not feed the model
        ax.annotate("", xy=edge_point(b, a), xytext=edge_point(a, b),
                    arrowprops={"arrowstyle": "-|>", "color": "#7b8794" if missing else "#3f8f56", "lw": 1.8, "linestyle": "--" if missing else "-"})
    ax.text(0.3, 10.1, "Arquitectura dibujada vs lo que existe hoy", fontsize=15, fontweight="bold", color="#1f2933")
    for i, (fill, edge, text) in enumerate(STATUS.values()):
        ax.add_patch(FancyBboxPatch((0.3 + i * 3.4, 0.15), 0.4, 0.3, boxstyle="round,pad=0.02", facecolor=fill, edgecolor=edge, linewidth=1.6))
        ax.text(0.85 + i * 3.4, 0.3, text, va="center", fontsize=10)
    ax.text(13.7, 10.1, "Exploratorio: parametros de cultivo pendientes, lectura simulada", ha="right", va="center", fontsize=8.5, style="italic", color="#5b6770")
    fig.savefig(path, facecolor="white", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    draw(sys.argv[1] if len(sys.argv) > 1 else "reports/architecture.png")
