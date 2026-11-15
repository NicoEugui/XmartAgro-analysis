"""The experiment log: one Markdown document with every run, its figures, the numbers behind each figure and the data lineage.

It is written from the same documents the figures are drawn from (`xmart_analysis.validation`, the calibration file, the dataset
manifest and the frontend payload), so the text cannot drift from the runs. `FIGURES` is the single list that names, for each figure, the
function that draws it and the table of values it plots; a test checks the plotted values against that table.
"""

import hashlib
from datetime import date
from pathlib import Path

from xmart_analysis.engine import tables

from . import scenario_runs
from . import validation as figures


def _md(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(" --- " for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def _details(summary, headers, rows):
    return f"<details><summary>{summary}</summary>\n\n{_md(headers, rows)}\n\n</details>"


def survey_table(doc):
    crops = list(doc["crops"])
    rows = [[s, doc["mentions"][s], *(doc["crops"][c]["stress"][s] for c in crops)] for s in doc["window"]]
    return ["season", "producers naming it", *(f"{c} stress" for c in crops)], rows


def ndvi_table(doc):
    return (["season", "NDVI Dec-Mar", "soybean_1st stress", "maize stress"],
            [[r["season"], r["ndvi_dec_mar"], r["soybean_1st_stress"], r["maize_stress"]] for r in doc["seasons"]])


def imerg_table(doc):
    return ["season", "IMERG Dec-Mar mm", "POWER Dec-Mar mm"], [[r["season"], r["imerg_mm"], r["power_mm"]] for r in doc["seasons_dec_mar"]]


def sensitivity_table(doc):
    return (["season", "stress with POWER rain", "stress with IMERG rain"],
            [[r["season"], r["power"], r["imerg"]] for r in doc["crops"][doc["first_crop"]]["stress"]])


def smap_table(doc):
    scores = doc["periods"]["validation"]["scores"]
    return ["predictor", "rank correlation", "anomaly correlation"], [[n, s["spearman"], s["anomaly_r"]] for n, s in scores.items()]


def sowing_table(doc):
    return (["crop", "sown on (calendar day, every season)", "ok", "tight", "out"],
            [[c, scenario_runs.day_label(r["sowing"]), r["counts"]["ok"], r["counts"]["tight"], r["counts"]["out"]] for c, e in doc["crops"].items() for r in e["dates"]])


def sensor_table(doc):
    window = f"RMSE first {doc['start_window_days']} days m3/m3"
    rows = [["no sensor", doc["open_loop"]["rmse"], doc["open_loop"]["first_days_rmse"]]]
    rows += [["daily sensor" if r["every_days"] == 1 else f"sensor every {r['every_days']} days", r["rmse"], r["first_days_rmse"]]
             for r in doc["with_sensor"]]
    return ["run", "RMSE whole year m3/m3", window], rows


FIGURES = {
    "sensor": (figures.plot_sensor, sensor_table),
    "sowing": (figures.plot_sowing, sowing_table),
    "survey": (figures.plot_survey, survey_table),
    "ndvi": (figures.plot_ndvi, ndvi_table),
    "imerg": (figures.plot_imerg, imerg_table),
    "rain_sensitivity": (figures.plot_rain_sensitivity, sensitivity_table),
    "smap": (figures.plot_smap, smap_table),
}


def _figure(name, doc, out, lang, caption):
    draw, table = FIGURES[name]
    path = Path(out) / "figures" / f"{name}.{lang}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    draw(doc, path, lang)
    headers, rows = table(doc)
    return f"![{caption}](figures/{path.name})\n\n" + _details("Values plotted in this figure", headers, rows)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def _lineage():
    rows = [[r["path"], r["role"], r["source_ref"], r["period"] or "-", r["rows"] or "-", r["sha256"][:12]] for r in tables.manifest()]
    return _md(["file", "role", "source", "period", "rows", "sha256"], rows)


def _model(calibration):
    c, v = calibration["calibration"], calibration["validation"]
    params = _md(["parameter", "value"], [[k, round(x, 4)] for k, x in calibration["parameters"].items()])
    metrics = _md(["period", "days", "RMSE m3/m3", "bias m3/m3", "correlation", "anomaly correlation"],
                  [[n, m["days"], m["rmse_m3_m3"], m["bias_m3_m3"], m["correlation"], m["anomaly_correlation"]]
                   for n, m in (("calibration " + "/".join(c["period"]), c), ("validation " + "/".join(v["period"]), v))])
    seeds = _md(["seed", *calibration["seed_runs"][0]["parameters"]], [[r["seed"], *(round(x, 4) for x in r["parameters"].values())]
                                                                       for r in calibration["seed_runs"]]) \
        if calibration["seed_runs"] and "parameters" in calibration["seed_runs"][0] else ""
    return params, metrics, seeds


def _sowing_extras(doc):
    dates = [[c, scenario_runs.day_label(r["sowing"]), f"{r['first_sowing']} to {r['last_sowing']}", f"{r['shift_days']:+d}", r["median_stress"], r["median_water_at_sowing_mm"], ", ".join(r["warnings"])]
             for c, e in doc["crops"].items() for r in e["dates"]]
    detail = doc["detail"]
    seasons = [[r["season"], r["sowing_date"], r["water_at_sowing_mm"], r["stress"], r["deficit_days"], r["class"]] for r in detail["seasons"]]
    reading = [[r["volumetric_moisture"], r["counts"]["ok"], r["counts"]["tight"], r["counts"]["out"]] for r in doc["reading_sensitivity"]["readings"]]
    return ("How to read the dates. A sowing date here is a calendar day without a year (for example 15 Nov). The model applies it to each of the historical seasons "
            "in turn, with that season's real weather: 15 Nov 1987, 15 Nov 1988 and so on up to the last complete season (the table gives the first and last date simulated "
            f"for every run). The sensor reading is taken on {scenario_runs.day_label(doc['reading_date'])} of each year and carried to the sowing date with that year's weather. "
            "A season is named after the year of sowing (1987/88 = sown in 1987); a sowing day earlier in the calendar than the reading day, such as maize on 1 Oct, is read as the "
            "next year's, hence the `sowing_far_from_reading` warning.\n\n"
            "Median stress and water at sowing per run (every run carries the fixed-cycle warning; `sowing_far_from_reading` marks a sowing far from the reading date):\n\n"
            + _md(["crop", "sown on", "first to last sowing simulated", "shift vs default (days)", "median stress", "median water at sowing mm", "warnings"], dates)
            + f"\n\n{_details(f'Season by season: {detail['crop']} sown on {scenario_runs.day_label(detail['sowing'])} each year', ['season', 'sown on', 'water at sowing mm', 'stress', 'deficit days', 'class'], seasons)}"
            + f"\n\nSensitivity to the sensor reading ({doc['reading_sensitivity']['crop']}, default sowing date; the reading is simulated):\n\n"
            + _md(["volumetric moisture", "ok", "tight", "out"], reading) + f"\n\n{doc['note']}.")


def _options(frontend):
    rows = [[o["id"], o["kind"], o["water_risk"] or "-", *(((o["drops"] or {}).get(k, "-")) for k in ("ok", "tight", "out"))]
            for o in frontend["summary"]["options"]]
    return _md(["option", "kind", "water risk", "ok", "tight", "out"], rows)


def build(validation_doc, calibration, frontend, out, files=None, lang="en"):
    """Write `experiments.md` and `figures/` into `out`; `files` maps the input files (smap_l3, smap_l4, modis_ndvi, imerg) to paths."""
    files = files or {}
    problems = tables.validate()
    params, metrics, seeds = _model(calibration)
    parts = [f"# XmartAgro experiment log\n\nSite: `{tables.active_site()}` ({tables.constants_of(tables.active_site())['latitude']}, "
             f"{tables.constants_of(tables.active_site())['longitude']}). Generated {date.today()} by `xmart-analysis report`. "
             "Exploratory: nothing here validates a crop or rotation outcome.",
             "## 1. Data architecture\n\nOnly NASA data and the team's own producer survey enter the repository.\n\n"
             "```\nNASA POWER (daily climate) --> water-balance engine --> scenarios per historical season --> frontend JSON\n"
             "NASA SMAP L4 -----------------> calibration (soil parameters, fitted) ----^\n"
             "simulated sensor year ---------> state correction (experiment only; the demo reading is still one simulated value)\n"
             "validators (not model inputs): SMAP L3/L4, MODIS NDVI, GPM IMERG, producer survey\n```\n\n" + _lineage()
             + "\n\nInput files of the runs below, identified by checksum (the NASA files are in the repository and listed above):\n\n"
             + _md(["input", "file", "sha256"], [[k, Path(p).name, _sha(p)] for k, p in files.items()] or [["-", "none given", "-"]]),
             "## 2. Model and calibration\n\nDaily soil-water bucket (Hargreaves evapotranspiration from latitude and temperature range, crop coefficient by stage), "
             f"calibrated by differential evolution against SMAP L4 root-zone moisture.\n\n{params}\n\n{metrics}\n\n"
             f"Chosen seed: {calibration['chosen_seed']}. {calibration['selection']}.\n\n"
             + (f"Parameters of every seed (they differ: the soil is not uniquely identified):\n\n{seeds}\n\n" if seeds else "")
             + "Crop parameters are all `pending` (no dataset yet).",
             "## 3. Model output for the bundled demo scenario\n\n" + _options(frontend)
             + "\n\nRisk comes from how many of the 39 historical seasons end in high deficit; the drops are counts, not probabilities."]
    n = 4
    sections = (
        ("sowing", "What happens if a crop is sown on a given date",
         "For each crop and sowing date (the default calendar day and four shifted by 15 and 30 days; each day is applied to every historical season with complete weather), how many of the historical seasons end in low, moderate or high deficit "
         "in the critical stage?",
         lambda d: "Each bar applies every complete historical season to a simulated reading at the chosen sowing date. " + " ".join(
             f"{c}: default date {e['default_sowing']}, median stress {min(r['median_stress'] for r in e['dates'])}-{max(r['median_stress'] for r in e['dates'])} "
             f"across the dates." for c, e in d["crops"].items())),
        ("survey", "Producers' unfavourable seasons vs modelled stress",
         "Do the seasons the producers called unfavourable match the model's critical-stage stress?",
         lambda d: f"The two most stressed seasons are {', '.join(d['crops']['soybean_1st']['highest_stress'])} for soybean and "
                   f"{', '.join(d['crops']['maize']['highest_stress'])} for maize; the most named by producers are "
                   f"{', '.join(d['crops']['soybean_1st']['most_named'])}. Agreement: {d['crops']['soybean_1st']['agree']} / {d['crops']['maize']['agree']}. "
                   f"{d['answered']} of {d['respondents']} respondents answered unambiguously."),
        ("smap", "Modelled soil water vs SMAP",
         "Does the model follow independent soil-moisture data in years it was not fitted on?",
         lambda d: "Validation period rank correlation / anomaly correlation: " + ", ".join(
             f"{n} {s['spearman']} / {s['anomaly_r']}" for n, s in d["periods"]["validation"]["scores"].items())
         + f" (n={d['periods']['validation']['days']} days). {d['depth_note']}"),
        ("ndvi", "Modelled stress vs MODIS NDVI",
         "Do seasons with a greener pixel in Dec-Mar have lower modelled stress?",
         lambda d: "Spearman of NDVI against minus stress: " + ", ".join(
             f"{c} {v['spearman_ndvi_vs_minus_stress']} (p={v['permutation_p']})" for c, v in d["correlations"].items())
         + f". {d['overlap']} of the {len(d['most_stressed_seasons'])} most stressed seasons are among the lowest-NDVI (chance: {d['overlap_expected_by_chance']}). "
           "Weak evidence: the pixel mixes crops, stubble and pasture."),
        ("imerg", "POWER rain vs GPM IMERG rain",
         "How well do the two NASA rain estimates agree at the field?",
         lambda d: f"Daily r {d['rain']['daily_r']}, monthly r {d['rain']['monthly_r']}, Dec-Mar by season r {d['rain']['season_dec_mar_r']}; "
                   f"annual mean POWER {d['rain']['mean_annual_mm']['power']} mm, IMERG {d['rain']['mean_annual_mm']['imerg']} mm "
                   f"({d['period'][0]} to {d['period'][1]}). Driest seasons by IMERG {d['driest_seasons']['imerg']}, by POWER {d['driest_seasons']['power']}."),
        ("rain_sensitivity", "Model run with POWER rain and with IMERG rain",
         "Does the result change if the model uses IMERG rain? Only the rain changes; soil parameters stay the POWER-fitted ones.",
         lambda d: " ".join(f"{c}: {v['seasons']} seasons, rank agreement {v['spearman_between_sources']}, mean absolute stress difference "
                            f"{v['mean_abs_difference']}, high-deficit seasons {v['high_deficit_seasons']['power']} (POWER) vs {v['high_deficit_seasons']['imerg']} (IMERG)."
                            for c, v in d["crops"].items())),
        ("sensor", "Water balance with and without a (simulated) soil-moisture sensor",
         "If the field has a soil the model does not know, does feeding the model a sensor series bring it closer to the field? "
         "The field and the sensor are both simulated, so the truth is known.",
         lambda d: (lambda daily: f"Over {d['period'][0]} to {d['period'][1]} the model without sensor has an error (RMSE) of {d['open_loop']['rmse']} m3/m3; with daily readings "
                    f"{daily['rmse']} (weekly {d['with_sensor'][1]['rmse']}, monthly {d['with_sensor'][2]['rmse']}). In the first "
                    f"{d['start_window_days']} days, while the model still carries a wrong starting state, it falls from {d['open_loop']['first_days_rmse']} to "
                    f"{daily['first_days_rmse']}. The bias goes from {d['open_loop']['bias']} to {daily['bias']}: the sensor's offset "
                    f"({d['sensor']['bias']}) and the field's different wilting point are a calibration gap, and correcting the water state toward the readings adopts it instead of removing it. "
                    f"The raw readings are {d['sensor']['errors']['rmse']} m3/m3 from the truth (noise {d['sensor']['noise_sd']}). "
                    f"Correction gain {d['gain']}. {d['note'].capitalize()}.")(d["with_sensor"][0])),
    )
    for key, title, question, reading in sections:
        if key not in validation_doc:
            continue
        doc = validation_doc[key]
        parts.append(f"## {n}. {title}\n\n**Question.** {question}\n\n{_figure(key, doc, out, lang, title)}\n\n**Reading.** {reading(doc)}")
        if key == "sowing":
            parts[-1] += "\n\n" + _sowing_extras(doc)
        if key == "rain_sensitivity":
            shares = [[r, s["power"], s["imerg"]] for r, s in doc["rotations_high_deficit_share"].items()]
            parts[-1] += "\n\nShare of seasons with high deficit per rotation:\n\n" + _md(["rotation", "POWER rain", "IMERG rain"], shares)
        n += 1
    parts.append(f"## {n}. Integrity checks\n\n"
                 + _md(["check", "result"], [["provenance and dataset manifest", "consistent" if not problems else "; ".join(problems)],
                                             ["values plotted are the values in the tables above", "enforced by tests (`tests/test_report.py`)"],
                                             ["files used are at the site's point", "enforced when loading (`file_not_at_site`)"]])
                 + "\n\n## Not validated\n\n- Crop parameters (`pending`) and therefore per-crop and per-rotation risk.\n"
                   "- Soil state and effect (no diagnosis exists); every sensor reading, including the year in section "
                   "\"Water balance with and without a (simulated) soil-moisture sensor\", is simulated: no real sensor data exists yet.\n"
                   "- Which rain source is closer to the truth (no gauge data).\n")
    path = Path(out) / "experiments.md"
    path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    return path
