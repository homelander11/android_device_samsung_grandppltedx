#!/usr/bin/env python3
"""Prepare a temporary early-charger ramdisk diagnostic and exact boot undo.

Reads the pinned ROM and a full 16 MiB boot backup. Kernel, DT, command line,
addresses, board ID and original init bytes stay unchanged. Never accesses a
device. The separately reviewed recovery ZIP writes only the boot partition.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile

import create_display_fix as base
import verify_boot_image

DEVICE = Path(__file__).resolve().parents[2]
MANIFEST = DEVICE / "tools/charger/early/manifest.json"
BOOT = "/dev/block/platform/mtk-msdc.0/11230000.msdc0/by-name/boot"
CACHE = "/dev/block/platform/mtk-msdc.0/11230000.msdc0/by-name/cache"
VERIFY = "/tmp/j2prime-early-boot-verify.sh"
VERIFIER = ('''#!/sbin/sh
set -eu
boot=@BOOT@
cache=@CACHE@
case "$1" in
--preflight)
    test "$(id -u)" = 0
    test "$(getprop ro.product.model)" = SM-G532G
    test "$(readlink -f "$boot")" = /dev/block/mmcblk0p14
    test "$(readlink -f "$cache")" = /dev/block/mmcblk0p27
    test -b "$boot" && test -b "$cache"
    test "$(cat /sys/class/block/mmcblk0p14/size)" = 32768
    capacity=$(cat /sys/class/power_supply/battery/capacity)
    case "$capacity" in ''|*[!0-9]*) exit 1;; esac
    if [ "$capacity" -lt 40 ]; then
        echo "Charge to at least 40% before the boot diagnostic/undo." >&2
        exit 1
    fi
    ;;
--hash)
    shift
    test -b "$boot"
    actual=$(sha256sum "$boot") || exit 1
    actual=${actual%% *}
    for expected do
        if [ "$actual" = "$expected" ]; then exit 0; fi
    done
    echo "Unexpected boot partition hash; nothing accepted." >&2
    exit 1
    ;;
*) exit 1;;
esac
'''.replace("@BOOT@", BOOT).replace("@CACHE@", CACHE)).encode()


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cpio_read(data):
    entries, pos = [], 0
    while pos + 110 <= len(data):
        header = data[pos:pos + 110]
        if header[:6] != b"070701":
            raise ValueError("expected newc ramdisk")
        fields = [int(header[6 + i * 8:14 + i * 8], 16) for i in range(13)]
        size, namesize = fields[6], fields[11]
        if not namesize or pos + 110 + namesize > len(data):
            raise ValueError("truncated cpio name")
        name = data[pos + 110:pos + 110 + namesize - 1].decode()
        start = (pos + 110 + namesize + 3) & ~3
        if start + size > len(data):
            raise ValueError("truncated cpio content")
        if name == "TRAILER!!!":
            return entries
        if name in {entry[0] for entry in entries}:
            raise ValueError("duplicate ramdisk entry")
        entries.append((name, fields, data[start:start + size]))
        pos = (start + size + 3) & ~3
    raise ValueError("missing cpio trailer")


def cpio_write(entries):
    output = bytearray()
    trailer = [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 11, 0]
    for name, fields, content in [*entries, ("TRAILER!!!", trailer, b"")]:
        fields = fields.copy()
        fields[6], fields[11], fields[12] = len(content), len(name.encode()) + 1, 0
        output += b"070701" + b"".join(f"{n:08x}".encode() for n in fields)
        output += name.encode() + b"\0"
        output += b"\0" * ((-len(output)) % 4)
        output += content
        output += b"\0" * ((-len(output)) % 4)
    return bytes(output)


def make_image(original, wrapper, dt, expected):
    verify_boot_image.verify(original, dt)
    if len(original) != 16777216:
        raise ValueError("need the full 16 MiB boot partition backup")
    h = struct.unpack_from("<10I", original, 8)
    kernel_size, ramdisk_size, page, dt_size = h[0], h[2], h[7], h[8]
    align = lambda n: (n + page - 1) // page * page
    ramdisk_at = page + align(kernel_size)
    dt_at = ramdisk_at + align(ramdisk_size)
    entries = cpio_read(gzip.decompress(original[ramdisk_at:ramdisk_at + ramdisk_size]))
    if any(name == "init.real" for name, _, _ in entries):
        raise ValueError("ramdisk is already modified")
    inits = [entry for entry in entries if entry[0] == "init"]
    if len(inits) != 1 or base.sha(inits[0][2]) != expected["original_init_sha256"]:
        raise ValueError("unexpected original first-stage init")
    new = [("init.real" if name == "init" else name, fields, content)
           for name, fields, content in entries]
    fields = inits[0][1].copy()
    fields[0] = max(entry[1][0] for entry in entries) + 1
    fields[1], fields[2], fields[3], fields[4], fields[5] = 0o100755, 0, 0, 1, 0
    new.append(("init", fields, wrapper))
    compressed = gzip.compress(cpio_write(new), compresslevel=9, mtime=0)
    header = bytearray(original[:page])
    struct.pack_into("<I", header, 16, len(compressed))
    kernel = original[page:page + kernel_size]
    digest = hashlib.sha1()
    for content in (kernel, compressed, b"", dt):
        digest.update(content)
        digest.update(struct.pack("<I", len(content)))
    header[576:608] = digest.digest() + b"\0" * 12
    body = (header + original[page:ramdisk_at] + compressed +
            b"\0" * (align(len(compressed)) - len(compressed)) + dt +
            b"\0" * (align(dt_size) - dt_size))
    if len(body) > len(original):
        raise ValueError("diagnostic exceeds boot partition")
    image = bytearray(original)
    image[:len(body)] = body
    verify_boot_image.verify(image, dt)
    assert original[dt_at:dt_at + dt_size] == dt
    assert image[page:page + kernel_size] == kernel
    for n in range(page):
        if not (16 <= n < 20 or 576 <= n < 608):
            assert image[n] == original[n], "unexpected header change"
    extracted = {name: content for name, _, content in cpio_read(gzip.decompress(compressed))}
    assert extracted["init.real"] == inits[0][2] and extracted["init"] == wrapper
    for name, _, content in entries:
        assert extracted["init.real" if name == "init" else name] == content
    return bytes(image)


def run_check(operation, *hashes):
    args = ("/sbin/sh", VERIFY, operation, *hashes)
    return 'assert(run_program(' + ', '.join('"' + x + '"' for x in args) + ') == "0");'


def package(path, updater, image, accepted):
    script = "\n".join([
        'ui_print("J2 Prime temporary early-charger boot diagnostic / exact undo");',
        f'assert(package_extract_file("verify-boot.sh", "{VERIFY}"));',
        run_check("--preflight"), run_check("--hash", *accepted),
        f'assert(package_extract_file("boot.img", "{BOOT}"));',
        run_check("--hash", base.sha(image)),
        'ui_print("Boot image verified. Reboot System without wiping.");', "",
    ]).encode()
    entries = {base.PREFIX + "update-binary": updater,
               base.PREFIX + "updater-script": script,
               "verify-boot.sh": VERIFIER, "boot.img": image}
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 28, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith("update-binary") else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("generated ZIP CRC failure")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom_zip", type=Path)
    parser.add_argument("boot_backup", type=Path)
    parser.add_argument("wrapper", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        expected = json.loads(MANIFEST.read_text())
        for name, digest in expected["sources_canonical_lf_sha256"].items():
            content = (MANIFEST.parent / name).read_bytes().replace(b"\r\n", b"\n")
            if base.sha(content) != digest:
                raise ValueError("early-helper source differs from tested manifest: " + name)
        if file_hash(args.rom_zip) != base.ROM_SHA256:
            raise ValueError("input ROM differs from diagnosed build")
        wrapper = args.wrapper.read_bytes()
        if base.sha(wrapper) != expected["wrapper_sha256"]:
            raise ValueError("wrapper differs from reviewed/tested production ELF")
        with zipfile.ZipFile(args.rom_zip) as archive:
            pinned = archive.read("boot.img")
            updater = archive.read(base.PREFIX + "update-binary")
        original = args.boot_backup.read_bytes()
        if original[:len(pinned)] != pinned:
            raise ValueError("current boot prefix differs from pinned ROM")
        dt = (DEVICE / "prebuilt/dt.img").read_bytes()
        image = make_image(original, wrapper, dt, expected)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        for name, content in (("before-early-boot.img", original), ("early-charger-boot.img", image)):
            path = args.out_dir / ("grandppltedx-20261028-" + name)
            if path.exists() and path.read_bytes() != content:
                raise ValueError("refusing to overwrite different image: " + str(path))
            path.write_bytes(content)
        accepted = (base.sha(original), base.sha(image))
        sums = []
        for suffix, content in (("early-charger-boot", image), ("early-charger-boot-undo", original)):
            path = args.out_dir / ("grandppltedx-20261028-" + suffix + ".zip")
            package(path, updater, content, accepted)
            sums.append(f"{base.sha(path.read_bytes())}  {path.name}\n")
            print(path.name, path.stat().st_size, "bytes")
        report = {"original_partition_sha256": accepted[0], "diagnostic_partition_sha256": accepted[1],
                  "kernel_dt_cmdline_addresses_original_init": "preserved; structural checks PASS",
                  "device_boot": "NOT TESTED", "packages": sums}
        (args.out_dir / "EARLY-CHARGER-BOOT.json").write_text(json.dumps(report, indent=2) + "\n")
        (args.out_dir / "EARLY-CHARGER-SHA256SUMS").write_text("".join(sums), encoding="ascii")
    except (OSError, ValueError, struct.error, zipfile.BadZipFile) as error:
        print("FAIL:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
