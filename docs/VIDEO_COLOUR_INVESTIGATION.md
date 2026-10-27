# Video colour inversion (2026-10-27)

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
Existing ZIPs lack a colour correction; the candidate is still unverified on
a live recording.
