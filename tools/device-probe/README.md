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
