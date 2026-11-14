"""JSON Schema (draft 2020-12) of the document in `payload.py`: what every field means and where the panel uses it.

Each property has a `description` (the meaning) and an `x-used-in` (the screen and element that shows it). A test fails if one is
missing or if the payload has a field the schema does not know.
"""

import json

from .payload import SCHEMA_VERSION

HEADER = "Main screen · header «Tu campo hoy: N mm de agua útil»"
SOIL_CARD = "Main screen · card «Tu suelo»"
OPTION_CARD = "Main screen · option card"
PRODUCER = "Data screen · Productor «Tu campo»"
AGRONOMIST = "Data screen · Agrónomo «Datos técnicos del campo»"
CHART = "Agronomist chart · yearly result of each option"
CONTEXT = "Not drawn on the current screens: context for a header, a footer or the presentation"
DEFICIT_NOTE = ("A season is classed by the share of the crop's water demand left unmet in its critical stage: low below 10 %, "
                "moderate from 10 % to 30 %, high from 30 % (provisional team convention).")


def _with(node, description, used):
    node["description"] = description
    node["x-used-in"] = used
    return node


def s(description, used, **extra):
    return _with({"type": "string", **extra}, description, used)


def n(description, used, **extra):
    return _with({"type": "number", **extra}, description, used)


def i(description, used, **extra):
    return _with({"type": "integer", **extra}, description, used)


def b(description, used):
    return _with({"type": "boolean"}, description, used)


def text(description, used):
    return _with({"$ref": "#/$defs/text"}, description, used)


def arr(items, description, used):
    return _with({"type": "array", "items": items}, description, used)


