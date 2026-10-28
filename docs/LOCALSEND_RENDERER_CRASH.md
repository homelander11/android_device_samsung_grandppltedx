# LocalSend startup crash: Impeller and legacy Mali, 2026-10-28

LocalSend 1.18.2 (versionCode64, ARM32) crashes on launch on the installed
LineageOS 18.1 build. Fresh reproduction and historical Android exit records
show native SIGSEGV on Flutter's `1.raster` thread, with the first three frames
inside `/vendor/lib/egl/libGLES_mali.so`.

## Measured cause

The driver SHA-256 is
`eadb237efe044552d89f125c8b489a9ca195bcc43f9b0d632efd2b16f0d0ec22`,
BuildId `b7112c7926410cf5efd5b5d336408b11`. Flutter's BuildId is
`3a12dddeb7d927ffd59fafb25152aac811dd47d1`.

The captured return chain reaches `glGetUniformLocation`'s internal path:
exported stub `0x468e0c` dispatches to `0x4848ec`, which calls `0x435f4c`,
then the name parser at `0x435c04`. At crash PC `0x435c60`, the ARM instruction
is `ldrb r1, [r10]` and the captured `r10` is zero. The null uniform-name
argument is passed from Flutter's calling frame near `0x5e64a0`. The evidence
identifies the immediate null-name lookup failure; it does not establish why
Impeller's preceding reflection/query produced that null name.

The controlled renderer comparison confirms an **Impeller/legacy-Mali
compatibility failure**. It does not justify globally patching the GPU driver
or claiming that all graphics paths are fixed.

## Tested workaround and its limit

* Default launch repeatedly produces the same SIGSEGV and stack.
* `enable-software-rendering=true` alone fails differently: Flutter aborts
  because Impeller does not support that software-rendering combination.
* A cold launch with `enable-impeller=false`, without software rendering,
  opens successfully. Flutter logs its explicit Impeller opt-out. The user
  confirms the interface and switching Receive/Send work. The test process
  later exits with Android reason10, `USER REQUESTED`, description `remove task`.
* Relaunching from the ordinary icon afterward produces the original native
  crash again. This proves the renderer override is **per launch**, not a
  permanent app/ROM fix. The app is reopened with the working override.

To repeat the tested workaround, substitute the J2 Prime's ADB serial. Do this
with no transfer in progress: force-stop terminates the app's current process.

```sh
adb -s J2PRIME_SERIAL shell am force-stop org.localsend.localsend_app
adb -s J2PRIME_SERIAL shell am start -W -n org.localsend.localsend_app/.MainActivity --ez enable-impeller false
```

The APK, app data, graphics driver and ROM files are unchanged. No transfer was
performed, so discovery and actual send/receive remain untested. No full ROM,
Flutter build or VPS was used. Private logs/APK copies stay outside Git.

## Permanent app-level option and source references

Flutter documents disabling Impeller in the application's manifest using
`io.flutter.embedding.android.EnableImpeller=false`. That is an app-build
setting; it has not been applied to the installed signed APK. Editing this ROM's
device manifest or HWUI renderer property would not set LocalSend's Flutter
engine option. A permanent solution for ordinary-icon launches remains open.
Newer Flutter releases can restrict Intent flags, so recheck this workaround
after app updates; acceptance was verified for this exact installed version.

An existing LocalSend issue reports the same Flutter BuildId and calling PCs
on another Samsung running LineageOS 18.1. This supports the compatibility
finding but supplies no verified permanent fix for this device.

* [LocalSend issue 3367](https://github.com/localsend/localsend/issues/3367)
* [Flutter Impeller deployment opt-out](https://docs.flutter.dev/perf/impeller)
* [Flutter engine flag delivery and release restrictions](https://docs.flutter.dev/release/breaking-changes/restrict-android-engine-flags-release-mode)
* [LocalSend 1.18.2 Android manifest](https://github.com/localsend/localsend/blob/v1.18.2/app/android/app/src/main/AndroidManifest.xml)
