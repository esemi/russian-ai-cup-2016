from random import choice
from math import fabs

from model.ActionType import ActionType
from model.Game import Game
from model.Move import Move
from model.Wizard import Wizard
from model.World import World
from model.Faction import Faction


class MyStrategy:

    LOW_HP_FACTOR = 0.4
    INITIATED = False
    CENTER_POINT = None
    HOME_POINT = None
    STAFF_SECTOR = None
    FRIENDLY_FACTION = None
    PASS_TICK_COUNT = 50

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
            self.FRIENDLY_FACTION = me.faction
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

    def _get_enemies_for_attack(self, world: World, me: Wizard, game: Game):
        all_targets = world.buildings + world.wizards + world.minions
        enemy_targets = [t for t in all_targets if t.faction not in [self.FRIENDLY_FACTION, Faction.NEUTRAL]]
        attack_enemies = [t for t in enemy_targets if me.get_distance_to_unit(t) <= me.cast_range]
        cast_attack = [t for t in attack_enemies if self._check_enemy_for_range_attack(me, game, t)]
        staff_attack = [t for t in attack_enemies if not self._check_enemy_for_range_attack(me, game, t)]
        return cast_attack, staff_attack

    @staticmethod
    def _check_enemy_for_range_attack(me: Wizard, game: Game, e):
        return me.get_distance_to_unit(e) > game.staff_range

    @staticmethod
    def _check_allow_range_attack(me: Wizard, game: Game):
        current_mana = me.mana
        # todo add fireball
        # if not me.remaining_cooldown_ticks_by_action[ActionType.FIREBALL] and game.fireball_manacost <= current_mana:
        #     return True
        if not me.remaining_cooldown_ticks_by_action[ActionType.FROST_BOLT] and game.frost_bolt_manacost <= current_mana:
            return True
        if not me.remaining_cooldown_ticks_by_action[ActionType.MAGIC_MISSILE] and game.magic_missile_manacost <= current_mana:
            return True

        return False

    def _check_enemy_in_attack_sector(self, me: Wizard, e):
        return fabs(me.get_angle_to_unit(e)) < self.STAFF_SECTOR / 2.0

    def _select_enemy_for_attack(self, me: Wizard, game: Game, staff_enemies: list, range_enemies: list):
        def _filter_into_attack_sector(el: list):
            return [e for e in el if self._check_enemy_in_attack_sector(me, e)]

        def _sort_by_hp(el: list):
            return sorted(el, key=lambda u: u.life)

        def _sort_by_angle(el: list):
            return sorted(el, key=lambda u: fabs(me.get_angle_to_unit(u)))

        # если есть враги в радиусе ближней атаки
        staff_in_attack_sector = _filter_into_attack_sector(staff_enemies)
        if staff_in_attack_sector:
            e = _sort_by_hp(staff_in_attack_sector)[0]
            self.log('select enemy for staff attack %s' % e.id)
            return e, True

        # если у нас есть возможность кастовать - то ищем цель и среди удалённых
        all_enemies = (staff_enemies + range_enemies) if self._check_allow_range_attack(me, game) else staff_enemies

        # find can attacked targets
        enemies_in_attack_sector = _filter_into_attack_sector(all_enemies)
        if enemies_in_attack_sector:
            # todo find low HP targets
            # todo find nearest targets
            # todo find primary targets
            e = _sort_by_hp(enemies_in_attack_sector)[0]
            self.log('select enemy in attack sector %s' % e.id)
            return e, True

        e = _sort_by_angle(all_enemies)[0]
        self.log('select enemy for turn %s' % e.id)
        return e, False

    def move(self, me: Wizard, world: World, game: Game, move: Move):
        self._init(game, me)

        # todo руководство другими волшебниками

        # todo usage bonuses

        # initial cooldown
        if self.PASS_TICK_COUNT:
            self.PASS_TICK_COUNT -= 1
            self.log('initial cooldown pass turn')
            return

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

        # есть враги в радиусе обстрела
        range_enemies, staff_enemies = self._get_enemies_for_attack(world, me, game)
        if range_enemies or staff_enemies:
            self.log('found range %d enemies and %d for staff attack' % (len(range_enemies), len(staff_enemies)))

            attack_enemy, can_attack = self._select_enemy_for_attack(me, game, staff_enemies, range_enemies)

            # todo если врагов больно много - отступаем по маленьку
            # todo если стрелять пока нечем - отступаем по маленьку
            # todo если враги в секторе ближней атаки - отступаем по маленьку

            angle_to_enemy = me.get_angle_to_unit(attack_enemy)
            if can_attack:
                self.log('select enemy for attack %s' % attack_enemy.id)
                move.cast_angle = angle_to_enemy
                if self._check_enemy_for_range_attack(me, game, attack_enemy):
                    self.log('cast attack')
                    # todo another attack cast
                    move.action = ActionType.MAGIC_MISSILE
                    move.min_cast_distance = me.get_distance_to_unit(attack_enemy) - attack_enemy.radius + game.magic_missile_radius
                else:
                    self.log('staff attack')
                    move.action = ActionType.STAFF
            else:
                self.log('select enemy for turn %s' % attack_enemy.id)
                move.turn = angle_to_enemy
        else:
            self.log('move to next waypoint')
            self._move_to_next_waypoint(move, game, me)
