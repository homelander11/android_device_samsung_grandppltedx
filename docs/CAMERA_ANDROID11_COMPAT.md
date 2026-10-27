# Camera compatibility investigation (updated 2026-10-27)

Installation follow-up: both the combined camera/audio update and subsequent
video-colour update are installed. The user confirms normal boot and working
camera after the colour update. Its pinned helper is mapped from the system
partition, with no temporary bind; production dependencies and node ownership
match. See `CAMERA_COLOUR_UPDATE.md` for current verification. Earlier trial
and pending-install notes below describe the preceding investigation stages.

The user confirms **rear/front live preview and photo saving** with the
temporary camera candidate. The raw-frame fallback enables video recording.
Its later frozen/silent playback is resolved in the combined live test by
correcting the primary audio HAL's missing deep-buffer PCM name; new rear/front
clips play with sound and Camera closes/reopens normally. Default codecs and
normal hardware composition remain active. See `AUDIO_DEEP_BUFFER_FIX.md`.

A combined camera/audio fix and exact undo are ready for recovery/device
testing. The real ROM updater passes install, reinstall, exact undo, metadata
and rejection checks on a disposable RAM fixture. Actual TWRP installation,
production dependency names during a full camera session, reboot persistence,
flash and extended lifecycle testing remain pending. No permanent camera/audio
update has been flashed. Original files are restored after each live test.
Keep the stable hardware-fixes branch and paused GPS experiments separate.

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

10. Video fails during CCodec configuration with `BAD_VALUE`: the selected
    `c2.android.avc.encoder` only accepts ANW-buffer legacy metadata, whereas
    this HAL offers native-handle metadata. The failure occurs at both 720p
    and QVGA. `storeMetaDataInBuffers(true)` now reports `-ENOSYS` in the
    camera-only helper. Android's existing CameraSource fallback then selects
    raw YUV callbacks; `false` still reaches the original HAL, preserving its
    return status and actual raw-mode transition. Handles are never relabeled
    as ANW buffers. Isolated ARM tests verify that enabling metadata has no
    HAL side effects, and disabling forwards the device and success/error
    status for both cameras. A live candidate successfully starts and stops:
    MPEG4Writer reports 509 encoded video frames and 1481 encoded audio
    frames, both tracks stop with status zero, and the MP4 index is written.
    The first video playback/sound test passes, but subsequent front-video
    tests freeze on a frame with intermittent sound. These are not passing
    end-to-end front-video results. Software encoding is roughly 15 fps in
    the sampled recordings; both performance and playback remain open. This software encoder need not sustain 30 fps at 720p.

