"""Static tables for the KOTOR 2 world: regions, items, locations.

IDs are an append-only ledger: never renumber or reuse an ID. Quest and module IDs come from tables.py (generated);
this file decides which of them are checks, where they sit and whether they may hold progression.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from BaseClasses import ItemClassification

from .protocol import MASTERS
from .tables import MODULES, QUESTS

GAME_NAME = "Star Wars Knights of the Old Republic II"
ID_BASE = 0x4B32_0000  # "K2"
# Offsets inside ID_BASE: items 0x0000-0x0FFF; locations: 0x1000 + module id (area visits), 0x2000 + quest id (quests).
VISIT_OFFSET = 0x1000
QUEST_OFFSET = 0x2000
MASTER_OFFSET = 0x3000


class Region(str, Enum):
    PROLOGUE = "Peragus and the Harbinger"
    TELOS = "Telos"
    EBON_HAWK = "Ebon Hawk"
    NAR_SHADDAA = "Nar Shaddaa"
    DXUN = "Dxun"
    ONDERON = "Onderon"
    DANTOOINE = "Dantooine"
    KORRIBAN = "Korriban"
    M4_78 = "M4-78"
    ENDGAME = "Endgame"  # the masters' meeting onwards: Telos academy, the Ravager, Malachor V


# Entering the endgame takes the Ebon Hawk away for good: these regions never hold this world's progression.
NO_RETURN_REGIONS = frozenset({Region.ENDGAME})
PROFILES = ("vanilla", "tslrcm", "tslrcm_m478")  # Content option values, in order
REGION_PROFILES = {Region.M4_78: frozenset({"tslrcm_m478"})}  # regions that exist only with some content

# Galaxy-map planet rows (planetary.2da) each access item unlocks; a_galaxymap checks them (DECISIONS D5).
COORDINATES: dict[Region, tuple[str, tuple[int, ...]]] = {
    Region.NAR_SHADDAA: ("Nar Shaddaa Coordinates", (6,)),
    Region.DXUN: ("Dxun and Onderon Coordinates", (1, 7)),
    Region.DANTOOINE: ("Dantooine Coordinates", (0,)),
    Region.KORRIBAN: ("Korriban Coordinates", (3,)),
    Region.M4_78: ("M4-78 Coordinates", (4,)),
}
# The endgame starts on entering the Enclave Courtyard (605DAN k_enter_605) with 000_Jedi_Found >= 4. Each master adds
# one: Zez-Kai Ell (303NAR zezkaiel.dlg), Kavar (506OND kavar.dlg), Vrook (602DAN vrook.dlg) and Lonna Vash: her body
# on Korriban (702KOR tr_vash) in vanilla, her conversation on M4-78 (805DRO vash01.dlg) with M4-78EP.
ENDGAME_PLANETS = (Region.NAR_SHADDAA, Region.DXUN, Region.DANTOOINE, Region.KORRIBAN)  # vanilla, tslrcm
ENDGAME_PLANETS_M478 = (*ENDGAME_PLANETS, Region.M4_78)  # tslrcm_m478

EVENT_VICTORY = "Victory"


@dataclass(frozen=True)
class ItemData:
    offset: int
    classification: ItemClassification
    count: int = 1
    groups: frozenset[str] = field(default_factory=frozenset)
    profiles: frozenset[str] = frozenset({"vanilla", "tslrcm", "tslrcm_m478"})  # content options it exists in


_P = ItemClassification.progression
ITEMS: dict[str, ItemData] = {
    # 0x00-0x0F planet access
    "Nar Shaddaa Coordinates": ItemData(0x00, _P, groups=frozenset({"Coordinates"})),
    "Dxun and Onderon Coordinates": ItemData(0x01, _P, groups=frozenset({"Coordinates"})),
    "Dantooine Coordinates": ItemData(0x02, _P, groups=frozenset({"Coordinates"})),
    "Korriban Coordinates": ItemData(0x03, _P, groups=frozenset({"Coordinates"})),
    "M4-78 Coordinates": ItemData(0x04, _P, groups=frozenset({"Coordinates"}), profiles=frozenset({"tslrcm_m478"})),
    # 0x10-0x1F Jedi Masters (jedi_masters shuffled only: count set in items.create_items)
    **{m.item: ItemData(0x10 + m.bit, _P, count=0, groups=frozenset({"Jedi Masters"})) for m in MASTERS},
    # 0x40-0x5F filler and useful (the client turns each into a delivery op, client.DELIVERY)
    "Credits": ItemData(0x40, ItemClassification.filler, count=0),
    "Medpacs": ItemData(0x41, ItemClassification.filler, count=0),
    "Stimulants": ItemData(0x42, ItemClassification.filler, count=0),
    "Components": ItemData(0x43, ItemClassification.filler, count=0),
    "Chemicals": ItemData(0x44, ItemClassification.filler, count=0),
    "Experience": ItemData(0x45, ItemClassification.filler, count=0),
    "Computer Spikes": ItemData(0x46, ItemClassification.filler, count=0),
    "Security Spikes": ItemData(0x47, ItemClassification.filler, count=0),
    # gear (protocol.GEAR_GROUPS): the tier follows the player's level when it arrives
    **{name: ItemData(0x48 + i, ItemClassification.filler, count=0, groups=frozenset({"Gear"}))
       for i, name in enumerate(("Weapon", "Armor", "Equipment", "Upgrade", "Lightsaber Part", "Droid Gear"))},
    "Lightsaber": ItemData(0x4E, ItemClassification.useful, count=0, groups=frozenset({"Gear"})),
    # Retired 2026-11-05 (now part of "Lightsaber Part"); kept so seeds made before still deliver it.
    "Lightsaber Crystal": ItemData(0x50, ItemClassification.useful, count=0, groups=frozenset({"Gear"})),
}
# Filler draw, in percent: 30 consumables, 15 credits, 15 experience, 40 gear.
FILLER_TABLE = {
    "Credits": 15, "Experience": 15,
    "Medpacs": 7, "Stimulants": 5, "Components": 6, "Chemicals": 6, "Computer Spikes": 3, "Security Spikes": 3,
    "Weapon": 9, "Armor": 8, "Equipment": 9, "Upgrade": 7, "Lightsaber Part": 3, "Droid Gear": 2, "Lightsaber": 2,
}
FILLER = tuple(FILLER_TABLE)
FILLER_WEIGHTS = tuple(FILLER_TABLE.values())

ITEM_NAME_TO_ID = {name: ID_BASE + data.offset for name, data in ITEMS.items()}
ITEM_NAME_GROUPS = {
    group: {name for name, data in ITEMS.items() if group in data.groups}
    for group in sorted({g for data in ITEMS.values() for g in data.groups})
}


@dataclass(frozen=True)
class LocationData:
    location_id: int
    region: Region
    kind: str  # "visit", "quest" or "master"
    tier: str  # "story" (always on, may hold progression) or "side" (questsanity all; filler only)
    profiles: frozenset[str]  # content options it exists in (vanilla, tslrcm, tslrcm_m478)
    module: str | None = None  # visit: the module resref (lower case)
    quest: str | None = None  # quest: the journal tag
    ends: tuple[int, ...] = ()  # quest: journal entry ids that complete it (any outcome)
    master: str | None = None  # master: the AP_M_* global ap_tick sets once that master is found

    @property
    def progression_ok(self) -> bool:
        """May hold this world's progression: a story check outside the no-return regions."""
        return self.tier == "story" and self.region not in NO_RETURN_REGIONS


