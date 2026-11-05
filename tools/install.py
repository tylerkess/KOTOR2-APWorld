"""Install or remove the KOTOR 2 Archipelago game files.

usage:
  .venv/bin/python tools/install.py "<KOTOR 2 folder>" [--profile vanilla|tslrcm]   build and install
  .venv/bin/python tools/install.py "<KOTOR 2 folder>" --uninstall                   put everything back

Installs into the game's override/ folder: ap_tick.ncs, ap_gm_lock.ncs, a_galaxymap.ncs (patched from your own
game's copy) and globalcat.2da (your effective table plus our rows), and bridge/build/version.dll next to
swkotor2.exe when it has been built. globalcat.2da also replaces the copy in any installed Workshop item that ships
one, since a Workshop item's override/ beats the game's (docs/DECISIONS.md D18). Any file it replaces is backed up first. A receipt (k2ap_receipt.json in the game
folder) lists what was added and replaced, and --uninstall reverses exactly that.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from kotor_layers import BACKUP, RECEIPT, backup_path, installed_workshop_items, workshop_root  # noqa: E402


def override_dir(game: Path) -> Path:
    for child in game.iterdir():
        if child.is_dir() and child.name.lower() == "override":
            return child
    path = game / "override"
    path.mkdir()
    return path


def place(src: Path, dst: Path, game: Path, receipt: dict) -> None:
    rel = Path(os.path.relpath(dst, game)).as_posix()
    if dst.exists() and rel not in receipt["added"] and rel not in receipt["replaced"]:
        backup = backup_path(game, rel)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, backup)
        receipt["replaced"].append(rel)
    elif not dst.exists():
        receipt["added"].append(rel)
    if dst.exists() and dst.read_bytes() == src.read_bytes():
        return  # unchanged (and version.dll may be locked by a running game)
    shutil.copy2(src, dst)


def workshop_globalcats(game: Path) -> list[Path]:
    """globalcat.2da in installed Workshop items' override folders. The game loads a Workshop item's override before
    its own (seen in game 2026-11-05 with TSLRCM: rows only in the game's override/globalcat.2da were not kept), so
    ours must replace these too. Our copy is the effective table plus our rows, so the mod keeps its own."""
    root = workshop_root(game)
    found = []
    for item in installed_workshop_items(game):
        override = next((c for c in (root / item).glob("*") if c.is_dir() and c.name.lower() == "override"), None)
        if override is not None:
            found += [c for c in override.iterdir() if c.name.lower() == "globalcat.2da"]
    return found


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
        for target in workshop_globalcats(game):
            place(Path(staging) / "globalcat.2da", target, game, receipt)
            print(f"globalcat.2da also written to Workshop item {target.parent.parent.name} (backed up; --uninstall "
                  f"restores it)")
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
        shutil.copy2(backup_path(game, rel), game / rel)
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
