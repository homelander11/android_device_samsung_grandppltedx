# Temporary early-boot charging diagnostic

The native diagnostic is installed and has captured the charging failure:
the obsolete `/system` remount creates a system-as-root path loop. See
[CHARGER_SAR_FIX.md](CHARGER_SAR_FIX.md) for the evidence and scoped correction.
Normal boot and actual charging-mode logging both pass. The charging UI still
requires a device test after installing that correction.

Before this diagnostic, the Android 11 UI trial booted normally,
but the user still sees the static lightning icon and needs a battery/USB
removal to boot again. The charging-only init/shell diagnostic is installed
with verified hashes and labels. It starts and exits normally in Android, but
the charging test produced neither ADB nor its cache directory/log. This does
not establish whether init was reached, the mode check matched, or execution
failed before cache became available.

A read-only full boot-partition capture matches the pinned ROM prefix exactly.
Its ramdisk has the original Android first-stage init; no Magisk modification
was found. The cold battery removal leaves only a 46-byte RAM-console header
in last_kmsg and no pstore log. More changes to animation assets would not
resolve this evidence gap.

## Prepared component and image

`tools/charger/early/init_wrapper.c` and `start.S` implement a 9,652-byte static
ARM executable. It needs no Android libraries, APEX, shell or services. PID 1
temporarily mounts proc to read the kernel command line, then unmounts only
the proc mount it created. It execs the unchanged original init as `init.real`,
with the exact original argv and environment and the same PID.

Only Samsung's `androidboot.mode=charger` value prefix forks a logging child.
This matches the kernel's `sec_batt.c` prefix check. The child gets its own
private mount namespace, mounts the already verified ext4 cache partition, and
writes `/cache/j2prime-early-charger.log` as root with mode 0600. Six bounded
kernel snapshots are synced over about 31 seconds; the log is under 7 MiB.
The child exits afterward. The parent does not wait for cache/logging and
continues to the original init even if proc or fork fails.

The helper never requests reboot/shutdown, changes charging controls or
calibration, or changes SELinux. A normal boot does not fork the logger.
Default execution outside PID 1 is refused; `--self-test` is the sole
production diagnostic entry point outside PID 1. The separate fixture builds
use private RAM-loop paths and are never accepted by the boot packager.

`tools/build/create_charger_early_boot.py` requires the exact ROM and a full
16 MiB current boot backup, plus the reviewed production wrapper hash. It
preserves kernel bytes, DT bytes, command line, addresses, board ID, original
init contents and every other original ramdisk file. It changes the ramdisk
and updates only its size and the legacy boot checksum. Structural/DT/checksum
validation passes for the resulting full partition image. Recovery, system
and vendor are not updated by these packages.

## Verification already completed

* The static production ELF has no interpreter or dynamic section and contains
  the production paths. Its self-test and non-PID1 refusal pass on the phone.
* Eight Unicorn ARM execution cases verify exact argv/env handoff, charger-only
  fork, prefix/substring handling, continued boot after proc/fork failure and
  the execution guard. These run the production machine code with virtual
  syscalls; they do not establish real PID 1 boot success.
* On-device fixture variants pass normal exec without logging, fork/wait,
  private mount namespace, static syscalls, RAM ext4 log content and mode 0600.
  No real cache or boot write occurs in those tests.
* The actual ROM updater passes raw-block install, reinstall, exact undo and
  repeat-undo on a 16 MiB RAM loop device. Low battery and unknown-image checks
  reject before writing. The real boot partition hash stays unchanged.
* The public SDK component builder reproduces the tested ELF byte-for-byte.
  All transferred packages and the original backup match their local hashes.

**The user installed this image and confirms normal Android boot.** ADB verifies
the exact diagnostic boot-partition hash, `sys.boot_completed=1`, the correct
device and a 94% charging battery. No early charging log or logger process is
present during normal boot, as intended. The subsequent charging test captures
a private 1,282,158-byte log with six snapshots. It confirms PID 1/init,
charging mode, the legacy mount, shell exit 127, charger exit 1 and the
`Too many symbolic links encountered` restart error. Kernel battery workers
continue through the last snapshot; no kernel panic is observed. This is a
diagnostic boot image, not a verified charging fix; it is outside product build
packaging. No full ROM or kernel build and no VPS was used.

## Files prepared in Download

| File | SHA-256 |
| --- | --- |
| `grandppltedx-20261028-early-charger-boot.zip` | `a36e83828a65d826d0dae833fc747f5ae67bf7994686412b359b5110d50bf973` |
| `grandppltedx-20261028-early-charger-boot-undo.zip` | `bee545efdbc690f4760d21b7a7cf331cd9d09ebcafa346866d9d7732efcaa9b7` |
| `grandppltedx-20261028-before-early-boot.img` | `2fdd5db2a3e047ce8710771a668e0290ee81ae905fe94020d832f2b14a5849c8` |

The ZIPs contain the pinned ROM updater and require root recovery, SM-G532G,
the verified boot/cache block paths, a 16 MiB boot partition, at least 40%
battery and an exact original/diagnostic partition hash. The image is verified
again after writing. Undo restores the exact full original partition, including
its original padding. The diagnostic image SHA-256 is
`5ae57639452c4f93baca11b284cde490410bbca642a753c55b113ce7371229ee`.

When the user is ready for this boot-ramdisk trial, install only the early-boot
diagnostic ZIP in TWRP with signature verification off. Reboot System without
wiping and confirm normal boot first. If normal boot fails, return to the
unchanged recovery and install the early-boot undo. The raw original image is
also available for recovery's image-to-Boot restore. Do not select Recovery.
Only after normal boot verification perform a bounded charging test, then
collect the private cache log. Do not publish logs or raw partition captures.
The separate init/shell diagnostic and its undo remain independent.

## Reproducing the small component

`build_sdk.py` uses the existing Windows SDK build tools with Python llvmlite
(LLVM 20) and keystone-engine. It emits only this component and local object/IR
files. `--fixtures` additionally builds the isolated-test variants.

```powershell
python tools/charger/early/build_sdk.py --build-tools SDK_BUILD_TOOLS_DIR --out-dir OUTPUT_DIR
python tools/charger/early/test_wrapper.py OUTPUT_DIR/init-wrapper
```

A GNU ARM Makefile is also provided. That cross-build has not been run here;
its output requires its own execution tests and reviewed manifest update.
The packager checks canonical source hashes and the exact tested ELF hash.

```sh
python tools/build/create_charger_early_boot.py ROM.zip FULL_BOOT_BACKUP.img OUTPUT_DIR/init-wrapper --out-dir ARTIFACTS_DIR
```

The source manifest records test scope and hashes. Build artifacts and private
logs stay outside this Git tree.
