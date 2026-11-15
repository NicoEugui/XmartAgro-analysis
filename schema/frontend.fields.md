# Frontend data: what every field means and where it is used

Generated from `frontend.schema.json` (do not edit by hand). Text fields are `{key, en, es}`: show `en` or `es`. `[]` marks the items of a list and `{name}` the free keys of a map. The shape follows the panel's API contract (`summary`, `inputs`, `scenarios`).

| Field | Type | Meaning | Used in |
| --- | --- | --- | --- |
| `schema_version` | string | Version of this schema. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `generated_at` | string | When the analysis was run, ISO 8601. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `as_of` | string | The day the water and the options are for, YYYY-MM-DD: the last day of the climate record. Show it («Estado al 13 nov») so nobody reads an old picture as today's. | Main screen · header «Tu campo hoy: N mm de agua útil» · date |
| `site` | object | Where the model runs and what it is built on. Results describe this point only. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `site.climate` | object | The daily climate the model runs on. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `site.climate.source` | one of `nasa_power` | Where the climate comes from. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `site.climate.first_day` | string | First day of the record, YYYY-MM-DD. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `site.climate.last_day` | string | Last day of the record, YYYY-MM-DD. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `site.climate.seasons` | integer | Number of historical seasons built from it (the length of every `years` list). | Agronomist chart · yearly result of each option |
| `site.soil_calibration` | object | State of the soil parameters (fitted to NASA SMAP L4). | Not drawn on the current screens: context for a header, a footer or the presentation |
| `site.soil_calibration.current` | boolean | True when the soil parameters were fitted at this point; false when they come from another point and are pending. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `site.soil_calibration.fitted_at` | object or null | The point where the soil parameters were fitted. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `site.soil_calibration.fitted_at.latitude` | number | Latitude, degrees. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `site.soil_calibration.fitted_at.longitude` | number | Longitude, degrees. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `site.note` | text | Warning that the model describes this point only. | Footer of the main screen |
| `status` | object | How far the results can be trusted. Always show the disclaimer. | Footer of the main screen and the presentation |
| `status.mode` | one of `demo`, `live` | demo while any input is simulated, live when every input is measured or entered by a person. The panel decides `pending` (a new field the nightly run has not reached) and `offline` (it cannot read the file) itself, and the error document says `error`; catalog.modes explains the five. | Badge at the top of every screen |
| `status.badge` | text | The text of the badge for this mode, e.g. «Modo demo · datos simulados». Show it at the top of every screen while the mode is demo. | Badge at the top of every screen |
| `status.simulated_inputs` | array | The inputs that are simulated, so the badge can say which numbers they feed; empty when the mode is live. | Badge at the top of every screen |
| `status.exploratory` | boolean | Always true: scenarios from historical climate, not forecasts. | Footer of the main screen |
| `status.validated_for_field` | boolean | Always false: nothing here is validated for a particular field. | Footer of the main screen |
| `status.disclaimer` | text | Sentence to show with the results. | Footer of the main screen |
| `status.simulated_reading` | boolean | True while the soil-moisture reading is simulated, not measured: show a «datos de ejemplo» banner. | Banner of the main screen |
| `status.values_by_status` | object | Count of the model's values by status: data, fitted, source, assumption (a team decision) or pending (waiting for a dataset). | Not drawn on the current screens: context for a header, a footer or the presentation |
| `status.values_by_status.{name}` | integer | Number of values with that status. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `status.sources` | array | The sources the model cites. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `status.sources[].id` | string | Source id. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `status.sources[].title` | string | Title. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `status.sources[].publisher` | string | Publisher. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `summary` | object | Everything the main screen needs, in the shape of the API's summary. | Main screen |
| `summary.field` | object | The place the analysis is for. | Main screen · field name |
| `summary.field.id` | string | Site id. | Main screen · field name |
| `summary.field.name` | string | Site name. | Main screen · field name |
| `summary.field.department` | string | Uruguayan department. | Main screen · field name |
| `summary.field.lat` | number | Latitude, degrees. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `summary.field.lon` | number | Longitude, degrees. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `summary.mock` | boolean | Always false: these are the model's results, not placeholder data. (`status.simulated_reading` says whether the reading is simulated.) | Banner of the main screen |
| `summary.generated_at` | string | When the analysis was run, ISO 8601. | Main screen · «actualizado» |
| `summary.water` | object | Water in the soil. | Main screen · header «Tu campo hoy: N mm de agua útil» |
| `summary.water.mm` | number | Available water in mm that the scenarios start from, derived from the reading with assumed soil parameters. Show it as an estimate, never as measured water. | Main screen · header «Tu campo hoy: N mm de agua útil» |
| `summary.water.capacity_mm` | number | Water the modelled soil can hold, mm. | Main screen · header «Tu campo hoy: N mm de agua útil» |
| `summary.water.source` | one of `sensor`, `smap_corrected`, `balance` | Where the number comes from, in the API's vocabulary: always `sensor` here. | Main screen · header «Tu campo hoy: N mm de agua útil» |
| `summary.water.reliability` | one of `low`, `medium`, `high` | How far to trust it: always `low` until the sensor is calibrated. | Main screen · header «Tu campo hoy: N mm de agua útil» |
| `summary.water.updated_at` | string | When the reading was taken, ISO 8601. | Main screen · header «Tu campo hoy: N mm de agua útil» |
| `summary.water.mm_status` | string | derived_from_assumptions: the millimetres come from assumed soil parameters. | Main screen · header «Tu campo hoy: N mm de agua útil» |
| `summary.water.is_simulated` | boolean | True when the reading is simulated. | Main screen · header «Tu campo hoy: N mm de agua útil» |
| `summary.water.volumetric_moisture` | number | Volumetric moisture in m3/m3 (0 to 0.6) the scenarios start from: the model's own state corrected by the readings of the last year when `series` is given, otherwise the last reading itself. | Main screen · header «Tu campo hoy: N mm de agua útil» |
| `summary.water.reading_moisture` | number or null | The last reading itself, m3/m3; null when there is no series and `volumetric_moisture` is the reading. | Main screen · header «Tu campo hoy: N mm de agua útil» · small print |
| `summary.water.series` | object or null | How the state above was reached from the readings of the last year (simulated while `is_simulated`). | Main screen · moisture chart «sensor vs modelo» |
| `summary.water.series.method` | one of `state_correction` | state_correction: each day the modelled water moves a share `gain` of the way to the reading. | Main screen · moisture chart «sensor vs modelo» |
| `summary.water.series.gain` | number | Share of the gap between model and reading corrected each day (0 ignores the sensor, 1 adopts it). | Main screen · moisture chart «sensor vs modelo» |
| `summary.water.series.days` | integer | Days with a reading. | Main screen · moisture chart «sensor vs modelo» |
| `summary.water.series.carried_days` | integer | Days after the last reading the model ran on its own to reach the last day of the climate record (0 with a sensor that reports every day). | Main screen · moisture chart «sensor vs modelo» |
| `summary.water.series.period` | array | First and last day of the series. | Main screen · moisture chart «sensor vs modelo» |
| `summary.water.series.history` | array | Reading and modelled state of every day, oldest first. | Main screen · moisture chart «sensor vs modelo» |
| `summary.water.series.history[].date` | string | The day, YYYY-MM-DD. | Main screen · moisture chart «sensor vs modelo» |
| `summary.water.series.history[].reading` | number | The reading of that day, m3/m3. | Main screen · moisture chart «sensor vs modelo» |
| `summary.water.series.history[].modeled` | number | The model's state that day after correcting toward the reading, m3/m3. | Main screen · moisture chart «sensor vs modelo» |
| `summary.water.correction` | object or null | Set when the satellite as model B corrects it stands in for the sensor: the readings of `series` are that corrected satellite. | Main screen · header «Tu campo hoy: N mm de agua útil» · small print |
| `summary.water.correction.model` | one of `B` | The model: B. | Main screen · header «Tu campo hoy: N mm de agua útil» · small print |
| `summary.water.correction.version` | integer | Version of model B used. | Main screen · header «Tu campo hoy: N mm de agua útil» · small print |
| `summary.water.correction.last_satellite_day` | string | Last day with a satellite value, YYYY-MM-DD. | Main screen · header «Tu campo hoy: N mm de agua útil» · small print |
| `summary.water.correction.note` | text | What this water rests on, to show as small print. | Main screen · header «Tu campo hoy: N mm de agua útil» · small print |
| `summary.soil` | object | Soil health. The model has no soil diagnosis yet, so the state is null. | Main screen · card «Tu suelo» |
| `summary.soil.state` | one of `good`, `fair`, `poor` or null | good, fair or poor; null while there is no diagnosis. | Main screen · card «Tu suelo» |
| `summary.soil.trend` | one of `improving`, `stable`, `declining` or null | improving, stable or declining; null while there is no diagnosis. | Main screen · card «Tu suelo» |
| `summary.soil.precision` | one of `low`, `medium`, `high` | How precise the estimate is: always `low` for now. | Main screen · card «Tu suelo» |
| `summary.soil.reasons` | array | Reasons for the state; empty while there is no diagnosis. | Main screen · card «Tu suelo» |
| `summary.soil.missing` | array | What is missing, for the line «Estimación de precisión baja: falta …». | Main screen · card «Tu suelo» |
| `summary.options` | array | Options to compare, in the order to show them. The current crop comes first. | Main screen · option card |
| `summary.options[].id` | string | Stable id, e.g. survey_03 or barley@06-10. | Main screen · option card |
| `summary.options[].name` | text | Name of the option, e.g. «Rotación observada 3». | Main screen · option card · title |
| `summary.options[].is_current` | boolean | True for the crop the producer has sown now: «Tu rotación actual», red outline. | Main screen · option card · badge |
| `summary.options[].water_risk` | one of `low`, `medium`, `high` or null | low, medium or high, from the number of high-deficit drops (provisional thresholds); null when nothing was simulated. | Main screen · option card · pill «Agua: riesgo …» |
| `summary.options[].drops` | object or null | The ten drops to draw; null when nothing was simulated (e.g. the cycle already ended). With `risk_basis.source` model_a they are model A's, otherwise the fixed cuts'. | Main screen · option card · ten drops |
| `summary.options[].risk_basis` | object | What `drops` and `water_risk` rest on, with the fixed cuts beside them to compare. | Main screen · option card · small print |
| `summary.options[].risk_basis.source` | one of `model_a`, `fixed_cuts` | model_a when the published model A reads the seasons, fixed_cuts when only the fixed stress cuts do. | Main screen · option card · small print |
| `summary.options[].risk_basis.model_version` | integer or null | Version of model A used; null with the fixed cuts. | Main screen · option card · small print |
| `summary.options[].risk_basis.fixed_cuts_drops` | object or null | The drops the fixed cuts of stress give. | Main screen · option card · small print |
| `summary.options[].risk_basis.fixed_cuts_water_risk` | one of `low`, `medium`, `high` or null | low, medium or high from the fixed cuts. | Main screen · option card · small print |
| `summary.options[].sentence` | text | One sentence for the card, e.g. «En 4 de cada 10 zafras históricas faltó agua en la etapa crítica». | Main screen · option card · sentence |
| `summary.options[].soil_effect` | one of `improves`, `stays`, `worsens` or null | improves, stays or worsens; always null: the model does not estimate it. | Main screen · option card · «Suelo: …» |
| `summary.options[].soil_reason` | text or null | Why the soil effect; always null. | Main screen · option card · «Suelo: …» |
| `summary.options[].why` | text or null | Longer explanation; always null. | Option detail view |
| `summary.options[].evidence` | array | Evidence for the option; empty for now. | Option detail view |
| `summary.options[].benefits` | array | Benefits; empty for now. | Option detail view |
| `summary.options[].gaps` | array | What the evaluation does not cover (fixed cycle length, far sowing date...). | Option detail view |
| `summary.options[].risks` | array | Risks; empty for now. | Option detail view |
| `summary.options[].kind` | one of `crop`, `rotation` | What the option is. | Main screen · option card |
| `summary.options[].detail` | text | The exact counts as a sentence, e.g. «104 de 280 combinaciones año-zafra con déficit alto». | Option detail view |
| `summary.options[].sowing` | string or null | Sowing day of a crop, MM-DD; null for a rotation. | Main screen · option card · subtitle |
| `summary.options[].critical_window` | object or null | Critical stage of the crop. | Main screen · option card · subtitle |
| `summary.options[].critical_window.start` | string | DD/MM. | Main screen · option card · subtitle |
| `summary.options[].critical_window.end` | string | DD/MM. | Main screen · option card · subtitle |
| `summary.options[].cycle_status` | one of `cycle_ended`, `critical_stage_passed`, `critical_stage_ahead`, `in_critical_stage` or null | For the crop already sown: where it is in its cycle. | Main screen · option card · sentence |
| `summary.options[].evaluated` | integer | Seasons (crop) or season-crop combinations (rotation) evaluated; 0 when nothing can be simulated. | Option detail view |
| `summary.options[].high_deficit` | integer or null | How many of the evaluated ones fell in high deficit. | Option detail view |
| `summary.options[].season_counts` | object or null | Counts per deficit class; null when nothing was simulated. | Option detail view |
| `summary.options[].crops` | array | Crops of a rotation in the written order; empty for a crop. | Main screen · option card · crops line |
| `summary.options[].crops[].name` | text | Crop name, as modelled (e.g. «Soja de segunda»). | Main screen · option card · crops line |
| `summary.options[].crops[].status` | one of `modelled`, `cover_without_risk`, `not_modelled` | modelled: its stress is reported; cover_without_risk: a cover crop with no stress of its own; not_modelled: no parameters yet. | Main screen · option card · crops line |
| `summary.options[].note` | text or null | How a rotation is evaluated: each crop-year on its own, order not simulated. | Option detail view |
| `inputs` | object | What the producer and the agronomist entered, normalised: crops as ids, days as MM-DD. | Data screen |
| `inputs.farmer` | object | The producer's part of the form. | Data screen · Productor «Tu campo» |
| `inputs.farmer.current_crop` | object | The crop sown now. | Data screen · Productor «Tu campo» · «¿Qué tienes sembrado ahora?» |
| `inputs.farmer.current_crop.crop` | string or null | Crop id from catalog.crops; null if none was entered. | Data screen · Productor «Tu campo» · crop chips |
| `inputs.farmer.current_crop.sowing_day` | string or null | Day it was sown, MM-DD. | Data screen · Productor «Tu campo» · «¿Cuándo lo sembraste?» |
| `inputs.farmer.seasons` | array | The producer's last seasons. | Data screen · Productor «Tu campo» · «Tus últimas zafras» |
| `inputs.farmer.seasons[].season` | string | Season, e.g. 2025/26. | Data screen · Productor «Tu campo» · season title |
| `inputs.farmer.seasons[].crops` | array | Crops grown in the season (e.g. barley + soybean_2nd), shown joined by « + ». | Data screen · Productor «Tu campo» · season crops |
| `inputs.farmer.seasons[].rating` | integer or null | How the season went, 1 (muy mal) to 5 (excelente). | Data screen · Productor «Tu campo» · rating buttons |
| `inputs.farmer.seasons[].yield_kg_ha` | number or null | Yield in kg/ha, optional, used instead of the scale. | Data screen · Productor «Tu campo» · «puedes escribirlo» |
| `inputs.farmer.seasons[].confirmed` | boolean | False while the season is only a suggestion (e.g. from satellite). | Data screen · Productor «Tu campo» · chip «sugeridas» |
| `inputs.agronomist` | object | The agronomist's part of the form; every datum is optional. | Data screen · Agrónomo «Datos técnicos del campo» |
| `inputs.agronomist.soil_test` | object | The soil analysis. | Data screen · Agrónomo «Datos técnicos del campo» · «Análisis de suelo» |
| `inputs.agronomist.soil_test.date` | string or null | Date of the analysis, YYYY-MM. | Data screen · Agrónomo «Datos técnicos del campo» · «Fecha del análisis» |
| `inputs.agronomist.soil_test.om_pct` | number or null | Organic matter, %. | Data screen · Agrónomo «Datos técnicos del campo» · «Materia orgánica (%)» |
| `inputs.agronomist.soil_test.p_bray_ppm` | number or null | Phosphorus (Bray), ppm. | Data screen · Agrónomo «Datos técnicos del campo» · «Fósforo Bray (ppm)» |
| `inputs.agronomist.soil_test.ph` | number or null | pH. | Data screen · Agrónomo «Datos técnicos del campo» · «pH» |
| `inputs.agronomist.erosion_t_ha_yr` | number or null | Estimated erosion, t/ha/year. | Data screen · Agrónomo «Datos técnicos del campo» · «Erosión estimada» |
| `inputs.agronomist.soil_type` | object | The soil type. | Data screen · Agrónomo «Datos técnicos del campo» · «Tipo de suelo» |
| `inputs.agronomist.soil_type.description` | string or null | CONEAT code and soil name, e.g. «CONEAT 10.8b, Brunosol». | Data screen · Agrónomo «Datos técnicos del campo» · soil card |
| `inputs.agronomist.soil_type.confirmed` | boolean or null | Whether the agronomist confirmed it (buttons «Confirmar» / «Corregir»). | Data screen · Agrónomo «Datos técnicos del campo» · soil card |
| `scenarios` | object | The result of every historical season for every option, in the shape of the API's scenarios. | Agronomist chart · yearly result of each option |
| `scenarios.from_year` | integer | Start year of the first season. | Agronomist chart · yearly result of each option |
| `scenarios.to_year` | integer | Start year of the last season. | Agronomist chart · yearly result of each option |
| `scenarios.options` | array | Options, in the same order as summary.options. | Agronomist chart · yearly result of each option |
| `scenarios.options[].id` | string | Same id as in summary.options. | Agronomist chart · yearly result of each option |
| `scenarios.options[].name` | text | Name of the option. | Agronomist chart · yearly result of each option |
| `scenarios.options[].years` | array | One result per season from `from_year` to `to_year`, in order; for a rotation, the class of the mean unmet demand of its modelled crops that season; empty when nothing was simulated. | Agronomist chart · yearly result of each option |
| `catalog` | object | The closed lists the forms offer: nothing is typed as free text. | Data screen |
| `catalog.crops` | array | Crops that can be sown on a date. | Data screen · Productor «Tu campo» · crop chips |
| `catalog.crops[].id` | string | Crop id. | Data screen · Productor «Tu campo» · crop chips |
| `catalog.crops[].name` | text | Name to show. | Data screen · Productor «Tu campo» · crop chips |
| `catalog.history_crops` | array | Crops valid in the history, including ones the model cannot simulate yet. | Data screen · Productor «Tu campo» · season crops |
| `catalog.history_crops[].id` | string | Crop id. | Data screen · Productor «Tu campo» · season crops |
| `catalog.history_crops[].name` | text | Name to show. | Data screen · Productor «Tu campo» · season crops |
| `catalog.ratings` | array | The rating scale. | Data screen · Productor «Tu campo» · rating buttons |
| `catalog.ratings[].value` | integer | 1 to 5. | Data screen · Productor «Tu campo» · rating buttons |
| `catalog.ratings[].label` | text | Button text, e.g. «Muy mal». | Data screen · Productor «Tu campo» · rating buttons |
| `catalog.seasons` | array | Seasons the history can cover, newest first. | Data screen · Productor «Tu campo» · season selector |
| `catalog.modes` | array | The four states of the panel with the text of each badge, `offline` included (only the panel can know it). | Badge at the top of every screen |
| `catalog.modes[].id` | one of `demo`, `live`, `pending`, `error`, `offline` | demo, live, pending, error or offline. | Badge at the top of every screen |
| `catalog.modes[].badge` | text | Badge text for the state. | Badge at the top of every screen |
| `catalog.modes[].meaning` | text | When the state applies and what to show. | Badge at the top of every screen |
| `charts` | array | The charts, in a fixed order: the data behind every figure of the experiment log. | Charts screen · one chart per entry, mirroring a figure of the experiment log |
| `charts[].id` | string | Stable id of the chart, e.g. sensor_series or sowing_maize. | Charts screen · one chart per entry, mirroring a figure of the experiment log |
| `charts[].figure` | string | The figure of reports/experiments.md it mirrors (retrospective, sowing, survey, smap, ndvi, imerg, rain_decision, sensor, sensor_windows, sensor_recalibration); a figure can have several charts. | Charts screen · one chart per entry, mirroring a figure of the experiment log |
| `charts[].group` | one of `sowing`, `validation`, `rain`, `sensor`, `retrospective` | Where to file it: sowing (what happens if a crop is sown on a date), validation (against independent data), rain (POWER vs IMERG), sensor (the simulated-sensor experiments) or retrospective (what the tool would have said before each past season). | Charts screen · one chart per entry, mirroring a figure of the experiment log |
| `charts[].title` | text | Title of the chart. | Charts screen · one chart per entry, mirroring a figure of the experiment log · title |
| `charts[].note` | text or null | The caveat to print under the chart. | Charts screen · one chart per entry, mirroring a figure of the experiment log · small print |
| `charts[].x` | object | The horizontal axis, shared by every series. | Charts screen · one chart per entry, mirroring a figure of the experiment log · x axis |
| `charts[].x.type` | one of `category`, `date`, `month_day`, `number` | category: the values are ids (names tells how to show them); date: YYYY-MM-DD; month_day: MM-DD, a calendar day without year; number: a quantity, where a point is placed by its value. | Charts screen · one chart per entry, mirroring a figure of the experiment log · x axis |
| `charts[].x.label` | text or null | Axis title. | Charts screen · one chart per entry, mirroring a figure of the experiment log · x axis |
| `charts[].x.values` | array | The positions, in order: ids, dates or numbers according to `type`. | Charts screen · one chart per entry, mirroring a figure of the experiment log · x axis |
| `charts[].x.names` | array or null | One name per value, when the ids need one (runs, soils, predictors); null otherwise. | Charts screen · one chart per entry, mirroring a figure of the experiment log · x axis |
| `charts[].x.tags` | array or null | One tag per value, for scatter charts where the position is a quantity (the season of each point); null otherwise. | Charts screen · one chart per entry, mirroring a figure of the experiment log · point tooltip |
| `charts[].y` | object | The vertical axis. | Charts screen · one chart per entry, mirroring a figure of the experiment log · y axis |
| `charts[].y.label` | text or null | Axis title. | Charts screen · one chart per entry, mirroring a figure of the experiment log · y axis |
| `charts[].y.unit` | string or null | Unit of the values: m3/m3 or mm; null for counts, shares and scores. | Charts screen · one chart per entry, mirroring a figure of the experiment log · y axis |
| `charts[].stacked` | boolean | True when the series are parts of one bar (stack them) instead of bars side by side. | Charts screen · one chart per entry, mirroring a figure of the experiment log |
| `charts[].simulated` | boolean | True when the data comes from a simulated sensor or a simulated reading: show the demo badge on it. | Charts screen · one chart per entry, mirroring a figure of the experiment log · badge |
| `charts[].source` | string | Where the numbers come from: nasa_power, gpm_imerg, smap_l3, modis_ndvi, producer_survey, simulated_sensor or simulated_panel. | Charts screen · one chart per entry, mirroring a figure of the experiment log · small print |
| `charts[].series` | array | The series to draw. | Charts screen · one chart per entry, mirroring a figure of the experiment log |
| `charts[].series[].id` | string | Id of the series. | Charts screen · one chart per entry, mirroring a figure of the experiment log |
| `charts[].series[].label` | text | Legend entry. | Charts screen · one chart per entry, mirroring a figure of the experiment log · legend |
| `charts[].series[].style` | one of `bar`, `line`, `points` | How to draw it: bar, line or points. | Charts screen · one chart per entry, mirroring a figure of the experiment log |
| `charts[].series[].values` | array | One value per position of `x.values`, in the same order; null when there is none. | Charts screen · one chart per entry, mirroring a figure of the experiment log |
| `learning` | object or null | What the models A, B and C add: their versions and how well they did, model A's reading of every option, model B's correction of the satellite and model C's proposal of the crop history. Null when no registry of trained models was given. | Model screen · what the three models add to the analysis |
| `learning.simulated` | boolean | True while the models were trained on the simulated panel: show the demo badge on it. | Model screen · what the three models add to the analysis · badge |
| `learning.note` | text | What the numbers mean and do not mean. | Model screen · what the three models add to the analysis · small print |
| `learning.models` | array | The published models, B, A and C. | Model screen · what the three models add to the analysis |
| `learning.models[].id` | one of `A`, `B`, `C` | A, B or C. | Model screen · what the three models add to the analysis · model card |
| `learning.models[].role` | text | What the model does. | Model screen · what the three models add to the analysis · model card |
| `learning.models[].version` | integer | Version number of the published model. | Model screen · what the three models add to the analysis · model card |
| `learning.models[].state` | one of `published`, `candidate`, `retired` | published, candidate or retired; only published models are shown. | Model screen · what the three models add to the analysis · model card |
| `learning.models[].trained_on` | string | Date of the training, YYYY-MM-DD. | Model screen · what the three models add to the analysis · model card |
| `learning.models[].examples` | integer | Examples the model learned from. | Model screen · what the three models add to the analysis · model card |
| `learning.models[].fields` | integer | Fields those examples come from. | Model screen · what the three models add to the analysis · model card |
| `learning.models[].simulated_data` | boolean | True when every example was simulated. | Model screen · what the three models add to the analysis · badge |
| `learning.models[].metric` | object | How the model did on fields it never saw, against the fixed rule it replaces. | Model screen · what the three models add to the analysis · model card |
| `learning.models[].metric.name` | text | The metric. | Model screen · what the three models add to the analysis · model card |
| `learning.models[].metric.value` | number | The model's value. | Model screen · what the three models add to the analysis · model card |
| `learning.models[].metric.fixed_rule_name` | text | The metric of the fixed rule. | Model screen · what the three models add to the analysis · model card |
| `learning.models[].metric.fixed_rule` | number | The fixed rule's value. | Model screen · what the three models add to the analysis · model card |
| `learning.models[].metric.lower_is_better` | boolean | True for an error, false for an accuracy. | Model screen · what the three models add to the analysis · model card |
| `learning.models[].metric.better` | boolean | True when the model beats the fixed rule. | Model screen · what the three models add to the analysis · model card |
| `learning.models[].reason` | string | Why it was published or not. | Model screen · what the three models add to the analysis · model card |
| `learning.options` | array | One entry per option with seasons to read. | Model screen · what the three models add to the analysis |
| `learning.options[].id` | string | Id of the option, as in summary.options. | Model screen · what the three models add to the analysis · option card |
| `learning.options[].model_version` | integer | Version of model A used. | Model screen · what the three models add to the analysis · option card |
| `learning.options[].seasons` | integer | Crop-seasons read: the ones the option's drops count (summary.options.evaluated). | Model screen · what the three models add to the analysis · option card |
| `learning.options[].of_10` | object | Of 10 seasons, how many model A expects the producer to call good (ok), normal (tight) or bad (out). | Model screen · what the three models add to the analysis |
| `learning.options[].of_10.ok` | integer | Seasons out of 10 with enough water. | Model screen · what the three models add to the analysis |
| `learning.options[].of_10.tight` | integer | Seasons out of 10 with tight water. | Model screen · what the three models add to the analysis |
| `learning.options[].of_10.out` | integer | Seasons out of 10 without water. | Model screen · what the three models add to the analysis |
| `learning.options[].water_risk` | one of `low`, `medium`, `high` or null | low, medium or high from model A's drops. | Model screen · what the three models add to the analysis · option card |
| `learning.options[].fixed_cuts_of_10` | object | The same with the fixed cuts of stress (what summary.options.drops shows). | Model screen · what the three models add to the analysis |
| `learning.options[].fixed_cuts_of_10.ok` | integer | Seasons out of 10 with enough water. | Model screen · what the three models add to the analysis |
| `learning.options[].fixed_cuts_of_10.tight` | integer | Seasons out of 10 with tight water. | Model screen · what the three models add to the analysis |
| `learning.options[].fixed_cuts_of_10.out` | integer | Seasons out of 10 without water. | Model screen · what the three models add to the analysis |
| `learning.options[].fixed_cuts_water_risk` | one of `low`, `medium`, `high` or null | low, medium or high from the fixed cuts. | Model screen · what the three models add to the analysis · option card |
| `learning.satellite` | object or null | Model B on the last days of the demo field: the satellite as it is, corrected, and the sensor. | Model screen · what the three models add to the analysis · satellite chart |
| `learning.satellite.model_version` | integer | Version of model B used. | Model screen · what the three models add to the analysis · satellite chart |
| `learning.satellite.field_id` | string | The field. | Model screen · what the three models add to the analysis · satellite chart |
| `learning.satellite.dates` | array | The days. | Model screen · what the three models add to the analysis · satellite chart |
| `learning.satellite.satellite` | array | One value per day. | Model screen · what the three models add to the analysis · satellite chart |
| `learning.satellite.corrected` | array | One value per day. | Model screen · what the three models add to the analysis · satellite chart |
| `learning.satellite.sensor` | array | One value per day. | Model screen · what the three models add to the analysis · satellite chart |
| `learning.satellite.rmse` | object | Error against the sensor over these days. | Model screen · what the three models add to the analysis · satellite chart |
| `learning.satellite.rmse.satellite` | number | Error of the satellite as it is. | Model screen · what the three models add to the analysis · satellite chart |
| `learning.satellite.rmse.corrected` | number | Error after model B. | Model screen · what the three models add to the analysis · satellite chart |
| `learning.satellite.unit` | string | m3/m3. | Model screen · what the three models add to the analysis · satellite chart |
| `learning.satellite.sensor_simulated` | boolean | True while the sensor is simulated. | Model screen · what the three models add to the analysis · badge |
| `learning.satellite.in_sample` | boolean | True when the field is one the model learned from, so this is not a test. | Model screen · what the three models add to the analysis · small print |
| `learning.satellite.note` | text | The caveat. | Model screen · what the three models add to the analysis · small print |
| `learning.crop_history` | array | One proposal per season with a complete MODIS curve at the demo field's point (real NASA data, a 250 m pixel that mixes fields). | Model screen · what the three models add to the analysis |
| `learning.crop_history[].season` | string | The season, e.g. 2022/23. | Model screen · what the three models add to the analysis · history proposal |
| `learning.crop_history[].crop` | string | Crop id or `fallow`. | Model screen · what the three models add to the analysis · history proposal |
| `learning.crop_history[].crop_name` | text | Name of the crop. | Model screen · what the three models add to the analysis · history proposal |
| `learning.crop_history[].confidence` | number | Share of the forest's votes the answer got, 0 to 1; low confidence means ask instead of propose. | Model screen · what the three models add to the analysis · history proposal |
| `learning.crop_history[].action` | one of `propose`, `ask` | propose when the confidence is enough to suggest the crop, ask when it is not and the app should ask the producer. | Model screen · what the three models add to the analysis · history proposal |
| `learning.crop_history[].confirmed` | boolean | False: the producer has not confirmed it. | Model screen · what the three models add to the analysis · history proposal |
| `learning.crop_history[].start_offset` | integer | Days from 1 April when the field turns green, -1 if it never does. | Model screen · what the three models add to the analysis · history proposal · detail |
| `learning.crop_history[].peak_offset` | integer | Days from 1 April of the greenest composite. | Model screen · what the three models add to the analysis · history proposal · detail |
| `learning.crop_history[].peak_value` | number | NDVI at the peak. | Model screen · what the three models add to the analysis · history proposal · detail |
| `learning.crop_history[].duration_days` | integer | Days the field stays green. | Model screen · what the three models add to the analysis · history proposal · detail |
| `learning.crop_history[].peaks` | integer | Number of green peaks. | Model screen · what the three models add to the analysis · history proposal · detail |
| `calendar` | object | The field on every date of the last year for every crop that can be sown, so the panel can answer «I open the app on this date and pick this crop» from this file alone. | Date picker · the field on a chosen date and crop |
| `calendar.step_days` | integer | Days between two dates of the calendar. | Date picker · the field on a chosen date and crop |
| `calendar.offer_days` | integer | A sowing further than this from the date is `offered: false`: the water of the date has faded. | Date picker · the field on a chosen date and crop |
| `calendar.from` | string | First date, YYYY-MM-DD. | Date picker · the field on a chosen date and crop |
| `calendar.to` | string | Last date, YYYY-MM-DD: the same day as `as_of`. | Date picker · the field on a chosen date and crop |
| `calendar.dates` | array | One entry per date, oldest first. | Date picker · the field on a chosen date and crop |
| `calendar.dates[].date` | string | The date, YYYY-MM-DD. | Date picker · the field on a chosen date and crop |
| `calendar.dates[].water` | object | The field's water that day (the same estimate as summary.water: assumed soil parameters, never measured water). | Date picker · the field on a chosen date and crop · header |
| `calendar.dates[].water.mm` | number | Available water in mm that day. | Date picker · the field on a chosen date and crop · header |
| `calendar.dates[].water.capacity_mm` | number | Water the modelled soil can hold, mm. | Date picker · the field on a chosen date and crop · header |
| `calendar.dates[].water.volumetric_moisture` | number | Volumetric moisture that day, m3/m3. | Date picker · the field on a chosen date and crop · header |
| `calendar.dates[].options` | array | One entry per crop that can be sown (catalog.crops). | Date picker · the field on a chosen date and crop |
| `calendar.dates[].options[].crop` | string | Crop id, as in catalog.crops. | Date picker · the field on a chosen date and crop · option card |
| `calendar.dates[].options[].sowing` | string | The crop's next sowing date, MM-DD. | Date picker · the field on a chosen date and crop · option card |
| `calendar.dates[].options[].days_to_sowing` | integer | Days from the date to that sowing. | Date picker · the field on a chosen date and crop · option card |
| `calendar.dates[].options[].offered` | boolean | True when the sowing is within `offer_days` of the date: show these first; the others are a rough guide. | Date picker · the field on a chosen date and crop · option card |
| `calendar.dates[].options[].evaluated` | integer | Historical seasons evaluated. | Date picker · the field on a chosen date and crop · option card |
| `calendar.dates[].options[].water_risk` | one of `low`, `medium`, `high` or null | low, medium or high from `drops`. | Date picker · the field on a chosen date and crop · option card · pill |
| `calendar.dates[].options[].drops` | object or null | The ten drops of the option's seasons: model A's when `risk_basis.source` is model_a, the fixed cuts' otherwise. | Date picker · the field on a chosen date and crop · option card · ten drops |
| `calendar.dates[].options[].risk_basis` | object | What `drops` rest on, with the fixed cuts beside them. | Date picker · the field on a chosen date and crop · small print |
| `calendar.dates[].options[].risk_basis.source` | one of `model_a`, `fixed_cuts` | model_a or fixed_cuts. | Date picker · the field on a chosen date and crop · small print |
| `calendar.dates[].options[].risk_basis.model_version` | integer or null | Version of model A used; null with the fixed cuts. | Date picker · the field on a chosen date and crop · small print |
| `calendar.dates[].options[].risk_basis.fixed_cuts_drops` | object or null | The drops the fixed cuts of stress give. | Date picker · the field on a chosen date and crop · small print |
| `calendar.dates[].options[].risk_basis.fixed_cuts_water_risk` | one of `low`, `medium`, `high` or null | low, medium or high from the fixed cuts. | Date picker · the field on a chosen date and crop · small print |
| `calendar.dates[].options[].critical_window` | object or null | The crop's critical stage, day/month. | Date picker · the field on a chosen date and crop · option card |
| `calendar.dates[].options[].critical_window.start` | string | DD/MM. | Date picker · the field on a chosen date and crop · option card |
| `calendar.dates[].options[].critical_window.end` | string | DD/MM. | Date picker · the field on a chosen date and crop · option card |
| `calendar.dates[].options[].median_water_at_sowing_mm` | number or null | Median across seasons of the water the soil holds on the sowing day, mm. | Date picker · the field on a chosen date and crop · option card · detail |
| `calendar.dates[].options[].warnings` | array | Warnings of this option. | Date picker · the field on a chosen date and crop · option card · gaps |
| `calendar.warnings` | array | The texts of every code used in `options[].warnings`. | Date picker · the field on a chosen date and crop |
| `calendar.warnings[].code` | string | The code. | Date picker · the field on a chosen date and crop · option card · gaps |
| `calendar.warnings[].text` | text | What it says. | Date picker · the field on a chosen date and crop · option card · gaps |

## The error document

When the analysis cannot be built the file holds this instead (`frontend.error.schema.json`): show `status.badge` and `status.error`, and no numbers.

| Field | Type | Meaning | Used in |
| --- | --- | --- | --- |
| `schema_version` | string | Version of this schema. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `generated_at` | string | When the analysis was attempted, ISO 8601. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `status` | object | The analysis failed: the badge and what went wrong. | Badge at the top of every screen |
| `status.mode` | string | Always `error`. | Badge at the top of every screen |
| `status.badge` | text | Badge text, «Análisis no disponible». | Badge at the top of every screen |
| `status.error` | object | What failed. | Error message of the screen |
| `status.error.code` | string | Stable code of the failure, e.g. climate_gap, invalid_answers, internal_error. | Error message of the screen |
| `status.error.field` | string or null | The field or input that failed; null when it is not tied to one. | Error message of the screen |
| `status.error.message` | string | What happened, in English, for a person to read. | Error message of the screen |
