"""
Persistence layer — JSON-based save/load for world data and players.
"""
import json, os, time, hashlib, secrets, random
from pathlib import Path
from .config import Config
from .world import Zone, Room, MobTemplate, ItemTemplate, Shop

cfg = Config()

class Persistence:
    def __init__(self, world):
        self.world = world
    
    # ─── World Data ─────────────────────────────────────────────────
    
    async def load_world(self):
        """Load all world data from JSON files."""
        await self.load_zones()
        await self.load_mob_templates()
        await self.load_item_templates()
        await self.load_shops()
    
    async def save_world(self):
        """Save all world data to JSON files."""
        await self.save_zones()
        await self.save_mob_templates()
        await self.save_item_templates()
        await self.save_shops()
    
    async def load_zones(self):
        """Load zones and their rooms."""
        zones_file = cfg.WORLD_DIR / "zones.json"
        if not zones_file.exists():
            self._create_default_world()
            return
        
        with open(zones_file) as f:
            data = json.load(f)
        
        self.world.zones.clear()
        self.world.rooms.clear()
        
        for zdata in data.get("zones", []):
            zone = Zone.from_dict(zdata)
            self.world.zones[zone.name] = zone
        
        for rdata in data.get("rooms", []):
            room = Room.from_dict(rdata)
            self.world.rooms[room.vnum] = room
            zone = self.world.zones.get(room.zone)
            if zone:
                zone.add_room(room)
    
    async def save_zones(self):
        """Save zones and rooms."""
        data = {
            "zones": [z.to_dict() for z in self.world.zones.values()],
            "rooms": [r.to_dict() for r in self.world.rooms.values()]
        }
        with open(cfg.WORLD_DIR / "zones.json", "w") as f:
            json.dump(data, f, indent=2)
    
    async def load_mob_templates(self):
        """Load mob templates."""
        mobs_file = cfg.MOB_DIR / "mobs.json"
        if not mobs_file.exists():
            self._create_default_mobs()
            return
        
        with open(mobs_file) as f:
            data = json.load(f)
        
        self.world.mob_templates.clear()
        for mdata in data:
            mob = MobTemplate.from_dict(mdata)
            self.world.mob_templates[mob.vnum] = mob
    
    async def save_mob_templates(self):
        """Save mob templates."""
        data = [m.to_dict() for m in self.world.mob_templates.values()]
        with open(cfg.MOB_DIR / "mobs.json", "w") as f:
            json.dump(data, f, indent=2)
    
    async def load_item_templates(self):
        """Load item templates."""
        items_file = cfg.WORLD_DIR / "items.json"
        if not items_file.exists():
            self._create_default_items()
            return
        
        with open(items_file) as f:
            data = json.load(f)
        
        self.world.item_templates.clear()
        for idata in data:
            item = ItemTemplate.from_dict(idata)
            self.world.item_templates[item.vnum] = item
    
    async def save_item_templates(self):
        """Save item templates."""
        data = [i.to_dict() for i in self.world.item_templates.values()]
        with open(cfg.WORLD_DIR / "items.json", "w") as f:
            json.dump(data, f, indent=2)
    
    async def load_shops(self):
        """Load shops."""
        shops_file = cfg.WORLD_DIR / "shops.json"
        if not shops_file.exists():
            return
        
        with open(shops_file) as f:
            data = json.load(f)
        
        self.world.economy.shops.clear()
        for sdata in data:
            shop = Shop.from_dict(sdata)
            self.world.economy.shops[shop.vnum] = shop
    
    async def save_shops(self):
        """Save shops."""
        data = [s.to_dict() for s in self.world.economy.shops.values()]
        with open(cfg.WORLD_DIR / "shops.json", "w") as f:
            json.dump(data, f, indent=2)
    
    # ─── Player Data ────────────────────────────────────────────────
    
    def load_player(self, name):
        """Load a player's save file."""
        name_lower = name.lower()
        player_file = cfg.PLAYER_DIR / f"{name_lower}.json"
        if not player_file.exists():
            return None
        
        with open(player_file) as f:
            data = json.load(f)
        return data
    
    def save_player(self, player):
        """Save a player's data to their save file."""
        data = player.to_dict()
        name_lower = player.name.lower()
        player_file = cfg.PLAYER_DIR / f"{name_lower}.json"
        
        with open(player_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def player_exists(self, name):
        """Check if a player save exists."""
        name_lower = name.lower()
        return (cfg.PLAYER_DIR / f"{name_lower}.json").exists()
    
    def hash_password(self, password):
        """Hash a password with a random salt."""
        salt = secrets.token_hex(16)
        h = hashlib.sha256((salt + password).encode()).hexdigest()
        return f"{salt}:{h}"
    
    def check_password(self, password, stored):
        """Check a password against stored hash."""
        try:
            salt, h = stored.split(":", 1)
            check = hashlib.sha256((salt + password).encode()).hexdigest()
            return h == check
        except:
            return False
    
    def create_player(self, name, password, race, cls):
        """Create a new player character."""
        from .entity import Player, Stats
        from .skills import init_player_skills
        
        player = Player()
        player.name = name
        player.short_desc = name
        player.password_hash = self.hash_password(password)
        player.save_data["race"] = race
        player.save_data["class"] = cls
        player.save_data["bind_vnum"] = 3001
        
        # Apply racial bonuses
        race_data = cfg.RACES.get(race, cfg.RACES["human"])
        for stat, val in race_data.items():
            if stat in ("str", "int", "wis", "dex", "con", "luc"):
                player.stats[stat] = val
        
        # Class modifiers
        cls_data = cfg.CLASSES.get(cls, cfg.CLASSES["warrior"])
        player.max_hp = int(cfg.BASE_HP * cls_data["hp_factor"])
        player.max_mana = int(cfg.BASE_MANA * cls_data["mana_factor"])
        player.hp = player.max_hp
        player.mana = player.max_mana
        
        # Starting skills
        init_player_skills(player, cls)
        
        # Starting equipment
        self._give_starting_gear(player, cls)
        
        # Starting location
        player.room_vnum = 3001  # Temple of Aylor
        
        return player
    
    def _give_starting_gear(self, player, cls):
        """Give a new player their starting equipment."""
        from .entity import ItemInstance
        from .world import ItemTemplate
        
        # All classes get a simple weapon
        if cls in ("mage", "cleric"):
            wpn = ItemTemplate(1001, "a wooden staff")
            wpn.short_desc = "a wooden staff"
            wpn.item_type = "weapon"
            wpn.weapon_type = "staff"
            wpn.damage = (1, 6)
            wpn.hitroll = 2
            wpn.keywords = ["staff", "wooden", "wooden staff"]
        elif cls in ("rogue", "ranger", "bard"):
            wpn = ItemTemplate(1002, "a sharp dagger")
            wpn.short_desc = "a sharp dagger"
            wpn.item_type = "weapon"
            wpn.weapon_type = "dagger"
            wpn.damage = (1, 6)
            wpn.hitroll = 3
            wpn.keywords = ["dagger", "sharp", "sharp dagger"]
        else:
            wpn = ItemTemplate(1003, "a sturdy sword")
            wpn.short_desc = "a sturdy sword"
            wpn.item_type = "weapon"
            wpn.weapon_type = "sword"
            wpn.damage = (2, 6)
            wpn.hitroll = 3
            wpn.damroll = 2
            wpn.keywords = ["sword", "sturdy", "sturdy sword"]
        
        # Set keyword so items work correctly
        wpn.keywords = wpn.keywords or [wpn.name.split()[-1]]
        player.inventory.append(ItemInstance(wpn))
        
        # Light source
        torch = ItemTemplate(1004, "a torch")
        torch.short_desc = "a torch"
        torch.item_type = "light"
        torch.flags = ["light"]
        torch.keywords = ["torch"]
        player.inventory.append(ItemInstance(torch))
        
        # Gold
        player.gold = 50
    
    def restore_player_from_data(self, data, player=None):
        """Restore a player object from saved data."""
        from .entity import Player, Stats
        if player is None:
            player = Player()
        
        player.name = data.get("name", "Player")
        player.short_desc = data.get("short_desc", player.name)
        player.level = data.get("level", 1)
        player.hp = data.get("hp", 50)
        player.max_hp = data.get("max_hp", 50)
        player.mana = data.get("mana", 50)
        player.max_mana = data.get("max_mana", 50)
        player.movement = data.get("movement", 100)
        player.max_movement = data.get("max_movement", 100)
        player.xp = data.get("xp", 0)
        player.xp_to_level = data.get("xp_to_level", 1000)
        player.practices = data.get("practices", 5)
        player.trains = data.get("trains", 0)
        player.hitroll = data.get("hitroll", 10)
        player.damroll = data.get("damroll", 5)
        player.armor = data.get("armor", 0)
        player.alignment = data.get("alignment", 0)
        player.gold = data.get("gold", 0)
        player.room_vnum = data.get("room_vnum", 3001)
        player.position = data.get("position", "standing")
        
        if "stats" in data:
            player.stats = Stats.from_dict(data["stats"])
        
        # Restore skills
        player.skills.update(data.get("skills", {}))
        
        # Restore equipment
        if "equipment" in data:
            from .entity import Equipment
            player.equipment = Equipment.from_dict(data["equipment"])
        
        # Restore inventory
        for item_data in data.get("inventory", []):
            from .entity import ItemInstance
            item = ItemInstance.from_dict(item_data)
            player.inventory.append(item)
        
        player.save_data = dict(data.get("save_data", {}))
        player.password_hash = data.get("password_hash", "")
        
        # Restore quests
        from .quests import QuestState
        quests_data = data.get("quests", {})
        for qid, qs_data in quests_data.items():
            player.quests[qid] = QuestState.from_dict(qs_data)
        
        return player
    
    def _create_default_world(self):
        """Create the default starting world if no data exists."""
        # Temple zone
        temple_zone = Zone("Temple of Aylor", 3000, 3099)
        temple_zone.topography = "city"
        temple_zone.levels = (1, 10)
        self.world.zones["temple"] = temple_zone
        
        # Temple room (starting room)
        r1 = Room(3001, "Temple of Aylor",
                  "You stand in the grand Temple of Aylor. Marble pillars rise toward a vaulted ceiling painted with celestial scenes. A warm light emanates from the altar at the center.",
                  "temple")
        r1.sector = "city"
        r1.flags = ["safe", "indoors"]
        r1.coord = (0, 0, 0)
        
        # Temple courtyard
        r2 = Room(3002, "Temple Courtyard",
                  "A peaceful courtyard surrounds the temple. Flowering bushes line the stone paths. The city gates lie to the south.",
                  "temple")
        r2.sector = "city"
        r2.coord = (0, 1, 0)
        
        # City square
        r3 = Room(3003, "City Square",
                  "The central square of Aylor is bustling with activity. Market stalls line the edges of the cobblestone plaza. Streets lead in all directions.",
                  "temple")
        r3.sector = "city"
        r3.coord = (0, 2, 0)
        
        # Connect rooms
        r1.add_exit("south", 3002)
        r2.add_exit("north", 3001)
        r2.add_exit("south", 3003)
        r3.add_exit("north", 3002)
        r3.add_exit("east", 3004)
        r3.add_exit("west", 3005)
        r3.add_exit("south", 3006)
        
        # Shop
        r4 = Room(3004, "General Store",
                  "Shelves line the walls of this small shop, filled with various goods. A friendly shopkeeper stands behind the counter.",
                  "temple")
        r4.sector = "city"
        r4.flags = ["indoors", "safe"]
        r4.coord = (1, 2, 0)
        
        # Blacksmith
        r5 = Room(3005, "Blacksmith",
                  "The heat of the forge washes over you as you enter. Weapons and armor hang on the walls. The blacksmith hammers away at an anvil.",
                  "temple")
        r5.sector = "city"
        r5.flags = ["indoors", "safe"]
        r5.coord = (-1, 2, 0)
        
        # City gates (leads to the road)
        r6 = Room(3006, "City Gates",
                  "Large iron-bound wooden doors mark the entrance to Aylor. The road beyond stretches south into the wilderness.",
                  "temple")
        r6.sector = "city"
        r6.coord = (0, 3, 0)
        
        # ---- Hunting Grounds ----
        
        # Road
        r7 = Room(3010, "The Great North Road",
                  "A well-traveled road stretches north-south through gently rolling hills. Fields of wildflowers sway in the breeze.",
                  "temple")
        r7.sector = "plains"
        r7.coord = (0, 4, 0)
        
        r8 = Room(3011, "Crossroads",
                  "The road intersects with a smaller path here. A weathered signpost points in several directions.",
                  "temple")
        r8.sector = "plains"
        r8.coord = (0, 5, 0)
        
        # Forest entrance
        r9 = Room(3020, "Edge of the Whisperwood",
                  "The trees here are tall and ancient, their branches intertwining overhead to create a dappled canopy. The path leads deeper into the forest.",
                  "temple")
        r9.sector = "forest"
        r9.coord = (2, 5, 0)
        
        r10 = Room(3021, "Whisperwood Path",
                   "Sunlight filters through the leaves, creating shifting patterns on the forest floor. You hear rustling in the underbrush.",
                   "temple")
        r10.sector = "forest"
        r10.coord = (2, 6, 0)
        
        r11 = Room(3022, "Forest Clearing",
                   "A peaceful clearing where a small stream babbles over smooth stones. Deer tracks are visible in the soft earth.",
                   "temple")
        r11.sector = "forest"
        r11.coord = (3, 6, 0)
        
        # Western hills
        r12 = Room(3030, "Rolling Hills",
                   "Gentle green hills stretch as far as the eye can see. A cool breeze carries the scent of wild thyme.",
                   "temple")
        r12.sector = "hills"
        r12.coord = (-2, 5, 0)
        
        r13 = Room(3031, "Hilltop",
                   "From this vantage point you can see the spires of Aylor to the north and the dark line of the Whisperwood to the east.",
                   "temple")
        r13.sector = "hills"
        r13.coord = (-2, 6, 0)
        
        # Dark cave
        r14 = Room(3040, "Cave Entrance",
                   "A dark opening in the hillside, partially hidden by overgrown bushes. A chill emanates from within.",
                   "temple")
        r14.sector = "mountain"
        r14.flags = ["dark"]
        r14.coord = (-3, 7, 0)
        
        r15 = Room(3041, "Cave Passage",
                   "The tunnel winds deeper into the earth. Water drips from the ceiling, and strange echoes bounce off the walls.",
                   "temple")
        r15.sector = "underdark"
        r15.flags = ["dark"]
        r15.coord = (-3, 8, 0)
        
        # Connect roads
        r6.add_exit("south", 3010)
        r7.add_exit("north", 3006)
        r7.add_exit("south", 3011)
        r8.add_exit("north", 3010)
        r8.add_exit("east", 3020)
        r8.add_exit("west", 3030)
        r9.add_exit("west", 3011)
        r9.add_exit("east", 3021)
        r10.add_exit("west", 3020)
        r10.add_exit("north", 3022)
        r11.add_exit("south", 3021)
        r12.add_exit("east", 3011)
        r12.add_exit("west", 3031)
        r13.add_exit("east", 3030)
        r13.add_exit("west", 3040)
        r14.add_exit("east", 3031)
        r14.add_exit("south", 3041)
        r15.add_exit("north", 3040)
        
        # Register all rooms and add to zone
        for room in [r1, r2, r3, r4, r5, r6, r7, r8, r9, r10, r11, r12, r13, r14, r15]:
            self.world.rooms[room.vnum] = room
            temple_zone.add_room(room)
        
        # Save synchronously
        self._save_zones_sync()
    
    def _create_default_mobs(self):
        """Create default mob templates."""
        templates = []
        
        # Rat
        rat = MobTemplate(1, "a giant rat")
        rat.short_desc = "a giant rat"
        rat.long_desc = "A mangy rat the size of a dog, with yellow teeth and beady red eyes."
        rat.keywords = ["rat", "giant", "giant rat"]
        rat.level = 1
        rat.hp = 25
        rat.mana = 10
        rat.stats = {"str": 8, "int": 4, "wis": 4, "dex": 12, "con": 10, "luc": 6}
        rat.hitroll = 3
        rat.damroll = 1
        rat.damage_type = "pierce"
        rat.armor = 3
        rat.xp = 60
        rat.gold = random.randint(1, 5)
        rat.flags = []
        templates.append(rat)
        
        # Rabbit
        rabbit = MobTemplate(2, "a rabbit")
        rabbit.short_desc = "a rabbit"
        rabbit.long_desc = "A small, fluffy rabbit with twitching nose and long ears."
        rabbit.keywords = ["rabbit", "bunny"]
        rabbit.level = 1
        rabbit.hp = 15
        rabbit.mana = 5
        rabbit.stats = {"str": 5, "int": 3, "wis": 5, "dex": 15, "con": 8, "luc": 10}
        rabbit.hitroll = 2
        rabbit.damroll = 1
        rabbit.damage_type = "bash"
        rabbit.armor = 5
        rabbit.xp = 40
        rabbit.gold = 0
        rabbit.flags = ["wimpy"]
        templates.append(rabbit)
        
        # Snake
        snake = MobTemplate(3, "a garden snake")
        snake.short_desc = "a garden snake"
        snake.long_desc = "A slender green snake with dark markings along its back."
        snake.keywords = ["snake", "garden", "garden snake"]
        snake.level = 2
        snake.hp = 30
        snake.mana = 15
        snake.stats = {"str": 7, "int": 3, "wis": 5, "dex": 14, "con": 10, "luc": 8}
        snake.hitroll = 5
        snake.damroll = 3
        snake.damage_type = "pierce"
        snake.armor = 4
        snake.xp = 100
        snake.gold = random.randint(2, 8)
        snake.flags = []
        templates.append(snake)
        
        # Goblin
        goblin = MobTemplate(4, "a goblin")
        goblin.short_desc = "a goblin"
        goblin.long_desc = "A small, green-skinned humanoid with sharp teeth and a cruel grin."
        goblin.keywords = ["goblin"]
        goblin.level = 3
        goblin.hp = 50
        goblin.mana = 20
        goblin.stats = {"str": 11, "int": 8, "wis": 7, "dex": 12, "con": 11, "luc": 7}
        goblin.hitroll = 6
        goblin.damroll = 4
        goblin.damage_type = "slash"
        goblin.armor = 5
        goblin.xp = 200
        goblin.gold = random.randint(5, 15)
        goblin.flags = ["aggressive"]
        goblin.equipment = {"main_hand": {"weapon_type": "sword", "damage": [2, 5], "hitroll": 2}}
        goblin.loot_table = [(1004, 30)]  # 30% chance to drop a torch
        templates.append(goblin)
        
        # Wolf
        wolf = MobTemplate(5, "a grey wolf")
        wolf.short_desc = "a grey wolf"
        wolf.long_desc = "A lean, grey-furred wolf with intelligent yellow eyes."
        wolf.keywords = ["wolf", "grey", "grey wolf"]
        wolf.level = 4
        wolf.hp = 70
        wolf.mana = 25
        wolf.stats = {"str": 13, "int": 6, "wis": 8, "dex": 14, "con": 13, "luc": 8}
        wolf.hitroll = 8
        wolf.damroll = 5
        wolf.damage_type = "pierce"
        wolf.armor = 4
        wolf.xp = 350
        wolf.gold = random.randint(3, 12)
        wolf.flags = ["aggressive"]
        wolf.loot_table = [(1005, 40)]  # pelt
        templates.append(wolf)
        
        # Skeleton
        skeleton = MobTemplate(6, "a skeleton")
        skeleton.short_desc = "a skeleton"
        skeleton.long_desc = "The remains of a long-dead warrior, now animated by dark magic. It clutches a rusty sword."
        skeleton.keywords = ["skeleton", "undead"]
        skeleton.level = 5
        skeleton.hp = 90
        skeleton.mana = 30
        skeleton.stats = {"str": 14, "int": 2, "wis": 3, "dex": 10, "con": 15, "luc": 4}
        skeleton.hitroll = 9
        skeleton.damroll = 6
        skeleton.damage_type = "slash"
        skeleton.armor = 6
        skeleton.xp = 500
        skeleton.gold = random.randint(5, 20)
        skeleton.flags = ["aggressive", "undead"]
        skeleton.resists = {"pierce": 25, "slash": 25}
        skeleton.weakness = {"bash": 25, "fire": 25}
        skeleton.loot_table = [(1006, 25)]  # rusty sword
        templates.append(skeleton)
        
        # Bandit
        bandit = MobTemplate(7, "a bandit")
        bandit.short_desc = "a bandit"
        bandit.long_desc = "A rough-looking man with a scarred face and a hand resting on his weapon."
        bandit.keywords = ["bandit", "human", "man"]
        bandit.level = 6
        bandit.hp = 110
        bandit.mana = 40
        bandit.stats = {"str": 14, "int": 10, "wis": 9, "dex": 13, "con": 13, "luc": 9}
        bandit.hitroll = 10
        bandit.damroll = 7
        bandit.damage_type = "slash"
        bandit.armor = 7
        bandit.xp = 650
        bandit.gold = random.randint(10, 30)
        bandit.flags = ["aggressive"]
        bandit.equipment = {"main_hand": {"weapon_type": "sword", "damage": [2, 7], "hitroll": 3}}
        bandit.loot_table = [(1007, 20)]  # leather armor piece
        templates.append(bandit)
        
        # Bear
        bear = MobTemplate(8, "a black bear")
        bear.short_desc = "a black bear"
        bear.long_desc = "A massive black bear, its fur matted and its claws as long as daggers."
        bear.keywords = ["bear", "black", "black bear"]
        bear.level = 8
        bear.hp = 180
        bear.mana = 40
        bear.stats = {"str": 18, "int": 4, "wis": 6, "dex": 10, "con": 17, "luc": 6}
        bear.hitroll = 12
        bear.damroll = 9
        bear.damage_type = "slash"
        bear.armor = 5
        bear.xp = 900
        bear.gold = random.randint(10, 40)
        bear.flags = ["aggressive"]
        bear.loot_table = [(1008, 50)]  # bearskin
        templates.append(bear)
        
        # ─── Quest Givers ────────────────────────────────────────────────
        
        # Priest of Aylor (vnum 10)
        priest = MobTemplate(10, "Priest of Aylor")
        priest.short_desc = "Priest of Aylor"
        priest.long_desc = "A kindly old man in white robes, his eyes twinkling with wisdom."
        priest.keywords = ["priest", "aylor", "old man"]
        priest.level = 20
        priest.hp = 500
        priest.mana = 500
        priest.stats = {"str": 12, "int": 18, "wis": 20, "dex": 10, "con": 14, "luc": 15}
        priest.hitroll = 5
        priest.damroll = 2
        priest.armor = 20
        priest.xp = 0
        priest.gold = 0
        priest.flags = ["sentinel"]  # Doesn't wander or attack
        templates.append(priest)
        
        # Explorer (vnum 11)
        explorer = MobTemplate(11, "Explorer Elara")
        explorer.short_desc = "Explorer Elara"
        explorer.long_desc = "A sturdy woman with a weathered map case slung over her shoulder."
        explorer.keywords = ["explorer", "elara", "woman"]
        explorer.level = 15
        explorer.hp = 300
        explorer.mana = 200
        explorer.stats = {"str": 14, "int": 15, "wis": 13, "dex": 16, "con": 14, "luc": 13}
        explorer.hitroll = 8
        explorer.damroll = 4
        explorer.armor = 15
        explorer.xp = 0
        explorer.gold = 0
        explorer.flags = ["sentinel"]
        templates.append(explorer)
        
        # City Guard Captain (vnum 12)
        captain = MobTemplate(12, "Captain Aldric")
        captain.short_desc = "Captain Aldric"
        captain.long_desc = "A scarred veteran in polished armor, with a stern gaze that misses nothing."
        captain.keywords = ["captain", "aldric", "guard"]
        captain.level = 25
        captain.hp = 800
        captain.mana = 200
        captain.stats = {"str": 18, "int": 12, "wis": 14, "dex": 15, "con": 18, "luc": 12}
        captain.hitroll = 15
        captain.damroll = 10
        captain.armor = 30
        captain.xp = 0
        captain.gold = 0
        captain.flags = ["sentinel"]
        templates.append(captain)
        
        # Hunter (vnum 13)
        hunter = MobTemplate(13, "Hunter Kaelen")
        hunter.short_desc = "Hunter Kaelen"
        hunter.long_desc = "A lean, weathered man in a fur-lined cloak, a longbow slung across his back."
        hunter.keywords = ["hunter", "kaelen", "man"]
        hunter.level = 18
        hunter.hp = 400
        hunter.mana = 250
        hunter.stats = {"str": 15, "int": 13, "wis": 15, "dex": 19, "con": 15, "luc": 14}
        hunter.hitroll = 12
        hunter.damroll = 8
        hunter.armor = 18
        hunter.xp = 0
        hunter.gold = 0
        hunter.flags = ["sentinel"]
        templates.append(hunter)
        
        # ─── Darkwood Forest Mobs ─────────────────────────────────────────
        
        # Giant spider (vnum 14)
        spider = MobTemplate(14, "a giant spider")
        spider.short_desc = "a giant spider"
        spider.long_desc = "A massive black-furred spider with eight gleaming eyes and dripping mandibles."
        spider.keywords = ["spider", "giant", "giant spider"]
        spider.level = 4
        spider.hp = 60
        spider.mana = 30
        spider.stats = {"str": 12, "int": 3, "wis": 5, "dex": 16, "con": 11, "luc": 7}
        spider.hitroll = 9
        spider.damroll = 5
        spider.damage_type = "pierce"
        spider.armor = 4
        spider.xp = 400
        spider.gold = random.randint(3, 10)
        spider.flags = ["aggressive"]
        spider.resists = {"poison": 50}
        spider.loot_table = [(1014, 30)]  # spider silk
        templates.append(spider)
        
        # Darkwood Treant (vnum 15)
        treant = MobTemplate(15, "a darkwood treant")
        treant.short_desc = "a darkwood treant"
        treant.long_desc = "An ancient tree-like being, its bark-like skin covered in dark moss. Its eyes glow with an emerald light."
        treant.keywords = ["treant", "darkwood", "tree"]
        treant.level = 7
        treant.hp = 150
        treant.mana = 80
        treant.stats = {"str": 18, "int": 10, "wis": 14, "dex": 6, "con": 18, "luc": 8}
        treant.hitroll = 10
        treant.damroll = 8
        treant.damage_type = "bash"
        treant.armor = 10
        treant.xp = 750
        treant.gold = random.randint(5, 20)
        treant.flags = ["aggressive"]
        treant.resists = {"pierce": 50, "bash": 25}
        treant.weakness = {"fire": 50}
        treant.loot_table = [(1015, 40)]  # darkwood branch
        templates.append(treant)
        
        # Goblin Shaman (vnum 16)
        shaman = MobTemplate(16, "a goblin shaman")
        shaman.short_desc = "a goblin shaman"
        shaman.long_desc = "A goblin adorned with feathers and bones, clutching a twisted staff. Dark energy crackles around its fingers."
        shaman.keywords = ["goblin", "shaman", "goblin shaman"]
        shaman.level = 6
        shaman.hp = 80
        shaman.mana = 150
        shaman.stats = {"str": 10, "int": 16, "wis": 14, "dex": 12, "con": 10, "luc": 9}
        shaman.hitroll = 8
        shaman.damroll = 5
        shaman.damage_type = "magic"
        shaman.armor = 5
        shaman.xp = 550
        shaman.gold = random.randint(10, 30)
        shaman.flags = ["aggressive"]
        shaman.loot_table = [(1010, 25), (1009, 20)]  # potions
        templates.append(shaman)
        
        # Darkwood Stalker (vnum 17)
        stalker = MobTemplate(17, "a darkwood stalker")
        stalker.short_desc = "a darkwood stalker"
        stalker.long_desc = "A lithe, shadowy figure wrapped in dark leathers. Only its eyes are visible beneath the hood."
        stalker.keywords = ["stalker", "darkwood", "assassin"]
        stalker.level = 9
        stalker.hp = 120
        stalker.mana = 80
        stalker.stats = {"str": 14, "int": 12, "wis": 10, "dex": 20, "con": 13, "luc": 12}
        stalker.hitroll = 14
        stalker.damroll = 9
        stalker.damage_type = "pierce"
        stalker.armor = 6
        stalker.xp = 1000
        stalker.gold = random.randint(15, 40)
        stalker.flags = ["aggressive"]
        stalker.loot_table = [(1016, 25)]  # shadow blade
        templates.append(stalker)
        
        # Darkwood Wraith (vnum 18)
        wraith = MobTemplate(18, "a darkwood wraith")
        wraith.short_desc = "a darkwood wraith"
        wraith.long_desc = "A translucent, spectral figure that drifts silently through the trees. An aura of cold emanates from it."
        wraith.keywords = ["wraith", "darkwood", "spectre"]
        wraith.level = 10
        wraith.hp = 100
        wraith.mana = 200
        wraith.stats = {"str": 8, "int": 16, "wis": 16, "dex": 14, "con": 8, "luc": 6}
        wraith.hitroll = 12
        wraith.damroll = 7
        wraith.damage_type = "cold"
        wraith.armor = 8
        wraith.xp = 1200
        wraith.gold = 0
        wraith.flags = ["aggressive", "undead"]
        wraith.resists = {"pierce": 75, "slash": 75, "cold": 100}
        wraith.weakness = {"fire": 50, "magic": 25}
        wraith.loot_table = [(1017, 15)]  # ethereal essence
        templates.append(wraith)
        
        # Darkwood Boar (vnum 19)
        boar = MobTemplate(19, "a darkwood boar")
        boar.short_desc = "a darkwood boar"
        boar.long_desc = "A massive wild boar with tusks the length of daggers. Its bristly hide is caked with mud and gore."
        boar.keywords = ["boar", "wild", "darkwood boar"]
        boar.level = 6
        boar.hp = 140
        boar.mana = 40
        boar.stats = {"str": 16, "int": 4, "wis": 6, "dex": 11, "con": 16, "luc": 7}
        boar.hitroll = 11
        boar.damroll = 7
        boar.damage_type = "pierce"
        boar.armor = 7
        boar.xp = 600
        boar.gold = random.randint(2, 8)
        boar.flags = ["aggressive"]
        boar.loot_table = [(1018, 35)]  # boar hide
        templates.append(boar)
        
        self.world.mob_templates.clear()
        for t in templates:
            self.world.mob_templates[t.vnum] = t
        
        # Save synchronously
        self._save_mobs_sync()
    
    def _create_default_items(self):
        """Create default item templates."""
        templates = []
        
        # Torch
        torch = ItemTemplate(1004, "a torch")
        torch.short_desc = "a torch"
        torch.item_type = "light"
        torch.value = 5
        torch.weight = 1
        torch.flags = ["light"]
        templates.append(torch)
        
        # Wolf pelt
        pelt = ItemTemplate(1005, "a wolf pelt")
        pelt.short_desc = "a wolf pelt"
        pelt.item_type = "trash"
        pelt.value = 15
        pelt.weight = 2
        templates.append(pelt)
        
        # Rusty sword
        rsword = ItemTemplate(1006, "a rusty sword")
        rsword.short_desc = "a rusty sword"
        rsword.item_type = "weapon"
        rsword.weapon_type = "sword"
        rsword.value = 20
        rsword.weight = 5
        rsword.damage = (2, 5)
        rsword.hitroll = 1
        rsword.level = 3
        templates.append(rsword)
        
        # Leather armor
        leather = ItemTemplate(1007, "a leather vest")
        leather.short_desc = "a leather vest"
        leather.item_type = "armor"
        leather.value = 30
        leather.weight = 4
        leather.armor_class = 4
        leather.slot = "chest"
        leather.level = 3
        templates.append(leather)
        
        # Bearskin
        bearskin = ItemTemplate(1008, "a bearskin")
        bearskin.short_desc = "a bearskin"
        bearskin.item_type = "trash"
        bearskin.value = 40
        bearskin.weight = 5
        templates.append(bearskin)
        
        # Health potion
        hp_pot = ItemTemplate(1009, "a health potion")
        hp_pot.short_desc = "a health potion"
        hp_pot.item_type = "potion"
        hp_pot.value = 25
        hp_pot.weight = 1
        hp_pot.spell = "heal"
        hp_pot.spell_level = 3
        templates.append(hp_pot)
        
        # Mana potion
        mp_pot = ItemTemplate(1010, "a mana potion")
        mp_pot.short_desc = "a mana potion"
        mp_pot.item_type = "potion"
        mp_pot.value = 25
        mp_pot.weight = 1
        mp_pot.spell = "mana_regen"
        mp_pot.spell_level = 3
        templates.append(mp_pot)
        
        # Iron sword
        isword = ItemTemplate(1011, "an iron sword")
        isword.short_desc = "an iron sword"
        isword.item_type = "weapon"
        isword.weapon_type = "sword"
        isword.value = 50
        isword.weight = 5
        isword.damage = (3, 7)
        isword.hitroll = 3
        isword.damroll = 2
        isword.level = 5
        templates.append(isword)
        
        # Leather boots
        boots = ItemTemplate(1012, "leather boots")
        boots.short_desc = "leather boots"
        boots.item_type = "armor"
        boots.value = 15
        boots.weight = 2
        boots.armor_class = 2
        boots.slot = "feet"
        boots.level = 2
        templates.append(boots)
        
        # Silver ring
        ring = ItemTemplate(1013, "a silver ring")
        ring.short_desc = "a silver ring"
        ring.item_type = "armor"
        ring.value = 100
        ring.weight = 0.5
        ring.armor_class = 1
        ring.slot = "finger_l"
        ring.hitroll = 1
        ring.level = 5
        templates.append(ring)
        
        # ─── Darkwood Forest Items ────────────────────────────────────────
        
        # Spider silk (vnum 1014)
        silk = ItemTemplate(1014, "a bundle of spider silk")
        silk.short_desc = "a bundle of spider silk"
        silk.long_desc = "A shimmering bundle of pure white spider silk, impossibly strong and light."
        silk.keywords = ["silk", "spider", "bundle"]
        silk.item_type = "trash"
        silk.value = 50
        silk.weight = 0.5
        templates.append(silk)
        
        # Darkwood branch (vnum 1015)
        branch = ItemTemplate(1015, "a darkwood branch")
        branch.short_desc = "a darkwood branch"
        branch.long_desc = "A heavy branch of dark, iron-hard wood. It could serve as an excellent club."
        branch.keywords = ["branch", "darkwood", "club"]
        branch.item_type = "weapon"
        branch.weapon_type = "club"
        branch.value = 60
        branch.weight = 6
        branch.damage = (3, 8)
        branch.hitroll = 2
        branch.damroll = 3
        branch.level = 6
        templates.append(branch)
        
        # Shadow blade (vnum 1016)
        sblade = ItemTemplate(1016, "a shadow blade")
        sblade.short_desc = "a shadow blade"
        sblade.long_desc = "A curved blade forged from dark steel that seems to drink the light around it."
        sblade.keywords = ["shadow", "blade", "dagger"]
        sblade.item_type = "weapon"
        sblade.weapon_type = "dagger"
        sblade.value = 150
        sblade.weight = 2
        sblade.damage = (4, 9)
        sblade.hitroll = 5
        sblade.damroll = 3
        sblade.level = 8
        templates.append(sblade)
        
        # Ethereal essence (vnum 1017)
        essence = ItemTemplate(1017, "ethereal essence")
        essence.short_desc = "ethereal essence"
        essence.long_desc = "A swirling vial of faintly glowing mist that pulses with otherworldly energy."
        essence.keywords = ["essence", "ethereal", "vial"]
        essence.item_type = "potion"
        essence.value = 200
        essence.weight = 0.5
        essence.spell = "mana_regen"
        essence.spell_level = 8
        essence.flags = ["glow"]
        templates.append(essence)
        
        # Boar hide (vnum 1018)
        boar_hide = ItemTemplate(1018, "a thick boar hide")
        boar_hide.short_desc = "a thick boar hide"
        boar_hide.long_desc = "A thick, bristly boar hide, good for making rugged leather armor."
        boar_hide.keywords = ["hide", "boar", "thick"]
        boar_hide.item_type = "trash"
        boar_hide.value = 35
        boar_hide.weight = 4
        templates.append(boar_hide)
        
        # Leather backpack (vnum 1019)
        backpack = ItemTemplate(1019, "a leather backpack")
        backpack.short_desc = "a leather backpack"
        backpack.long_desc = "A sturdy leather backpack with multiple pockets and straps."
        backpack.keywords = ["backpack", "leather", "bag", "pack"]
        backpack.item_type = "container"
        backpack.value = 75
        backpack.weight = 3
        backpack.capacity = 30  # Can hold 30 units of weight
        backpack.slot = "back"
        templates.append(backpack)
        
        # Small pouch (vnum 1020)
        pouch = ItemTemplate(1020, "a small leather pouch")
        pouch.short_desc = "a small leather pouch"
        pouch.long_desc = "A small leather pouch with a drawstring closure."
        pouch.keywords = ["pouch", "small", "leather"]
        pouch.item_type = "container"
        pouch.value = 25
        pouch.weight = 0.5
        pouch.capacity = 8
        pouch.slot = "waist"
        templates.append(pouch)
        
        self.world.item_templates.clear()
        for t in templates:
            self.world.item_templates[t.vnum] = t
        
        # Save synchronously
        self._save_items_sync()
    
    def _save_zones_sync(self):
        """Synchronous zone/room save."""
        data = {
            "zones": [z.to_dict() for z in self.world.zones.values()],
            "rooms": [r.to_dict() for r in self.world.rooms.values()]
        }
        cfg.WORLD_DIR.mkdir(parents=True, exist_ok=True)
        with open(cfg.WORLD_DIR / "zones.json", "w") as f:
            json.dump(data, f, indent=2)
    
    def _save_mobs_sync(self):
        """Synchronous mob template save."""
        cfg.MOB_DIR.mkdir(parents=True, exist_ok=True)
        data = [m.to_dict() for m in self.world.mob_templates.values()]
        with open(cfg.MOB_DIR / "mobs.json", "w") as f:
            json.dump(data, f, indent=2)
    
    def _save_items_sync(self):
        """Synchronous item template save."""
        cfg.WORLD_DIR.mkdir(parents=True, exist_ok=True)
        data = [i.to_dict() for i in self.world.item_templates.values()]
        with open(cfg.WORLD_DIR / "items.json", "w") as f:
            json.dump(data, f, indent=2)
