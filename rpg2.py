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
from dataclasses import dataclass, field, asdict, replace
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


@dataclass(frozen=True)
class Zone:
    name: str
    tile_type: TileType
    danger: float
    description: str
    features: Tuple[str, ...] = field(default_factory=tuple)


@dataclass
class Location:
    position: Tuple[int, int]
    tile_type: TileType
    discovered: bool = False
    zone: str = ""
    description: str = ""
    danger: float = 0.0
    features: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, object]:
        return {
            "position": list(self.position),
            "tile_type": self.tile_type.name,
            "discovered": self.discovered,
            "zone": self.zone,
            "description": self.description,
            "danger": self.danger,
            "features": list(self.features),
        }

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "Location":
        return Location(
            position=(int(data["position"][0]), int(data["position"][1])),
            tile_type=TileType[data["tile_type"]],
            discovered=bool(data.get("discovered", False)),
            zone=str(data.get("zone", "")),
            description=str(data.get("description", "")),
            danger=float(data.get("danger", 0.0)),
            features=tuple(data.get("features", [])),
        )


ZONE_BLUEPRINTS: Dict[Tuple[int, str], Zone] = {
    (0, "C"): Zone(
        "Plaza de Eteria",
        TileType.TOWN,
        0.0,
        "El corazón comercial del reino, siempre bullicioso.",
        ("Posada", "Mercado", "Gremio de aventureros"),
    ),
    (1, "C"): Zone(
        "Barrio Artesano",
        TileType.TOWN,
        0.0,
        "Calles estrechas llenas de talleres y vecinos amables.",
        ("Forja", "Biblioteca", "Tablón de misiones"),
    ),
    (2, "N"): Zone(
        "Bosque Brumoso",
        TileType.FOREST,
        0.4,
        "Árboles retorcidos cubiertos por una niebla perpetua.",
        ("Hierbas curativas", "Riachuelos ocultos"),
    ),
    (2, "S"): Zone(
        "Ruinas Antiguas",
        TileType.RUINS,
        0.45,
        "Restos de una civilización olvidada plagados de trampas.",
        ("Obeliscos", "Criptas selladas"),
    ),
    (2, "E"): Zone(
        "Caverna Ámbar",
        TileType.CAVE,
        0.5,
        "Minerales brillantes iluminan los pasajes sinuosos.",
        ("Vetas de mana", "Minerales raros"),
    ),
    (2, "W"): Zone(
        "Lago Sereno",
        TileType.LAKE,
        0.25,
        "Aguas tranquilas donde descansan espíritus acuáticos.",
        ("Pesca", "Isletas cubiertas de flores"),
    ),
    (2, "NE"): Zone(
        "Laderas Ventosas",
        TileType.FOREST,
        0.38,
        "Colinas arboladas batidas por corrientes de aire constante.",
        ("Miradores", "Senderos secretos"),
    ),
    (2, "NW"): Zone(
        "Sendero del Roble",
        TileType.FOREST,
        0.33,
        "Robles milenarios crean un dosel casi impenetrable.",
        ("Setas raras", "Refugios naturales"),
    ),
    (2, "SE"): Zone(
        "Catacumbas Menores",
        TileType.RUINS,
        0.48,
        "Pasadizos estrechos comunicados con las ruinas mayores.",
        ("Altares hundidos", "Reliquias olvidadas"),
    ),
    (2, "SW"): Zone(
        "Manantial Termal",
        TileType.LAKE,
        0.3,
        "Corrientes cálidas emergen de grietas cristalinas.",
        ("Baños minerales", "Vapor relajante"),
    ),
    (3, "N"): Zone(
        "Bosque Umbrío",
        TileType.FOREST,
        0.5,
        "Sombras densas ocultan bestias ágiles y territoriales.",
        ("Cuevas de lobos", "Raíces luminosas"),
    ),
    (3, "S"): Zone(
        "Cementerio Real",
        TileType.RUINS,
        0.55,
        "Mausoleos derruidos donde vagan espíritus inquietos.",
        ("Mausoleos", "Estatuas derruidas"),
    ),
    (3, "E"): Zone(
        "Galerías del Eco",
        TileType.CAVE,
        0.6,
        "Túneles que resuenan con rugidos de criaturas subterráneas.",
        ("Cristales resonantes", "Corrientes subterráneas"),
    ),
    (3, "W"): Zone(
        "Pantano Plateado",
        TileType.LAKE,
        0.4,
        "Ciénagas cubiertas por una niebla plateada que confunde el paso.",
        ("Nenúfares", "Esencias alquímicas"),
    ),
    (3, "NE"): Zone(
        "Arboleda del Silbido",
        TileType.FOREST,
        0.45,
        "Bosquecillo donde el viento canta entre las hojas.",
        ("Piedras cantoras", "Nidos elevados"),
    ),
    (3, "NW"): Zone(
        "Pico del Cuervo",
        TileType.CAVE,
        0.58,
        "Acantilados abruptos custodiados por goblins vigías.",
        ("Nidos de cuervos", "Miradores naturales"),
    ),
    (3, "SE"): Zone(
        "Cripta Olvidada",
        TileType.RUINS,
        0.6,
        "Catacumbas profundas donde resuenan cánticos apagados.",
        ("Runas marchitas", "Sarcófagos"),
    ),
    (3, "SW"): Zone(
        "Isla de los Suspiros",
        TileType.LAKE,
        0.42,
        "Pequeñas islas conectadas por pasarelas de madera.",
        ("Recolección de perlas", "Viento calmante"),
    ),
    (4, "N"): Zone(
        "Muro de Espinas",
        TileType.FOREST,
        0.6,
        "Un cinturón de vegetación agresiva que protege el norte.",
        ("Zarzales", "Bestias guardianas"),
    ),
    (4, "S"): Zone(
        "Santuario Perdido",
        TileType.RUINS,
        0.65,
        "Templo hundido dedicado a una deidad olvidada.",
        ("Altares brillantes", "Guardianes espectrales"),
    ),
    (4, "E"): Zone(
        "Fosa de Obsidiana",
        TileType.CAVE,
        0.68,
        "Pozos profundos llenos de cristales oscuros.",
        ("Gemas afiladas", "Vapores tóxicos"),
    ),
    (4, "W"): Zone(
        "Delta Turquesa",
        TileType.LAKE,
        0.45,
        "Aguas rápidas que desembocan en el mar interior.",
        ("Pesca difícil", "Corrientes impredecibles"),
    ),
    (4, "NE"): Zone(
        "Atalaya del Relámpago",
        TileType.CAVE,
        0.7,
        "Ruinas verticales donde se concentran tormentas mágicas.",
        ("Pararrayos", "Runas chisporroteantes"),
    ),
    (4, "NW"): Zone(
        "Bosque del Alba",
        TileType.FOREST,
        0.55,
        "La luz del amanecer se filtra creando destellos dorados.",
        ("Flores etéreas", "Círculos de hadas"),
    ),
    (4, "SE"): Zone(
        "Nexo del Caos",
        TileType.RUINS,
        0.7,
        "Portal inestable sellado por antiguos guardianes.",
        ("Sellos arcanos", "Energía errática"),
    ),
    (4, "SW"): Zone(
        "Marjal Dorado",
        TileType.LAKE,
        0.5,
        "Turberas brillantes donde afloran minerales dorados.",
        ("Limo dorado", "Vapores cálidos"),
    ),
}


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
    day: int
    turn_count: int
    quest_board: List[Quest]
    shop_stock: List[Equipment | Item]

    def to_dict(self) -> Dict[str, object]:
        return {
            "state": self.state.name,
            "player": self.player.to_dict() if self.player else None,
            "game_map": {f"{x},{y}": location.to_dict() for (x, y), location in self.game_map.items()},
            "discovered": [list(pos) for pos in self.discovered],
            "day": self.day,
            "turn_count": self.turn_count,
            "quest_board": [quest.to_dict() for quest in self.quest_board],
            "shop_stock": [
                {"kind": "item", "value": item.to_dict()} if isinstance(item, Item)
                else {"kind": "equipment", "value": item.to_dict()}
                for item in self.shop_stock
            ],
        }

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "GameState":
        map_dict = {}
        for key, value in data.get("game_map", {}).items():
            x_str, y_str = key.split(",")
            map_dict[(int(x_str), int(y_str))] = Location.from_dict(value)
        player_data = data.get("player")
        player = Player.from_dict(player_data) if player_data else None
        quest_board = [Quest.from_dict(q) for q in data.get("quest_board", [])]
        stock: List[Equipment | Item] = []
        for entry in data.get("shop_stock", []):
            if entry.get("kind") == "equipment":
                stock.append(Equipment.from_dict(entry["value"]))
            else:
                stock.append(Item.from_dict(entry["value"]))
        return GameState(
            state=State[data["state"]],
            player=player,
            game_map=map_dict,
            discovered=[(int(pos[0]), int(pos[1])) for pos in data.get("discovered", [])],
            day=int(data.get("day", 1)),
            turn_count=int(data.get("turn_count", 0)),
            quest_board=quest_board,
            shop_stock=stock,
        )


