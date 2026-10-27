# Camera preview/session and autofocus update (2026-10-27)

This helper update targets black preview on camera mode/app changes and the
legacy autofocus lock cycle when returning from video playback. It retains the
installed photo/video, chroma-order and memory-cookie corrections. It requires
the combined camera/audio update, video-colour update and graphics guard already
installed on the pinned 2026-10-25 LineageOS 18.1 image. Only
`vendor/lib/libcamcx.so` is replaced. No full ROM build or VPS is needed.

The session-only candidate passes the user's preview/app-switching tests and
built-in recording/playback with correct colour and sound. Its third-party
recording works, but returning from playback deadlocks in the AF-move setter.
The combined autofocus helper passes isolated native tests and a read-only live
vendor dispatch check. The user confirms two successful third-party short-video
record/playback/return cycles. The provider, media service and composer retain
their PIDs, with no health timeouts. The user also confirms rear/front switching,
photos, recording/playback, colour and sound in the built-in Camera with the
combined helper. Exact rollback to the installed colour helper is verified,
including its actual mapped system inode; Wi-Fi/audio/mic/wake versions remain
unchanged.

**Permanent installation and reboot verification pass.** The user installed the
ZIP in TWRP and booted Android. ADB confirms the exact corrected helper hash,
its mapping from the installed system inode without a helper bind mount, the
live corrected AF setter dispatch, and 0644 root:root vendor_file metadata.
Graphics/audio/microphone/wake hashes and Wi-Fi's `force_connect_cmd=1` remain
correct. A post-reboot user camera regression check is still pending.
See `THIRD_PARTY_CAMERA.md` for evidence and
`tools/camera/preview-session.json` for exact hashes and ABI constraints.

The fix and exact helper undo are created by
`tools/build/create_camera_session_fix.py`. Both verify the pinned ROM version,
26 dependencies including the installed graphics guard, and the old/new helper
hash before writing. ARM exports/dependencies and DF_1_GLOBAL are checked during
packaging. The real ROM updater passes install/reinstall/undo on a disposable
64 MiB ext4 RAM image: all other 29 files are unchanged, uid/gid0, mode0644 and
vendor_file label pass, and unknown helper/dependency or symlink inputs are
rejected before replacement. Only block/mount/verifier/shell paths differ in the
fixture; it writes no phone partition.

| File | SHA-256 |
| --- | --- |
| `grandppltedx-20261027-camera-session-fix.zip` | `07e17700576de50168ae79db2078e9f95d2970f85c6d8e5325d66333bada9685` |
| `grandppltedx-20261027-camera-session-undo.zip` | `49cb9d6d177db1d914e47e4ae1a5da5c7011da75d97139d2b073d4a81ea9fd44` |

Keep System unmounted in TWRP, leave ZIP signature verification off, install
only the session-fix ZIP and reboot without
wiping. Keep the undo available; it restores the installed colour helper and
retains all audio/display fixes. For a complete rollback, use session undo first,
then graphics-guard undo, colour undo, and finally combined camera/audio undo.
The earlier guard/colour installers intentionally reject a newer unknown helper.
If recovery reboot is refused, use `RECOVERY_REBOOT_FIX.md`'s existing RAM helper.

After installation, verify both cameras' preview/photos, short recordings,
playback and return from Gallery, repeated app/mode switching, microphone,
Wi-Fi and power/home wake. Long recordings, other profiles, flash, other camera
apps and normal Soong compilation remain pending.
