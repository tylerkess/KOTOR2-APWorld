"""Resolve KOTOR 2 resources the way the game sees them, with or without Steam Workshop mods.

The Aspyr build loads Workshop items from steamapps/workshop/content/208580/<id>/ (their override/ and modules/ folders)
on top of the game folder. PyKotor's Installation knows only the game folder, so this module puts the given Workshop
items' files in front of it. The order of `workshop_ids` is the priority order (first wins).

Unverified (docs/DECISIONS.md D3): whether the game's own override/ folder beats a Workshop item's override/. Lookups
here put Workshop items first.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logging.disable(logging.CRITICAL)  # PyKotor logs every case-insensitive lookup

from pykotor.extract.installation import Installation
from pykotor.resource.formats.erf import read_erf
from pykotor.resource.formats.rim import read_rim
from pykotor.resource.type import ResourceType

import re

TSLRCM_WORKSHOP_ID = "485537937"  # "The Sith Lords Restored Content Mod" (TSLRCM)
TSLRCM_M478_WORKSHOP_ID = "1402798020"  # "TSLRCM + M4-78EP" (one Workshop item holds both)
WORKSHOP_PROFILES = {"vanilla": (), "tslrcm": (TSLRCM_WORKSHOP_ID,), "tslrcm_m478": (TSLRCM_M478_WORKSHOP_ID,)}
PROFILES = ("vanilla", "tslrcm", "tslrcm_m478")
# Modules that tell the setups apart (whatever installed them: Workshop or a manual install into Modules/).
M478_MODULE = "801dro"  # M4-78EP
TSLRCM_MODULE = "298tel"  # TSLRCM's restored HK factory (also in TSLRCM + M4-78EP)


def installed_workshop_items(game_folder: Path) -> list[str]:
    """Items Steam lists as installed (appworkshop_208580.acf). Folders alone are not enough: Steam leaves files
    behind when an item is unsubscribed."""
    acf = game_folder.parent.parent / "workshop" / "appworkshop_208580.acf"
    if not acf.is_file():
        return []
    text = acf.read_text(encoding="utf-8", errors="replace")
    block = text.split('"WorkshopItemsInstalled"', 1)[-1].split('"WorkshopItemDetails"', 1)[0]
    return re.findall(r'^\s*"(\d+)"\s*$', block, re.M)


def workshop_root(game_folder: Path) -> Path:
    """steamapps/common/<game> -> steamapps/workshop/content/208580"""
    return game_folder.parent.parent / "workshop" / "content" / "208580"


def _ci_children(folder: Path) -> dict[str, Path]:
    return {p.name.lower(): p for p in folder.iterdir()} if folder.is_dir() else {}


def _ci_dir(parent: Path, name: str) -> Path | None:
    return _ci_children(parent).get(name.lower())


@dataclass
class Layers:
    game_folder: Path
    workshop_ids: tuple[str, ...] = ()
    inst: Installation = field(init=False)
    _override_dirs: list[dict[str, Path]] = field(init=False)
    _module_dirs: list[dict[str, Path]] = field(init=False)

    def __post_init__(self) -> None:
        self.inst = Installation(str(self.game_folder))
        root = workshop_root(self.game_folder)
        self._override_dirs, self._module_dirs = [], []
        for item in self.workshop_ids:
            base = root / item
            if not base.is_dir():
                raise FileNotFoundError(f"Workshop item {item} not installed ({base})")
            if (d := _ci_dir(base, "override")) is not None:
                self._override_dirs.append(_ci_children(d))
            if (d := _ci_dir(base, "modules")) is not None:
                self._module_dirs.append(_ci_children(d))
        if (d := _ci_dir(self.game_folder, "override")) is not None:
            self._override_dirs.append(_ci_children(d))

    @property
    def profile(self) -> str:
        """vanilla, tslrcm or tslrcm_m478, from the modules the game would load."""
        modules = set(self.module_names())
        if M478_MODULE in modules:
            return "tslrcm_m478"
        return "tslrcm" if TSLRCM_MODULE in modules else "vanilla"

    @classmethod
    def installed(cls, game_folder: Path) -> "Layers":
        """The game as the player has it: every Workshop item Steam lists as installed (cosmetic ones included)."""
        root = workshop_root(game_folder)
        return cls(game_folder, tuple(i for i in installed_workshop_items(game_folder) if (root / i).is_dir()))

    def override(self, resref: str, restype: ResourceType) -> bytes | None:
        filename = f"{resref}.{restype.extension}".lower()
        for files in self._override_dirs:
            if filename in files:
                return files[filename].read_bytes()
        return None

    def resource(self, resref: str, restype: ResourceType) -> bytes | None:
        """Override layers, then the game's own lookup (modules are not searched: use module_resource)."""
        data = self.override(resref, restype)
        if data is not None:
            return data
        found = self.inst.resource(resref, restype)
        return None if found is None else found.data

    def module_names(self) -> list[str]:
        """Module resrefs (e.g. 101per), base game and Workshop modules together, lower case."""
        names = set()
        for path in Path(self.game_folder, "Modules").iterdir():
            n = path.name.lower()
            if n.endswith(".rim") and not n.endswith("_s.rim"):
                names.add(n[:-4])
            elif n.endswith(".mod"):
                names.add(n[:-4])
        for files in self._module_dirs:
            for n in files:
                if n.endswith(".mod") or (n.endswith(".rim") and not n.endswith("_s.rim")):
                    names.add(n[:-4])
        return sorted(names)

    def module_resources(self, module: str) -> dict[tuple[str, ResourceType], bytes]:
        """Every resource of a module: a .mod (Workshop first, then Modules/) replaces the module's .rim files."""
        module = module.lower()
        for files in self._module_dirs:
            if f"{module}.mod" in files:
                return _read_capsule(files[f"{module}.mod"])
        game_modules = _ci_children(Path(self.game_folder, "Modules"))
        if f"{module}.mod" in game_modules:
            return _read_capsule(game_modules[f"{module}.mod"])
        out: dict[tuple[str, ResourceType], bytes] = {}
        for suffix in (".rim", "_s.rim", "_dlg.erf"):
            for files in self._module_dirs:
                if module + suffix in files:
                    out.update(_read_capsule(files[module + suffix]))
                    break
            else:
                if module + suffix in game_modules:
                    out.update(_read_capsule(game_modules[module + suffix]))
        return out


def _read_capsule(path: Path) -> dict[tuple[str, ResourceType], bytes]:
    data = path.read_bytes()
    capsule = read_rim(data) if path.name.lower().endswith(".rim") else read_erf(data)
    return {(str(r.resref).lower(), r.restype): r.data for r in capsule}
