"""Dump the KOTOR 2 tables the world is designed from into research/<profile>/.

usage: .venv/bin/python tools/extract_research.py "<KOTOR 2 folder>"

Profiles: vanilla (game folder only), tslrcm (TSLRCM Workshop item on top) and tslrcm_m478 (TSLRCM + M4-78EP item),
each when its Workshop item is installed.
Writes per profile:
  journal.tsv     every quest and entry in global.jrl (tag, planet, entry id, end flag, xp, text)
  planetary.tsv   planetary.2da
  globalcat.tsv   globalcat.2da (declared globals: the only ones a save keeps)
  modules.tsv     every module and its area name (from the module's .are)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kotor_layers import WORKSHOP_PROFILES, Layers, installed_workshop_items, workshop_root  # noqa: E402
import twoda  # noqa: E402

from pykotor.common.language import Language  # noqa: E402
from pykotor.resource.formats.gff import read_gff  # noqa: E402
from pykotor.resource.formats.tlk import read_tlk  # noqa: E402
from pykotor.resource.generics.jrl import read_jrl  # noqa: E402
from pykotor.resource.type import ResourceType  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "research"


class Text:
    """dialog.tlk lookups; a Workshop item's dialog.tlk (TSLRCM ships one) replaces the game's."""

    def __init__(self, layers: Layers) -> None:
        path = Path(layers.game_folder, "dialog.tlk")
        for item in layers.workshop_ids:
            candidate = workshop_root(layers.game_folder) / item / "dialog.tlk"
            if candidate.is_file():
                path = candidate
                break
        self.tlk = read_tlk(path.read_bytes())

    def __call__(self, locstring) -> str:
        if locstring is None:
            return ""
        if locstring.stringref != -1:
            entry = self.tlk.get(locstring.stringref)
            s = entry.text if entry is not None else ""
        else:
            s = locstring.get(Language.ENGLISH, 0) or ""
        return s.replace("\n", " ").replace("\r", " ").replace("\t", " ")


def writer(path: Path):
    f = path.open("w", newline="", encoding="utf-8")
    return f, csv.writer(f, delimiter="\t", lineterminator="\n")


def dump_2da(layers: Layers, name: str, path: Path) -> None:
    table = twoda.read(layers.resource(name, ResourceType.TwoDA))  # not PyKotor's reader: see tools/twoda.py
    f, w = writer(path)
    with f:
        w.writerow(["row", *table.headers])
        for label, row in zip(table.labels, table.rows):
            w.writerow([label, *row])


def dump_journal(layers: Layers, text: Text, path: Path) -> None:
    jrl = read_jrl(layers.resource("global", ResourceType.JRL))
    f, w = writer(path)
    with f:
        w.writerow(["tag", "quest", "planet_id", "plot_index", "priority", "entry_id", "end", "xp_percentage", "text"])
        for quest in jrl.quests:
            for entry in quest.entries:
                w.writerow([quest.tag, text(quest.name), quest.planet_id, quest.plot_index, int(quest.priority),
                            entry.entry_id, int(entry.end), entry.xp_percentage, text(entry.text)[:300]])


def dump_modules(layers: Layers, text: Text, path: Path) -> None:
    f, w = writer(path)
    with f:
        w.writerow(["module", "area_name"])
        for module in layers.module_names():
            resources = layers.module_resources(module)
            name = ""
            for (resref, restype), data in resources.items():
                if restype == ResourceType.ARE:
                    name = text(read_gff(data).root.get_locstring("Name"))
                    break
            w.writerow([module, name])


def main(folder: str) -> None:
    """One research/<profile>/ per profile whose Workshop item Steam lists as installed (vanilla always). A profile
    folder already on disk is kept when its item is not installed now."""
    game = Path(folder)
    installed = set(installed_workshop_items(game))
    for profile, ids in WORKSHOP_PROFILES.items():
        if any(i not in installed or not (workshop_root(game) / i).is_dir() for i in ids):
            print(f"skipped research/{profile}/ (Workshop item {', '.join(ids)} not installed)")
            continue
        layers = Layers(game, ids)
        if layers.profile != profile:
            raise SystemExit(f"{profile}: the files look like {layers.profile}")
        out = OUT / profile
        out.mkdir(parents=True, exist_ok=True)
        text = Text(layers)
        dump_journal(layers, text, out / "journal.tsv")
        dump_2da(layers, "planetary", out / "planetary.tsv")
        dump_2da(layers, "globalcat", out / "globalcat.tsv")
        dump_modules(layers, text, out / "modules.tsv")
        print(f"wrote research/{profile}/")


if __name__ == "__main__":
    main(sys.argv[1])
