#!/usr/bin/env python3
"""Guard the pinned camera bundle's unavailable SensorListener startup paths.

Only changes three known code regions; does not access a phone or calibration.
The paired listener must match its deliberately-null factory implementation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

MANIFEST = json.loads((Path(__file__).resolve().parent / "camera/sensor-startup.json").read_text())

def digest(data):
    return hashlib.sha256(data).hexdigest()

def corrected(data, listener):
    if digest(listener) != MANIFEST["listener_sha256"]:
        raise ValueError("unknown SensorListener; refusing to disable available sensors")
    sha = digest(data)
    if sha == MANIFEST["patched_sha256"]:
        return bytes(data)
    if sha != MANIFEST["original_sha256"]:
        raise ValueError("unknown feature library; refusing modification")
    result = bytearray(data)
    for item in MANIFEST["changes"]:
        old, new = bytes.fromhex(item["original"]), bytes.fromhex(item["patched"])
        offset = item["offset"]
        if len(old) != len(new) or result[offset:offset + len(old)] != old:
            raise ValueError("unexpected sensor startup instruction block")
        result[offset:offset + len(old)] = new
    if digest(result) != MANIFEST["patched_sha256"]:
        raise ValueError("sensor startup guard hash mismatch")
    return bytes(result)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vendor_lib", type=Path, help="directory containing the two vendor libraries")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--apply", action="store_true")
    group.add_argument("--output", type=Path, help="write a separate candidate instead of editing the input")
    args = parser.parse_args()
    try:
        path = args.vendor_lib / "libfeatureio.so"
        before = path.read_bytes()
        after = corrected(before, (args.vendor_lib / "libcam.utils.sensorlistener.so").read_bytes())
        if args.output:
            if args.output.resolve() == path.resolve():
                raise ValueError("use --apply for in-place modification")
            args.output.write_bytes(after)
        elif before != after:
            if not args.apply:
                print("Guards available; use --output for a separate candidate or --apply", file=sys.stderr)
                return 1
            path.write_bytes(after)
    except (OSError, ValueError) as error:
        print("FAIL:", error, file=sys.stderr)
        return 1
    print("Sensor startup guards verified:", MANIFEST["patched_sha256"])
    return 0

if __name__ == "__main__":
    sys.exit(main())
