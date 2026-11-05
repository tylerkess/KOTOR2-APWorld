# Decisions (append only)

- **D1 (2026-11-04)** KOTOR 2 rather than KOTOR 1. A KOTOR 1 world already exists (Firebringer92/Archipelago-Fire, MIT,
  alpha); none exists for KOTOR 2, and its modding scene is larger. Owner's choice.
- **D2 (2026-11-04)** Target build: Steam/Aspyr 1.0.2.0 (TimeDateStamp 0x5603005D), the owner's copy and the build K2SE's
  addresses were taken from. GOG has different addresses: later.
- **D3 (2026-11-04)** TSLRCM + M4-78EP (Workshop 1402798020) is an option, `tslrcm`, default on. It adds 27 quests, the
  M4-78 modules (801-809DRO) and restored areas (225/235/298/299TEL, 307/350NAR, 703KOR, 908/909MAL). Tables are
  extracted per profile (research/vanilla, research/tslrcm). Unverified: game `override/` vs Workshop `override/`
  priority; tools/kotor_layers.py assumes Workshop first.
- **D4 (2026-11-04)** Bridge is our own code. K2SE (no license) is used only as a source of addresses and engine facts;
  KotOR Patch Manager (MIT) for its address database.
- **D5 (2026-11-04)** Planet gating through an Override `a_galaxymap.ncs`. The game's copy lives inside module 003EBO
  (TSLRCM's .mod), so an Override file wins without touching the module. Its logic (read from TSLRCM's compiled copy):
  hub open on `262TEL_Escape_Telos`, M4-78 on `000_M478_Found`, endgame on `900MAL_Open`, Dxun before Onderon on
  `401DXN_Visited`.
- **D6 (2026-11-04)** No containers or shops as checks in the first version (Mass Effect lesson: rolled loot, closed
  areas, randomized stock).
- **D7 (2026-11-04)** Galaxy-map gating patches the player's own a_galaxymap at install time instead of shipping a
  rewrite (supersedes the "Override a_galaxymap" detail of D5): vanilla and TSLRCM copies differ (5882 vs 9167 bytes),
  and TSLRCM's 703KOR copy is identical to its 003EBO one, so one Override file serves both modules.
- **D8 (2026-11-04)** Goal = EndGame (routine 564), seen by the bridge's dispatcher hook, while the last snapshot is in
  904MAL. a_end_game sets GBL_GAME_COMPLETE and calls EndGame in the same run, so no tick or save sees it.
- **D9 (2026-11-04)** Area visits are recorded in the save (AP_V_* booleans) by ap_tick whether or not the client is
  connected, so offline play still sends them later. Quest checks read the journal, which the save keeps anyway.
- **D10 (2026-11-04)** No DeathLink yet (the K command exists; sending needs a death signal). Party members are not
  items yet (story scenes force several into the party).
- **D11 (2026-11-04)** M4-78 follows the game's own condition (owner, confirmed in t3m4.dlg): T3-M4 recovers the
  coordinates from Kaah's datapad (Korriban Sith Academy) and sets 000_M478_Found. Logic: M4-78 is entered from
  Korriban with M4-78 Coordinates. It is a mandatory mission once open (owner): visits 801-805DRO and "Re-activate
  M4-78" may hold progression; 806/807DRO and the other quests stay filler-only until confirmed.
- **D12 (2026-11-04)** Endgame correction: 605DAN k_enter_605 starts it when 000_Jedi_Found >= 4, one per master
  (303NAR Zez-Kai Ell, 506OND Kavar, 602DAN Vrook, and Vash: 702KOR tr_vash in vanilla, 805DRO vash01.dlg with
  M4-78EP). Logic needs Nar Shaddaa, Dxun and Onderon, Dantooine and Korriban, plus M4-78 with TSLRCM. Open: TSLRCM's
  702KOR/703KOR still hold tr_vash, so with M4-78EP Vash may count twice; requiring M4-78 is safe either way.
- **D13 (2026-11-04)** 2DA files are read with tools/twoda.py, not PyKotor: PyKotor 2.3.12 trusts the data-size field,
  which TSLRCM's globalcat.2da sets to 0, and returns every cell blank. build_scripts refuses a globalcat that reads
  back with blank names and checks a write/read round trip.
