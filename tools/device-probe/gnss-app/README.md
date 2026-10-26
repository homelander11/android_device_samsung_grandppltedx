# Foreground GPS diagnostic

This small app requests the real `gps` provider while visible and reports
satellite counts, strongest C/N0, NMEA count, first-fix time, fix count and
accuracy. It never reads coordinates, logs NMEA contents, stores a recording
or requests Internet/storage access. Mock fixes are excluded. Pausing/stopping
the app removes its requests; a session stops automatically after ten minutes.
The screen stays awake only during the test. Progress logs use `J2PrimeGpsProbe`.

Build with an existing Android SDK/JDK, without building Android or downloading
dependencies:

```sh
python device/samsung/grandppltedx/tools/device-probe/gnss-app/build.py \
  --sdk /path/to/android-sdk --out-dir /path/to/local/probe-build
adb install -g /path/to/local/probe-build/j2prime-gps-probe.apk
adb shell am start -W -n dev.j2prime.gnssprobe/.MainActivity
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

Remove the app when diagnostics finish:

```sh
adb shell am force-stop dev.j2prime.gnssprobe
adb uninstall dev.j2prime.gnssprobe
```
