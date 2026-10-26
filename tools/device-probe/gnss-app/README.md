# Foreground GPS diagnostic

This small app requests the real `gps` provider while visible and reports
satellite counts, strongest C/N0, NMEA count, first-fix time, fix count and
accuracy. It also reads only GSV field 3 (satellite total) and GSA field 2
(fix mode) to distinguish an empty receiver report from missing satellite
callbacks. These are session maxima; GSV totals from different constellations
are not added together. Unknown values display as -1. It never reads
coordinates, logs NMEA contents, stores a recording
or requests Internet/storage access. Mock fixes are excluded. Pausing/stopping
the app removes its requests; a session stops automatically after ten minutes.
The screen stays awake only during the test. Progress logs use `J2PrimeGpsProbe`.
Each report includes monotonic elapsed milliseconds for its request session,
so device clock changes and pause/resume resets do not hide the test duration.

Build with an existing Android SDK/JDK, without building Android or downloading
dependencies:

```sh
python device/samsung/grandppltedx/tools/device-probe/gnss-app/build.py \
  --sdk /path/to/android-sdk --out-dir /path/to/local/probe-build
adb install -g /path/to/local/probe-build/j2prime-gps-probe.apk
adb shell timeout -s KILL 4 cmd activity start-activity -n dev.j2prime.gnssprobe/.MainActivity
adb logcat -d -s J2PrimeGpsProbe:I '*:S'
```

Defaults are build tools 35.0.0/platform android-35; the app targets Android 11
and uses API-24-compatible location callbacks. The build creates a disposable
local debug signing key, using the conventional public debug password. Keep
build output and keys outside source control. The APK is not included in a ROM.

The local build, APK signature check, installation, permission grant and
foreground request were verified on SM-G532G. The initial outdoor test returned
zero satellites; vendor crashes were then identified. Successful callback
registration alone does not prove the engine is navigating or positioning.
The NMEA-only live trial later hung system_server during GNSS service lookup;
it was rolled back, Android recovered, and Location was left off. See
`docs/GPS_POSITIONING_FOLLOWUP.md` before further service tests.

With both compatibility candidates temporarily mounted, a subsequent 60-second
foreground test received hundreds of NMEA callbacks without restarting Android
or either GPS process. Two later app request stop/start cycles also kept both
processes alive. This verifies data flow and those request cycles, not satellite
reception, Location-setting toggles, cold boot or successful positioning.

The subsequent newer week-rollover engine trial reported one satellite through
both GnssStatus and GSV, with 12.8 dB-Hz C/N0, zero used and no fixes. Its final
session report had 353,526 elapsed milliseconds and 3,532 NMEA callbacks.
The probe was stopped and original GPS libraries restored afterward. A real
GPS position fix remains unverified.

Use a host-side subprocess timeout for log collection when USB may disconnect.
The bounded native `cmd` launch avoids an `am -W` shell wrapper that remained
blocked during an earlier trial. Keep the activity visible and check for
`PROGRESS` records; callback registration alone is insufficient.

Remove the app when diagnostics finish:

```sh
adb shell am force-stop dev.j2prime.gnssprobe
adb uninstall dev.j2prime.gnssprobe
```
