#!/usr/bin/env python3
"""Package the pinned Android 11 camera/audio candidate and exact undo for TWRP.

Uses the diagnosed ROM's updater. Replaces ten camera libraries, the primary
audio HAL's deep-buffer PCM name, and adds
private camera runtime files, a license and node-ownership init commands.
No boot, recovery, userdata, calibration, microphone, Wi-Fi or global Skia/ICU writes.
"""
import argparse
import json
from pathlib import Path
import sys
import zipfile

import create_display_fix as base
import create_recording_fix as recording

TOOLS = Path(__file__).resolve().parents[1]
DEVICE = TOOLS.parent
META = json.loads((TOOLS / "camera/android11-metadata.json").read_text())
SENSOR = json.loads((TOOLS / "camera/sensor-startup.json").read_text())
AUDIO = json.loads((TOOLS / "audio/deep-buffer-pcm.json").read_text())
COLOUR = json.loads((TOOLS / "camera/video-colour.json").read_text())
MOUNT = "/tmp/j2prime-camera-system"
VERIFY = "/tmp/j2prime-camera-verify.sh"
NEW_FILES = ("lib/libcamcx.so", "lib/libicu60.so", "lib/libicui60.so",
             "lib/libskic.so", "etc/licenses/ICU-60.txt",
             "etc/init/zz-grandppltedx-camera.rc")
VERIFIER = b'''#!/sbin/sh
set -eu
file=$1
shift
test ! -L "$file" || exit 1
actual=ABSENT
if [ -e "$file" ]; then
    actual=$(sha256sum "$file") || exit 1
    actual=${actual%% *}
fi
for expected do
    if [ "$actual" = "$expected" ]; then exit 0; fi
done
echo "Unexpected camera/dependency hash: $actual" >&2
exit 1
'''


def check(path, *hashes):
    args = ", ".join('"' + x + '"' for x in ("/sbin/sh", VERIFY, path, *hashes))
    return f'assert(run_program({args}) == "0");'


