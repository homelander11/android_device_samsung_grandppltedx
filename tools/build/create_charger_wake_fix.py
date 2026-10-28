#!/usr/bin/env python3
"""Package one charger-only brightness initialization and its exact removal.

Requires the pinned ROM with the installed modern charging UI and SAR mount
correction. No binary, boot, recovery, calibration or charge-control changes.
"""
import argparse
import json
from pathlib import Path
import sys
import zipfile

import create_charger_sar_fix as sar

ui = sar.ui
MANIFEST = ui.TOOLS / "charger/backlight.json"
SOURCE = ui.TOOLS.parent / "configs/init/zz-grandppltedx-charger-backlight.rc"
TARGET = "system/vendor/etc/init/zz-grandppltedx-charger-backlight.rc"


def package(path, updater, payload, undo=False):
    dest = ui.MOUNT + "/" + TARGET
    checks = dict(ui.CHECKS)
    checks[sar.TARGET] = json.loads(sar.MANIFEST.read_text())["patched_sha256"]
    lines = [
        'ui_print("J2 Prime charging-screen wake initialization / undo");',
        f'assert(package_extract_file("verify-charger.sh", "{ui.VERIFY}"));',
        ui.check("--battery"),
        'assert(!is_mounted("/system") && !is_mounted("/system_root"));',
        f'assert(mount("ext4", "EMMC", "{ui.base.BLOCK}", "{ui.MOUNT}") != "");',
        f'assert(file_getprop("{ui.MOUNT}/system/build.prop", "ro.lineage.version") == "{ui.base.VERSION}");',
        f'assert(file_getprop("{ui.MOUNT}/system/build.prop", "ro.build.version.sdk") == "30");',
    ]
    lines += [ui.check(ui.MOUNT + "/" + name, digest) for name, digest in sorted(checks.items())]
    for name, (target, _) in ui.TARGETS.items():
        lines.append(ui.check(ui.MOUNT + "/" + target, ui.EVIDENCE["candidate_files"][name]["sha256"]))
    lines.append(ui.check(dest, "ABSENT", ui.base.sha(payload)))
    # All dependency/target checks precede the sole mutation.
    if undo:
        lines += [f'delete("{dest}");', ui.check(dest, "ABSENT")]
    else:
        lines += [
            f'assert(package_extract_file("charger-backlight.rc", "{dest}"));',
            f'set_metadata("{dest}", "uid", 0, "gid", 0, "mode", 0644, "selabel", "u:object_r:vendor_configs_file:s0");',
            ui.check(dest, ui.base.sha(payload)),
        ]
    lines += [
        f'assert(unmount("{ui.MOUNT}") != "");',
        'ui_print("Charging wake init verified. Reboot System without wiping.");',
    ]
    entries = {
        ui.base.PREFIX + "update-binary": updater,
        ui.base.PREFIX + "updater-script": ("\n".join(lines) + "\n").encode(),
        "verify-charger.sh": ui.VERIFIER,
    }
    if not undo:
        entries["charger-backlight.rc"] = payload
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
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        expected = json.loads(MANIFEST.read_text())
        if sar.file_hash(args.rom_zip) != ui.base.ROM_SHA256:
            raise ValueError("input ROM differs from diagnosed build")
        payload = SOURCE.read_bytes().replace(b"\r\n", b"\n")
        if ui.base.sha(payload) != expected["payload_canonical_lf_sha256"]:
            raise ValueError("unexpected charging backlight payload")
        with zipfile.ZipFile(args.rom_zip) as archive:
            updater = archive.read(ui.base.PREFIX + "update-binary")
        args.out_dir.mkdir(parents=True, exist_ok=True)
        sums = []
        for suffix in ("fix", "undo"):
            path = args.out_dir / f"grandppltedx-20261028-charging-wake-{suffix}.zip"
            package(path, updater, payload, undo=suffix == "undo")
            sums.append(f"{ui.base.sha(path.read_bytes())}  {path.name}\n")
            print(path.name, path.stat().st_size, "bytes")
        (args.out_dir / "CHARGING-WAKE-SHA256SUMS").write_bytes("".join(sums).encode("ascii"))
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print("FAIL:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
