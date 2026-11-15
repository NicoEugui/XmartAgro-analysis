"""What every soil system must give: a unit for a point, in one shape."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SoilUnit:
    """A soil unit of some system: where a point falls, and what that unit says about its soil."""

    system: str  # "coneat", or the name of another country's system
    code: str  # the unit's code in that system, e.g. "11.4"
    productivity_index: float | None  # the system's own index of what the soil can produce (CONEAT: 100 is the country's average)
    dominant_orders: tuple[str, ...]  # soil orders that dominate the unit, e.g. ("Vertisol", "Brunosol")


class SoilMap(Protocol):
    system: str

    def lookup(self, latitude: float, longitude: float) -> SoilUnit | None:
        """The soil unit of a point, or None if the point is outside the map."""
        ...


class NullSoilMap:
    """No soil system configured: every lookup is None and the project uses its own defaults."""

    system = "none"

    def lookup(self, latitude, longitude):
        return None
