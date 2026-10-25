#!/usr/bin/env python3
"""Reject a packaged GUI shim that cannot supply this device's Android 11 ABI.

This checks ELF imports/exports and the installed-versus-built file, not a
successful HAL load, compatible object layouts, or working display/cameras.
"""
import argparse
from pathlib import Path
import sys

from elf32 import Elf32


def validate(shim, libui, callstack):
    gui, ui, stack = Elf32(shim), Elf32(libui), Elf32(callstack)
    if any(elf.machine != 40 for elf in (gui, ui, stack)):
        raise ValueError("expected ARM ELF32 libraries")
    required = (
        "_ZN7android19GraphicBufferMapper4lockEPK13native_handlejRKNS_4RectEPPv",
        "_ZN7android19GraphicBufferMapper4lockEPK13native_handleiRKNS_4RectEPPv",
        "_ZN7android13GraphicBuffer4lockEjPPv",
    )
    for name in required:
        if not gui.exports(name):
            raise ValueError("GUI shim does not export " + name)
    if "libutilscallstack.so" not in gui.needed:
        raise ValueError("GUI shim must load libutilscallstack for its MTK camera clients")
    for name, symbol in gui.symbols.items():
        if symbol["section"] == 0 and symbol["binding"] == 1 and (
                "GraphicBuffer" in name or "Fence" in name) and not ui.exports(name):
            raise ValueError("libui does not supply shim import " + name)
    if not stack.exports("_ZN7android9CallStackC1Ev"):
        raise ValueError("CallStack constructor is unavailable")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product", type=Path, help="out/target/product/grandppltedx")
    args = parser.parse_args()
    root = args.product
    installed = root / "system/vendor/lib/libshim_gui.so"
    built = root / "obj/SHARED_LIBRARIES/libshim_gui_intermediates/libshim_gui.so"
    try:
        validate(installed, root / "system/lib/libui.so", root / "system/lib/libutilscallstack.so")
        if installed.read_bytes() != built.read_bytes():
            raise ValueError("installed GUI shim differs from the stripped source-built module")
    except (OSError, ValueError) as error:
        print("FAIL:", error, file=sys.stderr)
        return 1
    print("GUI shim exports/imports and source-built packaging passed; device tests remain required.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
