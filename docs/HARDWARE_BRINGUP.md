# LineageOS 18.1 hardware bring-up

October 27 playback follow-up: the primary audio HAL requests a nonexistent
deep-buffer PCM name and opens device -1. A pinned string correction selects
the kernel's existing DL2/device 24. Temporary tests now pass synthetic video
with tone, previously frozen clips, and fresh rear/front camera recordings
with sound and Camera reopening. See `AUDIO_DEEP_BUFFER_FIX.md`. Persistent
installation/reboot and other audio routes remain pending; GPU and codec
experiments are inactive.

Recovery reboot follow-up: the existing TWRP image is intact. Android 11 refused
software recovery requests because the active fstab has no `/misc` entry. A
RAM-only boot-message/fstab workaround now reaches TWRP through normal init
shutdown, with the recovery partition hash unchanged. A device-gated init source
patch is prepared for future builds and still needs compilation/boot testing.
See `RECOVERY_REBOOT_FIX.md`; no recovery reflash or full build was needed.

Latest tests (October 26): the user confirms normal boot, Wi-Fi and speaker
playback; ADB reports `sys.boot_completed=1`. The GPS socket update unblocked
startup. A separate Light-driver color/brightness bug left the resumed panel
dark. Its one-byte correction passes live brightness and three sleep/wake
cycles, and the user confirms power/home work. See `BACKLIGHT_WAKE_FIX.md` for
the persistent update and pending reboot test. Correcting four HD-recording
NVRAM selectors also restores microphone recording: the user confirms a moving
meter and audible voice. See `MICROPHONE_RECORDING_FIX.md` for the temporary
live test, small recovery update and remaining persistence/call tests.

The first VM build was flashed by the user and stopped at the fixed Samsung
logo. Saved Android logs exposed an old GUI shim overwriting the source-built
one, blocking composer loading. See `DISPLAY_BOOT_FIX.md` for the correction,
successful before/after loader tests and remaining normal-boot requirements.

With display v2, the Lineage animation runs. Watchdog dumps show the display
thread blocked on an unregistered/missing Light HAL. `LIGHTS_BOOT_FIX.md`
documents the service/wrapper, unused driver dependency correction, backlight
access and successful factory/RAM-installer checks. The user installed this fix;
fresh logs now pass display initialization and block in legacy GPS initialization.
`GNSS_BOOT_FIX.md` records the next correction: relocate the worker socket from
unwritable `/data/misc` into its existing GPS-owned directory. The exact-UID
socket probe and recovery install/reinstall/undo pass; the user subsequently
confirmed normal boot. Satellite positioning remains untested.

## Scope and baseline (2026-10-25)

Sources audited: device `cf62bac`, vendor `d3a6207`, kernel `a75b32e2` on
`lineage-18.1`. Development branch: `codex/lineage-18.1-hardware-fixes`.
The project contains the three component trees, not a full Android checkout.
At the initial audit, no ROM build or flash was performed. Windows checkouts
are not suitable for an Android build; the kernel also has reserved filenames
and case collisions.

### Remote build follow-up

The user subsequently authorized a paid Linux VM build. The complete pinned
LineageOS 18.1 checkout and Ubuntu 20.04 container passed `m nothing` and a full
`m -j16 bacon` build on 2026-10-25. See `BUILD_VALIDATION.md` for exact source
revisions, artifact hashes, image/OTA checks and remaining tests. Build instructions and
the APN manifest compatibility pin are in `tools/build/README.md`. The audit's
hardware observations below precede this build and remain device-test gates.

The complete source graph exposed an invalid inherited camera module name:
`android.hardware.camera.provider@2.4-impl-legacy` does not exist in this branch.
Packaging now uses `@2.4-impl`, which links the branch's `@2.4-legacy` HAL1
provider, together with the 32-bit service.

Compilation rejected the initial audio patch's broad
`AUDIO_NO_SYSTEM_DECLARATIONS` switch because it also hides required framework
enums. The revised patch uses a dedicated opt-in layout guard in `system/media`.
A 32-bit C++ probe passes for both the MTK `0xb0` mix-handle offset and unchanged
default `0xb4` offset, retaining framework stream/usage declarations in both.
Source review also confirmed that framework `DeviceHalHidl` uses the shared
conversion utility. The final patch therefore keeps that utility normal and
links a private, separately named conversion class into only the 4.0 HAL
implementation. Changing the shared utility globally would shift the mismatch
to the framework client. The targeted audio component build passed, including
the normal shared utility and HAL implementation. Binary inspection confirms
the HAL has no dependency on the normal 4.0 conversion library, and its private
conversion symbols are hidden. In the ARM mix-port conversion branch, the
framework writes the handle at `0xb4`; the private HAL conversion writes it at
`0xb0`, matching the vendor's measured read. Speaker/mic tests remain pending.

