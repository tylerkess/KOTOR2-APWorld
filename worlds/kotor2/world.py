from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from rule_builder.rules import Has
from worlds.AutoWorld import World

from . import data, items, regions, web_world
from . import options as k2_options


class KotOR2World(World):
    """
    Five years after the Jedi Civil War, the last Jedi wakes on a mining colony at the edge of the galaxy. Find the
    coordinates scattered across the multiworld, track down the hidden Jedi Masters and face the true Sith on
    Malachor V.
    """

    game = data.GAME_NAME
    web = web_world.KotOR2WebWorld()
    options_dataclass = k2_options.KotOR2Options
    options: k2_options.KotOR2Options
    origin_region_name = "Menu"

    item_name_to_id: ClassVar[dict[str, int]] = data.ITEM_NAME_TO_ID
    location_name_to_id: ClassVar[dict[str, int]] = data.LOCATION_NAME_TO_ID
    item_name_groups = data.ITEM_NAME_GROUPS
    location_name_groups = data.LOCATION_NAME_GROUPS

    def create_regions(self) -> None:
        regions.create_regions(self)

    def create_items(self) -> None:
        items.create_items(self)

    def create_item(self, name: str) -> items.KotOR2Item:
        return items.create_item(self, name)

    def get_filler_item_name(self) -> str:
        return self.random.choices(data.FILLER, weights=data.FILLER_WEIGHTS)[0]

    def set_rules(self) -> None:
        self.set_completion_rule(Has(data.EVENT_VICTORY))

    def fill_slot_data(self) -> Mapping[str, Any]:
        return {
            **self.options.as_dict("content", "m4_78_access", "jedi_masters", "masters_required", "unmet_masters",
                                 "questsanity", "side_areas"),
            "world_version": WORLD_VERSION,
        }


WORLD_VERSION = "0.0.1"
