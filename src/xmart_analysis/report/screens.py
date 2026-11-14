"""Render the platform screens as figures (Matplotlib) from a session document.

The figures are drawn only from the session produced by `platform_session.build_session`: whatever a screen
shows is a value the engine returned, a value the person entered or a label. Text comes from the label catalog
in the requested language. Severity of deficit uses one sequential palette (light to dark) plus counts and
words, never red/blue "good/bad" colours, and the options are never ranked.

Screens: main (soil water and scenarios), options (cards) and data (producer and agronomist sheet).
"""

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Polygon  # noqa: E402

from xmart_analysis.engine import crops_uy as cu
from xmart_analysis.engine import platform_session as _ps
from xmart_analysis.engine.i18n import label

INK, MUTED, PAGE, CARD, BORDER = "#1f2a30", "#5b6770", "#f4f1ea", "#ffffff", "#cfc8b8"
ACCENT, WATER, WATER_LIGHT = "#2d6a8f", "#2d6a8f", "#bcd5e4"
SEVERITY = {"low_deficit": "#f3dcae", "moderate_deficit": "#e0903f", "high_deficit": "#8a3d14"}
DPI = 130


def T(key, lang, **params):
    return label(key, **params)[lang]


def _L(value, lang):
    """Text of a label object, or the text itself when the document is already resolved to one language."""
    return value[lang] if isinstance(value, dict) else value


def _cap(text):
    return text[:1].upper() + text[1:]


def _text(ax, x, y, s, size=10, color=INK, weight="normal", ha="left", va="top", style="normal", wrap=None, **kw):
    if wrap:
        s = "\n".join(textwrap.wrap(s, wrap))
    return ax.text(x, y, s, fontsize=size, color=color, fontweight=weight, ha=ha, va=va, fontstyle=style, **kw)


def _page(width, height):
    fig = plt.figure(figsize=(width, height), dpi=DPI, facecolor=PAGE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")
    return fig, ax


def _box(ax, x, y, w, h, face=CARD, edge=BORDER, radius=0.12, lw=1.0):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={radius}", facecolor=face,
                                edgecolor=edge, linewidth=lw))


def _drop(ax, x, y, r, color):
    ax.add_patch(Polygon([(x - r * 0.8, y + r * 0.45), (x + r * 0.8, y + r * 0.45), (x, y + r * 2.0)], closed=True,
                         facecolor=color, edgecolor=INK, linewidth=0.8, zorder=3))
    ax.add_patch(Circle((x, y), r, facecolor=color, edgecolor=INK, linewidth=0.8, zorder=4))


def _footer(ax, width, lang, y=0.32):
    _text(ax, 0.35, y, T("screen.footer", lang), size=8, color=MUTED, wrap=int(width * 14), style="italic")


def _moisture_label_key(session):
    source = session["outputs"]["main_screen"]["soil_water"]["source"]
    return {"simulated_iot_sensor": "screen.main.moisture", "manual_entry": "screen.main.moisture_manual"}.get(
        source, "screen.main.moisture_real")


