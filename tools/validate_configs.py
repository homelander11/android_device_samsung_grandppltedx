#!/usr/bin/env python3
"""Low-memory configuration checks; these do not establish hardware functionality."""
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


DEVICE = Path(__file__).resolve().parents[1]


def validate(device=DEVICE):
    errors = []
    for name in ("BoardConfig.mk", "device.mk"):
        source = (device / name).read_text(encoding="utf-8")
        for relative in set(re.findall(r"\$\(DEVICE_PATH\)/([\w./-]+)", source)):
            if not (device / relative).exists():
                errors.append(f"{name}: missing device path: {relative}")
    xml_count = 0
    for path in sorted(device.rglob("*.xml")):
        try:
            ET.parse(path)
            xml_count += 1
        except ET.ParseError as exc:
            errors.append(f"{path.relative_to(device)}: {exc}")

    policy = ET.parse(device / "configs/audio/audio_policy_configuration.xml")
    for module in policy.findall("./modules/module"):
        ports = {}
        for port in list(module.findall("./mixPorts/mixPort")) + list(
                module.findall("./devicePorts/devicePort")):
            name = port.get("name", port.get("tagName"))
            if name in ports:
                errors.append(f"duplicate audio port: {name}")
            ports[name] = port
            is_device = port.tag == "devicePort"
            is_input = (port.get("role") == "source") == is_device
            prefix = "AUDIO_CHANNEL_IN_" if is_input else "AUDIO_CHANNEL_OUT_"
            for profile in port.findall("profile"):
                for mask in profile.get("channelMasks", "").split(","):
                    if mask and mask != "dynamic" and not mask.startswith(
                            (prefix, "AUDIO_CHANNEL_INDEX_")):
                        errors.append(f"{name}: invalid channel direction: {mask}")
        for item in module.findall("./attachedDevices/item"):
            if item.text not in ports:
                errors.append(f"unknown attached device: {item.text}")
        default = module.findtext("defaultOutputDevice")
        if default and default not in ports:
            errors.append(f"unknown default output: {default}")
        for route in module.findall("./routes/route"):
            sink = route.get("sink")
            if sink not in ports or ports[sink].get("role") != "sink":
                errors.append(f"invalid route sink: {sink}")
            for source in route.get("sources", "").split(","):
                if source not in ports or ports[source].get("role") != "source":
                    errors.append(f"invalid route source: {source}")

    # Both are shipped: an overlay must not replace the working driver parameter.
    for name in ("wpa_supplicant.conf", "wpa_supplicant_overlay.conf"):
        params = [line.split("=", 1)[1].split() for line in
                  (device / "configs/wifi" / name).read_text().splitlines()
                  if line.startswith("driver_param=")]
        if len(params) != 1 or not {
                "use_p2p_group_interface=1", "force_connect_cmd=1"}.issubset(params[0]):
            errors.append(f"{name}: missing known-working Wi-Fi driver parameters")
    return errors, xml_count


if __name__ == "__main__":
    errors, count = validate()
    for error in errors:
        print(f"FAIL: {error}")
    print(f"Parsed {count} XML files; checked device paths, audio routes/channels and Wi-Fi.")
    print("Static checks only; hardware and Android build validation are separate.")
    sys.exit(bool(errors))
