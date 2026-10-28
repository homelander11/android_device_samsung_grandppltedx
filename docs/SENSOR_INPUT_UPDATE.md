# Samsung sensor input access / rotation bring-up (2026-10-27)

Auto-rotate was enabled but the framework received no accelerometer events.
The kernel exposes a Bosch BMA254 accelerometer and STK3013 proximity input.
The installed Sensors 1.0 service runs as system:system with wakelock, uhid and
context_hub supplementary groups. It lacks input. Both sensor event nodes are
root:input 0660; accelerometer poll_delay is also root:input 0660. The running
HAL has no input event descriptors. The sensors HAL enumerating two devices
therefore did not establish working sensor access.

An isolated process using the exact service UID/GID/groups reproduces EACCES
for both event nodes and poll_delay. Adding only input permits all three opens.
That comparison performs open/close only. A second isolated process loads the
unchanged sensor HAL under the corrected credentials and receives multiple
acceleration events with valid gravity units and increasing timestamps. The
running sensor service and system_server PIDs remain unchanged. The original
disabled state and 200ms delay are restored and verified; calibration is not
written. The BMA254 delay attribute reports milliseconds but accepts nanoseconds:
restore reads must be multiplied by 1000000 before writing. The initial test
cleanup used the wrong units, was detected by readback and corrected to the
original value before proceeding.

Battery Saver appeared in a power dump, but the later authoritative low_power
setting is 0. Auto-rotate is 1. The input permission failures are independently
reproduced; this is not treated as a Battery Saver-only issue.

## Source configuration

`configs/init/zz-grandppltedx-sensors.rc` overrides the normal
`vendor.sensors-hal-1-0` definition and adds supplementary input. Its UID/GID,
standard groups, interface, class, BLOCK_SUSPEND capability and rtprio limit are
retained. The existing recursive configs/init installation rule packages it.
The zz filename orders it after the standard service in the vendor init folder.
No HAL binary, kernel, device-node mode/owner or calibration change is needed.

The [LineageOS 18.1 standard service](https://github.com/LineageOS/android_hardware_interfaces/blob/lineage-18.1/sensors/1.0/default/android.hardware.sensors@1.0-service.rc)
provides the preserved settings. Android 11 supports service overrides; see
[init's override and import rules](https://github.com/LineageOS/android_system_core/blob/lineage-18.1/init/README.md).
Do not restart this running Sensors 1.0 HAL as a live experiment: the
[framework's polling-HAL death path](https://github.com/LineageOS/android_frameworks_native/blob/lineage-18.1/services/sensorservice/SensorDevice.cpp)
fatally restarts its consumer instead of reconnecting the polling interface.
Use an orderly reboot to load the new service credentials.

This project explicitly boots permissive via BoardConfig.mk. The credential
and HAL tests establish DAC access for that current image. Enforcing-mode
input/sysfs policy remains unvalidated; this update does not broaden SELinux
rules or change the configured enforcement mode.

## Recovery update and undo

`tools/build/create_sensor_input_fix.py` builds a fix and exact undo for the
pinned 2026-10-25 ROM. The fix adds only
`vendor/etc/init/zz-grandppltedx-sensors.rc`; undo removes that file. Both check
the base ROM/SDK, exact original service file, service binary and sensor HAL,
and accept only an absent or exact known override. Unknown files and symlinks
are rejected before write/delete. The new file is root:root 0644 with the
vendor_configs_file label, matching the existing service configuration.

The real recovery updater passes install, reinstall, undo and repeated undo
on a disposable 64MiB ext4 RAM filesystem. All other 33 seeded files, including
the working camera/audio/mic/wake/graphics files, stay unchanged. Unknown
override, each unknown dependency and symlink rejection pass. Only the
block/mount/verifier/interpreter paths change in the fixture; no phone partition
is written by that test.

| Package | SHA-256 |
| --- | --- |
| grandppltedx-20261027-sensor-input-fix.zip | 0703330350b92e436b63662260a9e2be3f7f7bbd090c14f8ac91c340f15b6b40 |
| grandppltedx-20261027-sensor-input-undo.zip | a45e604b5be166f3018297f7f4c824fa5ee7bfd8cfdab311f0beb225bbe457c7 |

In TWRP, keep System unmounted and ZIP signature verification off. Install the
sensor-input-fix ZIP and reboot System without wiping. Keep undo accessible.
It restores the original service selection by removing only the added override.
Use the existing RAM recovery-reboot helper if needed. No ROM build or VPS is
required.

**The user confirms recovery installation, Android boot and working rotation.**
The battery then depleted and the phone shut down. After reconnection, ADB
verifies the installed override's exact SHA-256, sensor service input group
1004, and open accelerometer/proximity evdev descriptors. Proximity and other
physical regressions remain pending. Enable Auto-rotate
and use Gallery/browser: portrait, left landscape, portrait and right landscape.
Check camera preview/icon and saved photo/video orientation, then camera recording
with colour and sound, Wi-Fi, microphone and power/home wake. Proximity near/far
and call-screen behavior need separate physical checks; do not infer them from
successful accelerometer data. Gyroscope/step feature declarations remain
unconfirmed against hardware; only accelerometer and proximity enumerate.
