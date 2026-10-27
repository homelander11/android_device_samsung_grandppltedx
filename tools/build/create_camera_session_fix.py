#!/usr/bin/env python3
"""Package the libcamcx preview-session correction and exact helper-only undo.

Requires the camera/audio, colour and graphics guard updates on the pinned ROM.
All dependencies and old/new helper hashes are checked before the single write.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import zipfile

import create_camera_fix as camera
import create_camera_colour_fix as colour
import create_display_fix as base

MANIFEST = json.loads((camera.TOOLS / "camera/preview-session.json").read_text())
MOUNT = "/tmp/j2prime-session-system"
VERIFY = "/tmp/j2prime-session-verify.sh"
LIBRARY = "lib/libcamcx.so"


def checks():
    result = colour.checks()
    result["lib/hw/gralloc.mt6735.so"] = MANIFEST["requires_gralloc_sha256"]
    return result


def check(path, *hashes):
    args = ", ".join('"' + value + '"' for value in ("/sbin/sh", VERIFY, path, *hashes))
    return f'assert(run_program({args}) == "0");'


def package(path, updater, payload):
    vendor = MOUNT + "/system/vendor/"
    target = vendor + LIBRARY
    lines = [
        'ui_print("J2 Prime camera preview-session correction / helper undo");',
        f'assert(package_extract_file("verify-session.sh", "{VERIFY}"));',
        'assert(!is_mounted("/system") && !is_mounted("/system_root"));',
        f'assert(mount("ext4", "EMMC", "{base.BLOCK}", "{MOUNT}") != "");',
        f'assert(file_getprop("{MOUNT}/system/build.prop", "ro.lineage.version") == "{base.VERSION}");',
        f'assert(file_getprop("{MOUNT}/system/build.prop", "ro.build.version.sdk") == "30");',
    ]
    lines += [check(vendor + name, digest) for name, digest in sorted(checks().items())]
    lines += [
        check(target, MANIFEST["original_sha256"], MANIFEST["patched_sha256"]),
        f'assert(package_extract_file("libcamcx.so", "{target}"));',
        f'set_metadata("{target}", "uid", 0, "gid", 0, "mode", 0644, "selabel", "u:object_r:vendor_file:s0");',
        check(target, base.sha(payload)),
        f'assert(unmount("{MOUNT}") != "");',
        'ui_print("Camera helper verified. Reboot System without wiping.");',
    ]
    entries = {
        base.PREFIX + "update-binary": updater,
        base.PREFIX + "updater-script": ("\n".join(lines) + "\n").encode(),
        "verify-session.sh": camera.VERIFIER,
        "libcamcx.so": payload,
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 27, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith("update-binary") else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("generated ZIP CRC failure")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom_zip", type=Path)
    parser.add_argument("old_helper", type=Path)
    parser.add_argument("new_helper", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if base.sha(args.rom_zip.read_bytes()) != base.ROM_SHA256:
            raise ValueError("input ROM differs from the diagnosed build")
        old, new = args.old_helper.read_bytes(), args.new_helper.read_bytes()
        if base.sha(old) != MANIFEST["original_sha256"] or base.sha(new) != MANIFEST["patched_sha256"]:
            raise ValueError("unexpected old/new preview-session helper hashes")
        before, after = base.Elf32(args.old_helper), base.Elf32(args.new_helper)
        exports = [n for n, s in before.symbols.items() if s["section"] and s["binding"] in (1, 2)]
        if after.machine != 40 or before.needed != after.needed or not all(after.exports(n) for n in exports):
            raise ValueError("preview-session helper changed the required ARM exports/dependencies")
        global_symbols = False
        for section in after.sections:
            if section[1] == 6:
                for offset in range(section[4], section[4] + section[5], section[9]):
                    tag, value = struct.unpack_from("<iI", new, offset)
                    if tag == 0x6ffffffb and value & 2:
                        global_symbols = True
        if not global_symbols:
            raise ValueError("preview-session helper requires DF_1_GLOBAL")
        with zipfile.ZipFile(args.rom_zip) as archive:
            updater = archive.read(base.PREFIX + "update-binary")
        args.out_dir.mkdir(parents=True, exist_ok=True)
        sums = []
        for suffix, payload in (("fix", new), ("undo", old)):
            path = args.out_dir / f"grandppltedx-20261027-camera-session-{suffix}.zip"
            package(path, updater, payload)
            sums.append(f"{base.sha(path.read_bytes())}  {path.name}\n")
            print(path, path.stat().st_size, "bytes")
        (args.out_dir / "CAMERA-SESSION-SHA256SUMS").write_text("".join(sums), encoding="ascii")
    except (OSError, ValueError) as error:
        print("FAIL:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
