"""
Entity system — Player and Mob instances with full stats, equipment, inventory.
"""
import json, random, time, math, hashlib
from .config import Config

cfg = Config()

class Stats:
    def __init__(self, base=None):
        self.base = base or {s: cfg.BASE_STAT for s in ["str","int","wis","dex","con","luc"]}
        self.modified = dict(self.base)
        self.temp = {s: 0 for s in self.base}
    
    def __getitem__(self, key):
        return self.base.get(key, 13) + self.temp.get(key, 0)
    
    def __setitem__(self, key, value):
        self.base[key] = max(3, min(cfg.MAX_STAT, value))
        self.refresh()
    
    def refresh(self):
        for k in self.base:
            self.modified[k] = self.base[k] + self.temp.get(k, 0)
    
    def to_dict(self):
        return {"base": dict(self.base), "temp": dict(self.temp)}
    
    @staticmethod
    def from_dict(d):
        s = Stats(d.get("base"))
        s.temp = d.get("temp", {k: 0 for k in s.base})
        return s

class Equipment:
    """Equipment slots for an entity."""
    def __init__(self):
        self.slots = {s: None for s in cfg.SLOTS}
    
    def equip(self, slot, item):
        if slot not in self.slots:
            return False
        self.slots[slot] = item
        return True
    
    def unequip(self, slot):
        item = self.slots.get(slot)
        self.slots[slot] = None
        return item
    
    def get(self, slot):
        return self.slots.get(slot)
    
    def is_empty(self, slot):
        return self.slots.get(slot) is None
    
    def all_equipped(self):
        return [item for item in self.slots.values() if item]
    
    def to_dict(self):
        result = {}
        for slot, item in self.slots.items():
            if item:
                result[slot] = item.to_dict() if hasattr(item, 'to_dict') else item
        return result
    
    @staticmethod
    def from_dict(d):
        e = Equipment()
        for slot, item_data in d.items():
            if slot in e.slots and item_data:
                from .entity import ItemInstance
                item = ItemInstance.from_dict(item_data) if isinstance(item_data, dict) else item_data
                e.slots[slot] = item
        return e

class Affect:
    """A temporary affect on an entity (buff/debuff)."""
    def __init__(self, name, attribute, bonus, duration, description=""):
        self.name = name
        self.attribute = attribute  # e.g. "hitroll", "armor", "str"
        self.bonus = bonus  # positive or negative modifier
        self.duration = duration  # in game ticks
        self.remaining = duration
        self.description = description
        self.affect_id = f"aff_{name}_{int(time.time()*1000)}"
    
    def tick(self):
        """Reduce duration. Returns True if expired."""
        self.remaining -= 1
        return self.remaining <= 0
    
    def apply(self, entity):
        """Apply the affect bonus to the entity."""
        if self.attribute in ("hitroll", "damroll", "armor"):
            pass  # Handled in _update_affect_bonuses
        elif self.attribute in ("str", "int", "wis", "dex", "con", "luc"):
            entity.stats.temp[self.attribute] = entity.stats.temp.get(self.attribute, 0) + self.bonus
            entity.stats.refresh()
    
    def remove(self, entity):
        """Remove the affect bonus from the entity."""
        if self.attribute in ("str", "int", "wis", "dex", "con", "luc"):
            entity.stats.temp[self.attribute] = entity.stats.temp.get(self.attribute, 0) - self.bonus
            entity.stats.refresh()

