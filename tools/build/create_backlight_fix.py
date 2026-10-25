#!/usr/bin/env python3
"""Package the tested single-byte BACKLIGHT fix and exact undo for TWRP.

Requires the diagnosed 20261025 ROM plus display, Light and GPS boot fixes.
Only lights.mt6735.so changes; earlier Light service/dependency fixes remain.
"""
import argparse
from pathlib import Path
import sys
import zipfile

import create_display_fix as base
import create_gnss_fix as gnss

OLD = "d83f7a9ed24076fc5d953ec964f5b2e698c342a4ac8acd18980feae60fe36be0"
NEW = "9d2a8737e6ee146cdf7e74b0233fc38efd614d0a9e6d79832688a2cce2b81b75"
MOUNT = "/tmp/j2prime-backlight-system"
VERIFY = "/tmp/j2prime-backlight-verify.sh"
DRIVER = "lib/hw/lights.mt6735.so"
CHECKS = {name: digest for name, digest in gnss.CHECKS.items() if name != DRIVER}
CHECKS["lib/hw/gps.default.so"] = gnss.NEW


def check(path, *hashes):
    args = ", ".join('"' + value + '"' for value in ("/sbin/sh", VERIFY, path, *hashes))
    return f'assert(run_program({args}) == "0");'


def package(path, binary, payload):
    vendor = MOUNT + "/system/vendor/"
    target = vendor + DRIVER
    lines = [
        'ui_print("J2 Prime BACKLIGHT grayscale brightness update");',
        f'assert(package_extract_file("verify-backlight.sh", "{VERIFY}"));',
        'assert(!is_mounted("/system") && !is_mounted("/system_root"));',
        f'assert(mount("ext4", "EMMC", "{base.BLOCK}", "{MOUNT}") != "");',
        f'assert(file_getprop("{MOUNT}/system/build.prop", "ro.lineage.version") == "{base.VERSION}");',
        f'assert(file_getprop("{MOUNT}/system/build.prop", "ro.build.version.sdk") == "30");',
    ]
    lines += [check(vendor + relative, digest) for relative, digest in CHECKS.items()]
    lines += [
        check(target, OLD, NEW),
        f'assert(package_extract_file("lights.mt6735.so", "{target}"));',
        f'set_metadata("{target}", "uid", 0, "gid", 0, "mode", 0644, "selabel", "u:object_r:vendor_file:s0");',
        check(target, base.sha(payload)),
        f'assert(unmount("{MOUNT}") != "");',
        'ui_print("Backlight driver verified; existing boot fixes preserved.");',
    ]
    entries = {
        base.PREFIX + "update-binary": binary,
        base.PREFIX + "updater-script": ("\n".join(lines) + "\n").encode(),
        "verify-backlight.sh": base.HASH_VERIFIER.replace(b"GUI shim", b"backlight HAL"),
        "lights.mt6735.so": payload,
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 26, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith("update-binary") else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("generated ZIP CRC failure")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom_zip", type=Path)
    parser.add_argument("patched_hal", type=Path)
    parser.add_argument("original_hal", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if base.sha(args.rom_zip.read_bytes()) != base.ROM_SHA256:
        parser.error("input ROM differs from the diagnosed build")
    old, new = args.original_hal.read_bytes(), args.patched_hal.read_bytes()
    if base.sha(old) != OLD or base.sha(new) != NEW:
        parser.error("unexpected pre/post brightness HAL hashes")
    if len(old) != len(new) or old[:5737] != new[:5737] or old[5738:] != new[5738:]:
        parser.error("brightness patch extends outside its single instruction byte")
    with zipfile.ZipFile(args.rom_zip) as archive:
        binary = archive.read(base.PREFIX + "update-binary")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    sums = []
    for suffix, payload in (("fix", new), ("undo", old)):
        path = args.out_dir / f"grandppltedx-20261026-backlight-{suffix}.zip"
        package(path, binary, payload)
        sums.append(f"{base.sha(path.read_bytes())}  {path.name}\n")
        print(path, path.stat().st_size, "bytes")
    (args.out_dir / "BACKLIGHT-FIX-SHA256SUMS").write_text("".join(sums), encoding="ascii")
