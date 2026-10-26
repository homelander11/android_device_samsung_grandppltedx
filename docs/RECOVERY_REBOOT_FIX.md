# Recovery reboot request refused on Android 11 (October 26, 2026)

Recovery access is restored: the connected phone reached TWRP `3.6.1_9-0`
after the temporary workaround below. No firmware partition was written.
The original TWRP partition was backed up privately and hashes identically
before and after. The microphone/backlight update ZIPs remain available in
`/sdcard`; their installation is a separate user step.

## Diagnosis

The user clarified that `adb reboot recovery` left Android running without
restarting. The installed recovery contains a valid Samsung recovery board
identifier, valid legacy payload checksum, gzip/cpio ramdisk and Samsung
trailer. It differs from the ROM's bundled recovery. The automatic recovery
replacement property is false, so replacing TWRP was not the cause.

The active fstab has no `/misc` entry. Android 11 init reads a bootloader
message for a plain recovery request, then tries to write `boot-recovery`
when the command is empty. A failed write returns before normal shutdown.
The bootloader-message library searches the default fstab for `/misc` and
fails if it cannot find it. This matches the request being refused while
Android continues running.

This Samsung kernel instead selects recovery from the literal `recovery`
reboot reason: `drivers/staging/samsung/sec_reboot.c` stores
`SEC_RESET_REASON_RECOVERY`. The device defconfig enables `CONFIG_SEC_REBOOT`.
We need normal init shutdown to reach that handler; mapping an arbitrary
physical partition to `/misc` is unnecessary.

## Verified one-time workaround for the installed ROM

`tools/device-probe/reboot_recovery_ram.sh` defaults to `--check`. The explicit
`--reboot` mode creates a zeroed 4096-byte regular file in `/dev` tmpfs and
temporarily bind-mounts a copy of the fstab with that RAM file as its `/misc`
entry. The bootloader-message library accepts a regular file, writes only
there, and lets init perform its normal shutdown with the `recovery` target.
The Samsung kernel then boots the existing TWRP image.

The helper pins this ROM version/API, SM-G532G model, hardware and exact
installed fstab hash. It requires the current permissive bring-up environment,
shared init/shell mount namespace, tmpfs `/dev`, unused RAM paths and the
expected recovery partition size. It rejects alternate recovery/default fstab
locations that would invalidate the diagnosed lookup. It does not remount a
firmware filesystem writable or execute a forced kernel reboot.

Normal reboot cleared the RAM files and bind mount, as verified in TWRP.
If the request does not start shutdown within 15 seconds, the helper detaches
the overlay and removes its RAM files. The original fstab is never edited.
The script remains in `/data/local/tmp` for another recovery request from the
current Android build:

```sh
adb shell sh /data/local/tmp/j2prime-reboot-recovery-ram.sh --check
adb shell sh /data/local/tmp/j2prime-reboot-recovery-ram.sh --reboot
```

These commands require the already authorized root ADB session used during
bring-up. Run them from Android, not from TWRP. No fake BCB is persisted across
boots, and no partition such as PARAM, para or nvram is used for the workaround.

## Source correction for future builds

The scoped `patches/android-11/system/core` patch makes the plain `recovery`
request's BCB operation conditional on `ro.vendor.recovery.skip_bcb` being
false. This device explicitly sets the property true in its vendor build
properties. The default remains false for other products, and existing BCB
handling/error checks for other reboot targets are unchanged. The kernel
receives the normal `recovery` reboot reason after graceful shutdown.

The patch installer now preflights `system/core` alongside the three existing
components. The new patch applies cleanly to the exact built revision
`92420679ffbd50b79d76525085b21278f8497037`; reverse-check detects repeated
application. All 13 host regression tests pass, including four-component
preflight/rollback checks, and all 21 XML/configuration checks pass.

The permanent init change has **not been compiled or boot-tested**. The paid
VPS stayed off and no full ROM build was performed. The successful live test
verifies the RAM workaround and Samsung's recovery selection, not a newly
built init binary. The existing installed ROM still needs the helper for a
software recovery reboot. The two hardware-fix ZIPs do not replace init.

After a future build, test ADB recovery reboot, the advanced-restart menu,
ordinary reboot and power-off. Sideload/automatic updater boot arguments are
separate paths and are not enabled by this plain-recovery patch. The physical
button sequence is also independent of Android's boot-message handling.

References: [exact built init source](https://github.com/LineageOS/android_system_core/blob/92420679ffbd50b79d76525085b21278f8497037/init/reboot.cpp),
[bootloader-message file handling](https://github.com/LineageOS/android_bootable_recovery/blob/lineage-18.1/bootloader_message/bootloader_message.cpp),
[fstab lookup](https://github.com/LineageOS/android_system_core/blob/92420679ffbd50b79d76525085b21278f8497037/fs_mgr/fs_mgr_fstab.cpp).
