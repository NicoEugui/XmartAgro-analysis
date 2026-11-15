# XmartAgro analysis

Background service that turns what the API stored (sensor readings, producer and agronomist inputs) into the
`results` documents the API serves. It is independent from the backend and talks to it only through MongoDB.

```
API (NestJS)  --writes-->  readings, inputs, jobs   <--reads/claims--  worker
API (NestJS)  <--reads---  results                  <--writes--------  worker
```

Exploratory prototype: results compare historical-climate scenarios, are not validated for any field, and are neither
forecasts nor recommendations. Soil state, soil effect and trend are `null` because no diagnosis exists.

## Layout

```
src/xmart_analysis/
  engine/   water-balance model, crops, scenarios, session (no I/O, standard library only)
  cli.py    `xmart-analysis run|validate`: the same analysis without a database
  worker/   domain, ports, mapping, use case, job loop, adapters (Mongo, memory, engine), CLI
  report/   figures and the experiment log drawn from the analysis documents (optional extra: matplotlib)
  validation/ comparison of the water balance with independent NASA data and the producer survey
  data/     NASA climate, calibration, model tables with their status and sources, label catalog (en/es)
docs/       narrative for the pitch (method, layers, modularity, use of AI, what is and is not validated)
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

It writes four files: `frontend.json` (the data of the three screens, the status and the validation blocks), `frontend.schema.json`
(JSON Schema, draft 2020-12, with a description on every field), `frontend.error.schema.json` (the document the file holds when the analysis fails) and `frontend.fields.md` (the same contract as a table). Every text is
`{key, en, es}`: show `en` or `es`. Options are never ranked, `status.exploratory` is always true and `status.validated_for_field` always
false: show the disclaimer. Nothing in the file needs a server.

**Demo or real, and errors.** `status.mode` is `demo` while any input is simulated (today the soil-moisture sensor) and `live` when every input is measured or entered by a
person; `status.badge` is the text to show at the top of every screen («Modo demo · datos simulados») and `status.simulated_inputs` says which inputs are simulated.
`catalog.modes` describes the four states the panel can be in with the text of each badge and what to show: `demo`, `live`, `error` and `offline` (only the panel can
know it cannot read the file). When the analysis cannot be built, `export` still writes a valid file, the error document (`status.mode` `error`, `status.error` with code, field and message, no
results), and exits with 1; an unexpected failure is reported as `internal_error` without leaking its text.

**The sensor series in the demo.** The demo scenario carries the simulated year of readings (`{"from_file": "sensor_simulated.csv", ...}`), the use case reads the last year of
readings of the field (`ReadingsRepository.history`, implemented for memory and Mongo) and the engine starts the scenarios from the model's own state corrected by that series,
not from the last noisy reading. `summary.water.series` has the day-by-day reading and modelled state for a «sensor vs modelo» chart, and `summary.water.reading_moisture` keeps the last reading.
With a single reading there is no series and nothing changes. The Mongo `history` query follows `latest` but has not been run against a live database here.

`schema/` holds the committed copies for the frontend developers: `frontend.schema.json`, `frontend.fields.md` and
`frontend.error.schema.json`, `frontend.example.json` (the demo, generated with a fixed time) and `frontend.error.example.json`. Tests fail if they drift from the code; regenerate with

```bash
xmart-analysis export --out schema --now 2026-11-14T10:30:00+00:00 && mv schema/frontend.json schema/frontend.example.json
```

(`frontend.error.example.json` comes from `payload.build_error`; `tests/test_sensor_demo.py` shows the document it must equal.)

## Data layout

Only NASA data and the team's own producer survey are used, for one place: the Soriano field.

```
data/
  sites.csv                 which site the model runs on (XMART_SITE can name it)
  datasets.csv              every dataset file: group, role, source, period, rows and checksum
  model_constants.csv, crop_parameters.csv, survey_crop_map.csv, sources.csv, labels   shared tables
  sites/soriano/            the field: NASA POWER climate, NASA GPM IMERG rain, NASA SMAP L4 and L3 soil moisture and MODIS NDVI (the validators and the calibration read these when a flag has no path), SMAP-fitted soil calibration, constants (latitude, longitude, season range), and `sensor_simulated.csv` (one SIMULATED year of daily soil-moisture readings; see "Simulated sensor")
  survey/                   the team's own producer survey (respondents, rotations, unfavourable seasons)
```

The NASA CSVs are AppEEARS point exports of 7 Nov 2026; the product, layers, dates and point of each request are in `sources.csv`. The request files AppEEARS also delivers carry the
account's email and task ids, so they are not kept in the repository.

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
