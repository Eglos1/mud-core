"""
Combat system — attack resolution, damage, death, combat loop.
"""
import asyncio, random, time, math
from .config import Config
cfg = Config()

class CombatSystem:
    """Manages all combat between entities."""
    
    def __init__(self, world):
        self.world = world
        self.combatants = {}  # entity_id -> {opponent_id, round_timer, start_time}
    
    def start_combat(self, attacker, target):
        """Initiate combat between two entities."""
        if attacker.fighting:
            return  # Already in combat
        
        attacker.fighting = target.entity_id
        target.fighting = attacker.entity_id
        
        # Notify room
        self.world.broadcast_to_room(attacker.room_vnum,
            f"\x1b[31m{attacker.short_desc} attacks {target.short_desc}!\x1b[0m",
            exclude=[attacker.entity_id])
        attacker.send(f"\x1b[31mYou attack {target.short_desc}!\x1b[0m")
        target.send(f"\x1b[31m{attacker.short_desc} attacks you!\x1b[0m")
        
        # Immediate first strike
        self.resolve_round(attacker, target)
    
    def stop_combat(self, entity):
        """Remove entity from combat."""
        if not entity.fighting:
            return
        
        opponent = self.world.entities.get(entity.fighting)
        entity.fighting = None
        entity.combat_round = 0
        entity.fled = False
        
        if opponent and opponent.fighting == entity.entity_id:
            opponent.fighting = None
            opponent.combat_round = 0
    
    def resolve_round(self, attacker, defender):
        """Resolve one round of combat between attacker and defender."""
        if not attacker or not defender:
            return
        if attacker.hp <= 0 or defender.hp <= 0:
            self.stop_combat(attacker)
            self.stop_combat(defender)
            return
        
        # Attacker attacks defender
        result = attacker.calculate_attack(defender)
        
        if result["hit"]:
            damage = result["damage"]
            died = defender.take_damage(damage, attacker, attacker.weapon_type())
            
            # Determine damage string
            wtype = cfg.WEAPON_DAMAGE.get(attacker.weapon_type(), "bash")
            if result["crit"]:
                verb = f"critically {wtype}s"
            elif damage > 15:
                verb = f"{wtype}s"
            elif damage > 8:
                verb = f"{wtype}s"
            else:
                verb = f"{wtype}s"
            
            log_msg = f"Your {verb} {defender.short_desc}. [{damage}]"
            room_msg = f"{attacker.short_desc} {verb} {defender.short_desc}. [{damage}]"
            
            attacker.send(f"\x1b[33m{log_msg}\x1b[0m")
            if defender.is_player:
                defender.send(f"\x1b[31m{attacker.short_desc} {verb} you! [{damage}]\x1b[0m")
            else:
                self.world.broadcast_to_room(defender.room_vnum, 
                    f"\x1b[33m{room_msg}\x1b[0m",
                    exclude=[attacker.entity_id, defender.entity_id if defender.is_player else None])
            
            if died:
                return  # Defender died
        else:
            if result["dodge"]:
                attacker.send(f"\x1b[34m{defender.short_desc} dodges your attack.\x1b[0m")
            elif result["parry"]:
                attacker.send(f"\x1b[34m{defender.short_desc} parries your attack.\x1b[0m")
            else:
                attacker.send(f"\x1b[34mYour attack misses {defender.short_desc}.\x1b[0m")
        
        # Defender counterattacks (if still alive and in combat)
        if defender.fighting == attacker.entity_id and defender.hp > 0:
            result2 = defender.calculate_attack(attacker)
            
            if result2["hit"]:
                damage2 = result2["damage"]
                died2 = attacker.take_damage(damage2, defender, defender.weapon_type())
                
                wtype2 = cfg.WEAPON_DAMAGE.get(defender.weapon_type(), "bash")
                log_msg2 = f"{defender.short_desc} {wtype2}s you! [{damage2}]"
                room_msg2 = f"{defender.short_desc} {wtype2}s {attacker.short_desc}. [{damage2}]"
                
                defender.send(f"\x1b[33mYour {wtype2} {attacker.short_desc}. [{damage2}]\x1b[0m")
                attacker.send(f"\x1b[31m{log_msg2}\x1b[0m")
                self.world.broadcast_to_room(attacker.room_vnum,
                    f"\x1b[33m{room_msg2}\x1b[0m",
                    exclude=[attacker.entity_id, defender.entity_id if defender.is_player else None])
                
                if died2:
                    return  # Attacker died
            else:
                if result2["dodge"]:
                    defender.send(f"\x1b[34m{attacker.short_desc} dodges your attack.\x1b[0m")
                elif result2["parry"]:
                    defender.send(f"\x1b[34m{attacker.short_desc} parries your attack.\x1b[0m")
                else:
                    defender.send(f"\x1b[34mYour attack misses {attacker.short_desc}.\x1b[0m")
        
        attacker.combat_round += 1
    
    async def tick_combat(self):
        """Process combat for all active combatants (called from game loop)."""
        # Build list of combat pairs
        processed = set()
        for eid, entity in list(self.world.entities.items()):
            if eid in processed:
                continue
            if not entity.fighting:
                continue
            if entity.hp <= 0:
                self.stop_combat(entity)
                continue
            
            # Check same room
            opponent = self.world.entities.get(entity.fighting)
            if not opponent or opponent.hp <= 0:
                self.stop_combat(entity)
                continue
            
            if entity.room_vnum != opponent.room_vnum:
                # Combat broken due to movement
                self.stop_combat(entity)
                self.stop_combat(opponent)
                entity.send("Combat broken — you are no longer in the same room.")
                continue
            
            # Resolve one round
            self.resolve_round(entity, opponent)
            processed.add(entity.entity_id)
            processed.add(opponent.entity_id)
            
            # Small delay between combat pairs
            await asyncio.sleep(0.05)
    
    def flee(self, entity):
        """Attempt to flee from combat."""
        room = self.world.rooms.get(entity.room_vnum)
        if not room or not room.exits:
            entity.send("There is nowhere to flee!")
            return False
        
        # Pick random exit
        direction = random.choice(list(room.exits.keys()))
        exit_obj = room.exits[direction]
        
        # Check if door is closed
        if exit_obj.door and exit_obj.door.get("closed"):
            # Try to open
            entity.send(f"The {direction} exit is closed!")
            return False
        
        # Move
        self.stop_combat(entity)
        self.world.move_entity(entity, exit_obj.target_room)
        entity.send(f"\x1b[33mYou flee {direction}!\x1b[0m")
        entity.fled = True
        self.world.broadcast_to_room(entity.room_vnum,
            f"{entity.short_desc} flees {direction}.")
        return True