@dataclass(frozen=True)
class Config:
    save_path: Path
    map_size: int
    debug_log: bool = False


CONFIG = Config(save_path=Path("~/.rpg_saves/save.json").expanduser(), map_size=9)


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
        self.start_position = (CONFIG.map_size // 2, CONFIG.map_size // 2)
        self._init_map()
        self.current_enemy: Optional[Enemy] = None
        self.player_guard_active = False
        self.day = 1
        self.turn_count = 0
        self.quest_board: List[Quest] = []
        self.shop_stock: List[Equipment | Item] = []
        self.refresh_quest_board()
        self.build_shop_stock()
        use_color = sys.stdout.isatty() and not getattr(args, "no_color", False)
        self.style = TerminalStyler(use_color)
        self.last_tip = ""

    def _init_map(self) -> None:
        size = CONFIG.map_size
        center = size // 2
        for y in range(size):
            for x in range(size):
                zone = self._zone_for_position(x, y, center)
                discovered = zone.tile_type == TileType.TOWN
                location = Location(
                    position=(x, y),
                    tile_type=zone.tile_type,
                    discovered=discovered,
                    zone=zone.name,
                    description=zone.description,
                    danger=zone.danger,
                    features=zone.features,
                )
                self.game_map[(x, y)] = location
                if discovered:
                    self.discovered.append((x, y))
        if self.start_position not in self.discovered:
            self.discovered.append(self.start_position)
            self.game_map[self.start_position].discovered = True

    def _zone_for_position(self, x: int, y: int, center: int) -> Zone:
        dx = x - center
        dy = y - center
        ring = max(abs(dx), abs(dy))
        direction = self._direction_for_delta(dx, dy)
        if ring <= 1:
            direction = "C"
        zone = ZONE_BLUEPRINTS.get((ring, direction))
        if zone:
            return zone
        fallback_type = {
            "N": TileType.FOREST,
            "S": TileType.RUINS,
            "E": TileType.CAVE,
            "W": TileType.LAKE,
            "NE": TileType.FOREST,
            "NW": TileType.FOREST,
            "SE": TileType.RUINS,
            "SW": TileType.LAKE,
        }.get(direction, TileType.FOREST)
        base_name = {
            "N": "Frontera Norte",
            "S": "Dominio Sur",
            "E": "Galerías Orientales",
            "W": "Costa Occidental",
            "NE": "Colina Boreal",
            "NW": "Acantilado Boreal",
            "SE": "Depresión Meridional",
            "SW": "Delta Meridional",
        }.get(direction, "Tierras Fronterizas")
        danger = 0.35 + 0.05 * ring
        description = "Territorio sin cartografiar repleto de oportunidades y peligros."
        return Zone(base_name, fallback_type, danger, description, ("Exploración incierta",))

    def _direction_for_delta(self, dx: int, dy: int) -> str:
        if dx == 0 and dy == 0:
            return "C"
        parts: List[str] = []
        if dy < 0:
            parts.append("N")
        elif dy > 0:
            parts.append("S")
        if dx > 0:
            parts.append("E")
        elif dx < 0:
            parts.append("W")
        return "".join(parts) if parts else "C"

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
        self.player.position = self.start_position
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
            - Pulsa E (mayúscula) o escribe "explorar" para buscar encuentros.
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
        self.describe_current_location()
        location = self.game_map[self.player.position]
        in_town = location.tile_type == TileType.TOWN
        menu = "[N]orte [S]ur [E]ste [O]este [E]xplorar [M]apa [Q]uests [I]nventario [C]arácter"
        if in_town:
            menu += " [P]osada [T]ienda"
        else:
            menu += " [R]esguardar"
        menu += " [S]alvar [X] Salir"
        print(menu)
        raw_choice = safe_input("> ")
        if raw_choice is None:
            self.state = State.GAME_OVER
            self.save_game()
            return
        choice = raw_choice.strip()
        lowered = choice.lower()
        if choice == "E" or lowered in {"explorar", "exp", "buscar"}:
            self.try_encounter()
        elif lowered in {"n", "s", "e", "o", "norte", "sur", "este", "oeste"}:
            self.move_player(lowered[0])
        elif lowered == "m":
            self.render_map(full=True)
            self.describe_current_location()
        elif lowered == "q":
            self.state = State.QUESTS
        elif lowered == "i":
            self.state = State.INVENTORY
        elif lowered == "c":
            self.state = State.CHARACTER
        elif lowered == "p" and in_town:
            self.visit_inn()
        elif lowered == "r" and not in_town:
            self.make_camp()
        elif lowered == "t":
            if in_town or self.testing:
                self.state = State.SHOP
            else:
                print("No hay ninguna tienda aquí.")
        elif lowered == "s":
            self.save_game()
        elif lowered == "x":
            self.state = State.MAIN_MENU
            self.save_game()
        else:
            print("Comando desconocido")

    def render_map(self, full: bool = False) -> None:
        assert self.player is not None
        size = CONFIG.map_size
        print(self.style.title("=== MAPA ==="))
        print(f"Día {self.day} · Turno {self.turn_count}")
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
        legend = "Leyenda: P=Jugador T=Town F=Forest C=Cave R=Ruins L=Lake ?=Desconocido"
        print(legend)

    def describe_current_location(self) -> None:
        assert self.player is not None
        location = self.game_map[self.player.position]
        header = f"{location.zone} [{location.tile_type.value}]"
        print(self.style.title(header))
        print(location.description)
        if location.features:
            print("Puntos de interés: " + ", ".join(location.features))
        danger_pct = int(location.danger * 100)
        self.last_tip = f"Peligro estimado {danger_pct}%."
        print(self.style.warning(self.last_tip))

    def advance_time(self, steps: int = 1) -> None:
        self.turn_count += steps
        if self.turn_count % 6 == 0:
            self.day += 1
            self.refresh_quest_board()
            self.build_shop_stock()
            if not self.testing:
                print(self.style.warning(f"Amanece el día {self.day}. Nuevas misiones y mercancías disponibles."))

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
        self.advance_time()

    def visit_inn(self) -> None:
        assert self.player is not None
        cost = 15
        if self.player.stats.gold < cost:
            print("La posada cuesta 15 de oro. No tienes suficiente oro.")
            return
        self.player.stats.gold -= cost
        self.player.stats.hp = self.player.stats.hp_max
        self.player.stats.mp = self.player.stats.mp_max
        self.player.status_effects.clear()
        print(self.style.success("Descansas en la posada y recuperas tus fuerzas."))
        self.last_tip = "Un buen descanso mantiene a raya a los monstruos."
        self.advance_time(2)

    def make_camp(self) -> None:
        assert self.player is not None
        location = self.game_map[self.player.position]
        print("Levantas un pequeño campamento y enciendes una fogata.")
        heal = max(1, int(self.player.stats.hp_max * 0.25))
        mana = max(1, int(self.player.stats.mp_max * 0.2))
        self.player.heal(heal)
        self.player.restore_mp(mana)
        cleansed = [
            effect
            for effect in list(self.player.status_effects)
            if effect.status in {StatusType.POISON, StatusType.BURN}
        ]
        if cleansed:
            for effect in cleansed:
                self.player.status_effects.remove(effect)
            print("El descanso te libra de efectos nocivos.")
        danger = max(0.1, location.danger - 0.15)
        self.advance_time(2)
        if roll_chance(self.rng, danger):
            print(self.style.danger("¡Una emboscada interrumpe tu descanso!"))
            enemy = self.generate_enemy(location.tile_type)
            self.current_enemy = enemy
            self.state = State.COMBAT
        else:
            print(self.style.success("Amaneces revitalizado tras el campamento."))
            self.last_tip = "Preparar un refugio reduce el peligro futuro."

    def try_encounter(self) -> None:
        assert self.player is not None
        location = self.game_map[self.player.position]
        self.advance_time()
        if location.tile_type == TileType.TOWN:
            print("Dentro de la ciudad no hay amenazas inmediatas.")
            return
        if roll_chance(self.rng, location.danger):
            enemy = self.generate_enemy(location.tile_type)
            print(self.style.warning(f"¡Encuentras un {enemy.name}!"))
            self.state = State.COMBAT
            self.current_enemy = enemy
        else:
            if roll_chance(self.rng, 0.25):
                self.trigger_zone_event(location)
            else:
                print("Exploras la zona sin incidentes relevantes.")

    def trigger_zone_event(self, location: Location) -> None:
        assert self.player is not None
        if location.tile_type == TileType.FOREST:
            herb = Item("Hierba curativa", "Ingrediente que restaura algo de salud.", {"heal_percent": 15}, 4)
            self.player.inventory.append(herb)
            print(self.style.success("Recolectas hierbas frescas entre los arbustos."))
        elif location.tile_type == TileType.CAVE:
            bomb = Item("Bomba", "Inflige daño explosivo al enemigo.", {"damage": 30}, 18)
            self.player.inventory.append(bomb)
            print(self.style.success("Encuentras una bomba olvidada entre rocas."))
        elif location.tile_type == TileType.RUINS:
            gold_found = self.rng.randint(12, 24)
            self.player.stats.gold += gold_found
            print(self.style.success(f"Descubres un cofre oculto con {gold_found} de oro."))
        elif location.tile_type == TileType.LAKE:
            heal = int(self.player.stats.hp_max * 0.15)
            self.player.heal(heal)
            print(self.style.success("El agua cristalina restaura tus fuerzas."))
        self.last_tip = "Los eventos de zona pueden repetirse tras descansar."

    def generate_enemy(self, tile: TileType) -> Enemy:
        if tile == TileType.CAVE:
            roll = self.rng.random()
            if roll < 0.4:
                return self.enemy_goblin()
            if roll < 0.75:
                return self.enemy_salamander()
            return self.enemy_cave_boss() if roll_chance(self.rng, 0.15) else self.enemy_salamander()
        if tile == TileType.FOREST:
            roll = self.rng.random()
            if roll < 0.45:
                return self.enemy_slime()
            if roll < 0.75:
                return self.enemy_wolf()
            return self.enemy_bandit()
        if tile == TileType.RUINS:
            roll = self.rng.random()
            if roll < 0.5:
                return self.enemy_skeleton()
            if roll < 0.85:
                return self.enemy_bandit()
            return self.enemy_cave_boss()
        if tile == TileType.LAKE:
            roll = self.rng.random()
            if roll < 0.55:
                return self.enemy_slime()
            if roll < 0.85:
                return self.enemy_spirit()
            return self.enemy_wolf()
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

    def enemy_wolf(self) -> Enemy:
        stats = Stats(lvl=2, exp=0, hp=38, hp_max=38, mp=12, mp_max=12, str=9, int_=4, agi=10, def_=4, gold=9)
        skills = [
            Skill("Mordisco", "Ataque rápido que desgarra.", 0, 11, "str"),
            Skill("Aullido", "Intimida y aturde momentáneamente.", 3, 0, "str", (StatusType.STUN, 0, 1)),
        ]
        drops = [
            Item("Poción", "Recupera salud.", {"heal_percent": 35}, 10),
            Item("Colmillo de lobo", "Material afilado.", {"sell": 6}, 6, False),
        ]
        return Enemy("Lobo sombrío", stats, skills, drops)

    def enemy_bandit(self) -> Enemy:
        stats = Stats(lvl=3, exp=0, hp=42, hp_max=42, mp=16, mp_max=16, str=11, int_=6, agi=9, def_=5, gold=14)
        skills = [
            Skill("Puñalada sucia", "Ataque con veneno.", 4, 14, "str", (StatusType.POISON, 3, 2)),
            Skill("Disparo preciso", "Ataque a distancia.", 3, 16, "str"),
        ]
        drops = [
            Item("Bomba", "Explosivo improvisado.", {"damage": 28}, 22),
            Item("Bolsa de monedas", "Pequeño botín.", {"sell": 12}, 12, False),
        ]
        return Enemy("Bandido", stats, skills, drops)

    def enemy_skeleton(self) -> Enemy:
        stats = Stats(lvl=3, exp=0, hp=48, hp_max=48, mp=14, mp_max=14, str=10, int_=7, agi=6, def_=6, gold=16)
        skills = [
            Skill("Lanza ósea", "Proyectil de hueso.", 0, 13, "str"),
            Skill("Grito sepulcral", "Aterroriza con energía oscura.", 4, 0, "int", (StatusType.STUN, 0, 1)),
        ]
        drops = [
            Item("Éter", "Recupera magia.", {"mp_percent": 35}, 14),
            Item("Hueso rúnico", "Relicario extraño.", {"sell": 15}, 15, False),
        ]
        return Enemy("Esqueleto", stats, skills, drops)

    def enemy_salamander(self) -> Enemy:
        stats = Stats(lvl=3, exp=0, hp=44, hp_max=44, mp=18, mp_max=18, str=9, int_=11, agi=7, def_=5, gold=18)
        skills = [
            Skill("Zarpazo", "Golpe ardiente.", 0, 12, "str"),
            Skill("Aliento ígneo", "Llama abrasadora.", 5, 18, "int", (StatusType.BURN, 4, 2)),
        ]
        drops = [
            Item("Escama cálida", "Escama que irradia calor.", {"sell": 10}, 10, False),
            Item("Poción", "Repara heridas.", {"heal_percent": 40}, 12),
        ]
        return Enemy("Salamandra", stats, skills, drops)

    def enemy_spirit(self) -> Enemy:
        stats = Stats(lvl=3, exp=0, hp=40, hp_max=40, mp=20, mp_max=20, str=7, int_=12, agi=8, def_=4, gold=15)
        skills = [
            Skill("Oleada", "Corriente de agua cortante.", 4, 16, "int"),
            Skill("Bruma sanadora", "Restablece parte de su energía.", 5, 0, "int", (StatusType.REGEN, 5, 3)),
        ]
        drops = [
            Item("Agua bendita", "Elimina toxinas.", {"cure": "POISON"}, 18),
            Item("Perla luminosa", "Resplandece al tacto.", {"sell": 14}, 14, False),
        ]
        return Enemy("Espíritu del lago", stats, skills, drops)

    def enemy_cave_boss(self) -> Enemy:
        stats = Stats(lvl=4, exp=0, hp=85, hp_max=85, mp=22, mp_max=22, str=14, int_=10, agi=8, def_=8, gold=35)
        skills = [
            Skill("Embate sísmico", "Sacude el suelo con gran fuerza.", 0, 20, "str"),
            Skill("Rugido petrificador", "Aturde con un estruendo.", 6, 0, "int", (StatusType.STUN, 0, 1)),
            Skill("Llama interna", "Invoca una erupción.", 8, 24, "int", (StatusType.BURN, 5, 2)),
        ]
        drops = [
            Item("Gema resonante", "Cristal cargado de energía.", {"sell": 40}, 40, False),
            Item("Poción", "Recupera gran cantidad de salud.", {"heal_percent": 50}, 20),
        ]
        return Enemy("Tirano de la Cueva", stats, skills, drops)

    def handle_combat(self) -> None:
        assert self.player is not None
        if self.current_enemy is None:
            print("No hay enemigo que enfrentar.")
            self.state = State.EXPLORATION
            return
        enemy: Enemy = self.current_enemy
        player = self.player
        self.player_guard_active = False
        while player.stats.hp > 0 and enemy.stats.hp > 0:
            turn_order = self.determine_turn_order(player, enemy)
            self.render_combat_status(player, enemy, turn_order)
            action = self.choose_combat_action(player)
            if action == ActionType.FLEE:
                if roll_chance(self.rng, 0.5):
                    print("Logras huir.")
                    self.current_enemy = None
                    self.state = State.EXPLORATION
                    return
                print("No consigues escapar.")
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
            self.current_enemy = None
            self.state = State.EXPLORATION

    def render_combat_status(self, player: Player, enemy: Enemy, turn_order: List[str]) -> None:
        print(self.style.title("=== COMBATE ==="))
        print(
            f"{player.name} HP {player.stats.hp}/{player.stats.hp_max} "
            f"MP {player.stats.mp}/{player.stats.mp_max}"
        )
        print(f"{enemy.name} HP {enemy.stats.hp}/{enemy.stats.hp_max} MP {enemy.stats.mp}/{enemy.stats.mp_max}")
        if player.status_effects:
            statuses = ", ".join(f"{s.status.name}({s.duration})" for s in player.status_effects)
            print(f"Estados jugador: {statuses}")
        if enemy.status_effects:
            statuses = ", ".join(f"{s.status.name}({s.duration})" for s in enemy.status_effects)
            print(f"Estados enemigo: {statuses}")
        order_names = [player.name if slot == "player" else enemy.name for slot in turn_order]
        print("Orden de turno: " + " → ".join(order_names))

    def choose_combat_action(self, player: Player) -> ActionType:
        print("1) Atacar  2) Habilidad  3) Objeto  4) Defender  5) Huir")
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
        if any(effect.status == StatusType.STUN for effect in player.status_effects):
            print(self.style.warning("Estás aturdido y pierdes el turno."))
            return
        if action == ActionType.ATTACK:
            damage = calc_damage(player.stats, enemy.stats, None, self.rng)
            enemy.stats.hp = clamp(enemy.stats.hp - damage, 0, enemy.stats.hp_max)
            print(self.style.success(f"Infliges {damage} de daño."))
        elif action == ActionType.SKILL:
            skill = self.select_player_skill(player)
            if skill is None:
                return
            player.stats.mp -= skill.mp_cost
            damage = calc_damage(player.stats, enemy.stats, skill, self.rng)
            enemy.stats.hp = clamp(enemy.stats.hp - damage, 0, enemy.stats.hp_max)
            print(self.style.success(f"{skill.name} causa {damage} de daño."))
            if skill.status:
                status = StatusEffect(skill.status[0], skill.status[1], skill.status[2])
                apply_status(enemy.status_effects, status)
        elif action == ActionType.ITEM:
            item = self.select_combat_item(player)
            if item is None:
                return
            self.use_item(player, item)
            if item.consumable:
                player.inventory.remove(item)
        elif action == ActionType.DEFEND:
            self.player_guard_active = True
            print("Adoptas una postura defensiva y reduces el daño recibido.")
        elif action == ActionType.FLEE:
            print("Intentas huir...")

    def resolve_enemy_action(self, enemy: Enemy, player: Player) -> None:
        if any(effect.status == StatusType.STUN for effect in enemy.status_effects):
            print(self.style.success(f"{enemy.name} está aturdido y no actúa."))
            return
        if enemy.stats.hp < enemy.stats.hp_max * 0.35:
            potion = next((item for item in enemy.drops if item.name == "Poción"), None)
            if potion:
                self.use_item_enemy(enemy, potion)
                enemy.drops.remove(potion)
                return
        skill = self.choose_enemy_skill(enemy, player)
        if skill and enemy.stats.mp < skill.mp_cost:
            skill = None
        if skill:
            enemy.stats.mp -= skill.mp_cost
            damage = calc_damage(enemy.stats, player.stats, skill, self.rng)
            if self.player_guard_active:
                damage = max(1, int(damage * 0.6))
            player.apply_damage(damage)
            print(self.style.danger(f"El {enemy.name} usa {skill.name} e inflige {damage} de daño."))
            if skill.status:
                status = StatusEffect(skill.status[0], skill.status[1], skill.status[2])
                apply_status(player.status_effects, status)
        else:
            damage = calc_damage(enemy.stats, player.stats, None, self.rng)
            if self.player_guard_active:
                damage = max(1, int(damage * 0.6))
            player.apply_damage(damage)
            print(self.style.danger(f"El {enemy.name} golpea por {damage}."))
        if self.player_guard_active:
            self.player_guard_active = False

    def describe_item_effect(self, item: Item) -> str:
        if "heal_percent" in item.effect:
            return f"+{item.effect['heal_percent']}% HP"
        if "mp_percent" in item.effect:
            return f"+{item.effect['mp_percent']}% MP"
        if "cure" in item.effect:
            return f"Cura {item.effect['cure']}"
        if "damage" in item.effect:
            return f"Inflige {item.effect['damage']} de daño"
        if "sell" in item.effect:
            return f"Valor {item.effect['sell']} oro"
        return "Efecto desconocido"

    def clone_item(self, item: Item) -> Item:
        return Item(item.name, item.description, dict(item.effect), item.price, item.consumable)

    def clone_equipment(self, equipment: Equipment) -> Equipment:
        return Equipment(
            equipment.name,
            equipment.description,
            equipment.slot,
            dict(equipment.stat_bonuses),
            equipment.price,
        )

    def select_player_skill(self, player: Player) -> Optional[Skill]:
        if not player.skills:
            print("No conoces habilidades todavía.")
            return None
        while True:
            print("Selecciona una habilidad (0 para cancelar):")
            for idx, skill in enumerate(player.skills, 1):
                status_info = f" [{skill.status[0].name}]" if skill.status else ""
                mp_label = f"{skill.mp_cost} MP"
                unavailable = " - MP insuficiente" if player.stats.mp < skill.mp_cost else ""
                print(f"[{idx}] {skill.name} ({mp_label}){status_info}{unavailable}")
            choice = safe_input("Habilidad: ")
            if choice is None or choice == "0":
                return None
            if choice.isdigit():
                index = int(choice) - 1
                if 0 <= index < len(player.skills):
                    skill = player.skills[index]
                    if player.stats.mp < skill.mp_cost:
                        print("No tienes MP suficiente para esa habilidad.")
                        continue
                    return skill
            print("Selección inválida.")

    def select_combat_item(self, player: Player) -> Optional[Item]:
        consumables = [item for item in player.inventory if isinstance(item, Item) and item.consumable]
        if not consumables:
            print("No tienes objetos utilizables ahora.")
            return None
        while True:
            print("Objetos disponibles (0 para cancelar):")
            for idx, item in enumerate(consumables, 1):
                print(f"[{idx}] {item.name} - {item.description}")
            choice = safe_input("Objeto: ")
            if choice is None or choice == "0":
                return None
            if choice.isdigit():
                index = int(choice) - 1
                if 0 <= index < len(consumables):
                    return consumables[index]
            print("Selección inválida.")

    def choose_enemy_skill(self, enemy: Enemy, player: Player) -> Optional[Skill]:
        available = [skill for skill in enemy.skills if enemy.stats.mp >= skill.mp_cost]
        if not available:
            return None
        status_targets = {
            skill
            for skill in available
            if skill.status
            and not any(effect.status == skill.status[0] for effect in player.status_effects)
        }
        if status_targets:
            return self.rng.choice(list(status_targets))
        if enemy.stats.hp < enemy.stats.hp_max * 0.5:
            return max(available, key=lambda s: s.base_power)
        return self.rng.choice(available)

    def build_shop_stock(self) -> None:
        base_stock: List[Equipment | Item] = [
            Equipment("Bastón Robusto", "Aumenta el poder mágico", "weapon", {"int_": 3}, 20),
            Equipment("Espada de Bronce", "Espada equilibrada para guerreros", "weapon", {"str": 3}, 22),
            Equipment("Daga Filoazul", "Ligera y precisa", "weapon", {"agi": 2, "str": 1}, 21),
            Equipment("Chaqueta de Cuero", "Armadura ligera resistente", "armor", {"def_": 3}, 18),
            Equipment("Amuleto de Maná", "Aumenta tu reserva de magia", "accessory", {"mp_max": 6}, 26),
        ]
        consumables: List[Equipment | Item] = [
            Item("Poción", "Recupera una parte de tu salud.", {"heal_percent": 40}, 10),
            Item("Éter", "Recupera parte de tu maná.", {"mp_percent": 40}, 12),
            Item("Antídoto", "Cura veneno.", {"cure": "POISON"}, 9),
            Item("Bomba", "Inflige daño explosivo.", {"damage": 30}, 18),
        ]
        rotation: List[Equipment | Item] = [
            Equipment("Cota de Escamas", "Protección media para aventureros.", "armor", {"def_": 5}, 34),
            Equipment("Anillo Veloz", "Incrementa la agilidad.", "accessory", {"agi": 2}, 28),
            Item("Panacea", "Remedio universal.", {"cure": "BURN"}, 14),
        ]
        stock = base_stock + consumables
        if self.testing:
            stock.extend(rotation[:1])
        else:
            for item in rotation:
                if roll_chance(self.rng, 0.5):
                    stock.append(item)
        self.shop_stock = stock

    def refresh_quest_board(self) -> None:
        selection = QUEST_BOARD_TEMPLATES[:]
        self.quest_board = []
        slots = 3 + (1 if self.day >= 6 else 0)
        while selection and len(self.quest_board) < slots:
            template = self.rng.choice(selection)
            selection.remove(template)
            required = template["required"] + min(2, self.day // 5)
            reward_exp = template["exp"] + self.day * 6
            reward_gold = template["gold"] + self.day * 4
            item_factory = template.get("item")
            reward_item = item_factory() if callable(item_factory) else None
            quest = Quest(
                name=template["name"],
                description=template["description"],
                objective_type="kill",
                target=template["target"],
                required=required,
                reward_exp=reward_exp,
                reward_gold=reward_gold,
                reward_item=reward_item,
            )
            self.quest_board.append(quest)

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
        for drop in enemy.drops:
            if roll_chance(self.rng, 0.45):
                loot = self.clone_item(drop)
                player.inventory.append(loot)
                if not self.testing:
                    print(self.style.success(f"Obtienes {loot.name}."))
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
            print(self.style.warning(f"{enemy.name} bebe una poción y recupera {amount} de HP."))
        elif "mp_percent" in item.effect:
            amount = int(enemy.stats.mp_max * item.effect["mp_percent"] / 100)
            enemy.stats.mp = clamp(enemy.stats.mp + amount, 0, enemy.stats.mp_max)
            print(self.style.warning(f"{enemy.name} recupera {amount} de MP."))

    def handle_shop(self) -> None:
        assert self.player is not None
        inventory = self.shop_stock
        print(self.style.title("=== TIENDA ==="))
        if not inventory:
            print("El escaparate está vacío por ahora.")
            self.state = State.EXPLORATION
            return
        for idx, item in enumerate(inventory, 1):
            detail = item.description
            if isinstance(item, Equipment):
                bonuses = ", ".join(f"{key.upper()} +{value}" for key, value in item.stat_bonuses.items())
                detail += f" ({bonuses})"
            else:
                detail += f" ({self.describe_item_effect(item)})"
            print(f"[{idx}] {item.name} - {item.price} oro :: {detail}")
        print("[0] Salir")
        choice = safe_input("> ")
        if choice is None or choice == "0":
            self.state = State.EXPLORATION
            return
        if choice.isdigit() and 1 <= int(choice) <= len(inventory):
            index = int(choice) - 1
            template = inventory[index]
            if self.player.stats.gold < template.price:
                print("No tienes suficiente oro.")
                return
            self.player.stats.gold -= template.price
            if isinstance(template, Equipment):
                purchased = self.clone_equipment(template)
                self.player.equip(purchased)
                inventory.pop(index)
                print(self.style.success(f"Equipas {template.name}."))
            else:
                purchased = self.clone_item(template)
                self.player.inventory.append(purchased)
                print(self.style.success(f"Compras {template.name}."))
            self.save_game()
        else:
            print("Opción no válida.")

    def shop_inventory(self) -> List[Equipment | Item]:
        return list(self.shop_stock)

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
        while True:
            print(self.style.title("=== MISIONES ==="))
            if not self.player.quests:
                print("No tienes misiones activas.")
            for quest in self.player.quests:
                status = "Completada" if quest.completed else f"{quest.progress}/{quest.required}"
                print(f"- {quest.name}: {quest.description} ({status})")
            location = self.game_map[self.player.position]
            if location.tile_type == TileType.TOWN and self.quest_board:
                print("\nTablón del gremio:")
                for idx, quest in enumerate(self.quest_board, 1):
                    print(
                        f"[{idx}] {quest.name} - {quest.description} "
                        f"(Objetivo: {quest.required} {quest.target})"
                    )
                print("[R]efrescar tablón (consume medio día)")
            print("[0] Volver")
            choice = safe_input("Acción: ")
            if choice is None or choice == "0":
                break
            if location.tile_type == TileType.TOWN and choice.lower() == "r":
                self.advance_time(3)
                self.refresh_quest_board()
                continue
            if location.tile_type == TileType.TOWN and choice.isdigit():
                index = int(choice) - 1
                if 0 <= index < len(self.quest_board):
                    template = self.quest_board[index]
                    if any(q.name == template.name and not q.completed for q in self.player.quests):
                        print("Ya tienes esta misión activa.")
                    else:
                        reward_item = (
                            self.clone_item(template.reward_item)
                            if template.reward_item
                            else None
                        )
                        new_quest = Quest(
                            name=template.name,
                            description=template.description,
                            objective_type=template.objective_type,
                            target=template.target,
                            required=template.required,
                            reward_exp=template.reward_exp,
                            reward_gold=template.reward_gold,
                            reward_item=reward_item,
                        )
                        self.player.quests.append(new_quest)
                        print(self.style.success(f"Aceptas la misión '{template.name}'."))
                        self.save_game()
                        self.quest_board.pop(index)
                else:
                    print("Selección inválida.")
            else:
                print("Debes estar en la ciudad para aceptar nuevas misiones.")
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
        state = GameState(
            self.state,
            self.player,
            self.game_map,
            self.discovered,
            self.day,
            self.turn_count,
            self.quest_board,
            self.shop_stock,
        )
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
        self.day = state.day
        self.turn_count = state.turn_count
        self.quest_board = state.quest_board or []
        self.shop_stock = state.shop_stock or []
        if not self.quest_board:
            self.refresh_quest_board()
        if not self.shop_stock:
            self.build_shop_stock()
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


QUEST_BOARD_TEMPLATES: List[Dict[str, object]] = [
    {
        "name": "Control de Slimes",
        "description": "Mantén la pradera limpia eliminando slimes cerca de la ciudad.",
        "target": "Slime",
        "required": 3,
        "exp": 50,
        "gold": 30,
        "item": lambda: Item("Poción", "Un extra del gremio.", {"heal_percent": 45}, 0),
    },
    {
        "name": "Caza de lobos",
        "description": "Los lobos están atacando caravanas al norte.",
        "target": "Lobo sombrío",
        "required": 3,
        "exp": 70,
        "gold": 45,
        "item": lambda: Item("Capa del cazador", "Mantiene el cuerpo caliente.", {"sell": 20}, 0, False),
    },
    {
        "name": "Patrulla de bandidos",
        "description": "Los caminos al oeste necesitan vigilancia constante.",
        "target": "Bandido",
        "required": 3,
        "exp": 80,
        "gold": 55,
        "item": lambda: Item("Bomba", "Explosivo reglamentario.", {"damage": 35}, 0),
    },
    {
        "name": "Purga de esqueletos",
        "description": "Las catacumbas emiten energía oscura.",
        "target": "Esqueleto",
        "required": 4,
        "exp": 90,
        "gold": 60,
        "item": lambda: Item("Éter", "Suministro arcano.", {"mp_percent": 50}, 0),
    },
    {
        "name": "Calmar espíritus",
        "description": "Los pescadores escuchan lamentos en el lago nocturno.",
        "target": "Espíritu del lago",
        "required": 2,
        "exp": 85,
        "gold": 58,
        "item": lambda: Item("Agua bendita", "Ahuyenta maldiciones.", {"cure": "POISON"}, 0),
    },
    {
        "name": "Dominar salamandras",
        "description": "Recupera el control de los respiraderos volcánicos de la cueva.",
        "target": "Salamandra",
        "required": 3,
        "exp": 95,
        "gold": 70,
        "item": lambda: Item("Escama cálida", "Material raro.", {"sell": 25}, 0, False),
    },
    {
        "name": "Derrotar al tirano",
        "description": "Acaba con el Tirano de la Cueva para abrir la ruta al este.",
        "target": "Tirano de la Cueva",
        "required": 1,
        "exp": 120,
        "gold": 120,
        "item": lambda: Item("Gema resonante", "Recuerdo del tirano.", {"sell": 60}, 0, False),
    },
]


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