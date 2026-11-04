from BaseClasses import Tutorial
from worlds.AutoWorld import WebWorld

from .options import option_groups


class KotOR2WebWorld(WebWorld):
    game = "Star Wars Knights of the Old Republic II"
    theme = "dirt"
    setup_en = Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up Star Wars: Knights of the Old Republic II for Archipelago.",
        "English",
        "setup_en.md",
        "setup/en",
        ["Tyler"],
    )
    tutorials = [setup_en]
    option_groups = option_groups