def render_main(session, path, lang):
    main = session["outputs"]["main_screen"]
    sw, sc = main["soil_water"], main["scenarios"]
    width, height = 8.3, 11.7
    fig, ax = _page(width, height)
    _text(ax, 0.4, 11.45, T("screen.main.title", lang), size=24, weight="bold")
    _text(ax, 0.4, 10.9, f"{session['inputs']['location']['latitude']:.4f}, {session['inputs']['location']['longitude']:.4f} · NASA POWER · {session['inputs']['reading_date'][3:]}/{session['inputs']['reading_date'][:2]}",
          size=10, color=MUTED)
    # two blocks: sensor moisture and available water
    _box(ax, 0.4, 9.55, 3.85, 1.15)
    _text(ax, 0.6, 10.55, T(_moisture_label_key(session), lang), size=9, color=MUTED, wrap=34)
    _text(ax, 0.6, 10.05, f"{sw['volumetric_moisture'] * 100:.0f} %", size=26, weight="bold", color=ACCENT)
    _text(ax, 1.75, 9.82, "m³/m³ × 100", size=8, color=MUTED)
    _box(ax, 4.45, 9.55, 3.45, 1.15)
    _text(ax, 4.65, 10.55, T("scenarios.level.available", lang).split(":")[0], size=9, color=MUTED, wrap=30)
    _text(ax, 4.65, 10.05, "—" if lang == "en" else "—", size=26, weight="bold", color=MUTED)
    _text(ax, 5.35, 10.0, T("screen.main.calibration", lang).split(":")[1].strip().capitalize() if False else
          {"en": "Not determined", "es": "Sin determinar"}[lang], size=12, weight="bold", color=INK)
    _text(ax, 0.4, 9.4, T("screen.main.calibration", lang), size=9, color=MUTED)

    # panel A: scenario evolution
    spread = sc["spread_by_day"]
    axA = fig.add_axes([0.1, 0.46, 0.85, 0.24], facecolor=CARD)
    days = [r["day"] for r in spread]
    axA.fill_between(days, [r["p10_mm"] for r in spread], [r["p90_mm"] for r in spread], color=WATER_LIGHT, label="p10-p90")
    axA.plot(days, [r["median_mm"] for r in spread], color=WATER, linewidth=2.2, label=T("screen.main.median", lang))
    axA.axhline(sc["stress_threshold_mm"], color=MUTED, linestyle="--", linewidth=1)
    axA.text(days[-1], sc["stress_threshold_mm"] + 3, f"{sc['stress_threshold_mm']:.0f} mm", color=MUTED, fontsize=8, ha="right")
    axA.set_xlabel(T("screen.main.axis_days", lang), fontsize=9)
    axA.set_ylabel(T("screen.main.axis_mm", lang), fontsize=8)
    axA.set_ylim(0, max(sc["initial_state"]["capacity_mm"], max(r["p90_mm"] for r in spread)) * 1.05)
    axA.set_title(T("screen.main.evolution", lang, n=sc["scenarios"]), loc="left", fontsize=10.5, fontweight="bold")
    axA.legend(frameon=False, fontsize=8, loc="upper right")
    axA.title.set_position((0, 1.02))
    for side in ("top", "right"):
        axA.spines[side].set_visible(False)
    axA.text(0.01, 0.03, T("scenarios.spread_label", lang), transform=axA.transAxes, fontsize=7.8, color=MUTED, style="italic")

    # panel B: sensitivity to soil assumptions, in volumetric moisture
    axB = fig.add_axes([0.1, 0.27, 0.85, 0.12], facecolor=CARD)
    ss = sc["structural_sensitivity"]
    base = {r["day"]: r for r in spread}
    if ss["envelope_by_day_m3_m3"]:
        for i, e in enumerate(ss["envelope_by_day_m3_m3"]):
            axB.vlines(i, e["median_min_m3_m3"], e["median_max_m3_m3"], color=ACCENT, linewidth=9, alpha=0.35)
            axB.plot(i, base[e["day"]]["median_m3_m3"], marker="D", color=INK, markersize=6)
        axB.set_xticks(range(len(ss["envelope_by_day_m3_m3"])))
        axB.set_xticklabels([f"{e['day']}" for e in ss["envelope_by_day_m3_m3"]], fontsize=8)
        axB.set_xlim(-0.6, len(ss["envelope_by_day_m3_m3"]) - 0.4)
    else:
        axB.text(0.5, 0.5, ss["status"], transform=axB.transAxes, ha="center")
    axB.set_ylabel("m³/m³", fontsize=8)
    axB.set_xlabel(T("screen.main.axis_days", lang), fontsize=8)
    axB.set_title(T("screen.main.sensitivity", lang), loc="left", fontsize=9.5, fontweight="bold")
    for side in ("top", "right"):
        axB.spines[side].set_visible(False)
    axB.text(0.99, 0.04, f"◆ {T('screen.main.base_median', lang)} · ▮ {T('screen.main.soil_range', lang)}",
             transform=axB.transAxes, ha="right", fontsize=7.5, color=MUTED)

    # reading notes
    notes = [_L(w["label"], lang) for w in sc["initial_state"]["reading_warnings"]]
    notes += [T(f"sensor.source_warning.{c}", lang) for c in sw.get("source_warnings", [])]
    if notes:
        _text(ax, 0.4, 1.05, T("screen.main.warnings", lang), size=8.5, weight="bold")
        _text(ax, 0.55, 0.85, "\n".join(notes), size=7.8, color=MUTED, wrap=118)
    _footer(ax, width, lang, 0.3)
    fig.savefig(path, dpi=DPI, facecolor=PAGE)
    plt.close(fig)