class Entity:
    """Base class for any game entity (player or mob)."""
    
    def __init__(self, entity_id=None):
        self.entity_id = entity_id or f"e_{int(time.time()*1000)}_{random.randint(0,99999)}"
        self.name = "Entity"
        self.short_desc = "an entity"
        self.long_desc = ""
        self.keywords = []
        self.room = None  # Room instance
        self.room_vnum = None  # Room vnum for persistence
        
        # Core stats
        self.stats = Stats()
        self.hp = cfg.BASE_HP
        self.max_hp = cfg.BASE_HP
        self.mana = cfg.BASE_MANA
        self.max_mana = cfg.BASE_MANA
        self.movement = 100
        self.max_movement = 100
        
        # Level
        self.level = 1
        self.xp = 0
        self.xp_to_level = cfg.xp_for_level(1)
        self.practices = 5
        self.trains = 0
        
        # Combat
        self.hitroll = cfg.BASE_HITROLL
        self.damroll = cfg.BASE_DAMROLL
        self.armor = 0
        self.alignment = 0
        self.wimpy = 0
        self.fighting = None  # entity_id of opponent
        self.combat_round = 0
        self.stunned = 0
        self.stance = "normal"
        
        # Inventory & equipment
        self.equipment = Equipment()
        self.inventory = []
        self.gold = 0
        self.weight = 0
        self.max_weight = 50
        
        # Skills
        self.skills = {}  # skill_name -> percentage
        self.skill_cooldowns = {}  # skill_name -> ready_time
        
        # Affects
        self.affects = {}  # affect_id -> Affect instance
        
        # State flags
        self.is_player = False
        self.is_mob = False
        self.is_pet = False
        self.owner_id = None
        self.fled = False
        self.position = "standing"  # standing, sitting, sleeping, fighting, stunned, dead
        
        # Tracking
        self.created_at = time.time()
        self.last_cmd_time = time.time()
        self.idle_time = 0
        
        # World reference (set when entering world)
        self.world = None
        
        # Save data
        self.save_data = {}
    
    @property
    def str(self): return self.stats["str"]
    @property
    def int(self): return self.stats["int"]
    @property
    def wis(self): return self.stats["wis"]
    @property
    def dex(self): return self.stats["dex"]
    @property
    def con(self): return self.stats["con"]
    @property
    def luc(self): return self.stats["luc"]
    
    def hitroll_total(self):
        """Calculate total hitroll."""
        hr = self.hitroll
        for item in self.equipment.all_equipped():
            hr += getattr(item, 'hitroll', 0) or 0
        return hr
    
    def damroll_total(self):
        """Calculate total damroll."""
        dr = self.damroll
        for item in self.equipment.all_equipped():
            dr += getattr(item, 'damroll', 0) or 0
        return dr
    
    def armor_total(self):
        """Calculate total armor."""
        ac = self.armor
        for item in self.equipment.all_equipped():
            ac += getattr(item, 'armor_class', 0) or 0
        return ac
    
    def weapon_damage(self):
        """Get weapon damage dice. Returns (min, max)."""
        weapon = self.equipment.get("main_hand")
        if weapon and hasattr(weapon, 'damage') and weapon.damage:
            return weapon.damage
        # Barehand
        return (1, 4)  # Unarmed damage
    
    def weapon_type(self):
        """Get weapon type."""
        weapon = self.equipment.get("main_hand")
        if weapon and hasattr(weapon, 'weapon_type'):
            return weapon.weapon_type
        return "fist"
    
    def get_skill(self, name):
        """Get skill percentage, 0 if not known."""
        return self.skills.get(name, 0)
    
    def has_skill(self, name):
        return self.skills.get(name, 0) > 0
    
    def skill_check(self, name):
        """Check if a skill succeeds. Returns True/False."""
        pct = self.get_skill(name)
        return pct > 0 and random.randint(1, 100) <= pct
    
    def can_use_skill(self, name):
        """Check if skill is off cooldown."""
        if name in self.skill_cooldowns:
            return time.time() >= self.skill_cooldowns[name]
        return True
    
    def use_skill(self, name):
        """Mark skill cooldown."""
        from .skills import get_skill_def
        skill = get_skill_def(name)
        cd = skill.cooldown if skill else 3
        self.skill_cooldowns[name] = time.time() + cd
    
    def add_affect(self, affect):
        """Add a temporary affect to the entity."""
        self.affects[affect.affect_id] = affect
    
    def remove_affect(self, affect_id):
        """Remove and clean up an affect."""
        affect = self.affects.pop(affect_id, None)
        if affect:
            affect.remove(self)
    
    def flee_combat(self):
        """Make the entity flee from combat."""
        if not self.fighting:
            return
        if self.world:
            room = self.world.rooms.get(self.room_vnum)
            if room and room.exits:
                import random
                exits = [d for d in room.exits if room.exits[d] and not (room.exits[d].door and room.exits[d].door.get("closed"))]
                if exits:
                    direction = random.choice(list(exits.keys()))
                    self.fighting = None
                    self.position = "standing"
                    target_vnum = exits[direction].target_room
                    self.world.move_entity(self, target_vnum)
                    if hasattr(self, 'send'):
                        self.send(f"\x1b[33mYou flee {direction}!\x1b[0m")
                    self.world.broadcast_to_room(self.room_vnum, f"{self.name} arrives, fleeing.", exclude=[self.entity_id] if hasattr(self, 'entity_id') else [])
    
    def calculate_attack(self, target):
        """Calculate attack outcome against a target."""
        hit = self.hitroll_total() + random.randint(1, 20)
        target_ac = target.armor_total()
        
        # Dodge check
        if random.random() < cfg.DODGE_BASE + (target.dex * 0.005):
            return {"hit": False, "dodge": True, "parry": False, "crit": False, "damage": 0, "msg": "dodges"}
        
        # Parry check
        if target.has_skill("parry") and target.skill_check("parry"):
            return {"hit": False, "dodge": False, "parry": True, "crit": False, "damage": 0, "msg": "parries"}
        
        # Hit check
        if hit <= target_ac:
            return {"hit": False, "dodge": False, "parry": False, "crit": False, "damage": 0, "msg": "misses"}
        
        # Damage
        dmin, dmax = self.weapon_damage()
        base_dam = random.randint(dmin, dmax) + self.damroll_total()
        
        # Critical hit
        crit = random.random() < cfg.CRIT_CHANCE
        if crit:
            base_dam = int(base_dam * cfg.CRIT_MULTIPLIER)
        
        # Apply target armor reduction
        reduction = int(base_dam * (target.armor_total() / 100.0))
        damage = max(1, base_dam - reduction)
        
        return {"hit": True, "dodge": False, "parry": False, "crit": crit,
                "damage": damage, "msg": "hits"}
    
    def take_damage(self, damage, attacker=None, damage_type="bash"):
        """Apply damage to this entity."""
        # Apply resistances
        resist_pct = 0
        if hasattr(self, 'resists'):
            resist_pct = self.resists.get(damage_type, 0) or 0
        # Apply weakness
        weakness_pct = 0
        if hasattr(self, 'weakness'):
            weakness_pct = self.weakness.get(damage_type, 0) or 0
        
        net_resist = resist_pct - weakness_pct
        damage = int(damage * (1.0 - net_resist/100.0))
        damage = max(1, damage)
        
        self.hp -= damage
        
        if self.hp <= 0:
            self.hp = 0
            self.die(attacker)
            return True  # dead
        
        return False  # alive
    
    def die(self, killer=None):
        """Handle entity death."""
        self.position = "dead"
        self.fighting = None
        
        if self.is_player:
            self.handle_player_death(killer)
        else:
            self.handle_mob_death(killer)
    
    def handle_player_death(self, killer):
        """Player death — lose gold, respawn at bind point."""
        gold_lost = int(self.gold * 0.15)
        self.gold -= gold_lost
        
        # Respawn at bind or starting room
        bind_vnum = self.save_data.get("bind_vnum", 3001)
        if self.world:
            self.world.move_entity(self, bind_vnum)
        
        self.hp = int(self.max_hp * 0.5)
        self.mana = int(self.max_mana * 0.5)
        self.position = "standing"
        
        if self.world:
            self.world.broadcast_to_room(self.room_vnum, 
                f"\x1b[31m{self.name} has been slain by {killer.name if killer else 'fate'}!\x1b[0m")
        self.send(f"\x1b[31mYou have been slain by {killer.name if killer else 'fate'}!\x1b[0m")
        self.send(f"\x1b[33mYou lose {gold_lost} gold coins.\x1b[0m")
    
    def handle_mob_death(self, killer):
        """Mob death — drop loot, give XP."""
        # Drop gold
        if self.gold > 0:
            drop_gold = random.randint(int(self.gold*0.5), self.gold)
            self.gold = 0
            if self.world and hasattr(self, 'template') and self.template:
                self.world.spawn_item_on_ground(self.room_vnum, "gold", drop_gold, f"{drop_gold} gold coins")
        
        # Drop loot from template
        if self.world and hasattr(self, 'template') and self.template:
            for loot_entry in self.template.loot_table:
                item_vnum, chance = loot_entry
                if random.random() * 100 < chance:
                    item_template = self.world.item_templates.get(item_vnum)
                    if item_template:
                        self.world.spawn_item_on_ground(self.room_vnum, item_template)
        
        # Drop inventory
        for item in self.inventory[:]:
            if self.world:
                self.world.remove_entity(item.entity_id)
                self.world.spawn_item_on_ground(self.room_vnum, item)
        
        # Give XP to killer
        if killer and hasattr(killer, 'is_player') and killer.is_player:
            xp_gain = int(self.get_xp_value())
            killer.gain_xp(xp_gain)
            killer.send(f"\x1b[33mYou receive {xp_gain} experience points.\x1b[0m")
            
            # Gold for killer too
            if self.gold > 0:
                killer.gold += self.gold
                killer.send(f"\x1b[33mYou receive {self.gold} gold coins.\x1b[0m")
        
        # Remove mob from world
        if self.world:
            self.world.remove_mob(self)
    
    def get_xp_value(self):
        """Calculate XP value of this entity."""
        base = 100 * self.level
        return max(10, int(base * cfg.XP_RATE))
    
    def gain_xp(self, amount):
        """Add XP and check for level up."""
        self.xp += amount
        while self.xp >= self.xp_to_level:
            self.level_up()
    
    def level_up(self):
        """Gain a level."""
        self.xp -= self.xp_to_level
        self.level += 1
        self.xp_to_level = cfg.xp_for_level(self.level)
        
        # Stat increases
        self.max_hp += int(cfg.HP_PER_LEVEL_BASE * cfg.CLASSES.get(self.save_data.get("class", "warrior"), {}).get("hp_factor", 1.0))
        self.max_mana += int(cfg.MANA_PER_LEVEL_BASE * cfg.CLASSES.get(self.save_data.get("class", "warrior"), {}).get("mana_factor", 1.0))
        self.hp = self.max_hp
        self.mana = self.max_mana
        
        self.practices += 3
        self.trains += cfg.STAT_POINTS_PER_LEVEL
        self.hitroll += 1
        self.damroll += 1
        
        self.send(f"\x1b[32m\x1b[1mYou raise a level! You are now level {self.level}!\x1b[0m")
        self.send(f"\x1b[33mHP: {self.max_hp}  Mana: {self.max_mana}  Practices: {self.practices}  Trains: {self.trains}\x1b[0m")
    
    def send(self, text):
        """Send text to this entity. Override for players."""
        pass
    
    def to_dict(self):
        result = {
            "name": self.name, "short_desc": self.short_desc, "level": self.level,
            "hp": self.hp, "max_hp": self.max_hp, "mana": self.mana, "max_mana": self.max_mana,
            "movement": self.movement, "max_movement": self.max_movement,
            "stats": self.stats.to_dict(),
            "xp": self.xp, "xp_to_level": self.xp_to_level,
            "practices": self.practices, "trains": self.trains,
            "hitroll": self.hitroll, "damroll": self.damroll,
            "armor": self.armor, "alignment": self.alignment, "wimpy": self.wimpy,
            "gold": self.gold, "room_vnum": self.room_vnum,
            "skills": dict(self.skills),
            "inventory": [item.to_dict() if hasattr(item, 'to_dict') else item for item in self.inventory],
            "equipment": self.equipment.to_dict(),
            "save_data": dict(self.save_data),
            "position": self.position,
        }
        if self.is_player:
            result["quests"] = {qid: qs.to_dict() for qid, qs in self.quests.items()}
            result["password_hash"] = self.password_hash
        return result

