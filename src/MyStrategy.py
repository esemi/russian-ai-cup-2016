from random import choice
from math import fabs

from src.model.ActionType import ActionType
from src.model.Game import Game
from src.model.Move import Move
from src.model.Wizard import Wizard
from src.model.World import World


class MyStrategy:

    LOW_HP_FACTOR = 0.4
    INITIATED = False
    CENTER_POINT = None
    HOME_POINT = None
    STAFF_SECTOR = None

    @staticmethod
    def log(message):
        print(message)

    def _init(self, game: Game, me: Wizard):
        if not self.INITIATED:
            self.log('init process run')
            map_size = game.map_size
            self.HOME_POINT = (me.x, me.y)
            self.CENTER_POINT = (map_size / 2, map_size / 2)
            self.STAFF_SECTOR = game.staff_sector
            self.MAX_SPEED = game.wizard_forward_speed
            self.INITIATED = True

    def _get_next_waypoint(self, me: Wizard):
        # todo release waypoints двигаемся к бонусу, башне или скоплению наших мобов
        wp = self.CENTER_POINT
        if me.get_distance_to(*wp) < me.radius:
            return None
        return wp

    def _goto(self, coords_tuple, move: Move, me: Wizard):
        angle = me.get_angle_to(*coords_tuple)
        move.turn = angle
        if fabs(angle) < self.STAFF_SECTOR / 4.0:
            move.speed = self.MAX_SPEED

    def _retreat_to_home(self, move: Move, game: Game, me: Wizard):
        # todo умное отступление с удержанием врагом в секторе обстрела
        # рандомно прыгаем влево-вправо по направлению движения
        move.strafe_speed = game.wizard_strafe_speed if choice([True, False]) else -1 * game.wizard_strafe_speed
        # рвём когти к дому
        self._goto(self.HOME_POINT, move, me)

    def _move_to_next_waypoint(self, move: Move, game: Game, me: Wizard):
        # рандомно прыгаем влево-вправо по направлению движения
        move.strafe_speed = game.wizard_strafe_speed if choice([True, False]) else -1 * game.wizard_strafe_speed
        # рвём когти к следующей точке
        wp = self._get_next_waypoint(me)
        if wp:
            self._goto(wp, move, me)

    def move(self, me: Wizard, world: World, game: Game, move: Move):
        self._init(game, me)

        # todo руководство другими волшебниками

        # action cooldown
        if me.remaining_action_cooldown_ticks > 0:
            self.log('cooldown pass turn')
            move.action = ActionType.NONE
            return

        # если ХП мало и мы находимся в секторе атаки врагов - отступаем
        if me.life < me.max_life * self.LOW_HP_FACTOR:
            self.log('retreat to home by low HP')
            self._retreat_to_home(move, game, me)
            return


        # todo есть враги в секторе атаки
            # todo выбираем цель
            # todo если можно атаковать
                # todo атакуем брик
            # todo иначе
                # todo отступаем брик

        # todo иначе
        self._move_to_next_waypoint(move, game, me)
