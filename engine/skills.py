"""
Skills and spells system.
"""
import random
from .config import Config
from .world import SkillDef
cfg = Config()

SKILL_DEFS = {}

def reg(skill_def):
    SKILL_DEFS[skill_def.name] = skill_def
    return skill_def

# ─── Combat Skills ────────────────────────────────────────────────

bash = SkillDef("bash", "combat_skill")
bash.level = 5; bash.mana_cost = 10; bash.cooldown = 3
bash.target = "offensive"; bash.damage_type = "bash"; bash.damage_dice = (2, 8)
bash.hit_bonus = 5; bash.dam_bonus = 3; bash.learn_every = 4
bash.desc_hit = "You slam into {target} with a powerful bash!"
bash.desc_miss = "Your bash misses {target}."
reg(bash)

backstab = SkillDef("backstab", "combat_skill")
backstab.level = 10; backstab.mana_cost = 15; backstab.cooldown = 5
backstab.target = "offensive"; backstab.damage_dice = (4, 10)
backstab.hit_bonus = 10; backstab.dam_bonus = 8; backstab.weapon_required = "dagger"
backstab.learn_every = 5; backstab.desc_hit = "You plunge your dagger deep into {target}'s back!"
reg(backstab)

fireball = SkillDef("fireball", "spell")
fireball.level = 8; fireball.mana_cost = 30; fireball.cooldown = 4
fireball.target = "offensive"; fireball.damage_type = "fire"; fireball.damage_dice = (3, 12)
fireball.hit_bonus = 0; fireball.dam_bonus = 5; fireball.learn_every = 4
fireball.desc_hit = "A roaring fireball erupts from your hands, engulfing {target}!"
reg(fireball)

heal = SkillDef("heal", "spell")
heal.level = 5; heal.mana_cost = 20; heal.cooldown = 3
heal.target = "defensive"; heal.learn_every = 3
heal.desc_hit = "You are healed by a warm light."
reg(heal)

kick = SkillDef("kick", "combat_skill")
kick.level = 3; kick.mana_cost = 5; kick.cooldown = 2
kick.target = "offensive"; kick.damage_type = "bash"; kick.damage_dice = (1, 6)
kick.hit_bonus = 2; kick.dam_bonus = 2; kick.learn_every = 4
reg(kick)

parry = SkillDef("parry", "skill")
parry.level = 3; parry.mana_cost = 0; parry.cooldown = 0
parry.target = "self"; parry.learn_every = 4
reg(parry)

dodge = SkillDef("dodge", "skill")
dodge.level = 1; dodge.mana_cost = 0; dodge.cooldown = 0
dodge.target = "self"; dodge.learn_every = 3
reg(dodge)

meditate = SkillDef("meditate", "skill")
meditate.level = 5; meditate.mana_cost = 0; meditate.cooldown = 10
meditate.target = "self"; meditate.learn_every = 4
meditate.desc_hit = "You enter a deep meditative trance."
reg(meditate)

track = SkillDef("track", "skill")
track.level = 5; track.mana_cost = 10; track.cooldown = 15
track.target = "self"; track.learn_every = 4
reg(track)

camouflage = SkillDef("camouflage", "skill")
camouflage.level = 8; camouflage.mana_cost = 15; camouflage.cooldown = 30
camouflage.target = "self"; camouflage.learn_every = 5
reg(camouflage)

shield_block = SkillDef("shield_block", "skill")
shield_block.level = 5; shield_block.mana_cost = 0; shield_block.cooldown = 0
shield_block.target = "self"; shield_block.learn_every = 4
reg(shield_block)

charge = SkillDef("charge", "combat_skill")
charge.level = 12; charge.mana_cost = 20; charge.cooldown = 6
charge.target = "offensive"; charge.damage_type = "bash"; charge.damage_dice = (3, 10)
charge.hit_bonus = 8; charge.dam_bonus = 6; charge.learn_every = 5
reg(charge)

lay_hands = SkillDef("lay_hands", "spell")
lay_hands.level = 8; lay_hands.mana_cost = 30; lay_hands.cooldown = 10
lay_hands.target = "defensive"; lay_hands.learn_every = 4
reg(lay_hands)

