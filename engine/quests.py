"""
Quest system — quest definitions, tracking, and rewards.
"""
import time, random, json
from pathlib import Path
from .config import Config
cfg = Config()

class QuestDef:
    """Definition of a quest template."""
    def __init__(self, quest_id, name):
        self.quest_id = quest_id
        self.name = name
        self.desc = ""
        self.quest_type = "kill"  # kill, fetch, explore, deliver, escort
        self.giver_vnum = 0       # Mob template vnum who gives the quest
        self.reward_xp = 0
        self.reward_gold = 0
        self.reward_items = []    # [(item_vnum, count), ...]
        self.reward_practices = 0
        self.reward_trains = 0
        
        # Kill quest: {mob_vnum: count_needed}
        self.kill_targets = {}
        
        # Fetch quest: {item_vnum: count_needed}
        self.fetch_targets = {}
        
        # Explore quest: [room_vnum, ...]
        self.explore_targets = []
        
        # Deliver quest: target_mob_vnum, message
        self.deliver_to = None
        self.deliver_item_vnum = None
        self.deliver_message = ""
        
        # Requirements
        self.min_level = 1
        self.max_level = 99
        self.prereq_quests = []  # quest_ids that must be completed first
        
        # Repeatability
        self.repeatable = False
        self.cooldown = 0  # seconds before repeatable
        
        # Dialogue
        self.offer_text = ""
        self.accept_text = ""
        self.progress_text = ""
        self.complete_text = ""
        self.decline_text = ""
        
    def to_dict(self):
        return {
            "quest_id": self.quest_id, "name": self.name, "desc": self.desc,
            "quest_type": self.quest_type, "giver_vnum": self.giver_vnum,
            "reward_xp": self.reward_xp, "reward_gold": self.reward_gold,
            "reward_items": self.reward_items,
            "reward_practices": self.reward_practices,
            "reward_trains": self.reward_trains,
            "kill_targets": self.kill_targets,
            "fetch_targets": self.fetch_targets,
            "explore_targets": self.explore_targets,
            "deliver_to": self.deliver_to,
            "deliver_item_vnum": self.deliver_item_vnum,
            "deliver_message": self.deliver_message,
            "min_level": self.min_level, "max_level": self.max_level,
            "prereq_quests": self.prereq_quests,
            "repeatable": self.repeatable, "cooldown": self.cooldown,
            "offer_text": self.offer_text, "accept_text": self.accept_text,
            "progress_text": self.progress_text,
            "complete_text": self.complete_text,
            "decline_text": self.decline_text,
        }
    
    @staticmethod
    def from_dict(d):
        q = QuestDef(d["quest_id"], d["name"])
        for attr in ["desc", "quest_type", "giver_vnum", "reward_xp", "reward_gold",
                      "reward_items", "reward_practices", "reward_trains",
                      "kill_targets", "fetch_targets", "explore_targets",
                      "deliver_to", "deliver_item_vnum", "deliver_message",
                      "min_level", "max_level", "prereq_quests",
                      "repeatable", "cooldown",
                      "offer_text", "accept_text", "progress_text",
                      "complete_text", "decline_text"]:
            if attr in d:
                setattr(q, attr, d[attr])
        return q


class QuestState:
    """Per-player quest tracking state."""
    def __init__(self, quest_id):
        self.quest_id = quest_id
        self.status = "inactive"  # inactive, active, completed
        self.progress = {}  # type-specific: {target: count}
        self.completed_at = 0
        self.cooldown_until = 0
        
    def to_dict(self):
        return {
            "quest_id": self.quest_id, "status": self.status,
            "progress": self.progress, "completed_at": self.completed_at,
            "cooldown_until": self.cooldown_until
        }
    
    @staticmethod
    def from_dict(d):
        q = QuestState(d["quest_id"])
        q.status = d.get("status", "inactive")
        q.progress = d.get("progress", {})
        q.completed_at = d.get("completed_at", 0)
        q.cooldown_until = d.get("cooldown_until", 0)
        return q


