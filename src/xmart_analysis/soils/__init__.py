"""Soil maps as a plug-in: ask a soil system which soil unit a coordinate falls in, whatever the country.

The rest of the project never names a system. It asks a `SoilMap` for the `SoilUnit` of a point and reads the same few things from it
(code, productivity index, dominant soil orders). Uruguay's system is CONEAT (`coneat.py`); another country adds an adapter that returns
the same `SoilUnit` (and is registered in `SYSTEMS`), and nothing else changes. With no system (`NullSoilMap`) the project works as before.
"""

from .coneat import ConeatMap
from .ports import NullSoilMap, SoilMap, SoilUnit

SYSTEMS = {"none": NullSoilMap, "coneat": ConeatMap}  # name -> adapter class; a new country's system is one more entry

__all__ = ["ConeatMap", "NullSoilMap", "SYSTEMS", "SoilMap", "SoilUnit"]
