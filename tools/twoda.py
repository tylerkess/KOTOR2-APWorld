"""Binary 2DA (V2.b) reader and writer that tolerate what the game tolerates.

PyKotor 2.3.12 trusts the data-size field before the string block. TSLRCM's globalcat.2da (and others written by
some tools) store 0 there; the game ignores the field, PyKotor then reads every cell as "" (found 2026-11-04: a
merged globalcat built that way would have undeclared every global in the game). This reader uses the rest of the
file as the string block; the writer always stores the real size.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

MAGIC = b"2DA V2.b\n"


@dataclass
class Table:
    headers: list[str]
    labels: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)

    def column(self, name: str) -> list[str]:
        i = self.headers.index(name)
        return [row[i] for row in self.rows]

    def add(self, values: dict[str, str]) -> None:
        self.labels.append(str(len(self.rows)))
        self.rows.append([values.get(h, "") for h in self.headers])


def read(data: bytes) -> Table:
    if not data.startswith(MAGIC):
        raise ValueError("not a binary 2DA (V2.b)")
    end = data.index(b"\0", len(MAGIC))
    headers = data[len(MAGIC):end].decode("latin-1").split("\t")[:-1]
    p = end + 1
    (count,) = struct.unpack_from("<I", data, p)
    p += 4
    labels = []
    for _ in range(count):
        tab = data.index(b"\t", p)
        labels.append(data[p:tab].decode("latin-1"))
        p = tab + 1
    n = count * len(headers)
    offsets = struct.unpack_from(f"<{n}H", data, p)
    p += 2 * n + 2  # the data-size field is not trusted
    block = data[p:]

    def cell(offset: int) -> str:
        return block[offset:block.index(b"\0", offset)].decode("latin-1")

    rows = [[cell(offsets[r * len(headers) + c]) for c in range(len(headers))] for r in range(count)]
    return Table(headers, labels, rows)


def write(table: Table) -> bytes:
    out = bytearray(MAGIC)
    out += "".join(h + "\t" for h in table.headers).encode("latin-1") + b"\0"
    out += struct.pack("<I", len(table.rows))
    out += "".join(label + "\t" for label in table.labels).encode("latin-1")
    strings: dict[str, int] = {}
    block = bytearray()
    offsets = []
    for row in table.rows:
        for value in row:
            if value not in strings:
                strings[value] = len(block)
                block += value.encode("latin-1") + b"\0"
            offsets.append(strings[value])
    if len(block) > 0xFFFF:
        raise ValueError("2DA string block over 64 KiB")
    out += struct.pack(f"<{len(offsets)}H", *offsets)
    out += struct.pack("<H", len(block))
    out += block
    return bytes(out)
