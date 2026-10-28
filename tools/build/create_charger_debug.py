#!/usr/bin/env python3
"""Add/remove charging-only cache/USB diagnostics for the installed UI trial.

No boot/recovery/library changes. The original UI trial must already be present.
The script is inactive on normal boots and is not included in full ROM builds.
"""
import argparse
import json
from pathlib import Path
import sys
import zipfile

import create_charger_fix as ui

SOURCE = ui.TOOLS / "charger/diagnostic"
FILES = {
    "init.rc": ("system/vendor/etc/init/zzzz-grandppltedx-charger-debug.rc", "vendor_configs_file"),
    "debug.sh": ("system/vendor/bin/j2prime-charger-debug.sh", "vendor_file"),
}


def package(path, updater, payloads, undo=False):
    lines = [
        'ui_print("J2 Prime charging-only diagnostics / undo");',
        f'assert(package_extract_file("verify-charger.sh", "{ui.VERIFY}"));',
        ui.check("--battery"),
        'assert(!is_mounted("/system") && !is_mounted("/system_root"));',
        f'assert(mount("ext4", "EMMC", "{ui.base.BLOCK}", "{ui.MOUNT}") != "");',
        f'assert(file_getprop("{ui.MOUNT}/system/build.prop", "ro.lineage.version") == "{ui.base.VERSION}");',
        f'assert(file_getprop("{ui.MOUNT}/system/build.prop", "ro.build.version.sdk") == "30");',
    ]
    for target, digest in sorted(ui.CHECKS.items()):
        lines.append(ui.check(ui.MOUNT + "/" + target, digest))
    for name, (target, _) in ui.TARGETS.items():
        lines.append(ui.check(ui.MOUNT + "/" + target, ui.EVIDENCE["candidate_files"][name]["sha256"]))
    for name, (target, _) in FILES.items():
        lines.append(ui.check(ui.MOUNT + "/" + target, "ABSENT", ui.base.sha(payloads[name])))
    for name, (target, label) in FILES.items():
        dest = ui.MOUNT + "/" + target
        if undo:
            lines += [f'delete("{dest}");', ui.check(dest, "ABSENT")]
        else:
            lines += [
                f'assert(package_extract_file("{name}", "{dest}"));',
                f'set_metadata("{dest}", "uid", 0, "gid", 0, "mode", 0644, "selabel", "u:object_r:{label}:s0");',
                ui.check(dest, ui.base.sha(payloads[name])),
            ]
    lines += [f'assert(unmount("{ui.MOUNT}") != "");',
              'ui_print("Diagnostic files verified. Reboot System without wiping.");']
    entries = {
        ui.base.PREFIX + "update-binary": updater,
        ui.base.PREFIX + "updater-script": ("\n".join(lines) + "\n").encode(),
        "verify-charger.sh": ui.VERIFIER,
    }
    if not undo:
        entries.update(payloads)
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
        if ui.base.sha(args.rom_zip.read_bytes()) != ui.base.ROM_SHA256:
            raise ValueError("input ROM differs from diagnosed build")
        payloads = {name: (SOURCE / name).read_bytes().replace(b"\r\n", b"\n") for name in FILES}
        expected = json.loads((SOURCE / "manifest.json").read_text())["canonical_lf_payload_sha256"]
        for name, data in payloads.items():
            if ui.base.sha(data) != expected[name]:
                raise ValueError("unexpected diagnostic payload hash: " + name)
        with zipfile.ZipFile(args.rom_zip) as archive:
            updater = archive.read(ui.base.PREFIX + "update-binary")
        args.out_dir.mkdir(parents=True, exist_ok=True)
        sums = []
        for suffix in ("debug", "debug-undo"):
            path = args.out_dir / f"grandppltedx-20261028-charging-{suffix}.zip"
            package(path, updater, payloads, undo=suffix == "debug-undo")
            sums.append(f"{ui.base.sha(path.read_bytes())}  {path.name}\n")
            print(path.name, path.stat().st_size, "bytes")
        (args.out_dir / "CHARGING-DEBUG-SHA256SUMS").write_text("".join(sums), encoding="ascii")
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print("FAIL:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
