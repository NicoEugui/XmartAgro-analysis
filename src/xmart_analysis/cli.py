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
from .engine import tables
from .engine.errors import EngineError
from .engine.i18n import LANGUAGES
from .worker.adapters.engine import EngineAnalyzer
from .worker.adapters.files import FileResults, load_scenario
from .worker.adapters.memory import MemoryInputs, MemoryReadings
from .worker.application import RunAnalysis
from .worker.config import Settings

DEMO = tables.DATA_DIR / "demo_scenario.json"
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
    """Run the validators whose input files were given (the producer survey always runs)."""
    context = engine_context.build_context()
    doc = {"survey": validation.survey.run(context)}
    if args.smap_l3:
        doc["smap"] = validation.smap.run(args.smap_l3, args.smap_l4, context)
    if args.modis_ndvi:
        doc["ndvi"] = validation.ndvi.run(args.modis_ndvi, context)
    if args.imerg:
        doc["imerg"] = validation.imerg.run(args.imerg, context)
        doc["rain_sensitivity"] = validation.rain_sensitivity.run(args.imerg, context)
    return doc


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


def frontend_document(scenario, now=None):
    """The frontend payload for a scenario file (the bundled demo by default)."""
    field_id, store = load_scenario(scenario or DEMO)
    analyzer = EngineAnalyzer()
    clock = (lambda: datetime.fromisoformat(now)) if now else (lambda: datetime.now(timezone.utc))
    use_case = RunAnalysis(MemoryReadings(store), MemoryInputs(store), FileResults("."), analyzer, Settings(), clock)
    answers, sensor_info, _, moment, _ = use_case.prepare(field_id)
    return payload.build(analyzer.analyze(answers, sensor_info), moment)


def export(args):
    """Write the static JSON for the frontend and the schema that documents it."""
    try:
        document = frontend_document(args.scenario, args.now)
    except EngineError as exc:
        print(json.dumps(exc.to_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "frontend.json").write_text(payload.dumps(document), encoding="utf-8")
    (out / "frontend.schema.json").write_text(schema.dumps(), encoding="utf-8")
    (out / "frontend.fields.md").write_text(schema.markdown(), encoding="utf-8")
    print("written:", ", ".join(str(out / name) for name in ("frontend.json", "frontend.schema.json", "frontend.fields.md")))
    return 0


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
        p.add_argument("--imerg", nargs="?", const=str(tables.site_file("imerg_daily.csv")),
                       help="NASA GPM IMERG Giovanni CSV for the site's cell (the bundled file if no path), adds the rain check")
        p.add_argument("--modis-ndvi", help="NASA MODIS MOD13Q1 CSV for the site, adds the vegetation check")
        p.add_argument("--smap-l3", help="NASA SMAP L3 CSV (SPL3SMP-E.006), adds the SMAP comparison")
        p.add_argument("--smap-l4", help="NASA SMAP L4 CSV (SPL4SMGP.008), adds the SMAP comparison")
    exp = sub.add_parser("export", help="write the static JSON for the frontend and its schema")
    exp.add_argument("scenario", nargs="?", help="scenario JSON (default: the bundled demo)")
    exp.add_argument("--out", default="out", help="directory for frontend.json and frontend.schema.json")
    exp.add_argument("--now", help="fix the generation time (ISO 8601) so the output is reproducible")
    exp.set_defaults(fn=export)
    cal = sub.add_parser("calibrate", help="refit the soil parameters to NASA SMAP L4 (needs scipy)")
    cal.add_argument("--smap-l4", required=True, help="NASA SMAP L4 CSV (SPL4SMGP.008) for the demo point")
    cal.add_argument("--out", default="calibration.json", help="where to write the result; copy it to data/ to adopt it")
    cal.set_defaults(fn=calibrate)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