def obj(description, used, properties):
    return _with({"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False},
                 description, used)


def mapping(values, description, used):
    return _with({"type": "object", "additionalProperties": values}, description, used)


def nullable(schema):
    inner = {k: v for k, v in schema.items() if k not in ("description", "x-used-in")}
    return {"description": schema["description"], "x-used-in": schema["x-used-in"], "anyOf": [inner, {"type": "null"}]}


def ref(name, description, used):
    return _with({"$ref": f"#/$defs/{name}"}, description, used)


DEFS = {
    "text": obj("A text in both languages. Show `en` or `es`; `key` is a stable id of the sentence in the label catalog.", "Every text",
                {"key": s("Stable id of the text.", "Every text"), "en": s("English text.", "Every text"),
                 "es": s("Spanish text.", "Every text")}),
    "season_counts": obj("Number of historical seasons (or crop-years of a rotation) in each deficit class. " + DEFICIT_NOTE, OPTION_CARD,
                         {"low_deficit": i("Seasons with low deficit.", OPTION_CARD),
                          "moderate_deficit": i("Seasons with moderate deficit.", OPTION_CARD),
                          "high_deficit": i("Seasons with high deficit.", OPTION_CARD)}),
    "drops": obj("The same counts split into ten parts by largest remainder: one drop each, light to dark. It is a share of historical "
                 "seasons, not a probability.", OPTION_CARD,
                 {"ok": i("Drops of low deficit: the water was enough (legend «tuvo agua»).", OPTION_CARD),
                  "tight": i("Drops of moderate deficit (legend «justa»).", OPTION_CARD),
                  "out": i("Drops of high deficit: the water ran short (legend «sin agua»).", OPTION_CARD)}),
}

SITE = obj("Where the model runs and what it is built on. Results describe this point only.", CONTEXT, {
    "climate": obj("The daily climate the model runs on.", CONTEXT, {
        "source": s("Where the climate comes from.", CONTEXT, enum=["nasa_power"]),
        "first_day": s("First day of the record, YYYY-MM-DD.", CONTEXT), "last_day": s("Last day of the record, YYYY-MM-DD.", CONTEXT),
        "seasons": i("Number of historical seasons built from it (the length of every `years` list).", CHART)}),
    "soil_calibration": obj("State of the soil parameters (fitted to NASA SMAP L4).", CONTEXT, {
        "current": b("True when the soil parameters were fitted at this point; false when they come from another point and are pending.", CONTEXT),
        "fitted_at": nullable(obj("The point where the soil parameters were fitted.", CONTEXT, {
            "latitude": n("Latitude, degrees.", CONTEXT), "longitude": n("Longitude, degrees.", CONTEXT)}))}),
    "note": text("Warning that the model describes this point only.", "Footer of the main screen")})

STATUS = obj("How far the results can be trusted. Always show the disclaimer.", "Footer of the main screen and the presentation", {
    "exploratory": b("Always true: scenarios from historical climate, not forecasts.", "Footer of the main screen"),
    "validated_for_field": b("Always false: nothing here is validated for a particular field.", "Footer of the main screen"),
    "disclaimer": text("Sentence to show with the results.", "Footer of the main screen"),
    "simulated_reading": b("True while the soil-moisture reading is simulated, not measured: show a «datos de ejemplo» banner.",
                           "Banner of the main screen"),
    "values_by_status": mapping(i("Number of values with that status.", CONTEXT),
                                "Count of the model's values by status: data, fitted, source, assumption (a team decision) or pending "
                                "(waiting for a dataset).", CONTEXT),
    "sources": arr(obj("A source the model cites.", CONTEXT, {"id": s("Source id.", CONTEXT), "title": s("Title.", CONTEXT),
                                                           "publisher": s("Publisher.", CONTEXT)}),
                   "The sources the model cites.", CONTEXT)})

SUMMARY = obj("Everything the main screen needs, in the shape of the API's summary.", "Main screen", {
    "field": obj("The place the analysis is for.", "Main screen · field name", {
        "id": s("Site id.", "Main screen · field name"), "name": s("Site name.", "Main screen · field name"),
        "department": s("Uruguayan department.", "Main screen · field name"), "lat": n("Latitude, degrees.", CONTEXT),
        "lon": n("Longitude, degrees.", CONTEXT)}),
    "mock": b("Always false: these are the model's results, not placeholder data. (`status.simulated_reading` says whether the reading "
              "is simulated.)", "Banner of the main screen"),
    "generated_at": s("When the analysis was run, ISO 8601.", "Main screen · «actualizado»", format="date-time"),
    "water": obj("Water in the soil.", HEADER, {
        "mm": n("Available water in mm that the scenarios start from, derived from the reading with assumed soil parameters. Show it "
                "as an estimate, never as measured water.", HEADER),
        "capacity_mm": n("Water the modelled soil can hold, mm.", HEADER),
        "source": s("Where the number comes from, in the API's vocabulary: always `sensor` here.", HEADER,
                    enum=["sensor", "smap_corrected", "balance"]),
        "reliability": s("How far to trust it: always `low` until the sensor is calibrated.", HEADER, enum=["low", "medium", "high"]),
        "updated_at": s("When the reading was taken, ISO 8601.", HEADER),
        "mm_status": s("derived_from_assumptions: the millimetres come from assumed soil parameters.", HEADER),
        "is_simulated": b("True when the reading is simulated.", HEADER),
        "volumetric_moisture": n("The reading itself, volumetric moisture in m3/m3 (0 to 0.6).", HEADER)}),
    "soil": obj("Soil health. The model has no soil diagnosis yet, so the state is null.", SOIL_CARD, {
        "state": nullable(s("good, fair or poor; null while there is no diagnosis.", SOIL_CARD, enum=["good", "fair", "poor"])),
        "trend": nullable(s("improving, stable or declining; null while there is no diagnosis.", SOIL_CARD,
                            enum=["improving", "stable", "declining"])),
        "precision": s("How precise the estimate is: always `low` for now.", SOIL_CARD, enum=["low", "medium", "high"]),
        "reasons": arr(text("A reason for the soil state.", SOIL_CARD), "Reasons for the state; empty while there is no diagnosis.", SOIL_CARD),
        "missing": arr(text("A datum that would improve the estimate.", SOIL_CARD),
                       "What is missing, for the line «Estimación de precisión baja: falta …».", SOIL_CARD)}),
    "options": arr(obj("One option to compare: the crop already sown or a rotation reported by the surveyed producers. Options are never "
                       "ranked.", OPTION_CARD, {
        "id": s("Stable id, e.g. survey_03 or barley@06-10.", OPTION_CARD),
        "name": text("Name of the option, e.g. «Rotación observada 3».", OPTION_CARD + " · title"),
        "is_current": b("True for the crop the producer has sown now: «Tu rotación actual», red outline.", OPTION_CARD + " · badge"),
        "water_risk": nullable(s("low, medium or high, from the number of high-deficit drops (provisional thresholds); null when nothing was "
                                 "simulated.", OPTION_CARD + " · pill «Agua: riesgo …»", enum=["low", "medium", "high"])),
        "drops": nullable(ref("drops", "The ten drops to draw; null when nothing was simulated (e.g. the cycle already ended).",
                              OPTION_CARD + " · ten drops")),
        "sentence": text("One sentence for the card, e.g. «En 4 de cada 10 zafras históricas faltó agua en la etapa crítica».",
                         OPTION_CARD + " · sentence"),
        "soil_effect": nullable(s("improves, stays or worsens; always null: the model does not estimate it.", OPTION_CARD + " · «Suelo: …»",
                                  enum=["improves", "stays", "worsens"])),
        "soil_reason": nullable(text("Why the soil effect; always null.", OPTION_CARD + " · «Suelo: …»")),
        "why": nullable(text("Longer explanation; always null.", "Option detail view")),
        "evidence": arr(text("Evidence.", "Option detail view"), "Evidence for the option; empty for now.", "Option detail view"),
        "benefits": arr(text("A benefit.", "Option detail view"), "Benefits; empty for now.", "Option detail view"),
        "gaps": arr(text("A caveat about the option.", "Option detail view"), "What the evaluation does not cover (fixed cycle length, far "
                                                                                 "sowing date...).", "Option detail view"),
        "risks": arr(text("A risk.", "Option detail view"), "Risks; empty for now.", "Option detail view"),
        "kind": s("What the option is.", OPTION_CARD, enum=["crop", "rotation"]),
        "detail": text("The exact counts as a sentence, e.g. «104 de 280 combinaciones año-zafra con déficit alto».", "Option detail view"),
        "sowing": nullable(s("Sowing day of a crop, MM-DD; null for a rotation.", OPTION_CARD + " · subtitle")),
        "critical_window": nullable(obj("Critical stage of the crop.", OPTION_CARD + " · subtitle", {
            "start": s("DD/MM.", OPTION_CARD + " · subtitle"), "end": s("DD/MM.", OPTION_CARD + " · subtitle")})),
        "cycle_status": nullable(s("For the crop already sown: where it is in its cycle.", OPTION_CARD + " · sentence",
                                   enum=["cycle_ended", "critical_stage_passed", "critical_stage_ahead", "in_critical_stage"])),
        "evaluated": i("Seasons (crop) or season-crop combinations (rotation) evaluated; 0 when nothing can be simulated.",
                       "Option detail view"),
        "high_deficit": nullable(i("How many of the evaluated ones fell in high deficit.", "Option detail view")),
        "season_counts": nullable(ref("season_counts", "Counts per deficit class; null when nothing was simulated.", "Option detail view")),
        "crops": arr(obj("A crop of a rotation as the producer wrote it.", OPTION_CARD + " · crops line", {
            "name": text("Crop name, as modelled (e.g. «Soja de segunda»).", OPTION_CARD + " · crops line"),
            "status": s("modelled: its stress is reported; cover_without_risk: a cover crop with no stress of its own; not_modelled: no "
                        "parameters yet.", OPTION_CARD + " · crops line", enum=["modelled", "cover_without_risk", "not_modelled"])}),
                     "Crops of a rotation in the written order; empty for a crop.", OPTION_CARD + " · crops line"),
        "note": nullable(text("How a rotation is evaluated: each crop-year on its own, order not simulated.", "Option detail view"))}),
        "Options to compare, in the order to show them. The current crop comes first.", OPTION_CARD)})

INPUTS = obj("What the producer and the agronomist entered, normalised: crops as ids, days as MM-DD.", "Data screen", {
    "farmer": obj("The producer's part of the form.", PRODUCER, {
        "current_crop": obj("The crop sown now.", PRODUCER + " · «¿Qué tienes sembrado ahora?»", {
            "crop": nullable(s("Crop id from catalog.crops; null if none was entered.", PRODUCER + " · crop chips")),
            "sowing_day": nullable(s("Day it was sown, MM-DD.", PRODUCER + " · «¿Cuándo lo sembraste?»"))}),
        "seasons": arr(obj("One past season.", PRODUCER + " · «Tus últimas zafras»", {
            "season": s("Season, e.g. 2025/26.", PRODUCER + " · season title"),
            "crops": arr(s("Crop id from catalog.history_crops.", PRODUCER + " · season crops"),
                         "Crops grown in the season (e.g. barley + soybean_2nd), shown joined by « + ».", PRODUCER + " · season crops"),
            "rating": nullable(i("How the season went, 1 (muy mal) to 5 (excelente).", PRODUCER + " · rating buttons", minimum=1, maximum=5)),
            "yield_kg_ha": nullable(n("Yield in kg/ha, optional, used instead of the scale.", PRODUCER + " · «puedes escribirlo»")),
            "confirmed": b("False while the season is only a suggestion (e.g. from satellite).", PRODUCER + " · chip «sugeridas»")}),
                     "The producer's last seasons.", PRODUCER + " · «Tus últimas zafras»")}),
    "agronomist": obj("The agronomist's part of the form; every datum is optional.", AGRONOMIST, {
        "soil_test": obj("The soil analysis.", AGRONOMIST + " · «Análisis de suelo»", {
            "date": nullable(s("Date of the analysis, YYYY-MM.", AGRONOMIST + " · «Fecha del análisis»")),
            "om_pct": nullable(n("Organic matter, %.", AGRONOMIST + " · «Materia orgánica (%)»")),
            "p_bray_ppm": nullable(n("Phosphorus (Bray), ppm.", AGRONOMIST + " · «Fósforo Bray (ppm)»")),
            "ph": nullable(n("pH.", AGRONOMIST + " · «pH»"))}),
        "erosion_t_ha_yr": nullable(n("Estimated erosion, t/ha/year.", AGRONOMIST + " · «Erosión estimada»")),
        "soil_type": obj("The soil type.", AGRONOMIST + " · «Tipo de suelo»", {
            "description": nullable(s("CONEAT code and soil name, e.g. «CONEAT 10.8b, Brunosol».", AGRONOMIST + " · soil card")),
            "confirmed": nullable(b("Whether the agronomist confirmed it (buttons «Confirmar» / «Corregir»).", AGRONOMIST + " · soil card"))})})})

SCENARIOS = obj("The result of every historical season for every option, in the shape of the API's scenarios.", CHART, {
    "from_year": i("Start year of the first season.", CHART), "to_year": i("Start year of the last season.", CHART),
    "options": arr(obj("One option.", CHART, {
        "id": s("Same id as in summary.options.", CHART), "name": text("Name of the option.", CHART),
        "years": arr(nullable(s("ok, tight or out for that season; null when the season could not be evaluated.", CHART,
                                enum=["ok", "tight", "out"])),
                     "One result per season from `from_year` to `to_year`, in order; for a rotation, the class of the mean unmet demand of its modelled crops that season; empty when nothing was simulated.", CHART)}),
        "Options, in the same order as summary.options.", CHART)})

CATALOG = obj("The closed lists the forms offer: nothing is typed as free text.", "Data screen", {
    "crops": arr(obj("A crop the producer can pick as sown now.", PRODUCER + " · crop chips", {
        "id": s("Crop id.", PRODUCER + " · crop chips"), "name": text("Name to show.", PRODUCER + " · crop chips")}),
        "Crops that can be sown on a date.", PRODUCER + " · crop chips"),
    "history_crops": arr(obj("A crop that can be part of a past season.", PRODUCER + " · season crops", {
        "id": s("Crop id.", PRODUCER + " · season crops"), "name": text("Name to show.", PRODUCER + " · season crops")}),
        "Crops valid in the history, including ones the model cannot simulate yet.", PRODUCER + " · season crops"),
    "ratings": arr(obj("A point of the rating scale.", PRODUCER + " · rating buttons", {
        "value": i("1 to 5.", PRODUCER + " · rating buttons"), "label": text("Button text, e.g. «Muy mal».", PRODUCER + " · rating buttons")}),
        "The rating scale.", PRODUCER + " · rating buttons"),
    "seasons": arr(s("Season, e.g. 2025/26.", PRODUCER + " · season selector"), "Seasons the history can cover, newest first.",
                   PRODUCER + " · season selector")})


def build():
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "XmartAgro frontend data",
            "description": "Static data for the XmartAgro panel in the shape of its API contract (summary, inputs, scenarios): one "
                           "exploratory analysis at one NASA POWER point. Text fields are {key, en, es}. Nothing here is a forecast, a yield "
                           "prediction or a recommendation. Every field has `x-used-in`: where the panel shows it.",
            "x-used-in": "The whole document: one file the panel reads, with no API call", "type": "object", "$defs": DEFS,
            "properties": {"schema_version": s("Version of this schema.", CONTEXT, const=SCHEMA_VERSION),
                           "generated_at": s("When the analysis was run, ISO 8601.", CONTEXT, format="date-time"),
                           "site": SITE, "status": STATUS, "summary": SUMMARY, "inputs": INPUTS, "scenarios": SCENARIOS, "catalog": CATALOG},
            "required": ["schema_version", "generated_at", "site", "status", "summary", "inputs", "scenarios", "catalog"],
            "additionalProperties": False}