class Player(Entity):
    """A player character."""
    
    def __init__(self, entity_id=None):
        super().__init__(entity_id)
        self.is_player = True
        self.telnet = None  # TelnetHandler
        self.password_hash = ""
        self.email = ""
        self.created = time.time()
        self.last_login = time.time()
        self.total_playtime = 0
        self.room_history = []
        self.bind_vnum = 3001  # Starting room / recall point
        self.prompt_format = "[{hp}/{mhp}hp {mana}/{mmana}mn {mv}/{mmv}mv]"
        self.auto_exits = True
        self.brief = False
        self.pagelen = 0
        self.paging_buffer = []
        self.current_pager_page = 0
        
        # Builder/Admin flags
        self.is_builder = False
        self.is_admin = False
        
        # Quests
        self.quests = {}  # quest_id -> QuestState
        
        # Toggles
        self.toggles = {
            "autoloot": False, "autogold": False, "autosac": False,
            "combat_spam": False, "telnet_ga": True
        }
    
    def send(self, text):
        """Send text to the player via telnet."""
        if self.telnet:
            self.telnet.send(text + "\r\n")
    
    def send_ansi(self, code, text):
        if self.telnet:
            self.telnet.send_ansi(code, text)
    
    def prompt(self):
        """Send the player's prompt."""
        parts = {
            "hp": self.hp, "mhp": self.max_hp,
            "mana": self.mana, "mmana": self.max_mana,
            "mv": self.movement, "mmv": self.max_movement,
            "gold": self.gold, "tnl": self.xp_to_level - self.xp,
            "level": self.level, "align": self.alignment,
        }
        prompt = self.prompt_format
        for k, v in parts.items():
            prompt = prompt.replace("{" + k + "}", str(v))
        
        if self.fighting:
            enemy = self.world.entities.get(self.fighting) if self.world else None
            if enemy:
                enemy_hp_pct = int((enemy.hp / max(1, enemy.max_hp)) * 100)
                prompt = f"[Fighting: {prompt} Enemy: {enemy_hp_pct}%]"
        
        if self.telnet:
            self.telnet.prompt(prompt)
    
    def is_connected(self):
        return self.telnet is not None
    
    def disconnect(self):
        if self.telnet:
            self.telnet.close()
            self.telnet = None

