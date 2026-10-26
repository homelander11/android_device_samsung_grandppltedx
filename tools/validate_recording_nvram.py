#!/usr/bin/env python3
"""Validate paired recording selectors against the bundled NVRAM table."""
import argparse
from pathlib import Path
import struct
import sys

from elf32 import Elf32

RECORDS = (
    ("GetHdRecordParamFromNV", 0x5c, "Audio_Hd_Record_Param", 4054),
    ("SetHdRecordParamToNV", 0x50, "Audio_Hd_Record_Param", 4054),
    ("GetHdRecordSceneTableFromNV", 0x5c, "Audio_Hd_Record_Scene_Table", 135),
    ("SetHdRecordSceneTableToNV", 0x50, "Audio_Hd_Record_Scene_Table", 135),
)


def validate(vendor, audio_data=None):
    table = Elf32(vendor / "lib/libcustom_nvram.so")
    audio = Elf32(vendor / "lib/libaudiocustparam_vendor.so")
    if audio_data is not None:
        audio.data = audio_data
    if table.machine != 40 or audio.machine != 40:
        raise ValueError("expected ARM NVRAM table and audio library")
    base, = struct.unpack("<I", table.symbol_data("g_i4CFG_File_Count"))
    count, = struct.unpack("<I", table.symbol_data("g_i4CFG_File_Custom_Count"))
    records = table.symbol_data("g_akCFG_File_Custom")
    if len(records) != count * 100:
        raise ValueError("unexpected NVRAM table ABI")
    result = []
    for name, offset, expected, size in RECORDS:
        if audio.symbols[name]["value"] & 1:
            raise ValueError(f"{name}: expected ARM selector instruction")
        instruction = audio.symbol_data(name)[offset:offset + 4]
        if len(instruction) != 4 or instruction[1:] != b"\x10\xa0\xe3":
            raise ValueError(f"{name}: expected MOV r1, #LID")
        lid = instruction[0]
        if not base <= lid < base + count:
            raise ValueError(f"{name}: LID {lid} outside the bundled custom table")
        item = records[(lid - base) * 100:(lid - base + 1) * 100]
        path = item[:64].split(b"\0", 1)[0].decode("ascii")
        record_size, number = struct.unpack_from("<II", item, 76)
        if path != "/data/nvram/media/" + expected or (record_size, number) != (size, 1):
            raise ValueError(f"{name}: LID {lid} selects {path} ({record_size} x {number}), "
                             f"expected {expected} ({size} x 1)")
        result.append((name, lid, expected, size))
    if result[0][1] != result[1][1] or result[2][1] != result[3][1]:
        raise ValueError("recording getters and setters disagree")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vendor", type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.vendor)
    except (OSError, ValueError, KeyError, IndexError, struct.error) as error:
        print("FAIL:", error, file=sys.stderr)
        return 1
    for name, lid, record, size in result:
        print(f"{name}: LID {lid} -> {record} ({size} bytes)")
    print("Recording selectors match the bundled NVRAM record names and sizes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
