# Camera video colour update (2026-10-27)

Install after the combined camera/audio update. This changes only the camera
helper, `vendor/lib/libcamcx.so`, to correct YV12/I420 chroma ordering in raw
video. It retains the existing camera/audio, microphone and wake fixes.
The corresponding source change is in the device tree for future ROM builds.
No full ROM build or VPS use was required.

| File | SHA-256 |
| --- | --- |
| `grandppltedx-20261027-camera-colour-fix.zip` | `6fb74b0cba81ced171594b821a197e9bc61b67ecd7fb99ae8adce2d6c0875c6a` |
| `grandppltedx-20261027-camera-colour-undo.zip` | `08f56dc3e02c8803fbc7c3ba94a0cf97fa74e97f5288dfe6a51801d76280f109` |

In TWRP, keep System unmounted and ZIP signature verification off. Install only
the **camera-colour-fix** ZIP, then reboot System without wiping. Keep its undo
ZIP accessible; it restores the previous helper while retaining the combined
camera/audio update. To revert everything, first install colour-undo, then the
earlier combined camera-audio-undo. The older full undo alone rejects the new
helper, as designed. If ordinary recovery reboot is refused, use the existing
RAM helper described in `RECOVERY_REBOOT_FIX.md`.

## Verification and remaining tests

Temporary testing verifies the mapped helper and logs conversion for camera
IDs 0 and 1. The user confirms correct red, video/sound from both cameras,
normal photo colours and a lower-resolution rear recording. Device-verified
buffers are 1280x720 and 320x240; other profiles need physical testing.
The isolated ARM test checks raw fallback without a second disable call,
copied descriptors, heap/index bounds, unchanged Y and callback arguments,
duplicates, wrong-camera/non-video/unknown-heap passthrough.

The real ROM updater and unchanged payloads pass install, reinstall and exact
undo on a disposable 64 MiB ext4 RAM image. Every other seeded file remains
unchanged, and target ownership/mode/SELinux label pass. Unknown helper,
unknown audio dependency and helper symlinks are rejected before replacement.
Only block/mount/verifier/shell paths differ in that fixture. No phone partition
is written by the test.

Permanent colour installation/reboot, longer recordings, other profiles,
repeated lifecycle/performance and normal Soong compilation remain pending.
After reboot, test both cameras' video colours/sound, photos and reopening;
recheck Recorder microphone, Wi-Fi and power/home wake. The update changes no
calibration, codec/display settings, boot/recovery or other vendor library.

Reproduce the packages with `tools/build/create_camera_colour_fix.py` using
the pinned ROM ZIP, previous helper and tested corrected helper. All hashes,
ARM exports, dependencies and `DF_1_GLOBAL` are verified. The full combined
package generator also accepts the pinned previous helper when packaging this
corrected version. See `VIDEO_COLOUR_INVESTIGATION.md` for diagnosis.
