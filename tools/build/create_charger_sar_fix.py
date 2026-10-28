#!/usr/bin/env python3
"""Remove only the obsolete charger-mode system remount; package exact undo.

Targets the pinned ROM with the installed Android 11 charging-UI trial.
Preserves the currently installed runtime init file except for this block.
Does not write boot, recovery, calibration, libraries or other init files.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import create_charger_fix as ui

MANIFEST = ui.TOOLS / "charger/sar-mount.json"
TARGET = "system/vendor/etc/init/hw/init.mt6735.rc"
BLOCK = b'''on property:ro.bootmode=charger
    mount ext4 /dev/block/platform/mtk-msdc.0/11230000.msdc0/by-name/system /system support_scfs wait ro

'''
COMMENT = b'''# First-stage init already mounted system-as-root. Remounting it on /system
# creates /system/bin -> /system/bin symlink loops in charging mode.

'''


def file_hash(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            result.update(chunk)
    return result.hexdigest()


def package(path, updater, payload, accepted):
    dest = ui.MOUNT + "/" + TARGET
    lines = [
        'ui_print("J2 Prime charging system-as-root mount correction / undo");',
        f'assert(package_extract_file("verify-charger.sh", "{ui.VERIFY}"));',
        ui.check("--battery"),
        'assert(!is_mounted("/system") && !is_mounted("/system_root"));',
        f'assert(mount("ext4", "EMMC", "{ui.base.BLOCK}", "{ui.MOUNT}") != "");',
        f'assert(file_getprop("{ui.MOUNT}/system/build.prop", "ro.lineage.version") == "{ui.base.VERSION}");',
        f'assert(file_getprop("{ui.MOUNT}/system/build.prop", "ro.build.version.sdk") == "30");',
    ]
    for target, digest in sorted(ui.CHECKS.items()):
        if target != TARGET:
            lines.append(ui.check(ui.MOUNT + "/" + target, digest))
    for name, (target, _) in ui.TARGETS.items():
        lines.append(ui.check(ui.MOUNT + "/" + target, ui.EVIDENCE["candidate_files"][name]["sha256"]))
    lines += [
        ui.check(dest, *accepted),
        f'assert(package_extract_file("init.mt6735.rc", "{dest}"));',
        f'set_metadata("{dest}", "uid", 0, "gid", 0, "mode", 0644, "selabel", "u:object_r:vendor_configs_file:s0");',
        ui.check(dest, ui.base.sha(payload)),
        f'assert(unmount("{ui.MOUNT}") != "");',
        'ui_print("Charging init file verified. Reboot System without wiping.");',
    ]
    entries = {
        ui.base.PREFIX + "update-binary": updater,
        ui.base.PREFIX + "updater-script": ("\n".join(lines) + "\n").encode(),
        "verify-charger.sh": ui.VERIFIER,
        "init.mt6735.rc": payload,
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 28, 0, 0, 0))
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
    parser.add_argument("original_init_rc", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        expected = json.loads(MANIFEST.read_text())
        if file_hash(args.rom_zip) != ui.base.ROM_SHA256:
            raise ValueError("input ROM differs from diagnosed build")
        old = args.original_init_rc.read_bytes()
        if ui.base.sha(old) != expected["original_sha256"] or old.count(BLOCK) != 1:
            raise ValueError("unexpected original charger init block")
        new = old.replace(BLOCK, COMMENT)
        if ui.base.sha(new) != expected["patched_sha256"]:
            raise ValueError("unexpected patched init hash")
        source = (ui.TOOLS.parent / "rootdir/init.mt6735.rc").read_bytes().replace(b"\r\n", b"\n")
        if BLOCK in source or COMMENT not in source:
            raise ValueError("source must contain the same system-as-root correction")
        with zipfile.ZipFile(args.rom_zip) as archive:
            updater = archive.read(ui.base.PREFIX + "update-binary")
        args.out_dir.mkdir(parents=True, exist_ok=True)
        accepted = (ui.base.sha(old), ui.base.sha(new))
        sums = []
        for suffix, payload in (("fix", new), ("undo", old)):
            path = args.out_dir / f"grandppltedx-20261028-charging-sar-{suffix}.zip"
            package(path, updater, payload, accepted)
            sums.append(f"{ui.base.sha(path.read_bytes())}  {path.name}\n")
            print(path.name, path.stat().st_size, "bytes")
        (args.out_dir / "CHARGING-SAR-SHA256SUMS").write_text("".join(sums), encoding="ascii")
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print("FAIL:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
