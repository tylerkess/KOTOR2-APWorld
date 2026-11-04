import unittest

from .. import protocol
from ..client import (Bridge, KotOR2Context, checked_locations, delivery_commands, delivery_op, vash_counted_twice,
                      wanted_options)
from ..data import ITEM_NAME_TO_ID, LOCATIONS
from . import KotOR2TestBase


def snapshot_line(module="101PER", received=0, identity=(0, 0, 0), visited=(), quests=None, globals_=None,
                  content="tslrcm") -> str:
    bits = "".join("1" if m in visited else "0" for m in protocol.VISIT_ORDER)
    quests = quests or {}
    states = ",".join(str(quests.get(tag, 0)) for tag in protocol.QUEST_ORDER)
    watched = ",".join(str((globals_ or {}).get(name, 0)) for name in protocol.WATCHED_GLOBALS)
    return (f"S {protocol.table_hash()} {content} {module} {received} {identity[0]} {identity[1]} {identity[2]} 0 {bits} "
            f"{states} {watched}")


class TestProtocol(KotOR2TestBase):
    run_default_tests = False

    def test_snapshot_round_trip(self) -> None:
        snap = protocol.Snapshot(snapshot_line("201TEL", 7, (1, 2, 3), {"101per", "201tel"}, {"arrested": 30}))
        self.assertEqual(snap.module, "201tel")
        self.assertEqual(snap.received, 7)
        self.assertEqual(snap.identity, (1, 2, 3))
        self.assertEqual(snap.visited, {"101per", "201tel"})
        self.assertEqual(snap.quests["arrested"], 30)

    def test_checks_from_snapshot(self) -> None:
        visit = next(loc for loc in LOCATIONS.values() if loc.module == "201tel")
        quest = next(loc for loc in LOCATIONS.values() if loc.quest == "arrested")
        missing = {visit.location_id, quest.location_id}
        snap = protocol.Snapshot(snapshot_line(visited={"201tel"}, quests={"arrested": 10}))
        self.assertEqual(checked_locations(snap, missing), {visit.location_id})  # 10 is not an end state
        snap = protocol.Snapshot(snapshot_line(visited={"201tel"}, quests={"arrested": quest.ends[0]}))
        self.assertEqual(checked_locations(snap, missing), missing)

    def test_tslrcm_academy_counts_as_the_academy_visit(self) -> None:
        academy = next(loc for loc in LOCATIONS.values() if loc.module == "702kor")
        snap = protocol.Snapshot(snapshot_line(visited={"703kor"}))
        self.assertEqual(checked_locations(snap, {academy.location_id}), {academy.location_id})

    def test_options_and_vash_warning(self) -> None:
        self.assertEqual(wanted_options({"content": 2, "m4_78_access": 0}), protocol.OPT_M478_BY_COORDINATES)
        self.assertEqual(wanted_options({"content": 2, "m4_78_access": 1}), 0)
        self.assertEqual(wanted_options({"content": 1, "m4_78_access": 0}), 0)
        snap = protocol.Snapshot(snapshot_line(visited={"805dro"}, globals_={"702KOR_Vash": 1, "000_Jedi_Found": 5}))
        self.assertEqual(snap.globals["000_Jedi_Found"], 5)
        self.assertTrue(vash_counted_twice(snap))
        self.assertFalse(vash_counted_twice(protocol.Snapshot(snapshot_line(visited={"805dro"}))))

    def test_master_checks_and_items(self) -> None:
        find = next(loc for loc in LOCATIONS.values() if loc.master == "AP_M_KAVAR")
        snap = protocol.Snapshot(snapshot_line(globals_={"AP_M_KAVAR": 1}))
        self.assertEqual(checked_locations(snap, {find.location_id}), {find.location_id})
        self.assertEqual(delivery_op(ITEM_NAME_TO_ID["Jedi Master: Lonna Vash"], 0, "s"), "M 3")

    def test_options_encoding(self) -> None:
        value = wanted_options({"content": 2, "m4_78_access": 0, "jedi_masters": 1, "masters_required": 3,
                                "unmet_masters": 1})
        self.assertEqual(value & 7, 7)
        self.assertEqual(value >> protocol.OPT_MASTERS_REQUIRED_SHIFT, 3)
        self.assertEqual(wanted_options({"content": 2, "m4_78_access": 0, "jedi_masters": 0, "unmet_masters": 1}), 1)
        self.assertLess(protocol.options_value(True, True, True, 4), 128)  # a Number global holds -128..127

    def test_delivery_ops(self) -> None:
        self.assertEqual(delivery_op(ITEM_NAME_TO_ID["Dantooine Coordinates"], 0, "s"), "P 2")
        self.assertEqual(delivery_op(ITEM_NAME_TO_ID["Credits"], 0, "s"), "G 750")
        self.assertEqual(delivery_op(123, 0, "s"), "N")
        crystal = ITEM_NAME_TO_ID["Lightsaber Crystal"]
        self.assertEqual(delivery_op(crystal, 4, "seed"), delivery_op(crystal, 4, "seed"))
        self.assertTrue(delivery_op(crystal, 4, "seed").startswith("C u_l_crys_"))

    def test_delivery_commands_start_at_the_save_index(self) -> None:
        items = [ITEM_NAME_TO_ID["Credits"]] * 30
        commands = delivery_commands(3, items, "s")
        self.assertEqual(len(commands), protocol.COMMANDS_PER_TICK)
        self.assertTrue(commands[0].startswith("I 3 "))
        self.assertEqual(delivery_commands(30, items, "s"), [])


