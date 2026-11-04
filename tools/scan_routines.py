"""Find every compiled script that calls given NWScript routines (by ID).

usage: .venv/bin/python tools/scan_routines.py "<KOTOR 2 folder>" <profile: vanilla|tslrcm> <routine id> [...]
Prints: source  script  routine-id  count. NCS ACTION is opcode 0x05, type 0x00, routine (uint16 BE), argc (uint8).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kotor_layers import TSLRCM_WORKSHOP_ID, Layers, _ci_children, _read_capsule  # noqa: E402

from pykotor.resource.type import ResourceType  # noqa: E402


def calls(data: bytes, ids: set[int]) -> dict[int, int]:
    found: dict[int, int] = {}
    for m in re.finditer(rb"\x05\x00(..)(.)", data, re.S):
        rid = int.from_bytes(m.group(1), "big")
        if rid in ids:
            found[rid] = found.get(rid, 0) + 1
    return found


def scripts(layers: Layers):
    """(source, resref, data), winner only: override layers, then module capsules, then chitin."""
    seen: set[str] = set()
    for files in layers._override_dirs:
        for name, path in files.items():
            if name.endswith(".ncs") and name[:-4] not in seen:
                seen.add(name[:-4])
                yield "override", name[:-4], path.read_bytes()
    for module in layers.module_names():
        for (resref, restype), data in layers.module_resources(module).items():
            if restype == ResourceType.NCS and (module, resref) not in seen:
                yield module, resref, data
    for res in layers.inst.core_resources():
        if res.restype() == ResourceType.NCS and res.resname().lower() not in seen:
            yield "chitin", res.resname().lower(), res.data()


def main(folder: str, profile: str, ids: list[int]) -> None:
    layers = Layers(Path(folder), (TSLRCM_WORKSHOP_ID,) if profile == "tslrcm" else ())
    for source, resref, data in scripts(layers):
        for rid, n in sorted(calls(data, set(ids)).items()):
            print(f"{source}\t{resref}\t{rid}\t{n}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3:]])
