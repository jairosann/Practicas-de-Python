"""Texto interactivo RPG minimalista.

Uso básico:
    python rpg.py            # inicia el juego
    python rpg.py --help     # opciones CLI, incluyendo --test para pruebas automatizadas
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from pathlib import Path
from textwrap import dedent
from typing import Dict, Iterable, List, Optional, Tuple


class ClassType(Enum):
    WARRIOR = "Guerrero"
    MAGE = "Mago"
    ROGUE = "Pícaro"


class ActionType(Enum):
    ATTACK = auto()
    SKILL = auto()
    ITEM = auto()
    DEFEND = auto()
    FLEE = auto()


class StatusType(Enum):
    POISON = auto()
    BURN = auto()
    STUN = auto()
    REGEN = auto()


class TileType(Enum):
    TOWN = "Town"
    FOREST = "Forest"
    CAVE = "Cave"
    RUINS = "Ruins"
    LAKE = "Lake"


class State(Enum):
    MAIN_MENU = auto()
    EXPLORATION = auto()
    COMBAT = auto()
    SHOP = auto()
    INVENTORY = auto()
    CHARACTER = auto()
    QUESTS = auto()
    SAVELOAD = auto()
    GAME_OVER = auto()


@dataclass
class Stats:
    lvl: int
    exp: int
    hp: int
    hp_max: int
    mp: int
    mp_max: int
    str: int
    int_: int
    agi: int
    def_: int
    gold: int

    def copy(self) -> "Stats":
        return Stats(**asdict(self))

    def exp_to_next(self) -> int:
        return int((100 * self.lvl) * 1.35)

    def gain_exp(self, amount: int) -> List[int]:
        self.exp += amount
        leveled: List[int] = []
        while self.exp >= self.exp_to_next():
            self.exp -= self.exp_to_next()
            self.lvl += 1
            leveled.append(self.lvl)
            self._increase_stats_on_level()
        return leveled

    def _increase_stats_on_level(self) -> None:
        self.hp_max += 10 + self.lvl
        self.mp_max += 5
        self.str += 2
        self.int_ += 2
        self.agi += 1
        self.def_ += 2
        self.hp = min(self.hp_max, self.hp + 10)
        self.mp = min(self.mp_max, self.mp + 5)

    def apply_delta(self, deltas: Dict[str, int]) -> None:
        for key, delta in deltas.items():
            current = getattr(self, key)
            setattr(self, key, current + delta)
        self.hp = clamp(self.hp, 0, self.hp_max)
        self.mp = clamp(self.mp, 0, self.mp_max)


@dataclass
class StatusEffect:
    status: StatusType
    potency: int
    duration: int

    def to_dict(self) -> Dict[str, int]:
        return {"status": self.status.name, "potency": self.potency, "duration": self.duration}

    @staticmethod
    def from_dict(data: Dict[str, int]) -> "StatusEffect":
        return StatusEffect(status=StatusType[data["status"]], potency=data["potency"], duration=data["duration"])


@dataclass
class Skill:
    name: str
    description: str
    mp_cost: int
    base_power: int
    scaling: str
    status: Optional[Tuple[StatusType, int, int]] = None  # status, potency, duration

    def to_dict(self) -> Dict[str, object]:
        result: Dict[str, object] = {
            "name": self.name,
            "description": self.description,
            "mp_cost": self.mp_cost,
            "base_power": self.base_power,
            "scaling": self.scaling,
        }
        if self.status:
            status, potency, duration = self.status
            result["status"] = {
                "type": status.name,
                "potency": potency,
                "duration": duration,
            }
        else:
            result["status"] = None
        return result

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "Skill":
        status_info = data.get("status")
        status_tuple: Optional[Tuple[StatusType, int, int]] = None
        if status_info:
            status_tuple = (
                StatusType[status_info["type"]],
                int(status_info["potency"]),
                int(status_info["duration"]),
            )
        return Skill(
            name=data["name"],
            description=data["description"],
            mp_cost=int(data["mp_cost"]),
            base_power=int(data["base_power"]),
            scaling=str(data["scaling"]),
            status=status_tuple,
        )


@dataclass
class Item:
    name: str
    description: str
    effect: Dict[str, int]
    price: int
    consumable: bool = True

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "effect": dict(self.effect),
            "price": self.price,
            "consumable": self.consumable,
        }

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "Item":
        return Item(
            name=data["name"],
            description=data["description"],
            effect=dict(data["effect"]),
            price=int(data["price"]),
            consumable=bool(data.get("consumable", True)),
        )


@dataclass
class Equipment:
    name: str
    description: str
    slot: str
    stat_bonuses: Dict[str, int]
    price: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "slot": self.slot,
            "stat_bonuses": dict(self.stat_bonuses),
            "price": self.price,
        }

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "Equipment":
        return Equipment(
            name=data["name"],
            description=data["description"],
            slot=data["slot"],
            stat_bonuses=dict(data["stat_bonuses"]),
            price=int(data["price"]),
        )


@dataclass
class Quest:
    name: str
    description: str
    objective_type: str
    target: str
    required: int
    reward_exp: int
    reward_gold: int
    reward_item: Optional[Item] = None
    progress: int = 0
    completed: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "objective_type": self.objective_type,
            "target": self.target,
            "required": self.required,
            "reward_exp": self.reward_exp,
            "reward_gold": self.reward_gold,
            "reward_item": self.reward_item.to_dict() if self.reward_item else None,
            "progress": self.progress,
            "completed": self.completed,
        }

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "Quest":
        reward_item_data = data.get("reward_item")
        return Quest(
            name=data["name"],
            description=data["description"],
            objective_type=data["objective_type"],
            target=data["target"],
            required=int(data["required"]),
            reward_exp=int(data["reward_exp"]),
            reward_gold=int(data["reward_gold"]),
            reward_item=Item.from_dict(reward_item_data) if reward_item_data else None,
            progress=int(data.get("progress", 0)),
            completed=bool(data.get("completed", False)),
        )


@dataclass
class Location:
    position: Tuple[int, int]
    tile_type: TileType
    discovered: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {
            "position": list(self.position),
            "tile_type": self.tile_type.name,
            "discovered": self.discovered,
        }

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "Location":
        return Location(
            position=(int(data["position"][0]), int(data["position"][1])),
            tile_type=TileType[data["tile_type"]],
            discovered=bool(data.get("discovered", False)),
        )


@dataclass
class Enemy:
    name: str
    stats: Stats
    skills: List[Skill]
    drops: List[Item]
    status_effects: List[StatusEffect] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "stats": self.stats.__dict__,
            "skills": [skill.to_dict() for skill in self.skills],
            "drops": [item.to_dict() for item in self.drops],
            "status_effects": [effect.to_dict() for effect in self.status_effects],
        }


@dataclass
class Player:
    name: str
    class_type: ClassType
    stats: Stats
    skills: List[Skill]
    inventory: List[Item] = field(default_factory=list)
    equipment: Dict[str, Equipment] = field(default_factory=dict)
    status_effects: List[StatusEffect] = field(default_factory=list)
    quests: List[Quest] = field(default_factory=list)
    position: Tuple[int, int] = (0, 0)

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "class_type": self.class_type.name,
            "stats": self.stats.__dict__,
            "skills": [skill.to_dict() for skill in self.skills],
            "inventory": [item.to_dict() for item in self.inventory],
            "equipment": {slot: eq.to_dict() for slot, eq in self.equipment.items()},
            "status_effects": [effect.to_dict() for effect in self.status_effects],
            "quests": [quest.to_dict() for quest in self.quests],
            "position": list(self.position),
        }

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "Player":
        stats_data = data["stats"]
        stats = Stats(
            lvl=int(stats_data["lvl"]),
            exp=int(stats_data["exp"]),
            hp=int(stats_data["hp"]),
            hp_max=int(stats_data["hp_max"]),
            mp=int(stats_data["mp"]),
            mp_max=int(stats_data["mp_max"]),
            str=int(stats_data["str"]),
            int_=int(stats_data["int_"] if "int_" in stats_data else stats_data["int"]),
            agi=int(stats_data["agi"]),
            def_=int(stats_data["def_"] if "def_" in stats_data else stats_data["def"]),
            gold=int(stats_data["gold"]),
        )
        equipment_data = {
            slot: Equipment.from_dict(eq_data) for slot, eq_data in data.get("equipment", {}).items()
        }
        player = Player(
            name=data["name"],
            class_type=ClassType[data["class_type"]],
            stats=stats,
            skills=[Skill.from_dict(skill) for skill in data.get("skills", [])],
            inventory=[Item.from_dict(item) for item in data.get("inventory", [])],
            equipment=equipment_data,
            status_effects=[StatusEffect.from_dict(s) for s in data.get("status_effects", [])],
            quests=[Quest.from_dict(q) for q in data.get("quests", [])],
            position=(int(data["position"][0]), int(data["position"][1])),
        )
        return player

    def max_hp(self) -> int:
        return self.stats.hp_max

    def max_mp(self) -> int:
        return self.stats.mp_max

    def apply_damage(self, amount: int) -> None:
        self.stats.hp = clamp(self.stats.hp - amount, 0, self.stats.hp_max)

    def heal(self, amount: int) -> None:
        self.stats.hp = clamp(self.stats.hp + amount, 0, self.stats.hp_max)

    def restore_mp(self, amount: int) -> None:
        self.stats.mp = clamp(self.stats.mp + amount, 0, self.stats.mp_max)

    def equip(self, equipment: Equipment) -> Optional[Equipment]:
        previous = self.equipment.get(equipment.slot)
        if previous:
            self.stats.apply_delta({key: -value for key, value in previous.stat_bonuses.items()})
        self.equipment[equipment.slot] = equipment
        self.stats.apply_delta(equipment.stat_bonuses)
        return previous

    def unequip(self, slot: str) -> Optional[Equipment]:
        equipment = self.equipment.pop(slot, None)
        if equipment:
            self.stats.apply_delta({key: -value for key, value in equipment.stat_bonuses.items()})
        return equipment


@dataclass
class GameState:
    state: State
    player: Optional[Player]
    game_map: Dict[Tuple[int, int], Location]
    discovered: List[Tuple[int, int]]

    def to_dict(self) -> Dict[str, object]:
        return {
            "state": self.state.name,
            "player": self.player.to_dict() if self.player else None,
            "game_map": {f"{x},{y}": location.to_dict() for (x, y), location in self.game_map.items()},
            "discovered": [list(pos) for pos in self.discovered],
        }

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "GameState":
        map_dict = {}
        for key, value in data.get("game_map", {}).items():
            x_str, y_str = key.split(",")
            map_dict[(int(x_str), int(y_str))] = Location.from_dict(value)
        player_data = data.get("player")
        player = Player.from_dict(player_data) if player_data else None
        return GameState(
            state=State[data["state"]],
            player=player,
            game_map=map_dict,
            discovered=[(int(pos[0]), int(pos[1])) for pos in data.get("discovered", [])],
        )


@dataclass(frozen=True)
class Config:
    save_path: Path
    map_size: int
    debug_log: bool = False


CONFIG = Config(save_path=Path("~/.rpg_saves/save.json").expanduser(), map_size=5)


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def roll_chance(rng: random.Random, chance: float) -> bool:
    return rng.random() < chance


def calc_damage(attacker: Stats, defender: Stats, skill: Optional[Skill], rng: random.Random) -> int:
    power = attacker.str
    scaling_value = attacker.str
    if skill:
        power = skill.base_power
        scaling_value = attacker.str if skill.scaling == "str" else attacker.int_
    else:
        power = max(5, attacker.str)
        scaling_value = attacker.str
    base = power + int(scaling_value * 0.6)
    variance = rng.uniform(0.85, 1.0)
    damage = int(base * variance)
    mitigation = int(defender.def_ * 0.45)
    damage = max(1, damage - mitigation)
    crit_chance = min(0.5, attacker.agi / 150)
    if roll_chance(rng, crit_chance):
        damage = int(damage * 1.5)
    block_chance = min(0.3, defender.def_ / 200)
    if roll_chance(rng, block_chance):
        damage = max(1, int(damage * 0.5))
    return damage


def apply_status(target_status: List[StatusEffect], effect: StatusEffect) -> None:
    for existing in target_status:
        if existing.status == effect.status:
            existing.duration = max(existing.duration, effect.duration)
            existing.potency = max(existing.potency, effect.potency)
            return
    target_status.append(effect)


class TerminalStyler:
    def __init__(self, use_color: bool) -> None:
        self.use_color = use_color

    def colorize(self, text: str, code: str) -> str:
        if not self.use_color:
            return text
        return f"\033[{code}m{text}\033[0m"

    def title(self, text: str) -> str:
        return self.colorize(text, "36;1")

    def success(self, text: str) -> str:
        return self.colorize(text, "32")

    def warning(self, text: str) -> str:
        return self.colorize(text, "33")

    def danger(self, text: str) -> str:
        return self.colorize(text, "31")


def safe_input(prompt: str) -> Optional[str]:
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        return None


class Game:
    def __init__(self, args: argparse.Namespace, testing: bool = False) -> None:
        self.args = args
        self.testing = testing
        self.rng = random.Random(args.seed) if args.seed is not None else random.Random()
        self.state = State.MAIN_MENU
        self.player: Optional[Player] = None
        self.game_map: Dict[Tuple[int, int], Location] = {}
        self.discovered: List[Tuple[int, int]] = []
        self._init_map()
        use_color = sys.stdout.isatty() and not getattr(args, "no_color", False)
        self.style = TerminalStyler(use_color)
        self.last_tip = ""

    def _init_map(self) -> None:
        tiles = [TileType.TOWN, TileType.FOREST, TileType.CAVE, TileType.RUINS, TileType.LAKE]
        size = CONFIG.map_size
        for y in range(size):
            for x in range(size):
                tile = tiles[(x + y) % len(tiles)]
                self.game_map[(x, y)] = Location(position=(x, y), tile_type=tile, discovered=(x, y) == (2, 2))
        self.discovered.append((2, 2))

    def run(self) -> None:
        try:
            while self.state != State.GAME_OVER:
                if self.state == State.MAIN_MENU:
                    self.handle_main_menu()
                elif self.state == State.EXPLORATION:
                    self.handle_exploration()
                elif self.state == State.COMBAT:
                    self.handle_combat()
                elif self.state == State.SHOP:
                    self.handle_shop()
                elif self.state == State.INVENTORY:
                    self.handle_inventory()
                elif self.state == State.CHARACTER:
                    self.handle_character()
                elif self.state == State.QUESTS:
                    self.handle_quests()
                elif self.state == State.SAVELOAD:
                    self.handle_saveload()
                else:
                    self.state = State.GAME_OVER
        except (EOFError, KeyboardInterrupt):
            if self.player:
                self.save_game()
            print("\nJuego guardado. ¡Hasta la próxima!")

    def handle_main_menu(self) -> None:
        print(self.style.title("=== MENÚ PRINCIPAL ==="))
        print("[1] Nueva partida\n[2] Cargar partida\n[3] Salir")
        choice = safe_input("> ")
        if choice is None or choice == "3":
            self.state = State.GAME_OVER
            return
        if choice == "1":
            self.start_new_game()
        elif choice == "2":
            if self.load_game():
                self.state = State.EXPLORATION
            else:
                print(self.style.warning("No se pudo cargar la partida."))
        else:
            print("Opción inválida")

    def start_new_game(self) -> None:
        name = safe_input("Nombre del héroe: ") or "Aventurero"
        class_choice = self.choose_class()
        self.player = self.create_player(name, class_choice)
        self.player.position = (2, 2)
        self.state = State.EXPLORATION
        self.show_tutorial()

    def choose_class(self) -> ClassType:
        classes = list(ClassType)
        for idx, class_type in enumerate(classes, 1):
            print(f"[{idx}] {class_type.value}")
        while True:
            choice = safe_input("Elige clase: ")
            if choice and choice.isdigit() and 1 <= int(choice) <= len(classes):
                return classes[int(choice) - 1]
            print("Selección inválida")

    def show_tutorial(self) -> None:
        tutorial = dedent(
            """
            ¡Bienvenido a Eteria!
            - Usa N/S/E/O para moverte por el mapa.
            - Pulsa I para abrir el inventario y equiparte.
            - Explora para encontrar enemigos, botín y misiones.
            - Visita la ciudad para curarte y comerciar.
            - Guarda con S con frecuencia para no perder progreso.
            """
        ).strip()
        print(tutorial)

    def handle_exploration(self) -> None:
        assert self.player is not None
        self.render_map()
        print("[E]xplorar [M]apa [Q]uests [I]nventario [C]arácter [T]ienda [S]alvar [X] Salir")
        choice = safe_input("> ")
        if choice is None:
            self.state = State.GAME_OVER
            self.save_game()
            return
        choice = choice.lower()
        if choice in {"n", "s", "e", "o"}:
            self.move_player(choice)
        elif choice == "e":
            self.try_encounter()
        elif choice == "m":
            self.render_map(full=True)
        elif choice == "q":
            self.state = State.QUESTS
        elif choice == "i":
            self.state = State.INVENTORY
        elif choice == "c":
            self.state = State.CHARACTER
        elif choice == "t":
            self.state = State.SHOP
        elif choice == "s":
            self.save_game()
        elif choice == "x":
            self.state = State.MAIN_MENU
        else:
            print("Comando desconocido")

    def render_map(self, full: bool = False) -> None:
        assert self.player is not None
        size = CONFIG.map_size
        print(self.style.title("=== MAPA ==="))
        for y in range(size):
            row = []
            for x in range(size):
                pos = (x, y)
                symbol = "?"
                if full or pos in self.discovered:
                    tile = self.game_map[pos].tile_type
                    symbol = tile.value[0]
                if pos == self.player.position:
                    symbol = "P"
                row.append(symbol)
            print(" ".join(row))
        self.last_tip = "Recuerda visitar la posada en la ciudad para curarte."
        print(self.last_tip)

    def move_player(self, direction: str) -> None:
        assert self.player is not None
        x, y = self.player.position
        if direction == "n":
            y = clamp(y - 1, 0, CONFIG.map_size - 1)
        elif direction == "s":
            y = clamp(y + 1, 0, CONFIG.map_size - 1)
        elif direction == "e":
            x = clamp(x + 1, 0, CONFIG.map_size - 1)
        elif direction == "o":
            x = clamp(x - 1, 0, CONFIG.map_size - 1)
        self.player.position = (x, y)
        if (x, y) not in self.discovered:
            self.discovered.append((x, y))
            self.game_map[(x, y)].discovered = True
        print(f"Te mueves a {self.game_map[(x, y)].tile_type.value} ({x},{y}).")

    def try_encounter(self) -> None:
        assert self.player is not None
        tile = self.game_map[self.player.position].tile_type
        encounter_chance = {
            TileType.TOWN: 0.0,
            TileType.FOREST: 0.45,
            TileType.CAVE: 0.55,
            TileType.RUINS: 0.4,
            TileType.LAKE: 0.35,
        }[tile]
        if roll_chance(self.rng, encounter_chance):
            enemy = self.generate_enemy(tile)
            print(self.style.warning(f"¡Encuentras un {enemy.name}!"))
            self.state = State.COMBAT
            self.current_enemy = enemy
        else:
            print("No pasa nada por ahora.")

    def generate_enemy(self, tile: TileType) -> Enemy:
        if tile == TileType.CAVE:
            return self.enemy_slime() if roll_chance(self.rng, 0.7) else self.enemy_goblin()
        if tile == TileType.FOREST:
            return self.enemy_slime()
        if tile == TileType.RUINS:
            return self.enemy_goblin()
        if tile == TileType.LAKE:
            return self.enemy_slime()
        return self.enemy_goblin()

    def enemy_slime(self) -> Enemy:
        stats = Stats(lvl=1, exp=0, hp=30, hp_max=30, mp=10, mp_max=10, str=6, int_=4, agi=5, def_=3, gold=5)
        skills = [Skill("Golpe viscoso", "Un golpe pegajoso.", 0, 8, "str")]
        drops = [Item("Gel", "Un trozo de gel." , {"sell": 3}, 3)]
        return Enemy("Slime", stats, skills, drops)

    def enemy_goblin(self) -> Enemy:
        stats = Stats(lvl=2, exp=0, hp=45, hp_max=45, mp=10, mp_max=10, str=9, int_=5, agi=7, def_=4, gold=8)
        skills = [Skill("Tajo", "Ataque veloz", 0, 10, "str")]
        drops = [Item("Daga Rota", "Vieja pero util", {"sell": 5}, 5)]
        return Enemy("Goblin", stats, skills, drops)

    def handle_combat(self) -> None:
        assert self.player is not None
        enemy: Enemy = self.current_enemy
        player = self.player
        while player.stats.hp > 0 and enemy.stats.hp > 0:
            self.render_combat_status(player, enemy)
            action = self.choose_combat_action(player)
            if action == ActionType.FLEE:
                if roll_chance(self.rng, 0.5):
                    print("Logras huir.")
                    self.state = State.EXPLORATION
                    return
                print("No consigues escapar.")
            turn_order = self.determine_turn_order(player, enemy)
            for actor in turn_order:
                if actor == "player":
                    self.resolve_player_action(player, enemy, action)
                    if enemy.stats.hp <= 0:
                        break
                else:
                    self.resolve_enemy_action(enemy, player)
                    if player.stats.hp <= 0:
                        break
            self.process_status_end_of_round(player, enemy)
        if player.stats.hp <= 0:
            print(self.style.danger("Has sido derrotado."))
            self.state = State.GAME_OVER
        else:
            self.combat_victory(player, enemy)
            self.state = State.EXPLORATION

    def render_combat_status(self, player: Player, enemy: Enemy) -> None:
        print(self.style.title("=== COMBATE ==="))
        print(f"{player.name} HP {player.stats.hp}/{player.stats.hp_max} MP {player.stats.mp}/{player.stats.mp_max}")
        print(f"{enemy.name} HP {enemy.stats.hp}/{enemy.stats.hp_max}")
        if player.status_effects:
            statuses = ", ".join(f"{s.status.name}( {s.duration})" for s in player.status_effects)
            print(f"Estados: {statuses}")
        if enemy.status_effects:
            statuses = ", ".join(f"{s.status.name}( {s.duration})" for s in enemy.status_effects)
            print(f"Enemigo: {statuses}")

    def choose_combat_action(self, player: Player) -> ActionType:
        print("1) Atacar 2) Habilidad 3) Objeto 4) Defender 5) Huir")
        choice = safe_input("> ")
        mapping = {
            "1": ActionType.ATTACK,
            "2": ActionType.SKILL,
            "3": ActionType.ITEM,
            "4": ActionType.DEFEND,
            "5": ActionType.FLEE,
        }
        return mapping.get(choice or "", ActionType.ATTACK)

    def determine_turn_order(self, player: Player, enemy: Enemy) -> List[str]:
        if player.stats.agi >= enemy.stats.agi:
            return ["player", "enemy"]
        return ["enemy", "player"]

    def resolve_player_action(self, player: Player, enemy: Enemy, action: ActionType) -> None:
        if action == ActionType.ATTACK:
            damage = calc_damage(player.stats, enemy.stats, None, self.rng)
            enemy.stats.hp = clamp(enemy.stats.hp - damage, 0, enemy.stats.hp_max)
            print(self.style.success(f"Infliges {damage} de daño."))
        elif action == ActionType.SKILL and player.skills:
            skill = player.skills[0]
            if player.stats.mp < skill.mp_cost:
                print("No tienes MP suficiente.")
            else:
                player.stats.mp -= skill.mp_cost
                damage = calc_damage(player.stats, enemy.stats, skill, self.rng)
                enemy.stats.hp = clamp(enemy.stats.hp - damage, 0, enemy.stats.hp_max)
                print(self.style.success(f"{skill.name} causa {damage} de daño."))
                if skill.status:
                    status = StatusEffect(skill.status[0], skill.status[1], skill.status[2])
                    apply_status(enemy.status_effects, status)
        elif action == ActionType.ITEM and player.inventory:
            item = player.inventory[0]
            self.use_item(player, item)
            if item.consumable:
                player.inventory.pop(0)
        elif action == ActionType.DEFEND:
            player.stats.def_ += 2
            print("Te preparas para defenderte.")
        elif action == ActionType.FLEE:
            print("Intentas huir...")

    def resolve_enemy_action(self, enemy: Enemy, player: Player) -> None:
        if enemy.stats.hp < enemy.stats.hp_max * 0.35 and any(item.name == "Poción" for item in enemy.drops):
            potion = next(item for item in enemy.drops if item.name == "Poción")
            self.use_item_enemy(enemy, potion)
            return
        if any(effect.status == StatusType.STUN for effect in player.status_effects):
            skill = enemy.skills[0]
        else:
            skill = enemy.skills[0]
        damage = calc_damage(enemy.stats, player.stats, skill, self.rng)
        player.apply_damage(damage)
        print(self.style.danger(f"El {enemy.name} golpea por {damage}."))

    def process_status_end_of_round(self, player: Player, enemy: Enemy) -> None:
        for effect in list(player.status_effects):
            self.apply_status_effect(player, effect)
        for effect in list(enemy.status_effects):
            self.apply_status_effect(enemy, effect)

    def apply_status_effect(self, target: Player | Enemy, effect: StatusEffect) -> None:
        if effect.status == StatusType.POISON:
            amount = max(1, effect.potency)
            if isinstance(target, Player):
                target.apply_damage(amount)
            else:
                target.stats.hp = clamp(target.stats.hp - amount, 0, target.stats.hp_max)
            print(f"{effect.status.name} causa {amount} de daño.")
        elif effect.status == StatusType.BURN:
            amount = max(1, effect.potency)
            if isinstance(target, Player):
                target.apply_damage(amount)
            else:
                target.stats.hp = clamp(target.stats.hp - amount, 0, target.stats.hp_max)
        elif effect.status == StatusType.REGEN:
            amount = max(1, effect.potency)
            if isinstance(target, Player):
                target.heal(amount)
            else:
                target.stats.hp = clamp(target.stats.hp + amount, 0, target.stats.hp_max)
        effect.duration -= 1
        if effect.duration <= 0:
            if isinstance(target, Player):
                target.status_effects.remove(effect)
            else:
                target.status_effects.remove(effect)

    def combat_victory(self, player: Player, enemy: Enemy) -> None:
        gained_exp = 20 + enemy.stats.lvl * 10
        player.stats.gold += enemy.stats.gold
        leveled = player.stats.gain_exp(gained_exp)
        if not self.testing:
            print(self.style.success(f"Ganas {gained_exp} de experiencia y {enemy.stats.gold} de oro."))
        if leveled and not self.testing:
            print(self.style.success(f"¡Subes a nivel {player.stats.lvl}!"))
            self.auto_unlock_skills(player)
            self.save_game()
        for quest in player.quests:
            if quest.objective_type == "kill" and quest.target == enemy.name:
                quest.progress += 1
                if quest.progress >= quest.required and not quest.completed:
                    quest.completed = True
                    rewards = self.apply_quest_rewards(player, quest)
                    if not self.testing:
                        print(self.style.success(f"Quest completada: {quest.name}. Recompensas: {rewards}"))
                    self.save_game()

    def auto_unlock_skills(self, player: Player) -> None:
        for level, skill in CLASS_SKILLS[player.class_type]:
            if player.stats.lvl >= level and skill.name not in [s.name for s in player.skills]:
                player.skills.append(skill)
                print(self.style.success(f"Aprendes {skill.name}."))

    def apply_quest_rewards(self, player: Player, quest: Quest) -> str:
        leveled = player.stats.gain_exp(quest.reward_exp)
        player.stats.gold += quest.reward_gold
        details = [f"{quest.reward_exp} EXP", f"{quest.reward_gold} oro"]
        if quest.reward_item:
            player.inventory.append(quest.reward_item)
            details.append(quest.reward_item.name)
        if leveled:
            self.auto_unlock_skills(player)
        return ", ".join(details)

    def use_item(self, player: Player, item: Item) -> None:
        if "heal_percent" in item.effect:
            amount = int(player.stats.hp_max * item.effect["heal_percent"] / 100)
            player.heal(amount)
            print(f"Recuperas {amount} de HP.")
        elif "mp_percent" in item.effect:
            amount = int(player.stats.mp_max * item.effect["mp_percent"] / 100)
            player.restore_mp(amount)
            print(f"Recuperas {amount} de MP.")
        elif "cure" in item.effect:
            player.status_effects = [s for s in player.status_effects if s.status.name != item.effect["cure"]]
            print("Remedias el estado.")
        elif "damage" in item.effect:
            if hasattr(self, "current_enemy"):
                enemy: Enemy = self.current_enemy
                enemy.stats.hp = clamp(enemy.stats.hp - item.effect["damage"], 0, enemy.stats.hp_max)
                print(f"Bomba inflige {item.effect['damage']} de daño.")

    def use_item_enemy(self, enemy: Enemy, item: Item) -> None:
        if "heal_percent" in item.effect:
            amount = int(enemy.stats.hp_max * item.effect["heal_percent"] / 100)
            enemy.stats.hp = clamp(enemy.stats.hp + amount, 0, enemy.stats.hp_max)
            print("El enemigo usa una poción.")

    def handle_shop(self) -> None:
        assert self.player is not None
        inventory = self.shop_inventory()
        print(self.style.title("=== TIENDA ==="))
        for idx, item in enumerate(inventory, 1):
            print(f"[{idx}] {item.name} - {item.price} oro")
        print("[0] Salir")
        choice = safe_input("> ")
        if choice is None or choice == "0":
            self.state = State.EXPLORATION
            return
        if choice.isdigit() and 1 <= int(choice) <= len(inventory):
            item = inventory[int(choice) - 1]
            if self.player.stats.gold >= item.price:
                self.player.stats.gold -= item.price
                if isinstance(item, Equipment):
                    self.player.equip(item)
                    print(self.style.success(f"Equipas {item.name}."))
                else:
                    self.player.inventory.append(item)
                    print(self.style.success(f"Compras {item.name}."))
                self.save_game()
            else:
                print("No tienes suficiente oro.")
        else:
            print("Opción no válida.")

    def shop_inventory(self) -> List[Equipment | Item]:
        weapon = Equipment("Bastón Robusto", "Aumenta el poder mágico", "weapon", {"int_": 3}, 20)
        armor = Equipment("Túnica Ligera", "Protección básica", "armor", {"def_": 2}, 15)
        potion = Item("Poción", "Recupera HP", {"heal_percent": 40}, 10)
        ether = Item("Éter", "Recupera MP", {"mp_percent": 40}, 12)
        return [weapon, armor, potion, ether]

    def handle_inventory(self) -> None:
        assert self.player is not None
        print(self.style.title("=== INVENTARIO ==="))
        for idx, item in enumerate(self.player.inventory, 1):
            print(f"[{idx}] {item.name} - {item.description}")
        print("[E]quipar  [U]sar  [0] Volver")
        choice = safe_input("> ")
        if choice is None or choice == "0":
            self.state = State.EXPLORATION
            return
        if choice.lower() == "e":
            self.equip_from_inventory()
        elif choice.lower() == "u":
            self.use_from_inventory()
        else:
            print("Opción inválida.")

    def equip_from_inventory(self) -> None:
        assert self.player is not None
        equipment_items = [item for item in self.player.inventory if isinstance(item, Equipment)]
        if not equipment_items:
            print("No tienes equipo para equipar.")
            return
        for idx, item in enumerate(equipment_items, 1):
            print(f"[{idx}] {item.name}")
        choice = safe_input("Selecciona equipo: ")
        if choice and choice.isdigit() and 1 <= int(choice) <= len(equipment_items):
            item = equipment_items[int(choice) - 1]
            self.player.equip(item)
            self.player.inventory.remove(item)
            print(self.style.success(f"Equipas {item.name}."))
            self.save_game()

    def use_from_inventory(self) -> None:
        assert self.player is not None
        if not self.player.inventory:
            print("Inventario vacío.")
            return
        for idx, item in enumerate(self.player.inventory, 1):
            print(f"[{idx}] {item.name}")
        choice = safe_input("Selecciona objeto: ")
        if choice and choice.isdigit() and 1 <= int(choice) <= len(self.player.inventory):
            item = self.player.inventory[int(choice) - 1]
            self.use_item(self.player, item)
            if item.consumable:
                self.player.inventory.pop(int(choice) - 1)

    def handle_character(self) -> None:
        assert self.player is not None
        stats = self.player.stats
        print(self.style.title(f"=== {self.player.name} ({self.player.class_type.value}) ==="))
        print(
            f"Nivel {stats.lvl} EXP {stats.exp}/{stats.exp_to_next()}\n"
            f"HP {stats.hp}/{stats.hp_max} MP {stats.mp}/{stats.mp_max}\n"
            f"STR {stats.str} INT {stats.int_} AGI {stats.agi} DEF {stats.def_}\n"
            f"Oro: {stats.gold}"
        )
        print("Habilidades:")
        for skill in self.player.skills:
            print(f"- {skill.name}: {skill.description}")
        safe_input("Enter para volver")
        self.state = State.EXPLORATION

    def handle_quests(self) -> None:
        assert self.player is not None
        print(self.style.title("=== MISIONES ==="))
        for quest in self.player.quests:
            status = "Completada" if quest.completed else f"{quest.progress}/{quest.required}"
            print(f"- {quest.name}: {quest.description} ({status})")
        safe_input("Enter para volver")
        self.state = State.EXPLORATION

    def handle_saveload(self) -> None:
        loaded = self.load_game()
        if loaded:
            self.state = State.EXPLORATION
        else:
            print("No se pudo cargar.")
            self.state = State.MAIN_MENU

    def save_game(self) -> None:
        if self.player is None:
            return
        state = GameState(self.state, self.player, self.game_map, self.discovered)
        data = state.to_dict()
        save_path = CONFIG.save_path
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with save_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        if not self.testing:
            print(self.style.success("Partida guardada."))

    def load_game(self) -> bool:
        save_path = CONFIG.save_path
        if not save_path.exists():
            return False
        try:
            with save_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError:
            print("Archivo de guardado corrupto.")
            return False
        state = GameState.from_dict(data)
        self.state = State.EXPLORATION
        self.player = state.player
        self.game_map = state.game_map
        self.discovered = state.discovered
        return True

    def create_player(self, name: str, class_type: ClassType) -> Player:
        base_stats = BASE_STATS[class_type].copy()
        base_stats.hp = base_stats.hp_max
        base_stats.mp = base_stats.mp_max
        skills = [skill for level, skill in CLASS_SKILLS[class_type] if level == 1]
        player = Player(name=name, class_type=class_type, stats=base_stats, skills=list(skills))
        player.inventory = [Item("Poción", "Recupera 35% HP", {"heal_percent": 35}, 0)]
        player.quests = [create_default_quest()]
        return player


def base_stats_for_class() -> Dict[ClassType, Stats]:
    return {
        ClassType.WARRIOR: Stats(1, 0, 50, 50, 15, 15, 10, 5, 7, 8, 30),
        ClassType.MAGE: Stats(1, 0, 40, 40, 25, 25, 5, 12, 6, 6, 30),
        ClassType.ROGUE: Stats(1, 0, 45, 45, 18, 18, 8, 6, 10, 7, 30),
    }


def create_class_skills() -> Dict[ClassType, List[Tuple[int, Skill]]]:
    return {
        ClassType.WARRIOR: [
            (1, Skill("Golpe Pesado", "Ataque básico del guerrero", 0, 10, "str")),
            (3, Skill("Cuchillada", "Ataque giratorio", 5, 18, "str")),
            (5, Skill("Grito de guerra", "Aumenta defensa", 6, 12, "str", (StatusType.REGEN, 5, 3))),
            (7, Skill("Rompeescudos", "Ignora defensa", 8, 22, "str")),
            (9, Skill("Embate", "Golpe demoledor", 10, 28, "str")),
            (11, Skill("Guardia de hierro", "Defensa absoluta", 12, 0, "str", (StatusType.REGEN, 8, 3))),
        ],
        ClassType.MAGE: [
            (1, Skill("Piro", "Chispa ardiente", 3, 12, "int", (StatusType.BURN, 3, 2))),
            (1, Skill("Hielo", "Proyectil congelante", 3, 11, "int")),
            (1, Skill("Escudo Arcano", "Reduce daño", 4, 0, "int", (StatusType.REGEN, 4, 3))),
            (3, Skill("Electro", "Descarga eléctrica", 5, 18, "int", (StatusType.STUN, 0, 1))),
            (5, Skill("Llama Viva", "Gran llamarada", 8, 25, "int", (StatusType.BURN, 5, 3))),
            (7, Skill("Tormenta", "Múltiples rayos", 10, 32, "int")),
        ],
        ClassType.ROGUE: [
            (1, Skill("Puñalada", "Ataque rápido", 0, 10, "str")),
            (1, Skill("Disparo", "Ataque a distancia", 2, 12, "str")),
            (1, Skill("Humo", "Reduce acierto", 4, 0, "str", (StatusType.REGEN, 3, 2))),
            (3, Skill("Hemorragia", "Daño en el tiempo", 5, 16, "str", (StatusType.POISON, 3, 3))),
            (5, Skill("Finta", "Aumenta evasión", 6, 0, "str", (StatusType.REGEN, 4, 2))),
            (7, Skill("Asalto", "Combo veloz", 9, 24, "str")),
        ],
    }


BASE_STATS = base_stats_for_class()
CLASS_SKILLS = create_class_skills()


def create_default_quest() -> Quest:
    return Quest(
        name="Derrota 2 Slimes",
        description="Elimina a 2 Slimes cercanos a la ciudad",
        objective_type="kill",
        target="Slime",
        required=2,
        reward_exp=40,
        reward_gold=20,
    )


def run_tests(args: argparse.Namespace) -> None:
    game = Game(args, testing=True)
    rng = game.rng

    player = game.create_player("TestMage", ClassType.MAGE)
    enemy = game.enemy_slime()
    simulate_turns(player, enemy, rng, rounds=3)
    assert player.stats.hp >= 0 and enemy.stats.hp >= 0

    game.player = player
    game.save_game()
    loaded = game.load_game()
    assert loaded
    assert game.player is not None
    assert player.stats.hp == game.player.stats.hp
    assert player.position == game.player.position

    player = game.create_player("Comprador", ClassType.MAGE)
    dummy_enemy = game.enemy_slime()
    rng.seed(42)
    base_damage = calc_damage(player.stats, dummy_enemy.stats, None, rng)
    weapon = game.shop_inventory()[0]
    assert isinstance(weapon, Equipment)
    player.stats.gold += weapon.price
    player.equip(weapon)
    rng.seed(42)
    new_damage = calc_damage(player.stats, dummy_enemy.stats, None, rng)
    assert new_damage >= base_damage

    player = game.create_player("Quest", ClassType.WARRIOR)
    player.quests = [create_default_quest()]
    enemy = game.enemy_slime()
    for _ in range(2):
        simulate_turns(player, enemy, rng, rounds=1)
        player.stats.hp = player.stats.hp_max
        enemy = game.enemy_slime()
        game.combat_victory(player, enemy)
    quest = player.quests[0]
    assert quest.completed
    assert player.stats.exp > 0 and player.stats.gold >= BASE_STATS[ClassType.WARRIOR].gold

    print("TESTS OK")


def simulate_turns(player: Player, enemy: Enemy, rng: random.Random, rounds: int) -> None:
    for _ in range(rounds):
        if player.stats.hp <= 0 or enemy.stats.hp <= 0:
            break
        order = [player, enemy] if player.stats.agi >= enemy.stats.agi else [enemy, player]
        for actor in order:
            if actor is player:
                damage = calc_damage(player.stats, enemy.stats, None, rng)
                enemy.stats.hp = clamp(enemy.stats.hp - damage, 0, enemy.stats.hp_max)
            else:
                damage = calc_damage(enemy.stats, player.stats, None, rng)
                player.apply_damage(damage)
            if player.stats.hp <= 0 or enemy.stats.hp <= 0:
                break


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RPG por turnos en consola")
    parser.add_argument("--seed", type=int, default=None, help="Semilla RNG")
    parser.add_argument("--debug", action="store_true", help="Activa mensajes debug")
    parser.add_argument("--no-color", action="store_true", dest="no_color", help="Desactiva color ANSI")
    parser.add_argument("--test", action="store_true", help="Ejecuta pruebas de humo")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> None:
    args = parse_args(argv)
    if args.test:
        run_tests(args)
        return
    game = Game(args)
    game.run()


if __name__ == "__main__":
    main()
