# Video colour inversion (2026-10-27)

The correction now passes temporary device tests. The camera provider's mapped
helper inode is verified, and logs confirm YV12-to-I420 conversion for camera
IDs 0 and 1. The user confirms correct red, moving video and sound on both
cameras, normal photo colours and a lower-resolution rear clip. Actual tested
buffers are 1382400 bytes (1280x720) and 115200 bytes (320x240); the latter was
reported by the UI test as a lower-quality option. Do not claim a device-verified
640x480 test from that result. Permanent colour installation/reboot, other
sizes, longer recording and normal Soong compilation remain pending.

The user installed the combined camera/audio update in TWRP and booted Android.
Installed helper, camera client, private Skia and primary-audio hashes match the
package; camera node ownership also survives reboot. Both cameras record video,
but colours are blue and a red test object becomes blue. Photos look normal;
video thumbnails are affected too. This remains an open video bug.

Parameters advertise `video-frame-format=yuv420p`, no effect and automatic white
balance. Android maps that format to I420 and its AVC encoder expects Y/U/V:
[CameraSource](https://github.com/LineageOS/android_frameworks_av/blob/lineage-18.1/media/libstagefright/CameraSource.cpp),
[C2SoftAvcEnc](https://github.com/LineageOS/android_frameworks_av/blob/lineage-18.1/media/codec2/components/avc/C2SoftAvcEnc.cpp).
The red-to-blue inversion supports a chroma-order mismatch rather than proving
defective hardware. No permanent colour correction has been installed.

## Read-only probe

`tools/device-probe/VideoColourProbe.java` decodes at most eight frames through
`OMX.google.h264.decoder` and reports only Y/U/V averages and plane strides.
It does not export recordings or save decoded frames. Build with the local
SDK/D8, then run the JAR using `app_process`:

```sh
CLASSPATH=/data/local/tmp/j2prime-colour-probe.jar app_process /system/bin \
  VideoColourProbe /sdcard/DCIM/Camera/TEST_VIDEO.mp4
```

The probe runs on the phone. Generated red measures Y=81/U=90/V=240; blue
measures Y=41/U=240/V=110. The red-object recording instead has central-region
U around 163 and V around 114. Missing input returns an explicit error. Earlier
missing-reference runs exited through Android's exception handler, not a proven OOM.

## Pending correction

Limit conversion to validated raw-video buffers, preserving luminance,
callback ownership/index/time, preview/photos and audio. The pinned `RecImgBuf`
constructor copies the memory descriptor at RVA 0x1f0e4. Identify its heap
independently of the copied descriptor's address. Android may also retain its
default YUV mode without a disable call after metadata rejection. Cover both
cases and multi-buffer boundaries in the isolated ARM tests.

The first trial never logged a conversion, so unchanged colours did not test
U/V correction. Further temporary testing has an independent rollback timer.
Require a conversion log and fresh correct-colour videos from both cameras,
then preview/photo/audio and resolution/lifecycle checks before packaging.
The earlier combined camera/audio ZIP lacks this colour correction. The
helper-only update will retain that installed update and replace only libcamcx.

## Verified implementation

The pinned raw video is Y/V/U while Android consumes the advertised Y/U/V.
`memory_context.c` swaps the two chroma quarters only for registered raw-video
heaps, known frame sizes and valid indices. Allocation size/count and the
complete heap size must agree. It preserves luminance, descriptor, ownership,
timestamps, cookies and non-video callbacks. Matching uses the data/handle
identity because the HAL copies descriptors. Duplicate timestamps are not
swapped twice, and unknown layouts pass unchanged.

Before rejecting metadata, the adapter explicitly calls the original raw-mode
setter and records its status. This covers Android retaining default YUV mode
without an additional disable call; explicit disable callers still receive
the real status. The isolated ARM test covers this sequence, copied memory,
multi-buffer boundaries, invalid indices/heaps/modes, other-camera isolation,
duplicate timestamps, unknown handles and unchanged callback arguments.
The helper retains all thirteen previous exports and the same dependencies.
`tools/camera/video-colour.json` pins the tested old/new helper hashes.

A temporary watchdog restored the helper after one slow camera dump during
capture. The final trial requires two consecutive dump timeouts; its front/
lower-resolution test stays healthy. Test setup now forces a provider restart
after binding and verifies its mapped inode. Restoration restarts it after
unmounting, using scoped lazy detach when the file mapping is busy. File hashes
alone do not establish which version an already-running process has mapped.