Vendor packaging now retains Android 11's `libalsautils` with its USB-audio
HAL, removing the old copy that overwrote it and lacked a required symbol.
The MTK primary HAL imports no symbols from that library. The `libion_mtk`
Soong module also now references the actual ION blob instead of accidentally
referencing `libdpframework.so`; only the ION blob exports `ion_custom_ioctl`.
The updated build graph no longer reports overwrite rules for these modules.

The bundled audio compensation library also had NVRAM IDs biased by +2
relative to `libcustom_nvram.so`. Its getter/setter defaulted to LID 53 (Wi-Fi,
512 bytes), while the expected audio compensation record is LID 51 (1260
bytes). This matches the phone's audio-thread Wi-Fi-record access failure and
filter fallback. The vendor branch corrects eight constant bytes, with pinned
input/output hashes and a reproducer. `validate_audio_nvram.py` independently
matches all seven selections to audio record names/sizes and rejects the
original blob. No live calibration bytes or permissions were changed.

A root-authorized SM-G532G was available through ADB, running Android 11/API 30,
LineageOS `18.1-20260827-UNOFFICIAL-grandppltedx`, with SELinux permissive.
Logs contain both October 18 boot entries and October 25 reproductions. A short
Bluetooth reproduction restored the previous OFF state and logging property.
A temporary calibration ownership test restored its exact original metadata;
the file's contents were unchanged. No firmware file was replaced, and the
compiled access-only probe was removed. Raw logs and calibration stay local.
The running image differed from the audited vendor baseline: it already
contained `camera.mt6735.so`, which the original `lineage-18.1` snapshot omitted.

## Implemented changes

* Preserve `force_connect_cmd=1` in **both** shipped supplicant configurations.
  The connected phone already uses it in its overlay; the upstream files did
  not. Keep the other Wi-Fi parameters, legacy HAL, and kernel driver unchanged.
* Change the Bluetooth SCO microphone profile from an output channel mask to
  `AUDIO_CHANNEL_IN_MONO`. The old mask cannot describe a capture device.
* Add `tools/validate_configs.py`: parses device XML, checks audio route endpoints
  and channel directions, and protects the Wi-Fi driver parameters.
* Limit Bluetooth's local extended-feature discovery to page 1 for this device.
  The scoped `system/bt` patch retains upstream behavior for other products.
* Give the Bluetooth HAL access to **only** its `BT_Addr` calibration file after
  NVRAM initialization. Parent directories and raw block permissions are not
  widened. The daemon's legacy root:3008 ownership is incompatible with the
  separate Android 11 bluetooth:bluetooth HAL process.
* Compile the audio 4.0 HAL implementation and its private conversion utility
  with the vendor port layout through an opt-in Soong setting. Keep the shared
  framework utility unchanged. Apply the required source patches under
  `patches/android-11/hardware/interfaces` and `system/media`.
* Create `/data/vendor/audiohal` and `audio_dump` for the audioserver-owned HAL.
* Correct the compensation library's NVRAM record IDs in the vendor branch.
  Keep audio-file permissions unchanged; the existing files already grant the
  HAL's primary `audio` group access. Never grant it Wi-Fi-record access as a
  workaround for the wrong ID.
* Package `android.hardware.camera.provider@2.4-service` for the already
  advertised hwbinder provider; remove the camera-stub flag. The vendor branch
  restores the missing camera module with pinned provenance. Its bytes match
  the installed phone's module; 33 related camera libraries already match that
  same earlier device snapshot. Existing patched libraries are preserved.
* Declare the packaged 32-bit power and memtrack passthrough HALs. Remove the
  advertised `vendor.mediatek.hardware.gnss@1.1` extension: this snapshot has
  the legacy GPS HAL behind standard GNSS 1.0, with no such extension service.
* Remove a stale power extension path that does not exist; the complete device
  power module is built from `mtk/power`. Its interactive/hint functions are
  still stubs and need separate power-management work.
* Bound the existing bring-up logcat output to a 1 MiB file plus three rotations.
* Add a standard-library ELF inventory tool. The vendor snapshot contains 425
  ELF files after restoring the camera module; inventory is not linker testing.

The kernel branch records the driver/interface audit; kernel code, defconfig,
and the working Wi-Fi driver remain unchanged.

## Measured evidence and verification limits

Bluetooth HCI capture, collected without pairing to another device:

