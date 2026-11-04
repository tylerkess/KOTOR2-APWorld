"""Print a compiled NWScript (.ncs) as an instruction listing with routine names (KOTOR 2).

usage: .venv/bin/python tools/ncs_listing.py <file.ncs>
PyKotor's PyPI build has no decompiler (its DeNCS module is missing), so this is the reading aid.
"""
from __future__ import annotations

import logging
import sys

logging.disable(logging.CRITICAL)
from pykotor.common.scriptdefs import TSL_FUNCTIONS  # noqa: E402
from pykotor.resource.formats.ncs import read_ncs  # noqa: E402


def main(path: str) -> None:
    ncs = read_ncs(open(path, "rb").read())
    index = {id(ins): i for i, ins in enumerate(ncs.instructions)}
    for i, ins in enumerate(ncs.instructions):
        name = ins.ins_type.name
        args = list(ins.args)
        if name.startswith("ACTION"):
            args = [f"{TSL_FUNCTIONS[args[0]].name}({args[0]})", f"argc={args[1]}"]
        jump = f" -> {index.get(id(ins.jump))}" if ins.jump is not None else ""
        print(f"{i:5} {name:12} {' '.join(map(str, args))}{jump}")


if __name__ == "__main__":
    main(sys.argv[1])
