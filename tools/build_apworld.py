"""Zip worlds/kotor2 into build/kotor2.apworld (tests and __pycache__ left out)."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORLD = ROOT / "worlds" / "kotor2"


def main() -> None:
    out = ROOT / "build" / "kotor2.apworld"
    out.parent.mkdir(exist_ok=True)
    manifest = json.loads((WORLD / "archipelago.json").read_text())
    manifest.setdefault("version", 7)
    manifest.setdefault("compatible_version", 7)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(WORLD.rglob("*")):
            rel = path.relative_to(WORLD)
            if path.is_dir() or "__pycache__" in rel.parts or rel.parts[0] == "test" or rel.name == "archipelago.json":
                continue
            z.write(path, f"kotor2/{rel.as_posix()}")
        z.writestr("kotor2/archipelago.json", json.dumps(manifest, indent=1))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
