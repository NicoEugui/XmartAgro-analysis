"""Data contract of the platform: which input feeds which output.

Every field a person (or the sensor backend) provides is declared here with its source, whether the
engine uses it today, and which outputs depend on it. The contract is shown at the start of a session and
verified by tests: changing a field marked `used` changes the engine output; changing a field marked
`stored_only` does not. This is how we know that what the platform asks for is what the output needs.
"""

INPUT_FIELDS = [
    {"field": "sensor.moisture", "source": "sensor", "label": "contract.field.sensor_moisture", "required": True,
     "status": "used", "outputs": ["main_screen", "option_cards"]},
    {"field": "reading_date", "source": "sensor", "label": "contract.field.reading_date", "required": True,
     "status": "used", "outputs": ["main_screen", "option_cards"]},
    {"field": "current_crop.crop", "source": "producer", "label": "contract.field.current_crop", "required": False,
     "status": "used", "outputs": ["option_cards"]},
    {"field": "current_crop.sowing", "source": "producer", "label": "contract.field.current_sowing", "required": False,
     "status": "used", "outputs": ["option_cards"]},
    {"field": "options", "source": "producer", "label": "contract.field.options", "required": True,
     "status": "used", "outputs": ["option_cards"]},
    {"field": "past_seasons.crops", "source": "producer", "label": "contract.field.past_crops", "required": False,
     "status": "stored_only", "outputs": ["data_sheet"]},
    {"field": "past_seasons.rating", "source": "producer", "label": "contract.field.past_rating", "required": False,
     "status": "stored_only", "outputs": ["data_sheet"]},
    {"field": "past_seasons.yield_kg_ha", "source": "producer", "label": "contract.field.past_yield", "required": False,
     "status": "stored_only", "outputs": ["data_sheet"]},
    {"field": "agronomist.analysis_date", "source": "agronomist", "label": "contract.field.analysis_date",
     "required": False, "status": "stored_only", "outputs": ["data_sheet"]},
    {"field": "agronomist.organic_matter_pct", "source": "agronomist", "label": "contract.field.organic_matter",
     "required": False, "status": "stored_only", "outputs": ["data_sheet"]},
    {"field": "agronomist.phosphorus_ppm", "source": "agronomist", "label": "contract.field.phosphorus",
     "required": False, "status": "stored_only", "outputs": ["data_sheet"]},
    {"field": "agronomist.ph", "source": "agronomist", "label": "contract.field.ph",
     "required": False, "status": "stored_only", "outputs": ["data_sheet"]},
    {"field": "agronomist.erosion_t_ha_yr", "source": "agronomist", "label": "contract.field.erosion",
     "required": False, "status": "stored_only", "outputs": ["data_sheet"]},
    {"field": "agronomist.soil_type", "source": "agronomist", "label": "contract.field.soil_type",
     "required": False, "status": "stored_only", "outputs": ["data_sheet"]},
]

OUTPUTS = {
    "main_screen": "contract.output.main_screen",
    "option_cards": "contract.output.option_cards",
    "data_sheet": "contract.output.data_sheet",
}


def used_fields():
    return [f["field"] for f in INPUT_FIELDS if f["status"] == "used"]


def stored_fields():
    return [f["field"] for f in INPUT_FIELDS if f["status"] == "stored_only"]


def fields_for_output(output):
    return [f["field"] for f in INPUT_FIELDS if output in f["outputs"]]
