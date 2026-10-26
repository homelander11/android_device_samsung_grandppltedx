# GPS positioning investigation: experimental candidates

Status on October 26, 2026: **GPS positioning is not working or verified.** An
outdoor foreground test returned zero satellites seen/used. The earlier GPS
socket-path fix unblocked boot; it did not establish satellite reception.

GPS candidates are on `codex/gnss-compatibility-candidates` in the device and
vendor repositories. The last normal-build baseline is
`codex/lineage-18.1-hardware-fixes`. Do not treat candidate code as a verified
GPS fix or mix the two vendor/device snapshots when evaluating it.

## Verified failures

The local GPS probe registers status/NMEA callbacks and requests the real GPS
provider in a foreground activity. It reports only counts, signal levels,
accuracy and timing; it never reads coordinates or stores NMEA contents.
The installed boot, GPS socket, microphone and Light corrections were verified
by their library hashes. Location was enabled for the test.

Two native failures were captured:

* GNSS service aborts in `Gnss::nmeaCb`, through
  `hidl_string::setToExternal`, because `data[size]` is not NUL. The legacy
  callback provides a pointer and length; the wrapper borrowed that buffer
  with an extra terminator requirement. The crash PC is `0xe8e7` in the
  exact compiled `android.hardware.gnss@1.0-impl.so`.
* `mnld` aborts in `pthread_mutex_destroy`, called by its `libmnl.so` private
  wrapper at PC `0xd03b`. Bionic reports an already-destroyed mutex. The
  same abort repeats when a GPS request is stopped and restarted.

The GPS daemon's NVRAM selector was separately checked: it already loads
LID 50 with a 52-byte buffer, matching this device's GPS record. The audio
library's earlier +2 selector error does not apply here. No GPS calibration,
assistance profiles, radio firmware or Wi-Fi configuration were changed.

## Candidates and validation boundaries

The GNSS source patch replaces the borrowed view with the public HIDL
length constructor, which copies the same bytes and adds a trailing NUL.
It targets `hardware/interfaces` revision
`203e87a39c04f30bc1f09f6c2306b701d6b97fe0`. Compilation of that source change
is pending; no paid VM was started.

For a temporary live test, the pinned wrapper's sole `setToExternal` import
was redirected to the existing same-signature `copyFrom` method. The only
resolved call site was the NMEA callback at `0xe8e6`; the object is empty
before that call and its destructor frees the copy. This diagnostic adapter
was not committed as a vendor blob or made into a flashable update.

That NMEA-only trial kept the GNSS service alive and advanced the kernel
from GPS INIT (1) to START/navigation (2). `mnld` still aborted on request
stop/restart. Later system_server watchdogs blocked during
`IGnss::getService`/`GnssLocationProvider.class_init_native`, returning the UI
to the Lineage animation. Consequently **the NMEA-only trial is not a safe,
complete GPS fix**.

The second candidate guards the private MNL mutex-destroy wrapper's
`0xffff` destroyed state and reuses its existing -1 error return. Every other
state still calls the original `pthread_mutex_destroy`, preserving 0/-1
normalization. It changes one 18-byte code region at file offset 53306 in
the pinned `libmnl.so`. It does not disable runtime checks or lower the
process/system target SDK. See vendor `mnl-mutex-provenance.json` and
`tools/fix_mnl_mutex.py` for exact bytes, source/hash guards and reproduction.

The exact original/patched Thumb instructions were executed in an isolated
ARM process using a private mutex table and a mock destructor. Tests cover
the original invalid call, skipping a destroyed mutex, normal destruction,
repeat destruction, real-call error normalization and another valid index.
All passed. The probe touched no GPS hardware, service or calibration.
**The guard has not been loaded into the production MNL process**, and a
combined service test, location start/stop cycles and satellite fixes remain
pending. Host byte-scope/idempotence/rejection tests supplement that CPU test.

## Restored phone state and next test gate

The diagnostic was stopped, Location set to off, the temporary wrapper bind
removed, and the original GNSS/MNL services restarted. Android recovered and
the user confirmed it booted. Boot animation is stopped; installed microphone
and backlight hashes remain correct. The installed wrapper/MNL hashes are
the originals, and no experimental GPS mount remains. No firmware partition
was flashed, no wipe was performed and no GPS calibration was written.

Leave Location off until another controlled test is arranged. Before any
combined trial, preserve the original libraries and a rollback script that
stops the probe, restores original mounts/services and disables Location on
failure. Check service registration/reinitialization as well as process
survival. The watchdog incident shows that an alive daemon and navigation
state alone are insufficient. Do not package or recommend these candidates
for persistent installation until that test passes.

References: [GNSS wrapper](https://github.com/LineageOS/android_hardware_interfaces/blob/203e87a39c04f30bc1f09f6c2306b701d6b97fe0/gnss/1.0/default/Gnss.cpp),
[owned and borrowed HIDL string behavior](https://github.com/LineageOS/android_system_libhidl/blob/lineage-18.1/base/HidlSupport.cpp),
[Bionic destroyed-mutex behavior](https://android.googlesource.com/platform/bionic/+/9864564fcaaf2f56dad0f2c3d942e3eb6ac625d6/libc/bionic/pthread_mutex.cpp).
