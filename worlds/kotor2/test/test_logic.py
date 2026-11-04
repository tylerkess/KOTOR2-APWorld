from BaseClasses import LocationProgressType

from ..data import (COORDINATES, ENDGAME_PLANETS, ENDGAME_PLANETS_M478, EVENT_VICTORY, ITEMS, LOCATIONS,
                    NO_RETURN_REGIONS, Region)
from ..protocol import MASTERS
from . import KotOR2TestBase


def coords(region: Region) -> str:
    return COORDINATES[region][0]


def location_names(test: KotOR2TestBase) -> set[str]:
    return {loc.name for loc in test.multiworld.get_locations(test.player)}


def pool_names(test: KotOR2TestBase) -> list[str]:
    return [item.name for item in test.multiworld.itempool if item.player == test.player]


class TestDefaults(KotOR2TestBase):  # content: tslrcm
    def test_prologue_telos_and_hawk_are_open(self) -> None:
        for region in (Region.PROLOGUE, Region.TELOS, Region.EBON_HAWK):
            self.assertTrue(self.can_reach_region(region.value), region)

    def test_each_planet_needs_its_coordinates(self) -> None:
        for region in (Region.NAR_SHADDAA, Region.DXUN, Region.DANTOOINE, Region.KORRIBAN):
            self.assertFalse(self.can_reach_region(region.value), region)
            self.collect_by_name(coords(region))
            self.assertTrue(self.can_reach_region(region.value), region)

    def test_onderon_comes_with_dxun(self) -> None:
        self.assertFalse(self.can_reach_region(Region.ONDERON.value))
        self.collect_by_name(coords(Region.DXUN))
        self.assertTrue(self.can_reach_region(Region.ONDERON.value))

    def test_endgame_needs_the_four_masters_planets(self) -> None:
        for region in ENDGAME_PLANETS:
            self.assertFalse(self.can_reach_region(Region.ENDGAME.value))
            self.collect_by_name(coords(region))
        self.assertTrue(self.can_reach_region(Region.ENDGAME.value))
        self.assertTrue(self.can_reach_location(EVENT_VICTORY))

    def test_no_m4_78_and_vash_on_korriban(self) -> None:
        names = location_names(self)
        self.assertNotIn(Region.M4_78.value, {r.name for r in self.multiworld.get_regions(self.player)})
        self.assertNotIn(coords(Region.M4_78), pool_names(self))
        self.assertIn("Korriban: Find Lonna Vash", names)
        self.assertNotIn("M4-78: Find Lonna Vash", names)
        for name in names:
            if name != EVENT_VICTORY:
                self.assertIn("tslrcm", LOCATIONS[name].profiles, name)

    def test_endgame_and_side_checks_hold_no_progression(self) -> None:
        for location in self.multiworld.get_locations(self.player):
            if location.address is None:
                continue
            loc = LOCATIONS[location.name]
            if loc.region in NO_RETURN_REGIONS or loc.tier == "side":
                self.assertEqual(location.progress_type, LocationProgressType.EXCLUDED, location.name)

    def test_fill_keeps_progression_out_of_excluded_checks(self) -> None:
        from Fill import distribute_items_restrictive
        from worlds.AutoWorld import call_all
        for seed in range(10):
            with self.subTest(seed=seed):
                self.world_setup(seed)
                distribute_items_restrictive(self.multiworld)
                call_all(self.multiworld, "post_fill")
                for location in self.multiworld.get_locations(self.player):
                    if location.progress_type == LocationProgressType.EXCLUDED:
                        self.assertFalse(location.item.advancement, location.name)
                self.assertTrue(self.multiworld.can_beat_game(self.multiworld.state))

    def test_coordinates_in_pool(self) -> None:
        names = pool_names(self)
        for name, item in ITEMS.items():
            if "Coordinates" in item.groups:
                self.assertEqual(names.count(name), 1 if "tslrcm" in item.profiles else 0, name)
        self.assertFalse(any(n.startswith("Jedi Master: ") for n in names))


class TestM478(KotOR2TestBase):
    options = {"content": "tslrcm_m478"}

    def test_m4_78_needs_only_its_coordinates(self) -> None:
        self.assertFalse(self.can_reach_region(Region.M4_78.value))
        self.collect_by_name(coords(Region.M4_78))
        self.assertTrue(self.can_reach_region(Region.M4_78.value))

    def test_endgame_needs_m4_78_too(self) -> None:  # Vash is on M4-78 with M4-78EP
        for region in ENDGAME_PLANETS_M478:
            self.assertFalse(self.can_reach_region(Region.ENDGAME.value))
            self.collect_by_name(coords(region))
        self.assertTrue(self.can_reach_region(Region.ENDGAME.value))

    def test_vash_on_m4_78(self) -> None:
        names = location_names(self)
        self.assertIn("M4-78: Find Lonna Vash", names)
        self.assertNotIn("Korriban: Find Lonna Vash", names)


class TestM478VanillaAccess(KotOR2TestBase):
    options = {"content": "tslrcm_m478", "m4_78_access": "vanilla"}

    def test_m4_78_is_reached_through_korriban(self) -> None:
        self.collect_by_name(coords(Region.M4_78))
        self.assertFalse(self.can_reach_region(Region.M4_78.value))
        self.collect_by_name(coords(Region.KORRIBAN))
        self.assertTrue(self.can_reach_region(Region.M4_78.value))


class TestVanilla(KotOR2TestBase):
    options = {"content": "vanilla"}

    def test_only_vanilla_content(self) -> None:
        for name in location_names(self):
            if name != EVENT_VICTORY:
                self.assertIn("vanilla", LOCATIONS[name].profiles, name)
        self.assertNotIn(coords(Region.M4_78), pool_names(self))
        self.assertIn("Korriban: Find Lonna Vash", location_names(self))

    def test_endgame_needs_korriban(self) -> None:
        for region in ENDGAME_PLANETS:
            self.assertFalse(self.can_reach_region(Region.ENDGAME.value))
            self.collect_by_name(coords(region))
        self.assertTrue(self.can_reach_region(Region.ENDGAME.value))


class TestStoryOnly(KotOR2TestBase):
    options = {"questsanity": "story", "side_areas": False}

    def test_only_story_checks(self) -> None:
        for location in self.multiworld.get_locations(self.player):
            if location.address is not None:
                self.assertEqual(LOCATIONS[location.name].tier, "story", location.name)


class TestShuffledMasters(KotOR2TestBase):
    options = {"content": "tslrcm_m478", "jedi_masters": "shuffled", "masters_required": 2}

    def test_endgame_waits_for_master_items_not_planets(self) -> None:
        for region in ENDGAME_PLANETS_M478:
            self.collect_by_name(coords(region))
        self.assertFalse(self.can_reach_region(Region.ENDGAME.value))
        self.collect_by_name(MASTERS[0].item)
        self.assertFalse(self.can_reach_region(Region.ENDGAME.value))
        self.collect_by_name(MASTERS[3].item)
        self.assertTrue(self.can_reach_region(Region.ENDGAME.value))

    def test_meeting_still_needs_dantooine(self) -> None:
        for master in MASTERS:
            self.collect_by_name(master.item)
        self.assertFalse(self.can_reach_region(Region.ENDGAME.value))
        self.collect_by_name(coords(Region.DANTOOINE))
        self.assertTrue(self.can_reach_region(Region.ENDGAME.value))

    def test_master_items_in_pool(self) -> None:
        self.assertEqual(sum(1 for n in pool_names(self) if n.startswith("Jedi Master: ")), 4)