def dumps():
    return json.dumps(build(), ensure_ascii=False, indent=2) + "\n"


def _ref(node):
    return node["$ref"].rsplit("/", 1)[1] if "$ref" in node else None


def _is_text(node):
    return _ref(node) == "text" or any(_ref(option) == "text" for option in node.get("anyOf", []))


def _kind(node, root):
    if _is_text(node):
        return "text or null" if "anyOf" in node else "text"
    if "$ref" in node:
        return _kind(root["$defs"][_ref(node)], root)
    if "anyOf" in node:
        inner = [_kind(option, root) for option in node["anyOf"] if option.get("type") != "null"]
        return f"{inner[0]} or null"
    if "enum" in node:
        return "one of " + ", ".join(f"`{v}`" for v in node["enum"])
    return node.get("type", "any")


def fields(node=None, root=None, path=""):
    """(path, type, meaning, used in) of every field, flattened; `[]` marks array items and `{name}` the free keys of a map."""
    root = root or build()
    node = node or root
    out = []
    if _is_text(node):
        return out
    target = node
    if "$ref" in target:
        target = root["$defs"][_ref(target)]
    if "anyOf" in target:
        target = next(option for option in target["anyOf"] if option.get("type") != "null")

    def row(name, child):
        return (name, _kind(child, root), child.get("description", ""), child.get("x-used-in", ""))
    for name, child in target.get("properties", {}).items():
        here = f"{path}.{name}".lstrip(".")
        out.append(row(here, child))
        out += fields(child, root, here)
    if target.get("type") == "array":
        out += fields(target["items"], root, f"{path}[]")
    if isinstance(target.get("additionalProperties"), dict):
        value = target["additionalProperties"]
        out.append(row(f"{path}.{{name}}", value))
        out += fields(value, root, f"{path}.{{name}}")
    return out


def markdown():
    """The same contract as a table a person can read."""
    lines = ["# Frontend data: what every field means and where it is used", "",
             "Generated from `frontend.schema.json` (do not edit by hand). Text fields are `{key, en, es}`: show `en` or `es`. "
             "`[]` marks the items of a list and `{name}` the free keys of a map. The shape follows the panel's API contract "
             "(`summary`, `inputs`, `scenarios`).", "", "| Field | Type | Meaning | Used in |", "| --- | --- | --- | --- |"]
    lines += [f"| `{p}` | {k} | {m.replace('|', '/')} | {u.replace('|', '/')} |" for p, k, m, u in fields()]
    return "\n".join(lines) + "\n"