class Mob(Entity):
    """A mob instance (spawned from a template)."""
    
    def __init__(self, template, entity_id=None):
        super().__init__(entity_id)
        self.is_mob = True
        self.template = template
        
        # Copy template data
        self.name = template.name
        self.short_desc = template.short_desc
        self.long_desc = template.long_desc
        self.keywords = list(template.keywords)
        self.level = template.level
        self.hp = template.hp
        self.max_hp = template.hp
        self.mana = template.mana
        self.max_mana = template.mana
        self.stats = Stats(dict(template.stats))
        self.hitroll = template.hitroll
        self.damroll = template.damroll
        self.armor = template.armor
        self.alignment = template.alignment
        self.xp = template.xp
        self.xp_to_level = 0  # Mobs don't level
        self.gold = template.gold
        self.resists = dict(template.resists)
        self.weakness = dict(template.weakness)
        self.faction = template.faction
        
        # AI state
        self.ai_state = "idle"  # idle, wander, hunt, combat, flee, return
        self.spawn_vnum = None  # Room where spawned
        self.home_vnum = None   # Room to return to
        self.wander_rooms = []  # Rooms in wander range
        self.agro_range = 3     # How far to pursue
        self.return_range = 20  # How far before returning home
        self.spec_proc = template.spec_proc
        self.dialogue = dict(template.dialogue)
        
        # Respawn timer
        self.respawn_delay = 60  # seconds before respawning
    
    def send(self, text):
        """Mobs don't receive text directly."""
        pass
    
    def die(self, killer=None):
        super().die(killer)
        # Schedule respawn
        if self.world and self.spawn_vnum:
            self.world.schedule_respawn(self.template.vnum, self.spawn_vnum, self.respawn_delay)

