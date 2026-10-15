"""
Mob AI — behavior trees for autonomous mob movement and combat.
"""
import asyncio, random, time, math

class MobAI:
    """Handles AI updates for all mobs in the world."""
    
    def __init__(self, world):
        self.world = world
        self.ai_cycles = 0
    
    async def tick(self):
        """Process one AI tick for all mobs."""
        self.ai_cycles += 1
        
        for mob in list(self.world.mobs):
            if mob.hp <= 0:
                continue
            if mob.fighting:
                continue  # Combat handled by combat system
            
            # Update AI state
            self.update_ai_state(mob)
    
    def update_ai_state(self, mob):
        """Update a mob's AI state based on its current situation."""
        state = mob.ai_state
        
        if state == "idle":
            # Check if should wander
            if random.random() < 0.02:  # ~2% chance per tick
                mob.ai_state = "wander"
        
        elif state == "wander":
            self.do_wander(mob)
        
        elif state == "hunt":
            self.do_hunt(mob)
        
        elif state == "return":
            self.do_return(mob)
        
        elif state == "flee":
            self.do_flee(mob)
    
    def do_wander(self, mob):
        """Move the mob in a random direction."""
        room = self.world.rooms.get(mob.room_vnum)
        if not room or not room.exits:
            mob.ai_state = "idle"
            return
        
        # Pick a random exit
        direction = random.choice(list(room.exits.keys()))
        exit_obj = room.exits[direction]
        
        # Don't go through closed doors
        if exit_obj.door and exit_obj.door.get("closed"):
            mob.ai_state = "idle"
            return
        
        # Check if wander range is exceeded
        if mob.home_vnum is not None:
            dist = self.room_distance(mob.room_vnum, mob.home_vnum)
            if dist > 10:
                mob.ai_state = "return"
                return
        
        # Move
        self.world.move_entity(mob, exit_obj.target_room)
        
        # Chance to stop wandering
        if random.random() < 0.3:
            mob.ai_state = "idle"
    
    def do_return(self, mob):
        """Return mob to its home room."""
        if mob.home_vnum is None:
            mob.ai_state = "idle"
            return
        
        if mob.room_vnum == mob.home_vnum:
            mob.ai_state = "idle"
            return
        
        # Pathfind toward home using simple direction heuristic
        path = self.simple_pathfind(mob.room_vnum, mob.home_vnum)
        if path:
            self.world.move_entity(mob, path[0])
        else:
            self.world.move_entity(mob, mob.home_vnum)
            mob.ai_state = "idle"
    
    def do_flee(self, mob):
        """Flee in a random direction."""
        room = self.world.rooms.get(mob.room_vnum)
        if not room or not room.exits:
            mob.ai_state = "idle"
            return
        
        direction = random.choice(list(room.exits.keys()))
        exit_obj = room.exits[direction]
        
        if not (exit_obj.door and exit_obj.door.get("closed")):
            self.world.move_entity(mob, exit_obj.target_room)
        
        # Check if should stop fleeing
        if mob.fighting is None:
            mob.ai_state = "idle"
    
    def simple_pathfind(self, from_vnum, to_vnum):
        """Simple BFS pathfinding between rooms."""
        if from_vnum == to_vnum:
            return []
        
        visited = {from_vnum}
        queue = [(from_vnum, [])]
        
        while queue and len(visited) < 50:  # Limit search depth
            current, path = queue.pop(0)
            room = self.world.rooms.get(current)
            if not room:
                continue
            
            for direction, exit_obj in room.exits.items():
                target = exit_obj.target_room
                if target in visited:
                    continue
                if exit_obj.door and exit_obj.door.get("closed"):
                    continue
                
                if target == to_vnum:
                    return path + [target]
                
                visited.add(target)
                queue.append((target, path + [target]))
        
        return []  # No path found
    
    def room_distance(self, from_vnum, to_vnum):
        """Approximate room distance."""
        path = self.simple_pathfind(from_vnum, to_vnum)
        return len(path)
    
    def check_aggression(self, mob, player_room_vnum):
        """Check if mob should attack players in its room."""
        if not hasattr(mob, 'template') or not mob.template:
            return
        
        if "aggressive" not in mob.template.flags:
            return
        if mob.fighting:
            return
        
        room = self.world.rooms.get(mob.room_vnum)
        if not room:
            return
        
        # Check if players are in the room
        for entity_id in room.mobs:
            entity = self.world.entities.get(entity_id)
            if entity and entity.is_player and entity.hp > 0:
                # Aggro!
                from .combat import CombatSystem
                combat = CombatSystem(self.world)
                combat.start_combat(mob, entity)
                break


class MobSpawner:
    """Handles periodic respawning of mobs throughout the world."""
    
    def __init__(self, world):
        self.world = world
        self.pending_respawns = []  # [(template_vnum, room_vnum, delay, time), ...]
    
    def schedule_spawn(self, template_vnum, room_vnum, delay=60):
        """Schedule a mob to respawn after delay seconds."""
        spawn_time = time.time() + delay
        self.pending_respawns.append((template_vnum, room_vnum, delay, spawn_time))
    
    async def tick(self):
        """Process pending respawns."""
        now = time.time()
        still_pending = []
        
        for template_vnum, room_vnum, delay, spawn_time in self.pending_respawns:
            if now >= spawn_time:
                self.spawn_mob(template_vnum, room_vnum)
            else:
                still_pending.append((template_vnum, room_vnum, delay, spawn_time))
        
        self.pending_respawns = still_pending
    
    def spawn_mob(self, template_vnum, room_vnum):
        """Spawn a mob from template into a room."""
        template = self.world.mob_templates.get(template_vnum)
        if not template:
            return None
        
        from .entity import Mob
        mob = Mob(template)
        mob.spawn_vnum = room_vnum
        mob.home_vnum = room_vnum
        
        self.world.add_mob(mob)
        self.world.move_entity(mob, room_vnum)
        return mob
