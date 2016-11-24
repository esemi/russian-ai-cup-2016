from math import fabs, radians
from copy import copy
import random

from model.ActionType import ActionType
from model.LivingUnit import LivingUnit
from model.Game import Game
from model.MinionType import MinionType
from model.Move import Move
from model.Wizard import Wizard
from model.Minion import Minion
from model.World import World
from model.Faction import Faction
from model.Building import Building
from model.BuildingType import BuildingType
from model.Message import Message
from model.LaneType import LaneType


class MyStrategy:
    # shortcuts
    W = None
    G = None
    STAFF_SECTOR = None
    FRIENDLY_FACTION = None

    LOGS_ENABLE = True
    INITIATED = False

    # waypoints functionality
    WAY_POINTS = {}
    CURRENT_LINE = None
    NEXT_WAYPOINT = 1
    PREV_WAYPOINT = 0

    # move constants
    MOVE_TURN = None
    MOVE_STRAFE_SPEED = None
    MOVE_SPEED = None

    # enemy base offset for last way point on all lines
    ENEMY_BASE_OFFSET = 660
    # offset of home base for first way point on all line
    FRIENDLY_BASE_OFFSET = 100
    # offset of map angle
    MAP_ANGLE_OFFSET = 600

    # angle sector of connected units is problem for go
    PROBLEM_ANGLE = radians(95)

    # количество тиков, которое мы пропускаем в начале боя
    PASS_TICK_COUNT = 5

    # если здоровья меньше данного количества - задумываемся об отступлении
    LOW_HP_FACTOR = 0.35

    # максимальное количество врагов в ближней зоне, если больше - нужно сваливать
    MAX_ENEMIES_IN_DANGER_ZONE = 1

    # pseudo enemy base unit. Use for angle to it when way line ended
    ENEMY_BASE = None

    # projectile care
    PROJECTILE_SAFE_RANGE_FACTOR = 0.95
    PROJECTILE_MAP = {}
    PROJECTILE_LAST_ENEMY = None

    def _init(self, game: Game, me: Wizard, world: World, move: Move):
        self.W = world
        self.G = game
        if not self.INITIATED:
            self.STAFF_SECTOR = self.G.staff_sector
            self.MAX_SPEED = self.G.wizard_forward_speed * 2
            self.FRIENDLY_FACTION = me.faction
            self._compute_waypoints(me)
            self._send_messages(me, move)
            self.INITIATED = True
            self.log('init process')

    def _send_messages(self, me: Wizard, move: Move):
        if me.master:
            teammates = [w for w in self.W.wizards
                         if w.faction == self.FRIENDLY_FACTION and not w.me]
            self.log('found %d teammates' % len(teammates))
            if teammates:
                direction = [Message(LaneType.MIDDLE, None, None), Message(LaneType.TOP, None, None),
                             Message(LaneType.BOTTOM, None, None)]
                index = 0
                msgs = []
                for i in range(0, len(teammates)):
                    msgs.append(direction[index])
                    index += 1
                    if index >= len(direction):
                        index = 0
                self.log('send %d msgs' % len(msgs))
                move.messages = msgs

    def _compute_waypoints(self, me: Wizard):
        map_size = self.G.map_size
        friendly_base = [b for b in self.W.buildings
                         if b.faction == self.FRIENDLY_FACTION and b.type == BuildingType.FACTION_BASE][0]
        init_point = (me.x, me.y)

        # top line
        wps = list()
        wps.append(init_point)
        wps.append((200, 2700))
        wps.append((200, 1700))
        wps.append((200, 800))
        wps.append((450, 450))
        wps.append((800, 180))
        wps.append((1700, 180))
        wps.append((2800, 150))
        self.log('compute top waypoints %s' % wps)
        self.WAY_POINTS[LaneType.TOP] = wps

        # bottom line
        wps = list()
        wps.append(init_point)
        wps.append((1200, 3800))
        wps.append((2300, 3800))
        wps.append((3200, 3800))
        wps.append((3550, 3550))
        wps.append((3800, 3200))
        wps.append((3800, 2300))
        wps.append((3750, 1200))
        self.log('compute bottom waypoints %s' % wps)
        self.WAY_POINTS[LaneType.BOTTOM] = wps

        # middle line
        wps = list()
        wps.append(init_point)
        wps.append((1050, 2850))
        wps.append((1800, 2120))
        wps.append((2940.0, 1060.0))
        self.log('compute middle waypoints %s' % wps)
        self.WAY_POINTS[LaneType.MIDDLE] = wps

        self.ENEMY_BASE = copy(friendly_base)
        self.ENEMY_BASE.x = map_size - self.ENEMY_BASE.x
        self.ENEMY_BASE.y = map_size - self.ENEMY_BASE.y

    def move(self, me: Wizard, world: World, game: Game, move: Move):
        self.log('TICK %s' % world.tick_index)
        self.log('me %s %s' % (me.x, me.y))
        self._init(game, me, world, move)

        # initial cooldown
        if self.PASS_TICK_COUNT:
            self.PASS_TICK_COUNT -= 1
            self.log('initial cooldown pass turn')
            return

        # select line rush for this battle
        if self.CURRENT_LINE is None:
            self.CURRENT_LINE = random.choice(list(self.WAY_POINTS.keys()))
            self.log('select %s line' % self.CURRENT_LINE)
            if me.messages:
                m = me.messages.pop()
                if m in list(self.WAY_POINTS.keys()):
                    self.CURRENT_LINE = m
                    self.log('select %s line by message' % self.CURRENT_LINE)

        # if die crutch
        # если находимся в досягаемости нашей первой точкт (инит поинт)
        # то нужно принудительно скипнуть индексе вейпоинтов
        if self._near_begin_waypoint(me):
            self.log('skip waypoint indexes')
            self.NEXT_WAYPOINT = 1
            self.PREV_WAYPOINT = 0

        # STRATEGY LOGIC
        enemy_targets = self._enemies_in_attack_distance(me)
        enemy_who_can_attack_me = self._enemies_who_can_attack_me(me)
        retreat_move_lock = False
        retreat_by_low_hp = False

        # чистим уже погибшие снаряды из карты
        current_projectiles_id = set([p.id for p in self.W.projectiles if p.owner_unit_id == me.id])
        cached_projectiles_id = set(self.PROJECTILE_MAP.keys())
        for k in cached_projectiles_id - current_projectiles_id:
            del self.PROJECTILE_MAP[k]

        # ищем последний созданный снаряд и его цель для карты снарядов
        if self.PROJECTILE_LAST_ENEMY:
            for p in self.W.projectiles:
                if p.owner_unit_id == me.id and p.id not in self.PROJECTILE_MAP:
                    self.PROJECTILE_MAP[p.id] = self.PROJECTILE_LAST_ENEMY
                    self.PROJECTILE_LAST_ENEMY = None
                    break
        self.log('projectile map %s' % str(self.PROJECTILE_MAP))

        # если ХП мало отступаем
        if me.life < me.max_life * self.LOW_HP_FACTOR:
            retreat_by_low_hp = True
            self.log('retreat by low HP')
            if len(enemy_who_can_attack_me):
                self._goto_backward(me)
                retreat_move_lock = True

        if len(enemy_who_can_attack_me) > self.MAX_ENEMIES_IN_DANGER_ZONE:
            self.log('retreat by enemies in danger zone')
            self._goto_backward(me)
            retreat_move_lock = True

        # если врагов в радиусе обстрела нет - идём к их базе если не находимся в режиме отступления
        if not enemy_targets and not retreat_by_low_hp:
            self.log('move to next waypoint')
            self._goto_forward(me)

        # если на поле есть наши снаряды и расстояние до цели меньше расстояния каста
        # пробуем подойти к цели (если не находимся в отступлении)
        if not retreat_by_low_hp:
            potential_miss_enemies = self._find_potential_miss_enemy(me)
            self.log('found %s potential miss enemies' % potential_miss_enemies)
            if potential_miss_enemies:
                e = self._sort_by_angle(me, potential_miss_enemies)[0]
                self._goto_enemy(me, e)

        if enemy_targets:
            # есть враги в радиусе обстрела
            self.log('found %d enemies for attack' % len(enemy_targets))
            selected_enemy = self._select_enemy_for_attack(me, enemy_targets)
            angle_to_enemy = me.get_angle_to_unit(selected_enemy)

            # если цель не в секторе атаки - поворачиваемся к ней (приоритет за направлением на точку отступления)
            if not self._enemy_in_attack_sector(me, selected_enemy):
                if not retreat_move_lock:
                    self.log('select enemy for turn %s' % selected_enemy.id)
                    self.MOVE_TURN = angle_to_enemy
                else:
                    self.log('ignore select enemy for turn %s by retreat' % selected_enemy.id)
            else:
                # если можем атаковать - атакуем
                self.log('select enemy for attack %s' % selected_enemy.id)
                move.cast_angle = angle_to_enemy
                if self._enemy_in_cast_distance(me, selected_enemy):
                    self.log('cast attack')
                    move.action = ActionType.MAGIC_MISSILE
                    move.min_cast_distance = self._cast_distance(me, selected_enemy)
                    self.PROJECTILE_LAST_ENEMY = selected_enemy.id
                    
                else:
                    self.log('staff attack')
                    move.action = ActionType.STAFF

        if self.MOVE_TURN is not None:
            move.turn = self.MOVE_TURN
            self.MOVE_TURN = None
        if self.MOVE_SPEED is not None:
            move.speed = self.MOVE_SPEED
            self.MOVE_SPEED = None
        if self.MOVE_STRAFE_SPEED is not None:
            move.strafe_speed = self.MOVE_STRAFE_SPEED
            self.MOVE_STRAFE_SPEED = None

    def _get_prev_waypoint(self, me: Wizard):
        wp = self.WAY_POINTS[self.CURRENT_LINE][self.PREV_WAYPOINT]
        if self._near_waypoint(me, wp):
            try:
                prev_wp = self.WAY_POINTS[self.CURRENT_LINE][self.PREV_WAYPOINT - 1]
                self.NEXT_WAYPOINT -= 1
                self.PREV_WAYPOINT -= 1
                wp = prev_wp
            except IndexError:
                pass
        return wp

    @staticmethod
    def _near_waypoint(me: Wizard, wp_coords):
        return me.get_distance_to(*wp_coords) < me.radius * 2

    def _near_begin_waypoint(self, me: Wizard):
        return self._near_waypoint(me, self.WAY_POINTS[self.CURRENT_LINE][0])

    def _get_next_waypoint(self, me: Wizard):
        wp = self.WAY_POINTS[self.CURRENT_LINE][self.NEXT_WAYPOINT]
        if self._near_waypoint(me, wp):
            try:
                next_wp = self.WAY_POINTS[self.CURRENT_LINE][self.NEXT_WAYPOINT + 1]
                self.NEXT_WAYPOINT += 1
                self.PREV_WAYPOINT += 1
                wp = next_wp
            except IndexError:
                return None
        return wp

    def _find_problem_units(self, me: Wizard, reverse=False):

        def is_problem_unit(angle, reverse, problem_sector):
            if reverse:
                return fabs(angle) > radians(180) - problem_sector
            else:
                return fabs(angle) < problem_sector

        units = self.W.buildings + self.W.wizards + self.W.minions + self.W.trees
        connected_u = [t for t in units if
                       me.get_distance_to_unit(t) <= (me.radius + t.radius) * 1.05 and me.id != t.id]
        problem_u = [t for t in connected_u if is_problem_unit(me.get_angle_to_unit(t), reverse, self.PROBLEM_ANGLE)]
        return None if not problem_u else problem_u[0]

    def _goto_forward(self, me: Wizard):
        coords_tuple = self._get_next_waypoint(me)
        problem_unit = self._find_problem_units(me)
        if problem_unit:
            angle_to_connected_unit = me.get_angle_to_unit(problem_unit)
            self.log('found connected unit %s (%.4f angle)' % (problem_unit.id, angle_to_connected_unit))
            if angle_to_connected_unit >= 0:
                self.log('run left')
                self.MOVE_STRAFE_SPEED = -1 * self.G.wizard_strafe_speed
            else:
                self.log('run right')
                self.MOVE_STRAFE_SPEED = self.G.wizard_strafe_speed
        else:
            turn_only = False
            if coords_tuple is None:
                turn_only = True
                coords_tuple = (self.ENEMY_BASE.x, self.ENEMY_BASE.y)
            angle = me.get_angle_to(*coords_tuple)
            self.MOVE_TURN = angle

            if fabs(angle) < self.STAFF_SECTOR / 4.0 and not turn_only:
                self.MOVE_SPEED = self.MAX_SPEED

    def _goto_enemy(self, me: Wizard, e: LivingUnit):
        angle = me.get_angle_to_unit(e)
        self.log('enemy angle for projectile care is %.2f' % angle)
        if fabs(angle) < self.STAFF_SECTOR / 4.0:
            self.MOVE_TURN = angle
            self.MOVE_SPEED = self.MAX_SPEED

    def _goto_backward(self, me: Wizard):
        coords_tuple = self._get_prev_waypoint(me)
        problem_unit = self._find_problem_units(me, True)
        if problem_unit:
            angle_to_connected_unit = me.get_angle_to_unit(problem_unit)
            self.log('backward angle %.4f' % angle_to_connected_unit)
            self.log('found connected unit %s (%.4f angle)' % (problem_unit.id, angle_to_connected_unit))
            if angle_to_connected_unit > 0:
                self.log('run right')
                self.MOVE_STRAFE_SPEED = -1 * self.G.wizard_strafe_speed
            else:
                self.log('run left')
                self.MOVE_STRAFE_SPEED = self.G.wizard_strafe_speed
        else:
            angle = me.get_angle_to(*coords_tuple)
            angle_reverse = radians(180) - fabs(angle)
            if angle > 0:
                angle_reverse *= -1
            self.log('backward angle %.4f %.4f' % (angle, angle_reverse))
            self.log('backward angle staff %.4f' % self.STAFF_SECTOR)
            self.MOVE_TURN = angle_reverse
            if fabs(angle_reverse) < self.STAFF_SECTOR / 4.0:
                self.MOVE_SPEED = -1 * self.MAX_SPEED

    @staticmethod
    def _sort_by_angle(me: Wizard, el: list):
        return sorted(el, key=lambda u: fabs(me.get_angle_to_unit(u)))

    def _select_enemy_for_attack(self, me: Wizard, enemy_targets: list):
        def _filter_into_attack_sector(el: list):
            return [e for e in el if self._enemy_in_attack_sector(me, e)]

        def _sort_by_hp(el: list):
            return sorted(el, key=lambda u: u.life)

        def _sort_by_distance(el: list):
            return sorted(el, key=lambda u: me.get_distance_to_unit(u))

        def _filter_can_attack_now(el: list):
            result = []
            if not me.remaining_action_cooldown_ticks:
                for e in el:
                    if self._enemy_in_cast_distance(me, e) and self.G.magic_missile_manacost <= me.mana and \
                            not me.remaining_cooldown_ticks_by_action[ActionType.MAGIC_MISSILE]:
                        result.append(e)
                    elif self._enemy_in_staff_distance(me, e) and \
                            not me.remaining_cooldown_ticks_by_action[ActionType.STAFF]:
                        result.append(e)
            return result

        def _select(enemies, type, distance_force=True):
            self.log('found %s enemies %d' % (type, len(enemies)))
            enemies_in_sector = _filter_into_attack_sector(enemies)
            if enemies_in_sector:  # выбираем того, кого мы сможем ударить прямо сейчас
                self.log('found enemies in attack sector %d' % len(enemies_in_sector))
                enemies_can_attack_now = _filter_can_attack_now(enemies_in_sector)
                if enemies_can_attack_now:
                    e = _sort_by_hp(enemies_can_attack_now)[0]
                    self.log('select enemy for attack now by HP %s' % e.id)
                elif distance_force:
                    e = _sort_by_distance(enemies_in_sector)[0]
                    self.log('select nearest enemy for delayed attack (turn now) %s' % e.id)
                else:
                    e = self._sort_by_angle(me, enemies_in_sector)[0]
                    self.log('select enemy for delayed attack by angle (turn now) %s' % e.id)
            else:  # если таких нет - ищем самого слабого
                self.log('all enemies not in attack sector')
                e = _sort_by_hp(enemies)[0]
                self.log('select enemy for turn %s' % e.id)
            return e

        buildings = [e for e in enemy_targets if isinstance(e, Building)]
        wizards = [e for e in enemy_targets if isinstance(e, Wizard)]
        minions = [e for e in enemy_targets if isinstance(e, Minion)]

        if wizards:
            e = _select(wizards, 'wizards', False)
            self.log('select wizard for attack %s' % e.id)
        elif minions:
            e = _select(minions, 'minions', True)
            self.log('select minion for attack %s' % e.id)
        else:
            e = _select(buildings, 'buildings', False)
            self.log('select building for attack %s' % e.id)
        return e

    def _get_enemies(self):
        all_targets = self.W.buildings + self.W.wizards + self.W.minions
        enemy_targets = [t for t in all_targets if t.faction not in [self.FRIENDLY_FACTION, Faction.NEUTRAL]]
        return enemy_targets

    def _enemies_in_attack_distance(self, me: Wizard):
        enemies = self._get_enemies()
        danger_enemies = [e for e in enemies
                          if self._enemy_in_staff_distance(me, e) or self._enemy_in_cast_distance(me, e)]
        self.log('found %d enemies in cast zone' % len(danger_enemies))
        return danger_enemies

    def _enemies_who_can_attack_me(self, me: Wizard):
        danger_enemies = []
        for e in self._get_enemies():
            distance_to_me = e.get_distance_to_unit(me) - me.radius
            attack_range = 0
            if isinstance(e, Building):
                attack_range = e.attack_range * 1.1
            elif isinstance(e, Wizard):
                attack_range = e.cast_range
                distance_to_me = self._cast_distance(e, me)
            elif isinstance(e, Minion) and e.type == MinionType.FETISH_BLOWDART:
                attack_range = self.G.fetish_blowdart_attack_range
            elif isinstance(e, Minion) and e.type == MinionType.ORC_WOODCUTTER:
                attack_range = self.G.orc_woodcutter_attack_range * 2.5

            if distance_to_me <= attack_range:
                danger_enemies.append(e)
        self.log('found %d enemies who can attack me' % len(danger_enemies))
        return danger_enemies

    def _enemy_in_staff_distance(self, me: Wizard, e):
        return me.get_distance_to_unit(e) <= (self.G.staff_range + e.radius)

    def _enemy_in_cast_distance(self, me: Wizard, e: LivingUnit):
        return self._cast_distance(me, e) < me.cast_range and not self._enemy_in_staff_distance(me, e)

    def _cast_distance(self, me: Wizard, e: LivingUnit):
        projectile_radius = self.G.magic_missile_radius
        return me.get_distance_to_unit(e) - e.radius - projectile_radius

    def _enemy_in_attack_sector(self, me: Wizard, e):
        return fabs(me.get_angle_to_unit(e)) <= self.STAFF_SECTOR / 2.0

    def log(self, message):
        if self.LOGS_ENABLE:
            print(message)

    def _find_potential_miss_enemy(self, me: Wizard):
        all_enemies = self._get_enemies()
        target_enemies = [e for e in all_enemies if e.id in self.PROJECTILE_MAP.items()]
        return [e for e in target_enemies
                if self._cast_distance(me, e) > me.cast_range * self.PROJECTILE_SAFE_RANGE_FACTOR]
