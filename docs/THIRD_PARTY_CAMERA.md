# Third-party camera lifecycle compatibility (2026-10-27)

The Play Store app `com.photo.android.camera` 6.8.3 initially showed black
video preview and left the built-in Camera unable to connect. Its photo path
uses Camera API1; later traces also show Android's Camera2 legacy wrapper.
The requested preview/video sizes are advertised by the HAL. Compatibility
therefore requires more than rejecting an unsupported resolution.

## Preview containers and callback rebinding

The old adapter retained dequeue markers after a client closed. Read-only
bookkeeping inspection found map-only containers with stale dequeue markers,
no operations in flight and no external strong references. Android 11's HIDL
`CameraDevice::open` registers the callbacks once per open. At that boundary,
`j2prime_camera_preview_new_session` can retire only those unreferenced metadata
containers. It never releases the borrowed Android buffer handles or calls an
old window. In-flight operations, active reconfiguration and external references
still prevent retirement.

HIDL keeps the embedded preview ops address when replacing its remote callback.
A quiescent same-ops rebind now forwards through the existing adapter without
freeing its containers. Geometry/count/usage changes retain their live-buffer
ownership checks. Separate camera IDs retain separate state.

With the installed graphics guard, the session-only helper passes isolated ARM
contracts and live preview/app switching. The user confirms built-in recording,
playback, moving video, colour and sound. The third-party app can also record a
short clip, but returning from playback exposes the separate autofocus deadlock
below. The first earlier trial had been interrupted by the independently
identified graphics cleanup crash; it was not treated as proof of compatibility.

## Autofocus lock cycle

The saved stall puts the provider's command thread in
`CallBack3A::enableAFMove(bool)`, waiting for its mutex. Its AF thread holds that
same mutex in `doNotifyCb` while a synchronous HIDL notify waits for the camera
service. The camera service holds its client lock while sending the enable
command. This cycle blocks new camera connections and explains the black preview
after playback. The rollback controller captures native stacks before restarting
the provider. No recordings are exported.

The pinned 28-byte setter only locks the mutex at object offset 0x8, writes the
independent aligned 32-bit enable flag at 0xc, then unlocks. The provider-scoped
shim publishes that same 0/1 flag using a relaxed atomic word store, avoiding the
callback mutex. It changes no callback registration or object lifetime and does
not suppress focus, shutter, error or data notifications. An already-started
notification can complete after the flag changes; Android still filters unwanted
messages. The legacy reader's aligned ARM LDR sees either flag value.

`tools/camera/preview-session.json` pins the camadapter hash, symbol, offsets and
helper hashes. Native sentinel tests confirm true/false writes change only the
flag; the existing callback and colour contracts pass. ARM disassembly contains
a word store with no mutex operation. A read-only live GOT check confirms the
vendor setter dispatches to the corrected helper. The vendor ELF's first LOAD
segment has virtual address 0x3000, accounted for when deriving its load bias.
Live combined lifecycle validation and installation status are recorded in
`CAMERA_SESSION_UPDATE.md`.

These changes target this pinned ARM32 HAL on Android 11. They do not establish
compatibility with all third-party apps or fix the preceding graphics module/
ION import errors. The separate null-module graphics cleanup guard is installed,
reboot-tested and included in the vendor source; see `GRALLOC_CRASH_GUARD.md`.

## Recovery of a blocked provider

Force-stopping the two known camera apps and restarting only
`vendor.camera-provider-2-4` restores the built-in camera. The tested root helper
`tools/device-probe/restart_camera.sh` has `--check` and explicit `--restart`
modes for this SM-G532G/grandppltedx Android 11 image. It neither uninstalls apps
nor clears their data. Always select the exact J2 Prime ADB serial:

```sh
adb -s YOUR_J2_PRIME_SERIAL shell sh /data/local/tmp/j2prime-restart-camera.sh --check
adb -s YOUR_J2_PRIME_SERIAL shell sh /data/local/tmp/j2prime-restart-camera.sh --restart
```
