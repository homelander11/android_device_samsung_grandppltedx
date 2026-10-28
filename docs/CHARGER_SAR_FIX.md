# Charging-mode system-as-root mount correction

The 2026-10-28 native early-boot log establishes a concrete charging startup
failure. Init reaches charging mode and starts the installed Android 11 charger,
then the legacy `ro.bootmode=charger` action in `init.mt6735.rc` mounts the system
partition a second time at `/system`.

This ROM uses system-as-root (SAR). The second mount exposes the filesystem
root inside `/system`, so its `bin -> /system/bin` symlink refers to itself.
Init reports `Cannot find '/system/bin/charger': Too many symbolic links
encountered`. The shell diagnostic exits 127 and the charger exits 1. Kernel
battery work continues through the final snapshot; a kernel panic was not
observed. The raw log contains private device data and is not committed.

`tools/charger/early/sar_mount_probe.c` reproduces this mechanism on the phone
by binding the SAR root at `/system` in a **private mount namespace**. Opening
the charger returns `ELOOP` (-40); unmounting restores access. Root propagation
is made private before mounting. The real charger hash and Android boot state
remain unchanged. It refuses PID 1, non-root and execution without `--run`.

## Source and installed-ROM correction

`rootdir/init.mt6735.rc` removes only the obsolete charger-mode system mount.
First-stage init already mounts SAR. EFS actions, charge controls, calibration,
kernel, boot, recovery and existing hardware fixes are unchanged.

`tools/build/create_charger_sar_fix.py` packages the same correction for the
pinned installed ROM and an exact undo. It derives the runtime payload from
the original ROM init file, preserving every byte outside that block/comment.
It does not replace the runtime file with the whole current source version.

This package requires the **already installed Android 11 charging-UI trial**.
The old Samsung LPM also has mandatory missing libraries; removing the remount
does not make that old executable usable. The modern charger/service/font
are described in [OFFLINE_CHARGING.md](OFFLINE_CHARGING.md). Their full-build
packaging is now active after the user wake/boot tests; see
`CHARGING_FINAL_UPDATE.md`.

The only runtime target is `/vendor/etc/init/hw/init.mt6735.rc`:

| State | SHA-256 |
| --- | --- |
| Original | `2bca24ad483f10b8a924fbc1a3d4ee69f417355a7b22413d8f45cab6badbf931` |
| Corrected | `2ed14a42098c6ecc2f1738cb083c79043ca02e706bde073ef9229686d28652c6` |

The installer checks the pinned ROM/SDK, dependencies, existing UI trial,
known target hash, non-symlink paths and at least 15% battery before extraction.
It sets uid/gid 0, mode 0644 and `vendor_configs_file`, then verifies the result.
Recovery must leave System unmounted before installation.

## Completed validation

* Real charging-mode native log identifies the failing action and `ELOOP`.
* The reproducible static ARM probe passes on-device, including default refusal
  and private-namespace reproduction/restoration. The public SDK builder emits
  the tested probe (9,328 bytes, SHA-256
  `13ca252f2b7813212a0f8eb35c0b4cd06d65e911928a4c7ae4a7e10e7e40b21f`)
  and still reproduces the original boot logger exactly.
* The actual ROM updater passes install, reinstall, undo and repeat-undo on a
  disposable 64 MiB RAM ext4 loop. Exact target hash/metadata and all 15 other
  baseline files stay correct. Both ZIPs reject low battery, unknown content
  and a symlink target before mutation. Only fixture block/mount/interpreter,
  verifier and battery-text paths differ from production.
* The real boot partition remains the installed early diagnostic image and
  Android stays booted. RAM mounts/loop/image/seed are cleaned afterward.
* Both final ZIPs have valid CRCs and match their hashes in phone Download.
  Thirteen installed charging/hardware file hashes still match the baseline.

| Package | SHA-256 |
| --- | --- |
| `grandppltedx-20261028-charging-sar-fix.zip` | `583936105bc8c4a345a6c4ece5a1666102f1ae0ec80c55506669b8696361e094` |
| `grandppltedx-20261028-charging-sar-undo.zip` | `5700390dcd5d1b95c4629008af97ed0e0547c788d374eea4e5e044db4b3a619b` |

**Installed; user and ADB confirm normal Android boot.** The runtime init hash,
root:root ownership, mode 0644 and vendor-config label match. Modern charger
service/animation/font and the diagnostic boot hash are unchanged; battery is
90% and USB charging at the first verification. The user subsequently confirms
an animated battery/percentage, normal blanking and long-press Android boot
without removing the battery. The original startup failure is resolved.

The separate brightness-cache initialization now also passes repeated
short-press wake; see [CHARGER_BACKLIGHT_WAKE.md](CHARGER_BACKLIGHT_WAKE.md).
The user confirms unplug stops charging mode. Diagnostic removal and the
remaining validation are in `CHARGING_FINAL_UPDATE.md`. No full ROM/kernel
build or VPS was used.

The initial physical tests now pass. Follow `CHARGING_FINAL_UPDATE.md` to
restore the exact original boot and remove the init/shell diagnostic with the
new cleanup package; its older undo expects the pre-SAR configuration.
Neither diagnostic belongs in a release ROM. If rolling back the modern UI,
undo the SAR correction first: the older UI undo expects the original init
hash. The SAR undo restores only that init file, including its old remount.

## Reproduction

From the device tree:

```sh
python tools/charger/early/build_sdk.py --build-tools SDK_BUILD_TOOLS_DIR --out-dir OUTPUT_DIR --sar-probe
python tools/build/create_charger_sar_fix.py ROM.zip ORIGINAL_INIT_MT6735_RC --out-dir ARTIFACTS_DIR
```

The SDK builder requires llvmlite (LLVM 20) and keystone-engine. A GNU ARM
`make -C tools/charger/early sar-mount-probe` target is also provided, but its
output has not been built/tested here. The probe is a standalone diagnostic;
it is never copied into a boot image or the product filesystem.