R = Region
# Area visits. "story": on the critical path, so it can't be missed (Peragus and Telos close once you leave them).
# "side": optional or unconfirmed areas, filler only. Modules not listed are not checks (cutscene and duplicate
# modules: 006EBO, 007EBO, 205TEL, 352NAR, 950COR, ...).
VISITS: dict[str, tuple[Region, str]] = {
    "001ebo": (R.PROLOGUE, "story"),
    "101per": (R.PROLOGUE, "story"), "102per": (R.PROLOGUE, "story"), "103per": (R.PROLOGUE, "story"),
    "104per": (R.PROLOGUE, "story"), "105per": (R.PROLOGUE, "story"), "106per": (R.PROLOGUE, "story"),
    "107per": (R.PROLOGUE, "story"),
    "151har": (R.PROLOGUE, "story"), "152har": (R.PROLOGUE, "story"), "153har": (R.PROLOGUE, "story"),
    "201tel": (R.TELOS, "story"), "202tel": (R.TELOS, "side"), "203tel": (R.TELOS, "side"),
    "204tel": (R.TELOS, "side"), "207tel": (R.TELOS, "side"), "208tel": (R.TELOS, "side"),
    "209tel": (R.TELOS, "side"), "211tel": (R.TELOS, "side"), "220tel": (R.TELOS, "side"),
    "221tel": (R.TELOS, "side"), "222tel": (R.TELOS, "side"), "231tel": (R.TELOS, "story"),
    "232tel": (R.TELOS, "story"), "233tel": (R.TELOS, "side"), "261tel": (R.TELOS, "story"),
    "262tel": (R.TELOS, "story"),
    "003ebo": (R.EBON_HAWK, "story"),
    "301nar": (R.NAR_SHADDAA, "story"), "302nar": (R.NAR_SHADDAA, "story"), "303nar": (R.NAR_SHADDAA, "story"),
    "304nar": (R.NAR_SHADDAA, "story"), "305nar": (R.NAR_SHADDAA, "story"), "306nar": (R.NAR_SHADDAA, "story"),
    "351nar": (R.NAR_SHADDAA, "story"), "371nar": (R.NAR_SHADDAA, "side"),
    "401dxn": (R.DXUN, "story"), "402dxn": (R.DXUN, "story"), "403dxn": (R.DXUN, "story"),
    "404dxn": (R.DXUN, "side"), "410dxn": (R.DXUN, "story"), "411dxn": (R.DXUN, "story"),
    "421dxn": (R.DXUN, "side"),
    "501ond": (R.ONDERON, "story"), "502ond": (R.ONDERON, "story"), "503ond": (R.ONDERON, "side"),
    "504ond": (R.ONDERON, "side"), "505ond": (R.ONDERON, "side"), "506ond": (R.ONDERON, "story"),
    "510ond": (R.ONDERON, "side"), "511ond": (R.ONDERON, "side"), "512ond": (R.ONDERON, "side"),
    "601dan": (R.DANTOOINE, "story"), "602dan": (R.DANTOOINE, "story"), "603dan": (R.DANTOOINE, "side"),
    "604dan": (R.DANTOOINE, "side"), "605dan": (R.DANTOOINE, "story"), "610dan": (R.DANTOOINE, "story"),
    "701kor": (R.KORRIBAN, "story"), "702kor": (R.KORRIBAN, "story"), "710kor": (R.KORRIBAN, "side"),
    "711kor": (R.KORRIBAN, "story"),
    # M4-78EP: a mandatory mission once open; Lonna Vash (the fourth master) is in the Main Behavior Core (805DRO).
    "801dro": (R.M4_78, "story"), "802dro": (R.M4_78, "story"), "803dro": (R.M4_78, "story"),
    "804dro": (R.M4_78, "story"), "805dro": (R.M4_78, "story"), "806dro": (R.M4_78, "side"),
    "807dro": (R.M4_78, "side"),
    "650dan": (R.ENDGAME, "side"),
    "851nih": (R.ENDGAME, "side"), "852nih": (R.ENDGAME, "side"),
    "901mal": (R.ENDGAME, "side"), "902mal": (R.ENDGAME, "side"), "903mal": (R.ENDGAME, "side"),
    "904mal": (R.ENDGAME, "side"), "905mal": (R.ENDGAME, "side"), "906mal": (R.ENDGAME, "side"),
    "907mal": (R.ENDGAME, "side"),
}

