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

BADGE = "Badge at the top of every screen"
STATUS = obj("How far the results can be trusted. Always show the disclaimer.", "Footer of the main screen and the presentation", {
    "mode": s("demo while any input is simulated, live when every input is measured or entered by a person. The panel decides `pending` (a new field the "
              "nightly run has not reached) and `offline` (it cannot read the file) itself, and the error document says `error`; catalog.modes explains the five.", BADGE, enum=["demo", "live"]),
    "badge": text("The text of the badge for this mode, e.g. «Modo demo · datos simulados». Show it at the top of every screen while the mode is demo.",
                  BADGE),
    "simulated_inputs": arr(s("What is simulated.", BADGE, enum=["sensor_readings", "training_panel"]),
                            "The inputs that are simulated, so the badge can say which numbers they feed; empty when the mode is live.", BADGE),
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
        "volumetric_moisture": n("Volumetric moisture in m3/m3 (0 to 0.6) the scenarios start from: the model's own state corrected by the readings "
                                 "of the last year when `series` is given, otherwise the last reading itself.", HEADER),
        "reading_moisture": nullable(n("The last reading itself, m3/m3; null when there is no series and `volumetric_moisture` is the reading.",
                                       HEADER + " · small print")),
        "series": nullable(obj("How the state above was reached from the readings of the last year (simulated while `is_simulated`).",
                               "Main screen · moisture chart «sensor vs modelo»", {
            "method": s("state_correction: each day the modelled water moves a share `gain` of the way to the reading.", "Main screen · moisture chart «sensor vs modelo»",
                        enum=["state_correction"]),
            "gain": n("Share of the gap between model and reading corrected each day (0 ignores the sensor, 1 adopts it).", "Main screen · moisture chart «sensor vs modelo»"),
            "days": i("Days with a reading.", "Main screen · moisture chart «sensor vs modelo»"),
            "carried_days": i("Days after the last reading the model ran on its own to reach the last day of the climate record (0 with a sensor that reports every day).",
                              "Main screen · moisture chart «sensor vs modelo»"),
            "period": arr(s("A date, YYYY-MM-DD.", "Main screen · moisture chart «sensor vs modelo»"), "First and last day of the series.",
                          "Main screen · moisture chart «sensor vs modelo»"),
            "history": arr(obj("One day.", "Main screen · moisture chart «sensor vs modelo»", {
                "date": s("The day, YYYY-MM-DD.", "Main screen · moisture chart «sensor vs modelo»"),
                "reading": n("The reading of that day, m3/m3.", "Main screen · moisture chart «sensor vs modelo»"),
                "modeled": n("The model's state that day after correcting toward the reading, m3/m3.", "Main screen · moisture chart «sensor vs modelo»")}),
                           "Reading and modelled state of every day, oldest first.", "Main screen · moisture chart «sensor vs modelo»")})),
        "correction": nullable(obj("Set when the satellite as model B corrects it stands in for the sensor: the readings of `series` are that corrected satellite.", HEADER + " · small print", {
            "model": s("The model: B.", HEADER + " · small print", enum=["B"]),
            "version": i("Version of model B used.", HEADER + " · small print"),
            "last_satellite_day": s("Last day with a satellite value, YYYY-MM-DD.", HEADER + " · small print"),
            "note": text("What this water rests on, to show as small print.", HEADER + " · small print")}))}),
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
        "drops": nullable(ref("drops", "The ten drops to draw; null when nothing was simulated (e.g. the cycle already ended). With `risk_basis.source` model_a they are model A's, otherwise the fixed cuts'.",
                              OPTION_CARD + " · ten drops")),
        "risk_basis": obj("What `drops` and `water_risk` rest on, with the fixed cuts beside them to compare.", OPTION_CARD + " · small print", {
            "source": s("model_a when the published model A reads the seasons, fixed_cuts when only the fixed stress cuts do.", OPTION_CARD + " · small print",
                        enum=["model_a", "fixed_cuts"]),
            "model_version": nullable(i("Version of model A used; null with the fixed cuts.", OPTION_CARD + " · small print")),
            "fixed_cuts_drops": nullable(ref("drops", "The drops the fixed cuts of stress give.", OPTION_CARD + " · small print")),
            "fixed_cuts_water_risk": nullable(s("low, medium or high from the fixed cuts.", OPTION_CARD + " · small print", enum=["low", "medium", "high"]))}),
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
                   PRODUCER + " · season selector"),
    "modes": arr(obj("A state the panel can be in.", BADGE, {
        "id": s("demo, live, pending, error or offline.", BADGE, enum=["demo", "live", "pending", "error", "offline"]),
        "badge": text("Badge text for the state.", BADGE), "meaning": text("When the state applies and what to show.", BADGE)}),
        "The four states of the panel with the text of each badge, `offline` included (only the panel can know it).", BADGE)})

