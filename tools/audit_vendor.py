#!/usr/bin/env python3
"""Inventory vendor ELF dependencies without executing proprietary code."""
import argparse
import json
from pathlib import Path
from elf32 import Elf32


def inventory(root):
    result = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        with path.open("rb") as stream:
            if stream.read(4) != b"\x7fELF":
                continue
        elf = Elf32(path)
        result[path.relative_to(root).as_posix()] = elf
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vendor", type=Path, help="proprietary/vendor directory")
    parser.add_argument("--json", type=Path, help="write a machine-readable inventory")
    args = parser.parse_args()
    elfs = inventory(args.vendor)
    modules = [path for path, elf in elfs.items() if elf.exports("HMI")]
    names = {Path(path).name for path in elfs}
    report = {
        "elf_count": len(elfs), "hal_modules": modules,
        "files": {path: {"machine": elf.machine, "needed": elf.needed,
                         "dependencies_outside_snapshot": [
                             name for name in elf.needed if name not in names]}
                  for path, elf in elfs.items()},
    }
    print(f"Inventoried {len(elfs)} ELF files; {len(modules)} HAL module exports.")
    for module in modules:
        print(f"HAL: {module}")
    if not any(Path(path).name.startswith("camera.") for path in modules):
        print("BLOCKER: no camera HAL module in the vendor snapshot")
    print("Dependencies outside the snapshot may be built by Android; this is not ldd.")
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