| Command | Requested page | Completion status |
| --- | --- | --- |
| Read Local Extended Features (`0x1004`) | 0 | `0x00`, reports maximum page 2 |
| Read Local Extended Features (`0x1004`) | 1 | `0x00`, LE host bits present |
| Read Local Extended Features (`0x1004`) | 2 | `0x30`, followed by parser abort |

The page cap avoids the observed failing request and preserves the successful
LE feature page. A newly compiled stack still needs enable/pairing/profile tests.

The compiled `UidAccessProbe` ran on the phone with real UID/GID 1002. Before the
ownership adjustment, read/write access was false; afterward, both were true.
The probe uses `Os.access()` and never reads/writes calibration contents. The
metadata adjustment was reverted and the content hash was unchanged. This
verifies the DAC repair, not Bluetooth's complete initialization.

Audio binary inspection confirmed that the running process loads
`/system/lib/android.hardware.audio.common@4.0-util.so`. Its
`audioPortConfigToHal` writes the mix handle at offset `0xb4`, while the MTK
HAL reads offset `0xb0`. The latter contains the module ID (10), explaining the
observed `IOport = 10` and `routing=10`. Android 11's framework-only `flags`
field creates this four-byte shift. The source patch removes that field only
inside the HAL server and its private conversion class. The framework keeps
its normal layout and shared conversion utility. Both audio components compile
and link on the authorized VM; the changes have not been deployed.

Checks performed:

* All device XML files (21 including the build manifest) and 98 vendor XML files parse.
* Expanded audio policy passes the Android 11 audio 6.0 XSD with the matching
  standard includes. XInclude-generated `xml:base` metadata was removed only
  from the temporary validation tree. The older audio 4.0 XSD lacks Android
  11's standard assistant-stream entries and is not the full-policy schema.
* Audio route references/channel directions and both Wi-Fi parameters pass the
  configuration validator.
* The scoped platform patches apply to the pinned LineageOS 18.1
  sources and are recognized as already applied on a repeat run.
* Four patch-installer regression tests pass: read-only preflight/idempotence,
  refusal to partially apply when another component fails preflight, rollback
  on an apply failure, and rejection of misleading parent Git repositories.
* The restored camera ELF is ARM32, exports `HMI`, and matches its recorded Git
  object and SHA-256. A camera provider/component build remains necessary.
* The small Java/D8 UID-access probe was compiled with the existing SDK. The
  subsequent VM build completed the full ROM and passed package/image checks.
  No ROM was flashed; functional hardware validation remains pending.
* A read-only boot partition capture matches the configured load addresses,
  2 KiB page size, Samsung board ID and exact prebuilt DT bytes. Its legacy
  payload SHA-1 validates. `tools/verify_boot_image.py` repeats these checks;
  five tests reject corrupted/truncated payloads, wrong DTs and wrong addresses.
  A Samsung marker found later in the partition is not at the current payload
  end, so it does not establish that a fresh image needs an added trailer.

## Observed blockers and investigation

| Area | Evidence from attached device | Required validation |
| --- | --- | --- |
| Bluetooth | Repeated `parse_read_local_extended_features_response` aborts; HCI status `0x30`. `BT_Addr` access also fails with errno 13. | Feature-page handling, stable enable/disable, classic pairing, BLE, A2DP, SCO, persistent factory address. |
| Audio | Speaker playback works after the ABI/calibration corrections. Fresh mic recording opens built-in-mic PCM capture without a crash and mute state is false, but playback/level meter are silent. | Resolve capture; test earpiece/headset, microphone levels and calls; regression-test speaker playback. Calls remain untested. |
| Camera | User confirms rear/front preview and saved photos with the temporary compatibility candidate. Matching source/vendor changes are on `codex/camera-android11-compat`; see `CAMERA_ANDROID11_COMPAT.md`. | Raw-video fallback now records and plays with sound (user confirmed). Reopen produced a connection dialog despite responsive service checks. Front video later freezes with intermittent sound; MDP blit failures and a gralloc cleanup crash were captured. Resolve graphics/playback and lifecycle, then verify flash and reboot persistence before a permanent ZIP. |
| GNSS | The socket correction resolved the initialization boot gate; the user confirms normal boot and `sys.boot_completed=1`. See `GNSS_BOOT_FIX.md`. | Satellite acquisition outdoors, NMEA, time/location injection and SUPL. No satellite fix has been established. |
| USB audio | `audio.usb.default.so` cannot resolve `profile_get_highest_sample_rate`. The old overwriting library is now excluded from packaging. | Verify the built library export; test USB playback/capture. |
| Widevine | Legacy protobuf `empty_string_` symbol cannot resolve. | Check the existing v29 compatibility library mapping and encrypted playback. |
| Security | Permissive kernel cmdline, ignored neverallows, insecure ADB defaults. | Dedicated SELinux bring-up before calling this a production-ready ROM. |
| Power/memtrack | Packaged passthrough implementations lacked declarations; device power hints/interactive callbacks are empty. | Verify discovery, display sleep, suspend current, wake reliability, thermal limits and memory accounting. |
| Modem/RIL | Both root and vendor init files declare CCCI daemons with different names; only the unprefixed services are running on the sampled phone. | Audit duplicate startup before changing it; test both SIMs, calls/SMS/data and in-call audio. No modem behavior was changed here. |
| Sensors | Sensor HAL is registered; the tree advertises gyroscope/step features without a capability inventory from stock. | Match feature declarations to actual sensor enumeration and test rotation/proximity. Registration alone is not validation. |

