# Third-party video-mode failure (2026-10-27)

The Play Store app `com.photo.android.camera` version 6.8.3 connects through
Camera API1, then shows black preview and can leave the built-in Camera unable
to connect. It requests advertised preview/video sizes, so this is not yet
explained as a simple unsupported-resolution request. Third-party compatibility
remains unresolved; the working default-camera/colour fixes do not establish
support for every camera app.

Force-stopping both apps and restarting only `vendor.camera-provider-2-4`
restores the built-in camera. The user confirmed rear/front preview after that
recovery. `tools/device-probe/restart_camera.sh` provides a device-gated root
`--check` and explicit `--restart` for this Android 11 SM-G532G. It neither
uninstalls apps, clears their data nor changes firmware. It has been tested on
the phone. Use the J2 Prime's exact ADB serial when other devices are connected:

```sh
adb -s YOUR_J2_PRIME_SERIAL shell sh /data/local/tmp/j2prime-restart-camera.sh --check
adb -s YOUR_J2_PRIME_SERIAL shell sh /data/local/tmp/j2prime-restart-camera.sh --restart
```

## Evidence and rejected experiment

The adapter reports a busy preview window during the new client's setup. After
both clients close, read-only bookkeeping inspection finds stale dequeue markers
on two rear and one front containers, with no operations in flight and only map
references. An experimental session-reset/rebind helper passes isolated ARM
tests, but its live trial is interrupted by a graphics-composer crash. This is
not a validated compatibility fix. The product source was restored, the
experiment archived privately, and no experimental helper update was published.

The temporary controller detected the composer restart and restored the
installed colour helper. After the subsequent full reboot, its SHA-256 again
matches `16938d52548fad5101abcb016f00e162a8f0c075b0b2fd3855e91525f3d81176`
with no file bind mount. The built-in camera was reopened. No recordings were
exported.

The native tombstone identifies SIGSEGV at `gralloc_backend_unregister+182`,
RVA 0x3caa, with a null module pointer and fault address 0xc8. Failed module
lookup errors occur before preview-window registration, so the crash does not
establish that the experimental session reset itself is faulty. It matches the
earlier independently captured graphics cleanup bug. Resolve/test that stability
path before further risky app testing; see `GRALLOC_CRASH_GUARD.md`. The
underlying import failure and camera-session compatibility still need fixes.