- **D14 (2026-11-04)** Option m4_78_access, default coordinates_only (owner): the item alone opens M4-78 on the galaxy
  map (ap_gm_lock, only while 262TEL_Escape_Telos = 1 and 900MAL_Open = 0; AP_OPTS bit 0 set by the client).
  000_M478_Found is not touched, so Korriban (T3-M4's datapad scene) plays as usual; owner: finding Vash on M4-78 does
  nothing to Korriban, and the Sith Academy locks once left after her datapad (vanilla: her body). vanilla keeps the
  game's condition (logic: M4-78 behind Korriban). Snapshots now carry watched globals (000_Jedi_Found, 702KOR_Vash,
  ...); the client warns if Vash is counted both on Korriban and on M4-78.
- **D15 (2026-11-04)** The Sith Academy visit counts 702KOR or 703KOR (TSLRCM's valley links to both). The Secret Tomb
  (711KOR, from the Shyrack cave off the valley) can be entered once, which sends its visit: it keeps progression.
- **D16 (2026-11-04)** Option jedi_masters (default vanilla, owner) with masters_required (1-4) and unmet_masters
  (attend/absent, owner's choice of "option 3"; an invite-or-not dialogue on receipt is the later "option 4").
  Shuffled: four Jedi Master items; ap_tick keeps 000_Jedi_Found at the item count (4 once masters_required is met,
  at most 3 before), overwriting the +1 from each master's dialogue; logic's endgame needs those items and Dantooine
  Coordinates (the meeting is in its Enclave) instead of every master's planet. "Find <master>" checks (both modes) latch AP_M_* from the master-specific LostJedi entries, dead flags, or
  702KOR_Vash. The meeting spawns masters by dead flag (TSLRCM k_650enter; vanilla k_def_650kavar/vrook/zez), so
  absent runs ap_masters first in those (prepended ExecuteScript) and marks unmet masters dead only then; their own
  planets are untouched. Side effect: TSLRCM's k_sup_galaxymap travel events keyed on the count (1, 2, 4) follow item
  arrivals instead of meetings.
- **D17 (2026-11-04)** Three content profiles (option `content`: vanilla, tslrcm, tslrcm_m478; default tslrcm),
  replacing the tslrcm toggle (owner installed standalone TSLRCM, 485537937, and unsubscribed the combined item).
  Extracted separately: TSLRCM adds 012EBO, 225/235/298/299TEL, 307/350NAR, 908/909MAL and the three HK factory quests;
  M4-78EP adds 703KOR, 801-809DRO and 21 quests. TSLRCM alone keeps vanilla Vash (her body, 702KOR tr_vash; no
  000_M478_Found anywhere), so M4-78, its coordinates and "M4-78: Find Lonna Vash" are tslrcm_m478 only. The installer
  detects the profile from what the game would load (Workshop items Steam lists as installed in
  appworkshop_208580.acf, since unsubscribing leaves files behind, plus the game folder): 801DRO means tslrcm_m478,
  298TEL means tslrcm. It is compiled into ap_tick (AP_CONTENT) and reported in every snapshot; the client refuses a
  seed whose content differs. research/tslrcm_m478 is the earlier extraction (the item is no longer installed here).
- **D18 (2026-11-05)** First in-game run. (1) A Workshop item's `override/` beats the game's own (answers D3's open
  question): with TSLRCM from the Workshop, our globals were declared only in the game's override/globalcat.2da and the
  save dropped them. The installer now also writes our merged globalcat.2da (the effective table plus our rows) into
  every installed Workshop item that ships one, backed up and recorded in the receipt; `--uninstall` restores it.
  Steam may restore the mod's copy on an update; the client then reports that the globals are not kept, and
  reinstalling fixes it. Other override files are unaffected (no Workshop item here ships a_galaxymap, the 650DAN
  scripts or ours). (2) PyKotor 2.3.12 compiles engine-call arguments first to last; the game pops them last to
  first, so every call with two or more arguments aborted ap_tick. tools/build_scripts.py reverses that loop and
  checks the order on every build. (3) Builds read the game as it was before our install (the receipt), so patches no
  longer stack on each reinstall.
- **D19 (2026-11-05)** The prologue can be skipped from the new-game screen, which left its checks (the 001EBO visit
  and four tutorial quests, "Save the Ebon Hawk" a story check that can hold progression) unreachable; seen in game
  with Nar Shaddaa Coordinates there. Every path continues in 101PER, so the client counts the prologue as done once
  101PER is visited (data.PROLOGUE_END_MODULE). Client-only: a save that already skipped it gets the checks on its next
  connection.
