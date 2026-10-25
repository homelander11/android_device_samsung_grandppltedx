#!/usr/bin/env python3
"""Check the GPS worker socket correction; no hardware function is established."""
import argparse
import hashlib
from pathlib import Path
import sys

from elf32 import Elf32

EXPECTED = "26810174325967eafe9a7292a3efb65c8700943d4189a1c37e08a52905c253cf"
DEVICE = Path(__file__).resolve().parents[1]


def validate(vendor, source=False):
    elf = Elf32(vendor / "lib/hw/gps.default.so")
    if elf.machine != 40 or not elf.exports("HMI"):
        raise ValueError("expected an ARM ELF32 GPS HAL with HMI export")
    if hashlib.sha256(elf.data).hexdigest() != EXPECTED:
        raise ValueError("GPS HAL lacks the exact diagnosed worker socket correction")
    if elf.data[84903:84925] != b"/data/gps_mnl/codec\0\0\0":
        raise ValueError("unexpected GPS socket string slot")
    init = DEVICE / "configs/init" if source else vendor / "etc/init"
    service = (init / "zz-grandppltedx-gnss.rc").read_text()
    directories = (init / "mtk_agpsd.rc").read_text()
    if "user gps" not in service or "group system gps radio inet" not in service:
        raise ValueError("GNSS service UID/groups differ from the tested configuration")
    if "mkdir /data/gps_mnl 0771 gps system" not in directories:
        raise ValueError("GPS-owned worker socket directory is not provisioned")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vendor", type=Path)
    parser.add_argument("--source", action="store_true",
                        help="check source device init files instead of packaged init files")
    args = parser.parse_args()
    try:
        validate(args.vendor, source=args.source)
    except (OSError, ValueError) as error:
        sys.exit("FAIL: " + str(error))
    print("GPS HAL/socket/init checks passed; normal boot and satellite fixes require device testing.")
