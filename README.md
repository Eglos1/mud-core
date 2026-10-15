# MUD Core

An asynchronous, Telnet-based multi-user dungeon server written in Python.
Rooms, zones, mobs, combat, skills, quests, an economy and persistence.

## Run
```sh
python3 game.py
```
Serves on `HOST:PORT` from `engine/config.py`; world data is loaded from
`data/` (zones, rooms, mob templates, players). `game.py` is the entry point;
the engine lives in `engine/` (server, world, combat, economy, quests,
skills, telnet, persistence).

## Connect
```sh
telnet localhost <PORT>
```

## License
MIT