def package(path, updater, original, modified, added, undo):
    vendor = MOUNT + "/system/vendor/"
    checks = dict(recording.CHECKS)
    # This formerly pinned dependency is now an explicitly checked payload.
    checks.pop("lib/hw/audio.primary.mt6737t.so")
    checks.update({
        "lib/hw/lights.mt6735.so": recording.backlight.NEW,
        "lib/libaudiocustparam_vendor.so": recording.NEW,
        "lib/libskia.so": next(x["original_sha256"] for x in META["entries"]
                               if x["name"] == "libskic.so"),
        "lib/libicui18n.so": next(x["original_sha256"] for x in META["entries"]
                                  if x["name"] == "libicui60.so"),
        "lib/libcam.utils.sensorlistener.so": SENSOR["listener_sha256"],
    })
    lines = [
        'ui_print("J2 Prime Android 11 camera and deep-buffer audio update");',
        f'assert(package_extract_file("verify-camera.sh", "{VERIFY}"));',
        'assert(!is_mounted("/system") && !is_mounted("/system_root"));',
        f'assert(mount("ext4", "EMMC", "{base.BLOCK}", "{MOUNT}") != "");',
        f'assert(file_getprop("{MOUNT}/system/build.prop", "ro.lineage.version") == "{base.VERSION}");',
        f'assert(file_getprop("{MOUNT}/system/build.prop", "ro.build.version.sdk") == "30");',
    ]
    lines += [check(vendor + name, sha) for name, sha in sorted(checks.items())]
    for name in original:
        lines.append(check(vendor + name, base.sha(original[name]), base.sha(modified[name])))
    for name, data in added.items():
        accepted = ["ABSENT", base.sha(data)]
        if name == "lib/libcamcx.so" and base.sha(data) == COLOUR["patched_sha256"]:
            accepted.append(COLOUR["original_sha256"])
        lines.append(check(vendor + name, *accepted))
    payload = original if undo else {**added, **modified}
    # Preflight is complete before any installed file is replaced.
    lines.append(f'assert(package_extract_dir("camera", "{vendor.rstrip("/")}"));')
    if not undo:
        lines.append(f'set_metadata("{vendor}etc/licenses", "uid", 0, "gid", 0, "mode", 0755, "selabel", "u:object_r:vendor_configs_file:s0");')
    for name, data in payload.items():
        label = "vendor_configs_file" if name.startswith("etc/") else "vendor_file"
        lines.append(f'set_metadata("{vendor}{name}", "uid", 0, "gid", 0, "mode", 0644, "selabel", "u:object_r:{label}:s0");')
        lines.append(check(vendor + name, base.sha(data)))
    if undo:
        for name in added:
            lines.append(f'delete("{vendor}{name}");')
            lines.append(check(vendor + name, "ABSENT"))
    lines += [f'assert(unmount("{MOUNT}") != "");',
              'ui_print("Camera/audio files verified. Reboot System without wiping.");']
    entries = {base.PREFIX + "update-binary": updater,
               base.PREFIX + "updater-script": ("\n".join(lines) + "\n").encode(),
               "verify-camera.sh": VERIFIER,
               **{"camera/" + name: data for name, data in payload.items()}}
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 27, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith("update-binary") else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("camera ZIP CRC failure")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom_zip", type=Path)
    parser.add_argument("vendor_lib", type=Path)
    parser.add_argument("original_lib", type=Path)
    parser.add_argument("helper", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if base.sha(args.rom_zip.read_bytes()) != base.ROM_SHA256:
            raise ValueError("input ROM differs from the diagnosed build")
        helper = base.Elf32(args.helper)
        required = ("j2prime_camera_thread_run",
                    "_ZN7android14Cam1DeviceBase22storeMetaDataInBuffersEb",
                    "_ZN7android14Cam1DeviceBase11takePictureEv",
                    "_ZN7android14Cam1DeviceBase16setPreviewWindowEP18preview_stream_ops",
                    "PerfServiceNative_userRegScn")
        if helper.machine != 40 or not all(helper.exports(n) for n in required):
            raise ValueError("helper lacks the required ARM camera ABI exports")
        import struct
        global_symbols = False
        for section in helper.sections:
            if section[1] == 6:  # SHT_DYNAMIC
                for offset in range(section[4], section[4] + section[5], section[9]):
                    tag, value = struct.unpack_from("<iI", helper.data, offset)
                    if tag == 0x6ffffffb and value & 2:  # DT_FLAGS_1 / DF_1_GLOBAL
                        global_symbols = True
        if not global_symbols:
            raise ValueError("helper requires DF_1_GLOBAL for Cam1 vtable interposition")
        original, modified, added = {}, {}, {"lib/libcamcx.so": args.helper.read_bytes()}
        for item in META["entries"] + [dict(name="libfeatureio.so",
                original_sha256=SENSOR["original_sha256"], patched_sha256=SENSOR["patched_sha256"])]:
            name = item["name"]
            data = (args.vendor_lib / name).read_bytes()
            if base.sha(data) != item["patched_sha256"]:
                raise ValueError("unexpected camera candidate: " + name)
            if name in ("libicu60.so", "libicui60.so", "libskic.so"):
                added["lib/" + name] = data
            else:
                before = (args.original_lib / name).read_bytes()
                if base.sha(before) != item["original_sha256"]:
                    raise ValueError("unexpected original camera library: " + name)
                original["lib/" + name], modified["lib/" + name] = before, data
        added["etc/init/zz-grandppltedx-camera.rc"] = (DEVICE / "configs/init/zz-grandppltedx-camera.rc").read_bytes()
        added["etc/licenses/ICU-60.txt"] = (args.vendor_lib.parent / "etc/licenses/ICU-60.txt").read_bytes()
        if set(added) != set(NEW_FILES):
            raise ValueError("unexpected camera update scope")
        audio_name = "lib/hw/audio.primary.mt6737t.so"
        audio = (args.vendor_lib / "hw/audio.primary.mt6737t.so").read_bytes()
        if base.sha(audio) != AUDIO["patched_sha256"] or len(audio) != AUDIO["size"]:
            raise ValueError("unexpected corrected primary audio HAL")
        offset = AUDIO["offset"]
        old, new = bytes.fromhex(AUDIO["original"]), bytes.fromhex(AUDIO["patched"])
        if len(old) != len(new) or audio[offset:offset + len(new)] != new:
            raise ValueError("unexpected deep-buffer PCM literal")
        before = audio[:offset] + old + audio[offset + len(new):]
        if base.sha(before) != AUDIO["original_sha256"]:
            raise ValueError("unexpected original primary audio HAL")
        original[audio_name], modified[audio_name] = before, audio
        with zipfile.ZipFile(args.rom_zip) as archive:
            updater = archive.read(base.PREFIX + "update-binary")
        args.out_dir.mkdir(parents=True, exist_ok=True)
        sums = []
        for suffix, undo in (("fix", False), ("undo", True)):
            path = args.out_dir / f"grandppltedx-20261027-camera-audio-{suffix}.zip"
            package(path, updater, original, modified, added, undo)
            sums.append(f"{base.sha(path.read_bytes())}  {path.name}\n")
            print(path, path.stat().st_size, "bytes")
        (args.out_dir / "CAMERA-FIX-SHA256SUMS").write_text("".join(sums), encoding="ascii")
    except (OSError, ValueError) as error:
        print("FAIL:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
