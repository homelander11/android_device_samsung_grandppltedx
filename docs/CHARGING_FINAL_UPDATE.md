# Charging fixes and diagnostic removal, 2026-10-28

The user verifies the charging animation and percentage, repeated short-Power
wake and long-Power Android boot. The user also confirms that unplugging USB
stops charging mode. The display sleeping between short presses is expected.
Normal Android boot and its unchanged brightness setting pass ADB checks.

The installed fixes address three independent gaps:

1. Start the existing Android 11 charger instead of the incompatible Samsung
   LPM, and provide a percentage description/font. See `OFFLINE_CHARGING.md`.
2. Remove the legacy `/system` remount that creates a SAR path loop. The native
   log and private-namespace probe establish that failure; see
   `CHARGER_SAR_FIX.md`.
3. Initialize the MTK brightness cache once during `on charger`. Real driver
   tests and physical short-press tests pass; see `CHARGER_BACKLIGHT_WAKE.md`.

## Future ROM builds

These changes are now included in the device tree's product configuration.
`WITH_LINEAGE_CHARGER := false` is set **before** inheriting Lineage common
configuration. Lineage 18.1's `common_mobile.mk` uses this supported switch to
omit its default animation description. The device selects
`grandppltedx_charger_animation` instead, installing one description at the
normal product path and explicitly requiring Lineage's unchanged density
selected battery images. This device selects hdpi. The font and its unchanged
OFL/license README are copied alongside the product images.

The active init override starts the tested Android 11 service, the root init
contains the SAR correction, and the charging-only brightness init is copied
by the existing init-directory rule. Active service/animation settings match
the tested trial exactly after comments are excluded. The font/license bytes
match exactly. Historical trial files under `tools/charger/candidate` stay
unchanged so the old recovery packages remain reproducible. Neither logger is
included in product packaging.

This avoids competing animation install rules and needs no new platform patch.
Checks use the published Lineage 18.1
[resource switch](https://github.com/LineageOS/android_vendor_lineage/blob/lineage-18.1/config/common_mobile.mk)
(Git blob `1f1c2414f5468bf989c7eb70d12ac1ac9dfb215d`) and
[image modules](https://github.com/LineageOS/android_vendor_lineage/blob/lineage-18.1/charger/Android.mk)
(`2fce7c43937cf244ea035d28aa7a1dee6adbce38`). Static configuration, file paths,
resource equivalence and destination checks pass. The official hdpi battery
scale/failure Git blobs (`92cd5b6e5a971e6cba510e729027d92d792df3ee` and
`572d8eff563e722e98c519e430910408a17080e0`) match the actual tested ROM
images exactly. **The Android build graph
and a fresh ROM build have not been run.** No full build or VPS was used.

A ROM built from this device tree includes the fixes; it does not require
reapplying the current development fix ZIPs. A newly built image still needs
normal hardware and charging regression tests.

## Remove the temporary diagnostics

Two verified files are in Download for one TWRP session:

| File | Purpose | SHA-256 |
| --- | --- | --- |
| `grandppltedx-20261028-charging-debug-cleanup.zip` | Remove only the known diagnostic init/script while retaining the current charging fixes | `6b6e1c6472a814eaa9fcb66b6e33df31e60c3766b1aa696b853ac52ac0cef46f` |
| `grandppltedx-20261028-early-charger-boot-undo.zip` | Restore the exact original full 16 MiB boot partition | `bee545efdbc690f4760d21b7a7cf331cd9d09ebcafa346866d9d7732efcaa9b7` |

The original init/shell diagnostic undo expects the earlier, uncorrected SAR
init file. Use the new cleanup package above with the current fixes instead.
It validates the modern UI, corrected SAR init, wake init and both diagnostic
targets before removing anything. Unknown or symlink targets are refused.
Its real-ROM-updater RAM ext4 test passes removal, repeat removal, low battery,
unknown/symlink second target and unknown prerequisite rejection. All fifteen
non-diagnostic baseline files are preserved, and the real boot stays unchanged.

The boot undo is the unchanged, previously RAM-block-tested package. It accepts
only the exact original/diagnostic boot hash and requires at least 40% battery.
The original full boot SHA-256 is
`2fdd5db2a3e047ce8710771a668e0290ee81ae905fe94020d832f2b14a5849c8`.
Kernel, DT and init are restored exactly; vendor/product fixes remain installed.

**Removal and final charging regression pass.** ADB verifies the exact full
original boot hash, absence of both logger files including symlinks, ten retained
charging/hardware hashes and unchanged Android brightness5. The user then
repeats the animation/percentage check, two short-Power wake cycles and
long-Power Android boot and reports that everything worked. After that cycle,
ADB confirms `sys.boot_completed=1`, the original boot and permanent SAR/wake
init hashes, brightness5 and battery97%.

Cleanup used TWRP with System unmounted and signature verification off, installing
the cleanup ZIP followed by the early-boot undo and rebooting without wiping.
The two inactive cache log files were copied privately, checked against their
on-phone SHA-256 values, and removed only after exact-hash verification. No raw
log, recording, calibration or partition capture is committed. The original
raw boot backup and undo packages remain available in Download.

Low-battery startup, measured off-mode current/charge rate, thermal behavior
and extended suspend testing remain unverified. Charge limits, calibration,
EFS and battery-driver settings were not changed.
