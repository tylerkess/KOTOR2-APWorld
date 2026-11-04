"""Install or remove the KOTOR 2 Archipelago game files.

usage:
  .venv/bin/python tools/install.py "<KOTOR 2 folder>" [--profile vanilla|tslrcm]   build and install
  .venv/bin/python tools/install.py "<KOTOR 2 folder>" --uninstall                   put everything back

Installs into the game's override/ folder: ap_tick.ncs, ap_gm_lock.ncs, a_galaxymap.ncs (patched from your own
game's copy) and globalcat.2da (your effective table plus our rows), and bridge/build/version.dll next to
swkotor2.exe when it has been built. Any file it replaces is backed up first. A receipt (k2ap_receipt.json in the game
folder) lists what was added and replaced, and --uninstall reverses exactly that.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECEIPT = "k2ap_receipt.json"
BACKUP = "k2ap_backup"


def override_dir(game: Path) -> Path:
    for child in game.iterdir():
        if child.is_dir() and child.name.lower() == "override":
            return child
    path = game / "override"
    path.mkdir()
    return path


def place(src: Path, dst: Path, game: Path, receipt: dict) -> None:
    rel = str(dst.relative_to(game))
    if dst.exists() and rel not in receipt["added"] and rel not in receipt["replaced"]:
        backup = game / BACKUP / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, backup)
        receipt["replaced"].append(rel)
    elif not dst.exists():
        receipt["added"].append(rel)
    shutil.copy2(src, dst)


def install(game: Path, profile: str | None) -> None:
    if not (game / "swkotor2.exe").exists():
        raise SystemExit(f"{game} has no swkotor2.exe")
    receipt_path = game / RECEIPT
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {"added": [], "replaced": []}
    with tempfile.TemporaryDirectory() as staging:
        cmd = [sys.executable, str(ROOT / "tools" / "build_scripts.py"), str(game), "--out", staging]
        if profile:
            cmd += ["--profile", profile]
        subprocess.run(cmd, check=True)
        override = override_dir(game)
        for path in sorted(Path(staging).iterdir()):
            place(path, override / path.name, game, receipt)
    dll = ROOT / "bridge" / "build" / "version.dll"
    if dll.exists():
        place(dll, game / "version.dll", game, receipt)
    else:
        print("bridge/build/version.dll not built: scripts installed, bridge NOT installed (see bridge/build.sh)")
    receipt_path.write_text(json.dumps(receipt, indent=1))
    print(f"installed; receipt {receipt_path}")


def uninstall(game: Path) -> None:
    receipt_path = game / RECEIPT
    if not receipt_path.exists():
        raise SystemExit("nothing to uninstall (no receipt)")
    receipt = json.loads(receipt_path.read_text())
    for rel in receipt["added"]:
        (game / rel).unlink(missing_ok=True)
    for rel in receipt["replaced"]:
        shutil.copy2(game / BACKUP / rel, game / rel)
    shutil.rmtree(game / BACKUP, ignore_errors=True)
    receipt_path.unlink()
    print(f"removed {len(receipt['added'])} files, restored {len(receipt['replaced'])}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("game")
    ap.add_argument("--profile", choices=("vanilla", "tslrcm", "tslrcm_m478"))
    ap.add_argument("--uninstall", action="store_true")
    args = ap.parse_args()
    (uninstall if args.uninstall else lambda g: install(g, args.profile))(Path(args.game))


if __name__ == "__main__":
    main()
