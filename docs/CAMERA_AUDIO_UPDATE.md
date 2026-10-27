# Combined system-only camera/audio update (2026-10-27)

This development update targets the diagnosed
`18.1-20261025-UNOFFICIAL-grandppltedx` ROM with its existing display,
Light/backlight and microphone fixes. It packages the camera compatibility
changes and the exact primary audio HAL deep-buffer PCM-name correction.
Future coherent ROM builds from the matching device/vendor branch include
these changes; this ZIP updates the already-installed image.

The user confirms both cameras' preview/photos, fresh rear/front video with
moving playback and sound, and Camera close/reopen in the temporary combined
trial. Default codecs and normal hardware composition are retained. These are
live-test results, not yet post-reboot verification of the permanent package.

## Files and installation

| File | SHA-256 |
| --- | --- |
| `grandppltedx-20261027-camera-audio-fix.zip` | `d72551da81889c322b4df61bd10b8aba9b709061a03681f8bf4783ebee9b05bc` |
| `grandppltedx-20261027-camera-audio-undo.zip` | `250b23b007111dc6ce44d94ac9a2744a6a944f149f50872b8bea19e2a9f7c066` |

Keep the undo ZIP accessible in recovery. In TWRP, unmount System in Mount,
install only the camera-audio **fix** ZIP, then reboot System. Do not wipe or
format anything. The development packages are unsigned, so TWRP ZIP signature
verification must be off. Undo is for reverting this update; do not install it
immediately after the fix. The installer rejects unknown inputs before writes.

After reboot, test both cameras' preview, photo saving, short videos with speech,
playback and close/reopen. Recheck Recorder microphone, Wi-Fi and power/home wake.
Report any installation error before attempting a different package.

## Installer verification and limits

The unchanged ROM updater binary and payloads pass install, reinstall, exact
original camera/audio undo, root ownership, file mode 0644 and SELinux labels
on a disposable 64 MiB ext4 RAM image. Unknown camera-library input, unknown
audio-HAL input and a symlink to the correct original HAL are rejected before
any payload write. Only block/mount/verifier/shell paths differ in that fixture.
The actual system partition is not used by this test.

Production-name private library loading passes in isolation. Actual TWRP
installation, a full camera session using those production names, reboot
persistence, long playback, flash and extended lifecycle/performance remain
pending. Calls, headphones and Bluetooth audio are unverified. The separate
gralloc cleanup issue remains; its candidate guard, GPU-composition experiments
and codec-selection experiments are not included. GPS work stays paused.

The package replaces ten camera libraries plus the primary HAL's one 20-byte
PCM-name slot, and adds four private runtimes, an ICU license and node-ownership
init commands. Microphone selectors, calibration, Wi-Fi, global Skia/ICU and
boot/recovery are preserved. No full ROM build or VPS use was required.

Generate with `tools/build/create_camera_fix.py` using the pinned ROM ZIP,
paired vendor library directory, pinned original camera directory and tested
32-bit `libcamcx` helper. The tool verifies every input and emits both ZIPs and
`CAMERA-FIX-SHA256SUMS`. See `CAMERA_ANDROID11_COMPAT.md` and
`AUDIO_DEEP_BUFFER_FIX.md` for implementation, provenance and test commands.
