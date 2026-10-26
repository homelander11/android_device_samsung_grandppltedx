# GPS positioning investigation: experimental candidates

Status on October 26, 2026: **GPS positioning is not working or verified.** An
outdoor foreground test with the older engine returned zero satellites.
The newer rollover candidate later reported one satellite at 12.8 dB-Hz,
zero used and no position fix. The earlier GPS socket-path fix unblocked boot;
it did not establish satellite reception or positioning.

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
normalization. In the first 2016 engine candidate it changes one 18-byte code
region at file offset 53306. In the newer 2018 candidate described below, the
equivalent region is at offset 53386 and its original -1 return is at `0xd074`.
It does not disable runtime checks or lower the
process/system target SDK. See vendor `mnl-mutex-provenance.json` and
`tools/fix_mnl_mutex.py` for exact bytes, source/hash guards and reproduction.

The exact original/patched Thumb instructions were executed in an isolated
ARM process using a private mutex table and a mock destructor. Tests cover
the original invalid call, skipping a destroyed mutex, normal destruction,
repeat destruction, real-call error normalization and another valid index.
All passed. The probe touched no GPS hardware, service or calibration.
Host byte-scope/idempotence/rejection tests supplement that CPU test.

## Combined temporary service tests

With user authorization after the watchdog incident, both candidates were
loaded together using temporary bind mounts. A 60-second foreground request
passed six bounded Location-service health checks, kept the original
system_server and both GPS process IDs, and produced hundreds of NMEA
callbacks. The kernel reported navigation state 2 throughout. Automatic
rollback restored both original library hashes and disabled Location.

A later trial passed two foreground app request stop/start cycles without
restarting either GPS process. Its probe also reports only GSV satellite
totals and GSA fix mode, never raw sentences or coordinate fields. The user
kept it outside for five minutes and reported zero satellites seen/used.
Collected receiver reports also showed GSV total 0 and GSA mode 1 (no fix),
with hundreds of NMEA callbacks. Both GPS process IDs and system_server
remained unchanged through 38 service health checks. The trial was manually
ended after the user returned, before its seven-minute observation deadline;
original GPS hashes and Location-off state were verified again. This verifies
service survival and the tested request cycles, not satellite reception,
Location-setting toggles or a cold-boot test.

The controlled harness starts an independent on-phone monitor before changing
services. It restores the original mounts and disables Location on a process
restart, Android restart or deadline, including when USB is disconnected.
Each binder command is bounded using `timeout -s KILL` with native `cmd`;
the earlier `am -W` shell wrapper did not reliably terminate on a TERM timeout.
GNSS is started fresh after enabling Location. Starting the legacy HAL while
Location is off exposed a separate cleanup/reinitialization problem: a later
request could reuse invalid control descriptors. This lifecycle issue remains
open and prevents treating the candidates as a complete persistent fix.

## Same-device week-rollover candidate

The earlier `lineage-15.1` vendor branch contains a newer MNL engine:
`MNL_VER_18110801ALPS05_3.70_21`, compared with this branch's
`MNL_VER_16092301ALPS05_3.70_20`. Its pinned source commit
[`d7d1ff06db5cf884b41f045cdb77103ed125e734`](https://github.com/RodrigoAyuso/android_vendor_samsung_grandppltedx/commit/d7d1ff06db5cf884b41f045cdb77103ed125e734)
explicitly updates the library for GPS week rollover. The two files have the
same size, 197 exported symbols, and all 20 MNL imports used by this device's
mnld. Those checks support testing compatibility; they do not prove private
data layouts or hardware operation.

The newer engine still contains the repeated-destroy wrapper, now at PC
`0xd08b`. An equivalent 18-byte guard was prepared at file offset 53386 and
its actual Thumb instructions passed the same isolated ARM CPU tests before
any live service trial. With the temporary NMEA-copy adapter, it then passed
two foreground app request stop/start cycles while preserving both GPS
processes and Android. During the subsequent outdoor trial, the final probe
record showed elapsed time 353,526 ms, 3,532 NMEA messages, one satellite seen
(peak one), C/N0 12.8 dB-Hz, zero used, no fixes and GSA mode 1. Both Android's
satellite callback and the receiver's GSV report counted that satellite;
no mock fixes were accepted. Android and both GPS processes stayed alive.
The trial was manually ended after the user returned, before its deadline.

This establishes that satellite reporting can work with this candidate; it
does not prove the version update alone caused the difference from the earlier
trial, since sky visibility and reception were not controlled. The user
described poor stock reception, but a matched stock-firmware comparison has
not established a hardware fault. More reception testing and a real position
fix are still required. The legacy GPIO status showed GPS antenna GPIO79 as
output-high during navigation and input/low after rollback. This verifies the
software control state, not antenna continuity or RF gain. The receiver still
logged `GET_RTC_FAIL`; that warning alone does not establish the cause.

The candidate vendor branch contains this pinned newer engine plus guard at
`dae7a5036dec139d06b7506ffa933dd6876940c4`. See vendor
`mnl-rollover-provenance.json` for the complete version update and
`mnl-mutex-provenance.json` for the separate local instruction change. The older
branch's general GPS status is not evidence that this newer engine works on
Android 11, and neither its commit message nor the version string establishes
that week rollover caused this phone's zero-satellite result.

## Restored phone state and next test gate

After the earlier watchdog incident, the diagnostic was stopped, Location set
to off, the temporary wrapper bind
removed, and the original GNSS/MNL services restarted. Android recovered and
the user confirmed it booted. Boot animation is stopped; installed microphone
and backlight hashes remain correct. The installed wrapper/MNL hashes are
the originals, and no experimental GPS mount remains. No firmware partition
was flashed, no wipe was performed and no GPS calibration was written.
Both later combined trials were also restored to these original GPS hashes.
The installed microphone and Light correction hashes still match their tested
versions. The paid build VM remained off; no full ROM build was performed.
After the controlled session, the diagnostic APK was uninstalled and its
stopped test scripts, adapters and native CPU probe removed from the phone.
Private logs and reproducible test inputs remain in the local research folder.

The current candidate passes all 15 host tests, 22 XML/configuration checks and
the GPS socket/init validator. The diagnostic APK builds and verifies its
signature locally. These checks supplement the isolated ARM and live service
tests; they do not establish successful positioning or production readiness.

Leave Location off between controlled tests. Before any
combined trial, preserve the original libraries and a rollback script that
stops the probe, restores original mounts/services and disables Location on
failure. Check service registration/reinitialization as well as process
survival. The watchdog incident shows that an alive daemon and navigation
state alone are insufficient. Do not package or recommend these candidates
for persistent installation until that test passes.

References: [GNSS wrapper](https://github.com/LineageOS/android_hardware_interfaces/blob/203e87a39c04f30bc1f09f6c2306b701d6b97fe0/gnss/1.0/default/Gnss.cpp),
[owned and borrowed HIDL string behavior](https://github.com/LineageOS/android_system_libhidl/blob/lineage-18.1/base/HidlSupport.cpp),
[Bionic destroyed-mutex behavior](https://android.googlesource.com/platform/bionic/+/9864564fcaaf2f56dad0f2c3d942e3eb6ac625d6/libc/bionic/pthread_mutex.cpp).