smite = SkillDef("smite", "combat_skill")
smite.level = 10; smite.mana_cost = 25; smite.cooldown = 5
smite.target = "offensive"; smite.damage_type = "magic"; smite.damage_dice = (3, 12)
smite.hit_bonus = 5; smite.dam_bonus = 10; smite.learn_every = 5
reg(smite)

life_drain = SkillDef("life_drain", "spell")
life_drain.level = 8; life_drain.mana_cost = 25; life_drain.cooldown = 4
life_drain.target = "offensive"; life_drain.damage_type = "magic"; life_drain.damage_dice = (2, 10)
life_drain.hit_bonus = 3; life_drain.dam_bonus = 5; life_drain.learn_every = 4
life_drain.desc_hit = "You drain the life force from {target}!"
reg(life_drain)

nature_heal = SkillDef("nature_heal", "spell")
nature_heal.level = 6; nature_heal.mana_cost = 25; nature_heal.cooldown = 4
nature_heal.target = "defensive"; nature_heal.learn_every = 4
reg(nature_heal)

summon_wolf = SkillDef("summon_wolf", "spell")
summon_wolf.level = 10; summon_wolf.mana_cost = 40; summon_wolf.cooldown = 20
summon_wolf.target = "room"; summon_wolf.learn_every = 5
reg(summon_wolf)

song_of_courage = SkillDef("song_of_courage", "skill")
song_of_courage.level = 8; song_of_courage.mana_cost = 20; song_of_courage.cooldown = 15
song_of_courage.target = "room"; song_of_courage.learn_every = 4
reg(song_of_courage)

identify = SkillDef("identify", "skill")
identify.level = 5; identify.mana_cost = 10; identify.cooldown = 3
identify.target = "self"; identify.learn_every = 3
reg(identify)

stealth = SkillDef("stealth", "skill")
stealth.level = 5; stealth.mana_cost = 10; stealth.cooldown = 5
stealth.target = "self"; stealth.learn_every = 4
reg(stealth)

pick_lock = SkillDef("pick_lock", "skill")
pick_lock.level = 8; pick_lock.mana_cost = 5; pick_lock.cooldown = 3
pick_lock.target = "self"; pick_lock.learn_every = 4
reg(pick_lock)

detect_trap = SkillDef("detect_trap", "skill")
detect_trap.level = 5; detect_trap.mana_cost = 5; detect_trap.cooldown = 5
detect_trap.target = "self"; detect_trap.learn_every = 3
reg(detect_trap)

lore = SkillDef("lore", "skill")
lore.level = 3; lore.mana_cost = 5; lore.cooldown = 3
lore.target = "self"; lore.learn_every = 3
reg(lore)

charm = SkillDef("charm", "spell")
charm.level = 12; charm.mana_cost = 35; charm.cooldown = 20
charm.target = "offensive"; charm.learn_every = 5
reg(charm)

# ═══════════════════════════════════════════════════════════════════
# MISSING CLASS SKILLS (added to complete class definitions)
# ═══════════════════════════════════════════════════════════════════

frost = SkillDef("frost", "spell")
frost.level = 7; frost.mana_cost = 25; frost.cooldown = 4
frost.target = "offensive"; frost.damage_type = "cold"; frost.damage_dice = (2, 10)
frost.hit_bonus = 3; frost.dam_bonus = 4; frost.learn_every = 4
frost.desc_hit = "A lance of pure ice streaks from your hand, striking {target}!"
reg(frost)

lightning = SkillDef("lightning", "spell")
lightning.level = 10; lightning.mana_cost = 35; lightning.cooldown = 5
lightning.target = "offensive"; lightning.damage_type = "lightning"; lightning.damage_dice = (3, 12)
lightning.hit_bonus = 0; lightning.dam_bonus = 8; lightning.learn_every = 5
lightning.desc_hit = "A brilliant bolt of lightning arcs from the sky, engulfing {target}!"
reg(lightning)

teleport = SkillDef("teleport", "spell")
teleport.level = 12; teleport.mana_cost = 50; teleport.cooldown = 30
teleport.target = "self"; teleport.learn_every = 5
teleport.desc_hit = "You teleport to your bind point."
reg(teleport)

cure = SkillDef("cure", "spell")
cure.level = 4; cure.mana_cost = 15; cure.cooldown = 2
cure.target = "defensive"; cure.learn_every = 3
cure.desc_hit = "A gentle light washes over you, curing your wounds."
reg(cure)

