#!/usr/bin/env python3
"""Package the inactive Android 11 charging-UI candidate and exact undo.

Requires the pinned ROM, original animation and candidate hashes. Writes only
one vendor init override and two product resources. No boot/recovery changes.
The recovery installer requires at least 15% real battery capacity.
"""
import argparse
import json
from pathlib import Path
import sys
import zipfile

import create_display_fix as base

TOOLS = Path(__file__).resolve().parents[1]
EVIDENCE = json.loads((TOOLS / "charger/investigation.json").read_text())
CANDIDATE = TOOLS / "charger/candidate"
MOUNT = "/tmp/j2prime-charger-system"
VERIFY = "/tmp/j2prime-charger-verify.sh"
ANIMATION = "system/product/etc/res/values/charger/animation.txt"
TARGETS = {
    "zz-grandppltedx-charger.rc": (
        "system/vendor/etc/init/zz-grandppltedx-charger.rc", "vendor_configs_file"),
    "animation.txt": (ANIMATION, "system_file"),
    "font_charger_18x32.png": (
        "system/product/etc/res/images/charger/font_charger_18x32.png", "system_file"),
}
CHECKS = {
    "system/bin/charger": EVIDENCE["evidence"]["charger"]["sha256"],
    "system/vendor/bin/lpm": EVIDENCE["evidence"]["vendor_lpm"]["sha256"],
    "system/etc/init/hw/init.rc": "1496caa9b6a176a01f00ead4386887fbaee4efb4e2fb59328d3eb41284770c4c",
    "system/vendor/etc/init/hw/init.mt6735.rc": "2bca24ad483f10b8a924fbc1a3d4ee69f417355a7b22413d8f45cab6badbf931",
    "system/product/etc/res/images/charger/battery_scale.png": EVIDENCE["evidence"]["original_battery_scale"]["sha256"],
    "system/product/etc/res/images/charger/battery_fail.png": "69195855819bbaecf8ae3732fc98b5ffb71a77de8ecb4094623dcbad353cd703",
}
VERIFIER = b'''#!/sbin/sh
set -eu
if [ "$1" = --battery ]; then
    capacity=$(cat /sys/class/power_supply/battery/capacity) || exit 1
    case "$capacity" in ''|*[!0-9]*) exit 1;; esac
    if [ "$capacity" -lt 15 ]; then
        echo "Charge to at least 15% before installing this charging-UI update." >&2
        exit 1
    fi
    exit 0
fi
file=$1
shift
# Reject symlinks in every path component before extraction or deletion.
parent=$file
while [ -n "$parent" ] && [ "$parent" != / ]; do
    test ! -L "$parent" || exit 1
    parent=${parent%/*}
done
actual=ABSENT
if [ -e "$file" ]; then
    test -f "$file" || exit 1
    actual=$(sha256sum "$file") || exit 1
    actual=${actual%% *}
fi
for expected do
    if [ "$actual" = "$expected" ]; then exit 0; fi
done
echo "Unexpected charging-UI target/dependency: $actual" >&2
exit 1
'''


def check(path, *hashes):
    args = ("/sbin/sh", VERIFY, path, *hashes)
    return 'assert(run_program(' + ', '.join('"' + x + '"' for x in args) + ') == "0");'


def package(path, updater, payloads, original, undo=False):
    lines = [
        'ui_print("J2 Prime experimental Android 11 charging UI / undo");',
        f'assert(package_extract_file("verify-charger.sh", "{VERIFY}"));',
        check("--battery"),
        'assert(!is_mounted("/system") && !is_mounted("/system_root"));',
        f'assert(mount("ext4", "EMMC", "{base.BLOCK}", "{MOUNT}") != "");',
        f'assert(file_getprop("{MOUNT}/system/build.prop", "ro.lineage.version") == "{base.VERSION}");',
        f'assert(file_getprop("{MOUNT}/system/build.prop", "ro.build.version.sdk") == "30");',
    ]
    lines += [check(MOUNT + "/" + name, digest) for name, digest in sorted(CHECKS.items())]
    for name, (target, _) in TARGETS.items():
        old = base.sha(original) if name == "animation.txt" else "ABSENT"
        lines += [check(MOUNT + "/" + target, old, base.sha(payloads[name]))]
    # All dependencies and targets must pass before any system-file mutation.
    for name, (target, label) in TARGETS.items():
        dest = MOUNT + "/" + target
        if undo and name != "animation.txt":
            lines += [f'delete("{dest}");', check(dest, "ABSENT")]
        else:
            source = "original-animation.txt" if undo else name
            digest = base.sha(original) if undo else base.sha(payloads[name])
            lines += [
                f'assert(package_extract_file("{source}", "{dest}"));',
                f'set_metadata("{dest}", "uid", 0, "gid", 0, "mode", 0644, "selabel", "u:object_r:{label}:s0");',
                check(dest, digest),
            ]
    lines += [f'assert(unmount("{MOUNT}") != "");',
              'ui_print("Charging UI files verified. Reboot System without wiping.");']
    entries = {
        base.PREFIX + "update-binary": updater,
        base.PREFIX + "updater-script": ("\n".join(lines) + "\n").encode(),
        "verify-charger.sh": VERIFIER,
        "LICENSES/OFL.txt": (CANDIDATE / "OFL.txt").read_bytes(),
        "LICENSES/FONT-README": (CANDIDATE / "FONT-README").read_bytes(),
    }
    entries.update({"original-animation.txt": original} if undo else payloads)
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
    parser.add_argument("original_animation", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if base.sha(args.rom_zip.read_bytes()) != base.ROM_SHA256:
            raise ValueError("input ROM differs from the diagnosed build")
        original = args.original_animation.read_bytes()
        if base.sha(original) != EVIDENCE["evidence"]["original_animation"]["sha256"]:
            raise ValueError("unexpected original animation")
        payloads = {name: (CANDIDATE / name).read_bytes() for name in TARGETS}
        for name, data in payloads.items():
            if base.sha(data) != EVIDENCE["candidate_files"][name]["sha256"]:
                raise ValueError("unexpected candidate hash: " + name)
        for name in ("OFL.txt", "FONT-README"):
            if base.sha((CANDIDATE / name).read_bytes()) != EVIDENCE["candidate_files"][name]["sha256"]:
                raise ValueError("unexpected font license/provenance hash: " + name)
        with zipfile.ZipFile(args.rom_zip) as archive:
            updater = archive.read(base.PREFIX + "update-binary")
        args.out_dir.mkdir(parents=True, exist_ok=True)
        sums = []
        for suffix in ("fix", "undo"):
            path = args.out_dir / f"grandppltedx-20261027-charging-ui-{suffix}.zip"
            package(path, updater, payloads, original, undo=suffix == "undo")
            sums.append(f"{base.sha(path.read_bytes())}  {path.name}\n")
            print(path.name, path.stat().st_size, "bytes")
        (args.out_dir / "CHARGING-UI-SHA256SUMS").write_text("".join(sums), encoding="ascii")
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print("FAIL:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
