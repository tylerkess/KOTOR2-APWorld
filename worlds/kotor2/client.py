"""Archipelago client for Star Wars: Knights of the Old Republic II.

Talks to K2APBridge (version.dll in the game folder) over \\\\.\\pipe\\K2APBridge. The game side reports a snapshot
about once a second (protocol.py) and takes commands; everything that decides what to send or deliver is a pure
function here so it can be tested without the game.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import random
import time
from typing import BinaryIO, Callable, Iterable, Sequence

import Utils
from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, handle_url_arg, server_loop
from NetUtils import ClientStatus

from . import protocol
from .data import (ITEM_NAME_TO_ID, LOCATIONS, PROLOGUE_END_MODULE, PROLOGUE_QUESTS, PROLOGUE_VISITS,
                   VISIT_ALIASES)
from .world import KotOR2World

logger = logging.getLogger("Client")  # the GUI shows the "Client" logger only (kvui logging_pairs)

PIPE_NAME = r"\\.\pipe\K2APBridge"
READ_BYTES = 8192
POLL_SECONDS = 0.5
RESEND_SECONDS = 5.0  # a command batch the save has not taken after this long is sent again
GOAL_MODULES = ("904mal",)
BIND_ATTEMPTS = 20  # polls (10 s) an unbound save may stay unbound after B before the globals are blamed  # a_end_game (904MAL) calls EndGame; the bridge reports it as event "E"

CONTENT_NAMES = {0: "vanilla", 1: "tslrcm", 2: "tslrcm_m478"}  # options.Content values
ITEM_ID_TO_NAME = {item_id: name for name, item_id in ITEM_NAME_TO_ID.items()}
CRYSTALS = ("u_l_crys_01", "u_l_crys_02", "u_l_crys_03", "u_l_crys_04", "u_l_crys_05", "u_l_crys_06", "u_l_crys_07")
# Filler that scales with the player's level when it arrives (ap_tick AP_Deliver): the level their XP has earned,
# whether or not they have levelled up yet.
CREDITS_PER_LEVEL = 150  # 150 on Peragus, ~1000 on Telos, 3000 at level 20
XP_PERCENT_OF_LEVEL = 25  # a quarter of what the current level needs to reach the next (1000 x level XP)
DELIVERY: dict[str, str] = {
    "Credits": f"GS {CREDITS_PER_LEVEL}",
    "Experience": f"XS {XP_PERCENT_OF_LEVEL}",
    "Medpacs": "C g_i_medeqpmnt01 3",
    "Stimulants": "C g_i_adrnaline003 2",
    "Components": "C compont_00001 25",
    "Chemicals": "C chem_00001 25",
    "Computer Spikes": "C g_i_progspike01 3",
    "Security Spikes": "C g_i_secspike01 3",
}


class BridgeError(Exception):
    pass


def delivery_op(item_id: int, index: int, seed_name: str) -> str:
    """The ap_tick op for received item `index` (protocol.py). Unknown items (another version's) are 'N': counted,
    never applied."""
    name = ITEM_ID_TO_NAME.get(item_id)
    if name is None:
        return "N"
    if name in protocol.PLANET_BITS:
        return f"P {protocol.PLANET_BITS[name][0]}"
    if name in protocol.MASTER_BY_ITEM:
        return f"M {protocol.MASTER_BY_ITEM[name].bit}"
    rng = random.Random(f"{seed_name}:{index}")  # the same choice for the same item on every client run
    if name in protocol.GEAR_GROUPS:
        families = protocol.GEAR_GROUPS[name]
        family = rng.choices(families, weights=[f.weight for f in families])[0]
        return (f"R2 {family.prefix} {family.size} {family.skip} {protocol.GEAR_RARE_PERCENT} "
                f"{protocol.GEAR_JACKPOT_PERCENT}")
    if name == "Lightsaber":
        if rng.randrange(100) < protocol.LIGHTSABER_UNIQUE_PERCENT:
            return f"C {rng.choice(protocol.LIGHTSABER_UNIQUES)} 1"
        return f"C {rng.choice(protocol.LIGHTSABER_FORMS).format(rng.choice(protocol.LIGHTSABER_COLOURS))} 1"
    if name == "Lightsaber Crystal":  # retired item, seeds made before 2026-11-05
        return f"C {rng.choice(CRYSTALS)} 1"
    return DELIVERY.get(name, "N")


def checked_locations(snapshot: protocol.Snapshot, missing: Iterable[int]) -> set[int]:
    """Location IDs among `missing` that the snapshot shows as done."""
    wanted = set(missing)
    done: set[int] = set()
    past_prologue = PROLOGUE_END_MODULE in snapshot.visited
    for loc in LOCATIONS.values():
        if loc.location_id not in wanted:
            continue
        if past_prologue and (loc.module in PROLOGUE_VISITS or loc.quest in PROLOGUE_QUESTS):
            done.add(loc.location_id)  # played or skipped (data.PROLOGUE_END_MODULE)
        elif loc.kind == "visit" and ({loc.module, *VISIT_ALIASES.get(loc.module, ())} & snapshot.visited):
            done.add(loc.location_id)
        elif loc.kind == "quest" and snapshot.quests.get(loc.quest, 0) in loc.ends:
            done.add(loc.location_id)
        elif loc.kind == "master" and snapshot.globals.get(loc.master, 0) == 1:
            done.add(loc.location_id)
    return done


def wanted_options(slot_data: dict) -> int:
    """AP_OPTS for this slot (protocol.py)."""
    return protocol.options_value(
        m478_by_coordinates=slot_data.get("content") == 2 and slot_data.get("m4_78_access", 0) == 0,
        masters_shuffled=slot_data.get("jedi_masters", 0) == 1,
        unmet_absent=slot_data.get("unmet_masters", 0) == 1,
        masters_required=int(slot_data.get("masters_required", 4)))


def vash_counted_twice(snapshot: protocol.Snapshot) -> bool:
    """Vash's body on Korriban (702KOR tr_vash) and her M4-78 conversation both add to 000_Jedi_Found: the endgame
    could open with a master unfound (docs/DECISIONS.md D12)."""
    return snapshot.globals.get("702KOR_Vash", 0) == 1 and "805dro" in snapshot.visited


def delivery_commands(snapshot_received: int, items: Sequence[int], seed_name: str,
                      limit: int = protocol.COMMANDS_PER_TICK) -> list[str]:
    """Commands for the next items the save has not taken (ap_tick applies them in order, once each)."""
    end = min(len(items), snapshot_received + limit)
    return [f"I {i} {delivery_op(items[i], i, seed_name)}" for i in range(snapshot_received, end)]


class Bridge:
    """Request/reply over the bridge's message-mode pipe; reconnects on the next request after a failure."""

    def __init__(self, opener: Callable[..., BinaryIO] = open) -> None:
        self._opener = opener
        self._pipe: BinaryIO | None = None

    def close(self) -> None:
        if self._pipe is not None:
            with contextlib.suppress(OSError):
                self._pipe.close()
            self._pipe = None

    def request(self, text: str) -> str:
        if not text.isascii():
            text = text.encode("ascii", "replace").decode("ascii")
        try:
            if self._pipe is None:
                self._pipe = self._opener(PIPE_NAME, "r+b", 0)
            self._pipe.write(text.encode("ascii"))
            reply = self._pipe.read(READ_BYTES).decode("ascii", "replace")
        except OSError as error:
            self.close()
            raise BridgeError(f"pipe: {error}") from error
        if reply == "OK":
            return ""
        if reply.startswith("OK "):
            return reply[3:]
        raise BridgeError(f"{text.split(' ', 1)[0]}: {reply}")


class KotOR2CommandProcessor(ClientCommandProcessor):
    ctx: KotOR2Context

    def _cmd_bridge(self) -> bool:
        """Show the bridge's status: hooks, ticks, queued commands."""
        self.ctx.status_requested = True
        return True


class KotOR2Context(CommonContext):
    game = KotOR2World.game
    command_processor = KotOR2CommandProcessor
    items_handling = 0b111

    def __init__(self, server_address: str | None, password: str | None, bridge: Bridge | None = None) -> None:
        super().__init__(server_address, password)
        self.bridge = bridge or Bridge()
        self.slot_data: dict = {}
        self.status_requested = False
        self._sent_from: int | None = None  # received index the last command batch started at
        self._sent_at = 0.0
        self._last_state = ""
        self._refused = ""
        self._goal_sent = False
        self._notices: list[str] = []
        self._bind_attempts = 0
        self._vash_warned = False

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict) -> None:
        if cmd == "Connected":
            self.slot_data = args.get("slot_data", {})
            self._sent_from = None
            self._goal_sent = False
        elif cmd == "ReceivedItems":
            for item in args.get("items", []):
                if item.player != self.slot:
                    name = self.item_names.lookup_in_slot(item.item)
                    self._notices.append(f"Received {name} from {self.player_names.get(item.player, '?')}")

    @property
    def room_seed(self) -> str | None:
        """The seed the server is running. Archipelago 0.6.8 reports it as server_seed_name; seed_name stays None
        unless a patch file set it."""
        return getattr(self, "server_seed_name", None) or self.seed_name

    # ----------------------------------------------------------------------------------------------- game side
    def _state(self, text: str, level: int = logging.INFO) -> None:
        if text != self._last_state:
            logger.log(level, text)
            self._last_state = text

    def _poll(self) -> tuple[set[int], bool]:
        """One bridge round trip (runs in a worker thread). Returns new location IDs and whether the goal fired."""
        if self.status_requested:
            self.status_requested = False
            hooked, ticks, age, queued = (self.bridge.request("STATUS").split() + ["?"] * 4)[:4]
            logger.info(f"Bridge: hooks {'on' if hooked == '1' else 'OFF'}, {ticks} ticks, last {age} ms ago, "
                        f"{queued} commands queued")
            with contextlib.suppress(BridgeError, ValueError):
                snap = protocol.Snapshot(self.bridge.request("SNAP"))
                logger.info("Game: " + ", ".join(f"{k} {v}" for k, v in snap.globals.items()))
        goal = False
        while (event := self.bridge.request("EVENT")) != "":
            if event == "E":
                goal = True
        try:
            snapshot = protocol.Snapshot(self.bridge.request("SNAP"))
        except BridgeError as error:
            if "nosnap" in str(error):
                self._state("Bridge connected; load a save to start")
                return set(), False
            raise
        if snapshot.table_hash != protocol.table_hash():
            self._state("The game's ap_tick script is from another version of this world: rerun the installer",
                        logging.ERROR)
            return set(), False
        if goal and snapshot.module not in GOAL_MODULES:
            goal = False

        wanted = CONTENT_NAMES.get(self.slot_data.get("content"))
        if wanted is not None and snapshot.content != wanted:
            self._state(f"This seed was made for {wanted} content, but the game's scripts were installed for "
                        f"{snapshot.content}: fix the YAML's content option or reinstall for the right setup",
                        logging.ERROR)
            return set(), False
        seed = self.room_seed
        if self.slot is None or seed is None:
            self._state("Bridge connected; waiting for the Archipelago server")
            return set(), False
        ours = protocol.identity(seed, self.slot)
        if snapshot.identity == (0, 0, 0):
            if snapshot.received != 0:
                self._state("This save has items from an unbound session; start a new game", logging.ERROR)
                return set(), False
            self._bind_attempts += 1
            if self._bind_attempts > BIND_ATTEMPTS:
                self._state("The game does not keep Archipelago's globals: another globalcat.2da (TSLRCM's Workshop "
                            "copy?) wins over the one the installer put in override. See docs/setup_en.md.",
                            logging.ERROR)
                return set(), False
            self.bridge.request("CMD B {} {} {}".format(*ours))
            self._state("Binding this save to your slot")
            return set(), False
        self._bind_attempts = 0
        if snapshot.identity != ours:
            self._state("This save belongs to another seed or slot: load the right save", logging.WARNING)
            return set(), False
        self._state(f"Playing: {snapshot.module.upper()}")
        opts = wanted_options(self.slot_data)
        if snapshot.globals.get("AP_OPTS") != opts:
            self.bridge.request(f"CMD O {opts}")
        if vash_counted_twice(snapshot) and not self._vash_warned:
            self._vash_warned = True
            logger.warning(f"Lonna Vash was counted on Korriban and on M4-78 (masters found: "
                           f"{snapshot.globals.get('000_Jedi_Found')}). Find every master before entering the "
                           f"Dantooine Enclave Courtyard, and please report this.")

        items = [item.item for item in self.items_received]
        now = time.monotonic()
        if snapshot.received < len(items):
            if self._sent_from != snapshot.received or now - self._sent_at > RESEND_SECONDS:
                self.bridge.request("CLEAR")
                for command in delivery_commands(snapshot.received, items, seed):
                    self.bridge.request(f"CMD {command}")
                self._sent_from, self._sent_at = snapshot.received, now
        for notice in self._notices[:5]:
            self.bridge.request(f"CMD T {notice[:120]}")
        del self._notices[:5]

        return checked_locations(snapshot, self.missing_locations), goal

    async def bridge_loop(self) -> None:
        try:
            while not self.exit_event.is_set():
                try:
                    new, goal = await asyncio.to_thread(self._poll)
                    if new and self.server and not self.server.socket.closed:
                        await self.send_msgs([{"cmd": "LocationChecks", "locations": sorted(new)}])
                    if goal and not self._goal_sent and self.server and not self.server.socket.closed:
                        await self.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
                        self._goal_sent = True
                        logger.info("Goal complete!")
                except BridgeError as error:
                    self._state(f"Waiting for KOTOR 2 with K2APBridge ({error})")
                except Exception as error:  # a bug here must not end the loop silently
                    if self._last_state != f"error: {error!r}":
                        logger.exception(f"KOTOR 2 bridge loop: {error!r}")
                        self._last_state = f"error: {error!r}"
                await asyncio.sleep(POLL_SECONDS)
        finally:
            self.bridge.close()


async def _main(args: argparse.Namespace) -> None:
    ctx = KotOR2Context(args.connect, args.password)
    ctx.auth = args.name
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
    bridge_task = asyncio.create_task(ctx.bridge_loop(), name="KOTOR 2 bridge loop")
    if gui_enabled and not getattr(args, "nogui", False):
        ctx.run_gui()
    ctx.run_cli()
    try:
        await ctx.exit_event.wait()
    finally:
        bridge_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await bridge_task
        await ctx.shutdown()


def launch(*launch_args: str) -> None:
    parser = get_base_parser(description="Star Wars: Knights of the Old Republic II Archipelago Client")
    parser.add_argument("--name", default=None, help="Slot name to connect as.")
    parser.add_argument("url", nargs="?", help="archipelago:// connection URL")
    args = handle_url_arg(parser.parse_args(launch_args or None), parser)
    Utils.init_logging("KotOR2Client", exception_logger="Client")
    asyncio.run(_main(args))

