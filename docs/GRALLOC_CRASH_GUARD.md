# Gralloc failed-module cleanup guard

The graphics composer crashes when the legacy gralloc module lookup fails and
cleanup then dereferences that null module. The latest third-party camera trial
repeats the earlier crash at RVA 0x3caa, fault address 0xc8. This is separate from
the installed video-colour correction and the still-open camera compatibility
issue.

`tools/fix_gralloc_unregister.py` replaces four bytes at RVA/file offset 0x3c6e:
`fdf7c4ef` becomes `00f042b8`, returning through the existing epilogue after the
existing lookup-error log. Successful-module cleanup is unchanged. This guards
the null dereference; it does not repair the preceding module/ION import errors.
The failure case cannot release resources through a missing module and may
retain them until the process exits.

Original SHA-256:
`1b8bb21c0673859e690191d68bf58af840a094df6fd6fdfb3ca738bf63f79532`.
Guarded SHA-256:
`970af7638d3e12d116c9171eae78a590ff9246169b30308ccfd2179cebb8c4cc`.

## Validation and current status

ARM emulation verifies unchanged normal/non-ION/munmap-error paths and safe
returns for failed module lookups. An isolated on-device process forces module
lookup failure and passes with the guard and original legacy shims preloaded.
It changes no display service. The current phone's original driver hash and
new tombstone match the pinned input and exact failure.

`tools/build/create_gralloc_guard_fix.py` generates a fix and exact undo for
the diagnosed ROM with the combined camera/audio and colour updates installed.
It checks 26 dependencies and accepts only original/guarded gralloc hashes,
then replaces only `vendor/lib/hw/gralloc.mt6735.so`. Fix/reinstall/undo, target
ownership/mode/SELinux label, unchanged other seeded files, unknown input and
dependency rejection, and symlink rejection pass using the real ROM updater
on a disposable 64 MiB ext4 RAM image. No phone partition is written by that test.

The user installed the guard in TWRP and rebooted successfully. The installed
driver matches the guarded hash, normal Android display works, and the composer
has stayed running through normal use. The user confirms the built-in camera's
live preview and photo capture work. The matching vendor tree now includes this
exact four-byte guard; `gralloc-unregister-provenance.json` records its input and
validation. Wider media/Wi-Fi/wake regression checks remain pending. The Play
Store camera still fails; this guard does not fix its preview/session problem.

| File | SHA-256 |
| --- | --- |
| `grandppltedx-20261027-gralloc-guard-fix.zip` | `c5791e5352c0d2ef63dddb08e084631ad44c4da845523161054ffd455a4834ab` |
| `grandppltedx-20261027-gralloc-guard-undo.zip` | `c0fd6412b24e6fa08fa7e6ae3d5dfab1292023a56ae5ca4e76ae2a178765c582` |

For device testing, keep undo accessible in recovery. Install only the guard
fix in TWRP with System unmounted and signature verification off, then reboot
without wiping. First check normal boot/display, default-camera preview/photos,
colour/sound playback, Wi-Fi and wake. Keep the third-party camera closed until
that baseline is verified. The guard undo restores the original graphics driver
without changing the installed camera/audio fixes. No full ROM build is needed.
If reverting several updates, undo this guard before the colour update, since
its installer deliberately requires the currently installed colour helper.
