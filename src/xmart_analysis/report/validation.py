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


def plot_station(doc, path, lang="en", station=None, weather=None, et0=None):
    from collections import defaultdict
    from xmart_analysis.validation import station as st

    station = station or st.load()
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(14, 4.4), dpi=130)
    days = [d for d in sorted(weather) if d in station]
    monthly = defaultdict(lambda: [0.0, 0.0])
    demand = defaultdict(lambda: [0.0, 0.0, 0])
    for d in days:
        monthly[(d.year, d.month)][0] += station[d]["rain_mm"]
        monthly[(d.year, d.month)][1] += weather[d]["PRECTOTCORR"]
        if station[d]["penman_et_mm"] is not None:
            demand[d.month][0] += station[d]["penman_et_mm"]
            demand[d.month][1] += et0[d]
            demand[d.month][2] += 1
    xs, ys = zip(*monthly.values())
    a.scatter(xs, ys, s=7, color="#2d6a8f", alpha=0.5)
    top = max(max(xs), max(ys))
    a.plot([0, top], [0, top], color=MUTED, linewidth=1, linestyle="--")
    a.set_xlabel(T("validation.station.axis_station", lang), fontsize=8.5)
    a.set_ylabel(T("validation.station.axis_power", lang), fontsize=8.5)
    a.set_title(f"{T('validation.station.monthly_rain', lang)} · r={doc['rain']['monthly_r']:.2f}", loc="left", fontsize=9.5, fontweight="bold")
    seasons = doc["seasons_dec_mar"][-5:]
    x = range(len(seasons))
    b.bar([i - 0.2 for i in x], [r["station_mm"] for r in seasons], 0.4, color="#2d6a8f", label=T("validation.station.axis_station", lang))
    b.bar([i + 0.2 for i in x], [r["power_mm"] for r in seasons], 0.4, color="#e0903f", label=T("validation.station.axis_power", lang))
    b.set_xticks(list(x), [r["season"] for r in seasons])
    b.legend(frameon=False, fontsize=8)
    b.set_title(T("validation.station.season_rain", lang), loc="left", fontsize=9.5, fontweight="bold")
    months = range(1, 13)
    c.plot(months, [demand[m][0] / demand[m][2] for m in months], color="#2d6a8f", label=T("validation.station.penman", lang))
    c.plot(months, [demand[m][1] / demand[m][2] for m in months], color="#e0903f", label=T("validation.station.hargreaves", lang))
    c.set_xticks(list(months))
    c.legend(frameon=False, fontsize=8)
    c.set_title(f"{T('validation.station.demand', lang)} · r={doc['evapotranspiration']['daily_r']:.2f}", loc="left", fontsize=9.5, fontweight="bold")
    for ax in (a, b, c):
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    fig.suptitle(T("validation.title.station", lang), x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.text(0.01, 0.01, T("validation.note.station", lang), fontsize=7.5, color=MUTED, style="italic")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def plot_ndvi(doc, path, lang="en"):
    fig, ax = plt.subplots(figsize=(7, 4.6), dpi=130)
    crop = next(iter(doc["correlations"]))
    seasons = doc["seasons"]
    highlight = set(doc["most_stressed_seasons"])
    for r in seasons:
        marked = r["season"] in highlight
        ax.scatter(r["ndvi_dec_mar"], r[f"{crop}_stress"], color="#8a3d14" if marked else "#2d6a8f", zorder=3)
        if marked:
            ax.annotate(r["season"], (r["ndvi_dec_mar"], r[f"{crop}_stress"]), textcoords="offset points", xytext=(5, 4), fontsize=7.5)
    ax.set_xlabel(T("validation.axis.ndvi", lang), fontsize=8.5)
    ax.set_ylabel(T("validation.axis.critical_stress", lang), fontsize=8.5)
    rho = doc["correlations"][crop]["spearman_ndvi_vs_minus_stress"]
    ax.set_title(f"{T('validation.title.ndvi', lang)}\nrho={rho:.2f}, n={len(seasons)}", loc="left", fontsize=9.5, fontweight="bold")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.text(0.01, 0.01, T("validation.note.ndvi", lang), fontsize=7.5, color=MUTED, style="italic")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, facecolor="white")
    plt.close(fig)
