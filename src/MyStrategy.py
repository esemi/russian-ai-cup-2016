from src.model.ActionType import ActionType
from src.model.Game import Game
from src.model.Move import Move
from src.model.Wizard import Wizard
from src.model.World import World


class MyStrategy:
    def move(self, me: Wizard, world: World, game: Game, move: Move):
        move.speed = game.wizard_forward_speed
        move.strafe_speed = game.wizard_strafe_speed
        move.turn = game.wizard_max_turn_angle
        move.action = ActionType.MAGIC_MISSILE
