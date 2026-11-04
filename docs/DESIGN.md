# KOTOR 2 Archipelago: design

Target: Star Wars: Knights of the Old Republic II (The Sith Lords), **Steam / Aspyr 1.0.2.0** (`swkotor2.exe`,
32-bit, PE TimeDateStamp `0x5603005D`), in three setups (the `content` option): vanilla, TSLRCM (Workshop 485537937),
and TSLRCM + M4-78EP (Workshop 1402798020), or the same mods installed by hand.

## Components

```
 Archipelago server
        |  (websocket)
 KOTOR 2 Client (Python, worlds/kotor2/client.py, CommonContext)
        |  named pipe \\.\pipe\K2APBridge   (one ASCII request, one reply)
 K2APBridge (version.dll proxy in the game folder, our C++)
        |  adds NWScript routines 877+ and runs ap_tick.ncs on the game thread
 NWScript package in Override (ap_*.ncs, a_galaxymap.ncs, globalcat.2da rows)
        |  ordinary engine calls: GetJournalEntry, CreateItemOnObject, Set/GetGlobalNumber ...
 The game
```

1. **apworld** (`worlds/kotor2/`): items, locations, regions, logic, options. Location IDs and item IDs are an
   append-only ledger (`data.py`).
2. **Bridge** (`bridge/`): a 32-bit `version.dll` proxy (K2SE's slot choice: not contended by the OpenGL shader fix that
   M4-78EP ships as `opengl32.dll`, and not a Steam depot file like `binkw32.dll`). It
   - hooks `CSWVirtualMachineCommands::ExecuteCommand` (vtable slot at `0x009940D8`, original `0x00668FD0`) so routine
     IDs from 877 up reach our handlers;
   - calls `CVirtualMachine::RunScript(CExoString*, objectId, int)` (`0x006FD8D0`) to run `ap_tick` about once a second
     while a module is loaded;
   - serves the client's named pipe on its own thread, exchanging strings with the game thread through two locked
     queues.
   Addresses come from K2SE's published research (DESIGN.md there; its source has no license, so none of its code is
   used) and KotOR Patch Manager's address DB (MIT). Each one is checked against the running image before hooking;
   any mismatch disables the bridge and logs why.
3. **NWScript package** (`nss/`, compiled with PyKotor's built-in compiler against `nwscript.nss` plus our routines):
   - `ap_tick`: delivers queued items, reports state (current module, the journal states we watch, goal flags).
   - `ap_gm_lock`: greys out planets whose coordinates have not arrived (global `AP_PLANETS` bits).
   - `a_galaxymap`: the player's own copy (vanilla or TSLRCM, read from module 003EBO at install time) with one
     `ExecuteScript("ap_gm_lock")` inserted before its `ShowGalaxyMap`. PyKotor round-trips both originals byte for
     byte; the patch adds 4 instructions and nothing else.
4. **Installer** (`tools/install.py`): compiles the scripts, merges our rows into the *effective* `globalcat.2da`
   (TSLRCM ships its own), copies everything into Override and puts `version.dll` next to the exe. Uninstall removes
   exactly what it added (a receipt file).

## Bridge routines (NWScript side)

```
int    APB_Version();            // 877: bridge protocol version, 0 = no bridge
string APB_Recv();               // 878: next command from the client, "" when none
void   APB_Send(string sEvent);  // 879: event to the client
```

All game logic stays in NWScript and Python; the C++ side moves strings. That keeps the reverse-engineered surface to
the routine dispatcher, the VM string/int stack accessors and RunScript.

## State in the save

Globals must be declared in `globalcat.2da` or the save drops them. Our rows (all `Number` unless noted):

| Global | Meaning |
|---|---|
| `AP_RECV_LO`, `AP_RECV_HI` | received-item index (lo + 100 * hi; Number globals hold -128..127) |
| `AP_ID_A`, `AP_ID_B`, `AP_ID_C` | seed/slot identity (1..99 each, from a hash); 0 0 0 = unbound |
| `AP_PLANETS` | bit per planet access item |
| `AP_V_<MODULE>` (Boolean) | area visited; set by ap_tick even with no client connected |

Item delivery is idempotent the ME1 way: the client queues `I <index> <op> <args>`; `ap_tick` applies it only when
`<index>` equals the stored received index and then increments it, in the same script run. Wire formats:
`worlds/kotor2/protocol.py` (snapshot and commands) and `bridge/PROTOCOL.md` (pipe).

## Checks

| Family | Detection | Default |
|---|---|---|
| Area visits | `GetModuleName()` reported by `ap_tick`; first entry sends the check | on |
| Story quests | journal state of the quest reaches an end state (any outcome) | on |
| Side quests | same, curated list; branch-exclusive or missable quests are filler-only or left out | option |
| Goal | the ending script (904MAL `a_end_game`) calls `EndGame`; the bridge reports it | always |

Rules learned from Mass Effect, applied here:
- **Points of no return** (Peragus/Harbinger are fine: they need no items; the endgame on the Telos academy, the Ravager
  and Malachor V is not): endgame locations exist but never hold this world's progression.
- **Choices**: a quest check is "completed, any outcome" so light side, dark side and faction choices all send it.
  Quests a choice can skip entirely are excluded (filler only) or left out.
- **Containers and shops**: not checks in the first version. Loot is rolled on open and several areas close for good.

## Items

| Item | Effect | Class |
|---|---|---|
| Nar Shaddaa / Dxun & Onderon / Dantooine / Korriban / M4-78 Coordinates | planet selectable on the galaxy map | progression |
| Credits, components, chemicals, medpacs, stims | CreateItemOnObject / GiveGoldToCreature | filler |
| XP bundles | GiveXPToCreature | filler |
| Lightsaber crystals, upgrades | CreateItemOnObject | useful |

Party members as items are a later option (story scenes force several of them into the party).

## Open questions (in-game tests)

- **Override vs Workshop priority**: does a file in the game's `override/` beat the same file in a Workshop item's
  `override/`? Our `globalcat.2da` must win over TSLRCM's. (`docs/DECISIONS.md` D3.)
- Whether `RunScript` from our per-frame call is safe during conversations, cutscenes and loading; `ap_tick` itself
  skips work in conversations (`GetIsInConversation`) and while `GetFirstPC()` is invalid.
