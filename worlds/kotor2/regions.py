from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification, Location, LocationProgressType, Region
from rule_builder.rules import Has, HasAll, HasFromList, Rule, True_

from . import data
from .data import Region as R
from .options import JediMasters, M478Access
from .protocol import MASTERS

if TYPE_CHECKING:
    from .world import KotOR2World


class KotOR2Location(Location):
    game = data.GAME_NAME


def coordinates(region: R) -> str:
    return data.COORDINATES[region][0]


# (from, to, rule). The prologue and Telos are linear and need nothing; the Ebon Hawk's galaxy map opens after Telos.
ENTRANCES: list[tuple[R, R, Rule]] = [
    (R.PROLOGUE, R.TELOS, True_()),
    (R.TELOS, R.EBON_HAWK, True_()),
    (R.EBON_HAWK, R.NAR_SHADDAA, Has(coordinates(R.NAR_SHADDAA))),
    (R.EBON_HAWK, R.DXUN, Has(coordinates(R.DXUN))),
    (R.DXUN, R.ONDERON, True_()),  # the Mandalorians fly you over; a_galaxymap opens Onderon once Dxun is visited
    (R.EBON_HAWK, R.DANTOOINE, Has(coordinates(R.DANTOOINE))),
    (R.EBON_HAWK, R.KORRIBAN, Has(coordinates(R.KORRIBAN))),
    # M4-78 (tslrcm_m478 content) is connected in create_regions: from the Ebon Hawk (m4_78_access coordinates_only: ap_gm_lock opens it) or
    # from Korriban (vanilla: the game also wants T3-M4 to have read Kaah's datapad, 000_M478_Found in t3m4.dlg).
]


def endgame_rule(world: KotOR2World) -> Rule:
    """vanilla masters: every master's planet. shuffled: the Jedi Master items (the game's count follows them), and
    Dantooine either way: the meeting is in its Enclave (605DAN/650DAN)."""
    if world.options.jedi_masters == JediMasters.option_shuffled:
        return HasFromList(*(m.item for m in MASTERS), count=world.options.masters_required.value) & \
            Has(coordinates(R.DANTOOINE))
    planets = data.ENDGAME_PLANETS_M478 if content(world) == "tslrcm_m478" else data.ENDGAME_PLANETS
    return HasAll(*(coordinates(r) for r in planets))


def content(world: KotOR2World) -> str:
    return data.PROFILES[world.options.content.value]


def region_exists(world: KotOR2World, region: R) -> bool:
    return content(world) in data.REGION_PROFILES.get(region, frozenset(data.PROFILES))


def location_included(world: KotOR2World, loc: data.LocationData) -> bool:
    if content(world) not in loc.profiles or not region_exists(world, loc.region):
        return False
    if loc.kind == "quest" and loc.tier == "side" and world.options.questsanity.value < 2:
        return False
    if loc.kind == "visit" and loc.tier == "side" and not world.options.side_areas:
        return False
    return True


def create_regions(world: KotOR2World) -> None:
    regions = {r: Region(r.value, world.player, world.multiworld) for r in R if region_exists(world, r)}
    menu = Region("Menu", world.player, world.multiworld)
    world.multiworld.regions += [menu, *regions.values()]
    menu.connect(regions[R.PROLOGUE])

    for name, loc in data.LOCATIONS.items():
        if not location_included(world, loc):
            continue
        location = KotOR2Location(world.player, name, loc.location_id, regions[loc.region])
        if not loc.progression_ok:
            location.progress_type = LocationProgressType.EXCLUDED
        regions[loc.region].locations.append(location)

    for source, target, rule in ENTRANCES:
        if source in regions and target in regions:
            entrance = regions[source].connect(regions[target], f"{source.value} -> {target.value}")
            world.set_rule(entrance, rule)

    if R.M4_78 in regions:
        source = R.KORRIBAN if world.options.m4_78_access == M478Access.option_vanilla else R.EBON_HAWK
        m4 = regions[source].connect(regions[R.M4_78], f"{source.value} -> {R.M4_78.value}")
        world.set_rule(m4, Has(coordinates(R.M4_78)))

    endgame = regions[R.EBON_HAWK].connect(regions[R.ENDGAME], f"{R.EBON_HAWK.value} -> {R.ENDGAME.value}")
    world.set_rule(endgame, endgame_rule(world))

    victory = KotOR2Location(world.player, data.EVENT_VICTORY, None, regions[R.ENDGAME])
    victory.place_locked_item(Item(data.EVENT_VICTORY, ItemClassification.progression, None, world.player))
    regions[R.ENDGAME].locations.append(victory)
