# Powered-off charging investigation

**2026-10-28 update:** the installed SAR/UI/backlight fixes now pass the user's
animation/percentage, repeated short-press wake, long-press Android boot and
unplug checks. Source packaging is active for future builds; full build
validation has not been run. Diagnostic removal is prepared, with a final
charging regression still required afterward. See
[CHARGING_FINAL_UPDATE.md](CHARGING_FINAL_UPDATE.md) for the current state.
The following sections retain the earlier investigation and trial results.

The user reports a static battery/lightning icon for more than five minutes
after the battery depleted. Rotation worked after the sensor update before
shutdown. The initial checks were performed locally with the phone off.
An online read-only follow-up confirms the installed files and dependency
failure. The first UI trial still failed; measured charging rate remains pending.

## Confirmed defects in the installed ROM's source image

The pinned `lineage-18.1-20261025-UNOFFICIAL-grandppltedx.zip` has SHA-256
`1a7670ccb03e1b22cf1a646b74a18d678c8e33fd71525bee1c86b5fb3691f445`.
The full OTA's new-block stream was read as ext4 metadata and selected files,
without writing a full system image. The retained metadata is about 3.9 MB.
This checks the actual packaged filesystem, rather than assuming every library
outside the proprietary tree is missing.

* `vendor.lpm` is the only charging-UI service. It starts `/vendor/bin/lpm`
  in `class sec-charger` and is marked `critical`.
* That ARM32 executable has a mandatory `DT_NEEDED` entry for
  `libpixelflinger.so`. No such library is present anywhere in the ROM's
  ext4 directory entries. The dynamic linker cannot load this executable
  from this filesystem as packaged. `libsuspend.so` is also absent. On the
  connected phone, the linker's dependency-list mode fails first on
  `libsuspend.so`; it succeeds for `/system/bin/charger`. This check does not
  execute either charging frontend. The later native log identifies a second
  startup failure: the charger-mode SAR remount described above.
* The GUI-enabled Android 11 `/system/bin/charger` is present, together with
  the Lineage battery animation. No service in the extracted system/vendor
  init files launches this executable. The root init `on charger` action
  starts `class charger`, which has no member service in this image.
* The product animation has 22 frames, but no `percent_display` directive.
  There is no PNG font in the ROM. Android 11 draws percentage text only
  when its configured font loads; the old `BOARD_CHARGER_SHOW_PERCENTAGE`
  setting does not supply that missing resource/configuration.

The absent dependency is a concrete startup defect. It plausibly explains
why the bootloader's static icon never gives way to a userspace charging UI;
that exact screen transition still needs observing. The icon does not prove
that the battery is or is not charging. Battery status, voltage/capacity change
and cable/charger behavior require device checks.

Some old LPM animation names also have no corresponding vendor asset, but
their optional/fatal behavior has not been established. Adding a guessed
`libpixelflinger` module or enabling generic MTK KPOC is not a validated fix.
This kernel uses Samsung's S2MU005 charging/fuel-gauge path. No charging
current, temperature threshold, calibration or kernel setting was changed.

## Prepared, inactive candidate

`tools/charger/candidate/` contains an Android 11 service override, an
animation description with percentage text, and an unchanged upstream minui
font with its SIL Open Font License and provenance. Nothing in `device.mk`,
`BoardConfig.mk` or the init-copy directory activates these files. The
reversible `tools/build/create_charger_fix.py` packages a fix and undo for a
controlled recovery trial. The first UI trial is installed and boots normally,
but it did not resolve the static powered-off screen.

The proposed override replaces `vendor.lpm` with the existing
`/system/bin/charger`. It uses `class charger`, so the normal init transition
out of charging mode stops it. It has no `critical` flag and no trigger that
starts it during normal Android boot. The old `class_start sec-charger`
action then has no LPM member to start. Before activation, verify that the
override is parsed after the original service on the actual device.

The existing 22-frame image and failure image are retained. The new description
adds an explicit font and places the percentage below the battery on the native
540 x 960 display. The font is 1728 x 64, grayscale, giving the 96 x 2 glyph
layout expected by minui. This is a static resource/layout check; framebuffer
initialization, brightness and real screen orientation remain untested.

The Android 11 charger has a built-in default health implementation when a
2.1 health service is unavailable. The candidate therefore does not start the
entire HAL class during charging. Actual fallback discovery of Samsung's battery
and charger-online sysfs properties must be verified. The root init already
starts the binder service managers during `on init`.

