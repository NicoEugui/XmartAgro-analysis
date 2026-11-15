# XmartAgro analysis

XmartAgro's analytics prototype was developed for the 2026 NASA Space Apps Challenge, for the
[Field Shift: Adapting Farms with NASA Data](https://www.spaceappschallenge.org/2026/challenges/field-shift-adapting-farms-with-nasa-data/)
challenge. It combines NASA Earth observation data with local agronomic inputs to explore crop rotation
and planting scenarios under historical climate conditions.

Background service that turns what the API stored (sensor readings, producer and agronomist inputs) into the
`results` documents the API serves. It is independent from the backend and talks to it only through MongoDB.

```
API (NestJS)  --writes-->  readings, inputs, jobs   <--reads/claims--  worker
API (NestJS)  <--reads---  results                  <--writes--------  worker
```

Exploratory prototype: results compare historical-climate scenarios, are not validated for any field, and are neither
forecasts nor recommendations. Soil state, soil effect and trend are `null` because no diagnosis exists.

> **New to the project?** Read `docs/como-funciona.md` (in Spanish): how everything works from A to Z, what is real and what is simulated, and how the nightly pipeline and the training would run in production.

## Layout

```
src/xmart_analysis/
  engine/   water-balance model, crops, scenarios, session (no I/O, standard library only)
  cli.py    `xmart-analysis run|validate`: the same analysis without a database
  worker/   domain, ports, mapping, use case, job loop, adapters (Mongo, memory, engine), CLI
  report/   figures and the experiment log drawn from the analysis documents (optional extra: matplotlib)
  validation/ comparison of the water balance with independent NASA data and the producer survey
  soils/    the soil-map plug-in: a port, the CONEAT adapter (Uruguay) and the rules that turn a soil unit into texture and capacity (extra: coneat)
  learning/ the simulated panel (fields, nodes, producers, seasons), models A, B and C, validation on fields kept apart, the model registry (extra: learn)
  data/     NASA climate, calibration, model tables with their status and sources, label catalog (en/es)
tests/      unittest suite (no database needed)
```

Dependencies point inward: the use case depends on ports (`worker/ports.py`), never on `pymongo`; the engine knows
nothing about the worker. A new store or data source is a new adapter.

## Run

```bash
cp .env.example .env            # fill in MONGODB_URI and credentials
docker compose up -d --build    # worker polling for jobs
docker compose logs -f worker
```

Without Docker: `pip install .` then `xmart-analysis-worker --once` (process pending jobs) or `--loop`.

### Without any database

```bash
pip install '.[plots]'                       # matplotlib is optional, only for figures
xmart-analysis run                           # bundled demo scenario -> out/*.results.json and the three screens (en, es)
xmart-analysis run my_scenario.json --lang es --out out
xmart-analysis validate                                     # the producers' survey, with figures
xmart-analysis validate --smap-l3 --smap-l4 --modis-ndvi --imerg   # also NASA SMAP, MODIS and GPM IMERG, from the files in the repository (see "Validation against independent data")
xmart-analysis calibrate --out calibration.json   # refit the soil parameters to the bundled SMAP L4 (needs the `calibrate` extra, scipy)
```

A scenario file has the shape of the API documents: `{field_id, readings: [...], inputs: {farmer, agronomist}}` (see
`src/xmart_analysis/data/demo_scenario.json`). The same use case runs as in production, with file adapters instead of Mongo.

## Static data for the frontend

```bash
xmart-analysis export --out dist                 # the bundled demo, or: xmart-analysis export my_scenario.json --out dist
```

Add `--models DIR` (the registry folder `learn` writes) and the document carries the `learning` block of the published models (versions and metrics, model A's reading of every option, model B's correction of the satellite, model C's crop-history proposals) and the models are applied to the result: B's corrected satellite is the starting water and A's drops are the options' drops (the fixed cuts stay in `risk_basis`). Without it that block is `null` and the analysis is the fixed-rule one. The document also carries `as_of` (the day it is for) and a `calendar`: the field's water and every crop's risk on one date per week of the last year, so a static front can answer any date and crop from the file alone (`schema/preview.html` shows how to read it). The schema is version 3.0.

It writes four files: `frontend.json` (the data of the three screens, the status and the validation blocks), `frontend.schema.json`
(JSON Schema, draft 2020-12, with a description on every field), `frontend.error.schema.json` (the document the file holds when the analysis fails) and `frontend.fields.md` (the same contract as a table). Every text is
`{key, en, es}`: show `en` or `es`. Options are never ranked, `status.exploratory` is always true and `status.validated_for_field` always
false: show the disclaimer. Nothing in the file needs a server.

**Demo or real, and errors.** `status.mode` is `demo` while any input is simulated (today the soil-moisture sensor) and `live` when every input is measured or entered by a
person; `status.badge` is the text to show at the top of every screen («Modo demo · datos simulados») and `status.simulated_inputs` says which inputs are simulated.
`catalog.modes` describes the four states the panel can be in with the text of each badge and what to show: `demo`, `live`, `error` and `offline` (only the panel can
know it cannot read the file). When the analysis cannot be built, `export` still writes a valid file, the error document (`status.mode` `error`, `status.error` with code, field and message, no
results), and exits with 1; an unexpected failure is reported as `internal_error` without leaking its text.

**Charts.** `charts` carries the data behind every figure of the experiment log (the sowing grid, the survey, SMAP, NDVI, IMERG, POWER vs IMERG, and the three sensor experiments), 26 charts in one
language-neutral format so the panel can draw similar graphs itself. A chart is columnar: `x.values` is the shared axis (`category`, `date`, `month_day` or `number`) and each series has a `values` list of the same
length, drawn as `bar`, `line` or `points` (`stacked` for parts of one bar). Every chart says which figure it mirrors (`figure`), where it comes from (`source`) and whether it is `simulated`
(show the demo badge on it). The charts are built from the same documents as the figures (`frontend/charts.py`, `validation/documents.py`), and a test checks that every value in a figure's table is in the charts, so the front
draws the numbers the report plots. The worker also stores them in the `results` document (`charts`, resolved to the panel's language). `frontend.json` grows to about 200 KB with them: if the
panel only needs some, it can read the groups it draws (`sowing`, `validation`, `rain`, `sensor`) and ignore the rest.

**The sensor series in the demo.** The demo scenario carries the simulated year of readings (`{"from_file": "sensor_simulated.csv", ...}`), the use case reads the last year of
readings of the field (`ReadingsRepository.history`, implemented for memory and Mongo) and the engine starts the scenarios from the model's own state corrected by that series,
not from the last noisy reading. `summary.water.series` has the day-by-day reading and modelled state for a «sensor vs modelo» chart, and `summary.water.reading_moisture` keeps the last reading.
With a single reading there is no series and nothing changes. The Mongo `history` query follows `latest` but has not been run against a live database here.

`schema/` holds the committed copies for the frontend developers: `frontend.schema.json`, `frontend.fields.md` and
`frontend.error.schema.json`, `frontend.example.json` (the demo, generated with a fixed time) and `frontend.error.example.json`. Tests fail if they drift from the code; regenerate with

```bash
xmart-analysis learn --out /tmp/models --now 2026-11-15T00:00:00+00:00 && xmart-analysis export --out schema --models /tmp/models --now 2026-11-14T10:30:00+00:00 && mv schema/frontend.json schema/frontend.example.json
```

(`frontend.error.example.json` comes from `payload.build_error`; `tests/test_sensor_demo.py` shows the document it must equal.)

## Data layout

Real data is only NASA data and the team's own producer survey, for two places: the Soriano field (the demo site) and La Estanzuela, Colonia (`sites/la_estanzuela/`: NASA POWER, SMAP L4 and L3, MODIS NDVI and its own SMAP-fitted soil; `XMART_SITE=la_estanzuela` runs the model there) and, for the learning panel, the NASA POWER climate of six more farm points (`sites/sim_*/`, kind `climate` in `sites.csv`: only climate, never calibrated or active). Everything else that trains the models is simulated, marked so, and lives in `data/learning/` (see "Learning layer"). The only outside references are two FAO papers that bound the simulated crops (`fao56`, `fao33`).

```
data/
  sites.csv                 which site the model runs on (XMART_SITE can name it)
  datasets.csv              every dataset file: group, role, source, period, rows and checksum
  model_constants.csv, crop_parameters.csv, survey_crop_map.csv, sources.csv, labels   shared tables
  sites/soriano/            the field: NASA POWER climate, NASA GPM IMERG rain, NASA SMAP L4 and L3 soil moisture and MODIS NDVI (the validators and the calibration read these when a flag has no path), SMAP-fitted soil calibration, constants (latitude, longitude, season range), and `sensor_simulated.csv` (one SIMULATED year of daily soil-moisture readings; see "Simulated sensor")
  survey/                   the team's own producer survey (respondents, rotations, unfavourable seasons)
  learning/                 SIMULATED panel tables: fields, nodes, producers, crop_ranges (see "Learning layer")
```

The Soriano NASA CSVs are AppEEARS point exports of 7 Nov 2026 and La Estanzuela's of 15 Nov 2026 (its POWER file comes from the public POWER API; a new site's calibration starts from another site's search bounds, then `xmart-analysis calibrate` refits it); the product, layers, dates and point of each request are in `sources.csv`. `data/requests/` keeps the AppEEARS requests of Soriano and La Estanzuela (product, layers, dates, point) with the account and task identifiers removed: only the task name
(`XmartAgro_...`), its type and its parameters remain, and a test fails if an email or a name appears.

The soil calibration records the point it was fitted at; the provenance report lists it as `pending` if it no longer matches the site.
To refit it: `xmart-analysis calibrate --out src/xmart_analysis/data/sites/soriano/calibration.json` (it reads the bundled SMAP L4; give `--smap-l4 FILE` for another export), then
`python -m xmart_analysis.datasets refresh`.

```bash
python -m xmart_analysis.datasets check      # every file matches the manifest, every site is complete
python -m xmart_analysis.datasets refresh    # rewrite rows, period and checksum after a dataset changes on purpose
python -m xmart_analysis.datasets import-power DOWNLOAD.csv src/xmart_analysis/data/sites/<site>/power_daily.csv
```

## Validation against independent data

`xmart-analysis validate` compares the model with data it was not built from. Each block is exploratory and runs only for the site's point.

| Flag | Input | Compares | Figure |
| --- | --- | --- | --- |
| (none) | the producer survey (bundled) | seasons the producers called unfavourable vs the modelled critical-stage stress | `validation_survey.*.png` |
| `--smap-l3 [FILE]` / `--smap-l4 [FILE]` | NASA SMAP (bundled in `sites/soriano/smap_l3.csv`, `smap_l4.csv`) | modelled soil water vs SMAP, in the validation years | `validation_smap.*.png` |
| `--modis-ndvi [FILE]` | NASA MODIS NDVI (bundled in `sites/soriano/modis_ndvi.csv`) | modelled stress vs vegetation greenness per season | `validation_ndvi.*.png` |
| `--imerg [FILE]` | NASA GPM IMERG (bundled in `sites/soriano/imerg_daily.csv`; give a path to use another export) | POWER rain vs IMERG rain, and the model run with each | `validation_imerg.*.png`, `validation_rain_sensitivity.*.png` |

```bash
xmart-analysis validate --smap-l3 --smap-l4 --modis-ndvi --imerg --out out      # writes out/validation.json plus the figures in en and es
```

Everything is also in `out/validation.json`. A file that is not at the site's point is refused (`file_not_at_site`).

### Rain source: POWER or IMERG

The model runs on NASA POWER rain. IMERG is a second NASA rain estimate for the same point, so `--imerg` answers two questions:

1. **Do the two rains agree?** (`imerg` block: daily, monthly and Dec-Mar-by-season correlation, annual mm, driest seasons by each source.)
2. **Does the answer change if the model uses IMERG rain?** (`rain_sensitivity` block.) The model is run twice on the 27 seasons both sources cover (1998/99 to 2024/25).
   Only the daily rain changes: temperature, evaporative demand and the soil parameters (fitted with POWER rain) stay the same.
   Per crop it gives `spearman_between_sources` (1 means the same season order), `mean_abs_difference` of stress, high-deficit seasons per source and the
   stress of every season; per rotation, the share of high-deficit seasons with each source; and the seasons the producers named.

Reference run for the Soriano field (2026-11-14):

| | POWER vs IMERG |
| --- | --- |
| Season order, soybean 1st / maize (rho) | 0.93 / 0.97 |
| Mean absolute stress difference, soybean / maize | 0.054 / 0.039 |
| High-deficit seasons, soybean (POWER / IMERG) | 19 / 18 |
| Rotations, high-deficit share | 5 to 8 points lower with IMERG |
| 2022/23 (named by 4 producers) | most stressed under both: 0.888 / 0.775 |

Read it as: the ranking of bad seasons does not depend on the rain source, the level does (IMERG rains more: 1289 vs 1159 mm per year). It does not say which source is
right, the soil parameters were not refitted with IMERG, and IMERG ends on 2025-09-30, so 2025/26 is not covered.

**Decision: the demo and every result use POWER rain.** It covers the whole record without gaps (to 13 November 2026, 2025/26 included), the soil parameters were fitted with it, and there is no
gauge data to say IMERG is closer to the truth. IMERG was tested and the comparison is kept: the experiment log has a section with the monthly rain, the stress of every season, the seasons by
outcome class and the rotations under each source (`reports/figures/rain_decision.en.png`, drawn by `plot_rain_decision`, with its values in a table). The rain source is not a setting: using IMERG would also mean
refitting the soil with it and giving up the years it does not cover.

## Simulated sensor

No real soil-moisture sensor exists yet, so the repository carries one simulated year (`sites/soriano/sensor_simulated.csv`, 365 daily readings, the last year of the climate record: 14 November 2025 to
13 November 2026, columns `date,volumetric_moisture,sensor_id`). It is listed in `datasets.csv` with kind `simulated` and counted as an `assumption`, never as data.

How it is made (`engine/sensor_series.py`): the same bucket is run with a soil the model does not know (another capacity and wilting point), which is the
simulated field; the sensor reports that field plus a constant offset and Gaussian noise (seeded by the seed and the first day of the window). Every parameter (seed, noise, offset, how different the soil is) is
an `assumption` in `model_constants.csv`. The model only receives the readings, never the simulated field, so comparing the two measures what a sensor adds.

```bash
xmart-analysis simulate-sensor        # rewrites the bundled series; the same seed gives the same file, so the manifest checksum still matches
```

The correction is a hook of the water balance: `simulate_moisture(..., observations={date: reading}, gain=g)` moves the modelled water a share `g` of the way to
each reading (0 ignores it, 1 adopts it); without observations nothing changes. A real ESP32 export with the columns `date` and `volumetric_moisture` is read by the
same `sensor_series.load`, so replacing the simulated file with real data changes the data, not the code.

Three simulated experiments, all in the experiment log (`validation/sensor_assimilation.py`):

- **One year** (14 November 2025 to 13 November 2026): the error (RMSE) of the model is 0.0153 m3/m3 without a sensor and 0.0130 with daily readings (0.0113 weekly, 0.0131 monthly); in the first 30 days 0.0341 and 0.0157. The bias goes from 0.0031 to 0.0101: the sensor's offset (0.01) is a calibration gap, and correcting the water state adopts it instead of removing it.
- **Every one-year window of the climate record** (473 windows, one start per month): a daily sensor lowers the whole-year error in 96% of them (first 30 days: 100%), by a median of 34% (from -26% to +58%). The gain of a single year (14% or 40% in two we looked at) is one draw from that spread: it depends on when the series starts.
- **Fitting the soil to the sensor** (`engine/soil_fit.py`, wilting point and capacity, first half of the series, tested on the second): the fitted soil follows the shape of the curve much better (spread of the error 0.0091 to 0.0017) but inherits the sensor's offset (bias 0.0096 to 0.0154), so the total error does not improve (0.0133 to 0.0155). The series alone cannot tell the soil from the sensor: with one perfect reference measurement that removes the offset (a soil sample dried and weighed) the error would fall to 0.0067. That is the case for calibrating the sensor, and it is not done with real data.

All simulated, not a field result.
The series always ends on the last day of the climate record (`sensor_days` days back from it): to bring it up to today, refresh NASA POWER
(`python -m xmart_analysis.datasets import-power ...`), then `xmart-analysis simulate-sensor` and `python -m xmart_analysis.datasets refresh`.
The demo starts from this series (see "Static data for the frontend").

## Soil map (CONEAT) as a plug-in

Soil comes from an optional module (`soils/`) so another country can connect its own system. `SoilMap.lookup(lat, lon)` returns a `SoilUnit` (system, code, productivity index, dominant soil orders); the CONEAT adapter reads the MGAP shapefile
(about 120 MB, **not kept in the repository**; it needs `pip install -e '.[coneat]'`) and the group data comes from `data/soils/coneat_groups.csv` (128 groups, read from the MGAP description of the groups). A new country adds an adapter that returns the same `SoilUnit` and
registers it in `soils.SYSTEMS`. With no system (`NullSoilMap`) every field falls back to a medium soil.

```bash
xmart-analysis coneat-groups "Descripcion de Grupos de suelos CONEAT.pdf"      # the table of groups (needs pdftotext)
xmart-analysis soil-units --system coneat --shapefile sue_utm.shp               # the unit of every field -> data/learning/soil_units.csv
```

What the panel takes from a unit (`soils/derive.py`, all provisional assumptions in `model_constants.csv` and `soil_order_texture.csv`): the **texture class** (the heaviest of the first two soil orders), the **capacity factor** of the simulated soil (it grows with the
productivity index, 1 at index 100) and the **planted satellite error** (by texture). CONEAT gives an index and dominant soils, not available water in millimetres, so the capacity is our derivation. The Soriano coordinate falls in group 11.4 (index 214).
The units are real MGAP data, the only data besides NASA and the survey; the table of units and the table of groups are listed in `datasets.csv` as `soil_map`.

## Learning layer

The specification asks for machine learning that learns from all fields. Real data is one field and nine unfavourable seasons, so the panel that trains the models is **simulated**: every row says `simulated: True`
and source `simulated_panel`, and the tables that make it live in `data/learning/` (kind `simulated` in `datasets.csv`). The panel measures whether the method recovers a structure planted on purpose, not how accurate it would be
on real fields; real data replaces it by adding rows to the same tables, with no change to the models.

| Table | What it holds |
|---|---|
| `fields.csv` | the real Soriano field, the second real point La Estanzuela (Colonia, own NASA climate, SMAP and MODIS) and six simulated fields (Salto, Paysandu, Rio Negro, Flores, Durazno, Florida) at six farm coordinates, each with its **own NASA POWER record** (`sites/sim_*/`, a `climate` site: climate only); the soil of every field comes from its CONEAT unit (`soil_units.csv`, see "Soil map"); the rest of a simulated field is simulated: a soil the model does not know, clay and slope, and the planted satellite error |
| `nodes.csv` | two sensor nodes per field (30 and 60 cm) with their own patch of soil, offset and noise; a node is usable only after a reference measurement tells its offset |
| `soil_plans.csv` | the soil analysis and Soil Use Plan of every field (organic matter, Bray phosphorus, pH, estimated erosion, soil type), simulated from its clay, slope and capacity; the CONEAT code is left empty |
| `producers.csv` | the twelve surveyed producers: their field, sowing shift, stage length, Kc and p variants, and how they rate a season |
| `crop_ranges.csv` | published range of Kc mid and p (FAO-56), Ky (FAO-33) and the simulated NDVI peak; a producer's variant stays inside it |

**Seasons.** The survey gives each producer's rotation without years, so the simulation assigns it: the crops cycle over the last five seasons (twelve producers, **60 seasons**); a respondent who wrote no rotation gets the crops all respondents wrote.
A national panel adds every crop in every field and historical season (1987 to 2025). The model computes the stress with the table's crop and its soil; the outcome uses the producer's variant and the field's real soil, Ky turns it into a yield,
noise adds what water does not explain, and the producer's scale makes the five ratings of the app. The real national seasons the team collects go to a check against these outcomes.

**Models** (`learning/models.py`, all share `Learner`; the gradual rule `(n * own + k * regional) / (n + k)` is in `pooling.py`):

| | Learns | Method | Judged by | Fixed starting rule |
|---|---|---|---|---|
| B | how far the satellite is from the calibrated sensor in a field like this | linear regression on satellite, clay, slope and season, plus the field's own mean error | RMSE on fields kept apart | the satellite as is |
| A | the chance a season is rated bad, normal or good given the stress the model computed | ordinal logistic regression, per crop and regional | accuracy on fields kept apart | the cuts 0.10 and 0.30 |
| C | what grew (a crop, or fallow) from five numbers of the NDVI curve | random forest | accuracy on fields kept apart | the most common class |

Validation keeps whole fields apart (a quarter, 20 random splits). A trained model is registered as the next version and **published only if the data is enough and it beats the fixed rule on fields it never saw**; otherwise it stays a
candidate with the reason, and the published one keeps serving (`learning/registry.py`).

```bash
pip install -e '.[learn]'                 # numpy, scipy, scikit-learn
xmart-analysis ingest --out models        # fills the series and examples stores (rows already there are skipped)
xmart-analysis learn --out models         # ingests, trains A, B and C, validates, registers; writes models/registry.json and models/learning.json
xmart-analysis learn --only B --now 2026-11-15T00:00:00+00:00
```

Result of the committed seed (simulated panel, fields kept apart): B takes the satellite error from 0.0300 to 0.0251 m3/m3 for a field with no sensor and to 0.0237 with 90 days of its own;
A gets 81.4% of the seasons right against 81.1% for the fixed cuts (almost no gain: the cuts are close to the planted rule); C gets 84.1% of the crops and 100% of the season group (winter, summer, fallow).
The stores (`learning/stores.py`) only ever add rows, so ingesting twice changes nothing and new data accumulates. The nightly pipeline itself is not wired to the registry (the front is emulated with a static JSON), but the exporter applies it: with `--models`, model B's corrected satellite sets the starting water (`summary.water.source` `smap_corrected`) and model A sets each option's drops and risk (`summary.options[].risk_basis`, with the fixed cuts beside it); without it the analysis uses the fixed rules and needs no numpy. `docs/como-funciona.md` documents how it would run.

### Soil health

`engine/soil_health.py` (rules, no learning) says how a rotation treats the soil: **state** (good, regular, poor), **trend** (improving, stable, worsening) and **precision** (low without a soil analysis, medium with one).
Each season scores the stubble its crop leaves, a cover crop or pasture, and the months the soil stays bare; soybean after soybean costs score up to a cap; the analysis moves it (estimated erosion above 7 t/ha/year or organic matter under 2.5% cost, organic matter from 4% gains).
What each crop does is in `data/crop_soil_effects.csv`, the thresholds in `model_constants.csv` (`soil_*`): all provisional assumptions to be sourced. `effect(rotation)` gives improves, maintains or worsens for an option and needs no analysis.
`learning/soil_health.py` applies the rules to the twelve producers: their rotation is what they wrote in the survey form (years assigned by the simulation, one crop per season), and the soil analysis is the simulated one of their field. The table goes into `learning.json`
(`soil_health`). Limits: bare months come from the crop's cycle until the NASA NDVI curve of each season is attached to a known crop, and this says how a rotation treats the soil, not how much soil is lost.

## Backtest: what the tool would have said before each past season

`learning/retrospective.py`. For a field, a crop and a past season the tool answers on the sowing day as it would today: it takes the water the soil holds that day and applies the climate of the **other** seasons (the season itself is left out),
counts the seasons that ended with water, tight or without it, and gives the risk; then the season is looked at with its real climate. Soybean sown in November 2022: high risk in 6 of the 8 fields of the panel (medium in 2) and the season ended without water in all 8,
worse than 97% to 100% of the other seasons. But with the crop parameters pending, soybean and maize end without water in about 64% of seasons, so a high warning adds little (67% against 64%); wheat and barley rarely do (9%, 6%) and were never warned.
The two seasons the surveyed producers named most (2022/23, 2025/26) have the highest mean stress in the panel. The fields and outcomes are simulated: this is the consistency of the warning, not a check against a real field. It is section 4 of the experiment log and the `retrospective` charts of the frontend JSON.

## Experiment log

`xmart-analysis report` writes one Markdown document, `reports/experiments.md`, with every run of this checkout, its figures and the data lineage. It is
generated, not written by hand, so it cannot drift from the runs, and it needs no Jupyter: the code lives in the package (`report/experiments.py`) and is tested.

```bash
xmart-analysis report --smap-l3 --smap-l4 --modis-ndvi --imerg --out reports   # the bundled NASA files; --lang es for Spanish figures
```

Each validator whose file is given gets a section; without a file its section is left out (the survey and the model sections always appear).

| Section | What it shows |
| --- | --- |
| Data architecture | data flow, every dataset in `datasets.csv` (role, source, period, rows, checksum) and the checksum of each external file used |
| Model and calibration | soil parameters, calibration and validation errors against SMAP L4, the parameters of every seed |
| Model output for the demo | every offered option with its water risk and drops |
| What happens if a crop is sown on a given date | for soybean (1st and 2nd), maize, wheat and barley, the default sowing date and four shifted by 15 and 30 days: seasons ending in ok / tight / out, median stress and water at sowing, the season-by-season result for one run and the sensitivity to the (simulated) sensor reading |
| Water balance with and without a (simulated) sensor | the simulated field, the sensor readings and the model with and without them, the error of each run |
| The sensor experiment over every one-year window | how the sensor's gain depends on the month the series starts (473 windows) |
| Fitting the soil to the sensor series | the soil fitted to the first half of the series and tested on the second, with and without a reference measurement |
| Decision: POWER rain for the demo, IMERG tested | the monthly rain, the stress of every season, the seasons by class and the rotations under each rain source |
| One section per experiment | the question, the figure, the numbers behind the figure (collapsed table) and a reading with its caveat |
| Integrity checks and Not validated | provenance and manifest status, and what the results do not support |

**Are the plotted data the ones in the table?** `report/experiments.py` keeps one list, `FIGURES`, pairing each figure with the table of the values it plots.
`tests/test_report.py` draws every figure, reads the points and bars back from the drawn chart and fails if a value of the table is not on it.

The PDF (`reports/experiments.pdf`) comes from `scripts/build_pdf.sh`: pandoc turns the Markdown into HTML and headless Chrome prints it (no LaTeX needed; set `CHROME` if Chrome is elsewhere). Regenerate it after every `report` run.
Every NASA file the runs use is in the repository (`sites/soriano/`), so anyone can rerun the report and get the same numbers; the document lists each with its checksum.

## Data and provenance

Everything the model uses that is not a formula lives in `src/xmart_analysis/data/` and carries a status:
`data` (NASA climate), `fitted` (calibrated to SMAP L4), `source`, `assumption` (team decision, with a note) or
`pending` (a value waiting for a dataset, e.g. the crop parameters). Only NASA and the team's own producer survey are cited (`sources.csv`).

The survey (`survey/producer_survey.csv`, `survey/survey_rotations.csv`, `survey/survey_unfavorable_seasons.csv`) holds what 12 producers wrote (an answer with a single, ambiguous year is left out): no names, no
localities, rotations as a list of crops in the written order (the respondents do not say which crop falls in which year).
`xmart-analysis validate` compares the seasons they called unfavourable with the model's critical-stage stress.

The rotations are the options compared (`{"kind": "rotation", "rotation": "survey_03"}`): each written crop is mapped to a
modelled crop by `survey_crop_map.csv` (a soybean right after a winter grain crop is read as second sowing, any other as
first), run over the 39 historical seasons at its default sowing date with the same starting moisture, and the counts are
added. Respondents 5 and 6 wrote no crop sequence and are not offered. Everything runs at one NASA POWER point, the Soriano field
(`latitude` and `longitude` in `sites/soriano/constants.csv`); results do not describe other places. A new POWER download is brought in with
`xmart_analysis.datasets.import_power(source_csv, target_csv)`, which trims the days not yet available and refuses gaps.

```bash
python -m xmart_analysis.provenance            # counts by status and source
python -m xmart_analysis.provenance --check    # fails if a value lacks a status or source
```

## Contract with the API

| Collection | Written by | Shape |
| --- | --- | --- |
| `readings` | API | `{field_id, sensor_id, moisture, sensor_type, received_at}` |
| `inputs` | API | `{_id: field_id, farmer, agronomist}` |
| `jobs` | API creates, worker updates | `{field_id, status, requested_at, claimed_at, attempts, error}` |
| `results` | worker | `{_id: field_id, schema_version, inputs_hash, engine_version, generated_at, summary, scenarios, analysis, mapping_notes}` |

To request an analysis the API inserts `{field_id, status: "pending", requested_at: <UTC Date>, attempts: 0}` into
`jobs` after saving readings or inputs. Statuses: `pending`, `running`, `done`, `failed`.

- **Latest reading:** newest document of the field in `readings`, whichever sensor sent it. `moisture` must already be
  volumetric (m3/m3); a raw ADC value is rejected, not interpreted. Unknown depth is flagged; the reading time is `received_at`.
- **Idempotent:** a job whose inputs hash and engine version match the stored result is marked done without recomputing.
- **Coalescing:** finishing a job marks older pending jobs of the same field done (`error.code = "superseded"`).
- **Concurrency:** `claim` is an atomic `find_one_and_update`; several workers can run side by side.
- **Failures:** engine errors fail the job once with a structured error; unexpected errors retry up to
  `WORKER_MAX_ATTEMPTS`; a job stuck in `running` is reclaimed after `WORKER_STALE_JOB_MINUTES`.
- **Honesty:** `water.mm` is the scenario's initial water derived from assumed soil parameters
  (`mm_status: "derived_from_assumptions"`), not measured available water. Unmatched free-text crop names are dropped
  and listed in `mapping_notes`. `analysis` holds the full output in `en` and `es`.
- **Provisional team conventions:** `water_risk` from high-deficit drops (`<=3` low, `<=6` medium, else high) in
  `worker/mapping/results.py`; the default compared options in `worker/config.py`.

## Configuration

See `.env.example`. `MONGODB_URI`, `MONGODB_USERNAME` and `MONGODB_PASSWORD` follow the API's convention; use a
dedicated pipeline user. `WORKER_UI_LANGUAGE` sets the language of `summary` and `scenarios`.

## Tests

```bash
PYTHONPATH=src:tests python -m unittest discover -s tests
```

The Mongo adapter has no automated tests yet. The regional snapshot (`data/regional_snapshot.json`: latest SMAP L4 value) is static and must be regenerated from the research data when refreshed.

## Open points with the backend

- The API creates `jobs` documents and can expose job status next to `results.generated_at`.
- API types must allow `null` in `soil.state`, `soil.trend`, `soil_effect` and `drops` (ended crop cycle) and accept the
  extra fields `water.mm_status`, `water.is_simulated`, `water.volumetric_moisture` and `status`.
- `scenarios.options[].years` is empty for rotation systems (the engine reports counts, not one class per season).
- The sensor payload should carry unit, depth and measurement time.
