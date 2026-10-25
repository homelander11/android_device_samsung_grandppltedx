#!/usr/bin/env python3
"""Check the packaged Light HAL service, wrapper, init registration and VINTF.

This rejects the missing-service condition observed in the watchdog traces.
Successful registration, backlight control and boot still need device tests.
"""
import argparse
import hashlib
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from elf32 import Elf32


def validate(product, require_brightness_fix=False):
    vendor = product / "system/vendor"
    service = Elf32(vendor / "bin/hw/android.hardware.light@2.0-service")
    wrapper = Elf32(vendor / "lib/hw/android.hardware.light@2.0-impl.so")
    driver = Elf32(vendor / "lib/hw/lights.mt6735.so")
    if any(elf.machine != 40 for elf in (service, wrapper, driver)):
        raise ValueError("Light HAL components must be ARM ELF32")
    for elf in (service, wrapper):
        if "android.hardware.light@2.0.so" not in elf.needed:
            raise ValueError("Light service/wrapper does not link the 2.0 interface")
    if not wrapper.exports("HIDL_FETCH_ILight") or not driver.exports("HMI"):
        raise ValueError("missing HIDL factory or legacy lights module export")
    if "libsecril-client.so" in driver.needed:
        raise ValueError("legacy lights HAL still requires the missing, unused Samsung RIL client")
    if require_brightness_fix and hashlib.sha256(driver.data).hexdigest() != (
            "9d2a8737e6ee146cdf7e74b0233fc38efd614d0a9e6d79832688a2cce2b81b75"):
        raise ValueError("legacy BACKLIGHT callback still writes packed ARGB instead of brightness")
    access = (vendor / "etc/init/zz-grandppltedx-lights.rc").read_text()
    if "chown system system /sys/class/leds/lcd-backlight/brightness" not in access:
        raise ValueError("missing system-UID access to the MTK backlight node")
    rc = (vendor / "etc/init/android.hardware.light@2.0-service.rc").read_text()
    if "service vendor.light-hal-2-0 /vendor/bin/hw/android.hardware.light@2.0-service" not in rc:
        raise ValueError("init service does not start the packaged Light executable")
    if "interface android.hardware.light@2.0::ILight default" not in rc:
        raise ValueError("init service does not register the default Light interface")
    manifest = ET.parse(vendor / "etc/vintf/manifest.xml")
    lights = [hal for hal in manifest.findall("hal")
              if hal.findtext("name") == "android.hardware.light"]
    if len(lights) != 1 or lights[0].findtext("transport") != "hwbinder":
        raise ValueError("expected one binderized Light HAL declaration")
    if lights[0].findtext("version") != "2.0" or not any(
            interface.findtext("name") == "ILight" and
            "default" in [item.text for item in interface.findall("instance")]
            for interface in lights[0].findall("interface")):
        raise ValueError("Light manifest must declare ILight 2.0/default")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product", type=Path)
    parser.add_argument("--require-brightness-fix", action="store_true")
    args = parser.parse_args()
    try:
        validate(args.product, require_brightness_fix=args.require_brightness_fix)
    except (OSError, ValueError, ET.ParseError) as error:
        print("FAIL:", error, file=sys.stderr)
        return 1
    print("Light HAL ELF/init/manifest checks passed; registration and device boot remain unverified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
