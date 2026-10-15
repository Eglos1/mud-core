"""
Server — main game loop, connection handling, player management.
"""
import asyncio, time, json, traceback, random
from pathlib import Path
from .config import Config
from .telnet import TelnetHandler
from .world import Room, Zone, Weather, MobTemplate, ItemTemplate
from .entity import Player, Mob, ItemInstance
from .combat import CombatSystem
from .economy import Economy
from .commands import CommandHandler
from .ai import MobAI, MobSpawner
from .persist import Persistence

from .world import World
cfg = Config()


class Server:
    """Manages connections, login, and game loop."""
    
    def __init__(self, config, world):
        self.cfg = config
        self.world = world
        self.server = None
        self.running = True
        self.login_sessions = {}  # writer -> session_data
    
    async def start(self):
        """Start the server."""
        self.server = await asyncio.start_server(
            self.handle_connection,
            self.cfg.HOST,
            self.cfg.PORT
        )
        
        # Start game loop
        asyncio.ensure_future(self.game_loop())
        
        print(f"Server listening on {self.cfg.HOST}:{self.cfg.PORT}")
    
    def stop(self):
        """Stop the server."""
        self.running = False
        if self.server:
            self.server.close()
    
    async def handle_connection(self, reader, writer):
        """Handle a new player connection."""
        addr = writer.get_extra_info('peername')
        print(f"New connection from {addr}")
        
        telnet = TelnetHandler(reader, writer)
        
        # Send greeting
        telnet.sendline("=" * 60)
        telnet.sendline(f"\x1b[1;36m   Welcome to the MUD!\x1b[0m")
        telnet.sendline("=" * 60)
        telnet.sendline("")
        
        # Login process
        player = await self._do_login(telnet)
        
        if not player:
            telnet.sendline("\x1b[31mLogin failed. Goodbye.\x1b[0m")
            telnet.close()
            return
        
        # Setup player
        player.telnet = telnet
        player.last_cmd_time = time.time()
        player.last_login = time.time()
        player.room_vnum = player.save_data.get("bind_vnum", 3001)
        
        # Add to world
        self.world.add_player(player)
        
        # Welcome message
        player.send(f"\n\x1b[1;32mWelcome back, {player.name}!\x1b[0m")
        player.send(f"\x1b[33mLevel {player.level} {player.save_data.get('race', '???')} {player.save_data.get('class', '???')}\x1b[0m")
        player.send("")
        
        # Show room
        room = self.world.rooms.get(player.room_vnum)
        if room:
            player.send(room.describe(player))
        
        # Broadcast login
        self.world.broadcast_to_room(player.room_vnum,
            f"\x1b[32m{player.name} has entered the game.\x1b[0m",
            exclude=[player.entity_id])
        
        # Main input loop
        await self._player_loop(player, telnet)
        
        # Player disconnected
        self.world.broadcast_to_room(player.room_vnum,
            f"\x1b[31m{player.name} has left the game.\x1b[0m")
        self.world.save_player(player)
        self.world.remove_player(player)
        print(f"{player.name} disconnected ({addr})")
    
    async def _do_login(self, telnet):
        """Handle login sequence — name/password/new character."""
        telnet.sendline("\x1b[33mWhat is your name?\x1b[0m")
        telnet.send("> ")
        
        name = await telnet.read_line()
        if not name:
            return None
        
        name = name.strip().capitalize()
        
        if self.world.persist.player_exists(name):
            # Existing player — login
            telnet.sendline(f"\x1b[33mWelcome back, {name}. Enter your password:\x1b[0m")
            telnet.send("> ")
            
            password = await telnet.read_line()
            if not password:
                return None
            
            data = self.world.persist.load_player(name)
            if not data or not self.world.persist.check_password(password.strip(), data.get("password_hash", "")):
                telnet.sendline("\x1b[31mIncorrect password.\x1b[0m")
                return None
            
            player = self.world.persist.restore_player_from_data(data)
            return player
        
        else:
            # New character
            telnet.sendline(f"\x1b[33mNew character! Create a password:\x1b[0m")
            telnet.send("> ")
            password = await telnet.read_line()
            if not password:
                return None
            password = password.strip()
            
            # Choose race
            telnet.sendline("\x1b[33mChoose your race:\x1b[0m")
            for race_name, race_data in cfg.RACES.items():
                stats_str = " ".join(f"{s.upper()}:{race_data[s]}" for s in ["str","int","wis","dex","con","luc"])
                telnet.sendline(f"  \x1b[36m{race_name:<12}\x1b[0m {stats_str}  \x1b[37m{race_data['desc']}\x1b[0m")
            telnet.send("> Race: ")
            
            race = await telnet.read_line()
            while not race or race.strip().lower() not in cfg.RACES:
                telnet.send("Valid races: " + ", ".join(cfg.RACES.keys()) + "\n> Race: ")
                race = await telnet.read_line()
                if not race:
                    return None
            race = race.strip().lower()
            
            # Choose class
            telnet.sendline("\x1b[33mChoose your class:\x1b[0m")
            for cls_name, cls_data in cfg.CLASSES.items():
                skills_str = ", ".join(cls_data["skills"][:3])
                telnet.sendline(f"  \x1b[36m{cls_name:<14}\x1b[0m HPx{cls_data['hp_factor']} MANAx{cls_data['mana_factor']}  Skills: {skills_str}")
            telnet.send("> Class: ")
            
            cls = await telnet.read_line()
            while not cls or cls.strip().lower() not in cfg.CLASSES:
                telnet.send("Valid classes: " + ", ".join(cfg.CLASSES.keys()) + "\n> Class: ")
                cls = await telnet.read_line()
                if not cls:
                    return None
            cls = cls.strip().lower()
            
            # Create player
            player = self.world.persist.create_player(name, password, race, cls)
            
            telnet.sendline(f"\x1b[32mWelcome to the world, {name} the {race.capitalize()} {cls.capitalize()}!\x1b[0m")
            return player
    
    async def _player_loop(self, player, telnet):
        """Main loop for a connected player."""
        while self.running:
            try:
                line = await telnet.read_line()
            except (ConnectionResetError, ConnectionError, EOFError):
                break
            
            if line is None:
                break
            
            line = line.strip()
            
            # Idle timeout check
            player.idle_time = time.time() - player.last_cmd_time
            if player.idle_time > cfg.IDLE_TIMEOUT:
                player.send("\x1b[31mYou have been idle too long and are disconnected.\x1b[0m")
                break
            
            # Process command
            await self.world.commands.execute(player, line)
        
        return
    
    async def game_loop(self):
        """Background game loop that ticks every second."""
        while self.running:
            await asyncio.sleep(1)
            try:
                await self.world.game_tick()
            except Exception as e:
                print(f"Game tick error: {e}")
                traceback.print_exc()
