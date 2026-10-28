# Powered-off charging: dark display after a short Power press

After the SAR mount correction, the user confirms an animated battery with a
percentage appears, the display later blanks, and holding Power boots Android
without a battery removal. A short Power press still leaves the display dark.

Both native and shell charging logs now save successfully. They show KEY_POWER
(116) press/release events, immediate panel resume by the running charger and
continued health/battery updates. On resume, KTD3102 brightness stays zero.
This establishes a backlight failure rather than a missing button event or
stopped charger. Raw device logs remain private.

## Cause and scoped correction

In this kernel, `mtkfb_set_backlight_level()` caches `pre_level`. The MTK
`lcd-backlight` LED interface calls it. `mtkfb_blank_resume()` restores that
value after the first resume. The initial panel brightness makes
the first animation visible, but the charger never initializes this cache.
After the first blank, zero is restored.

`configs/init/zz-grandppltedx-charger-backlight.rc` writes brightness **102/255**
once during the `on charger` event. This seeds the existing driver path; the
kernel then blanks and restores the backlight normally. There is no polling,
new service, charger binary modification or input interception. The event does
not run on a normal Android boot, so the user's Android brightness setting
and the already corrected Light HAL retain control there.

The existing `device.mk` init-directory copy includes this file in future
builds. The modern charger service/resources are now integrated too; see
`CHARGING_FINAL_UPDATE.md` for build selection and diagnostic removal.

## Verified and pending results

* An on-device reversible framebuffer test reproduces a zero-brightness resume
  after setting the cached LED level to zero. One LED write of 102 then gives
  **two subsequent blank/resume cycles at actual brightness 102**. The original
  LED/panel level 5 is restored and Android remains booted. No persistent
  brightness setting is changed.
* `create_charger_wake_fix.py` and its undo pass the actual ROM updater on a
  disposable 64 MiB RAM ext4 loop: install, reinstall, undo, repeat-undo,
  low-battery rejection, unknown-target rejection and symlink rejection.
  Exact payload, root:root 0644 and `vendor_configs_file` are checked; all
  16 baseline files stay unchanged. Only fixture block/mount/interpreter,
  verifier and battery-text paths differ. The real boot hash stays unchanged.
* Both final ZIP CRCs and transferred Download SHA-256 values pass. The RAM
  fixture is cleaned. No ROM/kernel build or VPS is used.
* **Installed and user-verified:** animation/percentage and both repeated
  short-press wake cycles work. ADB verifies the exact init hash/metadata,
  normal boot and unchanged Android brightness5. The native log records the
  charger init action and brightness102. Long-press Android boot and unplug
  stopping charging mode also pass. Post-diagnostic-removal regression remains.

The recovery update adds only
`/vendor/etc/init/zz-grandppltedx-charger-backlight.rc`; undo removes exactly
that known file. Both require the pinned ROM, modern charging UI, corrected SAR
init hash, non-symlink targets and at least 15% battery. Charging limits,
calibration, EFS, boot/recovery and hardware libraries are unchanged.

| Payload/package | SHA-256 |
| --- | --- |
| Init file, canonical LF | `5fd82466fc07984f88e9fc71dccd8cdba15411c19f1b8f637e148f4ba2be9dba` |
| `grandppltedx-20261028-charging-wake-fix.zip` | `14e6c652f01e7c38003fbe4be7390d5dd1a8e9829312c84e5081547ca2b4b0e2` |
| `grandppltedx-20261028-charging-wake-undo.zip` | `1c665206539743e651461d43a391095602338dc3b1df45e0d8a44e0c1ed88e2e` |

Install the fix in TWRP with System unmounted and signature verification off.
Reboot System without wiping, verify normal Android brightness/wake first,
then power off with USB attached. Check the first animation, wait for blanking
and test several short presses. Finally verify long-press boot, unplug shutdown
and reconnect behavior. These initial physical tests now pass. Follow
`CHARGING_FINAL_UPDATE.md` for the current diagnostic cleanup and exact original
boot restore; the older init/shell undo expects the pre-SAR configuration.

When undoing development updates, remove this wake init before rolling back
the SAR/UI prerequisites. Its undo expects those known prerequisite hashes.

To reproduce the small recovery packages from this device tree:

```sh
python tools/build/create_charger_wake_fix.py ROM.zip --out-dir ARTIFACTS_DIR
```
