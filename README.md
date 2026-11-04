# Star Wars: Knights of the Old Republic II, Archipelago

An [Archipelago](https://archipelago.gg) world for KOTOR 2 (Steam/Aspyr build): vanilla, TSLRCM, or TSLRCM with the
M4-78 Enhancement Project.
**Status: pre-alpha.** The world generates and its tests pass; the game side has not run in game yet.

Game page: [worlds/kotor2/docs](worlds/kotor2/docs/en_Star%20Wars%20Knights%20of%20the%20Old%20Republic%20II.md).
Setup: [setup_en.md](worlds/kotor2/docs/setup_en.md). Design: [docs/DESIGN.md](docs/DESIGN.md), decisions:
[docs/DECISIONS.md](docs/DECISIONS.md).

## Playing

You need KOTOR 2 (Steam/Aspyr) and Archipelago 0.6.8 or newer. Nothing to build or compile.

> [!NOTE]
> **Not released yet.** These are the steps for the first release (prebuilt bridge, installer inside the client). Until
> then the game files can only be installed from source: see [Testing from source](#testing-from-source).

1. **Install the world:** double-click `kotor2.apworld` from the release.
2. **Install the game files:** with KOTOR 2 closed, open **KOTOR 2 Client** from the Archipelago Launcher and type
   `/install`. It finds your game, detects your setup (vanilla, TSLRCM, or TSLRCM + M4-78EP, from the Steam Workshop
   or installed by hand), and puts the bridge (`version.dll`) and the scripts in place. Anything it replaces is backed
   up; `/uninstall` puts everything back.
3. **Make a seed:** in the Launcher, **Options Creator** (game "Star Wars Knights of the Old Republic II"). Set
   `content` to the setup `/install` reported. Save the YAML in `Players\`, click **Generate**, then **Host** (or upload
   the zip at archipelago.gg/uploads).
4. **Play:** start KOTOR 2 and begin a **new game**, then connect from **KOTOR 2 Client** (local host:
   `localhost:38281`). The first save you play while connected is bound to your slot; other saves are left alone.

**Is it working?** `%LOCALAPPDATA%\K2APBridge\bridge.log` shows `hooks installed`, then `tick` lines once you control
your character. In the client, `/bridge` shows the hooks, ticks and watched game globals. A new Peragus area sends a
check; once you have the Ebon Hawk, planets without their coordinates are greyed out on the galaxy map.

**If the client says the game "does not keep Archipelago's globals":** TSLRCM's Workshop `globalcat.2da` is winning
over ours (the open question in [docs/DESIGN.md](docs/DESIGN.md)). Report it.

## Testing from source

For developers and testers until the first release. This route builds the bridge and compiles the scripts yourself,
so it needs Python 3.10+ with `pykotor` and a 32-bit Windows C++ compiler: MinGW-w64 from WSL or Linux (below), or
Visual Studio with `bridge/CMakeLists.txt`. Paths are for a default Steam install seen from WSL.

1. `python3 -m venv .venv && .venv/bin/pip install pykotor pefile`
2. `sudo apt install g++-mingw-w64-i686`, then `sh bridge/build.sh` (writes `bridge/build/version.dll`).
3. With KOTOR 2 closed:
   `.venv/bin/python tools/install.py "/mnt/c/Program Files (x86)/Steam/steamapps/common/Knights of the Old Republic II"`
   (`--uninstall` restores everything; rerun after updating the repository).
4. `python3 tools/build_apworld.py`, then double-click `build\kotor2.apworld` in Windows Explorer.
5. Continue from step 3 of [Playing](#playing). The client still runs on Windows, from the Archipelago Launcher.

## Layout

- `worlds/kotor2/`: the world (data, regions, items, options), the client and `protocol.py` (game wire format).
- `nss/`: NWScript sources (`ap_tick`, `ap_gm_lock`); `tools/build_scripts.py` compiles them.
- `bridge/`: K2APBridge, the `version.dll` proxy that adds NWScript routines 877-879 and runs `ap_tick`.
- `tools/`: research extraction (`extract_research.py`, `scan_routines.py`, `ncs_listing.py`), the table generator
  (`gen_tables.py`), the installer (`install.py`), tests (`test_world.py`) and packaging (`build_apworld.py`).

## Development

```
python3 -m venv .venv && .venv/bin/pip install pykotor pefile
.venv/bin/python tools/extract_research.py "<KOTOR 2 folder>"   # research/<profile>/*.tsv
.venv/bin/python tools/gen_tables.py                             # worlds/kotor2/tables.py (ID ledger)
python3 tools/test_world.py                                      # needs an Archipelago checkout (AP_DIR)
sh bridge/build.sh                                               # needs g++-mingw-w64-i686
.venv/bin/python tools/install.py "<KOTOR 2 folder>"             # --uninstall to revert
python3 tools/build_apworld.py                                   # build/kotor2.apworld
```

Addresses in `bridge/src/engine.h` come from K2SE's published research and KotOR Patch Manager's address database,
re-checked against the target executable; no code from either is used.
