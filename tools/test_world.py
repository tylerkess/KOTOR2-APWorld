"""Run the world's tests inside an Archipelago checkout.

usage: python tools/test_world.py [pytest arguments]
AP_DIR: the Archipelago checkout (default: ../ME1-APWorld/vendor/Archipelago, which has a .venv with pytest).
The world is symlinked into <AP_DIR>/worlds/kotor2 for the run and always removed afterwards.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORLD = os.path.join(REPO, "worlds", "kotor2")
AP = os.environ.get("AP_DIR", os.path.join(REPO, "..", "ME1-APWorld", "vendor", "Archipelago"))
TARGET = os.path.join(AP, "worlds", "kotor2")


def ap_python() -> str:
    for rel in (("Scripts", "python.exe"), ("bin", "python")):
        path = os.path.join(AP, ".venv", *rel)
        if os.path.exists(path):
            return path
    raise SystemExit(f"no .venv in {AP}: set AP_DIR to an Archipelago checkout with a virtual environment")


def main(args: list[str]) -> int:
    if os.path.lexists(TARGET):
        raise SystemExit(f"{TARGET} already exists: remove it first")
    try:
        os.symlink(WORLD, TARGET, target_is_directory=True)
    except OSError:
        shutil.copytree(WORLD, TARGET, ignore=shutil.ignore_patterns("__pycache__"))
    try:
        return subprocess.run([ap_python(), "-m", "pytest", "-p", "no:cacheprovider", "-q",
                               os.path.join("worlds", "kotor2", "test"), *args], cwd=AP).returncode
    finally:
        if os.path.islink(TARGET):
            os.remove(TARGET)
        elif os.path.isdir(TARGET):
            shutil.rmtree(TARGET)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
