# GPS initialization blocks Android startup (October 26, 2026)

The Light fix installed successfully according to TWRP's saved log. The next
boot passes display initialization and logs `boot_progress_enable_screen`.
The remaining animation hang has a different watchdog stack: LocationManager
waits inside `GnssLocationProvider.native_init`. After a system_server restart,
even GNSS `interfaceChain` queries wait because the service's only thread is
still occupied by the original initialization request.

The GNSS process is present, as are `mnld` and AGPS. Its single native thread
waits in `pthread_cond_wait` at legacy GPS HAL PC `0x513d`, called from `0x8a8f`.
This is the HAL's initialization-ready wait. The worker is no longer present.
These are Thumb addresses in the exact pinned module, not portable offsets.

## Diagnosed failure and correction

Disassembly of `gps_state_thread` shows a filesystem stream socket bind at
`0xa1d2` to `/data/misc/codec_sock`. The bind-error branch closes the earlier
datagram socket and exits through worker cleanup before initialization is
signaled. That leaves the legacy `init` caller waiting indefinitely.

On this phone `/data/misc` is mode 1771, system:misc. The GNSS service runs as
gps (1021), with groups system/gps/radio/inet; it cannot create that socket.
A static ARM syscall probe, after dropping root to that exact UID/GID/group
set, confirms `bind` returns EACCES under `/data/misc`. The same probe binds
and removes its diagnostic socket successfully under `/data/gps_mnl`, already
created mode 0771 gps:system by `mtk_agpsd.rc`. Both diagnostic names are checked
absent before/after testing. This establishes the permission failure; normal
service initialization after patching remains to be tested.

Change only the driver's single `/data/misc/codec_sock` literal to
`/data/gps_mnl/codec`, padding the original 22-byte string slot with NULs.
Fourteen bytes differ at file offset `0x14ba7` (84903). The file stays 131,265
bytes. All other bytes, executable sections, ELF headers, dynamic symbols and
dependencies are identical. Existing MNL datagram paths stay unchanged.
The socket's existing mode/group logic stays unchanged too. No other file in
the bundled vendor snapshot references `codec_sock`; an external factory tool
using the old path would need the new path.

The vendor tree includes the corrected blob, `gps-socket-provenance.json`, and
guarded `tools/fix_gps_socket.py`. It rejects unknown SHA-256 inputs and is
idempotent. The original comes from the same device repository revision
`d3a6207e911fd01ff898bb64ac5cd71740a68516`, Git blob
`3027839add42d897d65ccbb4d3d3650dc92d398c`.

* Original SHA-256: `9dea2246a148f6f60d0f3c9a69b7d9fe92da4a645abf7153c815ac73ead5befc`
* Corrected SHA-256: `26810174325967eafe9a7292a3efb65c8700943d4189a1c37e08a52905c253cf`

## Validation and reproduction

The permission probe uses direct Linux ARM syscalls, avoiding recovery's older
Android libraries and ART bootstrap requirements. Generate it with
`python3 tools/device-probe/make_gps_socket_probe.py OUTPUT`. Run only from an
authorized root recovery shell after checking these two paths are absent:

```
/data/misc/j2prime-gnss-bind-test.sock
/data/gps_mnl/j2prime-gnss-bind-test.sock
```

Measured result: `PASS uid=1021: old parent bind EACCES; GPS-owned parent bind/unlink OK`.
Recovery SELinux is permissive, as is this bring-up ROM; this is not a test of
enforcing SELinux policy. The probe loads no vendor HAL and requests no GPS fix.

Host checks confirm the exact byte scope, unchanged ELF code/metadata,
idempotence and unknown-input rejection. `validate_gnss_socket.py VENDOR_DIR`
rejects the original HAL and verifies the corrected blob plus matching init
configuration (add `--source` for the source snapshot). The build runner checks source blobs before building and the
installed vendor directory after `bacon`. Existing configuration checks pass,
including both Wi-Fi parameters; all nine existing regression tests pass.

The complete recovery updater ran on a temporary 16 MiB ext4 RAM image:
installation, repeated installation, exact-original undo, mode 0644 and
`vendor_file` labeling all succeeded. An intentionally altered input was
rejected before replacement. Test ZIPs differed only in the system block-device
argument, pointing to the verified RAM-image loop device. All test mounts,
loop attachments and diagnostic sockets were removed. Installed firmware was
only read by these diagnostics, not changed. No VPS or Android build was used.

## Recovery update and remaining tests

`create_gnss_fix.py BASE_ROM PATCHED_HAL ORIGINAL_HAL --out-dir DIR` generates
the fix/undo ZIPs using the exact original ROM's updater. Obtain ORIGINAL_HAL
from the pinned revision above. All three input hashes are checked. The ZIP
guards pin the 20261025 ROM/API 30, corrected GUI shim, Light driver/service,
GNSS init files and original/corrected GPS HAL. Only `gps.default.so` is replaced.

Install `grandppltedx-20261026-gnss-fix.zip` in TWRP after display v2 and the
Light fix, with ZIP signature verification off. Reboot System without wiping.
This ZIP contains no boot image, Wi-Fi change, process-UID change, directory
permission change, NVRAM or userdata operation. The undo ZIP restores the old
GPS module and its original initialization failure.

Normal boot and GPS operation are **unverified until the user installs/tests**.
Check that the animation finishes, `sys.boot_completed=1`, GNSS service requests
return, no recurring GNSS/watchdog deadlock occurs, and Wi-Fi still connects.
Then test outdoor cold/warm satellite fixes, NMEA, stopping/restarting location,
time/location injection, SUPL and suspend/resume. A successful boot alone does
not establish working positioning. Camera's separately observed vendor Skia
ICU-60 symbol failure, Bluetooth, audio and microphone testing remain open.

References: [Android 11 GNSS wrapper](https://github.com/LineageOS/android_hardware_interfaces/blob/lineage-18.1/gnss/1.0/default/Gnss.cpp),
[thread creation wrapper](https://github.com/LineageOS/android_hardware_interfaces/blob/lineage-18.1/gnss/1.0/default/ThreadCreationWrapper.cpp),
and [device kernel ARM syscall numbers](https://github.com/RodrigoAyuso/android_kernel_samsung_grandppltedx/blob/lineage-18.1/arch/arm/include/uapi/asm/unistd.h).