class QuestManager:
    """Manages all quest definitions and player quest states."""
    
    def __init__(self, world):
        self.world = world
        self.quest_defs = {}  # quest_id -> QuestDef
        self._loaded = False
    
    def load_default_quests(self):
        """Create the default set of quests."""
        quests = []
        
        # Q1: Rat Trouble (kill quest)
        q1 = QuestDef("rat_trouble", "Rat Trouble")
        q1.desc = "The Temple grounds are overrun with giant rats! Kill 5 of them."
        q1.quest_type = "kill"
        q1.giver_vnum = 10  # Priest of Aylor
        q1.kill_targets = {1: 5}  # 5 giant rats
        q1.reward_xp = 300
        q1.reward_gold = 25
        q1.reward_practices = 2
        q1.min_level = 1
        q1.offer_text = (
            "The priest looks at you with concern.\r\n"
            "\"Welcome to the Temple of Aylor. I'm afraid we have a bit of a problem. "
            "The sewers beneath the city have spawned giant rats that are terrorizing "
            "the gardens. Could you please kill five of them for us?\""
        )
        q1.accept_text = "\"Excellent! The groundskeepers will be relieved. Return to me when you're done.\""
        q1.progress_text = "\"Have you dealt with those rats yet? I've counted only {killed} so far.\""
        q1.complete_text = (
            "\"You've cleared out the rats! Thank you, friend. Please accept this reward.\"\r\n"
            "The priest hands you some gold coins."
        )
        q1.decline_text = "\"Very well. Perhaps another time.\""
        quests.append(q1)
        
        # Q2: Forest Pests (kill quest)
        q2 = QuestDef("forest_pests", "Forest Pests")
        q2.desc = "The Whisperwood is overrun with snakes and wolves. Kill 3 garden snakes and 2 grey wolves."
        q2.quest_type = "kill"
        q2.giver_vnum = 10  # Same priest
        q2.kill_targets = {3: 3, 5: 2}  # 3 snakes, 2 wolves
        q2.reward_xp = 800
        q2.reward_gold = 75
        q2.reward_practices = 3
        q2.reward_items = [(1009, 2)]  # 2 health potions
        q2.min_level = 3
        q2.prereq_quests = ["rat_trouble"]
        q2.offer_text = (
            "\"You handled those rats well. Now I have another task — the Whisperwood "
            "to the east has become dangerous. Garden snakes and grey wolves are straying "
            "too close to the city. Thin their numbers for us, would you?\""
        )
        q2.accept_text = "\"Good luck in the forest. Be careful of the wolves.\""
        q2.complete_text = (
            "\"You've made the forest safer for everyone. Well done!\""
        )
        quests.append(q2)
        
        # Q3: Cave Expedition (explore quest)
        q3 = QuestDef("cave_expedition", "Cave Expedition")
        q3.desc = "Explore the dark cave in the hills and report back what you find."
        q3.quest_type = "explore"
        q3.giver_vnum = 11  # Explorer
        q3.explore_targets = [3041]  # Cave Passage
        q3.reward_xp = 1500
        q3.reward_gold = 150
        q3.reward_trains = 1
        q3.min_level = 5
        q3.offer_text = (
            "The explorer adjusts her pack and points west.\r\n"
            "\"I've heard reports of a cave system in the hills west of the crossroads. "
            "I'd investigate myself, but my knee... Could you go take a look and come "
            "back to tell me what's there?\""
        )
        q3.accept_text = "\"Head west from the crossroads, then follow the hills. Can't miss it!\""
        q3.complete_text = (
            "\"A cave passage, you say? Fascinating! And skeletons too? "
            "This is valuable information. Here's something for your trouble.\""
        )
        quests.append(q3)
        
        # Q4: Bandit Hunt (kill quest, advanced)
        q4 = QuestDef("bandit_hunt", "Bandit Hunt")
        q4.desc = "Bandits on the Great North Road are ambushing travelers. Kill 3 bandits."
        q4.quest_type = "kill"
        q4.giver_vnum = 12  # City Guard Captain
        q4.kill_targets = {7: 3}
        q4.reward_xp = 2500
        q4.reward_gold = 200
        q4.reward_practices = 4
        q4.reward_items = [(1011, 1)]  # Iron sword
        q4.min_level = 6
        q4.prereq_quests = ["forest_pests"]
        q4.offer_text = (
            "The grizzled captain slams his fist on the table.\r\n"
            "\"Those damn bandits on the north road are getting bolder. "
            "They hit a merchant caravan just yesterday. I need someone to "
            "teach them a lesson. Kill three of the bastards and I'll make it worth your while.\""
        )
        q4.accept_text = "\"Hah! That's the spirit. Bring me their heads... or just come back alive.\""
        q4.complete_text = (
            "\"You did it! The road's a little safer thanks to you. Here's your reward — "
            "and this sword's been gathering dust in the armory. Take it.\""
        )
        quests.append(q4)
        
        # Q5: Bear Necessities (kill quest)
        q5 = QuestDef("bear_necessities", "Bear Necessities")
        q5.desc = "A black bear has been spotted on the hilltop. Kill it and bring proof."
        q5.quest_type = "kill"
        q5.giver_vnum = 13  # Hunter
        q5.kill_targets = {8: 1}
        q5.reward_xp = 4000
        q5.reward_gold = 350
        q5.reward_practices = 5
        q5.reward_trains = 2
        q5.reward_items = [(1013, 1)]  # Silver ring
        q5.min_level = 8
        q5.prereq_quests = ["cave_expedition"]
        q5.offer_text = (
            "The hunter sharpens his knife as you approach.\r\n"
            "\"There's a massive black bear denned up on the hilltop west of here. "
            "It's been killing livestock. I'd go myself, but I'm getting too old for "
            "that kind of fight. You look capable — think you can take it down?\""
        )
        q5.accept_text = "\"Good man. That bear's hide will make a fine rug.\""
        q5.complete_text = (
            "\"You got it! I knew I had a good feeling about you. Here's your reward — "
            "and this ring has been in my family for generations. It's served me well, "
            "but I think you've earned it more.\""
        )
        quests.append(q5)
        
        for q in quests:
            self.quest_defs[q.quest_id] = q
        
        self._loaded = True
    
    def get_quest(self, quest_id):
        return self.quest_defs.get(quest_id)
    
    def get_quests_for_mob(self, mob_vnum):
        """Get all quests offered by a specific mob template vnum."""
        return [q for q in self.quest_defs.values() if q.giver_vnum == mob_vnum]
    
    def can_start_quest(self, player, quest_id):
        """Check if a player can start a quest."""
        quest = self.quest_defs.get(quest_id)
        if not quest:
            return False, "That quest doesn't exist."
        
        qstate = player.quests.get(quest_id)
        if qstate and qstate.status == "active":
            return False, "You already have this quest."
        if qstate and qstate.status == "completed":
            if quest.repeatable:
                if time.time() < qstate.cooldown_until:
                    remaining = int(qstate.cooldown_until - time.time())
                    return False, f"You must wait {remaining} seconds."
            else:
                return False, "You've already completed this quest."
        
        if player.level < quest.min_level:
            return False, f"You must be level {quest.min_level} to start this quest."
        if player.level > quest.max_level:
            return False, "You are too high level for this quest."
        
        # Check prerequisites
        for prereq in quest.prereq_quests:
            pre_state = player.quests.get(prereq)
            if not pre_state or pre_state.status != "completed":
                pre_name = self.quest_defs.get(prereq, QuestDef(prereq, "Unknown")).name
                return False, f"You must complete '{pre_name}' first."
        
        return True, "You can start this quest."
    
    def accept_quest(self, player, quest_id):
        """Player accepts a quest."""
        can, msg = self.can_start_quest(player, quest_id)
        if not can:
            player.send(msg)
            return False
        
        qstate = QuestState(quest_id)
        qstate.status = "active"
        
        # Initialize progress
        quest = self.quest_defs[quest_id]
        if quest.quest_type == "kill":
            for mob_vnum, count in quest.kill_targets.items():
                qstate.progress[str(mob_vnum)] = 0
        elif quest.quest_type == "fetch":
            for item_vnum, count in quest.fetch_targets.items():
                qstate.progress[str(item_vnum)] = 0
        elif quest.quest_type == "explore":
            qstate.progress["visited"] = 0
        
        player.quests[quest_id] = qstate
        player.send(f"\x1b[32mQuest accepted: {quest.name}\x1b[0m")
        player.send(quest.accept_text)
        return True
    
    def advance_kill_quest(self, player, mob_template_vnum):
        """Called when a player kills a mob — check kill quests."""
        for qid, qstate in list(player.quests.items()):
            if qstate.status != "active":
                continue
            quest = self.quest_defs.get(qid)
            if not quest or quest.quest_type != "kill":
                continue
            key = str(mob_template_vnum)
            if key in quest.kill_targets:
                qstate.progress[key] = qstate.progress.get(key, 0) + 1
                needed = quest.kill_targets[key]
                current = qstate.progress[key]
                player.send(f"\x1b[33m[Quest] {quest.name}: {current}/{needed} {quest.kill_targets.get(key, mob_template_vnum)} killed.\x1b[0m")
                if self._check_kill_quest_complete(qstate, quest):
                    return qid  # Quest fully completed
        return None
    
    def _check_kill_quest_complete(self, qstate, quest):
        """Check if all kill targets are met."""
        for mob_vnum, needed in quest.kill_targets.items():
            key = str(mob_vnum)
            if qstate.progress.get(key, 0) < needed:
                return False
        return True
    
    def advance_explore_quest(self, player, room_vnum):
        """Called when a player enters a room — check explore quests."""
        for qid, qstate in list(player.quests.items()):
            if qstate.status != "active":
                continue
            quest = self.quest_defs.get(qid)
            if not quest or quest.quest_type != "explore":
                continue
            if room_vnum not in quest.explore_targets:
                continue
            visited = qstate.progress.get("visited_rooms", [])
            if room_vnum not in visited:
                visited.append(room_vnum)
                qstate.progress["visited_rooms"] = visited
                qstate.progress["visited"] = len(visited)
                player.send(f"\x1b[33m[Quest] {quest.name}: Explored {len(visited)}/{len(quest.explore_targets)} locations.\x1b[0m")
                if len(visited) >= len(quest.explore_targets):
                    return qid
        return None
    
    def complete_quest(self, player, quest_id):
        """Complete a quest and give rewards."""
        qstate = player.quests.get(quest_id)
        quest = self.quest_defs.get(quest_id)
        if not qstate or not quest:
            player.send("Quest not found.")
            return False
        if qstate.status != "active":
            player.send("This quest isn't active.")
            return False
        
        # Verify completion conditions
        if quest.quest_type == "kill":
            if not self._check_kill_quest_complete(qstate, quest):
                player.send("You haven't completed the kill requirements yet.")
                return False
        elif quest.quest_type == "explore":
            visited = qstate.progress.get("visited_rooms", [])
            if len(visited) < len(quest.explore_targets):
                player.send("You haven't explored all required locations.")
                return False
        
        # Give rewards
        player.gain_xp(quest.reward_xp)
        player.gold += quest.reward_gold
        player.practices += quest.reward_practices
        player.trains += quest.reward_trains
        
        # Give item rewards
        for item_vnum, count in quest.reward_items:
            template = self.world.item_templates.get(item_vnum)
            if template:
                from .entity import ItemInstance
                for _ in range(count):
                    item = ItemInstance(template)
                    player.inventory.append(item)
                    player.send(f"\x1b[33mYou receive {item.short_desc}.\x1b[0m")
        
        player.send(f"\x1b[32mQuest completed: {quest.name}!\x1b[0m")
        player.send(f"\x1b[33mYou receive {quest.reward_xp} XP and {quest.reward_gold} gold.\x1b[0m")
        
        # Mark complete
        qstate.status = "completed"
        qstate.completed_at = time.time()
        if quest.repeatable:
            qstate.cooldown_until = time.time() + quest.cooldown
        
        return True
    
    def list_active_quests(self, player):
        """Show a player's active quests."""
        active = [(qid, qs) for qid, qs in player.quests.items() if qs.status == "active"]
        if not active:
            player.send("You have no active quests.")
            return
        
        player.send("\x1b[33m--- Active Quests ---\x1b[0m")
        for qid, qs in active:
            quest = self.quest_defs.get(qid)
            if not quest:
                continue
            player.send(f"\x1b[32m{quest.name}\x1b[0m")
            
            if quest.quest_type == "kill":
                for mob_vnum, needed in quest.kill_targets.items():
                    mob_t = self.world.mob_templates.get(mob_vnum)
                    mob_name = mob_t.short_desc if mob_t else f"mob#{mob_vnum}"
                    current = qs.progress.get(str(mob_vnum), 0)
                    player.send(f"  Kill {mob_name}: {current}/{needed}")
            elif quest.quest_type == "explore":
                visited = qs.progress.get("visited_rooms", [])
                player.send(f"  Explore locations: {len(visited)}/{len(quest.explore_targets)}")
            else:
                player.send(f"  Progress: {qs.progress}")
            player.send("")