### Intended deployment paths, after testing

| Candidate file | Intended destination |
| --- | --- |
| `zz-grandppltedx-charger.rc` | `/vendor/etc/init/zz-grandppltedx-charger.rc` |
| `animation.txt` | `/product/etc/res/values/charger/animation.txt` |
| `font_charger_18x32.png` | `/product/etc/res/images/charger/font_charger_18x32.png` |

The animation destination is currently supplied by a Lineage resource module.
Future build integration must replace that module's configuration deliberately;
do not introduce two build rules for the same destination. Keep a reversible
backup of the original animation and remove only the added override/font on
undo. Do not overwrite boot or recovery for a service/resource trial.

## Validation and next device checks

Local checks confirm the mandatory missing dependency, installed GUI executable,
init service gap, unchanged 22-frame timing/ranges and valid upstream grayscale
font/glyph dimensions. Candidate provenance and hashes are recorded in
`tools/charger/investigation.json`. No full ROM build or VPS was used.
The files are now installed, but the charging UI is not a verified fix.

On 2026-10-27 reconnection, Android and sysfs both report charging at 2%, 3631 mV,
34.4 degrees C. This establishes the current Android status, not that capacity
is rising or powered-off charging works. The charging executable, old LPM,
both init files, animation and images match their pinned hashes. The sensor
override also matches; the sensor service has input group 1004 and open
accelerometer/proximity descriptors. The recovery installer refuses battery
capacity below 15% before mounting/writing the system partition. Keep the
charger attached and allow adequate charge before a recovery trial.

On 2026-10-28, the phone reports 100% and Full. The previous aborted RAM test
has cleared after reboot. The corrected installer passes with the actual ROM
updater on a fresh, disposable 64 MiB RAM ext4 filesystem: install, reinstall,
undo, repeat-undo, low-battery rejection, unknown-target rejection and symlink
rejection. Exact target contents, ownership/modes/labels and unrelated baseline
files are checked. The fixture substitutes only block/mount/interpreter,
verifier and battery-text paths. It never writes the phone's system partition.
The final archives contain the same tested installer/payload bytes plus the
unchanged upstream font license and README. Their CRCs and on-phone hashes pass.

| Development package in Download | SHA-256 |
| --- | --- |
| `grandppltedx-20261027-charging-ui-fix.zip` | `40e2cdaaf719700efeba3d42d9e20f2c5fd2df26e4c3029c1ce71b5df07d4880` |
| `grandppltedx-20261027-charging-ui-undo.zip` | `3fa21040d5714204a98f0a3c22f86ef701c18569881550f06888a00f8973f5cc` |

After the user confirmed recovery readiness, the verified RAM-only helper
requested recovery. The user then confirmed installation and normal boot.
ADB verifies all three installed SHA-256 values, uid/gid 0, mode 0644 and
the intended SELinux labels. `sys.boot_completed=1`; no userspace charging
frontend runs during normal boot. The user subsequently powered off with the
charger attached and still observed the static lightning icon. ADB is absent
in that mode. The first candidate therefore **fails the physical UI test**;
the later native diagnostic establishes that the legacy mount breaks its paths.
The user was asked to boot Android so prior-boot logs can be collected. Keep
undo available. Full-build activation remains deferred.

The user reports that Power cannot boot from that static screen and unplugging
does not shut it down. Booting requires removing USB and the battery, reinserting
the battery and powering on. This indicates a broader startup/event-handling
failure, rather than proving that only the drawing resources are wrong. After
that cold start, `/proc/last_kmsg` contains only a 46-byte RAM-console header;
pstore is empty. No failure cause can be extracted from those logs.

Two standalone, six-second-bounded health lookup probes run in Android without
starting a UI or modifying properties/sysfs/services. Health 2.0 returns a
service and 2.1 returns null promptly. Thus a health-2.1 lookup hang was not
reproduced in Android; the charging-mode service state still needs capturing.

## Charging-only diagnostic trial

`tools/build/create_charger_debug.py` packages only
`zzzz-grandppltedx-charger-debug.rc` and `j2prime-charger-debug.sh`, plus undo.
It requires the exact installed UI trial and its original dependencies. Both
new targets are checked before either is changed. No full-build rule activates
the diagnostics. Their canonical payload hashes and results are recorded in
`tools/charger/diagnostic/manifest.json`.