# A visit also counts in these modules (TSLRCM's Korriban valley leads to 702KOR or 703KOR, both "Sith Academy").
VISIT_ALIASES: dict[str, tuple[str, ...]] = {"702kor": ("703kor",)}
# The prologue (001EBO, T3-M4 on the Ebon Hawk) can be skipped from the new-game screen; either way the game continues
# in 101PER. So 101PER counts as finishing the prologue: its visit and its quests are sent then (docs/DECISIONS.md D19).
PROLOGUE_END_MODULE = "101per"
PROLOGUE_VISITS = frozenset({"001ebo"})
PROLOGUE_QUESTS = frozenset({"tutorial_garage", "tutorial_heal_pc", "tutorial_3CFD", "tutorial_fix_ebo"})

# Quests: completed (any end entry, so every choice sends it). "story": on the critical path. Quests not listed are
# not checks (no end entry, or not tied to one place: PcForce, ForceChain, JediRelics, pazaak rules, ...).
_PLANET_REGION = {0: R.DANTOOINE, 1: R.DXUN, 2: R.EBON_HAWK, 3: R.KORRIBAN, 4: R.M4_78, 6: R.NAR_SHADDAA,
                  7: R.ONDERON, 8: R.PROLOGUE, 9: R.TELOS}
QUEST_OVERRIDES: dict[str, tuple[Region, str] | None] = {
    # story
    "tutorial_fix_ebo": (R.PROLOGUE, "story"),
    "TurboliftLockdown": (R.PROLOGUE, "story"),
    "RecoverEbonHawk": (R.PROLOGUE, "story"),
    "arrested": (R.TELOS, "story"),
    "ehstolen": (R.TELOS, "story"),
    "pricepassage": (R.DXUN, "story"),
    "m478active": (R.M4_78, "story"),
    # regions the journal's planet column gets wrong
    "tutorial_garage": (R.PROLOGUE, "side"), "tutorial_heal_pc": (R.PROLOGUE, "side"),
    "tutorial_3CFD": (R.PROLOGUE, "side"),
    "LightsaberQuest": (R.EBON_HAWK, "side"), "GalacticHistory": (R.EBON_HAWK, "side"),
    "LostJedi": (R.ENDGAME, "side"), "DefeatDarthNihilus": (R.ENDGAME, "side"),
    "DestroyRavager": (R.ENDGAME, "side"), "MassShadowGenerator": (R.ENDGAME, "side"),
    "hkfactory": (R.ENDGAME, "side"), "telosfactory": (R.ENDGAME, "side"), "generation51": (R.ENDGAME, "side"),
    # not checks
    "PcForce": None, "ForceChain": None, "JediRelics": None, "EscapeMiningFacility": None, "DroidEspionage": None,
    "pazaak_rules": None, "pazaak_rules2": None,
}


