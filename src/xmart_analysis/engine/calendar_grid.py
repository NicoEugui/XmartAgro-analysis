"""The field on any day of the last year, for every crop: what the panel needs to answer «what if I open the app on this date and pick this crop».

The front is a static file, so the answers are worked out here once, for a calendar of dates (one every `calendar_step_days`, back from the last day of the
climate record) and every crop that can be sown. For each date the water is the field's state on that day (the series of readings, or the satellite model B
corrects, run day by day), and each crop is evaluated by the same function the main screen uses (`platform_session.crop_card`), at the crop's next sowing date.
A sowing further than `far_sowing_days` away carries the engine's own warning: the water the field has today fades with time.
"""

from datetime import date, timedelta

from . import crops_uy as cu
from . import platform_session as ps
from . import sensor_series, tables
from . import sensor_input as si
from . import water_model as wm
from . import water_scenarios as ws


def state_by_day(session, context):
    """{day: moisture} of the field every day from the first reading to the last day of the climate record.

    It is the series of the main screen (the model's water corrected toward each reading) with the days without a reading filled in by the model, and
    after the last reading the model runs on alone, as it does for the water the main screen starts from."""
    soil = session["outputs"]["main_screen"]["soil_water"]
    if not soil.get("series"):  # one reading and no series: the only day the field's state is known
        return {date.fromisoformat((soil.get("reading_date") or max(context["weather"]).isoformat())[:10]): soil["volumetric_moisture"]}
    history = soil["series"]["history"]
    states = sensor_series.assimilate(context, {date.fromisoformat(h["date"]): h["reading"] for h in history})
    last, end = max(states), max(context["weather"])
    if last < end:
        states.update(wm.simulate_moisture(context["params"], context["weather"], context["et0"], last, end, states[last]))
    return states


def calendar_days(states, step=None):
    """The dates offered, oldest first: the last day of the series and one every `step` days back to the first."""
    step = timedelta(days=step or tables.constant("calendar_step_days"))
    first, last = min(states), max(states)
    days, day = [], last
    while day >= first:
        days.append(day)
        day -= step
    return sorted(days)


def next_sowing(crop, day):
    """((month, day), days until it): the crop's default sowing date on or after `day`."""
    month, mday = cu.CROPS[crop]["sowing"]
    for year in (day.year, day.year + 1):
        sowing = ws.safe_date(year, month, mday)
        if sowing >= day:
            return (month, mday), (sowing - day).days


def build(session, context, crops=None):
    """[{date, moisture, water_mm, cards: [(days until sowing, crop card)]}] for every date of the calendar and every crop that can be sown."""
    soil = session["outputs"]["main_screen"]["soil_water"]
    info = {"source": soil["source"], "is_simulated": soil["is_simulated"]}
    kw = {"params": context["params"], "weather": context["weather"], "et0": context["et0"]}
    states = state_by_day(session, context)
    out = []
    for day in calendar_days(states):
        theta, cards = states[day], []
        for crop in crops or ps.CROP_CHOICES:
            sowing, days = next_sowing(crop, day)
            cards.append((days, ps.crop_card(crop, sowing, theta, (day.month, day.day), False, kw, info)))
        out.append({"date": day, "moisture": theta, "water_mm": si.to_available_water_mm(theta, context["params"]), "cards": cards})
    return out
