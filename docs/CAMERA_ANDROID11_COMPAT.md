# Camera compatibility investigation (2026-10-26)

The user now confirms **rear/front live preview and photo saving** with the
temporary v15 candidate. Video currently fails with "could not start media recorder" in the app; its
cause is still under investigation. Flash, repeated reopen and reboot persistence
remain separate test requirements. This branch records the compatibility work;
it is not yet a permanent camera release. No camera update has been flashed.
The original camera files are restored after each live test. Keep the stable
hardware-fixes branch and the paused GPS experiments separate from this work.

## Confirmed failures

1. `libcam_platform.so` cannot load because vendor Skia imports ICU 60 symbols,
   while Android 11 provides a different ICU ABI. A matching, privately named
   ICU 60 pair passes `RTLD_NOW` loading of Skia and the complete platform
   library. Two Skia UChar-pointer mangles also need correction. This restores
   valid rear/front camera metadata during live tests. Do not rename ICU major
   symbols to Android 11's version or replace the framework ICU libraries.
2. Old camera libraries call `android::Thread::run` with a null default name;
   Android 11 aborts on that input. `libcamcx` provides a uniquely named adapter
   that supplies `MtkCam` only for a null name. Eight pinned camera libraries
   need their import redirected to it. The framework Thread implementation
   stays unchanged.
3. Vendor image allocators pass a null `request_memory` cookie. Android 11's
   HAL1 HIDL wrapper dereferences that cookie. The callback-registration adapter
   binds a separate allocator/cookie pair to each physical camera, preserving
   explicit cookies and all allocation arguments. The physical ID at object
   offset `0xbc` is specific to the pinned `libcam.device1.so` constructor.
4. The optional legacy CPU boost bridge allocates 52-byte Binder Parcel objects
   on its stack. An isolated probe of this ROM's Parcel constructor writes
   60 bytes. Entering the bridge corrupts saved registers and crashes preview
   startup. The camera CPU-controller adapter reports initialization unavailable
   so its existing failure path skips that incompatible bridge. Kernel CPU
   frequency and thermal control continue normally; camera performance still
   needs testing. Capture's noise-reduction algorithm also calls the legacy
   bridge directly. Its register-save corruption caused a null object pointer
   in `AppIIR::NRInit`, after precapture had completed. `performance.c` supplies
   camera-only C entry points: registration returns the documented invalid
   handle `-1`, and the void boost/configuration/cleanup calls do nothing.
   ARM emulation of the actual NRInit failure branch confirms successful
   algorithm initialization with no boost; noise reduction is not disabled.
   The subsequent rear/front capture tests save photos successfully.
5. The bundled SensorListener factory deliberately returns null. EIS startup
   dereferences it. A private candidate guards both EIS variants, clears their
   sensor-enabled flags when unavailable, and continues the image-processing
   initialization. ARM emulation verifies null handling and matches the original
   valid-listener calls, results and live registers. The live test advances to
   preview-buffer setup. Autofocus initialization also dereferences this null
   factory. A four-byte guard marks only its in-memory motion-assist option
   unavailable before the existing disabled path. The constructor initializes
   both sensor-enabled flags to zero; ordinary image-based autofocus remains
   enabled. ARM checks cover four option values, and the live trial passes the
   former AF initialization crash. No calibration file is changed.
6. Preview crashed in `NSDisplayClient::StreamImgBuf` while taking a strong
   reference to a native buffer. The HAL subtracts `0x3c` from the returned
   handle pointer and calls the recovered buffer's `incRef`. Android 11's HAL1
   wrapper instead returns a pointer into its map of standalone handles. That
   pointer has no enclosing native-buffer object. `preview_window.c` supplies a
   96-byte legacy container, maps enqueue/cancel/lock to the original handle
   pointer, records geometry/usage, and tracks the HAL's strong references.
   Reconfiguration is refused while buffers are outstanding. The isolated ARM
   test covers both cameras, reference lifetime, geometry, handle translation,
   allocation-failure cancellation, failed callbacks, passthrough operations
   and teardown. The live trial passes the previous native-buffer crash.
7. Preview then waits indefinitely in `PQClient::assertStateLocked` for an absent
   picture-quality service. The provider-only adapter returns `-ENODEV` through
   its existing error path. `getTDSHPFlag` skips its remote call and the image
   engine keeps its initialized defaults. The live trial passes this wait;
   optional legacy picture-quality processing remains unavailable.
