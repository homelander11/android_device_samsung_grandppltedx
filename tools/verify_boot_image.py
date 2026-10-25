#!/usr/bin/env python3
"""Validate grandppltedx's legacy Android boot header, DT and payload checksum.

This checks image structure, not bootloader acceptance or successful boot.
It never writes to an image or device.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


DEVICE = Path(__file__).resolve().parents[1]
PARTITION_SIZE = 16777216


def verify(data, dt):
    if len(data) < 2048 or len(data) > PARTITION_SIZE:
        raise ValueError("image is truncated or exceeds the 16 MiB partition")
    if data[:8] != b"ANDROID!":
        raise ValueError("missing Android boot magic")
    words = struct.unpack_from("<10I", data, 8)
    kernel_size, kernel_addr, ramdisk_size, ramdisk_addr = words[:4]
    second_size, second_addr, tags_addr, page_size, dt_size, _ = words[4:]
    if (kernel_addr, ramdisk_addr, tags_addr, page_size) != (
            0x40004000, 0x44000000, 0x4e000000, 2048):
        raise ValueError("load addresses/page size differ from the device layout")
    if not kernel_size or not ramdisk_size or second_size or second_addr:
        raise ValueError("expected kernel, ramdisk and no second-stage payload")
    if dt_size != len(dt):
        raise ValueError("legacy DT size differs from the device prebuilt")
    board = data[48:64].split(b"\0", 1)[0].decode("ascii")
    if board not in ("SRPPI01A000KU", "SRPPI01A000RU"):
        raise ValueError("unexpected Samsung board identifier")
    digest = hashlib.sha1()
    offset = page_size
    for name, size in (("kernel", kernel_size), ("ramdisk", ramdisk_size),
                       ("second", second_size), ("dt", dt_size)):
        if offset + size > len(data):
            raise ValueError(f"truncated {name} payload")
        payload = data[offset:offset + size]
        digest.update(payload)
        digest.update(struct.pack("<I", size))
        if name == "dt" and payload != dt:
            raise ValueError("embedded DT does not match the device prebuilt")
        offset = (offset + size + page_size - 1) // page_size * page_size
    if offset > len(data):
        raise ValueError("truncated final payload padding")
    if digest.digest() != data[576:596]:
        raise ValueError("legacy boot payload SHA-1 does not match the header")
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "board": board, "kernel_size": kernel_size,
            "ramdisk_size": ramdisk_size, "dt_size": dt_size,
            "payload_end": offset,
            "samsung_marker_at_payload_end":
                data[offset:offset + 16] == b"SEANDROIDENFORCE"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--dt", type=Path, default=DEVICE / "prebuilt/dt.img")
    args = parser.parse_args()
    try:
        result = verify(args.image.read_bytes(), args.dt.read_bytes())
    except (OSError, ValueError, struct.error) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    print("Boot structure/DT/checksum passed; physical-device boot remains unverified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
