#!/usr/bin/env python3
"""Package the diagnosed GPS socket path correction and exact undo for TWRP.

No build/device access. Both ZIPs replace only gps.default.so and pin the base
ROM, earlier display/Light fixes, GNSS init files and both known GPS hashes.
"""
import argparse
from pathlib import Path
import sys
import zipfile

import create_display_fix as base

OLD = "9dea2246a148f6f60d0f3c9a69b7d9fe92da4a645abf7153c815ac73ead5befc"
NEW = "26810174325967eafe9a7292a3efb65c8700943d4189a1c37e08a52905c253cf"
MOUNT = "/tmp/j2prime-gnss-system"
VERIFY = "/tmp/j2prime-gnss-verify.sh"
CHECKS = {
    "lib/libshim_gui.so": "c52b763c485f0613b5d95047d0d993a04f23f6429f37143172d46de2f20cb362",
    "lib/hw/lights.mt6735.so": "d83f7a9ed24076fc5d953ec964f5b2e698c342a4ac8acd18980feae60fe36be0",
    "bin/hw/android.hardware.light@2.0-service": "fda54b6ab123270033bbcf7687543b7c71c229feae7c3ad65cce6607f89eab6a",
    "etc/init/zz-grandppltedx-gnss.rc": "532b85eebdaf7b09694291a1bcc659549df1579b2b041e96a5fd8a23a15cc853",
    "etc/init/mtk_agpsd.rc": "57ec1d934b78d6a78c02fa74caae5766b28ab97c873b9711f1b211e931dae800",
}


def check(path, *hashes):
    args = ", ".join('"' + value + '"' for value in ("/sbin/sh", VERIFY, path, *hashes))
    return f'assert(run_program({args}) == "0");'


def package(path, binary, payload):
    vendor = MOUNT + "/system/vendor/"
    target = vendor + "lib/hw/gps.default.so"
    lines = [
        'ui_print("J2 Prime GPS worker socket update");',
        f'assert(package_extract_file("verify-gps.sh", "{VERIFY}"));',
        'assert(!is_mounted("/system") && !is_mounted("/system_root"));',
        f'assert(mount("ext4", "EMMC", "{base.BLOCK}", "{MOUNT}") != "");',
        f'assert(file_getprop("{MOUNT}/system/build.prop", "ro.lineage.version") == "{base.VERSION}");',
        f'assert(file_getprop("{MOUNT}/system/build.prop", "ro.build.version.sdk") == "30");',
    ]
    lines += [check(vendor + relative, digest) for relative, digest in CHECKS.items()]
    lines += [
        check(target, OLD, NEW),
        f'assert(package_extract_file("gps.default.so", "{target}"));',
        f'set_metadata("{target}", "uid", 0, "gid", 0, "mode", 0644, "selabel", "u:object_r:vendor_file:s0");',
        check(target, base.sha(payload)),
        f'assert(unmount("{MOUNT}") != "");',
        'ui_print("GPS library verified; boot and userdata unchanged.");',
    ]
    entries = {
        base.PREFIX + "update-binary": binary,
        base.PREFIX + "updater-script": ("\n".join(lines) + "\n").encode(),
        "verify-gps.sh": base.HASH_VERIFIER.replace(b"GUI shim", b"GPS HAL"),
        "gps.default.so": payload,
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


def main():
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
        parser.error("unexpected original or patched GPS HAL")
    if (len(old) != len(new) or old[:84903] != new[:84903]
            or old[84925:] != new[84925:]):
        parser.error("GPS library changes extend outside its socket string slot")
    with zipfile.ZipFile(args.rom_zip) as archive:
        binary = archive.read(base.PREFIX + "update-binary")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    sums = []
    for suffix, payload in (("fix", new), ("undo", old)):
        path = args.out_dir / f"grandppltedx-20261026-gnss-{suffix}.zip"
        package(path, binary, payload)
        sums.append(f"{base.sha(path.read_bytes())}  {path.name}\n")
        print(path, path.stat().st_size, "bytes")
    (args.out_dir / "GNSS-FIX-SHA256SUMS").write_text("".join(sums), encoding="ascii")
    return 0


if __name__ == "__main__":
    sys.exit(main())
