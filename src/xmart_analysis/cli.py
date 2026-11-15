"""Run the analysis without a database: `xmart-analysis run|validate`. Figures need the `plots` extra (matplotlib)."""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import validation
from .frontend import payload, schema
from .engine import context as engine_context
from .engine import sensor_series, tables
from .engine.errors import EngineError
from .engine.i18n import LANGUAGES
from .worker.adapters.engine import EngineAnalyzer
from .worker.adapters.files import FileResults, load_scenario
from .worker.adapters.memory import MemoryInputs, MemoryReadings
from .worker.application import RunAnalysis
from .worker.config import Settings

DEMO = tables.DATA_DIR / "demo_scenario.json"
NASA_FILES = {  # flag: (file bundled in the site folder, what it adds)
    "--smap-l3": ("smap_l3.csv", "NASA SMAP L3 CSV (SPL3SMP-E.006), adds the SMAP comparison; goes with --smap-l4"),
    "--smap-l4": ("smap_l4.csv", "NASA SMAP L4 CSV (SPL4SMGP.008), adds the SMAP comparison; goes with --smap-l3"),
    "--modis-ndvi": ("modis_ndvi.csv", "NASA MODIS MOD13Q1 CSV for the site, adds the vegetation check"),
    "--imerg": ("imerg_daily.csv", "NASA GPM IMERG Giovanni CSV for the site's cell, adds the rain check"),
}
NO_PLOTS = "Figures need matplotlib: pip install 'xmartagro-analysis[plots]'"


def import_report(name):
    try:
        return __import__(f"xmart_analysis.report.{name}", fromlist=[name])
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("matplotlib"):
            raise SystemExit(NO_PLOTS) from None
        raise


