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
  report/   figures drawn from the analysis documents (optional extra: matplotlib)
  validation/ comparison of the water balance with NASA SMAP data
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
xmart-analysis validate                                     # survey and weather station, with figures
xmart-analysis validate --smap-l3 L3.csv --smap-l4 L4.csv --modis-ndvi NDVI.csv   # also NASA SMAP and MODIS (files for the site's point)
xmart-analysis calibrate --smap-l4 L4.csv --out calibration.json   # refit the soil parameters (needs the `calibrate` extra, scipy)
```

A scenario file has the shape of the API documents: `{field_id, readings: [...], inputs: {farmer, agronomist}}` (see
`src/xmart_analysis/data/demo_scenario.json`). The same use case runs as in production, with file adapters instead of Mongo.

## Static data for the frontend

```bash
xmart-analysis export --out dist                 # the bundled demo, or: xmart-analysis export my_scenario.json --out dist
xmart-analysis export --out dist --smap-l3 L3.csv --smap-l4 L4.csv --modis-ndvi NDVI.csv   # adds those validation blocks
```

It writes three files: `frontend.json` (the data of the three screens, the status and the validation blocks), `frontend.schema.json`
(JSON Schema, draft 2020-12, with a description on every field) and `frontend.fields.md` (the same contract as a table). Every text is
`{key, en, es}`: show `en` or `es`. Options are never ranked, `status.exploratory` is always true and `status.validated_for_field` always
false: show the disclaimer. Nothing in the file needs a server.

`schema/` holds the committed copies for the frontend developers: `frontend.schema.json`, `frontend.fields.md` and
`frontend.example.json` (the demo, generated with a fixed time). Tests fail if they drift from the code; regenerate with

```bash
xmart-analysis export --out schema --now 2026-11-14T10:30:00+00:00 && mv schema/frontend.json schema/frontend.example.json
```

## Data layout

```
data/
  sites.csv                 which site the model runs on (XMART_SITE overrides it) and where its soil calibration comes from
  datasets.csv              every dataset file: group, role, source, period, rows and checksum
  model_constants.csv, crop_parameters.csv, survey_crop_map.csv, sources.csv, labels   shared tables
  sites/soriano/            the original Soriano field coordinate: NASA POWER climate, SMAP-fitted calibration, constants
  sites/la_estanzuela/      the INIA La Estanzuela point (active): NASA POWER climate, INIA station daily record, constants
  survey/                   the team's own producer survey (respondents, rotations, unfavourable seasons)
```

Each site folder holds what belongs to that place only: its climate, its constants (latitude, longitude, season range and the
`et0_scale` fitted there) and, when it has one, its weather station. The model reads the active site; `XMART_SITE=soriano`
runs the same analysis on the other one. The INIA site borrows the Soriano soil parameters (`calibration_site` in `sites.csv`)
until SMAP L4 at its own point is fitted, and the provenance report lists them as `pending` meanwhile. To adopt its own: run
`XMART_SITE=la_estanzuela xmart-analysis calibrate --smap-l4 L4.csv --out sites/la_estanzuela/calibration.json` from `data/`, add the file to
`datasets.csv`, set `calibration_site` to `la_estanzuela` in `sites.csv` and run `python -m xmart_analysis.datasets refresh`.

```bash
python -m xmart_analysis.datasets check      # every file matches the manifest, every site is complete
python -m xmart_analysis.datasets refresh    # rewrite rows, period and checksum after a dataset changes on purpose
python -m xmart_analysis.datasets import-power DOWNLOAD.csv src/xmart_analysis/data/sites/<site>/power_daily.csv
```

## Data and provenance

Everything the model uses that is not a formula lives in `src/xmart_analysis/data/` and carries a status:
`data` (NASA climate), `fitted` (calibrated to SMAP L4), `source`, `assumption` (team decision, with a note) or
`pending` (a value waiting for a dataset, e.g. the crop parameters). Only NASA and the team's own producer survey are cited (`sources.csv`).

The survey (`survey/producer_survey.csv`, `survey/survey_rotations.csv`, `survey/survey_unfavorable_seasons.csv`) holds what 12 producers wrote (an answer with a single, ambiguous year is left out): no names, no
localities, rotations as a list of crops in the written order (the respondents do not say which crop falls in which year).
`xmart-analysis validate` compares the seasons they called unfavourable with the model's critical-stage stress.

The weather station (`data/sites/la_estanzuela/station_daily.csv`, INIA La Estanzuela daily rain, air temperature and Penman
evapotranspiration, 1986-2026) is used only to validate the NASA POWER climate the model runs on; it does not feed the model.
It is not at the NASA point, so daily agreement is partial. The evaporative demand is Hargreaves on NASA POWER times `et0_scale` (`model_constants.csv`), a factor fitted so it matches the
station's Penman ET on average; the soil parameters in `calibration.json` were fitted to SMAP L4 with that corrected demand, and a
test fails if the two ever get out of step. A new station export is added with
`xmart_analysis.validation.station.import_station(source_csv, target_csv)`.

The rotations are the options compared (`{"kind": "rotation", "rotation": "survey_03"}`): each written crop is mapped to a
modelled crop by `survey_crop_map.csv` (a soybean right after a winter grain crop is read as second sowing, any other as
first), run over the 39 historical seasons at its default sowing date with the same starting moisture, and the counts are
added. Respondents 5 and 6 wrote no crop sequence and are not offered. Everything runs at one NASA POWER point, the one of the INIA La Estanzuela station
(`latitude` and `longitude` in `model_constants.csv`); results do not describe other places. A new POWER download is brought in with
`xmart_analysis.datasets.import_power(source_csv, target_csv)`, which trims the days not yet available and refuses gaps; after changing
the point, refit the soil parameters (`xmart-analysis calibrate`), because `calibration.json` records the point it was fitted at and
the provenance report shows it as `pending` until it matches.

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
