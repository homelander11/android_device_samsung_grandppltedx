# Microphone recording calibration selectors (October 26, 2026)

The user confirmed the built-in microphone worked on Samsung stock firmware.
On this Android 11 ROM, Recorder started but showed no meter and played silence.
After loading the correction below, the user made a fresh foreground recording
and confirmed **the meter moves and their voice is audible**. Persistence after
recovery installation/reboot, calls and other microphone routes still need testing.

## Cause and scope

The bundled `libaudiocustparam_vendor.so` selects the wrong NVRAM records for
HD recording, with the same +2 selector bias previously found in the filter
library. The bundled `libcustom_nvram.so` table establishes the correct IDs:

| Consumer | Old selection | Correct selection |
| --- | --- | --- |
| HD recording parameters, getter and setter | 65: DC calibration, 12 bytes | 63: HD recording parameters, 4054 bytes |
| HD recording scene table, getter and setter | 66: vibration-speaker filter, 1260 bytes | 64: HD recording scene table, 135 bytes |

The old getters trust the selected record's size. They can read only 12 bytes
into a 4054-byte parameter structure and read 1260 bytes into the much smaller
135-byte scene structure. The primary HAL preloads these through its parameter
client and uses the results to select and configure recording processing.
Live logs with the original library selected voice-recognition mode 125; with
the corrected library the same route selects mode 0. An unsilenced 3-second
voice-recognition test changed from an almost constant value of 14 to varying
audio (over 47,000 changing/nonzero samples of 48,000, across repeated tests).

Change only four ARM `mov r1, #LID` immediate bytes, at file offsets 13440,
13948, 14408 and 14916. Both getters and paired setters are corrected. The
36,292-byte size, all remaining code, ELF headers, symbols and dependencies
are preserved. No NVRAM/calibration file is replaced, erased or written. Other
audio selectors have not been changed by this fix. Wi-Fi, speaker routing,
microphone coupling, boot images, GPS and Light drivers are untouched.

* Original SHA-256: `d4f20563caa3d8a8c1eaab2ea0bf853baf1056ab8f03306793c0210867dc3690`
* Corrected SHA-256: `f3fb7b40768fe76339c02b198474a2f6dffb262350fbbba20995747baec5fe8e`

Vendor `recording-lid-provenance.json` records the pinned source revision,
original Git object, hashes, instructions and paired NVRAM table. Reproduce
with `tools/fix_recording_lids.py LIBRARY --apply`; repeated application is
idempotent and unknown binaries are rejected before any write. This requires
the matching vendor snapshot, not a library borrowed from another device.

## Validation and diagnostic limits

`tools/validate_recording_nvram.py VENDOR_DIRECTORY` checks each getter/setter
instruction against the actual bundled table's record names and payload sizes.
The build runner checks source before compilation and installed vendor output
after a full ROM build. Four regression tests reject the original mismatch,
a regressed setter and unknown binaries, and verify the exact byte scope and
idempotence. A full ROM build was not needed; the paid VPS stayed off.

A temporary bind over the library and audio-HAL restart loaded the corrected
library. The bind was detached afterward; the running process keeps the tested
mapping until it exits. Installed firmware remains the original until the ZIP
is installed. The primary HAL and microphone mode properties are original;
experimental recording-processing bypasses were removed. User confirmation
comes from their normal foreground Recorder app, not those bypasses.

Root `app_process` MIC-source probes can return all zeros because Android marks
the background recording as `silenced:true`. Such a result does **not** prove
a HAL failure. `MicLevelProbe.java` now reports `SILENCED` using the recording
configuration, labels silenced/unknown captures inconclusive, and retains only
aggregate statistics. Unsilenced voice-recognition capture and the user's
foreground recording are the meaningful microphone checks. No recordings or
device calibration are included in the repositories.

The native recovery updater passed install, reinstall, exact-original undo,
mode 0644/root ownership/vendor_file labeling, and unknown-library rejection
before replacement on a 16 MiB ext4 RAM fixture. The test substitutes only the
verified RAM loop device, `/data/local/tmp` for recovery's `/tmp`, and Android's
`/system/bin/sh` for recovery's `/sbin/sh`. It does not flash a firmware partition
or establish that the unchanged ZIP has already run in TWRP.

## Persistent recovery update

`tools/build/create_recording_fix.py BASE_ROM PATCHED_LIBRARY ORIGINAL_LIBRARY
--out-dir DIR` generates `grandppltedx-20261026-recording-fix.zip` and its undo.
It pins the 20261025 ROM/API 30, earlier display/Light/GPS fixes, primary audio
HAL, NVRAM table and old/new recording library hashes. Only the recording
parameter library is replaced. It accepts either the dependency-corrected or
brightness-corrected Light driver, so it can be installed before or after the
separate backlight update. It does not install that backlight correction itself.

In TWRP, leave System unmounted, disable ZIP signature verification for these
local unsigned development packages, install the recording fix and the separate
backlight fix, then reboot System without wiping. Each undo restores only its
own previous library. Do not flash an undo unless reverting that change.

After reboot, check normal boot, a fresh foreground recording and playback,
power/home wake and Wi-Fi/speaker operation. Then test call uplink/downlink,
speakerphone, camcorder audio, wired-headset microphone and Bluetooth SCO when
available. Calls have not been tested; GPS positioning, Bluetooth pairing and
camera operation remain separate open items.

Reference for the legacy preload/scene-processing flow:
[MediaTek AudioSpeechEnhanceInfo source](https://github.com/nofearnohappy/vendor_AOSP/blob/master/mediatek/proprietary/hardware/audio/common/V3/aud_drv/AudioSpeechEnhanceInfo.cpp).
The binary instructions and table in this device's pinned snapshot determine
the actual correction; the reference is not a replacement HAL.
