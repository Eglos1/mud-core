"""
World model — rooms, exits, zones, mob/object templates, weather.
"""
import json, random, time, math, traceback
from pathlib import Path
from .config import Config

# Lazy imports (avoid circular deps with persist, entity, etc.)
_economy = None; _commands = None; _ai = None; _persist = None; _player = None; _item_instance = None
def _lazy_imports():
    global _economy, _commands, _ai, _persist, _player, _item_instance
    if _economy is None:
        from .economy import Economy as E
        from .commands import CommandHandler as C
        from .ai import MobAI as A, MobSpawner as S
        from .persist import Persistence as P
        from .entity import Player as Pl, Mob as Mo, ItemInstance as I
        _economy, _commands, _ai, _persist = E, C, A, S
        _player, _mob_cls, _item_instance = Pl, Mo, I
    P = _persist; _ai_spawner = _ai
    return _economy, _commands, _ai, _ai_spawner, _persist, _player, _mob_cls, _item_instance

class Exit:
    def __init__(self, direction, target_room, flags=None, desc=None, key=None, door=None):
        self.direction = direction  # north, south, east, west, up, down, etc.
        self.target_room = target_room
        self.flags = flags or []
        self.desc = desc or ""
        self.key = key
        self.door = door  # {name, closed, locked}
    
    def to_dict(self):
        return {
            "direction": self.direction,
            "target_room": self.target_room,
            "flags": self.flags,
            "desc": self.desc,
            "key": self.key,
            "door": self.door
        }
    
    @staticmethod
    def from_dict(d):
        return Exit(d["direction"], d["target_room"], d.get("flags"), d.get("desc"), d.get("key"), d.get("door"))

class Room:
    def __init__(self, vnum, name="Void", desc="Nothing here.", zone=None):
        self.vnum = vnum
        self.name = name
        self.desc = desc
        self.zone = zone
        self.exits = {}  # direction -> Exit
        self.sector = "city"  # city, forest, desert, water, mountain, etc.
        self.flags = []  # "indoors", "dark", "safe", "no_mob", "no_magic", etc.
        self.contents = []  # [entity_id, entity_id, ...]
        self.mobs = []  # [mob_id, mob_id, ...]
        self.items = []  # [item_id, item_id, ...]
        self.extra_descs = {}  # keyword -> text
        self.respawns = []  # [(mob_vnum, count, delay), ...]
        self.coord = None  # (x, y, z) for mapping
        self.owner = None  # player name for player housing
        self.note = ""
    
    def get_exit(self, direction):
        return self.exits.get(direction)
    
    def add_exit(self, direction, target_vnum, **kwargs):
        self.exits[direction] = Exit(direction, target_vnum, **kwargs)
    
    def remove_exit(self, direction):
        return self.exits.pop(direction, None)
    
    def describe(self, looker=None, brief=False):
        """Generate room description for a player."""
        lines = []
        lines.append(f"[{self.vnum}] {self.name}")
        
        if not brief:
            if self.sector != "city" and not any(f == "indoors" for f in self.flags):
                world_obj = getattr(looker, "world", None) if looker else None
                weather_line = ""
                if world_obj:
                    weather = getattr(world_obj, "weather", None)
                    if weather:
                        weather_line = f"\x1b[36m{weather.current_condition()}\x1b[0m "
                lines.append("  " + weather_line + self.desc)
            else:
                lines.append("  " + self.desc)
        
        # Exits
        exits_str = ", ".join(sorted(self.exits.keys()))
        if exits_str:
            lines.append(f"\x1b[33mExits: {exits_str}\x1b[0m")
        else:
            lines.append("\x1b[31mNo exits!\x1b[0m")
        
        # Contents
        if looker and hasattr(looker, "world") and looker.world:
            for entity_id in self.mobs:
                mob = looker.world.entities.get(entity_id)
                if mob and mob is not looker:
                    lines.append(f"\x1b[31m{mob.short_desc or 'Something'}\x1b[0m")
            for entity_id in self.items:
                item = looker.world.entities.get(entity_id)
                if item:
                    lines.append(f"\x1b[33m{item.short_desc or 'Something'}\x1b[0m")
        
        return "\r\n".join(lines)
    
    def to_dict(self):
        return {
            "vnum": self.vnum,
            "name": self.name,
            "desc": self.desc,
            "zone": self.zone,
            "exits": {d: e.to_dict() for d, e in self.exits.items()},
            "sector": self.sector,
            "flags": self.flags,
            "extra_descs": self.extra_descs,
            "respawns": self.respawns,
            "coord": self.coord,
            "owner": self.owner,
            "note": self.note
        }
    
    @staticmethod
    def from_dict(d):
        r = Room(d["vnum"], d.get("name", "Room"), d.get("desc", ""), d.get("zone"))
        for direc, edata in d.get("exits", {}).items():
            r.exits[direc] = Exit.from_dict(edata)
        r.sector = d.get("sector", "city")
        r.flags = d.get("flags", [])
        r.extra_descs = d.get("extra_descs", {})
        r.respawns = d.get("respawns", [])
        r.coord = d.get("coord")
        r.owner = d.get("owner")
        r.note = d.get("note", "")
        return r

