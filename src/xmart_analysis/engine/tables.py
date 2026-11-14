"""Single reader of the model's data (`data/`).

Layout: shared tables at the top (`model_constants.csv`, `crop_parameters.csv`, `sources.csv`...), one folder per site under
`sites/<site_id>/` (the climate, the calibration and the constants of that place, and nothing else) and the
team's own producer survey under `survey/`. `sites.csv` says which site the model runs on (`XMART_SITE` overrides it) and
`datasets.csv` lists every dataset file with its group, role, source and checksum.

Every number the model uses that is not a formula lives in a table next to its status and source (see `sources.csv`); the
engine modules read them here and hold no parameter values of their own. `provenance()` lists every value with its source and
`validate()` fails if one has none or if a dataset no longer matches its manifest entry.
"""

import csv
import hashlib
import json
import os
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from .errors import EngineError

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
STATUSES = ("source", "fitted", "data", "assumption", "pending")  # pending: a value waiting for a dataset
NEEDS_SOURCE = ("source", "fitted", "data")
GROUPS = ("sowing", "cycle", "kc", "p")
SITE_CONSTANTS = ("latitude", "longitude", "season_first_year", "season_last_year")
SITE_ENV = "XMART_SITE"


@lru_cache(maxsize=None)
def read(name):
    with open(DATA_DIR / f"{name}.csv", newline="", encoding="utf-8") as stream:
        return tuple(csv.DictReader(stream))


def number(text):
    value = float(text)
    return int(value) if value.is_integer() and "." not in text else value


def sites():
    return {r["site_id"]: r for r in read("sites")}


def active_site():
    """The site the model runs on: `XMART_SITE`, else the one marked active in `sites.csv`."""
    table, chosen = sites(), os.environ.get(SITE_ENV)
    if chosen is None:
        actives = [r["site_id"] for r in table.values() if r["active"] == "1"]
        chosen = actives[0] if actives else None
    if chosen not in table:
        raise EngineError("unknown_site", "site", f"Unknown site {chosen!r}; known: {sorted(table)}", site=chosen,
                          known=sorted(table))
    return chosen


def site_dir(site_id=None):
    return DATA_DIR / "sites" / (site_id or active_site())


def site_file(name, site_id=None):
    return site_dir(site_id) / name


def calibration_path(site_id=None):
    return site_file("calibration.json", site_id)


def _parse_constants(rows):
    out = {}
    for row in rows:
        raw = row["value"]
        out[row["name"]] = tuple(number(x) for x in raw.split(";")) if ";" in raw else number(raw)
    return out


@lru_cache(maxsize=None)
def constants_of(site_id):
    """Shared constants plus the constants of one site."""
    with open(site_file("constants.csv", site_id), newline="", encoding="utf-8") as stream:
        return {**_parse_constants(read("model_constants")), **_parse_constants(csv.DictReader(stream))}


def constants():
    return constants_of(active_site())


def constant(name):
    try:
        return constants()[name]
    except KeyError:
        raise EngineError("unknown_constant", "constants", f"No constant named {name!r} for site {active_site()!r}",
                          name=name) from None


def season_years():
    return list(range(constant("season_first_year"), constant("season_last_year") + 1))


def month_day(prefix):
    return (constant(f"{prefix}_month"), constant(f"{prefix}_day"))


def crops():
    out = {}
    for row in read("crop_parameters"):
        if not int(row["supported"]):
            continue
        spec = {"p": number(row["p"]), "stages": tuple(number(row[f"stage_{s}"]) for s in
                                                       ("initial", "development", "mid", "late")),
                "kc": tuple(number(row[f"kc_{s}"]) for s in ("initial", "mid", "final")),
                "counts_risk": bool(int(row["counts_risk"])), "status": {group: row["status"] for group in GROUPS}}
        if int(row["perennial"]):
            spec["perennial"] = True
        else:
            spec["sowing"] = (number(row["sowing_month"]), number(row["sowing_day"]))
        out[row["crop"]] = spec
    return out


def unsupported_crops():
    return tuple(r["crop"] for r in read("crop_parameters") if not int(r["supported"]))


def calibration_is_current():
    """True when the soil parameters were fitted at the model point."""
    fit = calibration()
    point = fit.get("point", {})
    here = (constant("latitude"), constant("longitude"))
    return abs(point.get("latitude", 999) - here[0]) < 0.01 and abs(point.get("longitude", 999) - here[1]) < 0.01


def survey_seasons():
    """{season: number of respondents who named it as unfavourable} from the producer survey."""
    out = {}
    for row in read("survey/survey_unfavorable_seasons"):
        out[row["season"]] = out.get(row["season"], 0) + 1
    return out


def survey_rotations():
    """{respondent: [(group, crop, years)]}: the crops of each rotation in the order the producer wrote them."""
    out = {}
    for row in sorted(read("survey/survey_rotations"), key=lambda r: (int(r["respondent"]), int(r["position"]))):
        out.setdefault(int(row["respondent"]), []).append((int(row["group"]), row["crop"], row["years"]))
    return out


def survey_crop_map():
    """{(survey crop, previous crop or ""): engine crop or None} (how written crops become modelled crops)."""
    return {(r["survey_crop"], r["previous_crop"]): r["engine_crop"] or None for r in read("survey_crop_map")}


