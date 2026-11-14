"""Figures of the validation documents (`xmart_analysis.validation`)."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from xmart_analysis.engine import crops_uy  # noqa: E402
from xmart_analysis.engine.i18n import label  # noqa: E402

MUTED, COLORS = "#5b6770", {"model": "#2d6a8f", "smap_l4": "#bcd5e4", "rain_index": "#e0903f"}


def T(key, lang, **params):
    return label(key, **params)[lang]


def plot_smap(doc, path, lang="en"):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), dpi=130)
    scores = doc["periods"]["validation"]["scores"]
    for ax, metric, title in zip(axes, ("spearman", "anomaly_r"), ("validation.metric.spearman", "validation.metric.anomaly")):
        names = list(scores)
        values = [scores[n][metric] for n in names]
        ax.barh([T(f"validation.predictor.{n}", lang) for n in names], values, color=[COLORS[n] for n in names])
        for i, value in enumerate(values):
            ax.text(value + 0.01, i, f"{value:.2f}", va="center", fontsize=9)
        ax.set_xlim(0, 1)
        ax.set_title(T(title, lang), loc="left", fontsize=10, fontweight="bold")
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    fig.suptitle(f"{T('validation.title.smap', lang)} · n={doc['periods']['validation']['days']}", x=0.01, ha="left",
                 fontsize=11, fontweight="bold")
    fig.text(0.01, 0.01, T("validation.note.smap", lang), fontsize=7.5, color=MUTED, style="italic")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def plot_survey(doc, path, lang="en"):
    fig, (left, right) = plt.subplots(1, 2, figsize=(10, 4.2), dpi=130)
    seasons = doc["window"]
    left.bar(seasons, [doc["mentions"][s] for s in seasons], color="#8a3d14")
    left.set_ylabel(T("validation.axis.mentions", lang), fontsize=8.5)
    width = 0.38
    for i, (crop, entry) in enumerate(doc["crops"].items()):
        offset = (i - 0.5) * width
        right.bar([k + offset for k in range(len(seasons))], [entry["stress"][s] for s in seasons], width,
                  label=T(f"validation.crop.{crop}", lang), color=("#2d6a8f", "#e0903f")[i])
    right.set_xticks(range(len(seasons)), seasons)
    right.set_ylabel(T("validation.axis.critical_stress", lang), fontsize=8.5)
    right.set_ylim(0, 1)
    right.legend(frameon=False, fontsize=8)
    for ax in (left, right):
        ax.tick_params(axis="x", labelsize=8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    fig.suptitle(T("validation.title.survey", lang), x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.text(0.01, 0.01, T("validation.note.survey", lang, answered=doc["answered"], total=doc["respondents"]), fontsize=7.5, color=MUTED, style="italic")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def plot_ndvi(doc, path, lang="en"):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), dpi=130, sharex=True)
    low = set(doc["lowest_ndvi_seasons"])
    for ax, (crop, color) in zip(axes, (("soybean_1st", "#2d6a8f"), ("maize", "#e0903f"))):
        for r in doc["seasons"]:
            marked = r["season"] in low
            ax.scatter(r["ndvi_dec_mar"], r[f"{crop}_stress"], color="#8a3d14" if marked else color, zorder=3)
            if marked:
                ax.annotate(r["season"], (r["ndvi_dec_mar"], r[f"{crop}_stress"]), textcoords="offset points", xytext=(5, 4), fontsize=7.5)
        c = doc["correlations"][crop]
        ax.set_title(f"{T(f'validation.crop.{crop}', lang)} · rho={c['spearman_ndvi_vs_minus_stress']:.2f} · p={c['permutation_p']:.2f}",
                     loc="left", fontsize=9.5, fontweight="bold")
        ax.set_xlabel(T("validation.axis.ndvi", lang), fontsize=8.5)
        ax.set_ylabel(T("validation.axis.critical_stress", lang), fontsize=8.5)
        ax.set_ylim(0, 1)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    fig.suptitle(T("validation.title.ndvi", lang), x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.text(0.01, 0.01, T("validation.note.ndvi", lang), fontsize=7.5, color=MUTED, style="italic")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def plot_imerg(doc, path, lang="en"):
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.4), dpi=130)
    seasons = doc["seasons_dec_mar"]
    xs, ys = [r["imerg_mm"] for r in seasons], [r["power_mm"] for r in seasons]
    left.scatter(xs, ys, color="#2d6a8f", zorder=3)
    top = max(xs + ys)
    left.plot([0, top], [0, top], color=MUTED, linewidth=1, linestyle="--")
    for r in seasons:
        if r["season"] in doc["driest_seasons"]["imerg"] + doc["driest_seasons"]["power"]:
            left.annotate(r["season"], (r["imerg_mm"], r["power_mm"]), textcoords="offset points", xytext=(5, 4), fontsize=7.5)
    left.set_xlabel(T("validation.imerg.axis_imerg", lang), fontsize=8.5)
    left.set_ylabel(T("validation.imerg.axis_power", lang), fontsize=8.5)
    left.set_title(f"r={doc['rain']['season_dec_mar_r']:.2f} · n={len(seasons)}", loc="left", fontsize=9.5, fontweight="bold")
    last = seasons[-6:]
    x = range(len(last))
    right.bar([i - 0.2 for i in x], [r["imerg_mm"] for r in last], 0.4, color="#2d6a8f", label=T("validation.imerg.source_imerg", lang))
    right.bar([i + 0.2 for i in x], [r["power_mm"] for r in last], 0.4, color="#e0903f", label=T("validation.imerg.source_power", lang))
    right.set_xticks(list(x), [r["season"] for r in last], fontsize=8)
    right.legend(frameon=False, fontsize=8)
    right.set_title(T("validation.imerg.last_seasons", lang), loc="left", fontsize=9.5, fontweight="bold")
    for ax in (left, right):
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    fig.suptitle(T("validation.title.imerg", lang), x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.text(0.01, 0.01, T("validation.note.imerg", lang), fontsize=7.5, color=MUTED, style="italic")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def plot_rain_sensitivity(doc, path, lang="en"):
    fig, ax = plt.subplots(figsize=(6.4, 5), dpi=130)
    named = {r["season"] for r in doc["producer_seasons"]}
    for r in doc["crops"][doc["first_crop"]]["stress"]:
        marked = r["season"] in named
        ax.scatter(r["power"], r["imerg"], color="#8a3d14" if marked else "#2d6a8f", zorder=3)
        if marked:
            ax.annotate(r["season"], (r["power"], r["imerg"]), textcoords="offset points", xytext=(5, 4), fontsize=7.5)
    ax.plot([0, 1], [0, 1], color=MUTED, linewidth=1, linestyle="--")
    ax.set_xlabel(T("validation.rain_sensitivity.axis_power", lang), fontsize=8.5)
    ax.set_ylabel(T("validation.rain_sensitivity.axis_imerg", lang), fontsize=8.5)
    rho = doc["crops"][doc["first_crop"]]["spearman_between_sources"]
    ax.set_title(f"{T('validation.title.rain_sensitivity', lang)}\nrho={rho:.2f}", loc="left", fontsize=9.5, fontweight="bold")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.text(0.01, 0.01, T("validation.note.rain_sensitivity", lang), fontsize=7.2, color=MUTED, style="italic")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def plot_sowing(doc, path, lang="en"):
    crops = doc["crops"]
    fig, axes = plt.subplots(1, len(crops), figsize=(3.2 * len(crops), 4.2), dpi=130, sharey=True)
    colors = (("ok", "#9bc3a8"), ("tight", "#e0b45c"), ("out", "#b5533c"))
    for ax, (crop, entry) in zip(axes, crops.items()):
        labels = [r["sowing"] for r in entry["dates"]]
        bottom = [0] * len(labels)
        for name, color in colors:
            values = [r["counts"][name] for r in entry["dates"]]
            ax.bar(labels, values, bottom=bottom, color=color, label=T(f"sowing.drop.{name}", lang))
            bottom = [b + v for b, v in zip(bottom, values)]
        ax.set_title(T(crops_uy.name_label_key(crop), lang), loc="left", fontsize=9, fontweight="bold")
        ax.tick_params(axis="x", labelsize=7, rotation=45)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    axes[0].set_ylabel(T("sowing.axis.seasons", lang), fontsize=8.5)
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, loc="upper right", ncol=3, frameon=False, fontsize=8)
    fig.suptitle(T("sowing.title", lang), x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.text(0.01, 0.01, T("sowing.note", lang), fontsize=7.2, color=MUTED, style="italic")
    fig.tight_layout(rect=(0, 0.05, 1, 0.94))
    fig.savefig(path, facecolor="white")
    plt.close(fig)
