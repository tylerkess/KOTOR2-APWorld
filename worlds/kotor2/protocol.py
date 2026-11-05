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
from dataclasses import dataclass

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
DELIVERY_OPS = ("N", "G", "X", "C", "M", "P", "GS", "XS", "R2")  # R2: gear with a jackpot chance


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


# ------------------------------------------------------------------------------------------------------ gear filler
# The game's own random loot (k_plc_it_* scripts) creates <prefix><NN>: NN 01..size, rising in value, picked from the
# player's level. A gear item names a group; the client picks a family in it, ap_tick picks NN from the earned level
# at delivery (op "R2 <prefix> <size> <skip> <rare %> <jackpot %>", nss/ap_tick.nss AP_GiveGear).
@dataclass(frozen=True)
class GearFamily:
    prefix: str
    size: int
    weight: int = 2  # within its group
    skip: int = 0  # a number the game lacks (a_gloves_03), replaced by its neighbour


GEAR_GROUPS: dict[str, tuple[GearFamily, ...]] = {
    "Weapon": (GearFamily("w_blaste_", 30), GearFamily("w_brifle_", 30), GearFamily("w_melee_", 30)),
    "Armor": (GearFamily("a_light_", 15), GearFamily("a_medium_", 15), GearFamily("a_heavy_", 15),
              GearFamily("a_robe_", 30)),
    "Equipment": (GearFamily("a_belt_", 30), GearFamily("a_gloves_", 30, skip=3), GearFamily("a_helmet_", 30),
                  GearFamily("e_imp1_", 10, 1), GearFamily("e_imp2_", 10, 1), GearFamily("e_imp3_", 10, 1),
                  GearFamily("e_imp4_", 10, 1), GearFamily("a_shield_", 7, 1)),
    "Upgrade": (GearFamily("u_a_over_", 30), GearFamily("u_a_unde_", 30), GearFamily("u_m_cell_", 15),
                GearFamily("u_m_edge_", 15), GearFamily("u_m_grip_", 15), GearFamily("u_r_firi_", 15),
                GearFamily("u_r_powe_", 15), GearFamily("u_r_targ_", 15)),
    "Lightsaber Part": (GearFamily("u_l_crys_", 25, 3), GearFamily("u_l_cell_", 13), GearFamily("u_l_emit_", 13),
                        GearFamily("u_l_lens_", 13)),
    "Droid Gear": (GearFamily("d_armor_", 15), GearFamily("d_device_", 15), GearFamily("d_interface_", 15),
                   GearFamily("d_tool_", 15), GearFamily("d_shield_", 6, 1)),
}
GEAR_RARE_PERCENT = 9  # chance a gear item rolls 0..+12 above the level instead of the game's window
GEAR_JACKPOT_PERCENT = 1  # chance it lands anywhere from level +3 up to tier 30

# Lightsabers: the number is only the blade colour (no 06). Uniques replace one now and then.
LIGHTSABER_COLOURS = ("01", "02", "03", "04", "05", "07", "08", "09", "10", "11")
LIGHTSABER_FORMS = ("g_w_lghtsbr{}", "g_w_shortsbr{}", "g_w_dblsbr0{}")
LIGHTSABER_UNIQUES = ("g1_w_lghtsbr01", "g1_w_lghtsbr02", "g1_w_shortsbr01", "g1_w_shortsbr02", "g1_w_dblsbr001",
                      "g1_w_dblsbr002", "w_sls_x02", "w_ls_x01", "g_w_drkjdisbr001", "g_w_drkjdisbr002")
LIGHTSABER_UNIQUE_PERCENT = 10


def gear_resrefs() -> set[str]:
    """Every template a gear or lightsaber delivery can create."""
    out = {f"{f.prefix}{n:02d}" for families in GEAR_GROUPS.values() for f in families
           for n in range(1, f.size + 1) if n != f.skip}
    out |= {form.format(colour) for form in LIGHTSABER_FORMS for colour in LIGHTSABER_COLOURS}
    return out | set(LIGHTSABER_UNIQUES)