ERROR_STATUS = obj("The analysis failed: the badge and what went wrong.", BADGE, {
    "mode": s("Always `error`.", BADGE, const="error"), "badge": text("Badge text, «Análisis no disponible».", BADGE),
    "error": obj("What failed.", "Error message of the screen", {
        "code": s("Stable code of the failure, e.g. climate_gap, invalid_answers, internal_error.", "Error message of the screen"),
        "field": nullable(s("The field or input that failed; null when it is not tied to one.", "Error message of the screen")),
        "message": s("What happened, in English, for a person to read.", "Error message of the screen")})})


CHART_USE = "Charts screen · one chart per entry, mirroring a figure of the experiment log"
_NUMBER_OR_TEXT = {"anyOf": [{"type": "string"}, {"type": "number"}]}

CHARTS = arr(obj("One chart: the data behind a figure of the experiment log, columnar (one shared x, one list of values per series).", CHART_USE, {
    "id": s("Stable id of the chart, e.g. sensor_series or sowing_maize.", CHART_USE),
    "figure": s("The figure of reports/experiments.md it mirrors (retrospective, sowing, survey, smap, ndvi, imerg, rain_decision, sensor, sensor_windows, "
                "sensor_recalibration); a figure can have several charts.", CHART_USE),
    "group": s("Where to file it: sowing (what happens if a crop is sown on a date), validation (against independent data), rain (POWER vs IMERG), sensor "
               "(the simulated-sensor experiments) or retrospective (what the tool would have said before each past season).", CHART_USE,
               enum=["sowing", "validation", "rain", "sensor", "retrospective"]),
    "title": text("Title of the chart.", CHART_USE + " · title"),
    "note": nullable(text("The caveat to print under the chart.", CHART_USE + " · small print")),
    "x": obj("The horizontal axis, shared by every series.", CHART_USE + " · x axis", {
        "type": s("category: the values are ids (names tells how to show them); date: YYYY-MM-DD; month_day: MM-DD, a calendar day without year; "
                  "number: a quantity, where a point is placed by its value.", CHART_USE + " · x axis", enum=["category", "date", "month_day", "number"]),
        "label": nullable(text("Axis title.", CHART_USE + " · x axis")),
        "values": _with({"type": "array", "items": _with(dict(_NUMBER_OR_TEXT), "One position on the axis.", CHART_USE + " · x axis")},
                        "The positions, in order: ids, dates or numbers according to `type`.", CHART_USE + " · x axis"),
        "names": nullable(arr(text("How to show that value.", CHART_USE + " · x axis"), "One name per value, when the ids need one (runs, soils, predictors); null otherwise.",
                              CHART_USE + " · x axis")),
        "tags": nullable(arr(s("A language-neutral tag.", CHART_USE + " · point tooltip"), "One tag per value, for scatter charts where the position is a quantity (the season of each point); null otherwise.",
                             CHART_USE + " · point tooltip"))}),
    "y": obj("The vertical axis.", CHART_USE + " · y axis", {
        "label": nullable(text("Axis title.", CHART_USE + " · y axis")),
        "unit": nullable(s("Unit of the values: m3/m3 or mm; null for counts, shares and scores.", CHART_USE + " · y axis"))}),
    "stacked": b("True when the series are parts of one bar (stack them) instead of bars side by side.", CHART_USE),
    "simulated": b("True when the data comes from a simulated sensor or a simulated reading: show the demo badge on it.", CHART_USE + " · badge"),
    "source": s("Where the numbers come from: nasa_power, gpm_imerg, smap_l3, modis_ndvi, producer_survey, simulated_sensor or simulated_panel.", CHART_USE + " · small print"),
    "series": arr(obj("One series.", CHART_USE, {
        "id": s("Id of the series.", CHART_USE),
        "label": text("Legend entry.", CHART_USE + " · legend"),
        "style": s("How to draw it: bar, line or points.", CHART_USE, enum=["bar", "line", "points"]),
        "values": arr(nullable(n("The value at that position.", CHART_USE)), "One value per position of `x.values`, in the same order; null when there is none.", CHART_USE)}),
        "The series to draw.", CHART_USE)}),
    "The charts, in a fixed order: the data behind every figure of the experiment log.", CHART_USE)