bless = SkillDef("bless", "spell")
bless.level = 6; bless.mana_cost = 20; bless.cooldown = 10
bless.target = "self"; bless.learn_every = 4
bless.desc_hit = "You feel blessed! Your attacks are more accurate."
reg(bless)

sanctuary = SkillDef("sanctuary", "spell")
sanctuary.level = 12; sanctuary.mana_cost = 40; sanctuary.cooldown = 30
sanctuary.target = "self"; sanctuary.learn_every = 5
sanctuary.desc_hit = "A shimmering golden aura surrounds you."
reg(sanctuary)

bow = SkillDef("bow", "combat_skill")
bow.level = 3; bow.mana_cost = 8; bow.cooldown = 3
bow.target = "offensive"; bow.damage_type = "pierce"; bow.damage_dice = (2, 8)
bow.hit_bonus = 5; bow.dam_bonus = 3; bow.learn_every = 4
bow.weapon_required = "bow"; bow.desc_hit = "Your arrow flies straight and true, piercing {target}!"
reg(bow)

animal_companion = SkillDef("animal_companion", "spell")
animal_companion.level = 8; animal_companion.mana_cost = 35; animal_companion.cooldown = 30
animal_companion.target = "room"; animal_companion.learn_every = 5
animal_companion.desc_hit = "You call upon nature and a loyal companion answers!"
reg(animal_companion)

aura = SkillDef("aura", "skill")
aura.level = 6; aura.mana_cost = 15; aura.cooldown = 15
aura.target = "self"; aura.learn_every = 4
aura.desc_hit = "A holy aura radiates from you."
reg(aura)

divine_shield = SkillDef("divine_shield", "spell")
divine_shield.level = 10; divine_shield.mana_cost = 30; divine_shield.cooldown = 20
divine_shield.target = "self"; divine_shield.learn_every = 5
divine_shield.desc_hit = "A shimmering shield of divine energy forms around you."
reg(divine_shield)

entangle = SkillDef("entangle", "spell")
entangle.level = 5; entangle.mana_cost = 20; entangle.cooldown = 6
entangle.target = "offensive"; entangle.learn_every = 4
entangle.desc_hit = "Thick vines erupt from the ground and entangle {target}!"
reg(entangle)

storm = SkillDef("storm", "spell")
storm.level = 12; storm.mana_cost = 45; storm.cooldown = 8
storm.target = "offensive"; storm.damage_type = "lightning"; storm.damage_dice = (4, 10)
storm.hit_bonus = 5; storm.dam_bonus = 10; storm.learn_every = 5
storm.desc_hit = "You summon a furious storm! Lightning and rain lash {target}!"
reg(storm)

summon_undead = SkillDef("summon_undead", "spell")
summon_undead.level = 8; summon_undead.mana_cost = 35; summon_undead.cooldown = 25
summon_undead.target = "room"; summon_undead.learn_every = 5
summon_undead.desc_hit = "Dark energies coalesce into an undead servant!"
reg(summon_undead)

curse = SkillDef("curse", "spell")
curse.level = 5; curse.mana_cost = 20; curse.cooldown = 6
curse.target = "offensive"; curse.learn_every = 4
curse.desc_hit = "You whisper a dark curse upon {target}!"
reg(curse)

fear = SkillDef("fear", "spell")
fear.level = 7; fear.mana_cost = 25; fear.cooldown = 10
fear.target = "offensive"; fear.learn_every = 4
fear.desc_hit = "You fill {target} with overwhelming terror!"
reg(fear)

flurry = SkillDef("flurry", "combat_skill")
flurry.level = 8; flurry.mana_cost = 10; flurry.cooldown = 4
flurry.target = "offensive"; flurry.damage_type = "bash"; flurry.damage_dice = (2, 6)
flurry.hit_bonus = 8; flurry.dam_bonus = 2; flurry.learn_every = 4
flurry.desc_hit = "You unleash a blinding flurry of strikes against {target}!"
reg(flurry)

def get_skill_def(name):
    return SKILL_DEFS.get(name)

def get_class_skills(class_name):
    class_info = cfg.CLASSES.get(class_name, {})
    return class_info.get("skills", [])

def init_player_skills(player, class_name):
    for skill_name in get_class_skills(class_name):
        player.skills[skill_name] = 50