8. The separate camera provider cannot read `/dev/devmap` (chip/device-info
   ioctl driver) or open `/dev/MTK_SMI`. Preserve the devmap read-only mode and
   system-group access, assigning its owner to cameraserver. Retain media
   ownership of SMI and use the camera group. Both changes are tested as exact
   temporary ownership changes with independent rollback. Preview startup
   advances, and the subsequent combined trial delivers live frames on both cameras.
9. Saved dumps from both processes confirm a photo-capture lock cycle:
   CameraClient holds its lock in takePicture, MTK waits synchronously for
   precapture, and internal AF completion waits for that same client lock in
   `lockIfMessageWanted`. A capture-depth guard omits the redundant public focus
   and focus-move notifications generated inside that synchronous capture scope.
   Normal focus callbacks outside capture, other cameras, shutter, error, image
   and timestamp callbacks retain their original arguments and ordering.
   Isolated tests cover nested capture scopes, cleanup on an error return,
   cross-camera delivery, null callbacks and unchanged cookies. A camera client
   depending on a separate public AF completion while capture is already in
   progress still needs compatibility testing.

An earlier trial froze the UI after a capture request. All temporary files and
device-node ownership were restored; a normal reboot recovered the UI. The user
confirmed the recovery before the revised capture test. The final photo tests
advance through precapture and noise reduction successfully. Keep the rollback
monitor in place for additional bring-up; do not treat a live process alone as
proof of a responsive camera.

The Android 11 wrapper's `sDequeueBuffer`, `sEnqueueBuffer`, and `sCancelBuffer`
are in [LineageOS hardware/interfaces](https://github.com/LineageOS/android_hardware_interfaces/blob/lineage-18.1/camera/device/1.0/default/CameraDevice.cpp).
The legacy buffer layout is in [the Android 6 window header](https://github.com/LineageOS/android_system_core/blob/cm-13.0/include/system/window.h).

## Source module and validation

`libshims/camera/Android.bp` builds the 32-bit vendor-only `libcamcx` module.
`-z global` is required for the pinned Cam1 vtable relocations to resolve the
callback and CPU-controller adapters. Only the camera dependency graph should
load it. Vendor activation still requires guarded dependency/import changes;
merely packaging this module does not fix preview.

A small ARM build using the installed SDK compiler, LLVM and linker passed
on-device isolated tests for null/non-null thread names, return values and
arguments, both camera allocator slots, explicit-cookie overrides,
re-registration, null callback removal and unsupported physical-ID passthrough.
The combined adapter loads in the real provider. Live logs confirm callback
registration for both camera IDs and progress past the previous allocation and
CPU-controller crashes. Source test targets are
`grandppltedx_camera_context_test` and `grandppltedx_camera_preview_test`; they
are not installed by the product. The normal Soong builds of the helper and
these test targets still need validation. These tests do not prove concurrency or close/reopen
correctness.

`tools/fix_camera_sensor_startup.py VENDOR_LIB_DIR --output CANDIDATE` reproduces
the combined EIS/AF guards without editing the input. `--apply` is an explicit
in-place option. It pins both the feature library and the deliberately-null
SensorListener implementation, rejects other pairs, and is idempotent. Exact
regions, before/after hashes and assembly are under `tools/camera/`. These
guards are not yet applied to the production vendor tree. Activating the source
module also requires the private ICU and scoped camera import changes described
above; merely rebuilding this checkpoint does not produce a working camera.

Live trials bind temporary files and use an independent deadline/process monitor
to restore original camera files on failure. The last trial restarted camera
and media services after the preview-buffer crash; system_server stayed running
and Android remained booted. No full ROM build, VPS use, kernel/boot/recovery
write, NVRAM/calibration change, or GPS test was needed. Private diagnostics are
not included in these repositories.

User-confirmed in the combined temporary trial: rear/front preview and a saved
photo from each camera. Video startup fails and is being investigated.
Remaining device tests: repeated open/close and switching, video/audio recording, flash,
background/resume, reboot persistence, memory lifetime and performance. Recheck
Wi-Fi, microphone recording and power/home wake before releasing a fix ZIP.