LEARN = "Model screen · what the three models add to the analysis"
_OF_10 = lambda what: obj(what, LEARN, {"ok": i("Seasons out of 10 with enough water.", LEARN), "tight": i("Seasons out of 10 with tight water.", LEARN),  # noqa: E731
                                        "out": i("Seasons out of 10 without water.", LEARN)})
LEARNING = nullable(obj("What the models A, B and C add: their versions and how well they did, model A's reading of every option, model B's correction of the satellite and model C's "
                        "proposal of the crop history. Null when no registry of trained models was given.", LEARN, {
    "simulated": b("True while the models were trained on the simulated panel: show the demo badge on it.", LEARN + " · badge"),
    "note": text("What the numbers mean and do not mean.", LEARN + " · small print"),
    "models": arr(obj("One published model.", LEARN + " · model card", {
        "id": s("A, B or C.", LEARN + " · model card", enum=["A", "B", "C"]),
        "role": text("What the model does.", LEARN + " · model card"),
        "version": i("Version number of the published model.", LEARN + " · model card"),
        "state": s("published, candidate or retired; only published models are shown.", LEARN + " · model card", enum=["published", "candidate", "retired"]),
        "trained_on": s("Date of the training, YYYY-MM-DD.", LEARN + " · model card"),
        "examples": i("Examples the model learned from.", LEARN + " · model card"),
        "fields": i("Fields those examples come from.", LEARN + " · model card"),
        "simulated_data": b("True when every example was simulated.", LEARN + " · badge"),
        "metric": obj("How the model did on fields it never saw, against the fixed rule it replaces.", LEARN + " · model card", {
            "name": text("The metric.", LEARN + " · model card"), "value": n("The model's value.", LEARN + " · model card"),
            "fixed_rule_name": text("The metric of the fixed rule.", LEARN + " · model card"),
            "fixed_rule": n("The fixed rule's value.", LEARN + " · model card"),
            "lower_is_better": b("True for an error, false for an accuracy.", LEARN + " · model card"),
            "better": b("True when the model beats the fixed rule.", LEARN + " · model card")}),
        "reason": s("Why it was published or not.", LEARN + " · model card")}), "The published models, B, A and C.", LEARN),
    "options": arr(obj("Model A's reading of one option, next to the fixed cuts'.", LEARN + " · option card", {
        "id": s("Id of the option, as in summary.options.", LEARN + " · option card"),
        "model_version": i("Version of model A used.", LEARN + " · option card"),
        "seasons": i("Crop-seasons read: the ones the option's drops count (summary.options.evaluated).", LEARN + " · option card"),
        "of_10": _OF_10("Of 10 seasons, how many model A expects the producer to call good (ok), normal (tight) or bad (out)."),
        "water_risk": nullable(s("low, medium or high from model A's drops.", LEARN + " · option card", enum=["low", "medium", "high"])),
        "fixed_cuts_of_10": _OF_10("The same with the fixed cuts of stress (what summary.options.drops shows)."),
        "fixed_cuts_water_risk": nullable(s("low, medium or high from the fixed cuts.", LEARN + " · option card", enum=["low", "medium", "high"]))}),
        "One entry per option with seasons to read.", LEARN),
    "satellite": nullable(obj("Model B on the last days of the demo field: the satellite as it is, corrected, and the sensor.", LEARN + " · satellite chart", {
        "model_version": i("Version of model B used.", LEARN + " · satellite chart"),
        "field_id": s("The field.", LEARN + " · satellite chart"),
        "dates": arr(s("A day, YYYY-MM-DD.", LEARN + " · satellite chart"), "The days.", LEARN + " · satellite chart"),
        "satellite": arr(n("SMAP root-zone moisture as delivered.", LEARN + " · satellite chart"), "One value per day.", LEARN + " · satellite chart"),
        "corrected": arr(n("Moisture after model B.", LEARN + " · satellite chart"), "One value per day.", LEARN + " · satellite chart"),
        "sensor": arr(n("Calibrated sensor moisture of the field.", LEARN + " · satellite chart"), "One value per day.", LEARN + " · satellite chart"),
        "rmse": obj("Error against the sensor over these days.", LEARN + " · satellite chart", {
            "satellite": n("Error of the satellite as it is.", LEARN + " · satellite chart"), "corrected": n("Error after model B.", LEARN + " · satellite chart")}),
        "unit": s("m3/m3.", LEARN + " · satellite chart"),
        "sensor_simulated": b("True while the sensor is simulated.", LEARN + " · badge"),
        "in_sample": b("True when the field is one the model learned from, so this is not a test.", LEARN + " · small print"),
        "note": text("The caveat.", LEARN + " · small print")})),
    "crop_history": arr(obj("Model C's proposal of what grew in one season, for the producer to confirm.", LEARN + " · history proposal", {
        "season": s("The season, e.g. 2022/23.", LEARN + " · history proposal"),
        "crop": s("Crop id or `fallow`.", LEARN + " · history proposal"),
        "crop_name": text("Name of the crop.", LEARN + " · history proposal"),
        "confidence": n("Share of the forest's votes the answer got, 0 to 1; low confidence means ask instead of propose.", LEARN + " · history proposal"),
        "action": s("propose when the confidence is enough to suggest the crop, ask when it is not and the app should ask the producer.", LEARN + " · history proposal",
                    enum=["propose", "ask"]),
        "confirmed": b("False: the producer has not confirmed it.", LEARN + " · history proposal"),
        "start_offset": i("Days from 1 April when the field turns green, -1 if it never does.", LEARN + " · history proposal · detail"),
        "peak_offset": i("Days from 1 April of the greenest composite.", LEARN + " · history proposal · detail"),
        "peak_value": n("NDVI at the peak.", LEARN + " · history proposal · detail"),
        "duration_days": i("Days the field stays green.", LEARN + " · history proposal · detail"),
        "peaks": i("Number of green peaks.", LEARN + " · history proposal · detail")}),
        "One proposal per season with a complete MODIS curve at the demo field's point (real NASA data, a 250 m pixel that mixes fields).", LEARN)}))


