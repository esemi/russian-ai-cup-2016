from .Faction import Faction
from .Unit import Unit


class CircularUnit(Unit):
    def __init__(self, id, x, y, speed_x, speed_y, angle, faction: (None, Faction), radius):
        Unit.__init__(self, id, x, y, speed_x, speed_y, angle, faction)

        self.radius = radius