# Finding a master (talking or fighting, either counts). Vash is on Korriban (her body) in vanilla and TSLRCM, on M4-78
# with M4-78EP.
_ALL = frozenset(PROFILES)
_NO_EP = frozenset({"vanilla", "tslrcm"})
_EP = frozenset({"tslrcm_m478"})
MASTER_LOCATIONS: tuple[tuple[str, int, Region, str, frozenset[str]], ...] = (
    # name, offset, region, master global, content
    ("Nar Shaddaa: Find Zez-Kai Ell", 0, R.NAR_SHADDAA, "AP_M_ZEZ", _ALL),
    ("Onderon: Find Kavar", 1, R.ONDERON, "AP_M_KAVAR", _ALL),
    ("Dantooine: Find Vrook", 2, R.DANTOOINE, "AP_M_VROOK", _ALL),
    ("Korriban: Find Lonna Vash", 3, R.KORRIBAN, "AP_M_VASH", _NO_EP),
    ("M4-78: Find Lonna Vash", 4, R.M4_78, "AP_M_VASH", _EP),
)


def _locations() -> dict[str, LocationData]:
    out: dict[str, LocationData] = {}
    for name, offset, region, flag, profiles in MASTER_LOCATIONS:
        out[name] = LocationData(ID_BASE + MASTER_OFFSET + offset, region, "master", "story", profiles, master=flag)
    for module, (region, tier) in VISITS.items():
        mid, area, profiles = MODULES[module]
        name = f"{area} ({module.upper()})" if area.lower() != "untitled" else module.upper()
        out[f"Visit {name}"] = LocationData(ID_BASE + VISIT_OFFSET + mid, region, "visit", tier,
                                            frozenset(profiles), module=module)
    for tag, (qid, quest, planet, ends, profiles) in QUESTS.items():
        if not ends or not profiles:
            continue
        place = QUEST_OVERRIDES.get(tag, (_PLANET_REGION.get(planet), "side"))
        if place is None or place[0] is None:
            continue
        region, tier = place
        out[f"{region.value}: {quest}"] = LocationData(ID_BASE + QUEST_OFFSET + qid, region, "quest", tier,
                                                       frozenset(profiles), quest=tag, ends=ends)
    return out


LOCATIONS: dict[str, LocationData] = _locations()
LOCATION_NAME_TO_ID = {name: loc.location_id for name, loc in LOCATIONS.items()}
LOCATION_NAME_GROUPS = {
    **{region.value: {n for n, loc in LOCATIONS.items() if loc.region is region} for region in Region},
    "Visits": {n for n, loc in LOCATIONS.items() if loc.kind == "visit"},
    "Quests": {n for n, loc in LOCATIONS.items() if loc.kind == "quest"},
    "Jedi Masters": {n for n, loc in LOCATIONS.items() if loc.kind == "master"},
}