CAL = "Date picker · the field on a chosen date and crop"
CALENDAR = obj("The field on every date of the last year for every crop that can be sown, so the panel can answer «I open the app on this date and pick this crop» from this file alone.", CAL, {
    "step_days": i("Days between two dates of the calendar.", CAL),
    "offer_days": i("A sowing further than this from the date is `offered: false`: the water of the date has faded.", CAL),
    "from": s("First date, YYYY-MM-DD.", CAL), "to": s("Last date, YYYY-MM-DD: the same day as `as_of`.", CAL),
    "dates": arr(obj("The field on one date.", CAL, {
        "date": s("The date, YYYY-MM-DD.", CAL),
        "water": obj("The field's water that day (the same estimate as summary.water: assumed soil parameters, never measured water).", CAL + " · header", {
            "mm": n("Available water in mm that day.", CAL + " · header"), "capacity_mm": n("Water the modelled soil can hold, mm.", CAL + " · header"),
            "volumetric_moisture": n("Volumetric moisture that day, m3/m3.", CAL + " · header")}),
        "options": arr(obj("One crop on this date, read at its next sowing date.", CAL + " · option card", {
            "crop": s("Crop id, as in catalog.crops.", CAL + " · option card"),
            "sowing": s("The crop's next sowing date, MM-DD.", CAL + " · option card"),
            "days_to_sowing": i("Days from the date to that sowing.", CAL + " · option card"),
            "offered": b("True when the sowing is within `offer_days` of the date: show these first; the others are a rough guide.", CAL + " · option card"),
            "evaluated": i("Historical seasons evaluated.", CAL + " · option card"),
            "water_risk": nullable(s("low, medium or high from `drops`.", CAL + " · option card · pill", enum=["low", "medium", "high"])),
            "drops": nullable(ref("drops", "The ten drops of the option's seasons: model A's when `risk_basis.source` is model_a, the fixed cuts' otherwise.", CAL + " · option card · ten drops")),
            "risk_basis": obj("What `drops` rest on, with the fixed cuts beside them.", CAL + " · small print", {
                "source": s("model_a or fixed_cuts.", CAL + " · small print", enum=["model_a", "fixed_cuts"]),
                "model_version": nullable(i("Version of model A used; null with the fixed cuts.", CAL + " · small print")),
                "fixed_cuts_drops": nullable(ref("drops", "The drops the fixed cuts of stress give.", CAL + " · small print")),
                "fixed_cuts_water_risk": nullable(s("low, medium or high from the fixed cuts.", CAL + " · small print", enum=["low", "medium", "high"]))}),
            "critical_window": nullable(obj("The crop's critical stage, day/month.", CAL + " · option card", {
                "start": s("DD/MM.", CAL + " · option card"), "end": s("DD/MM.", CAL + " · option card")})),
            "median_water_at_sowing_mm": nullable(n("Median across seasons of the water the soil holds on the sowing day, mm.", CAL + " · option card · detail")),
            "warnings": arr(s("A warning code, as in `warnings`.", CAL + " · option card · gaps"), "Warnings of this option.", CAL + " · option card · gaps")}),
            "One entry per crop that can be sown (catalog.crops).", CAL)}),
        "One entry per date, oldest first.", CAL),
    "warnings": arr(obj("The text of a warning code.", CAL + " · option card · gaps", {
        "code": s("The code.", CAL + " · option card · gaps"), "text": text("What it says.", CAL + " · option card · gaps")}),
        "The texts of every code used in `options[].warnings`.", CAL)})