def _card_lines(card, lang):
    """The sub-heading and the reading sentence of an option card."""
    if card["kind"] == "rotation":
        counts = {}
        for c in card["crops"]:
            counts[_L(c["name"], lang)] = counts.get(_L(c["name"], lang), 0) + 1
        names = ", ".join(f"{n} ×{k}" if k > 1 else n for n, k in counts.items())
        return names, T("card.rotation_detail", lang, crops=card["crops_modelled"], n=card["high_deficit_combinations"],
                        total=card["combinations"])
    status = card.get("status")
    sub = f"{_cap(T('flow.menu.crop', lang))} · {card['sowing'][3:]}/{card['sowing'][:2]}"
    if card["critical_window"]:
        sub += " · " + T("screen.cards.critical_window", lang, start=card["critical_window"]["start"],
                         end=card["critical_window"]["end"])
    if status in ("cycle_ended", "critical_stage_passed"):
        reading = T("card." + ("cycle_ended" if status == "cycle_ended" else "stage_passed"), lang,
                    day=card["day_of_cycle"], cycle=card["cycle_days"])
    else:
        reading = T("card.deficit_reading", lang, n=card["high_deficit_seasons"], total=card["scenarios"])
        if status == "critical_stage_ahead":
            sub += " · " + T("screen.cards.stage_ahead", lang, day=card["day_of_cycle"], cycle=card["cycle_days"]).split(": ")[0]
        elif status == "in_critical_stage":
            pct = round(card["critical_stage_remaining_fraction"] * 100)
            sub += " · " + T("screen.cards.stage_in_progress", lang, day=card["day_of_cycle"], cycle=card["cycle_days"], pct=pct).split(": ")[0]
    return sub, reading


def render_options(session, path, lang):
    cards = session["outputs"]["option_cards"]
    width = 8.3
    card_h, gap = 2.45, 0.2
    height = 1.9 + len(cards) * (card_h + gap) + 1.6
    fig, ax = _page(width, height)
    _text(ax, 0.4, height - 0.35, T("screen.cards.title", lang), size=22, weight="bold")
    _text(ax, 0.4, height - 0.95, T("screen.cards.subtitle", lang), size=9.5, color=MUTED, wrap=100)
    y = height - 1.45
    for card in cards:
        top = y
        _box(ax, 0.3, top - card_h, width - 0.6, card_h)
        _text(ax, 0.55, top - 0.2, _L(card["title"], lang), size=13.5, weight="bold")
        if card["is_current"]:
            _box(ax, width - 2.4, top - 0.52, 1.9, 0.32, face=ACCENT, edge=ACCENT, radius=0.15)
            _text(ax, width - 1.45, top - 0.36, T("flow.current_card", lang), size=8.5, color="white", ha="center", va="center",
                  weight="bold")
        sub, reading = _card_lines(card, lang)
        _text(ax, 0.55, top - 0.62, sub, size=8.8, color=MUTED)
        if card["split_in_10_parts"]:
            # ten drops, light to dark = low to high deficit
            order = [c for c in ("low_deficit", "moderate_deficit", "high_deficit") for _ in range(card["split_in_10_parts"][c])]
            for i, cls in enumerate(order):
                _drop(ax, 0.8 + i * 0.5, top - 1.12, 0.17, SEVERITY[cls])
            counts = card["season_counts"]
            _text(ax, 5.95, top - 0.95, "\n".join(f"{T('deficit_class.' + c, lang)}: {counts[c]}" for c in SEVERITY), size=8.2, color=MUTED)
            _text(ax, 0.55, top - 1.45, reading, size=10.5, weight="bold")
        else:
            _text(ax, 0.55, top - 1.0, reading, size=9.2, weight="bold", color=MUTED, wrap=86)
        _text(ax, 0.55, top - 1.75, T("screen.cards.soil_none", lang), size=8.8, color=MUTED)
        if card["kind"] == "rotation":
            skipped = [_L(c["name"], lang) for c in card["crops"] if c["status"] == "not_modelled"]
            if skipped:
                _text(ax, 0.55, top - 2.0, T("rotation.unmodelled", lang, crops=", ".join(skipped)), size=7.6, color="#8a3d14",
                      style="italic", wrap=140)
        elif card["warnings"]:
            shown = [w for w in card["warnings"] if w["code"] != "current_crop_partial_cycle"][-2:] or card["warnings"][-1:]
            _text(ax, 0.55, top - 2.0, "\n".join("⚠ " + _L(w["label"], lang) for w in shown), size=7.2, color="#8a3d14", wrap=140,
                  style="italic")
        y -= card_h + gap
    _text(ax, 0.4, y - 0.05, T("screen.cards.legend_note", lang), size=8, color=MUTED, wrap=118)
    _text(ax, 0.4, y - 0.65, T("screen.cards.confidence", lang), size=8, color=MUTED, wrap=118)
    _footer(ax, width, lang, y - 1.15)
    fig.savefig(path, dpi=DPI, facecolor=PAGE)
    plt.close(fig)


UNITS = {"agronomist.organic_matter_pct": " %", "agronomist.phosphorus_ppm": " ppm", "agronomist.erosion_t_ha_yr": " t/ha/año",
         "past_seasons.yield_kg_ha": " kg/ha"}


def _fmt_md(value):
    return f"{value[3:]}/{value[:2]}"


