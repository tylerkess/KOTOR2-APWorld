from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification, LocationProgressType

from . import data
from .protocol import MASTERS

if TYPE_CHECKING:
    from .world import KotOR2World


class KotOR2Item(Item):
    game = data.GAME_NAME


def create_item(world: KotOR2World, name: str) -> KotOR2Item:
    return KotOR2Item(name, data.ITEMS[name].classification, data.ITEM_NAME_TO_ID[name], world.player)


def create_items(world: KotOR2World) -> None:
    content = data.PROFILES[world.options.content.value]
    pool = [create_item(world, name) for name, item in data.ITEMS.items()
            for _ in range(item.count) if content in item.profiles]
    if world.options.jedi_masters == world.options.jedi_masters.option_shuffled:
        pool += [create_item(world, m.item) for m in MASTERS]  # a fixed order: generation must be reproducible

    unfilled = world.multiworld.get_unfilled_locations(world.player)
    if len(pool) > len(unfilled):
        raise RuntimeError(f"{data.GAME_NAME}: {len(pool)} items for {len(unfilled)} locations")
    # Useful items avoid excluded locations, which are reserved for filler.
    room = sum(1 for loc in unfilled if loc.progress_type != LocationProgressType.EXCLUDED) - len(pool)
    for _ in range(len(unfilled) - len(pool)):
        name = world.get_filler_item_name()
        while data.ITEMS[name].classification & ItemClassification.useful and room <= 0:
            name = world.get_filler_item_name()
        if data.ITEMS[name].classification & ItemClassification.useful:
            room -= 1
        pool.append(create_item(world, name))
    world.multiworld.itempool += pool
