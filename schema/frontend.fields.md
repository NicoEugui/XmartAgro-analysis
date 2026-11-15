# Frontend data: what every field means and where it is used

Generated from `frontend.schema.json` (do not edit by hand). Text fields are `{key, en, es}`: show `en` or `es`. `[]` marks the items of a list and `{name}` the free keys of a map. The shape follows the panel's API contract (`summary`, `inputs`, `scenarios`).

| Field | Type | Meaning | Used in |
| --- | --- | --- | --- |
| `schema_version` | string | Version of this schema. | Not drawn on the current screens: context for a header, a footer or the presentation |
| `generated_at` | string | When the analysis was run, ISO 8601. | Not drawn on the current screens: context for a header, a footer or the presentation |
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
| `status.mode` | one of `demo`, `live` | demo while any input is simulated, live when every input is measured or entered by a person. The panel adds `offline` itself when it cannot read the file, and the error document says `error`; catalog.modes explains the four. | Badge at the top of every screen |
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
| `summary.water.series.period` | array | First and last day of the series. | Main screen · moisture chart «sensor vs modelo» |
| `summary.water.series.history` | array | Reading and modelled state of every day, oldest first. | Main screen · moisture chart «sensor vs modelo» |
| `summary.water.series.history[].date` | string | The day, YYYY-MM-DD. | Main screen · moisture chart «sensor vs modelo» |
| `summary.water.series.history[].reading` | number | The reading of that day, m3/m3. | Main screen · moisture chart «sensor vs modelo» |
| `summary.water.series.history[].modeled` | number | The model's state that day after correcting toward the reading, m3/m3. | Main screen · moisture chart «sensor vs modelo» |
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
| `summary.options[].drops` | object or null | The ten drops to draw; null when nothing was simulated (e.g. the cycle already ended). | Main screen · option card · ten drops |
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
| `catalog.modes[].id` | one of `demo`, `live`, `error`, `offline` | demo, live, error or offline. | Badge at the top of every screen |
| `catalog.modes[].badge` | text | Badge text for the state. | Badge at the top of every screen |
| `catalog.modes[].meaning` | text | When the state applies and what to show. | Badge at the top of every screen |

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
