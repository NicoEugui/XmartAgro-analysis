"""Figures of the validation documents (`xmart_analysis.validation`)."""

import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from xmart_analysis.engine import crops_uy  # noqa: E402
from xmart_analysis.report import scenario_runs  # noqa: E402
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
        labels = [scenario_runs.day_label(r["sowing"], lang) for r in entry["dates"]]
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


def plot_sensor(doc, path, lang="en"):
    fig, (ax, bars) = plt.subplots(1, 2, figsize=(11, 4.4), dpi=130, gridspec_kw={"width_ratios": [1.7, 1]})
    days = [datetime.date.fromisoformat(r["date"]) for r in doc["series"]]
    column = lambda name: [r[name] for r in doc["series"]]  # noqa: E731
    ax.scatter(days, column("sensor"), s=3, color="#c9ced2", zorder=1, label=T("sensor.series.readings", lang))
    for name, color, width in (("truth", "#2f2f2f", 1.4), ("open_loop", "#e0903f", 1.2), ("with_sensor", "#2d6a8f", 1.4)):
        ax.plot(days, column(name), color=color, linewidth=width, zorder=2, label=T(f"sensor.series.{name}", lang))
    ax.set_ylabel(T("sensor.axis.moisture", lang), fontsize=8.5)
    ax.tick_params(labelsize=8)
    ax.legend(frameon=False, fontsize=7.5, ncol=2, loc="upper center", bbox_to_anchor=(0.5, 1.0))
    runs = [("open_loop", doc["open_loop"], T("sensor.run.open_loop", lang))] + [
        (f"every_{r['every_days']}", r, T("sensor.run.every", lang, days=r["every_days"])) for r in doc["with_sensor"]]
    x = range(len(runs))
    for shift, key, color, name in ((-0.2, "rmse", "#2d6a8f", T("sensor.bar.year", lang)),
                                    (0.2, "first_days_rmse", "#bcd5e4", T("sensor.bar.start", lang, days=doc["start_window_days"]))):
        heights = [entry[key] for _, entry, _ in runs]
        bars.bar([i + shift for i in x], heights, width=0.38, color=color, label=name)
        for i, value in zip(x, heights):
            bars.text(i + shift, value, f"{value:.3f}", ha="center", va="bottom", fontsize=7)
    bars.set_xticks(list(x), [label for _, _, label in runs], fontsize=7.5, rotation=20)
    bars.set_ylabel(T("sensor.axis.rmse", lang), fontsize=8.5)
    bars.legend(frameon=False, fontsize=7.5)
    for axis in (ax, bars):
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
    fig.suptitle(f"{T('sensor.title', lang)} · {doc['period'][0]} / {doc['period'][1]}", x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.text(0.01, 0.01, T("sensor.note", lang), fontsize=7.2, color=MUTED, style="italic")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def _grouped(ax, categories, series, labels=True, value_format="{:.3f}", size=7):
    """Bars side by side: `series` is {label: (values, color)}, one value per category."""
    width = 0.8 / len(series)
    for k, (name, (values, color)) in enumerate(series.items()):
        xs = [i + (k - (len(series) - 1) / 2) * width for i in range(len(categories))]
        ax.bar(xs, values, width * 0.95, color=color, label=name)
        if labels:
            for x, value in zip(xs, values):
                ax.text(x, value, value_format.format(value), ha="center", va="bottom" if value >= 0 else "top", fontsize=size)
    ax.set_xticks(range(len(categories)), categories, fontsize=7.5)
    ax.tick_params(axis="y", labelsize=8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def plot_rain_decision(doc, path, lang="en"):
    imerg, sens = doc["imerg"], doc["sensitivity"]
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), dpi=130)
    (monthly, stress), (classes, rotations) = axes
    power_c, imerg_c = "#e0903f", "#2d6a8f"
    cycle = imerg["monthly_mean_mm"]
    _grouped(monthly, [str(r["month"]) for r in cycle], {T("validation.imerg.source_power", lang): ([r["power"] for r in cycle], power_c),
                                                          T("validation.imerg.source_imerg", lang): ([r["imerg"] for r in cycle], imerg_c)}, labels=False)
    monthly.set_title(T("rain_decision.monthly", lang), loc="left", fontsize=9.5, fontweight="bold")
    monthly.set_xlabel(T("rain_decision.month", lang), fontsize=8)
    monthly.legend(frameon=False, fontsize=8)
    rows = sens["crops"][sens["first_crop"]]["stress"]
    for i, r in enumerate(rows):
        stress.plot([i, i], [r["power"], r["imerg"]], color="#c9ced2", linewidth=1, zorder=1)
    stress.scatter(range(len(rows)), [r["power"] for r in rows], color=power_c, s=22, zorder=3)
    stress.scatter(range(len(rows)), [r["imerg"] for r in rows], color=imerg_c, s=22, zorder=3)
    stress.set_xticks(range(0, len(rows), 3), [rows[i]["season"] for i in range(0, len(rows), 3)], fontsize=7, rotation=45)
    stress.set_ylabel(T("rain_decision.stress_axis", lang), fontsize=8)
    stress.set_title(T("rain_decision.stress", lang), loc="left", fontsize=9.5, fontweight="bold")
    crops = list(sens["crops"])
    labels = [f"{T(f'validation.crop.{c}', lang).replace(' (', chr(10) + '(')}\n{name}" for c in crops for name in ("POWER", "IMERG")]
    counts = [sens["crops"][c]["class_counts"][source] for c in crops for source in ("power", "imerg")]
    bottom = [0] * len(counts)
    for name, color in (("ok", "#9bc3a8"), ("tight", "#e0b45c"), ("out", "#b5533c")):
        values = [c[name] for c in counts]
        classes.bar(range(len(counts)), values, bottom=bottom, color=color, label=T(f"sowing.drop.{name}", lang))
        bottom = [b + v for b, v in zip(bottom, values)]
    classes.set_xticks(range(len(counts)), labels, fontsize=7.5)
    classes.set_title(T("rain_decision.classes", lang), loc="left", fontsize=9.5, fontweight="bold")
    classes.legend(frameon=False, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3)
    shares = sens["rotations_high_deficit_share"]
    _grouped(rotations, [r.replace("survey_", "") for r in shares], {"POWER": ([v["power"] for v in shares.values()], power_c),
                                                                      "IMERG": ([v["imerg"] for v in shares.values()], imerg_c)}, value_format="{:.2f}", size=6.5)
    rotations.set_title(T("rain_decision.rotations", lang), loc="left", fontsize=9.5, fontweight="bold")
    rotations.legend(frameon=False, fontsize=8)
    for ax in (monthly, stress, classes):
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    fig.suptitle(T("rain_decision.title", lang), x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.text(0.01, 0.01, T("rain_decision.note", lang), fontsize=7.5, color=MUTED, style="italic")
    fig.tight_layout(rect=(0, 0.03, 1, 0.96), h_pad=3)
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def plot_sensor_windows(doc, path, lang="en"):
    fig, (whole, first) = plt.subplots(1, 2, figsize=(11, 4.2), dpi=130)
    months = [str(r["month"]) for r in doc["by_start_month"]]
    for ax, blind, sensor, title in ((whole, "open_loop", "with_sensor", T("sensor_windows.whole", lang)),
                                     (first, "open_loop_first", "with_sensor_first", T("sensor_windows.first", lang, days=doc["start_window_days"]))):
        _grouped(ax, months, {T("sensor_windows.no_sensor", lang): ([r[blind] for r in doc["by_start_month"]], "#e0903f"),
                              T("sensor_windows.daily", lang): ([r[sensor] for r in doc["by_start_month"]], "#2d6a8f")}, labels=False)
        ax.set_title(title, loc="left", fontsize=9.5, fontweight="bold")
        ax.set_xlabel(T("sensor_windows.start_month", lang), fontsize=8)
    whole.legend(frameon=False, fontsize=8)
    helped = doc["share_helped"]
    fig.suptitle(f"{T('sensor_windows.title', lang)} · n={doc['windows']} · {helped['whole_year']:.0%} / {helped['first_days']:.0%}", x=0.01, ha="left", fontsize=10.5, fontweight="bold")
    fig.text(0.01, 0.01, T("sensor_windows.note", lang), fontsize=7.2, color=MUTED, style="italic")
    fig.tight_layout(rect=(0, 0.04, 1, 0.93))
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def plot_sensor_recalibration(doc, path, lang="en"):
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.2), dpi=130)
    soils = ("original", "fitted", "fitted_with_reference")
    for ax, metric in zip(axes, ("rmse", "bias", "spread")):
        _grouped(ax, [T(f"sensor_recal.{s}", lang).replace(", ", ",\n").replace(" to ", " to\n") for s in soils],
                 {T(f"sensor_recal.{mode}", lang): ([doc["test"][f"{s}_{mode}"][metric] for s in soils], color)
                  for mode, color in (("open_loop", "#e0903f"), ("corrected", "#2d6a8f"))}, value_format="{:.4f}", size=6.5)
        ax.set_title(T(f"sensor_recal.{metric}", lang), loc="left", fontsize=9.5, fontweight="bold")
        ax.tick_params(axis="x", labelsize=6.5)
    axes[0].legend(frameon=False, fontsize=7.5)
    fig.suptitle(T("sensor_recal.title", lang), x=0.01, ha="left", fontsize=10.5, fontweight="bold")
    fig.text(0.01, 0.01, T("sensor_recal.note", lang), fontsize=7.2, color=MUTED, style="italic")
    fig.tight_layout(rect=(0, 0.04, 1, 0.93))
    fig.savefig(path, facecolor="white")
    plt.close(fig)