def run(args):
    field_id, store = load_scenario(args.scenario or DEMO)
    sink = FileResults(args.out)
    settings = Settings(ui_language="es" if args.lang == "both" else args.lang)
    use_case = RunAnalysis(MemoryReadings(store), MemoryInputs(store), sink, EngineAnalyzer(), settings,
                           lambda: datetime.now(timezone.utc))
    try:
        outcome = use_case(field_id)
    except EngineError as exc:
        print(json.dumps(exc.to_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(f"{outcome.status}: {sink.path(field_id)}")
    for note in outcome.notes:
        print("note:", note)
    if not args.no_figures:
        screens, doc = import_report("screens"), sink.load(field_id)
        for lang in LANGUAGES if args.lang == "both" else (args.lang,):
            for path in screens.render_all(doc["analysis"][lang], Path(args.out), lang).values():
                print("figure:", path)
    return 0


def validate(args):
    if bool(args.smap_l3) != bool(args.smap_l4):
        raise SystemExit("--smap-l3 and --smap-l4 go together")
    try:
        return _validate(args)
    except EngineError as exc:
        print(json.dumps(exc.to_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


def validation_document(args):
    """Run the validators whose input files were given (the producer survey and the simulated-sensor experiments always run)."""
    return validation.documents.build(engine_context.build_context(), args.smap_l3, args.smap_l4, args.modis_ndvi, args.imerg)


def _validate(args):
    doc = validation_document(args)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "validation.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("document:", out / "validation.json")
    survey = doc["survey"]
    print("site:", tables.active_site())
    for crop, entry in survey["crops"].items():
        print(f"survey, {crop}: highest stress {entry['highest_stress']}, most named {entry['most_named']}, agree={entry['agree']}")
    if "ndvi" in doc:
        n = doc["ndvi"]
        print(f"ndvi (n={len(n['seasons'])} seasons): {n['correlations']}; {n['overlap']} of the {len(n['most_stressed_seasons'])} most stressed "
              f"seasons are among the lowest-NDVI (chance: {n['overlap_expected_by_chance']})")
    if "imerg" in doc:
        r = doc["imerg"]["rain"]
        print(f"imerg ({doc['imerg']['period'][0]} to {doc['imerg']['period'][1]}): monthly rain r={r['monthly_r']}, Dec-Mar season r="
              f"{r['season_dec_mar_r']}, annual mm {r['mean_annual_mm']}, driest {doc['imerg']['driest_seasons']}")
    if "rain_sensitivity" in doc:
        for crop, c in doc["rain_sensitivity"]["crops"].items():
            print(f"rain sensitivity, {crop}: {c['seasons']} seasons, rho between sources {c['spearman_between_sources']}, mean abs stress "
                  f"difference {c['mean_abs_difference']}, high-deficit seasons {c['high_deficit_seasons']}")
        for r in doc["rain_sensitivity"]["producer_seasons"]:
            print(f"  producers' season {r['season']} ({r['mentions']} mentions): stress POWER {r['power']}, IMERG {r['imerg']}")
    for period, entry in doc.get("smap", {}).get("periods", {}).items():
        print(f"smap {period} (n={entry['days']}):", {k: (v["spearman"], v["anomaly_r"]) for k, v in entry["scores"].items()})
    if not args.no_figures:
        figures = import_report("validation")
        for lang in LANGUAGES:
            figures.plot_survey(survey, out / f"validation_survey.{lang}.png", lang)
            print("figure:", out / f"validation_survey.{lang}.png")
            if "ndvi" in doc:
                figures.plot_ndvi(doc["ndvi"], out / f"validation_ndvi.{lang}.png", lang)
                print("figure:", out / f"validation_ndvi.{lang}.png")
            if "imerg" in doc:
                figures.plot_imerg(doc["imerg"], out / f"validation_imerg.{lang}.png", lang)
                print("figure:", out / f"validation_imerg.{lang}.png")
            if "rain_sensitivity" in doc:
                figures.plot_rain_sensitivity(doc["rain_sensitivity"], out / f"validation_rain_sensitivity.{lang}.png", lang)
                print("figure:", out / f"validation_rain_sensitivity.{lang}.png")
            if "smap" in doc:
                figures.plot_smap(doc["smap"], out / f"validation_smap.{lang}.png", lang)
                print("figure:", out / f"validation_smap.{lang}.png")
    return 0


def _clock(now):
    """The clock of a run: the fixed instant given (ISO 8601) or the real time."""
    return (lambda: datetime.fromisoformat(now)) if now else (lambda: datetime.now(timezone.utc))


def frontend_document(scenario, now=None):
    """The frontend payload for a scenario file (the bundled demo by default)."""
    field_id, store = load_scenario(scenario or DEMO)
    analyzer = EngineAnalyzer()
    use_case = RunAnalysis(MemoryReadings(store), MemoryInputs(store), FileResults("."), analyzer, Settings(), _clock(now))
    answers, sensor_info, _, moment, _ = use_case.prepare(field_id)
    return payload.build(analyzer.analyze(answers, sensor_info), moment)


def export(args):
    """Write the static JSON for the frontend and the schemas that document it.

    The file the panel reads is always valid: when the analysis fails it holds the error document (status.mode `error`), and the
    command still exits with 1 and prints the error."""
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    code = 0
    try:
        document = frontend_document(args.scenario, args.now)
    except Exception as exc:  # noqa: BLE001 - whatever fails, the file must say so instead of staying stale
        error = exc.to_dict() if isinstance(exc, EngineError) else {"type": type(exc).__name__}
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        document, code = payload.build_error(error, _clock(args.now)()), 1
    names = {"frontend.json": payload.dumps(document), "frontend.schema.json": schema.dumps(),
             "frontend.error.schema.json": schema.dumps_error(), "frontend.fields.md": schema.markdown()}
    for name, text in names.items():
        (out / name).write_text(text, encoding="utf-8")
    print("written:", ", ".join(str(out / name) for name in names))
    return code


def report(args):
    """Write the experiment log (Markdown, figures and the values behind them) from the runs of this checkout."""
    try:
        doc = validation_document(args)
        doc["sowing"] = import_report("scenario_runs").run()
        frontend = frontend_document(None)
    except EngineError as exc:
        print(json.dumps(exc.to_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    calibration = json.loads(tables.calibration_path().read_text(encoding="utf-8"))
    files = {k: v for k, v in (("smap_l3", args.smap_l3), ("smap_l4", args.smap_l4), ("modis_ndvi", args.modis_ndvi), ("imerg", args.imerg)) if v}
    print("written:", import_report("experiments").build(doc, calibration, frontend, args.out, files, args.lang))
    return 0


def simulate_sensor(args):
    """Write the simulated year of sensor readings (the bundled one by default); the manifest checks it against its checksum."""
    sensor_series.write(args.out, sensor_series.readings(engine_context.build_context()))
    print("written:", args.out, tables.describe(Path(args.out).resolve()))
    return 0


def calibrate(args):
    from . import calibration

    try:
        doc = calibration.calibrate(args.smap_l4)
    except ModuleNotFoundError as exc:
        raise SystemExit("Calibration needs scipy: pip install 'xmartagro-analysis[calibrate]'") from exc
    Path(args.out).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("written:", args.out)
    print("parameters:", doc["parameters"])
    for part in ("calibration", "validation"):
        print(part, {k: v for k, v in doc[part].items() if k != "period"})
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="xmart-analysis", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn, help_text in (("run", run, "analyze a scenario file and draw the screens"),
                                ("validate", validate, "compare the model with the producer survey and, optionally, NASA SMAP, MODIS and IMERG")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--out", default="out", help="directory for documents and figures")
        p.add_argument("--no-figures", action="store_true")
        p.set_defaults(fn=fn)
    sub.choices["run"].add_argument("scenario", nargs="?", help="scenario JSON (default: the bundled demo)")
    sub.choices["run"].add_argument("--lang", choices=(*LANGUAGES, "both"), default="both")
    rep = sub.add_parser("report", help="write the experiment log (Markdown with figures and the values behind them)")
    rep.add_argument("--out", default="reports", help="directory for experiments.md and figures/")
    rep.add_argument("--lang", choices=LANGUAGES, default="en", help="language of the figures")
    rep.set_defaults(fn=report)
    for p in (sub.choices["validate"], rep):
        for flag, (name, text) in NASA_FILES.items():
            p.add_argument(flag, nargs="?", const=str(tables.site_file(name)), help=f"{text} (the bundled file if no path)")
    exp = sub.add_parser("export", help="write the static JSON for the frontend and its schema")
    exp.add_argument("scenario", nargs="?", help="scenario JSON (default: the bundled demo)")
    exp.add_argument("--out", default="out", help="directory for frontend.json and frontend.schema.json")
    exp.add_argument("--now", help="fix the generation time (ISO 8601) so the output is reproducible")
    exp.set_defaults(fn=export)
    sim = sub.add_parser("simulate-sensor", help="write the simulated year of soil-moisture sensor readings")
    sim.add_argument("--out", default=str(sensor_series.default_path()), help="where to write the readings CSV")
    sim.set_defaults(fn=simulate_sensor)
    cal = sub.add_parser("calibrate", help="refit the soil parameters to NASA SMAP L4 (needs scipy)")
    cal.add_argument("--smap-l4", default=str(tables.site_file(NASA_FILES["--smap-l4"][0])), help="NASA SMAP L4 CSV (SPL4SMGP.008) for the site's point (the bundled file by default)")
    cal.add_argument("--out", default="calibration.json", help="where to write the result; copy it to data/ to adopt it")
    cal.set_defaults(fn=calibrate)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
