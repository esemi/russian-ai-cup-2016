from .BonusType import BonusType
from .CircularUnit import CircularUnit
from .Faction import Faction


class Bonus(CircularUnit):
    def __init__(self, id, x, y, speed_x, speed_y, angle, faction: (None, Faction), radius, type: (None, BonusType)):
        CircularUnit.__init__(self, id, x, y, speed_x, speed_y, angle, faction, radius)

        self.type = type
