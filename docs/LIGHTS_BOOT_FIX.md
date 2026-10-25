# Lineage animation hang: missing Light HAL (October 25–26, 2026)

After display fix v2, the Lineage animation runs but the launcher never starts.
Boot logs and two watchdog dumps identify the next gate: `system_server`
repeatedly dies during boot phase 100. The display thread holds DisplayManager's
lock while waiting in `ILight::getService` during brightness initialization;
the main thread waits for that lock. Logs repeatedly say the Light HAL is not
registered and cannot be started.

The image declares `android.hardware.light@2.0::ILight/default` but contains no
service, implementation or init service. `device.mk` requested an unavailable
Samsung-specific module. The earlier running ROM did have that Samsung service.

## Corrections

* Package Android 11's `android.hardware.light@2.0-service` and `@2.0-impl` from
  the cached hardware/interfaces tree. The existing binderized manifest stays.
* Remove the legacy `lights.mt6735.so` driver's unused DT_NEEDED entry for the
  absent `libsecril-client.so`. It imports no RIL client functions and has no
  `dlsym` import. Only its dynamic table changes: code, strings, symbols,
  section/program headers and 22,196-byte size stay identical. No modem library changes.
* Give the system-UID HAL access to the real MTK LED-class backlight node during
  init. The existing Samsung panel-class permission rule remains. This sets
  ownership/mode only; it writes no brightness value.
* Add a `lights` build target, an uninstalled enumeration probe and packaged
  ELF/init/VINTF checks. Full `bacon` builds run the new checker as well.

The vendor branch includes `lights-dependency-provenance.json` and guarded,
idempotent `tools/fix_lights_dependency.py`; unknown blobs are rejected.
Original driver SHA-256:
`5150222ba0218d4dcc51dc81f616e7f9dbe5de15122518c8a49b283b62b45237`.
Corrected driver SHA-256:
`d83f7a9ed24076fc5d953ec964f5b2e698c342a4ac8acd18980feae60fe36be0`.

## Validation

Only Light components and the diagnostic were compiled on the briefly restarted
VM. No new ROM or kernel build. Service/implementation compilation completed
in 1m36s; the diagnostic build in 1m16s, including graph regeneration. Both
passed packaging checks. The unchanged platform revision is hardware/interfaces
`203e87a39c04f30bc1f09f6c2306b701d6b97fe0`.

The installed Android filesystem was mounted read-only in recovery with matching
APEX libraries. New HAL files came from a RAM fixture. The original driver
reproduces the missing RIL-client load error. The corrected driver passes
`dlopen(RTLD_NOW)`; the real HIDL factory opens it and reports types 0 through 5,
including BACKLIGHT. No `setLight` or brightness change was requested. Service
dependencies resolve too. Recovery has a different kernel, so this is not a
normal-boot or brightness-function test.

The entire fix installer, repeat installation and undo succeeded on a temporary
16 MiB ext4 image in recovery RAM. Test ZIPs differ from real ZIPs only in the
system block-device argument, pointing to the verified RAM-image loop device.
All version/hash guards, extraction/deletion and SELinux metadata commands ran.
Undo restored the exact old driver and removed only the four added files.
Independent checks confirm unchanged code/symbols, idempotence and rejection of
an unknown binary. Temporary mounts and fixture files are removed after testing.

## Installation and remaining tests

Install `grandppltedx-20261025-lights-fix.zip` in TWRP after display v2, with ZIP
signature verification off, then reboot System. No wipe or full ROM flash.
Guards require the exact base ROM, v2 GUI hash, matching Light interface and
known driver hashes. Four files are added and only the light driver is replaced.
Boot, userdata, calibration, radio libraries and Wi-Fi configurations are untouched.

`grandppltedx-20261025-lights-undo.zip` removes those additions and restores the
original driver, including the original missing-Light boot problem.

Normal boot, service registration, brightness range/slider, screen off/on and
suspend still need testing. Then repeat Wi-Fi/audio/Bluetooth/camera/GNSS tests.
The latest logs also show camera platform loading failing on `ucnv_toUChars_60`
in vendor `libskia.so`; loading the top-level camera HAL did not establish
working capture. This separate camera issue remains open.

References: [Android 11 Light wrapper](https://github.com/LineageOS/android_hardware_interfaces/blob/lineage-18.1/light/2.0/default/Light.cpp)
and [service declaration](https://github.com/LineageOS/android_hardware_interfaces/blob/lineage-18.1/light/2.0/default/android.hardware.light%402.0-service.rc).
