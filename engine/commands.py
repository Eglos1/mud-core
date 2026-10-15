"""
Command handler — processes all player commands.
"""
import asyncio, random, math, time, re, traceback
from .config import Config
from .combat import CombatSystem

cfg = Config()

class CommandHandler:
    """Handles parsing and execution of player commands."""
    
    def __init__(self, world):
        self.world = world
        self.combat = CombatSystem(world)
        self.commands = {}
        self._register_all()
    
    def register(self, name, func, aliases=None, min_level=0, hide_help=False):
        """Register a command."""
        self.commands[name] = {
            "func": func,
            "aliases": aliases or [],
            "min_level": min_level,
            "hide_help": hide_help
        }
        for alias in (aliases or []):
            self.commands[alias] = {"func": func, "aliases": [], "min_level": min_level, "hide_help": True}
    
    def _register_all(self):
        """Register all commands."""
        
        # ─── Movement ────────────────────────────────────────────
        def make_mover(direction):
            def move_fn(player, args):
                self._move_player(player, direction)
            return move_fn
        for d in ["north", "south", "east", "west", "up", "down"]:
            self.register(d, make_mover(d), hide_help=True)
        self.register("n", make_mover("north"), aliases=["north"], hide_help=True)
        self.register("s", make_mover("south"), aliases=["south"], hide_help=True)
        self.register("e", make_mover("east"), aliases=["east"], hide_help=True)
        self.register("w", make_mover("west"), aliases=["west"], hide_help=True)
        self.register("u", make_mover("up"), aliases=["up"], hide_help=True)
        self.register("d", make_mover("down"), aliases=["down"], hide_help=True)
        
        # ─── Look ────────────────────────────────────────────────
        async def do_look(player, args):
            room = self.world.rooms.get(player.room_vnum)
            if not room:
                player.send("You are in the void.")
                return
            
            if args:
                # Look at specific thing
                self._do_look_at(player, room, args)
                return
            
            player.send(room.describe(player, brief=player.brief))
            # Show players in room
            for eid in (room.contents or []):
                entity = self.world.entities.get(eid)
                if entity and entity is not player and entity.is_player:
                    player.send(f"\x1b[32m[{entity.name} is here.]\x1b[0m")
        
        self.register("look", do_look, aliases=["l", "examine", "exam"])
        
        # ─── Say ─────────────────────────────────────────────────
        async def do_say(player, args):
            if not args:
                player.send("Say what?")
                return
            msg = f"{player.name} says, '{args}'"
            for eid in (self.world.rooms.get(player.room_vnum, {}).contents or []):
                entity = self.world.entities.get(eid)
                if entity and entity is not player:
                    entity.send(f"\x1b[36m{msg}\x1b[0m")
            player.send(f"\x1b[36mYou say, '{args}'\x1b[0m")
        
        self.register("say", do_say, aliases=["'", "tell"])
        
        # ─── Gossip/Shout ──────────────────────────────────────────
        async def do_gossip(player, args):
            if not args:
                player.send("Gossip what?")
                return
            msg = f"[Gossip] {player.name}: {args}"
            for p in self.world.players:
                if p.is_connected():
                    p.send(f"\x1b[35m{msg}\x1b[0m")
        
        self.register("gossip", do_gossip, aliases=["g", "gs"])
        
        async def do_shout(player, args):
            if not args:
                player.send("Shout what?")
                return
            msg = f"{player.name} shouts, '{args}'"
            for p in self.world.players:
                if p.is_connected():
                    p.send(f"\x1b[33m{msg}\x1b[0m")
        
        self.register("shout", do_shout)
        
        # ─── Who ──────────────────────────────────────────────────
        async def do_who(player, args):
            player.send(f"\x1b[33mPlayers online ({len([p for p in self.world.players if p.is_connected()])}):\x1b[0m")
            for p in self.world.players:
                if p.is_connected():
                    cls = p.save_data.get("class", "???").capitalize()
                    race = p.save_data.get("race", "???").capitalize()
                    player.send(f"  [Lv{p.level:>3}] {p.name:<20} {race:<10} {cls:<12}")
        
        self.register("who", do_who)
        
        # ─── Score ────────────────────────────────────────────────
        async def do_score(player, args):
            cls = player.save_data.get("class", "???")
            race = player.save_data.get("race", "???")
            player.send(f"+{'-'*60}+")
            player.send(f"|  \x1b[1m{player.name}\x1b[0m the {race} {cls}")
            player.send(f"+{'-'*60}+")
            player.send(f"  Level: {player.level}    HP: {player.hp}/{player.max_hp}")
            player.send(f"  Mana: {player.mana}/{player.max_mana}    Moves: {player.movement}/{player.max_movement}")
            player.send(f"  XP: {player.xp}/{player.xp_to_level}    Gold: {player.gold}")
            player.send(f"  STR:{player.str:>3}  INT:{player.int:>3}  WIS:{player.wis:>3}  DEX:{player.dex:>3}  CON:{player.con:>3}  LUC:{player.luc:>3}")
            player.send(f"  Hitroll: {player.hitroll_total()}  Damroll: {player.damroll_total()}  Armor: {player.armor_total()}")
            player.send(f"  Practices: {player.practices}  Trains: {player.trains}")
            player.send(f"+{'-'*60}+")
        
        self.register("score", do_score, aliases=["sc"])
        
        # ─── Inventory ────────────────────────────────────────────
        async def do_inventory(player, args):
            if not player.inventory:
                player.send("You are carrying nothing.")
            else:
                player.send("\x1b[33mYou are carrying:\x1b[0m")
                for item in player.inventory:
                    desc = item.short_desc
                    if item.worn:
                        desc += " \x1b[34m(worn)\x1b[0m"
                    player.send(f"  {desc}")
            player.send(f"Gold: {player.gold}  Weight: {player.weight}/{player.max_weight}")
        
        self.register("inventory", do_inventory, aliases=["i", "inv"])
        
        # ─── Equipment ────────────────────────────────────────────
        async def do_equipment(player, args):
            player.send("\x1b[33mYou are wearing:\x1b[0m")
            empty = True
            for slot in cfg.SLOTS:
                item = player.equipment.get(slot)
                if item:
                    empty = False
                    player.send(f"  <{slot:12}> {item.short_desc}")
            if empty:
                player.send("  Nothing.")
        
        self.register("equipment", do_equipment, aliases=["eq", "worn"])
        
        # ─── Get ──────────────────────────────────────────────────
        async def do_get(player, args):
            if not args:
                player.send("Get what?")
                return
            
            room = self.world.rooms.get(player.room_vnum)
            if not room:
                return
            
            # Parse args: "get all corpse" or "get sword" or "get sword bag"
            parts = args.lower().split()
            target = parts[0]
            source = parts[1] if len(parts) > 1 else None
            
            items_to_get = []
            
            if target == "all":
                items_to_get = list(room.items)
            else:
                for item_id in room.items:
                    item = self.world.entities.get(item_id)
                    if item and target in item.keywords:
                        items_to_get.append(item_id)
            
            if not items_to_get:
                player.send("You don't see that here.")
                return
            
            for item_id in items_to_get:
                item = self.world.entities.get(item_id)
                if item:
                    # Check weight
                    new_weight = player.weight + item.weight
                    if new_weight > player.max_weight:
                        player.send(f"{item.short_desc} is too heavy for you to carry.")
                        continue
                    
                    # Move from room to player's inventory
                    if item_id in room.items:
                        room.items.remove(item_id)
                    player.inventory.append(item)
                    player.weight = new_weight
                    player.send(f"You pick up {item.short_desc}.")
                    self.world.broadcast_to_room(player.room_vnum,
                        f"{player.name} picks up {item.short_desc}.",
                        exclude=[player.entity_id])
        
        self.register("get", do_get, aliases=["take", "pick"])
        
        # ─── Drop ─────────────────────────────────────────────────
        async def do_drop(player, args):
            if not args:
                player.send("Drop what?")
                return
            
            target = args.lower().strip()
            items_to_drop = []
            
            if target == "all":
                items_to_drop = list(player.inventory)
            else:
                for item in player.inventory:
                    if target in [k.lower() for k in item.keywords]:
                        items_to_drop.append(item)
            
            if not items_to_drop:
                player.send("You don't have that.")
                return
            
            room = self.world.rooms.get(player.room_vnum)
            if not room:
                return
            
            for item in items_to_drop:
                if item in player.inventory:
                    player.inventory.remove(item)
                    player.weight = max(0, player.weight - item.weight)
                    room.items.append(item.uid if hasattr(item, 'uid') else id(item))
                    player.send(f"You drop {item.short_desc}.")
        
        self.register("drop", do_drop, aliases=["discard"])
        
        # ─── Wear/Wield ───────────────────────────────────────────
        async def do_wear(player, args):
            if not args:
                player.send("Wear what?")
                return
            
            target = args.lower().strip()
            item = None
            
            for inv_item in player.inventory:
                if target in [k.lower() for k in inv_item.keywords]:
                    item = inv_item
                    break
            
            if not item:
                player.send(f"You don't have '{target}'.")
                return
            
            slot = item.slot
            if not slot and item.item_type == "weapon":
                slot = "main_hand"
            elif not slot:
                player.send(f"You can't wear {item.short_desc}.")
                return
            
            if slot == "main_hand" and player.equipment.get("main_hand"):
                # Move current weapon to off_hand if possible, otherwise drop
                current = player.equipment.unequip("main_hand")
                if current:
                    # Try offhand
                    if not player.equipment.get("off_hand"):
                        player.equipment.equip("off_hand", current)
                    else:
                        player.inventory.append(current)
            
            player.equipment.equip(slot, item)
            if item in player.inventory:
                player.inventory.remove(item)
            item.worn = True
            
            if slot == "main_hand":
                player.send(f"You wield {item.short_desc}.")
            else:
                player.send(f"You wear {item.short_desc} on your {slot}.")
        
        self.register("wear", do_wear, aliases=["wield", "equip"])
        
        # ─── Remove ───────────────────────────────────────────────
        async def do_remove(player, args):
            if not args:
                player.send("Remove what?")
                return
            
            target = args.lower().strip()
            for slot in cfg.SLOTS:
                item = player.equipment.get(slot)
                if item and target in [k.lower() for k in item.keywords]:
                    player.equipment.unequip(slot)
                    player.inventory.append(item)
                    item.worn = False
                    player.send(f"You remove {item.short_desc}.")
                    return
            
            player.send(f"You aren't wearing '{target}'.")
        
        self.register("remove", do_remove, aliases=["rem"])
        
        # ─── Drink/Quaff ────────────────────────────────────────────
        async def do_drink(player, args):
            if not args:
                player.send("Drink what?")
                return
            
            target_name = args.lower().strip()
            
            # Find potion in inventory
            found = None
            for item in player.inventory:
                if item.item_type == "potion" and target_name in [k.lower() for k in item.keywords]:
                    found = item
                    break
            
            if not found:
                player.send(f"You don't have '{target_name}' (a potion).")
                return
            
            # Apply potion effect
            spell = getattr(found, 'spell', None)
            spell_level = getattr(found, 'spell_level', 1)
            
            if spell == "heal":
                healed = random.randint(15, 30) + spell_level * 2
                player.hp = min(player.max_hp, player.hp + healed)
                player.send(f"\x1b[32mYou drink the potion. It heals you for {healed} hit points!\x1b[0m")
            elif spell == "mana_regen":
                restored = random.randint(15, 30) + spell_level * 2
                player.mana = min(player.max_mana, player.mana + restored)
                player.send(f"\x1b[36mYou drink the potion. It restores {restored} mana points!\x1b[0m")
            else:
                player.send("You drink the potion but nothing happens.")
            
            # Consume the potion
            player.inventory.remove(found)
        
        self.register("drink", do_drink, aliases=["quaff"])
        
        # ─── Kill ─────────────────────────────────────────────────
        async def do_kill(player, args):
            if not args:
                player.send("Kill what?")
                return
            
            if player.fighting:
                player.send("You are already fighting!")
                return
            
            target_name = args.lower().strip()
            
            # Find target in room
            room = self.world.rooms.get(player.room_vnum)
            if not room:
                return
            
            target = None
            for mob_id in room.mobs:
                mob = self.world.entities.get(mob_id)
                if mob and mob.is_mob and mob.hp > 0:
                    keywords = [k.lower() for k in mob.keywords]
                    if target_name in keywords or target_name == mob.name.lower():
                        target = mob
                        break
            
            if not target:
                player.send("They aren't here.")
                return
            
            self.combat.start_combat(player, target)
        
        self.register("kill", do_kill, aliases=["attack", "hit", "murder"])
        
        # ─── Flee ─────────────────────────────────────────────────
        async def do_flee(player, args):
            if not player.fighting:
                player.send("You aren't fighting!")
                return
            self.combat.flee(player)
        
        self.register("flee", do_flee)
        
        # ─── Recall ───────────────────────────────────────────────
        async def do_recall(player, args):
            if player.fighting:
                player.send("You can't recall while fighting!")
                return
            
            bind = player.save_data.get("bind_vnum", 3001)
            self.world.move_entity(player, bind)
            player.send("\x1b[33mYou close your eyes and concentrate... You feel yourself being pulled through space!\x1b[0m")
        
        self.register("recall", do_recall, aliases=["home"])
        
        # ─── Train ────────────────────────────────────────────────
        async def do_train(player, args):
            if not args:
                player.send(f"Train what? Stats: str, int, wis, dex, con, luc. Trains: {player.trains}")
                return
            
            if player.trains <= 0:
                player.send("You have no training sessions left.")
                return
            
            stat = args.lower().strip()[:3]
            valid = {"str": "str", "int": "int", "wis": "wis", "dex": "dex", "con": "con", "luc": "luc"}
            
            if stat not in valid:
                player.send("Valid stats: str, int, wis, dex, con, luc")
                return
            
            player.stats[valid[stat]] += 1
            player.trains -= 1
            player.send(f"\x1b[33mYou train {valid[stat].upper()} to {player.stats[valid[stat]]}!\x1b[0m")
        
        self.register("train", do_train)
        
        # ─── Practice ──────────────────────────────────────────────
        async def do_practice(player, args):
            if not args:
                player.send(f"Practices: {player.practices}")
                known = [s for s in player.skills if player.skills[s] > 0]
                if known:
                    player.send("Known skills:")
                    for s in sorted(known):
                        player.send(f"  {s}: {player.skills[s]}%")
                return
            
            skill_name = args.lower().strip()
            
            if player.practices <= 0:
                player.send("You have no practices left.")
                return
            
            # Check if skill exists
            from .skills import get_skill_def
            skill_def = get_skill_def(skill_name)
            if not skill_def:
                player.send(f"Unknown skill: {skill_name}")
                return
            
            # Check prerequisites
            for prereq_name, prereq_level in skill_def.prereqs:
                if player.get_skill(prereq_name) < prereq_level:
                    player.send(f"You need {prereq_name} at {prereq_level}% first.")
                    return
            
            # Check level requirement
            if player.level < skill_def.level:
                player.send(f"You need to be level {skill_def.level} to learn {skill_name}.")
                return
            
            # Improve
            current = player.get_skill(skill_name)
            learn_every = skill_def.learn_every or 4
            gain = random.randint(1, min(5, 100 - current))
            gain = min(gain, 100 - current)
            
            if gain <= 0:
                player.send(f"You are already a master of {skill_name}.")
                return
            
            practices_needed = max(1, int(gain * learn_every / 2))
            if player.practices < practices_needed:
                practices_needed = player.practices
                gain = int(practices_needed * 2 / learn_every)
            
            player.skills[skill_name] = min(100, current + gain)
            player.practices -= practices_needed
            player.send(f"\x1b[33mYou practice {skill_name} and improve to {player.skills[skill_name]}% ({practices_needed} practices).\x1b[0m")
        
        self.register("practice", do_practice, aliases=["prac"])
        
        # ─── Skills ───────────────────────────────────────────────
        async def do_skills(player, args):
            known = [(s, p) for s, p in player.skills.items() if p > 0]
            if not known:
                player.send("You know no skills.")
                return
            
            player.send(f"\x1b[33mSkills known ({len(known)}):\x1b[0m")
            for s, p in sorted(known):
                player.send(f"  {s:<20} {p:>3}%")
        
        self.register("skills", do_skills)
        
        # ─── Use skill/spell ──────────────────────────────────────
        async def do_cast(player, args):
            if not args:
                player.send("Cast what?")
                return
            
            parts = args.split()
            skill_name = parts[0].lower()
            target_name = parts[1] if len(parts) > 1 else None
            
            if not player.has_skill(skill_name):
                player.send(f"You don't know '{skill_name}'.")
                return
            
            if not player.can_use_skill(skill_name):
                player.send("That skill is on cooldown.")
                return
            
            from .skills import get_skill_def
            skill_def = get_skill_def(skill_name)
            if not skill_def:
                player.send("Unknown skill.")
                return
            
            # Mana check
            if player.mana < skill_def.mana_cost:
                player.send("You don't have enough mana.")
                return
            
            # Find target
            target = None
            if skill_def.target == "self":
                target = player
            elif skill_def.target == "offensive":
                if player.fighting:
                    target = self.world.entities.get(player.fighting)
                elif target_name:
                    room = self.world.rooms.get(player.room_vnum)
                    if room:
                        for mob_id in room.mobs:
                            mob = self.world.entities.get(mob_id)
                            if mob and target_name.lower() in [k.lower() for k in mob.keywords]:
                                target = mob
                                break
                if not target:
                    player.send("They aren't here.")
                    return
            
            # Apply skill
            player.mana -= skill_def.mana_cost
            player.use_skill(skill_name)
            
            if skill_def.damage_dice and skill_def.damage_dice != (0, 0) and target:
                # Combat skill
                nd, sz = skill_def.damage_dice
                damage = sum(random.randint(1, sz) for _ in range(nd)) + skill_def.dam_bonus + player.damroll_total()
                
                hit_bonus = skill_def.hit_bonus + player.hitroll_total() + random.randint(1, 20)
                if hit_bonus > target.armor_total():
                    died = target.take_damage(damage, player, skill_def.damage_type)
                    msg = skill_def.desc_hit or f"Your {skill_name} hits {target.short_desc}!"
                    player.send(f"\x1b[33m{msg} [{damage}]\x1b[0m")
                    if died:
                        pass  # Handled by take_damage
                else:
                    msg = skill_def.desc_miss or f"Your {skill_name} misses {target.short_desc}."
                    player.send(f"\x1b[34m{msg}\x1b[0m")
            
            elif skill_def.damage_dice == (0, 0) and skill_name in ("heal", "nature_heal", "lay_hands", "cure"):
                # Healing skill
                nd, sz = 2, 6
                if skill_def.damage_dice and skill_def.damage_dice != (0, 0):
                    nd, sz = skill_def.damage_dice
                healed = sum(random.randint(1, sz) for _ in range(nd)) + skill_def.dam_bonus
                player.hp = min(player.max_hp, player.hp + healed)
                player.send(f"\x1b[32mA warm glow heals you for {healed} hit points!\x1b[0m")
            
            elif skill_name == "teleport":
                # Teleport to bind point
                bind = getattr(player, "bind_vnum", 3001)
                self._move_player(player, None, dest_vnum=bind)
                player.send("\x1b[35mYou teleport through space and time!\x1b[0m")
            
            elif skill_name in ("bless", "aura", "divine_shield", "sanctuary"):
                # Buff skills — add temporary armor/hitroll bonus via affects
                buff_map = {"bless": "hitroll", "aura": "hitroll", "divine_shield": "armor", "sanctuary": "armor"}
                attr = buff_map.get(skill_name, "armor")
                bonus = {"bless": 3, "aura": 5, "divine_shield": 8, "sanctuary": 10}.get(skill_name, 3)
                duration = {"bless": 20, "aura": 15, "divine_shield": 25, "sanctuary": 30}.get(skill_name, 15)
                from .entity import Affect
                aff = Affect(skill_name, attr, bonus, duration, f"A shimmering {skill_name} surrounds you.")
                player.add_affect(aff)
                player.send(f"\x1b[33m{skill_def.desc_hit}\x1b[0m")
            
            elif skill_name == "curse" and target:
                # Curse reduces target's hitroll/armor
                from .entity import Affect
                aff = Affect("curse", "hitroll", -5, 15, f"{target.short_desc} is cursed!")
                target.add_affect(aff)
                player.send(f"\x1b[31mYou curse {target.short_desc}, weakening them!\x1b[0m")
                if hasattr(target, 'send') and target != player:
                    target.send(f"\x1b[31mYou feel a dark curse upon you!\x1b[0m")
            
            elif skill_name == "fear" and target:
                # Fear makes target flee
                player.send(f"\x1b[31mYou terrify {target.short_desc}!\x1b[0m")
                if hasattr(target, 'send') and target != player:
                    target.send(f"\x1b[31mYou are filled with terror and flee!\x1b[0m")
                if hasattr(target, 'flee_combat'):
                    target.flee_combat()
            
            elif skill_name == "entangle" and target:
                # Entangle stuns target for 2 rounds
                target.stunned = max(target.stunned, 2)
                player.send(f"\x1b[32mVines entangle {target.short_desc}!\x1b[0m")
                if hasattr(target, 'send') and target != player:
                    target.send(f"\x1b[32mThick vines entangle you!\x1b[0m")
            
            elif skill_name in ("summon_wolf", "animal_companion", "summon_undead"):
                # Summon an ally mob
                room = self.world.rooms.get(player.room_vnum)
                if room:
                    from .entity import Mob
                    ally = Mob(
                        name=f"summoned_{skill_name}",
                        short_desc={ "summon_wolf": "a grey wolf", "animal_companion": "a fierce badger", "summon_undead": "a skeletal minion" }.get(skill_name, "a summoned creature"),
                        long_desc="It fights by your side.",
                        keywords=[skill_name, "summoned"],
                        level=player.level,
                        hp=player.level * 10,
                        damage_dice=(2, player.level // 2 + 3),
                        gold=0,
                        xp=0
                    )
                    ally.room_vnum = player.room_vnum
                    ally.owner_id = player.entity_id
                    ally.is_pet = True
                    self.world.entities[ally.entity_id] = ally
                    room.mobs.append(ally.entity_id)
                    player.send(f"\x1b[33m{skill_def.desc_hit}\x1b[0m")
            
            else:
                player.send(f"You use {skill_name}.")
        
        self.register("cast", do_cast, aliases=["c", "use"])
        
        # ─── Open/Close/Door ──────────────────────────────────────
        async def do_open(player, args):
            if not args:
                player.send("Open what?")
                return
            self._handle_door(player, args.lower(), "open")
        self.register("open", do_open)
        
        async def do_close(player, args):
            if not args:
                player.send("Close what?")
                return
            self._handle_door(player, args.lower(), "close")
        self.register("close", do_close)
        
        # ─── Shop commands ────────────────────────────────────────
        async def do_list(player, args):
            shop = self.world.economy.get_shop_at_room(player.room_vnum)
            if not shop:
                player.send("There is no shop here.")
                return
            self.world.economy.list_shop_items(shop, player)
        self.register("list", do_list)
        
        async def do_buy(player, args):
            if not args:
                player.send("Buy what?")
                return
            shop = self.world.economy.get_shop_at_room(player.room_vnum)
            if not shop:
                player.send("There is no shop here.")
                return
            
            # Try to find by number or keyword
            try:
                idx = int(args) - 1
                if 0 <= idx < len(shop.products):
                    item_vnum = shop.products[idx]
                    self.world.economy.buy_item(shop, player, item_vnum)
            except ValueError:
                # Search by keyword
                for item_vnum in shop.products:
                    template = self.world.item_templates.get(item_vnum)
                    if template and args.lower() in template.name.lower():
                        self.world.economy.buy_item(shop, player, item_vnum)
                        return
                player.send(f"The shop doesn't sell '{args}'.")
        self.register("buy", do_buy)
        
        async def do_sell(player, args):
            if not args:
                player.send("Sell what?")
                return
            shop = self.world.economy.get_shop_at_room(player.room_vnum)
            if not shop:
                player.send("There is no shop here.")
                return
            
            target = args.lower()
            for item in player.inventory[:]:
                if target in [k.lower() for k in item.keywords]:
                    self.world.economy.sell_item(shop, player, item)
                    return
            player.send(f"You don't have '{args}'.")
        self.register("sell", do_sell)
        
        # ─── Rest/Sleep ────────────────────────────────────────────
        async def do_rest(player, args):
            player.position = "sitting"
            player.send("You rest.")
        self.register("rest", do_rest)
        
        async def do_sleep(player, args):
            if player.fighting:
                player.send("You can't sleep in combat!")
                return
            player.position = "sleeping"
            player.send("You go to sleep.")
        self.register("sleep", do_sleep)
        
        async def do_stand(player, args):
            player.position = "standing"
            player.send("You stand up.")
        self.register("stand", do_stand, aliases=["wake"])
        
        # ─── Toggles ──────────────────────────────────────────────
        async def do_toggle(player, args):
            if not args:
                player.send("Toggles: " + ", ".join(f"{k}: {v}" for k, v in player.toggles.items()))
                return
            toggle = args.lower().strip()
            if toggle in player.toggles:
                player.toggles[toggle] = not player.toggles[toggle]
                player.send(f"{toggle} is now {'ON' if player.toggles[toggle] else 'OFF'}.")
            else:
                player.send(f"Unknown toggle: {toggle}")
        self.register("toggle", do_toggle)
        
        # ─── Emote ────────────────────────────────────────────────
        async def do_emote(player, args):
            if not args:
                player.send("Emote what?")
                return
            msg = f"{player.name} {args}"
            for eid in (self.world.rooms.get(player.room_vnum, {}).contents or []):
                entity = self.world.entities.get(eid)
                if entity and entity is not player:
                    entity.send(f"\x1b[35m{msg}\x1b[0m")
            player.send(f"\x1b[35m{msg}\x1b[0m")
        self.register("emote", do_emote, aliases=[":"])
        
        # ─── Help ─────────────────────────────────────────────────
        async def do_help(player, args):
            if args:
                # Look up specific command help
                cmd_name = args.lower().strip()
                cmd = self.commands.get(cmd_name)
                if not cmd or cmd.get("hide_help"):
                    player.send(f"No help found for '{cmd_name}'.")
                    return
                player.send(f"\x1b[33mHelp: {cmd_name}\x1b[0m")
                player.send(f"  Aliases: {', '.join(cmd['aliases']) if cmd['aliases'] else 'none'}")
                player.send(f"  Min level: {cmd['min_level']}")
            else:
                player.send("\x1b[33mCommands:\x1b[0m")
                cmds = sorted([name for name, c in self.commands.items() if not c.get("hide_help")])
                cols = 4
                for i in range(0, len(cmds), cols):
                    row = cmds[i:i+cols]
                    player.send("  " + "  ".join(f"{c:<15}" for c in row))
                player.send("\nType 'help <command>' for details.")
        self.register("help", do_help, aliases=["?"])
        
        # ─── Quit ─────────────────────────────────────────────────
        async def do_quit(player, args):
            if player.fighting:
                player.send("You can't quit in combat!")
                return
            player.send("Goodbye!")
            self.world.save_player(player)
            self.world.remove_player(player)
        self.register("quit", do_quit)
        
        # ─── Save ─────────────────────────────────────────────────
        async def do_save(player, args):
            self.world.save_player(player)
            player.send("Saved.")
        self.register("save", do_save)
        
        # ─── Time/Weather ─────────────────────────────────────────
        async def do_time(player, args):
            w = self.world.weather
            player.send(f"\x1b[36m{w.current_condition()}\x1b[0m")
            player.send(f"Temperature: {w.temperature}°F  Humidity: {w.humidity}%  Wind: {w.wind}mph")
            player.send(f"Day {w.day}, hour {w.time}:00")
        self.register("time", do_time, aliases=["weather"])
        
        # ─── Scan ─────────────────────────────────────────────────
        async def do_scan(player, args):
            room = self.world.rooms.get(player.room_vnum)
            if not room:
                return
            
            directions_found = {}
            for direction, exit_obj in room.exits.items():
                target_room = self.world.rooms.get(exit_obj.target_room)
                if target_room:
                    mobs_there = [self.world.entities.get(mid) for mid in target_room.mobs]
                    mob_names = [m.short_desc for m in mobs_there if m and m.hp > 0]
                    if mob_names:
                        directions_found[direction] = mob_names
            
            if not directions_found:
                player.send("You scan the area but see nothing.")
                return
            
            player.send("\x1b[33mYou scan the area...\x1b[0m")
            for direction, mobs in directions_found.items():
                player.send(f"  \x1b[32m{direction.capitalize()} from here you see:\x1b[0m")
                for m in mobs[:3]:
                    player.send(f"    - {m}")
        self.register("scan", do_scan)
        
        # ─── Builder Commands ─────────────────────────────────────
        async def do_dig(player, args):
            """Dig a new room in a direction."""
            if not player.is_builder:
                player.send("You don't have building permissions.")
                return
            
            if not args:
                player.send("Usage: dig <direction> [room_name]")
                return
            
            parts = args.split(None, 1)
            direction = parts[0].lower()
            room_name = parts[1] if len(parts) > 1 else "A new room"
            
            if direction not in ("north", "south", "east", "west", "up", "down"):
                player.send(f"Invalid direction: {direction}")
                return
            
            current_room = self.world.rooms.get(player.room_vnum)
            if not current_room:
                return
            
            if current_room.get_exit(direction):
                player.send(f"There is already an exit {direction}.")
                return
            
            # Find a new vnum
            new_vnum = max(self.world.rooms.keys()) + 1 if self.world.rooms else 3001
            
            new_room = Room(new_vnum, room_name, "A newly created room.", current_room.zone)
            new_room.sector = "city"
            new_room.coord = self._calc_coord(current_room.coord, direction)
            
            self.world.rooms[new_vnum] = new_room
            
            # Create bidirectional exits
            rev = {"north":"south", "south":"north", "east":"west", "west":"east", "up":"down", "down":"up"}
            current_room.add_exit(direction, new_vnum)
            new_room.add_exit(rev.get(direction, "south"), player.room_vnum)
            
            player.send(f"\x1b[33mYou dig a new room: {new_vnum} - {room_name}\x1b[0m")
            
            # Add to zone
            zone = self.world.zones.get(current_room.zone)
            if zone:
                zone.add_room(new_room)
        
        async def do_link(player, args):
            """Link two rooms with an exit."""
            if not player.is_builder:
                player.send("You don't have building permissions.")
                return
            
            try:
                parts = args.split()
                direction = parts[0].lower()
                target_vnum = int(parts[1])
            except:
                player.send("Usage: link <direction> <target_vnum>")
                return
            
            current_room = self.world.rooms.get(player.room_vnum)
            target_room = self.world.rooms.get(target_vnum)
            
            if not current_room or not target_room:
                player.send("Invalid room(s).")
                return
            
            rev = {"north":"south", "south":"north", "east":"west", "west":"east", "up":"down", "down":"up"}
            current_room.add_exit(direction, target_vnum)
            target_room.add_exit(rev.get(direction, "south"), player.room_vnum)
            
            player.send(f"\x1b[33mLinked {player.room_vnum} ({direction}) <-> {target_vnum} ({rev.get(direction)})\x1b[0m")
        
        async def do_set(player, args):
            """Set room properties."""
            if not player.is_builder:
                player.send("You don't have building permissions.")
                return
            
            room = self.world.rooms.get(player.room_vnum)
            if not room:
                return
            
            if not args:
                player.send("Usage: set <property> <value>")
                player.send("Properties: name, desc, sector, flag +/-")
                return
            
            parts = args.split(None, 1)
            prop = parts[0].lower()
            value = parts[1] if len(parts) > 1 else ""
            
            if prop == "name":
                room.name = value
                player.send("Room name updated.")
            elif prop == "desc":
                room.desc = value
                player.send("Room description updated.")
            elif prop == "sector":
                valid_sectors = ["city", "forest", "desert", "water", "mountain", "underdark", "plains", "hills"]
                if value in valid_sectors:
                    room.sector = value
                    player.send(f"Sector set to {value}.")
                else:
                    player.send(f"Valid sectors: {', '.join(valid_sectors)}")
            elif prop == "flag" or prop == "flags":
                if value.startswith("+"):
                    flag = value[1:]
                    if flag not in room.flags:
                        room.flags.append(flag)
                    player.send(f"Flag +{flag} added.")
                elif value.startswith("-"):
                    flag = value[1:]
                    room.flags = [f for f in room.flags if f != flag]
                    player.send(f"Flag -{flag} removed.")
                else:
                    player.send(f"Current flags: {', '.join(room.flags)}")
            else:
                player.send(f"Unknown property: {prop}")
        
        # Register builder commands (hidden, admin-level)
        for cmd_name, func, aliases in [
            ("dig", do_dig, None),
            ("link", do_link, None),
            ("set", do_set, None),
        ]:
            pass  # Will be registered when builder system is ready
        
        # ─── Channels ─────────────────────────────────────────────
        async def do_gtell(player, args):
            """Group/guild tell."""
            if not args:
                return
            msg = f"[Group] {player.name}: {args}"
            # Broadcast to party members
            for p in self.world.players:
                if p.is_connected() and p.save_data.get("party") == player.save_data.get("party"):
                    p.send(f"\x1b[32m{msg}\x1b[0m")
        self.register("gtell", do_gtell, aliases=["grouptell"])
        
        # ─── Sudo (admin) ─────────────────────────────────────────
        async def do_sudo(player, args):
            """Execute a command as another player."""
            if not player.is_builder and not player.is_admin:
                player.send("You don't have permission.")
                return
            if not args:
                return
            # Parse: sudo <target> <command>
            parts = args.split(None, 1)
            if len(parts) < 2:
                return
            target_name = parts[0].lower()
            cmd_to_run = parts[1]
            
            for p in self.world.players:
                if p.is_connected() and p.name.lower() == target_name:
                    await self.execute(p, cmd_to_run)
                    break
        self.register("sudo", do_sudo, hide_help=True)
        
        # ─── OOC ──────────────────────────────────────────────────
        async def do_ooc(player, args):
            """Out of character chat."""
            if not args:
                return
            msg = f"[OOC] {player.name}: {args}"
            for p in self.world.players:
                if p.is_connected():
                    p.send(f"\x1b[37m{msg}\x1b[0m")
        self.register("ooc", do_ooc, aliases=["ooc"])
        
        # ═══════════════════════════════════════════════════════════════
        # ─── Quest Commands ───────────────────────────────────────────
        # ═══════════════════════════════════════════════════════════════
        
        async def do_quest(player, args):
            """Quest system — view, accept, or list quests."""
            qm = self.world.quest_manager
            
            if not args:
                # Show active quests
                qm.list_active_quests(player)
                return
            
            parts = args.split(None, 1)
            action = parts[0].lower()
            rest = parts[1] if len(parts) > 1 else ""
            
            if action == "list":
                # List all available quests in the current room
                room = self.world.rooms.get(player.room_vnum)
                if not room:
                    return
                # Find quest givers in room
                quests_offered = []
                for mob_id in room.mobs:
                    mob = self.world.entities.get(mob_id)
                    if mob and hasattr(mob, 'template') and mob.template:
                        qs = qm.get_quests_for_mob(mob.template.vnum)
                        quests_offered.extend(qs)
                
                if not quests_offered:
                    player.send("No one here offers quests.")
                    return
                
                player.send("\x1b[33mAvailable Quests:\x1b[0m")
                for q in quests_offered:
                    can, reason = qm.can_start_quest(player, q.quest_id)
                    status = "\x1b[32mavailable\x1b[0m" if can else f"\x1b[31m{reason}\x1b[0m"
                    player.send(f"  \x1b[36m{q.name:<25}\x1b[0m {status}")
                    player.send(f"    {q.desc}")
            
            elif action == "accept":
                if not rest:
                    player.send("Usage: quest accept <quest_name>")
                    return
                # Find quest by name
                for q in qm.quest_defs.values():
                    if rest.lower() in q.name.lower():
                        player.send(q.offer_text)
                        player.send("\n\x1b[33mType 'quest yes' to accept or 'quest no' to decline.\x1b[0m")
                        player._pending_quest = q.quest_id
                        return
                player.send(f"No quest named '{rest}'.")
            
            elif action == "yes":
                qid = getattr(player, '_pending_quest', None)
                if not qid:
                    player.send("Nothing to accept.")
                    return
                qm.accept_quest(player, qid)
                player._pending_quest = None
            
            elif action == "no":
                qid = getattr(player, '_pending_quest', None)
                if qid:
                    quest = qm.get_quest(qid)
                    if quest and quest.decline_text:
                        player.send(quest.decline_text)
                    player._pending_quest = None
                else:
                    player.send("Nothing to decline.")
            
            elif action == "info":
                if not rest:
                    player.send("Usage: quest info <quest_name>")
                    return
                for q in qm.quest_defs.values():
                    if rest.lower() in q.name.lower():
                        player.send(f"\x1b[33m=== {q.name} ===\x1b[0m")
                        player.send(f"Type: {q.quest_type}")
                        player.send(f"Desc: {q.desc}")
                        player.send(f"Min Level: {q.min_level}")
                        if q.prereq_quests:
                            prereq_names = [qm.get_quest(p).name for p in q.prereq_quests if qm.get_quest(p)]
                            player.send(f"Requires: {', '.join(prereq_names)}")
                        player.send(f"Rewards: {q.reward_xp} XP, {q.reward_gold} gold")
                        return
                player.send(f"No quest named '{rest}'.")
            
            else:
                player.send("Usage: quest [list|accept|info] [name]")
        
        self.register("quest", do_quest, aliases=["qst", "quests"])
        
        async def do_journal(player, args):
            """View your quest journal — completed and active quests."""
            if not player.quests:
                player.send("Your journal is empty.")
                return
            
            active = [(qid, qs) for qid, qs in player.quests.items() if qs.status == "active"]
            completed = [(qid, qs) for qid, qs in player.quests.items() if qs.status == "completed"]
            
            if active:
                player.send("\x1b[33m=== Active Quests ===\x1b[0m")
                for qid, qs in active:
                    quest = self.world.quest_manager.get_quest(qid)
                    if quest:
                        player.send(f"\x1b[32m{quest.name}\x1b[0m")
                        if quest.quest_type == "kill":
                            for mob_vnum, needed in quest.kill_targets.items():
                                mob_t = self.world.mob_templates.get(mob_vnum)
                                mob_name = mob_t.short_desc if mob_t else f"mob#{mob_vnum}"
                                current = qs.progress.get(str(mob_vnum), 0)
                                player.send(f"  Kill {mob_name}: {current}/{needed}")
                        elif quest.quest_type == "explore":
                            visited = qs.progress.get("visited_rooms", [])
                            player.send(f"  Explore: {len(visited)}/{len(quest.explore_targets)} locations")
                        player.send("")
            
            if completed:
                player.send(f"\x1b[33m=== Completed Quests ({len(completed)}) ===\x1b[0m")
                for qid, qs in completed:
                    quest = self.world.quest_manager.get_quest(qid)
                    if quest:
                        player.send(f"  \x1b[32m\u2713 {quest.name}\x1b[0m")
        
        self.register("journal", do_journal, aliases=["j", "log"])
        
        async def do_complete(player, args):
            """Complete a quest (must be at the quest giver)."""
            if not args:
                player.send("Complete what quest?")
                return
            
            qm = self.world.quest_manager
            
            # Find quest by name
            quest = None
            for q in qm.quest_defs.values():
                if args.lower() in q.name.lower():
                    quest = q
                    break
            
            if not quest:
                player.send(f"No quest named '{args}'.")
                return
            
            # Check if quest is active
            qstate = player.quests.get(quest.quest_id)
            if not qstate or qstate.status != "active":
                player.send("You don't have that quest active.")
                return
            
            # Check if giver is in room
            room = self.world.rooms.get(player.room_vnum)
            giver_found = False
            if room:
                for mob_id in room.mobs:
                    mob = self.world.entities.get(mob_id)
                    if mob and hasattr(mob, 'template') and mob.template:
                        if mob.template.vnum == quest.giver_vnum:
                            giver_found = True
                            break
            
            if not giver_found:
                player.send("The quest giver isn't here. Return to them to complete this quest.")
                return
            
            # Show completion text
            if quest.complete_text:
                player.send(quest.complete_text)
            
            qm.complete_quest(player, quest.quest_id)
        
        self.register("complete", do_complete, aliases=["done", "finish"])
        
        # ═══════════════════════════════════════════════════════════════
        # ─── Channel Commands ─────────────────────────────────────────
        # ═══════════════════════════════════════════════════════════════
        
        async def do_newbie(player, args):
            """Newbie channel — help for new players."""
            if not args:
                player.send("Usage: newbie <message>")
                return
            msg = f"[Newbie] {player.name}: {args}"
            for p in self.world.players:
                if p.is_connected():
                    p.send(f"\x1b[32m{msg}\x1b[0m")
        self.register("newbie", do_newbie, aliases=["n", "nch"])
        
        async def do_auction(player, args):
            """Auction channel — buy/sell announcements."""
            if not args:
                player.send("Usage: auction <message>")
                return
            msg = f"[Auction] {player.name}: {args}"
            for p in self.world.players:
                if p.is_connected():
                    p.send(f"\x1b[33m{msg}\x1b[0m")
        self.register("auction", do_auction, aliases=["auc", "auction"])
        
        async def do_chat(player, args):
            """Local chat — everyone in the same room can hear."""
            if not args:
                player.send("Usage: chat <message>")
                return
            msg = f"{player.name} chats, '{args}'"
            for eid in (self.world.rooms.get(player.room_vnum, {}).contents or []):
                entity = self.world.entities.get(eid)
                if entity and entity is not player:
                    entity.send(f"\x1b[37m{msg}\x1b[0m")
            player.send(f"\x1b[37mYou chat, '{args}'\x1b[0m")
        self.register("chat", do_chat, aliases=["ch"])
        
        async def do_announce(player, args):
            """Announce — broadcast to all players (admin only)."""
            if not player.is_admin:
                player.send("You don't have permission.")
                return
            if not args:
                player.send("Announce what?")
                return
            msg = f"\x1b[31m\x1b[1m[Announcement] {args}\x1b[0m"
            for p in self.world.players:
                if p.is_connected():
                    p.send(msg)
        self.register("announce", do_announce, aliases=["broadcast", "ann"], hide_help=True)
        
        # ═══════════════════════════════════════════════════════════════
        # ─── Container Commands ───────────────────────────────────────
        # ═══════════════════════════════════════════════════════════════
        
        async def do_put(player, args):
            """Put an item into a container."""
            if not args:
                player.send("Put what in what?")
                return
            parts = args.lower().split(" in ", 1)
            if len(parts) < 2:
                parts = args.lower().split(None, 1)
                if len(parts) < 2:
                    player.send("Usage: put <item> <container>")
                    return
                player.send("Usage: put <item> in <container>")
                return
            
            item_name = parts[0].strip()
            container_name = parts[1].strip()
            
            # Find container in inventory
            container = None
            for inv_item in player.inventory:
                if inv_item.item_type == "container" and container_name in [k.lower() for k in inv_item.keywords]:
                    container = inv_item
                    break
            
            if not container:
                player.send(f"You don't have '{container_name}'.")
                return
            
            # Find item in inventory
            item_to_put = None
            for inv_item in player.inventory:
                if item_name in [k.lower() for k in inv_item.keywords] and inv_item is not container:
                    item_to_put = inv_item
                    break
            
            if not item_to_put:
                player.send(f"You don't have '{item_name}'.")
                return
            
            # Check container capacity
            container_contents = getattr(container, 'contents', [])
            current_weight = sum(getattr(i, 'weight', 0) or 0 for i in container_contents)
            if current_weight + item_to_put.weight > (container.capacity or 0):
                player.send(f"{container.short_desc} is too full.")
                return
            
            # Put item in container
            if item_to_put in player.inventory:
                player.inventory.remove(item_to_put)
            if not hasattr(container, 'contents') or container.contents is None:
                container.contents = []
            container.contents.append(item_to_put)
            player.weight = max(0, player.weight - item_to_put.weight)
            player.send(f"You put {item_to_put.short_desc} in {container.short_desc}.")
        self.register("put", do_put)
        
        async def do_get_from(player, args):
            """Get an item from a container."""
            if not args:
                player.send("Get what from where?")
                return
            parts = args.lower().split(" from ", 1)
            if len(parts) < 2:
                player.send("Usage: get <item> from <container>")
                return
            
            item_name = parts[0].strip()
            container_name = parts[1].strip()
            
            # Find container
            container = None
            for inv_item in player.inventory:
                if inv_item.item_type == "container" and container_name in [k.lower() for k in inv_item.keywords]:
                    container = inv_item
                    break
            
            if not container:
                player.send(f"You don't have '{container_name}'.")
                return
            
            container_contents = getattr(container, 'contents', [])
            item_to_get = None
            for c_item in container_contents:
                if item_name in [k.lower() for k in c_item.keywords]:
                    item_to_get = c_item
                    break
            
            if not item_to_get:
                player.send(f"There is no '{item_name}' in {container.short_desc}.")
                return
            
            # Check weight
            new_weight = player.weight + item_to_get.weight
            if new_weight > player.max_weight:
                player.send(f"{item_to_get.short_desc} is too heavy.")
                return
            
            container_contents.remove(item_to_get)
            player.inventory.append(item_to_get)
            player.weight = new_weight
            player.send(f"You get {item_to_get.short_desc} from {container.short_desc}.")
        
        self.register("get", do_get_from, aliases=["take"], hide_help=True)
        # Re-register the original get as well - but we need to handle the conflict
        # Actually let's just register an alias. The main get command already exists.
        # Let's add "getfrom" as a separate command
        self.register("getfrom", do_get_from, aliases=["grab"], hide_help=True)
        
        async def do_container_inv(player, args):
            """Check what's inside a container."""
            if not args:
                player.send("Usage: look in <container>")
                return
            
            # Find container in inventory or room
            container = None
            for inv_item in player.inventory:
                if inv_item.item_type == "container" and args.lower() in [k.lower() for k in inv_item.keywords]:
                    container = inv_item
                    break
            
            if not container:
                room = self.world.rooms.get(player.room_vnum)
                if room:
                    for item_id in room.items:
                        item = self.world.entities.get(item_id)
                        if item and item.item_type == "container" and args.lower() in [k.lower() for k in item.keywords]:
                            container = item
                            break
            
            if not container:
                player.send(f"You don't see '{args}' here.")
                return
            
            contents = getattr(container, 'contents', [])
            if not contents:
                player.send(f"{container.short_desc} is empty.")
            else:
                player.send(f"{container.short_desc} contains:")
                for c_item in contents:
                    player.send(f"  {c_item.short_desc}")
        
        self.register("container", do_container_inv, aliases=["contents", "con"], hide_help=True)
        
        # ═══════════════════════════════════════════════════════════════
        # ─── Builder Commands (register the ones defined above) ─────
        # ═══════════════════════════════════════════════════════════════
        
        # These were defined but never registered — now register them:
        self.register("dig", do_dig, min_level=50, hide_help=True)
        self.register("link", do_link, min_level=50, hide_help=True)
        self.register("set", do_set, min_level=50, hide_help=True)
        
        async def do_show_zones(player, args):
            """List all zones in the world."""
            if not player.is_builder:
                player.send("Builder access required.")
                return
            player.send("\x1b[33m=== Zones ===\x1b[0m")
            for zname, zone in self.world.zones.items():
                player.send(f"  \x1b[32m{zname}\x1b[0m"
                           f"  Rooms: {len(zone.rooms)}"
                           f"  Vnums: {zone.low_vnum}-{zone.hi_vnum}"
                           f"  Level range: {zone.levels[0]}-{zone.levels[1]}")
        self.register("zones", do_show_zones, min_level=50, hide_help=True)
        
        async def do_room_info(player, args):
            """Show detailed info about the current room."""
            if not player.is_builder:
                player.send("Builder access required.")
                return
            room = self.world.rooms.get(player.room_vnum)
            if not room:
                return
            player.send(f"\x1b[33m=== Room {room.vnum} ===\x1b[0m")
            player.send(f"Name: {room.name}")
            player.send(f"Zone: {room.zone}")
            player.send(f"Sector: {room.sector}")
            player.send(f"Flags: {', '.join(room.flags) if room.flags else 'none'}")
            player.send(f"Coord: {room.coord}")
            player.send("Exits:")
            for direction, exit_obj in room.exits.items():
                target = self.world.rooms.get(exit_obj.target_room)
                target_name = target.name if target else "VOID"
                door_info = ""
                if exit_obj.door:
                    door_info = f" [door: {exit_obj.door.get('name', '')}]"
                player.send(f"  {direction:<6} -> {exit_obj.target_room} ({target_name}){door_info}")
            player.send(f"Mobs: {len(room.mobs)}  Items: {len(room.items)}  Players: {len([e for e in room.contents if e and self.world.entities.get(e) and self.world.entities.get(e).is_player])}")
        self.register("rminfo", do_room_info, min_level=50, hide_help=True)
        
        # ═══════════════════════════════════════════════════════════════
        # ─── Info/Utility Commands ─────────────────────────────────────
        # ═══════════════════════════════════════════════════════════════
        
        async def do_info(player, args):
            """Show game information."""
            player.send("\x1b[33m=== Aylor MUD ===\x1b[0m")
            player.send("A text-based fantasy world.")
            player.send(f"Players online: {len([p for p in self.world.players if p.is_connected()])}")
            player.send(f"Zones: {len(self.world.zones)}")
            player.send(f"Total rooms: {len(self.world.rooms)}")
            player.send(f"Mob types: {len(self.world.mob_templates)}")
            player.send(f"Item types: {len(self.world.item_templates)}")
            player.send(f"\n\x1b[33mTips:\x1b[0m")
            player.send("  Type 'help' for commands")
            player.send("  Type 'quest list' to see available quests")
            player.send("  Type 'journal' to view your quests")
            player.send("  Type 'time' for weather and time")
        self.register("info", do_info, aliases=["version"])
        
        async def do_bind(player, args):
            """Set your bind/recall point to the current room."""
            if player.fighting:
                player.send("You can't do that in combat!")
                return
            room = self.world.rooms.get(player.room_vnum)
            if not room:
                return
            if "safe" not in room.flags:
                player.send("You can only bind in a safe room.")
                return
            player.save_data["bind_vnum"] = player.room_vnum
            player.send(f"\x1b[33mYour recall point has been set to '{room.name}'.\x1b[0m")
        self.register("bind", do_bind)
        
        async def do_socials(player, args):
            """List available social emotes."""
            player.send("\x1b[33mSocials:\x1b[0m")
            socials = ["smile", "frown", "laugh", "cry", "wave", "bow", "curtsey",
                       "applaud", "cheer", "nod", "shake", "grin", "poke", "hug"]
            cols = 4
            for i in range(0, len(socials), cols):
                player.send("  " + ", ".join(f"{s:<12}" for s in socials[i:i+cols]))
            player.send("\nUsage: <social> [target]")
        self.register("socials", do_socials)
        
        # ─── Dynamic socials ───────────────────────────────────────
        social_actions = {
            "smile": "smiles at {target}.", "frown": "frowns.", "laugh": "laughs.",
            "cry": "cries.", "wave": "waves at {target}.", "bow": "bows to {target}.",
            "curtsey": "curtseys.", "applaud": "applauds.", "cheer": "cheers!",
            "nod": "nods.", "shake": "shakes {poss} head.", "grin": "grins.",
            "poke": "pokes {target}.", "hug": "hugs {target}."
        }
        for sname, sdesc in social_actions.items():
            def make_social(sdesc=sname, sname=sname):
                def fn(player, args):
                    target = args.strip() if args else None
                    if target:
                        msg = f"{player.name} {sdesc.replace('{target}', target).replace('{poss}', 'their')}"
                    else:
                        msg = f"{player.name} {sdesc.replace('{target}', 'them').replace('{poss}', 'their')}"
                    player.send(f"\x1b[35m{msg}\x1b[0m")
                    for eid in (self.world.rooms.get(player.room_vnum, {}).contents or []):
                        entity = self.world.entities.get(eid)
                        if entity and entity is not player:
                            entity.send(f"\x1b[35m{msg}\x1b[0m")
                return fn
            self.register(sname, make_social(sname=sname, sdesc=sdesc))
    
    async def execute(self, player, raw):
        """Parse and execute a command string."""
        if not raw or not raw.strip():
            return
        
        raw = raw.strip()
        player.last_cmd_time = time.time()
        
        # Split into command and arguments
        parts = raw.split(None, 1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # Check if player is dead
        if player.hp <= 0 and player.position == "dead":
            player.send("You can't do that while dead.")
            return
        
        # Find command
        cmd = self.commands.get(cmd_name)
        if not cmd:
            # Check if it's a direction
            for d in ["north", "south", "east", "west", "up", "down", "n", "s", "e", "w", "u", "d"]:
                if cmd_name == d:
                    self._move_player(player, d)
                    return
            # Check if it's social/emote
            # Unknown command
            player.send(f"Huh? Type 'help' for commands.")
            return
        
        # Check fighting restriction for movement commands
        if player.fighting and cmd_name in ("north", "south", "east", "west", "up", "down", "n", "s", "e", "w", "u", "d"):
            player.send("You can't move while fighting! Try 'flee'.")
            return
        
        try:
            result = cmd["func"](player, args)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            player.send(f"\x1b[31mAn error occurred: {str(e)}\x1b[0m")
            traceback.print_exc()
    
    def _do_look_at(self, player, room, target):
        """Look at a specific entity or item."""
        target_lower = target.lower()

        # Check room extra descriptions
        if target_lower in room.extra_descs:
            player.send(room.extra_descs[target_lower])
            return

        # Check mobs in room
        for mob_id in room.mobs:
            mob = self.world.entities.get(mob_id)
            if mob and (target_lower in [k.lower() for k in mob.keywords] or target_lower == mob.name.lower()):
                player.send(mob.long_desc or f"You see {mob.short_desc}.")
                return

        # Check players in room
        for eid in room.contents or []:
            entity = self.world.entities.get(eid)
            if entity and entity.is_player and entity is not player:
                if target_lower in entity.name.lower():
                    player.send(f"You see {entity.name}.")
                    return

        # Check items in room
        for item_id in room.items:
            item = self.world.entities.get(item_id)
            if item and target_lower in [k.lower() for k in item.keywords]:
                player.send(item.long_desc or f"You see {item.short_desc}.")
                return

        # Check player's inventory
        for item in player.inventory:
            if target_lower in [k.lower() for k in item.keywords]:
                player.send(item.long_desc or f"You see {item.short_desc}.")
                return

        # Check equipment
        for slot in cfg.SLOTS:
            item = player.equipment.get(slot)
            if item and target_lower in [k.lower() for k in item.keywords]:
                player.send(item.long_desc or f"You see {item.short_desc}.")
                return

        player.send(f"You don't see '{target}' here.")

    def _handle_door(self, player, direction, action):
        """Handle open/close on doors."""
        room = self.world.rooms.get(player.room_vnum)
        if not room:
            return

        door_dir = direction.split()[0] if direction.split() else direction
        exit_obj = room.get_exit(door_dir)

        if not exit_obj or not exit_obj.door:
            player.send(f"There is no door {door_dir}.")
            return

        door = exit_obj.door

        if action == "open":
            if door.get("locked"):
                player.send("The door is locked.")
                return
            if not door.get("closed"):
                player.send("It's already open.")
                return
            door["closed"] = False
            player.send(f"You open the {door.get('name', 'door')}.")
            self.world.broadcast_to_room(player.room_vnum,
                f"{player.name} opens the {door.get('name', 'door')}.",
                exclude=[player.entity_id])

        elif action == "close":
            if door.get("closed"):
                player.send("It's already closed.")
                return
            door["closed"] = True
            player.send(f"You close the {door.get('name', 'door')}.")
            self.world.broadcast_to_room(player.room_vnum,
                f"{player.name} closes the {door.get('name', 'door')}.",
                exclude=[player.entity_id])

    def _calc_coord(self, coord, direction):
        """Calculate new coordinates from a direction."""
        if not coord:
            return None
        x, y, z = coord
        delta = {"north": (0, 1, 0), "south": (0, -1, 0), "east": (1, 0, 0),
                  "west": (-1, 0, 0), "up": (0, 0, 1), "down": (0, 0, -1)}
        dx, dy, dz = delta.get(direction, (0, 0, 0))
        return (x + dx, y + dy, z + dz)

    def _move_player(self, player, direction, dest_vnum=None):
        """Synchronous movement handler. If dest_vnum is set, teleport directly."""
        if player.fighting and direction is not None:
            # Try to break combat, not move while fighting
            self.combat.flee(player)
            return
        
        if dest_vnum is not None:
            # Direct teleport
            old_vnum = player.room_vnum
            self.world.move_entity(player, dest_vnum)
            if old_vnum != dest_vnum:
                self.world.broadcast_to_room(old_vnum, f"{player.name} disappears.", exclude=[player.entity_id])
                self.world.broadcast_to_room(dest_vnum, f"{player.name} appears.", exclude=[player.entity_id])
            new_room = self.world.rooms.get(dest_vnum)
            if new_room:
                player.send(new_room.describe(player, brief=player.brief))
            return
        
        room = self.world.rooms.get(player.room_vnum)
        if not room:
            return
        
        exit_obj = room.get_exit(direction)
        if not exit_obj:
            player.send(f"You can't go that way.")
            return
        
        if exit_obj.door and exit_obj.door.get("closed"):
            player.send(f"The door is closed.")
            return
        
        # Movement cost
        cost = {"city": 0, "plains": 1, "forest": 2, "hills": 2, "mountain": 3, "water": 4, "underdark": 2}
        mv_cost = cost.get(room.sector, 1)
        if player.movement < mv_cost:
            player.send("You are too exhausted to move.")
            return
        
        player.movement -= mv_cost
        
        # Move
        old_vnum = player.room_vnum
        self.world.move_entity(player, exit_obj.target_room)
        
        # Regenerate mana slightly with movement
        player.mana = min(player.max_mana, player.mana + 1)
        
        # Notify rooms
        self.world.broadcast_to_room(old_vnum, f"{player.name} leaves {direction}.", exclude=[player.entity_id])
        self.world.broadcast_to_room(player.room_vnum, f"{player.name} arrives.", exclude=[player.entity_id])
        
        # Auto-look
        new_room = self.world.rooms.get(player.room_vnum)
        if new_room:
            player.send(new_room.describe(player, brief=player.brief))
        
        # Check aggressive mobs
        new_room = self.world.rooms.get(player.room_vnum)
        if new_room:
            for mob_id in list(new_room.mobs):
                mob = self.world.entities.get(mob_id)
                if mob and mob.hp > 0:
                    self.world.mob_ai.check_aggression(mob, player.room_vnum)
