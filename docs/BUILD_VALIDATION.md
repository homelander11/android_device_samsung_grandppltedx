# LineageOS 18.1 build validation — 2026-10-25

Latest test status (October 26): normal boot, Wi-Fi and speaker playback are
confirmed. `sys.boot_completed=1` after the GPS correction. The separately
tested `BACKLIGHT_WAKE_FIX.md` update resolves power/home wake in live tests
and the user's confirmation; persistent install/reboot remains pending.
Microphone recording is silent, and phone calls have not been tested.

Latest follow-up (October 26): display v2 and the Light fix now pass display
startup. The next watchdog blocks in GNSS initialization. `GNSS_BOOT_FIX.md`
documents a 14-byte vendor socket-path correction, verified GPS-UID permission
probe and RAM recovery install/reinstall/undo checks. No new full build or VPS
use was needed; the original ROM still requires all three follow-up updates.
Normal boot and satellite positioning remain unverified.

**Device follow-up:** the user subsequently flashed this ZIP; it stops at the
fixed Samsung logo. Android logs identify an old GUI shim overwriting its
source-built replacement and preventing the composer from loading. See
`DISPLAY_BOOT_FIX.md` for the correction, loader tests and small recovery ZIP.
The original ROM ZIP below remains unchanged and requires that follow-up fix.

Display v2 subsequently reaches the Lineage animation. Watchdog dumps identify
a missing Light HAL as the next gate. `LIGHTS_BOOT_FIX.md` records the targeted
build, driver dependency correction and tested small recovery update. Full
normal boot remains unverified.

`lineage-18.1-20261025-UNOFFICIAL-grandppltedx.zip` built successfully with
`m -j16 bacon` on a Linux VM. The final invocation completed at 14:12 UTC with
exit status 0. This is an Android 11/API 30 userdebug bring-up build for
grandppltedx; **no new image was flashed or boot-tested**.

## Exact sources and output

| Component | Compiled revision |
| --- | --- |
| Device | `71fecc466d8886da2e494fd628d84b37f7346c88` |
| Vendor | `f35626cafbb6e9b70f829ba52c345d375a0c2249` |
| Kernel | `6298fb15e62cf15d19e7fe08de030f48ad36fbed` |

These revisions are on the `codex/lineage-18.1-hardware-fixes` branches of the
homelander11 forks. The pinned `repo manifest -r` accompanies the artifacts;
the device's three scoped Android 11 patches are applied on top of its platform
revisions. Subsequent documentation-only commits do not change this build.

Build host: 20 vCPUs, 62 GiB RAM, 493 GB ext4 storage, Ubuntu 24.04 host with the
documented Ubuntu 20.04 container. No complete Android build ran on the local
12 GB Windows PC. Preserve the Linux checkout and `out/` for incremental work.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| ROM ZIP | 559607222 | `1a7670ccb03e1b22cf1a646b74a18d678c8e33fd71525bee1c86b5fb3691f445` |
| boot.img | 9138176 | `e5f443c5c6073c245b83dcf23fabd56596ad70d4b975ce22180dff950bc3a503` |
| recovery.img | 16529408 | `2e7b7ea59f03845db1373a009baee92c65821ef873e75a88851e6aa85c27bab8` |

The inherited stock Android 6 fingerprint is retained for compatibility; the
compiled platform is Android 11. The updater asserts grandpplte/grandppltedx,
updates system and boot, and contains no userdata format command. Recovery is
provided separately. A functioning recovery/backup path is still required for
physical testing.

## Verified

* Full ROM compilation, kernel compilation and OTA signing/packaging complete.
* Nine Python regression tests pass. Scoped platform patch preflight,
  idempotence, rollback and component-root checks pass.
* The targeted audio build passes. ARM inspection proves the framework keeps
  the normal `0xb4` mix-handle offset while the HAL's private conversion uses
  the vendor's `0xb0` offset. Private symbols are hidden and the HAL does not
  depend on the normal shared 4.0 conversion library.
* The independent calibration checker matches all seven filter selections to
  the intended 1260-byte audio records. It rejects the original blob, whose
  default selects the 512-byte Wi-Fi record. The correction changes eight
  library constant bytes; no live calibration content was modified.
* ROM and target-files ZIP CRC checks pass. All **312,639** new OTA blocks
  match the built filesystem image after Brotli decompression.
* Nine files were extracted from the actual ext4 image and compared against
  target-files. This confirms the corrected audio blob, original matching
  camera HAL, camera provider service, both audio conversion components,
  correct ION blob, modern ALSA utility, and both Wi-Fi configurations.
* The shipped ALSA utility exports `profile_get_highest_sample_rate`.
  Both supplicant configurations retain `force_connect_cmd=1`.
* Boot and recovery fit their 16 MiB partitions and pass legacy header,
  load-address, Samsung board ID, exact DT and payload SHA-1 checks.

The ext4 image uses a system-as-root layout. Verification resolves ordinary
system files below `/system/`; an initial checker assumed `/lib` at the image
root. The library was present and no ROM change was required for that lookup.

The build also exposed two source-setup issues now documented in
`tools/build/README.md`: pin the APN snapshot compatible with Android 11, and
enable Git LFS before sync. The ARM WebView payload is a separate Git project;
its full APK was fetched and matched its LFS SHA-256 before final packaging.

## Physical testing still required

Compilation and image validation do not establish working hardware. First test
boot, recovery access, Wi-Fi association/reconnection and suspend/resume. Then
test Bluetooth enable/disable, classic/BLE pairing, A2DP/SCO and address
persistence; speaker/earpiece/wired/USB playback, recording and both-SIM calls;
both cameras' preview/still/video/flash; and outdoor GNSS cold/warm fixes.

GNSS functional repair remains unestablished. USB audio runtime behavior,
Widevine's protobuf compatibility, power HAL stubs, modem init duplication,
sensor capability declarations and SELinux enforcing bring-up remain open.
Permissive SELinux/insecure ADB defaults are inherited; this is not a hardened
production release. See `HARDWARE_BRINGUP.md` for evidence and subsystem tests.

## Saved artifacts and VM retention

The local project `artifacts/` folder contains the ROM, boot/recovery,
`SHA256SUMS`, `package-validation.json`, pinned manifest, updater script and a
compressed build-evidence archive. The evidence includes build logs, platform
patches, audio disassembly and verification code. Private phone logs and boot
partition captures are excluded.

The VM checkout and `out/` remain available for incremental builds. Deleting
the VM loses that cache. Provider billing must be managed in the BookMyHost
panel; an Ubuntu shutdown or stopped build container does not prove billing
has ended.