class FakePipe:
    def __init__(self, game: "FakeGame") -> None:
        self.game = game
        self.reply = b""

    def write(self, data: bytes) -> None:
        self.reply = self.game.handle(data.decode()).encode()

    def read(self, _n: int) -> bytes:
        return self.reply

    def close(self) -> None:
        pass


class FakeGame:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.snapshot = snapshot_line()

    def handle(self, request: str) -> str:
        verb, _, arg = request.partition(" ")
        if verb == "SNAP":
            return "OK " + self.snapshot
        if verb == "EVENT":
            return "OK"
        if verb == "CMD":
            self.commands.append(arg)
            return "OK"
        if verb == "CLEAR":
            self.commands.clear()
            return "OK"
        return "ERR badrequest"


class TestPoll(unittest.IsolatedAsyncioTestCase):  # CommonContext needs a running event loop
    def make(self) -> tuple[KotOR2Context, FakeGame]:
        game = FakeGame()
        ctx = KotOR2Context(None, None, Bridge(opener=lambda *_: FakePipe(game)))
        ctx.slot, ctx.seed_name = 1, "seed"
        return ctx, game

    async def test_unbound_save_is_bound(self) -> None:
        ctx, game = self.make()
        ctx._poll()
        self.assertEqual(game.commands, ["B {} {} {}".format(*protocol.identity("seed", 1))])

    async def test_wrong_content_is_refused(self) -> None:
        ctx, game = self.make()
        ctx.slot_data = {"content": 2}
        game.snapshot = snapshot_line(content="tslrcm")
        self.assertEqual(ctx._poll(), (set(), False))
        self.assertEqual(game.commands, [])  # not even bound

    async def test_foreign_save_is_left_alone(self) -> None:
        ctx, game = self.make()
        game.snapshot = snapshot_line(identity=(9, 9, 9), visited={"101per"})
        self.assertEqual(ctx._poll(), (set(), False))
        self.assertEqual(game.commands, [])

    async def test_items_are_sent_from_the_save_index(self) -> None:
        from NetUtils import NetworkItem
        ctx, game = self.make()
        ours = protocol.identity("seed", 1)
        ctx.items_received = [NetworkItem(ITEM_NAME_TO_ID["Credits"], 0, 0), NetworkItem(ITEM_NAME_TO_ID["Korriban Coordinates"], 0, 0)]
        game.snapshot = snapshot_line(identity=ours, received=1)
        ctx._poll()
        self.assertEqual(game.commands, ["I 1 P 3"])
        ctx._poll()  # nothing new within RESEND_SECONDS: no duplicate batch
        self.assertEqual(game.commands, ["I 1 P 3"])