The framework rejects the legacy metadata in
[CCodec](https://github.com/LineageOS/android_frameworks_av/blob/lineage-18.1/media/codec2/sfplugin/CCodec.cpp),
and [CameraSource](https://github.com/LineageOS/android_frameworks_av/blob/lineage-18.1/media/libstagefright/CameraSource.cpp)
already implements the metadata-to-raw fallback used here.

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
load it. Use the matching vendor camera branch, which now contains the guarded
dependency/import changes and private ICU/Skia libraries. The device helper
and matching vendor changes must be built together.

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
guards are now applied to the matching vendor camera branch.

`tools/prepare_camera_android11.py VENDOR_LIB --icuuc ORIGINAL_ICU60 --output EMPTY_DIR`
reproduces the dependency/import changes with LIEF 0.16.6. Every input/output is
pinned in `tools/camera/android11-metadata.json`; unknown inputs are rejected.
The original vendor Skia and ICU libraries remain unchanged. Camera adapter
imports use a private `libskic.so`, `libicui60.so`, `libicu60.so` pair, and only
the camera dependency graph loads `libcamcx.so`. Protected code/data sections
and their addresses remain byte-for-byte unchanged for metadata-only edits.
The full camera-platform dependency graph passes an isolated on-device
`RTLD_NOW` check with these production names. End-to-end testing of these
names and a normal Soong build remain pending. Vendor provenance is in
`camera-android11-compat.json`; the ICU license is packaged in vendor/etc/licenses.

Live trials bind temporary files and use an independent deadline/process monitor
to restore original camera files on failure. The fresh v17 diagnostic trial later stalled after about four minutes; its
monitor captured a provider trace and restored all original files/permissions.
No new recorder-start error was retained in that trial. This stability issue
needs diagnosis before a permanent update is released; the successful photo
tests alone do not establish long-running or close/reopen reliability.
System_server stayed running and Android remained booted. No full ROM build, VPS use, kernel/boot/recovery
write, NVRAM/calibration change, or GPS test was needed. Private diagnostics are
not included in these repositories.

User-confirmed in the combined temporary trial: rear/front preview and a saved
photo from each camera, plus video recording/playback with sound after the
raw-frame correction. A later lifecycle trial returned normally from its
service checks, but the app UI displayed "Can't connect" after background/resume
and force-stop/reopen. Do not count service responsiveness as a passing reopen
test. Preview buffer diagnostics now report rejected busy transitions; no
unsafe reference dropping or forced buffer release was added.
Remaining device tests: repeated open/close and switching, video/audio recording, flash,
background/resume, reboot persistence, memory lifetime and performance. Recheck
Wi-Fi, microphone recording and power/home wake before releasing a fix ZIP.

## System-only package (ready for recovery/device testing)

`tools/build/create_camera_fix.py` generates a fix and exact undo for the pinned
20261025 ROM with its existing display, Light/backlight and microphone updates.
It checks every camera/audio/dependency hash before replacing anything, accepts
reinstallation, rejects symlink destinations and unknown libraries, and requires
the helper's ARM ABI exports and `DF_1_GLOBAL`. Ten camera libraries and the
primary audio HAL's pinned deep-buffer name are replaced;
four private runtime libraries, the ICU license and a node-ownership init file
are added. The original global vendor/framework Skia/ICU, microphone selectors, Wi-Fi,
calibration, boot, recovery and userdata are not modified.

The combined updater/payload passed install, reinstall, exact-original undo,
root ownership, file modes, SELinux labels, unknown camera/audio input and
symlink rejection before any payload replacement on a disposable 64 MiB ext4
RAM image. Only its block
path, mount/verification paths and shell were redirected for this fixture.
This is not an installation of the final ZIP in TWRP. The currently packaged
helper hash is `6ded15f2623a57e8ed748b86100d492fdc775825828839e9053c4f31986ef355`.
The combined live test now passes rear/front video playback with sound and
Camera reopening. Production-name end-to-end and reboot validation remain
required after installing the development update. It is not a fully validated
release for other users/devices.

## Playback graphics failure and recovery

The v21 front-camera tests save AVC/AAC tracks (54, 82 and 188 encoded video
frames in sampled clips), but the user reports a frozen playback frame and
intermittent sound. During playback, MediaTek MDP logs ION physical-address
lookup failures and blit error -6. The graphics composer then crashes at
`gralloc_backend_unregister+182`, RVA `0x3caa`, dereferencing a null module at
offset `0xc8`. Both register and unregister logged failed `hw_get_module`
lookups immediately beforehand. This restarted Android's framework; the
camera guard restored every camera file and original device-node ownership.
A normal reboot subsequently returned Android to the launcher. The persistent
microphone, wake and original gralloc hashes remain unchanged.

`tools/fix_gralloc_unregister.py ORIGINAL --output CANDIDATE` prepares a
**separate, unactivated** four-byte cleanup guard. It returns through the
existing epilogue after the existing failed-lookup error log. It never invents
a module pointer or frees an ION handle with an unknown client. Successful
lookup/cleanup, including the munmap-error path, remains instruction-for-
instruction unchanged. In the error case resources cannot be released through
a missing module; the guard prevents the null dereference rather than claiming
to repair that underlying lookup/import failure.

ARM emulation compares normal cleanup, a non-ION handle, munmap failure and
two module-lookup failures. The old error path reproduces the invalid read;
the guarded version returns with saved registers and stack intact. An isolated
on-device process also passes forced lookup failure with the guarded DSO and
the original legacy shims preloaded. No installed graphics file or display
service was changed. A conventional source probe is provided as
`grandppltedx_gralloc_cleanup_probe`; its normal Soong build remains pending.
Use `LD_PRELOAD=/vendor/lib/libshim_bionic.so:/system/lib/libutilscallstack.so`
and the vendor/system library search paths for this renamed diagnostic DSO.
The original gralloc path receives those shims through the ROM's loader map;
both /vendor and /system/vendor aliases pass isolated loading. No alias-map
change is justified by the observed failure.

The guard is not in the vendor tree or camera ZIP. It requires further graphics
validation; playback still needs an actual ION/composition investigation.

## Further playback isolation

A temporary SurfaceFlinger GPU-composition test plays an existing clip normally
(user confirmed), but a subsequent combined camera/GPU trial still produces
frozen playback and missing sound. Logs verify that GPU composition remained
enabled during that failed trial. It is not a validated playback fix. The
experimental boot service/script are retained only under
`tools/camera/composition/`; they are not installed by the product or ZIP.

Read-only on-device analysis of a failing saved clip finds monotonic AVC/AAC
packet timestamps, non-silent decoded PCM and 16 distinct decoded video frames
through `OMX.google.h264.decoder`. This establishes useful recorded content,
not working surface playback. `MediaTrackProbe.java` reports aggregate counts
without copying recordings or retaining decoded pixels/audio. Run through
`app_process`, which initializes the framework runtime; bare `dalvikvm` is not
a valid launcher for this probe's media JNI.

The next temporary test sets `debug.stagefright.ccodec=0` and restarts only
mediaserver to refresh its cached codec list. The log confirms selection of
`OMX.google.h264.decoder` for normal surface playback. User validation and
combined camera/codec tests are pending. No persistent codec change is active
in the source or ZIP yet. The supported property is documented in
[LineageOS Codec2InfoBuilder](https://github.com/LineageOS/android_frameworks_av/blob/lineage-18.1/media/codec2/sfplugin/Codec2InfoBuilder.cpp).

The failing stereo clip also has equal, positively correlated channels; its
mono downmix retains the same nonzero RMS level. Stereo phase cancellation is
not supported by these measurements. Do not alter the working microphone
selectors on the strength of a silent video-player result. Three synthetic
moving-pattern/tone clips (QVGA, VGA and 720p) are prepared for an independent
playback comparison. Their generation uses the installed PC FFmpeg, without
any Android/VPS build or user media export. The temporary codec test has
automatically restored its original property and restarted only mediaserver.
Its user-visible playback result remains pending.

## Confirmed deep-buffer playback mismatch

The later legacy-codec trial still gives mixed playback results. Focused logs
then expose a separate audio failure: the HAL tries to open PCM device -1.
Its isolated deep-buffer name `Deep_Buffer_PLayback` is absent from this kernel;
the implemented DL2 stream is `MultiMedia2_PLayback` (card 0/device 24).
`tools/fix_audio_deep_buffer.py` corrects only that same-length data string in
the pinned primary HAL. See `AUDIO_DEEP_BUFFER_FIX.md` for hashes and ARM tests.

The temporary correction successfully opens PCM 24. The user confirms moving
patterns plus tone, the previously frozen front clip, another existing clip,
and new rear/front camera recordings with moving playback and sound. Camera
also closes/reopens successfully in that combined trial. These tests retain
default codec selection and normal hardware composition. The earlier mixed
codec/GPU results do not justify activating those experiments.

Permanent camera/audio installation, production dependency names in a full
camera session, reboot persistence and extended lifecycle tests remain pending.
The separate gralloc null-cleanup issue is still documented above; this audio
correction does not repair its error path or establish every graphics route.
