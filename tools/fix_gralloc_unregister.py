#!/usr/bin/env python3
"""Prepare a null-module cleanup guard for the pinned legacy gralloc.

Activated in the matching vendor tree after installation/reboot testing. A failed
hw_get_module lookup previously fell through and dereferenced a null module.
Return after the existing error log. Successful module lookup is unchanged.
This does not correct the preceding ION import/blit failures.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

MANIFEST = json.loads((Path(__file__).resolve().parent /
                       "camera/gralloc-unregister.json").read_text())


def corrected(data):
    digest = hashlib.sha256(data).hexdigest()
    if digest == MANIFEST["patched_sha256"]:
        return bytes(data)
    if digest != MANIFEST["original_sha256"]:
        raise ValueError("unknown gralloc; refusing to modify the display driver")
    offset = MANIFEST["offset"]
    old, new = bytes.fromhex(MANIFEST["original"]), bytes.fromhex(MANIFEST["patched"])
    if len(old) != len(new) or data[offset:offset + len(old)] != old:
        raise ValueError("unexpected cleanup instruction")
    result = data[:offset] + new + data[offset + len(old):]
    if hashlib.sha256(result).hexdigest() != MANIFEST["patched_sha256"]:
        raise ValueError("gralloc guard hash mismatch")
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.original.resolve() == args.output.resolve():
            raise ValueError("output must be separate from the installed vendor input")
        result = corrected(args.original.read_bytes())
        args.output.write_bytes(result)
    except (OSError, ValueError) as error:
        print("FAIL:", error, file=sys.stderr)
        return 1
    print("Verified graphics cleanup guard:", MANIFEST["patched_sha256"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
