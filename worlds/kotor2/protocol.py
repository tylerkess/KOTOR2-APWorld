"""What the game side reports and accepts. Pure Python (no Archipelago imports): tools/build_scripts.py uses it to
generate the NWScript tables, and the client uses it to read snapshots.

Snapshot line sent by ap_tick each tick (one space between fields):
    S <table hash> <content> <module> <received index> <id a> <id b> <id c> <planets> <visit bits> <quest states> <watched>
content: the profile the installer built the scripts for (vanilla, tslrcm, tslrcm_m478).
visit bits: one '0'/'1' per VISIT_ORDER entry (AP_V_<MODULE> globals, set on entering the module and kept by the save).
quest states: GetJournalEntry(tag) per QUEST_ORDER entry, comma separated.
watched: GetGlobalNumber per WATCHED_GLOBALS entry, comma separated.

Commands the client sends (ap_tick takes up to COMMANDS_PER_TICK per run, never during a conversation):
    I <index> <op> [args]   deliver received item <index>; applied only when it equals the save's received index
        ops: G <credits> | X <xp> | C <resref> <count> | P <planet bit> | M <master bit> | N
    B <a> <b> <c>           bind this save to a slot (only an unbound save with received index 0)
    O <n>                   set AP_OPTS: bit 0 M4-78 opens with its coordinates alone, bit 1 Jedi Masters shuffled,
                            bit 2 unmet masters absent, bits 3-5 masters required (1-4)
    T <text>                floating text over the player
    K                       death (DeathLink)
"""
from __future__ import annotations

import hashlib

from .tables import MODULES, QUESTS

PROTOCOL = 1
COMMANDS_PER_TICK = 20

VISIT_ORDER: tuple[str, ...] = tuple(sorted(MODULES, key=lambda m: MODULES[m][0]))
QUEST_ORDER: tuple[str, ...] = tuple(sorted(QUESTS, key=lambda t: QUESTS[t][0]))

# Planet access bits in the AP_PLANETS global, and the planetary.2da rows each bit opens.
PLANET_BITS: dict[str, tuple[int, tuple[int, ...]]] = {
    "Nar Shaddaa Coordinates": (0, (6,)),
    "Dxun and Onderon Coordinates": (1, (1, 7)),
    "Dantooine Coordinates": (2, (0,)),
    "Korriban Coordinates": (3, (3,)),
    "M4-78 Coordinates": (4, (4,)),
}

OPT_M478_BY_COORDINATES = 1
OPT_MASTERS_SHUFFLED = 2
OPT_UNMET_MASTERS_ABSENT = 4
OPT_MASTERS_REQUIRED_SHIFT = 3  # 3 bits: masters required, 1-4


class Master:
    """A hidden Jedi Master. `met` is set by ap_tick (and kept by the save) once the master-specific journal entry
    (LostJedi) appears, the dead flag is set, or one of `extra_met` is 1. Entries read from global.jrl: Zez-Kai Ell
    43 defeated / 45 agreed (40 = poisoned, not met); Kavar 55 / 57 (50, 53 not met); Vrook 75 / 77 (70, 73 not met);
    Vash 61 / 62 / 69 on M4-78, or her body on Korriban in vanilla (702KOR_Vash, set by tr_vash)."""

    def __init__(self, bit: int, item: str, met: str, journal: tuple[int, ...], dead: str,
                 extra_met: tuple[str, ...] = ()) -> None:
        self.bit, self.item, self.met, self.journal, self.dead, self.extra_met = bit, item, met, journal, dead, extra_met


MASTERS = (
    Master(0, "Jedi Master: Zez-Kai Ell", "AP_M_ZEZ", (43, 45), "000_ZezKaiEll_Dead"),
    Master(1, "Jedi Master: Kavar", "AP_M_KAVAR", (55, 57), "000_Kavar_Dead"),
    Master(2, "Jedi Master: Vrook", "AP_M_VROOK", (75, 77), "000_Vrook_Dead"),
    Master(3, "Jedi Master: Lonna Vash", "AP_M_VASH", (61, 62, 69), "000_Vash_Dead", ("702KOR_Vash",)),
)
MASTER_BY_ITEM = {m.item: m for m in MASTERS}

NUMBER_GLOBALS = ("AP_RECV_LO", "AP_RECV_HI", "AP_ID_A", "AP_ID_B", "AP_ID_C", "AP_PLANETS", "AP_OPTS", "AP_MITEMS",
                  *(m.met for m in MASTERS))
M478_ROW = 4  # planetary.2da
# Game globals reported in every snapshot (options, and the master count: docs/DECISIONS.md D12).
WATCHED_GLOBALS = ("AP_OPTS", "000_Jedi_Found", "702KOR_Vash", "000_M478_Found", "262TEL_Escape_Telos", "900MAL_Open",
                   "AP_MITEMS", *(m.met for m in MASTERS))


def options_value(m478_by_coordinates: bool, masters_shuffled: bool, unmet_absent: bool, masters_required: int) -> int:
    value = OPT_M478_BY_COORDINATES if m478_by_coordinates else 0
    if masters_shuffled:
        value |= OPT_MASTERS_SHUFFLED | (max(1, min(4, masters_required)) << OPT_MASTERS_REQUIRED_SHIFT)
        if unmet_absent:
            value |= OPT_UNMET_MASTERS_ABSENT
    return value


def visit_global(module: str) -> str:
    return f"AP_V_{module.upper()}"


# Delivery ops ap_tick understands (client.delivery_op). Part of table_hash: an ap_tick without an op would stall the
# item queue on it (unknown ops are never consumed), so a client with new ops asks for a reinstall instead.
DELIVERY_OPS = ("N", "G", "X", "C", "M", "P", "GS", "XS")


def table_hash() -> str:
    text = ",".join(DELIVERY_OPS) + "|" + ",".join(VISIT_ORDER) + "|" + ",".join(QUEST_ORDER) + "|" + repr(sorted(PLANET_BITS.items())) + "|" + \
        ",".join(WATCHED_GLOBALS) + "|" + repr([vars(m) for m in MASTERS])
    return hashlib.sha1(text.encode()).hexdigest()[:8]


def received_globals(index: int) -> tuple[int, int]:
    """Number globals hold -128..127: the index is stored as two base-100 digits (up to 9999 items)."""
    return index % 100, index // 100


def identity(seed_name: str, slot: int) -> tuple[int, int, int]:
    """Three 1..99 values naming one slot of one seed (0 0 0 means unbound)."""
    digest = hashlib.sha1(f"{seed_name}:{slot}".encode()).digest()
    return tuple(1 + digest[i] % 99 for i in range(3))  # type: ignore[return-value]


class Snapshot:
    def __init__(self, line: str) -> None:
        parts = line.split(" ")
        if len(parts) < 12 or parts[0] != "S":
            raise ValueError(f"not a snapshot: {line[:60]!r}")
        self.table_hash = parts[1]
        self.content = parts[2]
        self.module = parts[3].lower()
        self.received = int(parts[4])
        self.identity = (int(parts[5]), int(parts[6]), int(parts[7]))
        self.planets = int(parts[8])
        bits = parts[9]
        self.visited = {module for module, bit in zip(VISIT_ORDER, bits) if bit == "1"}
        states = parts[10].split(",")
        self.quests = {tag: int(state) for tag, state in zip(QUEST_ORDER, states) if state.lstrip("-").isdigit()}
        self.globals = {name: int(v) for name, v in zip(WATCHED_GLOBALS, parts[11].split(",")) if v.lstrip("-").isdigit()}
