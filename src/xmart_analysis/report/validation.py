"""Figures of the validation documents (`xmart_analysis.validation`)."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

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
