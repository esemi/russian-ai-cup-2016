from .LineType import LineType
from .SkillType import SkillType


class Message:
    def __init__(self, line: (None, LineType), skill_to_learn: (None, SkillType), raw_message):
        self.line = line
        self.skill_to_learn = skill_to_learn
        self.raw_message = raw_message