def calibration():
    return json.loads(calibration_path().read_text(encoding="utf-8"))


def sources():
    return {r["source_ref"]: r for r in read("sources")}


def manifest():
    return read("datasets")


def describe(relative_path):
    """Checksum, row count and period of a dataset file, computed from the file."""
    path = DATA_DIR / relative_path
    info = {"rows": "", "period": "", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    if path.suffix != ".csv":
        return info
    text = path.read_text(encoding="utf-8")
    if "-END HEADER-" in text:  # NASA POWER export
        data = list(csv.DictReader(text.split("-END HEADER-")[1].strip().splitlines()))
        days = [date(int(r["YEAR"]), 1, 1) + timedelta(days=int(r["DOY"]) - 1) for r in data]
    else:
        data = list(csv.DictReader(text.splitlines()))
        days = [date.fromisoformat(r["date"]) for r in data] if data and "date" in data[0] else []
    info["rows"] = str(len(data))
    info["period"] = f"{days[0]}/{days[-1]}" if days else ""
    return info


def provenance():
    """Every table value with its status and source references."""
    rows = [{"table": "crop_parameters", "item": r["crop"], "status": r["status"], "source_ref": r["source_ref"],
             "note": "waiting for a dataset" if r["status"] == "pending" else ""}
            for r in read("crop_parameters") if int(r["supported"])]
    rows += [{"table": "model_constants", "item": r["name"], "status": r["status"], "source_ref": r["source_ref"],
              "note": r["note"]} for r in read("model_constants")]
    with open(site_file("constants.csv"), newline="", encoding="utf-8") as stream:
        rows += [{"table": f"site:{active_site()}", "item": r["name"], "status": r["status"], "source_ref": r["source_ref"],
                  "note": r["note"]} for r in csv.DictReader(stream)]
    rows += [{"table": "datasets", "item": r["path"], "status": "data", "source_ref": r["source_ref"],
              "note": f"{r['group']}, {r['role']}"} for r in manifest() if r["kind"] != "fit"]
    rows += [{"table": "survey_crop_map", "item": f"{r['survey_crop']}|{r['previous_crop']}", "status": "assumption",
              "source_ref": "", "note": r["note"]} for r in read("survey_crop_map")]
    fit = calibration()
    current = calibration_is_current()
    rows += [{"table": "calibration", "item": name, "status": "fitted" if current else "pending",
              "source_ref": "smap_l4;nasa_power" if current else "",
              "note": (f"{value} fitted to {fit['target']} over {fit['calibration']['period'][0]} to {fit['calibration']['period'][1]}"
                       if current else f"{value} fitted at {fit.get('point')}: refit with SMAP L4 at the model point")} for name, value in fit["parameters"].items()]
    return rows


def check_sites():
    problems, table = [], sites()
    if sum(r["active"] == "1" for r in table.values()) != 1:
        problems.append("sites.csv: exactly one site must be active")
    for site_id, row in table.items():
        folder = DATA_DIR / "sites" / site_id
        for name in ("constants.csv", "power_daily.csv"):
            if not (folder / name).exists():
                problems.append(f"sites/{site_id}: missing {name}")
        if (folder / "constants.csv").exists():
            have = {r["name"] for r in csv.DictReader(open(folder / "constants.csv", encoding="utf-8"))}
            problems += [f"sites/{site_id}/constants.csv: missing {n}" for n in SITE_CONSTANTS if n not in have]
        if not (folder / "calibration.json").exists():
            problems.append(f"sites/{site_id}: missing calibration.json")
    return problems


def check_manifest():
    problems, listed = [], set()
    for row in manifest():
        path, group = row["path"], row["group"]
        listed.add(path)
        if not (DATA_DIR / path).exists():
            problems.append(f"datasets.csv: {path} does not exist")
            continue
        folder = "survey/" if group == "survey" else f"sites/{group.split(':')[1]}/" if group.startswith("site:") else None
        if folder is None or not path.startswith(folder) or (group.startswith("site:") and group.split(":")[1] not in sites()):
            problems.append(f"datasets.csv: {path} does not belong to group {group!r}")
        for key, value in describe(path).items():
            if row[key] != value:
                problems.append(f"datasets.csv: {path} {key} is {value!r}, the manifest says {row[key]!r} (refresh it if intended)")
    on_disk = {str(p.relative_to(DATA_DIR)) for pattern in ("sites/*/*", "survey/*") for p in DATA_DIR.glob(pattern)
               if p.is_file() and p.name != "constants.csv"}
    problems += [f"datasets.csv: {p} is not listed" for p in sorted(on_disk - listed)]
    return problems


def validate():
    """Problems that make a table untrustworthy (empty list if none)."""
    problems, known = check_sites() + check_manifest(), sources()
    for row in provenance():
        where = f"{row['table']}:{row['item']}"
        if row["status"] not in STATUSES:
            problems.append(f"{where}: unknown status {row['status']!r}")
        refs = [x for x in row["source_ref"].split(";") if x]
        if row["status"] in NEEDS_SOURCE and not refs:
            problems.append(f"{where}: a {row['status']} value needs a source_ref")
        problems += [f"{where}: source {x!r} is not in sources.csv" for x in refs if x not in known]
        if row["status"] == "assumption" and not row["note"].strip():
            problems.append(f"{where}: an assumption needs a note")
    return problems
