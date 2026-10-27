#!/usr/bin/env python3
"""Package the pinned Samsung sensor-service input-group override and exact undo.

Adds/removes one init file. The original service, HAL and all hardware binaries
remain unchanged. Requires a reboot; never restart the running Sensors 1.0 HAL.
"""
import argparse
import json
from pathlib import Path
import sys
import zipfile

import create_display_fix as base

TOOLS = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((TOOLS / "sensors/input-group.json").read_text())
PAYLOAD = TOOLS.parent / "configs/init/zz-grandppltedx-sensors.rc"
TARGET = "etc/init/zz-grandppltedx-sensors.rc"
MOUNT = "/tmp/j2prime-sensors-system"
VERIFY = "/tmp/j2prime-sensors-verify.sh"
VERIFIER = b"""#!/sbin/sh
set -eu
file=$1
shift
test ! -L "$file" || exit 1
actual=ABSENT
if [ -e "$file" ]; then
    test -f "$file" || exit 1
    actual=$(sha256sum "$file") || exit 1
    actual=${actual%% *}
fi
for expected do
    if [ "$actual" = "$expected" ]; then exit 0; fi
done
echo "Unexpected sensor configuration/dependency: $actual" >&2
exit 1
"""


def check(path, *digests):
    args = ", ".join('"' + value + '"' for value in ("/sbin/sh", VERIFY, path, *digests))
    return f'assert(run_program({args}) == "0");'


def validate_payload(payload):
    if base.sha(payload) != MANIFEST["patched_sha256"]:
        raise ValueError("unexpected sensor override hash")
    lines = [line.strip() for line in payload.decode().splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    expected = [
        "service vendor.sensors-hal-1-0 /vendor/bin/hw/android.hardware.sensors@1.0-service",
        "override",
        "interface android.hardware.sensors@1.0::ISensors default",
        "class hal", "user system",
        "group system wakelock uhid context_hub input",
        "capabilities BLOCK_SUSPEND", "rlimit rtprio 10 10",
    ]
    if lines != expected:
        raise ValueError("override must preserve the standard service and add only input")


def package(path, updater, payload, undo=False):
    vendor = MOUNT + "/system/vendor/"
    target = vendor + TARGET
    lines = [
        'ui_print("J2 Prime sensor-service input-group fix / undo");',
        f'assert(package_extract_file("verify-sensors.sh", "{VERIFY}"));',
        'assert(!is_mounted("/system") && !is_mounted("/system_root"));',
        f'assert(mount("ext4", "EMMC", "{base.BLOCK}", "{MOUNT}") != "");',
        f'assert(file_getprop("{MOUNT}/system/build.prop", "ro.lineage.version") == "{base.VERSION}");',
        f'assert(file_getprop("{MOUNT}/system/build.prop", "ro.build.version.sdk") == "30");',
    ]
    lines += [check(vendor + name, digest) for name, digest in sorted(MANIFEST["checks"].items())]
    lines += [check(target, "ABSENT", MANIFEST["patched_sha256"])]
    if undo:
        lines += [f'delete("{target}");', check(target, "ABSENT")]
    else:
        lines += [
            f'assert(package_extract_file("zz-grandppltedx-sensors.rc", "{target}"));',
            f'set_metadata("{target}", "uid", 0, "gid", 0, "mode", 0644, "selabel", "u:object_r:vendor_configs_file:s0");',
            check(target, MANIFEST["patched_sha256"]),
        ]
    lines += [f'assert(unmount("{MOUNT}") != "");',
              'ui_print("Sensor init configuration verified. Reboot System without wiping.");']
    entries = {
        base.PREFIX + "update-binary": updater,
        base.PREFIX + "updater-script": ("\n".join(lines) + "\n").encode(),
        "verify-sensors.sh": VERIFIER,
    }
    if not undo:
        entries["zz-grandppltedx-sensors.rc"] = payload
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
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if base.sha(args.rom_zip.read_bytes()) != base.ROM_SHA256:
            raise ValueError("input ROM differs from the diagnosed build")
        payload = PAYLOAD.read_bytes().replace(b"\r\n", b"\n")
        validate_payload(payload)
        with zipfile.ZipFile(args.rom_zip) as archive:
            updater = archive.read(base.PREFIX + "update-binary")
        args.out_dir.mkdir(parents=True, exist_ok=True)
        sums = []
        for suffix in ("fix", "undo"):
            path = args.out_dir / f"grandppltedx-20261027-sensor-input-{suffix}.zip"
            package(path, updater, payload, undo=suffix == "undo")
            sums.append(f"{base.sha(path.read_bytes())}  {path.name}\n")
            print(path, path.stat().st_size, "bytes")
        with (args.out_dir / "SENSOR-INPUT-SHA256SUMS").open("w", encoding="ascii", newline="\n") as stream:
            stream.write("".join(sums))
    except (OSError, ValueError) as error:
        print("FAIL:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
