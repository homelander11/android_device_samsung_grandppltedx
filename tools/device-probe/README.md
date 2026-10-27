# Access-only device probe

`make_gps_socket_probe.py OUTPUT` emits a static ARM EABI executable using the
device kernel's Linux syscall numbers, requiring only host Python. Before
running it as root in recovery, verify both paths below are absent. It drops
to UID/GID 1021 and exactly the configured GNSS supplementary groups, then
checks old-parent bind EACCES and new-parent bind/unlink success:

```
/data/misc/j2prime-gnss-bind-test.sock
/data/gps_mnl/j2prime-gnss-bind-test.sock
```

It creates only these diagnostic sockets, closes them and removes a successful
bind. It does not load the GPS HAL, start a daemon, request positioning or
access calibration. It inherits the current SELinux domain; the measured test
uses permissive recovery and establishes DAC, not enforcing-policy behavior.
See `docs/GNSS_BOOT_FIX.md` for the native wait/error path and results.

`light_probe.cpp`, built uninstalled by the `lights` target, loads the standard
Light implementation, invokes its real legacy-driver factory and enumerates
types. It does not call `setLight` or register a service. ELF constructors and
legacy module open functions run. Use matching Android libraries; see
`docs/LIGHTS_BOOT_FIX.md` for the measured missing-service/dependency errors.

`hal_link_probe.c` is a separate Android linker diagnostic built by the
`graphics` build target, with `installable: false`. It runs `dlopen(RTLD_NOW)`
and ELF constructors, but does not call HAL open/enumeration/EGL initialization.
It exits without unloading legacy DSOs, matching HAL service lifetime. Use
matching Android userspace, not recovery's older libraries. A successful load
does not establish hardware function. See `docs/DISPLAY_BOOT_FIX.md`.

`UidAccessProbe.java` uses Android's `Os.access()` after setting its real UID/GID.
It never opens, reads, or writes the target file. Run only through an authorized
root ADB session. Supplementary groups remain those of the launching process;
the audit's ADB process did not have the legacy BT calibration group 3008.

Compile with an existing Android SDK (API 30 or newer), convert the class with
D8 using `--min-api 30`, and put `classes.dex` in a JAR. The audit used the
already installed Java/Android SDK and built no Android system components.

```sh
adb push uid-probe.jar /data/local/tmp/j2prime-uid-probe.jar
adb shell dalvikvm -cp /data/local/tmp/j2prime-uid-probe.jar \
    UidAccessProbe 1002 1002 /data/nvram/APCFG/APRDEB/BT_Addr
adb shell rm /data/local/tmp/j2prime-uid-probe.jar
```

The 2026-10-25 test temporarily applied the exact ownership/mode from
`zz-grandppltedx-calibration.rc`, tested access, then restored the original
metadata in a `finally` block. A before/after SHA-256 comparison confirmed the
calibration bytes were unchanged. No calibration content or hash is published.
This establishes the DAC fix, not successful Bluetooth pairing or audio.

`MediaTrackProbe.java` analyzes an existing saved clip on the device. Build it
with the installed Android SDK and D8 (`--min-api 30`), package classes.dex in a
JAR, then run `CLASSPATH=PROBE_JAR app_process /system/bin MediaTrackProbe CLIP`.
It prints packet/timestamp statistics and aggregate decoded AAC levels. An
optional codec name, e.g. `OMX.google.h264.decoder`, replaces audio analysis
with a bounded 16-frame byte-buffer decode/diversity check. No decoded media
is saved. Use app_process rather than bare dalvikvm for framework media JNI.
A decodable non-silent file does not prove normal display/speaker playback.

`grandppltedx_gralloc_cleanup_probe` is a separate-process fault-injection
target, not installed in the product. Prepare the exact candidate with
`fix_gralloc_unregister.py`, verify its pinned hash, and put it at
`/data/local/tmp/j2prime-gralloc-unregister-candidate.so`. The renamed DSO needs
`LD_PRELOAD=/vendor/lib/libshim_bionic.so:/system/lib/libutilscallstack.so` and
`LD_LIBRARY_PATH=/vendor/lib:/system/lib`, since it does not use the installed
gralloc path's automatic shim injection. The probe exports a failed module
lookup and checks safe return. Its conventional Soong build is pending; an
equivalent locally built constructor harness passes on the phone. Do not load
the fault-injection harness into any graphics service.