class Zone:
    def __init__(self, name, low_vnum, hi_vnum):
        self.name = name
        self.low_vnum = low_vnum
        self.hi_vnum = hi_vnum
        self.rooms = {}
        self.flags = []
        self.topography = "plains"
        self.levels = (1, 10)
        self.owner = None
        # Respawn table: [(mob_vnum, chance, count, max_room_vnum), ...]
        self.respawn_table = []
        # Loot table: [(item_vnum, chance), ...]
        self.loot_table = []
    
    def add_room(self, room):
        self.rooms[room.vnum] = room
    
    def to_dict(self):
        return {
            "name": self.name,
            "low_vnum": self.low_vnum,
            "hi_vnum": self.hi_vnum,
            "flags": self.flags,
            "topography": self.topography,
            "levels": self.levels,
            "respawn_table": self.respawn_table,
            "loot_table": self.loot_table
        }
    
    @staticmethod
    def from_dict(d):
        z = Zone(d["name"], d["low_vnum"], d["hi_vnum"])
        z.flags = d.get("flags", [])
        z.topography = d.get("topography", "plains")
        z.levels = tuple(d.get("levels", (1, 10)))
        z.respawn_table = d.get("respawn_table", [])
        z.loot_table = d.get("loot_table", [])
        return z

class Weather:
    def __init__(self, world):
        self.world = world
        self.season = "spring"
        self.weather = "clear"
        self.temperature = 70
        self.humidity = 50
        self.wind = 5
        self.time = 0  # game hours
        self.day = 0
    
    def advance(self, hours=1):
        self.time += hours
        if self.time >= 24:
            self.time -= 24
            self.day += 1
        
        # Change season every 90 days
        season_idx = (self.day // 90) % 4
        self.season = ["spring", "summer", "autumn", "winter"][season_idx]
        
        # Random weather changes
        if random.random() < 0.1:
            self.weather = random.choice(["clear", "cloudy", "rain", "storm", "fog", "snow"])
            if self.season == "summer":
                self.temperature = random.randint(65, 95)
            elif self.season == "winter":
                self.temperature = random.randint(10, 40)
            elif self.season == "spring":
                self.temperature = random.randint(40, 70)
            else:
                self.temperature = random.randint(30, 60)
        
        self.humidity = random.randint(20, 90)
        self.wind = random.randint(0, 30)
    
    def current_condition(self):
        hour = self.time
        time_str = "night" if hour < 6 or hour >= 20 else ("morning" if hour < 12 else ("afternoon" if hour < 18 else "evening"))
        
        cond = self.weather
        if self.temperature > 90:
            cond += ", scorching"
        elif self.temperature < 32:
            cond += ", freezing"
        
        if self.wind > 20:
            cond += ", windy"
        
        return f"{time_str}, {self.season}, {cond}"
    
    def to_dict(self):
        return {"season": self.season, "weather": self.weather, 
                "temperature": self.temperature, "humidity": self.humidity,
                "time": self.time, "day": self.day}
    
    @staticmethod
    def from_dict(d, world):
        w = Weather(world)
        w.season = d.get("season", "spring")
        w.weather = d.get("weather", "clear")
        w.temperature = d.get("temperature", 70)
        w.humidity = d.get("humidity", 50)
        w.time = d.get("time", 0)
        w.day = d.get("day", 0)
        return w

class MobTemplate:
    """Template for a mob type — defines base stats and behavior."""
    def __init__(self, vnum, name):
        self.vnum = vnum
        self.name = name
        self.short_desc = name
        self.long_desc = ""
        self.keywords = []
        self.level = 1
        self.hp = 50
        self.mana = 50
        self.stats = {"str": 13, "int": 13, "wis": 13, "dex": 13, "con": 13, "luc": 13}
        self.hitroll = 5
        self.damroll = 3
        self.damage_type = "bash"
        self.armor = 0
        self.xp = 100
        self.gold = 0
        self.alignment = 0
        self.flags = []  # "aggressive", "wimpy", "undead", "sentinel"
        self.resists = {}
        self.weakness = {}
        self.skills = []
        self.loot_table = []
        self.equipment = {}
        self.inventory = []
        self.spec_proc = None  # Special procedure name
        self.dialogue = {}
        self.faction = None
        self.damage_strings = {
            "hits": "hits",
            "wounds": "wounds",
            "mauls": "mauls",
            "destroys": "DESTROYS",
        }
    
    def to_dict(self):
        return {
            "vnum": self.vnum, "name": self.name, "short_desc": self.short_desc,
            "long_desc": self.long_desc, "keywords": self.keywords,
            "level": self.level, "hp": self.hp, "mana": self.mana,
            "stats": self.stats, "hitroll": self.hitroll, "damroll": self.damroll,
            "damage_type": self.damage_type, "armor": self.armor,
            "xp": self.xp, "gold": self.gold, "alignment": self.alignment,
            "flags": self.flags, "resists": self.resists, "weakness": self.weakness,
            "skills": self.skills, "equipment": self.equipment,
            "inventory": self.inventory, "dialogue": self.dialogue,
            "faction": self.faction, "damage_strings": self.damage_strings
        }
    
    @staticmethod
    def from_dict(d):
        m = MobTemplate(d["vnum"], d["name"])
        for attr in ["short_desc", "long_desc", "keywords", "level", "hp", "mana",
                      "stats", "hitroll", "damroll", "damage_type", "armor",
                      "xp", "gold", "alignment", "flags", "resists", "weakness",
                      "skills", "equipment", "inventory", "dialogue", "faction",
                      "damage_strings"]:
            if attr in d:
                setattr(m, attr, d[attr])
        return m

class ItemTemplate:
    """Template for an item type."""
    def __init__(self, vnum, name):
        self.vnum = vnum
        self.name = name
        self.short_desc = name
        self.long_desc = ""
        self.keywords = []
        self.item_type = "trash"  # weapon, armor, container, potion, scroll, food, drink, light, etc.
        self.value = 0
        self.weight = 1
        self.level = 1
        self.flags = []  # "glow", "hum", "magic", "evil", "bless", "no_sell", "quest"
        
        # Weapon stats
        self.weapon_type = "sword"
        self.damage = (1, 6)  # (min, max) damage dice
        self.hitroll = 0
        self.damroll = 0
        
        # Armor stats
        self.armor_class = 0
        self.slot = None  # equipment slot
        self.max_charges = 0
        self.current_charges = 0
        
        # Container
        self.capacity = 0
        
        # Drink/Food
        self.full_value = 0
        self.current_value = 0
        
        # Food
        self.hp_regen = 0
        self.mana_regen = 0
        
        # Spell effect
        self.spell = None
        self.spell_level = 0
    
    def to_dict(self):
        return {
            "vnum": self.vnum, "name": self.name, "short_desc": self.short_desc,
            "long_desc": self.long_desc, "keywords": self.keywords,
            "item_type": self.item_type, "value": self.value, "weight": self.weight,
            "level": self.level, "flags": self.flags,
            "weapon_type": self.weapon_type, "damage": self.damage,
            "hitroll": self.hitroll, "damroll": self.damroll,
            "armor_class": self.armor_class, "slot": self.slot,
            "max_charges": self.max_charges, "current_charges": self.current_charges,
            "capacity": self.capacity,
            "full_value": self.full_value, "current_value": self.current_value,
            "hp_regen": self.hp_regen, "mana_regen": self.mana_regen,
            "spell": self.spell, "spell_level": self.spell_level
        }
    
    @staticmethod
    def from_dict(d):
        i = ItemTemplate(d["vnum"], d["name"])
        for attr in ["short_desc", "long_desc", "keywords", "item_type", "value", "weight",
                      "level", "flags", "weapon_type", "damage", "hitroll", "damroll",
                      "armor_class", "slot", "max_charges", "current_charges",
                      "capacity", "full_value", "current_value",
                      "hp_regen", "mana_regen", "spell", "spell_level"]:
            if attr in d:
                setattr(i, attr, d[attr])
        return i

class SkillDef:
    """Definition of a skill or spell."""
    def __init__(self, name, skill_type="skill"):
        self.name = name
        self.skill_type = skill_type  # skill, spell, combat_skill
        self.level = 1
        self.mana_cost = 0
        self.movement_cost = 0
        self.cooldown = 0  # rounds
        self.target = "offensive"  # offensive, defensive, self, room
        self.damage_type = None
        self.damage_dice = (0, 0)  # (num, size)
        self.hit_bonus = 0
        self.dam_bonus = 0
        self.duration = 0
        self.affects = {}  # stat_name -> amount
        self.desc_hit = ""
        self.desc_miss = ""
        self.weapon_required = None  # weapon type needed
        self.prereqs = []  # [(skill_name, level), ...]
        self.learn_every = 5  # practices per % learned
    
    def to_dict(self):
        return {
            "name": self.name, "skill_type": self.skill_type,
            "level": self.level, "mana_cost": self.mana_cost,
            "movement_cost": self.movement_cost, "cooldown": self.cooldown,
            "target": self.target, "damage_type": self.damage_type,
            "damage_dice": self.damage_dice, "hit_bonus": self.hit_bonus,
            "dam_bonus": self.dam_bonus, "duration": self.duration,
            "affects": self.affects, "desc_hit": self.desc_hit,
            "desc_miss": self.desc_miss, "weapon_required": self.weapon_required,
            "prereqs": self.prereqs, "learn_every": self.learn_every
        }
    
    @staticmethod
    def from_dict(d):
        s = SkillDef(d["name"], d.get("skill_type", "skill"))
        for attr in ["level", "mana_cost", "movement_cost", "cooldown", "target",
                      "damage_type", "damage_dice", "hit_bonus", "dam_bonus",
                      "duration", "affects", "desc_hit", "desc_miss",
                      "weapon_required", "prereqs", "learn_every"]:
            if attr in d:
                setattr(s, attr, d[attr])
        return s

class Shop:
    """Definition of a shop."""
    def __init__(self, vnum, name):
        self.vnum = vnum
        self.name = name
        self.keeper_vnum = None  # Mob vnum who runs the shop
        self.room_vnum = None
        self.products = []  # [item_vnum, ...] or None = buy anything
        self.buy_types = ["trash"]  # item types they buy
        self.markup = 1.5
        self.demarkup = 0.25
        self.no_sell_flags = []  # items with these flags can't be sold
        self.profit_cap = 1000000
    
    def to_dict(self):
        return {
            "vnum": self.vnum, "name": self.name,
            "keeper_vnum": self.keeper_vnum, "room_vnum": self.room_vnum,
            "products": self.products, "buy_types": self.buy_types,
            "markup": self.markup, "demarkup": self.demarkup,
            "no_sell_flags": self.no_sell_flags, "profit_cap": self.profit_cap
        }
    
    @staticmethod
    def from_dict(d):
        s = Shop(d["vnum"], d["name"])
        for attr in ["keeper_vnum", "room_vnum", "products", "buy_types",
                      "markup", "demarkup", "no_sell_flags", "profit_cap"]:
            if attr in d:
                setattr(s, attr, d[attr])
        return s
class World:
    """The game world — central hub holding all state."""
    
    def __init__(self, config=None):
        self.cfg = config or Config()
        self.rooms = {}       # vnum -> Room
        self.zones = {}       # name -> Zone
        self.entities = {}    # entity_id -> Entity (players + mobs + items)
        self.mobs = []        # list of active Mob instances
        self.players = []     # list of connected Player instances
        self.mob_templates = {}   # vnum -> MobTemplate
        self.item_templates = {}  # vnum -> ItemTemplate
        
        # Lazy-load to avoid circular imports
        from .economy import Economy
        from .commands import CommandHandler
        from .ai import MobAI, MobSpawner
        from .persist import Persistence
        
        self.weather = Weather(self)
        self.economy = Economy(self)
        self.commands = CommandHandler(self)
        self.mob_ai = MobAI(self)
        self.mob_spawner = MobSpawner(self)
        self.persist = Persistence(self)
        from .quests import QuestManager
        self.quest_manager = QuestManager(self)
        self.game_time = 0  # total game ticks
    
    async def load_all(self):
        """Load all world data."""
        await self.persist.load_world()
        
        # Initial mob spawns
        for zone in self.zones.values():
            for room in list(zone.rooms.values()):
                for template_vnum, count, delay in room.respawns:
                    for _ in range(count):
                        self.mob_spawner.spawn_mob(template_vnum, room.vnum)
        
        # Load quest definitions
        self.quest_manager.load_default_quests()
        
        # Ensure Darkwood Forest zone exists (for existing worlds)
        if "darkwood" not in self.zones:
            self._create_darkwood_zone()
        
        # Spawn some default mobs in hunting grounds
        self._spawn_default_mobs()
    
    def _spawn_default_mobs(self):
        """Spawn default mobs in appropriate rooms."""
        # Rats near city gates
        for _ in range(3):
            self.mob_spawner.spawn_mob(1, 3010)  # rat on road
        
        # Rabbits in forest
        for _ in range(3):
            self.mob_spawner.spawn_mob(2, 3020)  # rabbit at forest edge
        for _ in range(2):
            self.mob_spawner.spawn_mob(2, 3021)  # rabbit in forest
        
        # Snakes in forest
        for _ in range(2):
            self.mob_spawner.spawn_mob(3, 3021)
        
        # Goblins on road
        for _ in range(2):
            self.mob_spawner.spawn_mob(4, 3011)  # goblin at crossroads
        
        # Wolves in forest/hills
        for _ in range(2):
            self.mob_spawner.spawn_mob(5, 3022)  # wolf in clearing
        for _ in range(2):
            self.mob_spawner.spawn_mob(5, 3030)  # wolf in hills
        
        # Skeletons in cave
        for _ in range(3):
            self.mob_spawner.spawn_mob(6, 3041)  # skeleton in cave
        
        # Bandits on road
        for _ in range(2):
            self.mob_spawner.spawn_mob(7, 3010)  # bandit on road
        
        # Bear in hills
        self.mob_spawner.spawn_mob(8, 3031)  # bear on hilltop
        
        # ─── Quest Givers ───────────────────────────────────────────────
        self.mob_spawner.spawn_mob(10, 3001)  # Priest in Temple
        self.mob_spawner.spawn_mob(11, 3011)  # Explorer at Crossroads
        self.mob_spawner.spawn_mob(12, 3006)  # Captain at City Gates
        self.mob_spawner.spawn_mob(13, 3030)  # Hunter at Rolling Hills
        
        # ─── Darkwood Forest Spawns ─────────────────────────────────────
        if 3050 in self.rooms:  # Only if Darkwood zone exists
            for _ in range(3):
                self.mob_spawner.spawn_mob(14, 3051)  # spiders in web-filled glade
            for _ in range(2):
                self.mob_spawner.spawn_mob(15, 3053)  # treants in grove
            for _ in range(2):
                self.mob_spawner.spawn_mob(16, 3052)  # shaman in goblin camp
            for _ in range(2):
                self.mob_spawner.spawn_mob(17, 3055)  # stalkers in dark path
            self.mob_spawner.spawn_mob(18, 3056)  # wraith at ruined tower
            for _ in range(2):
                self.mob_spawner.spawn_mob(19, 3050)  # boars at forest entrance
    
    def _create_darkwood_zone(self):
        """Create the Darkwood Forest zone and connect it to the world."""
        darkwood_zone = Zone("Darkwood Forest", 3050, 3099)
        darkwood_zone.topography = "forest"
        darkwood_zone.levels = (4, 12)
        self.zones["darkwood"] = darkwood_zone
        
        # East from Whisperwood Path (3021) → Darkwood Forest Entrance (3050)
        r50 = Room(3050, "Darkwood Forest Entrance",
                   "The trees here tower overhead, their dark bark and dense canopy blocking out most of the sunlight. "
                   "An ancient, gnarled archway marks the entrance to the Darkwood. The air is cool and damp.",
                   "darkwood")
        r50.sector = "forest"
        r50.coord = (4, 6, 0)
        r50.desc = r50.desc  # keep the same
        
        r51 = Room(3051, "Web-Filled Glade",
                   "This clearing is strung with massive webs that glisten with dew. The skeletal remains of small "
                   "animals hang from the branches above. The ground is carpeted with dry leaves and bones.",
                   "darkwood")
        r51.sector = "forest"
        r51.coord = (5, 5, 0)
        r51.flags = ["dark"]
        
        r52 = Room(3052, "Goblin Camp",
                   "A crude encampment of hide tents and smoldering fires. The goblins here have set up a permanent "
                   "base, and the ground is littered with stolen goods and bones.",
                   "darkwood")
        r52.sector = "forest"
        r52.coord = (5, 7, 0)
        
        r53 = Room(3053, "Treant Grove",
                   "The trees here are enormous, their trunks wider than houses. Ancient faces are carved into the bark, "
                   "and the ground is thick with moss and ferns. A sense of ancient watchfulness fills the air.",
                   "darkwood")
        r53.sector = "forest"
        r53.coord = (3, 8, 0)
        
        r54 = Room(3054, "Murky Stream",
                   "A sluggish, dark-water stream cuts through the forest. The water is stained the color of tea by "
                   "decaying leaves. Strange bubbles rise to the surface.",
                   "darkwood")
        r54.sector = "water"
        r54.coord = (4, 9, 0)
        
        r55 = Room(3055, "Path of Shadows",
                   "The forest presses close here, the path barely wide enough for a single person. Twisted roots "
                   "reach across the trail like grasping fingers. The shadows seem to move on their own.",
                   "darkwood")
        r55.sector = "forest"
        r55.coord = (6, 6, 0)
        r55.flags = ["dark"]
        
        r56 = Room(3056, "Ruined Tower",
                   "An ancient stone tower lies in crumbling ruins at the heart of the Darkwood. Vines crawl up "
                   "the weathered stones, and an eerie blue light emanates from the broken doorway. The air hums "
                   "with residual magic.",
                   "darkwood")
        r56.sector = "forest"
        r56.coord = (7, 6, 0)
        r56.flags = ["dark", "indoors"]
        
        r57 = Room(3057, "Darkwood Heart",
                   "The deepest part of the forest. Five ancient standing stones form a circle around a pool of "
                   "perfectly still, black water. Nothing grows within the circle. The silence here is absolute.",
                   "darkwood")
        r57.sector = "forest"
        r57.coord = (5, 8, 0)
        r57.flags = ["dark", "no_mob"]
        
        # ─── Connect rooms ────────────────────────────────────────────
        # From Whisperwood Path (3021) east to Darkwood Entrance
        # Check if 3021 already has exits
        ww_path = self.rooms.get(3021)
        if ww_path:
            ww_path.add_exit("east", 3050)
        
        r50.add_exit("west", 3021)
        r50.add_exit("east", 3051)
        r50.add_exit("south", 3052)
        
        r51.add_exit("west", 3050)
        r51.add_exit("east", 3055)
        
        r52.add_exit("north", 3050)
        r52.add_exit("south", 3054)
        
        r53.add_exit("south", 3054)
        
        r54.add_exit("north", 3052)
        r54.add_exit("east", 3057)
        r54.add_exit("south", 3053)
        
        r55.add_exit("west", 3051)
        r55.add_exit("east", 3056)
        r55.add_exit("north", 3057)
        
        r56.add_exit("west", 3055)
        
        r57.add_exit("west", 3054)
        r57.add_exit("south", 3055)
        
        # Register all rooms
        for room in [r50, r51, r52, r53, r54, r55, r56, r57]:
            self.rooms[room.vnum] = room
            darkwood_zone.add_room(room)
        
        print(f"Created Darkwood Forest zone with {len([r50, r51, r52, r53, r54, r55, r56, r57])} rooms.")
    
    async def save_all(self):
        """Save all world data."""
        for player in self.players:
            self.save_player(player)
        await self.persist.save_world()
    
    def save_player(self, player):
        """Save a player's data."""
        self.persist.save_player(player)
    
    def add_player(self, player):
        """Add a player to the world."""
        if player not in self.players:
            self.players.append(player)
        self.entities[player.entity_id] = player
        
        # Add to room
        self._add_to_room(player, player.room_vnum)
    
    def remove_player(self, player):
        """Remove a player from the world."""
        if player in self.players:
            self.players.remove(player)
        self.entities.pop(player.entity_id, None)
        
        # Remove from room
        if player.room_vnum:
            room = self.rooms.get(player.room_vnum)
            if room and player.entity_id in room.contents:
                room.contents.remove(player.entity_id)
        
        player.disconnect()
    
    def add_mob(self, mob):
        """Add a mob to the world."""
        self.mobs.append(mob)
        self.entities[mob.entity_id] = mob
    
    def remove_mob(self, mob):
        """Remove a mob from the world."""
        if mob in self.mobs:
            self.mobs.remove(mob)
        self.entities.pop(mob.entity_id, None)
        
        # Remove from room
        if mob.room_vnum:
            room = self.rooms.get(mob.room_vnum)
            if room and mob.entity_id in room.mobs:
                room.mobs.remove(mob.entity_id)
    
    def move_entity(self, entity, target_vnum):
        """Move an entity to a different room."""
        # Remove from old room
        if entity.room_vnum:
            old_room = self.rooms.get(entity.room_vnum)
            if old_room:
                if entity.entity_id in old_room.contents:
                    old_room.contents.remove(entity.entity_id)
                if entity.entity_id in old_room.mobs and entity.is_mob:
                    old_room.mobs.remove(entity.entity_id)
        
        # Add to new room
        entity.room_vnum = target_vnum
        self._add_to_room(entity, target_vnum)
    
    def _add_to_room(self, entity, vnum):
        """Add an entity to a room's contents."""
        room = self.rooms.get(vnum)
        if not room:
            return
        if entity.entity_id not in room.contents:
            room.contents.append(entity.entity_id)
        if entity.is_mob and entity.entity_id not in room.mobs:
            room.mobs.append(entity.entity_id)
    
    def spawn_item_on_ground(self, room_vnum, item_or_template, count=1, custom_name=None):
        """Spawn an item on the ground in a room."""
        from .entity import ItemInstance
        # ItemTemplate is defined in this module
        
        room = self.rooms.get(room_vnum)
        if not room:
            return None
        
        if isinstance(item_or_template, ItemTemplate):
            item = ItemInstance(item_or_template)
        elif isinstance(item_or_template, str) and item_or_template == "gold":
            # Special gold handling
            item = ItemInstance(None)
            item.name = f"{count} gold coins"
            item.short_desc = f"{count} gold coins"
            item.item_type = "gold"
            item.value = count
            item.weight = 0.01 * count
            item.extra_data["count"] = count
        else:
            return None
        
        if custom_name:
            item.short_desc = custom_name
        
        self.entities[item.uid] = item
        room.items.append(item.uid)
        return item
    
    def broadcast_to_room(self, room_vnum, message, exclude=None):
        """Send a message to all players in a room."""
        if exclude is None:
            exclude = []
        room = self.rooms.get(room_vnum)
        if not room:
            return
        for eid in room.contents:
            if eid in exclude:
                continue
            entity = self.entities.get(eid)
            if entity and entity.is_player and entity.is_connected():
                entity.send(message)
    
    def find_entity(self, name):
        """Find a player by name (case-insensitive)."""
        name_lower = name.lower()
        for p in self.players:
            if p.is_connected() and p.name.lower() == name_lower:
                return p
        return None
    
    async def game_tick(self):
        """Main game loop — runs every second."""
        self.game_time += 1
        
        # Advance weather every 10 ticks (10 seconds = 1 game hour)
        if self.game_time % 10 == 0:
            self.weather.advance(1)
        
        # Tick combat every 2 seconds
        if self.game_time % 2 == 0:
            await self.commands.combat.tick_combat()
        
        # Tick mob AI every 3 seconds
        if self.game_time % 3 == 0:
            await self.mob_ai.tick()
        
        # Tick mob spawner every 5 seconds
        if self.game_time % 5 == 0:
            await self.mob_spawner.tick()
        
        # Process affects for all entities every tick
        for entity in list(self.entities.values()):
            if hasattr(entity, 'affects') and entity.affects:
                expired = []
                for aff_id, aff in entity.affects.items():
                    if aff.tick():
                        expired.append(aff_id)
                for aff_id in expired:
                    aff = entity.affects.pop(aff_id, None)
                    if aff:
                        aff.remove(entity)
                        if hasattr(entity, 'send'):
                            entity.send(f"\x1b[33mYour {aff.name} fades.\x1b[0m")
        
        # Regen for all players every tick
        for player in self.players:
            if player.is_connected() and player.hp > 0:
                self._regen_player(player)
                # Wimpy check
                if player.wimpy > 0 and player.hp < player.wimpy and player.fighting:
                    self.commands._move_player(player, None, dest_vnum=getattr(player, "bind_vnum", 3001))
                    player.send(f"\x1b[33mYou flee from combat in terror! (wimpy)\x1b[0m")
        
        # Save all players every 60 seconds
        if self.game_time % 60 == 0:
            for player in self.players:
                if player.is_connected():
                    self.save_player(player)
        
        # Send prompts every 2 ticks
        if self.game_time % 2 == 0:
            for player in self.players:
                if player.is_connected() and player.hp > 0:
                    player.prompt()
    
    def _regen_player(self, player):
        """Regenerate HP, mana, and movement for a player."""
        # Base regen
        hp_regen = 1 + (player.con // 4)
        mp_regen = 1 + (player.int // 4)
        mv_regen = 1 + (player.dex // 4)
        
        # Position multiplier
        pos_mult = {"sleeping": 3, "sitting": 2, "resting": 2, "standing": 1, "fighting": 0.5}
        mult = pos_mult.get(player.position, 1)
        
        hp_regen = int(hp_regen * mult)
        mp_regen = int(mp_regen * mult)
        
        player.hp = min(player.max_hp, player.hp + hp_regen)
        player.mana = min(player.max_mana, player.mana + mp_regen)
        player.movement = min(player.max_movement, player.movement + mv_regen)
        
        # Natural healing bonus when sitting
        if player.position == "sitting" or player.position == "sleeping":
            player.hp = min(player.max_hp, player.hp + hp_regen)
        
        # Check for death timeout
        if player.hp <= 0:
            # Dead players slowly recover
            pass



