#!/usr/bin/env python3
"""Package a single-library TWRP fix and undo ZIP for the 2026-10-25 ROM.

No device access. Reuses that ROM's update-binary; neither ZIP updates boot,
formats partitions, or touches userdata. TWRP ZIP signature verification must
be off for these unsigned development packages.
"""
import argparse
import hashlib
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from elf32 import Elf32

ROM_SHA256 = "1a7670ccb03e1b22cf1a646b74a18d678c8e33fd71525bee1c86b5fb3691f445"
OLD_SHA256 = "45191a874d9c61979a2e7236ca654c4a78b4d1e09e21d88ba08689d4871fb93d"
VERSION = "18.1-20261025-UNOFFICIAL-grandppltedx"
BLOCK = "/dev/block/platform/mtk-msdc.0/11230000.msdc0/by-name/system"
MOUNT = "/tmp/j2prime-display-system"
LIBRARY = MOUNT + "/system/vendor/lib/libshim_gui.so"
PREFIX = "META-INF/com/google/android/"
VERIFY = "/tmp/j2prime-display-verify.sh"
HASH_VERIFIER = b'''#!/sbin/sh
set -eu
file=$1
shift
actual=$(sha256sum "$file") || exit 1
actual=${actual%% *}
for expected do
    if [ "$actual" = "$expected" ]; then
        echo "GUI shim SHA-256 verified"
        exit 0
    fi
done
echo "Unexpected GUI shim SHA-256: $actual" >&2
exit 1
'''


def sha(data, algorithm="sha256"):
    return hashlib.new(algorithm, data).hexdigest()


def package(path, binary, payload, accepted):
    hashes = ", ".join('"' + sha(data) + '"' for data in accepted)
    script = f'''ui_print("J2 Prime Android 11 display compatibility update");
assert(package_extract_file("verify-shim.sh", "{VERIFY}"));
assert(!is_mounted("/system") && !is_mounted("/system_root"));
assert(mount("ext4", "EMMC", "{BLOCK}", "{MOUNT}") != "");
assert(file_getprop("{MOUNT}/system/build.prop", "ro.lineage.version") == "{VERSION}");
assert(file_getprop("{MOUNT}/system/build.prop", "ro.build.version.sdk") == "30");
assert(run_program("/sbin/sh", "{VERIFY}", "{LIBRARY}", {hashes}) == "0");
assert(package_extract_file("libshim_gui.so", "{LIBRARY}"));
set_metadata("{LIBRARY}", "uid", 0, "gid", 0, "mode", 0644, "selabel", "u:object_r:vendor_file:s0");
assert(run_program("/sbin/sh", "{VERIFY}", "{LIBRARY}", "{sha(payload)}") == "0");
assert(unmount("{MOUNT}") != "");
ui_print("Library verified. Boot and userdata were not changed.");
'''
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in ((PREFIX + "update-binary", binary),
                           (PREFIX + "updater-script", script.encode()),
                           ("verify-shim.sh", HASH_VERIFIER),
                           ("libshim_gui.so", payload)):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 25, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith("update-binary") else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("generated ZIP failed its CRC check")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom_zip", type=Path)
    parser.add_argument("new_shim", type=Path)
    parser.add_argument("old_shim", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if sha(args.rom_zip.read_bytes()) != ROM_SHA256:
        parser.error("base ROM hash differs from the diagnosed build")
    old, new = args.old_shim.read_bytes(), args.new_shim.read_bytes()
    if sha(old) != OLD_SHA256:
        parser.error("unexpected original GUI shim")
    elf = Elf32(args.new_shim)
    required = ("_ZN7android19GraphicBufferMapper4lockEPK13native_handlejRKNS_4RectEPPv",
                "_ZN7android13GraphicBuffer4lockEjPPv")
    if elf.machine != 40 or not all(elf.exports(name) for name in required):
        parser.error("new ARM shim is missing required lock exports")
    if "libutilscallstack.so" not in elf.needed:
        parser.error("new shim is missing its CallStack dependency")
    with zipfile.ZipFile(args.rom_zip) as archive:
        binary = archive.read(PREFIX + "update-binary")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for suffix, payload in (("fix", new), ("undo", old)):
        path = args.out_dir / f"grandppltedx-20261025-display-{suffix}-v2.zip"
        package(path, binary, payload, (old, new))
        outputs.append(f"{sha(path.read_bytes())}  {path.name}\n")
        print(path, path.stat().st_size, "bytes")
    (args.out_dir / "DISPLAY-FIX-v2-SHA256SUMS").write_text("".join(outputs), encoding="ascii")
    return 0


if __name__ == "__main__":
    sys.exit(main())