Do not enable `CONFIG_BT` merely because it is disabled: this MTK stack uses
`/dev/stpbt` in userspace, and `CONFIG_MTK_COMBO_BT=y` is already selected.
Likewise, `CONFIG_MEDIA_CAMERA_SUPPORT` is not the MTK camera switch;
`CONFIG_MTK_IMGSENSOR=y` and the imx219/s5k5e3yx drivers are already selected.

The audio service name `android.hardware.audio@2.0-service` is an Android 11
phony alias for `android.hardware.audio.service`; that service probes 6.0, 5.0,
4.0 and 2.0 implementations. Renaming it does not fix the observed audio issue.
`maxActiveCount=0` means unlimited, not disabled capture.

## Sources consulted

* [LineageOS 18.1 audio service](https://github.com/LineageOS/android_hardware_interfaces/blob/203e87a39c04f30bc1f09f6c2306b701d6b97fe0/audio/common/all-versions/default/service/service.cpp)
* [LineageOS 18.1 Bluetooth parser](https://github.com/LineageOS/android_system_bt/blob/bcca9a572f1cc539ba21ebe940c3642ce8707d1a/hci/src/hci_packet_parser.cc).
* [Android 11 audio port layout](https://github.com/LineageOS/android_system_media/blob/lineage-18.1/audio/include/system/audio.h)
  and [header build variants](https://github.com/LineageOS/android_system_media/blob/lineage-18.1/audio/Android.bp).
* [Sony Xperia L1 MT6737T tree](https://github.com/SonyMTKDev/android_device_sony_pine-deprecated/tree/a0fc73df002090629d12832ce3c8aae8980e4bf1).
* [Motorola MT6737 common tree](https://github.com/Motorola-MT6737/android_device_motorola_mt6737-common/tree/8622aa4d1d42e330edb50c49025cb4db637bdd90).
* [LineageOS MT6735 common tree](https://github.com/LineageOS/android_device_cyanogen_mt6735-common/tree/0033d5b1d2b2065adfb4a0b116db1c77e17fa302).

Older device trees establish MTK interfaces and service requirements; they are
not evidence that their blobs or framework patches are Android 11 compatible.
The existing `patches/` directory includes old framework paths and must not be
blindly applied to an Android 11 checkout.

## Lightweight validation

From an Android/project root:

```sh
python device/samsung/grandppltedx/tools/validate_configs.py
python device/samsung/grandppltedx/tools/audit_vendor.py vendor/samsung/grandppltedx/proprietary/vendor
git -C device/samsung/grandppltedx diff --check
```

On a Linux Android 11 checkout, first preflight/apply the scoped platform patches
using `tools/apply_android11_patches.py --check` and then `--apply`. Other legacy
port patches still need their own compatibility review. Start with targeted
builds rather than a full ROM:

```sh
m -j2 libbluetooth android.hardware.audio.common@4.0-util \
  android.hardware.audio@4.0-impl android.hardware.camera.provider@2.4-service
```

Install matching audio conversion/core components together; mixing layouts can
corrupt route data. Init and vendor changes need a coherent image/recovery
deployment and should not be approximated by overwriting live system libraries.

Test Wi-Fi association/reconnection and suspend resume first, including the
ADB transport if it uses Wi-Fi. Then test one subsystem at a time with before/
after logs. Bluetooth requires repeated on/off, classic and BLE pairing, A2DP,
SCO and factory address persistence. Audio requires speaker/earpiece/wired
headset playback, mic capture and both-SIM calls. Camera requires both sensors,
preview/still/video/flash. GNSS requires an outdoor cold/warm fix and SUPL tests.
Retain a known-working boot/system image and recovery path before deployment.
Do not publish raw bugreports, location dumps, NVRAM or EFS data.
