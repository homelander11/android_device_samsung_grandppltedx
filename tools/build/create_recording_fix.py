#!/usr/bin/env python3
"""Package the four recording-selector bytes and an exact undo for the tested ROM."""
import argparse
from pathlib import Path
import sys
import zipfile

import create_backlight_fix as backlight
import create_display_fix as base

OLD = "d4f20563caa3d8a8c1eaab2ea0bf853baf1056ab8f03306793c0210867dc3690"
NEW = "f3fb7b40768fe76339c02b198474a2f6dffb262350fbbba20995747baec5fe8e"
MOUNT = "/tmp/j2prime-recording-system"
VERIFY = "/tmp/j2prime-recording-verify.sh"
LIBRARY = "lib/libaudiocustparam_vendor.so"
CHECKS = dict(backlight.CHECKS)
CHECKS.update({
    "lib/libcustom_nvram.so": "6b5844dd0a9fed78c16da81d83c9217f62797c711a01c6506a28dcf749308615",
    "lib/hw/audio.primary.mt6737t.so": "c4f37051f521c4fffd7eb13f9016cda9df528fdabdba42386e87f6b5e32419e6",
})


def check(path, *hashes):
    args = ", ".join('"' + value + '"' for value in ("/sbin/sh", VERIFY, path, *hashes))
    return f'assert(run_program({args}) == "0");'


def package(path, binary, payload):
    vendor = MOUNT + "/system/vendor/"
    target = vendor + LIBRARY
    lines = [
        'ui_print("J2 Prime HD recording parameter selectors");',
        f'assert(package_extract_file("verify-recording.sh", "{VERIFY}"));',
        'assert(!is_mounted("/system") && !is_mounted("/system_root"));',
        f'assert(mount("ext4", "EMMC", "{base.BLOCK}", "{MOUNT}") != "");',
        f'assert(file_getprop("{MOUNT}/system/build.prop", "ro.lineage.version") == "{base.VERSION}");',
        f'assert(file_getprop("{MOUNT}/system/build.prop", "ro.build.version.sdk") == "30");',
    ]
    lines += [check(vendor + relative, digest) for relative, digest in CHECKS.items()]
    lines += [
        check(vendor + backlight.DRIVER, backlight.OLD, backlight.NEW),
        check(target, OLD, NEW),
        f'assert(package_extract_file("libaudiocustparam_vendor.so", "{target}"));',
        f'set_metadata("{target}", "uid", 0, "gid", 0, "mode", 0644, "selabel", "u:object_r:vendor_file:s0");',
        check(target, base.sha(payload)),
        f'assert(unmount("{MOUNT}") != "");',
        'ui_print("Recording library verified; device calibration preserved.");',
    ]
    entries = {
        base.PREFIX + "update-binary": binary,
        base.PREFIX + "updater-script": ("\n".join(lines) + "\n").encode(),
        "verify-recording.sh": base.HASH_VERIFIER.replace(b"GUI shim", b"recording library"),
        "libaudiocustparam_vendor.so": payload,
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
    parser.add_argument("patched_library", type=Path)
    parser.add_argument("original_library", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if base.sha(args.rom_zip.read_bytes()) != base.ROM_SHA256:
        parser.error("input ROM differs from the diagnosed build")
    old, new = args.original_library.read_bytes(), args.patched_library.read_bytes()
    if base.sha(old) != OLD or base.sha(new) != NEW:
        parser.error("unexpected pre/post recording library hashes")
    differences = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
    if len(old) != len(new) or differences != [13440, 13948, 14408, 14916]:
        parser.error("recording patch extends outside its four selector bytes")
    with zipfile.ZipFile(args.rom_zip) as archive:
        binary = archive.read(base.PREFIX + "update-binary")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    sums = []
    for suffix, payload in (("fix", new), ("undo", old)):
        path = args.out_dir / f"grandppltedx-20261026-recording-{suffix}.zip"
        package(path, binary, payload)
        sums.append(f"{base.sha(path.read_bytes())}  {path.name}\n")
        print(path, path.stat().st_size, "bytes")
    (args.out_dir / "RECORDING-FIX-SHA256SUMS").write_text("".join(sums), encoding="ascii")
