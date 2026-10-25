#!/usr/bin/env python3
"""Check audio-filter LIDs against the bundled NVRAM table, without device I/O."""
import argparse
from pathlib import Path
import struct
import sys

from elf32 import Elf32


EXPECTED = ("Headphone_CompFlt", "Audio_CompFlt", "VibSpk_CompFlt",
            "Audio_CompFlt", "MusicDRC_CompFlt", "RingToneDRC_CompFlt")


def read_va(elf, address, size):
    for section in elf.sections:
        if section[3] <= address and address + size <= section[3] + section[5]:
            offset = section[4] + address - section[3]
            return elf.data[offset:offset + size]
    raise ValueError(f"unmapped ELF address: {address:#x}")


def validate(vendor, audio_data=None):
    table = Elf32(vendor / "lib/libcustom_nvram.so")
    audio = Elf32(vendor / "lib/libaudiocompensationfilter_vendor.so")
    # Optional bytes support a read-only regression check of the original blob.
    if audio_data is not None:
        audio.data = audio_data
    base, = struct.unpack("<I", table.symbol_data("g_i4CFG_File_Count"))
    count, = struct.unpack("<I", table.symbol_data("g_i4CFG_File_Custom_Count"))
    records = table.symbol_data("g_akCFG_File_Custom")
    if len(records) != count * 100:
        raise ValueError("unexpected NVRAM table ABI")

    def record(lid):
        if not base <= lid < base + count:
            raise ValueError(f"LID {lid} is outside the custom NVRAM table")
        item = records[(lid - base) * 100:(lid - base + 1) * 100]
        name = item[:64].split(b"\0", 1)[0].decode("ascii")
        size, number = struct.unpack_from("<II", item, 76)
        return name, size * number

    getter = audio.symbol_data("getAudioCompFltCustParamFromStorage")
    setter = audio.symbol_data("setAudioCompFltCustParamToStorage")
    if getter[0x27] != 0x21 or setter[0x21] != 0x21:
        raise ValueError("unexpected getter/setter instruction layout")
    if getter[0x26] != setter[0x20]:
        raise ValueError("getter and setter select different default LIDs")
    getter_base = audio.symbols["getAudioCompFltCustParamFromStorage"]["value"] & ~1
    setter_base = audio.symbols["setAudioCompFltCustParamToStorage"]["value"] & ~1
    address = getter_base + 0x22 + struct.unpack_from("<I", getter, 0x9c)[0]
    other = setter_base + 0x1c + struct.unpack_from("<I", setter, 0x6c)[0]
    if address != other:
        raise ValueError("getter and setter use different filter tables")
    lids = struct.unpack("<6I", read_va(audio, address, 24))
    result = []
    for kind, lid, expected in zip(range(7), (getter[0x26],) + lids,
                                    ("Audio_CompFlt",) + EXPECTED):
        name, size = record(lid)
        if name != "/data/nvram/media/" + expected or size != 1260:
            raise ValueError(f"filter {kind}: LID {lid} resolves to {name} ({size} bytes), "
                             f"expected {expected} (1260 bytes)")
        result.append((kind, lid, name))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vendor", type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.vendor)
    except (OSError, ValueError, KeyError, IndexError, struct.error) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    for kind, lid, name in result:
        print(f"filter {kind}: LID {lid} -> {name}")
    print("Audio-filter LIDs and record sizes match the bundled NVRAM table.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
