#!/usr/bin/env python3
"""Build guarded fix/undo TWRP ZIPs adding the missing Android 11 Light HAL.

Requires the exact diagnosed ROM and matching targeted `lights` build output.
Adds the service/wrapper/two init files and corrects the legacy driver's unused
dependency. No device access, full ROM build, boot image or userdata operation.
"""
import argparse
from pathlib import Path
import sys
import zipfile

import create_display_fix as base
from verify_lights import validate

MOUNT = "/tmp/j2prime-lights-system"
VERIFY = "/tmp/j2prime-lights-verify.sh"
GUI_SHA256 = "c52b763c485f0613b5d95047d0d993a04f23f6429f37143172d46de2f20cb362"
DRIVER_ORIGINAL = "5150222ba0218d4dcc51dc81f616e7f9dbe5de15122518c8a49b283b62b45237"
DRIVER_PATCHED = "d83f7a9ed24076fc5d953ec964f5b2e698c342a4ac8acd18980feae60fe36be0"
DRIVER = "lib/hw/lights.mt6735.so"
FILES = (
    ("bin/hw/android.hardware.light@2.0-service", "0755", "hal_light_default_exec"),
    ("lib/hw/android.hardware.light@2.0-impl.so", "0644", "vendor_file"),
    ("etc/init/android.hardware.light@2.0-service.rc", "0644", "vendor_configs_file"),
    ("etc/init/zz-grandppltedx-lights.rc", "0644", "vendor_configs_file"),
    (DRIVER, "0644", "vendor_file"),
)
VERIFIER = b'''#!/sbin/sh
set -eu
file=$1
shift
for expected do
    if [ "$expected" = ABSENT ] && [ ! -e "$file" ] && [ ! -L "$file" ]; then
        echo "Light HAL path is absent as expected"
        exit 0
    fi
done
actual=$(sha256sum "$file") || exit 1
actual=${actual%% *}
for expected do
    if [ "$actual" = "$expected" ]; then
        echo "Light HAL SHA-256 verified"
        exit 0
    fi
done
echo "Unexpected Light HAL file: $file SHA-256=$actual" >&2
exit 1
'''


def check(path, *hashes):
    arguments = ", ".join('"' + value + '"' for value in ("/sbin/sh", VERIFY, path, *hashes))
    return f'assert(run_program({arguments}) == "0");'


def write_zip(path, binary, payloads, originals, checks, undo=False):
    vendor = MOUNT + "/system/vendor/"
    lines = [
        'ui_print("J2 Prime Android 11 Light HAL update");',
        f'assert(package_extract_file("verify-lights.sh", "{VERIFY}"));',
        'assert(!is_mounted("/system") && !is_mounted("/system_root"));',
        f'assert(mount("ext4", "EMMC", "{base.BLOCK}", "{MOUNT}") != "");',
        f'assert(file_getprop("{MOUNT}/system/build.prop", "ro.lineage.version") == "{base.VERSION}");',
        f'assert(file_getprop("{MOUNT}/system/build.prop", "ro.build.version.sdk") == "30");',
        check(vendor + "lib/libshim_gui.so", GUI_SHA256),
    ]
    for relative, digest in checks:
        lines.append(check(MOUNT + "/system/" + relative, digest))
    # Preflight every path before any installed file is created or removed.
    for relative, _, _ in FILES:
        old = base.sha(originals[relative]) if relative in originals else "ABSENT"
        lines.append(check(vendor + relative, old, base.sha(payloads[relative])))
    for relative, mode, label in FILES:
        target = vendor + relative
        if undo and relative not in originals:
            lines.append(f'delete("{target}");')
            lines.append(check(target, "ABSENT"))
        else:
            expected = originals[relative] if undo else payloads[relative]
            lines.append(f'assert(package_extract_file("payload/{relative}", "{target}"));')
            lines.append(f'set_metadata("{target}", "uid", 0, "gid", 0, "mode", {mode}, '
                         f'"selabel", "u:object_r:{label}:s0");')
            lines.append(check(target, base.sha(expected)))
    lines += [f'assert(unmount("{MOUNT}") != "");',
              'ui_print("Light HAL files verified; boot and userdata unchanged.");']
    entries = {base.PREFIX + "update-binary": binary,
               base.PREFIX + "updater-script": ("\n".join(lines) + "\n").encode(),
               "verify-lights.sh": VERIFIER}
    entries.update({"payload/" + name: data for name, data in
                    (originals if undo else payloads).items()})
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 25, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith("update-binary") else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC validation failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom_zip", type=Path)
    parser.add_argument("product", type=Path)
    parser.add_argument("--original-driver", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if base.sha(args.rom_zip.read_bytes()) != base.ROM_SHA256:
        parser.error("input ROM differs from the diagnosed build")
    validate(args.product)
    vendor = args.product / "system/vendor"
    payloads = {name: (vendor / name).read_bytes() for name, _, _ in FILES}
    originals = {DRIVER: args.original_driver.read_bytes()}
    if base.sha(originals[DRIVER]) != DRIVER_ORIGINAL or base.sha(payloads[DRIVER]) != DRIVER_PATCHED:
        parser.error("unexpected original or patched legacy light driver")
    checks = [("lib/android.hardware.light@2.0.so", base.sha((args.product / "system/lib/android.hardware.light@2.0.so").read_bytes()))]
    with zipfile.ZipFile(args.rom_zip) as archive:
        binary = archive.read(base.PREFIX + "update-binary")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    sums = []
    for suffix, undo in (("fix", False), ("undo", True)):
        path = args.out_dir / f"grandppltedx-20261025-lights-{suffix}.zip"
        write_zip(path, binary, payloads, originals, checks, undo=undo)
        sums.append(f"{base.sha(path.read_bytes())}  {path.name}\n")
        print(path, path.stat().st_size, "bytes")
    (args.out_dir / "LIGHTS-FIX-SHA256SUMS").write_text("".join(sums), encoding="ascii")
    return 0


if __name__ == "__main__":
    sys.exit(main())
