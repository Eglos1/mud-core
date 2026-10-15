"""
MUD Configuration — all tunables in one place.
"""
from pathlib import Path

class Config:
    # Network
    HOST = "0.0.0.0"
    PORT = 4000
    MAX_PLAYERS = 256
    IDLE_TIMEOUT = 900  # 15 min
    
    # Directories
    DATA_DIR = Path(__file__).parent.parent / "data"
    WORLD_DIR = DATA_DIR / "world"
    PLAYER_DIR = DATA_DIR / "players"
    MOB_DIR = DATA_DIR / "mobs"
    
    # Combat
    BASE_HITROLL = 10
    BASE_DAMROLL = 5
    CRIT_CHANCE = 0.05
    CRIT_MULTIPLIER = 2.0
    DODGE_BASE = 0.05
    PARRY_BASE = 0.03
    
    # XP & Leveling
    XP_RATE = 1.0
    XP_PER_LEVEL_BASE = 1000
    XP_PER_LEVEL_MULT = 1.5
    
    def xp_for_level(self, level):
        return int(self.XP_PER_LEVEL_BASE * (self.XP_PER_LEVEL_MULT ** (level - 1)))
    
    # Stats
    MAX_STAT = 50
    BASE_STAT = 13
    STAT_POINTS_PER_LEVEL = 3
    
    # HP/Mana per level
    HP_PER_CON = 2
    MANA_PER_INT = 2
    BASE_HP = 50
    BASE_MANA = 50
    HP_PER_LEVEL_BASE = 10
    MANA_PER_LEVEL_BASE = 8
    
    # Equipment slots
    SLOTS = [
        "light", "head", "face", "ears", "neck", "shoulders",
        "back", "chest", "arms", "wrists", "hands", "finger_l",
        "finger_r", "waist", "legs", "feet", "main_hand", "off_hand",
        "ranged", "ammo"
    ]
    
    # Races
    RACES = {
        "human":  {"str": 13, "int": 13, "wis": 13, "dex": 13, "con": 13, "luc": 13, "desc": "Balanced in all things"},
        "elf":    {"str": 11, "int": 16, "wis": 14, "dex": 15, "con": 10, "luc": 12, "desc": "Graceful and magical"},
        "dwarf":  {"str": 16, "int": 10, "wis": 12, "dex": 11, "con": 17, "luc": 11, "desc": "Tough and stout"},
        "orc":    {"str": 18, "int": 8,  "wis": 9,  "dex": 12, "con": 16, "luc": 8,  "desc": "Brutal and strong"},
        "halfling": {"str": 9,  "int": 13, "wis": 11, "dex": 18, "con": 14, "luc": 16, "desc": "Quick and lucky"},
        "wolfen": {"str": 15, "int": 11, "wis": 12, "dex": 14, "con": 14, "luc": 11, "desc": "Feral hunters"},
        "undead": {"str": 14, "int": 14, "wis": 10, "dex": 10, "con": 12, "luc": 6,  "desc": "Cursed cursed souls"},
    }
    
    # Classes
    CLASSES = {
        "warrior":  {"hp_factor": 1.4, "mana_factor": 0.6, "skills": ["bash", "parry", "charge", "shield_block"]},
        "mage":     {"hp_factor": 0.7, "mana_factor": 1.6, "skills": ["fireball", "frost", "lightning", "teleport"]},
        "cleric":   {"hp_factor": 1.0, "mana_factor": 1.2, "skills": ["heal", "cure", "bless", "sanctuary"]},
        "rogue":    {"hp_factor": 1.1, "mana_factor": 0.9, "skills": ["backstab", "stealth", "pick_lock", "detect_trap"]},
        "ranger":   {"hp_factor": 1.2, "mana_factor": 0.8, "skills": ["bow", "track", "camouflage", "animal_companion"]},
        "paladin":  {"hp_factor": 1.3, "mana_factor": 0.9, "skills": ["smite", "lay_hands", "aura", "divine_shield"]},
        "druid":    {"hp_factor": 1.0, "mana_factor": 1.3, "skills": ["nature_heal", "summon_wolf", "entangle", "storm"]},
        "necromancer": {"hp_factor": 0.8, "mana_factor": 1.5, "skills": ["life_drain", "summon_undead", "curse", "fear"]},
        "monk":     {"hp_factor": 1.2, "mana_factor": 0.7, "skills": ["meditate", "flurry", "dodge", "kick"]},
        "bard":     {"hp_factor": 0.9, "mana_factor": 1.1, "skills": ["lore", "charm", "song_of_courage", "identify"]},
    }
    
    # Damage types
    DAMAGE_TYPES = ["pierce", "slash", "bash", "magic", "fire", "cold", "lightning", "poison", "psychic"]
    
    # Weapon types -> damage type
    WEAPON_DAMAGE = {
        "sword": "slash", "axe": "slash", "dagger": "pierce",
        "spear": "pierce", "staff": "bash", "mace": "bash",
        "bow": "pierce", "crossbow": "pierce", "whip": "slash",
        "polearm": "pierce", "club": "bash", "flail": "bash"
    }
    
    # Weather
    SEASONS = ["spring", "summer", "autumn", "winter"]
    WEATHER_TYPES = ["clear", "cloudy", "rain", "storm", "fog", "snow"]
    
    # Shops
    SHOP_MARKUP = 1.5     # sold items cost 1.5x base
    SHOP_DEMARKUP = 0.25  # sell for 25% of base
