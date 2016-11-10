from math import fabs

from model.ActionType import ActionType
from model.Game import Game
from model.Move import Move
from model.Wizard import Wizard
from model.World import World
from model.Faction import Faction
from model.LivingUnit import LivingUnit


class MyStrategy:
    LOGS_ENABLE = True
    INITIATED = False
    WAY_POINTS = list()
    NEXT_WAYPOINT = 1
    PREV_WAYPOINT = 0
    LOW_HP_FACTOR = 0.4
    STAFF_SECTOR = None
    FRIENDLY_FACTION = None
    PASS_TICK_COUNT = 10
    WARNING_DISTANCE_FACTOR = 1.2
    # максимальное количество врагов в ближней зоне
    # если больше - нужно сваливать
    MAX_ENEMIES_IN_STAFF_ZONE = 1
    W = None

    def _init(self, game: Game, me: Wizard, world: World):
        self.W = world
        self.G = game
        if not self.INITIATED:
            def compute_waypoints(home_x, home_y, map_size):
                wps = list()
                wps.append((home_x, home_y))  # add home base
                wps.append((map_size / 2, map_size / 2))  # center
                wps.append((map_size - home_x, map_size - home_y))  # add enemy base
                return wps

            self.PROBLEM_ANGLE = 1.6
            self.STAFF_SECTOR = self.G.staff_sector
            self.MAX_SPEED = self.G.wizard_forward_speed
            self.FRIENDLY_FACTION = me.faction
            self.WAY_POINTS = compute_waypoints(me.x, me.y, map_size=self.G.map_size)
            self.INITIATED = True
            self.log('init process way points %s' % self.WAY_POINTS)
        else:
            self.log('TICK %s' % world.tick_index)

    def move(self, me: Wizard, world: World, game: Game, move: Move):
        self._init(game, me, world)

        # initial cooldown
        if self.PASS_TICK_COUNT:
            self.PASS_TICK_COUNT -= 1
            self.log('initial cooldown pass turn')
            return

        # если ХП мало - стоим или отступаем
        if self._need_retreat(me):
            self.log('retreat case')
            if self._enemies_in_warning_distance_count(me):
                self.log('retreat to home by low HP and enemies in attack range')
                self._goto(self._get_prev_waypoint(me), move, me)
            return

        # есть враги в радиусе обстрела
        range_enemies, staff_enemies = self._get_enemies_for_attack(me)
        if range_enemies or staff_enemies:
            self.log('found range %d enemies and %d for staff attack' % (len(range_enemies), len(staff_enemies)))

            attack_enemy, can_attack = self._select_enemy_for_attack(me, staff_enemies, range_enemies)
            if not attack_enemy:
                self.log('cooldown for attack - hold on place')
                return

            angle_to_enemy = me.get_angle_to_unit(attack_enemy)
            if can_attack:
                self.log('select enemy for attack %s' % attack_enemy.id)
                move.cast_angle = angle_to_enemy
                if self._enemy_in_range_attack_distance(me, game, attack_enemy):
                    self.log('cast attack')
                    move.action = ActionType.MAGIC_MISSILE
                    move.min_cast_distance = me.get_distance_to_unit(
                        attack_enemy) - attack_enemy.radius + self.G.magic_missile_radius
                else:
                    self.log('staff attack')
                    move.action = ActionType.STAFF
            else:
                self.log('select enemy for turn %s' % attack_enemy.id)
                move.turn = angle_to_enemy
        else:
            self.log('move to next waypoint')
            self._goto(self._get_next_waypoint(me), move, me)

    def _get_prev_waypoint(self, me: Wizard):
        wp = self.WAY_POINTS[self.PREV_WAYPOINT]
        if me.get_distance_to(*wp) < me.radius * 2:
            try:
                prev_wp = self.WAY_POINTS[self.PREV_WAYPOINT - 1]
                self.NEXT_WAYPOINT -= 1
                self.PREV_WAYPOINT -= 1
                wp = prev_wp
            except IndexError:
                pass
        return wp

    def _get_next_waypoint(self, me: Wizard):
        wp = self.WAY_POINTS[self.NEXT_WAYPOINT]
        if me.get_distance_to(*wp) < me.radius * 2:
            try:
                next_wp = self.WAY_POINTS[self.NEXT_WAYPOINT + 1]
                self.NEXT_WAYPOINT += 1
                self.PREV_WAYPOINT += 1
                wp = next_wp
            except IndexError:
                pass
        return wp

    def _find_problem_units(self, me: Wizard):
        units = self.W.buildings + self.W.wizards + self.W.minions + self.W.trees
        connected_u = [t for t in units if me.get_distance_to_unit(t) <= (me.radius + t.radius) * 1.05 and me.id != t.id]
        problem_u = [t for t in connected_u if fabs(me.get_angle_to_unit(t)) < self.PROBLEM_ANGLE]
        return None if not problem_u else problem_u[0]

    def _goto(self, coords_tuple, move: Move, me: Wizard):
        problem_unit = self._find_problem_units(me)
        if problem_unit:
            angle_to_connected_unit = me.get_angle_to_unit(problem_unit)
            self.log('found connected unit %s (%.4f angle)' % (problem_unit, angle_to_connected_unit))
            if angle_to_connected_unit > 0:
                self.log('run left')
                move.strafe_speed = -1 * self.G.wizard_strafe_speed
            else:
                self.log('run right')
                move.strafe_speed = self.G.wizard_strafe_speed
        else:
            angle = me.get_angle_to(*coords_tuple)
            move.turn = angle
            if fabs(angle) < self.STAFF_SECTOR / 4.0:
                move.speed = self.MAX_SPEED

    def _get_enemies_for_attack(self, me: Wizard):
        enemy_targets = self._get_enemies()
        cast_attack = [t for t in enemy_targets if self._enemy_in_range_attack_distance(me, self.G, t)]
        staff_attack = [t for t in enemy_targets if self._can_staff_attack_enemy(me, self.G, t)]
        return cast_attack, staff_attack

    @staticmethod
    def _enemy_in_range_attack_distance(me: Wizard, game: Game, e: LivingUnit):
        distance = me.get_distance_to_unit(e)
        return (game.staff_range + e.radius) < distance <= me.cast_range

    @staticmethod
    def _can_staff_attack_enemy(me: Wizard, game: Game, e):
        distance = me.get_distance_to_unit(e)
        return distance <= (game.staff_range + e.radius)

    @staticmethod
    def _can_range_attack(me: Wizard, game: Game):
        return not me.remaining_cooldown_ticks_by_action[ActionType.MAGIC_MISSILE] and \
               game.magic_missile_manacost <= me.mana

    def _check_enemy_in_attack_sector(self, me: Wizard, e):
        return fabs(me.get_angle_to_unit(e)) < self.STAFF_SECTOR / 2.0

    def _select_enemy_for_attack(self, me: Wizard, staff_enemies: list, range_enemies: list):
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
        all_enemies = (staff_enemies + range_enemies) if self._can_range_attack(me, self.G) else staff_enemies

        if not all_enemies:
            return None, False

        # find can attacked targets
        enemies_in_attack_sector = _filter_into_attack_sector(all_enemies)
        if enemies_in_attack_sector:
            e = _sort_by_hp(enemies_in_attack_sector)[0]
            self.log('select enemy in attack sector %s' % e.id)
            return e, True

        e = _sort_by_angle(all_enemies)[0]
        self.log('select enemy for turn %s' % e.id)
        return e, False

    def _need_retreat(self, me: Wizard):
        enemies_in_staff_zone = self._enemies_in_staff_distance(me)
        return me.life < me.max_life * self.LOW_HP_FACTOR or len(enemies_in_staff_zone) > self.MAX_ENEMIES_IN_STAFF_ZONE

    def _get_enemies(self):
        all_targets = self.W.buildings + self.W.wizards + self.W.minions
        enemy_targets = [t for t in all_targets if t.faction not in [self.FRIENDLY_FACTION, Faction.NEUTRAL]]
        return enemy_targets

    def _enemies_in_warning_distance_count(self, me: Wizard):
        enemies = self._get_enemies()
        danger_enemies = [e for e in enemies
                          if me.get_distance_to_unit(e) <= me.cast_range * self.WARNING_DISTANCE_FACTOR]
        self.log('found %d enemies in warning zone' % len(danger_enemies))
        return len(danger_enemies) > 0

    def _enemies_in_staff_distance(self, me: Wizard):
        enemies = self._get_enemies()
        danger_enemies = [e for e in enemies
                          if me.get_distance_to_unit(e) <= (self.G.staff_range + e.radius)]
        self.log('found %d enemies in staff zone' % len(danger_enemies))
        return danger_enemies

    def log(self, message):
        if self.LOGS_ENABLE:
            print(message)