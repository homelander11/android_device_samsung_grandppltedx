#!/usr/bin/env python3
"""Remove only the charging init/shell diagnostic after the tested fixes.

The old diagnostic undo expects the pre-SAR init hash. This cleanup instead
pins the installed modern UI, corrected SAR init and charging wake init.
The independent, previously tested early-boot undo restores original boot.
"""
import argparse
import json
from pathlib import Path
import sys
import zipfile

import create_charger_debug as debug
import create_charger_sar_fix as sar
import create_charger_wake_fix as wake

ui = debug.ui


def package(path, updater, expected):
    checks = dict(ui.CHECKS)
    checks[sar.TARGET] = json.loads(sar.MANIFEST.read_text())["patched_sha256"]
    checks[wake.TARGET] = json.loads(wake.MANIFEST.read_text())["payload_canonical_lf_sha256"]
    lines = [
        'ui_print("J2 Prime charging init/shell diagnostic cleanup");',
        f'assert(package_extract_file("verify-charger.sh", "{ui.VERIFY}"));',
        ui.check("--battery"),
        'assert(!is_mounted("/system") && !is_mounted("/system_root"));',
        f'assert(mount("ext4", "EMMC", "{ui.base.BLOCK}", "{ui.MOUNT}") != "");',
        f'assert(file_getprop("{ui.MOUNT}/system/build.prop", "ro.lineage.version") == "{ui.base.VERSION}");',
        f'assert(file_getprop("{ui.MOUNT}/system/build.prop", "ro.build.version.sdk") == "30");',
    ]
    for target, digest in sorted(checks.items()):
        lines.append(ui.check(ui.MOUNT + "/" + target, digest))
    for name, (target, _) in ui.TARGETS.items():
        lines.append(ui.check(ui.MOUNT + "/" + target, ui.EVIDENCE["candidate_files"][name]["sha256"]))
    for name, (target, _) in debug.FILES.items():
        lines.append(ui.check(ui.MOUNT + "/" + target, "ABSENT", expected[name]))
    # Validate every prerequisite and both diagnostic targets before deletion.
    for target, _ in debug.FILES.values():
        dest = ui.MOUNT + "/" + target
        lines += [f'delete("{dest}");', ui.check(dest, "ABSENT")]
    lines += [
        f'assert(unmount("{ui.MOUNT}") != "");',
        'ui_print("Only diagnostic init/script removed; charging fixes retained.");',
    ]
    entries = {
        ui.base.PREFIX + "update-binary": updater,
        ui.base.PREFIX + "updater-script": ("\n".join(lines) + "\n").encode(),
        "verify-charger.sh": ui.VERIFIER,
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
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if sar.file_hash(args.rom_zip) != ui.base.ROM_SHA256:
            raise ValueError("input ROM differs from diagnosed build")
        expected = json.loads((debug.SOURCE / "manifest.json").read_text())["canonical_lf_payload_sha256"]
        with zipfile.ZipFile(args.rom_zip) as archive:
            updater = archive.read(ui.base.PREFIX + "update-binary")
        args.out_dir.mkdir(parents=True, exist_ok=True)
        path = args.out_dir / "grandppltedx-20261028-charging-debug-cleanup.zip"
        package(path, updater, expected)
        digest = sar.file_hash(path)
        (args.out_dir / "CHARGING-CLEANUP-SHA256SUMS").write_bytes(f"{digest}  {path.name}\n".encode("ascii"))
        print(path.name, path.stat().st_size, "bytes", digest)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print("FAIL:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