The diagnostic starts once during init. On normal boots, it reads the boot mode
and Samsung LPM flag and exits immediately; this no-op path passes an actual
on-device test. In charging mode, it reuses debug USB only when the existing
build already has `ro.debuggable=1` and `ro.adb.secure=0`; it does not change
authentication or persistent USB properties. It starts logd, mounts the existing
cache filesystem if necessary, and saves bounded snapshots of boot/service
properties, battery readings, process state, charger wait stacks and logs to
`/cache/j2prime-charger-debug/latest.txt` (directory 0700, file 0600). Snapshots
are synced so a battery removal has a better chance of retaining the evidence.
These logs are private and must not be committed. No charge-control or
calibration node is written, and the script does not request reboot/shutdown.

The actual ROM updater passes a fresh 64 MiB RAM ext4 fixture: install,
reinstall, undo, repeat-undo, low-battery/unknown-file/symlink rejection; exact
new hashes and metadata are checked and all 14 baseline files stay unchanged.
Both diagnostic ZIP hashes are verified after copying to Download.

| Diagnostic package | SHA-256 |
| --- | --- |
| `grandppltedx-20261028-charging-debug.zip` | `cabfb6eb601dc891a5071c6c8f5f177f042b01b7720ce85f090819550b936ab2` |
| `grandppltedx-20261028-charging-debug-undo.zip` | `a324b5fd5dfda5e0aea50e677d2ef39bfaee1142477b45d2ed3364ac0389541f` |

After installing the diagnostic and confirming normal boot, perform one bounded
charging-screen test with USB connected. Collect live ADB state if it appears;
otherwise allow about one minute before returning to Android and collecting
the cache log. A missing cache log does not itself establish why init did not
reach the diagnostic. Remove the diagnostic after the investigation; retain
the UI undo until the powered-off charging behavior is verified.

The user installed this diagnostic and booted. ADB confirms both exact hashes,
mode 0644 and intended labels; the one-shot service is stopped during normal
Android. A normal-mode explicit start exits successfully without writes. The
subsequent charging test still shows the static icon; ADB never appears and
the cache log/directory is absent after the required battery removal. Thus this
trial alone was inconclusive about the failed boot stage. The subsequently
installed static ramdisk diagnostic and exact boot undo are documented in
`CHARGER_EARLY_BOOT.md`. Its charging log now confirms init was reached and
the obsolete remount caused the path loop; this also explains shell exit 127.

Once the phone has enough charge and device testing resumes:

1. Read Android's battery status/capacity/voltage/temperature and existing
   charging-mode logs where available. Verify the sensor override's installed
   hash, effective input group and physical rotation after this reboot.
2. Check the exact installed charger binary, resources, boot mode, init import
   order, framebuffer/input nodes and linker dependencies against this evidence.
   Confirm the known recovery/undo path before installing a candidate.
3. Test a reversible service/resource candidate with sufficient battery reserve.
   Check animation, correct percentage, display blank/wake, power-button normal
   boot and clean normal-boot service state. Check cable removal shutdown and
   reconnect behavior, plus capacity/voltage rise with the charger attached.
4. Recheck Wi-Fi association, power/home wake, microphone, camera photos/video
   with sound/colour and rotation. Keep charging safety limits and calibration
   unchanged. Only promote the candidate after these results are recorded.

## Primary sources

* [Android 11 charger build and GUI/recovery variants](https://github.com/LineageOS/android_system_core/blob/lineage-18.1/healthd/Android.bp)
* [Health-service fallback](https://github.com/LineageOS/android_system_core/blob/lineage-18.1/healthd/charger_utils.cpp)
* [Animation parser and percentage font field](https://github.com/LineageOS/android_system_core/blob/lineage-18.1/healthd/AnimationParser.cpp)
* [Percentage drawing](https://github.com/LineageOS/android_system_core/blob/lineage-18.1/healthd/healthd_draw.cpp)
* [Minui font layout](https://github.com/LineageOS/android_bootable_recovery/blob/lineage-18.1/minui/graphics.cpp)
* [Unchanged upstream font, license and font README](https://github.com/LineageOS/android_bootable_recovery/tree/lineage-18.1/fonts)
* [Android init override and service-class behavior](https://github.com/LineageOS/android_system_core/blob/lineage-18.1/init/README.md)