def _format_value(row, lang, session):
    v = row["value"]
    if not row["entered"]:
        return T("screen.sheet.not_entered", lang)
    field = row["field"]
    if field == "past_seasons.rating":
        return ", ".join(T(f"screen.sheet.rating.{x}", lang) if x else "·" for x in v)
    if field == "past_seasons.crops":
        return "; ".join(" + ".join(T(_ps.crop_label_key(c), lang) for c in crops) or "·" for crops in v)
    if field == "current_crop.crop":
        return cu_name(v, lang)
    if field == "current_crop.sowing":
        return _fmt_md(v)
    if field == "options":
        return "; ".join(T("rotation.title", lang, n=int(o["rotation"].split("_")[1])) if o["kind"] == "rotation"
                         else f"{cu_name(o['crop'], lang)} {_fmt_md(o['sowing'])}" for o in v)
    if field == "agronomist.soil_type":
        text = v if isinstance(v, str) else str(v)
        confirmed = session["inputs"]["agronomist"].get("soil_type_confirmed")
        tag = {True: {"en": "confirmed", "es": "confirmado"}, False: {"en": "not confirmed", "es": "sin confirmar"}}.get(confirmed)
        return f"{text}" + (f" ({tag[lang]})" if tag else "")
    unit = UNITS.get(field, "")
    if isinstance(v, list):
        return ", ".join("·" if x is None else f"{x}{unit}" for x in v)
    return f"{v}{unit}"


def cu_name(crop, lang):
    return T(cu.name_label_key(crop), lang)


def render_data(session, path, lang):
    rows = session["data_sheet"]["rows"]
    row_h = 0.62
    n_rows = len([r for r in rows if r["source"] in ("producer", "agronomist")])
    width, height = 8.3, 2.0 + n_rows * row_h + 2 * 0.9 + 3.3 + 1.2
    fig, ax = _page(width, height)
    _text(ax, 0.4, height - 0.35, T("screen.sheet.title", lang), size=21, weight="bold", wrap=34)
    y = height - 1.3
    for source, key in (("producer", "screen.sheet.farmer"), ("agronomist", "screen.sheet.agronomist")):
        _text(ax, 0.4, y, T(key, lang), size=12, weight="bold")
        _text(ax, 6.0, y, T("screen.sheet.column_use", lang), size=8.5, color=MUTED)
        y -= 0.5
        for row in [r for r in rows if r["source"] == source]:
            _box(ax, 0.3, y - row_h + 0.06, width - 0.6, row_h - 0.1, radius=0.08)
            _text(ax, 0.5, y - 0.1, _L(row["label"], lang), size=8.6, weight="bold", wrap=24)
            _text(ax, 2.5, y - 0.1, _format_value(row, lang, session), size=8.2, color=INK if row["entered"] else MUTED, wrap=52)
            used = row["status"] == "used"
            _text(ax, 6.2, y - 0.1, ("✔ " if used else "○ ") + T(f"contract.status.{row['status']}", lang), size=8,
                  color=ACCENT if used else MUTED, wrap=22, weight="bold" if used else "normal")
            y -= row_h
        y -= 0.4
    rain = session["data_sheet"]["rain_dec_mar_context"]["seasons"]
    if rain:
        axR = fig.add_axes([0.1, 1.55 / height, 0.85, 2.7 / height], facecolor=CARD)
        axR.bar([r["season"] for r in rain], [r["rain_dec_mar_mm"] for r in rain], color=WATER_LIGHT, edgecolor=WATER)
        for i, r in enumerate(rain):
            axR.text(i, r["rain_dec_mar_mm"] + 8, f"{r['rain_dec_mar_mm']:.0f}", ha="center", fontsize=8)
        axR.set_ylabel("mm", fontsize=8)
        axR.set_title({"en": "December-March rainfall by season (NASA POWER, context only)",
                       "es": "Lluvia de diciembre a marzo por zafra (NASA POWER, solo contexto)"}[lang], loc="left", fontsize=9.5,
                      fontweight="bold")
        for side in ("top", "right"):
            axR.spines[side].set_visible(False)
    _text(ax, 0.4, 1.25, T("screen.sheet.provenance", lang), size=7.8, color=MUTED, wrap=124, style="italic")
    _footer(ax, width, lang, 0.55)
    fig.savefig(path, dpi=DPI, facecolor=PAGE)
    plt.close(fig)


def render_all(session, outdir, lang):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {"main": out / f"screen_main.{lang}.png", "options": out / f"screen_options.{lang}.png",
             "data": out / f"screen_data.{lang}.png"}
    render_main(session, paths["main"], lang)
    render_options(session, paths["options"], lang)
    render_data(session, paths["data"], lang)
    return paths
