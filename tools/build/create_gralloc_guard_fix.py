#!/usr/bin/env python3
"""Package the pinned gralloc crash guard and exact undo for device testing.

Only the failed-module cleanup instruction changes. Normal display-service
testing remains required; this does not fix the preceding import failure or
establish third-party camera compatibility.
"""
import argparse
from pathlib import Path
import sys
import zipfile

import create_camera_colour_fix as colour
import create_display_fix as base
import fix_gralloc_unregister as guard

MOUNT = "/tmp/j2prime-gralloc-system"
VERIFY = "/tmp/j2prime-gralloc-verify.sh"
LIBRARY = "lib/hw/gralloc.mt6735.so"


def checks():
    result = colour.checks()
    result["lib/libcamcx.so"] = colour.MANIFEST["patched_sha256"]
    result.pop(LIBRARY, None)
    return result


def check(path, *hashes):
    args = ", ".join('"' + value + '"' for value in ("/sbin/sh", VERIFY, path, *hashes))
    return f'assert(run_program({args}) == "0");'


def package(path, updater, payload):
    vendor = MOUNT + "/system/vendor/"
    target = vendor + LIBRARY
    lines = [
        'ui_print("J2 Prime graphics cleanup crash guard / undo");',
        f'assert(package_extract_file("verify-gralloc.sh", "{VERIFY}"));',
        'assert(!is_mounted("/system") && !is_mounted("/system_root"));',
        f'assert(mount("ext4", "EMMC", "{base.BLOCK}", "{MOUNT}") != "");',
        f'assert(file_getprop("{MOUNT}/system/build.prop", "ro.lineage.version") == "{base.VERSION}");',
        f'assert(file_getprop("{MOUNT}/system/build.prop", "ro.build.version.sdk") == "30");',
    ]
    lines += [check(vendor + name, digest) for name, digest in sorted(checks().items())]
    lines += [
        check(target, guard.MANIFEST["original_sha256"], guard.MANIFEST["patched_sha256"]),
        f'assert(package_extract_file("gralloc.mt6735.so", "{target}"));',
        f'set_metadata("{target}", "uid", 0, "gid", 0, "mode", 0644, "selabel", "u:object_r:vendor_file:s0");',
        check(target, base.sha(payload)),
        f'assert(unmount("{MOUNT}") != "");',
        'ui_print("Graphics driver verified. Reboot System without wiping.");',
    ]
    entries = {
        base.PREFIX + "update-binary": updater,
        base.PREFIX + "updater-script": ("\n".join(lines) + "\n").encode(),
        "verify-gralloc.sh": colour.camera.VERIFIER,
        "gralloc.mt6735.so": payload,
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
    parser.add_argument("original_gralloc", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if base.sha(args.rom_zip.read_bytes()) != base.ROM_SHA256:
            raise ValueError("input ROM differs from the diagnosed build")
        old = args.original_gralloc.read_bytes()
        if base.sha(old) != guard.MANIFEST["original_sha256"]:
            raise ValueError("unexpected original graphics driver")
        new = guard.corrected(old)
        with zipfile.ZipFile(args.rom_zip) as archive:
            updater = archive.read(base.PREFIX + "update-binary")
        args.out_dir.mkdir(parents=True, exist_ok=True)
        sums = []
        for suffix, payload in (("fix", new), ("undo", old)):
            path = args.out_dir / f"grandppltedx-20261027-gralloc-guard-{suffix}.zip"
            package(path, updater, payload)
            sums.append(f"{base.sha(path.read_bytes())}  {path.name}\n")
            print(path, path.stat().st_size, "bytes")
        (args.out_dir / "GRALLOC-GUARD-SHA256SUMS").write_text("".join(sums), encoding="ascii")
    except (OSError, ValueError) as error:
        print("FAIL:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
