#!/usr/bin/env python3
"""Correct the pinned MT6737T audio HAL's deep-buffer PCM name for this kernel.

The replacement has the same length, including NUL. No executable bytes, ELF
layout, microphone selectors or calibration data are changed. Reject unknown
vendor binaries rather than applying a generic string substitution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

MANIFEST = json.loads((Path(__file__).resolve().parent /
                       "audio/deep-buffer-pcm.json").read_text())


def corrected(data):
    digest = hashlib.sha256(data).hexdigest()
    if digest == MANIFEST["patched_sha256"]:
        return bytes(data)
    if digest != MANIFEST["original_sha256"] or len(data) != MANIFEST["size"]:
        raise ValueError("unknown audio HAL; refusing to modify playback routing")
    offset = MANIFEST["offset"]
    old, new = bytes.fromhex(MANIFEST["original"]), bytes.fromhex(MANIFEST["patched"])
    if len(old) != len(new) or data[offset:offset + len(old)] != old:
        raise ValueError("unexpected deep-buffer PCM literal")
    result = data[:offset] + new + data[offset + len(old):]
    if hashlib.sha256(result).hexdigest() != MANIFEST["patched_sha256"]:
        raise ValueError("audio HAL correction hash mismatch")
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.original.resolve() == args.output.resolve():
            raise ValueError("output must be separate from the input vendor library")
        args.output.write_bytes(corrected(args.original.read_bytes()))
    except (OSError, ValueError) as error:
        print("FAIL:", error, file=sys.stderr)
        return 1
    print("Deep-buffer PCM corrected:", MANIFEST["patched_sha256"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