def build():
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "XmartAgro frontend data",
            "description": "Static data for the XmartAgro panel in the shape of its API contract (summary, inputs, scenarios): one "
                           "exploratory analysis at one NASA POWER point. Text fields are {key, en, es}. Nothing here is a forecast, a yield "
                           "prediction or a recommendation. Every field has `x-used-in`: where the panel shows it.",
            "x-used-in": "The whole document: one file the panel reads, with no API call", "type": "object", "$defs": DEFS,
            "properties": {"schema_version": s("Version of this schema.", CONTEXT, const=SCHEMA_VERSION),
                           "generated_at": s("When the analysis was run, ISO 8601.", CONTEXT, format="date-time"),
                           "as_of": s("The day the water and the options are for, YYYY-MM-DD: the last day of the climate record. Show it («Estado al 13 nov») so nobody reads an old picture as today's.", HEADER + " · date"),
                           "site": SITE, "status": STATUS, "summary": SUMMARY, "inputs": INPUTS, "scenarios": SCENARIOS, "catalog": CATALOG,
                           "charts": CHARTS, "learning": LEARNING, "calendar": CALENDAR},
            "required": ["schema_version", "generated_at", "as_of", "site", "status", "summary", "inputs", "scenarios", "catalog", "charts", "learning", "calendar"],
            "additionalProperties": False}


def build_error():
    """The schema of the document the file holds when the analysis could not be built."""
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "XmartAgro frontend data: error document",
            "description": "What the frontend file holds instead of the analysis when it could not be built. Same envelope (schema_version, "
                           "generated_at, status), no results: show status.badge and status.error, and no numbers.",
            "x-used-in": "The whole document: one file the panel reads, with no API call", "type": "object", "$defs": {"text": DEFS["text"]},
            "properties": {"schema_version": s("Version of this schema.", CONTEXT, const=SCHEMA_VERSION),
                           "generated_at": s("When the analysis was attempted, ISO 8601.", CONTEXT, format="date-time"),
                           "status": ERROR_STATUS},
            "required": ["schema_version", "generated_at", "status"], "additionalProperties": False}


def dumps_error():
    return json.dumps(build_error(), ensure_ascii=False, indent=2) + "\n"


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
        return " or ".join(inner) + (" or null" if any(option.get("type") == "null" for option in node["anyOf"]) else "")
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
    lines += ["", "## The error document", "",
              "When the analysis cannot be built the file holds this instead (`frontend.error.schema.json`): show `status.badge` and "
              "`status.error`, and no numbers.", "", "| Field | Type | Meaning | Used in |", "| --- | --- | --- | --- |"]
    lines += [f"| `{p}` | {k} | {m.replace('|', '/')} | {u.replace('|', '/')} |" for p, k, m, u in fields(root=build_error())]
    return "\n".join(lines) + "\n"