class ItemInstance:
    """An instance of an item in the game world (in a room, inventory, or equipment)."""
    
    def __init__(self, template, uid=None):
        self.uid = uid or f"i_{int(time.time()*1000)}_{random.randint(0,99999)}"
        self.template = template
        
        # Copy from template
        self.name = template.name
        self.short_desc = template.short_desc
        self.long_desc = template.long_desc
        self.keywords = list(template.keywords)
        self.item_type = template.item_type
        self.value = template.value
        self.weight = template.weight
        self.level = template.level
        self.flags = list(template.flags)
        self.weapon_type = template.weapon_type
        self.damage = tuple(template.damage) if template.damage else (0, 0)
        self.hitroll = template.hitroll
        self.damroll = template.damroll
        self.armor_class = template.armor_class
        self.slot = template.slot
        self.max_charges = template.max_charges
        self.current_charges = template.current_charges
        self.capacity = template.capacity
        self.full_value = template.full_value
        self.current_value = template.current_value
        self.hp_regen = template.hp_regen
        self.mana_regen = template.mana_regen
        self.spell = template.spell
        self.spell_level = template.spell_level
        
        # Instance-specific
        self.owner = None
        self.worn = False
        self.extra_data = {}
        self.inscription = ""
    
    def to_dict(self):
        return {
            "uid": self.uid, "template_vnum": self.template.vnum,
            "short_desc": self.short_desc, "item_type": self.item_type,
            "value": self.value, "weight": self.weight, "level": self.level,
            "flags": self.flags, "weapon_type": self.weapon_type,
            "damage": list(self.damage), "hitroll": self.hitroll,
            "damroll": self.damroll, "armor_class": self.armor_class,
            "slot": self.slot, "current_charges": self.current_charges,
            "current_value": self.current_value,
            "extra_data": self.extra_data, "inscription": self.inscription
        }
    
    @staticmethod
    def from_dict(d):
        # Create a minimal template to hold the data
        from .world import ItemTemplate
        t = ItemTemplate(d.get("template_vnum", 0), d.get("short_desc", d.get("name", "item")))
        t.short_desc = d.get("short_desc", "an item")
        t.item_type = d.get("item_type", "trash")
        t.value = d.get("value", 0)
        t.weight = d.get("weight", 1)
        t.level = d.get("level", 1)
        t.flags = d.get("flags", [])
        t.weapon_type = d.get("weapon_type", "sword")
        t.damage = tuple(d.get("damage", [0, 0]))
        t.hitroll = d.get("hitroll", 0)
        t.damroll = d.get("damroll", 0)
        t.armor_class = d.get("armor_class", 0)
        t.slot = d.get("slot")
        t.max_charges = d.get("max_charges", 0)
        t.current_charges = d.get("current_charges", 0)
        t.capacity = d.get("capacity", 0)
        t.full_value = d.get("full_value", 0)
        t.current_value = d.get("current_value", 0)
        t.hp_regen = d.get("hp_regen", 0)
        t.mana_regen = d.get("mana_regen", 0)
        t.spell = d.get("spell")
        t.spell_level = d.get("spell_level", 0)
        
        item = ItemInstance(t, d.get("uid"))
        item.extra_data = d.get("extra_data", {})
        item.inscription = d.get("inscription", "")
        return item
