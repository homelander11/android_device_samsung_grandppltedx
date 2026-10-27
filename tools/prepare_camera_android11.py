#!/usr/bin/env python3
"""Prepare the pinned MTK camera dependencies in a separate output directory.

Requires LIEF 0.16.6 for ICU/Skia ELF string-table rebuilding. Camera libraries
use equal-length dynstr edits and retain their original code and layout.
No phone access, downloads, calibration changes, or in-place edits.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from fix_camera_sensor_startup import corrected

MANIFEST = json.loads((Path(__file__).resolve().parent /
                       "camera/android11-metadata.json").read_text())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def protect_sections(original, candidate):
    for name in (".text", ".rodata", ".data", ".ARM.exidx"):
        before = original.get_section(name)
        if before is None:
            continue
        after = candidate.get_section(name)
        if (after is None or before.virtual_address != after.virtual_address or
                bytes(before.content) != bytes(after.content)):
            raise ValueError("ELF code/data layout changed: " + name)


def prepare(vendor_lib, icuuc, output):
    import lief
    if lief.__version__.split("-")[0] != MANIFEST["lief_version"]:
        raise ValueError("requires LIEF " + MANIFEST["lief_version"])
    if output.resolve() == vendor_lib.resolve():
        raise ValueError("output must be separate from the vendor input")
    inputs = []
    for item in MANIFEST["entries"]:
        source = icuuc if item["name"] == "libicu60.so" else vendor_lib / item["source_name"]
        data = source.read_bytes()
        already = digest(data) == item["patched_sha256"]
        if not already and digest(data) != item["original_sha256"]:
            raise ValueError("unknown input: " + item["name"])
        inputs.append((item, source, data, already))
    # Validate the paired sensor implementation before writing any candidates.
    feature = corrected((vendor_lib / "libfeatureio.so").read_bytes(),
                        (vendor_lib / "libcam.utils.sensorlistener.so").read_bytes())
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("output must be empty")
    for item, source, data, already in inputs:
        target = output / item["name"]
        if already:
            target.write_bytes(data)
        elif "thread_adapter" in item:
            if data.count(b"libutils.so\0") != 1:
                raise ValueError("ambiguous libutils dependency: " + item["name"])
            result = data.replace(b"libutils.so\0", b"libcamcx.so\0")
            if item["name"] == "libcam.camadapter.so":
                if result.count(b"libskia.so\0") != 1:
                    raise ValueError("ambiguous camera Skia dependency")
                result = result.replace(b"libskia.so\0", b"libskic.so\0")
            if item["thread_adapter"]:
                old = b"_ZN7android6Thread3runEPKcij\0"
                new = b"j2prime_camera_thread_run\0"
                if result.count(old) != 1:
                    raise ValueError("ambiguous Thread import: " + item["name"])
                result = result.replace(old, new.ljust(len(old), b"\0"))
            target.write_bytes(result)
        else:
            elf = lief.parse(str(source))
            if item["name"] in ("libicu60.so", "libicui60.so", "libskic.so"):
                for entry in elf.dynamic_entries:
                    if entry.tag == lief.ELF.DynamicEntry.TAG.SONAME:
                        entry.name = item["name"]
            if item["name"] in ("libicui60.so", "libskic.so"):
                elf.get_library("libicuuc.so").name = "libicu60.so"
            if item["name"] == "libskic.so":
                elf.get_library("libicui18n.so").name = "libicui60.so"
                for old, new in (
                    ("_ZN6icu_6013UnicodeStringC1EPKt", "_ZN6icu_6013UnicodeStringC1EPKDs"),
                    ("_ZNK6icu_6013UnicodeString13doCaseCompareEiiPKtiij",
                     "_ZNK6icu_6013UnicodeString13doCaseCompareEiiPKDsiij"),
                ):
                    elf.get_dynamic_symbol(old).name = new
            elf.write(str(target))
        result = target.read_bytes()
        if len(result) != item["size"] or digest(result) != item["patched_sha256"]:
            raise ValueError("candidate hash mismatch: " + item["name"])
        protect_sections(lief.parse(str(source)), lief.parse(str(target)))
        print("PASS:", item["name"], item["patched_sha256"])
    (output / "libfeatureio.so").write_bytes(feature)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vendor_lib", type=Path)
    parser.add_argument("--icuuc", type=Path, required=True,
                        help="pinned unmodified ICU 60 donor (see provenance)")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        prepare(args.vendor_lib, args.icuuc, args.output)
    except (OSError, ValueError, ImportError) as error:
        print("FAIL:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
