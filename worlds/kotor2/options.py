from dataclasses import dataclass

from Options import Choice, DefaultOnToggle, OptionGroup, PerGameCommonOptions, Range


class Content(Choice):
    """Which version of the game you play. Pick what you actually have installed: the installer bakes it into the game
    scripts and the client refuses a seed made for another one.

    vanilla: the game as released.
    tslrcm: The Sith Lords Restored Content Mod.
    tslrcm_m478: TSLRCM plus the M4-78 Enhancement Project (the Workshop "TSLRCM + M4-78EP" item, or both installed).
    M4-78 is a planet to unlock, and Lonna Vash is found there instead of on Korriban."""

    display_name = "Game Content"
    option_vanilla = 0
    option_tslrcm = 1
    option_tslrcm_m478 = 2
    default = 1


class Questsanity(Choice):
    """Which completed quests are checks (any outcome counts, so light side and dark side choices both send it).

    story: the critical-path quests only.
    all: also side quests and bonus missions. Side quests only ever hold filler: a choice can skip them."""

    display_name = "Questsanity"
    option_story = 1
    option_all = 2
    default = 2


class SideAreas(DefaultOnToggle):
    """Visiting optional areas (swoop tracks, Telos side districts, turret sequences, ...) are checks.
    They only ever hold filler."""

    display_name = "Optional Area Visits"


class M478Access(Choice):
    """How M4-78 opens (tslrcm_m478 content only).

    coordinates_only: the M4-78 Coordinates item alone opens it on the galaxy map, before or after Korriban. Korriban
    plays as usual either way (T3-M4 still reads Kaah's datapad).
    vanilla: as in the game, T3-M4 must also have read Kaah's datapad from the Korriban Sith Academy."""

    display_name = "M4-78 Access"
    option_coordinates_only = 0
    option_vanilla = 1
    default = 0


class JediMasters(Choice):
    """How the hidden Jedi Masters (Zez-Kai Ell, Kavar, Vrook, Lonna Vash) count toward the endgame.

    vanilla: as in the game, you must find all four, so every master's planet is needed.
    shuffled: four Jedi Master items are in the pool and the endgame waits for them instead; finding a master is a
    check like any other, so a seed can skip whole planets. Kill or invite is still your choice whenever you meet one."""

    display_name = "Jedi Masters"
    option_vanilla = 0
    option_shuffled = 1
    default = 0


class MastersRequired(Range):
    """With shuffled Jedi Masters: how many Jedi Master items open the endgame."""

    display_name = "Jedi Masters Required"
    range_start = 1
    range_end = 4
    default = 4


class UnmetMasters(Choice):
    """With shuffled Jedi Masters: what the masters' meeting on Dantooine does with a master you never met.

    attend: they come as if you had invited them.
    absent: they are treated as dead, as if you had killed them (a darker ending)."""

    display_name = "Unmet Masters"
    option_attend = 0
    option_absent = 1
    default = 0


@dataclass
class KotOR2Options(PerGameCommonOptions):
    content: Content
    m4_78_access: M478Access
    jedi_masters: JediMasters
    masters_required: MastersRequired
    unmet_masters: UnmetMasters
    questsanity: Questsanity
    side_areas: SideAreas


option_groups = [
    OptionGroup("Game", [Content, M478Access]),
    OptionGroup("Jedi Masters", [JediMasters, MastersRequired, UnmetMasters]),
    OptionGroup("Checks", [Questsanity, SideAreas]),
]
