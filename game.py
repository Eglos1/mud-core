#!/usr/bin/env python3
"""
MUD Core — Main entry point.
Starts the world server, loads data, begins event loop.
"""
import asyncio, signal, sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from engine.server import Server, World
from engine.config import Config

async def main():
    cfg = Config()
    world = World(cfg)
    
    # Load world data
    await world.load_all()
    
    # Start server
    server = Server(cfg, world)
    await server.start()
    
    # Main loop — never exits
    print(f"MUD started on {cfg.HOST}:{cfg.PORT}")
    print(f"Players: {cfg.MAX_PLAYERS} max, idle timeout {cfg.IDLE_TIMEOUT}s")
    print(f"World: {len(world.zones)} zones, {len(world.rooms)} rooms, {len(world.mob_templates)} mob templates")
    
    try:
        await asyncio.Event().wait()  # run forever
    except KeyboardInterrupt:
        print("\nShutting down...")
        await world.save_all()
        server.stop()
        print("Goodbye!")

if __name__ == "__main__":
    asyncio.run(main())
