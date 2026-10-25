# LineageOS 18.1 hardware bring-up

## Scope and baseline (2026-10-25)

Sources audited: device `cf62bac`, vendor `d3a6207`, kernel `a75b32e2` on
`lineage-18.1`. Development branch: `codex/lineage-18.1-hardware-fixes`.
The project contains the three component trees, not a full Android checkout.
No ROM build or flash was performed. Windows checkouts are not suitable for an
Android build; the kernel also has reserved filenames and case collisions.

A root-authorized SM-G532G was available through ADB, running Android 11/API 30,
LineageOS `18.1-20260827-UNOFFICIAL-grandppltedx`, with SELinux permissive.
Logs were collected read-only. They contain both October 18 boot entries and
October 25 reproductions. Raw logs and device-specific calibration stay local.
The running image differs from these repositories: it contains
`camera.mt6735.so`, which is absent from this vendor branch.

## Completed configuration changes

* Preserve `force_connect_cmd=1` in **both** shipped supplicant configurations.
  The connected phone already uses it in its overlay; the upstream files did
  not. Keep the other Wi-Fi parameters, legacy HAL, and kernel driver unchanged.
* Change the Bluetooth SCO microphone profile from an output channel mask to
  `AUDIO_CHANNEL_IN_MONO`. The old mask cannot describe a capture device.
* Add `tools/validate_configs.py`: parses device XML, checks audio route endpoints
  and channel directions, and protects the Wi-Fi driver parameters.

These changes are statically validated. They do not establish working audio or
Bluetooth on a newly built image.

## Observed blockers and investigation

| Area | Evidence from attached device | Required validation |
| --- | --- | --- |
| Bluetooth | Repeated `parse_read_local_extended_features_response` aborts; HCI status `0x30`. `BT_Addr` access also fails with errno 13. | Feature-page handling, stable enable/disable, classic pairing, BLE, A2DP, SCO, persistent factory address. |
| Audio | Primary MTK HAL is mapped and audio HIDL 4.0 is registered. `create_audio_patch` fails and logs `routing=10` even for speaker. Calibration access failures also appear. | Routing ABI, speaker/earpiece/headset, playback and microphone capture, calls. |
| Camera | Zero enumerated cameras; provider `legacy/0` is advertised as hwbinder but no service starts it. Published vendor tree lacks the camera HAL. | Restore a matched HAL/dependency set, resolve framework ABI, preview and capture on both sensors. |
| GNSS | GNSS HIDL and `mnld` run. Legacy HAL depends on framework-private libraries and talks to `/data/gps_mnl` sockets. | Active request, satellite acquisition outdoors, NMEA, time/location injection and SUPL. Service registration alone is insufficient. |
| USB audio | `audio.usb.default.so` cannot resolve `profile_get_highest_sample_rate`. | Audit `libalsautils` installation and exports; test a USB audio device. |
| Widevine | Legacy protobuf `empty_string_` symbol cannot resolve. | Check the existing v29 compatibility library mapping and encrypted playback. |
| Security | Permissive kernel cmdline, ignored neverallows, insecure ADB defaults. | Dedicated SELinux bring-up before calling this a production-ready ROM. |

Do not enable `CONFIG_BT` merely because it is disabled: this MTK stack uses
`/dev/stpbt` in userspace, and `CONFIG_MTK_COMBO_BT=y` is already selected.
Likewise, `CONFIG_MEDIA_CAMERA_SUPPORT` is not the MTK camera switch;
`CONFIG_MTK_IMGSENSOR=y` and the imx219/s5k5e3yx drivers are already selected.

The audio service name `android.hardware.audio@2.0-service` is an Android 11
phony alias for `android.hardware.audio.service`; that service probes 6.0, 5.0,
4.0 and 2.0 implementations. Renaming it does not fix the observed audio issue.
`maxActiveCount=0` means unlimited, not disabled capture.

## Sources consulted

* [LineageOS 18.1 audio service](https://github.com/LineageOS/android_hardware_interfaces/blob/203e87a39c04f30bc1f09f6c2306b701d6b97fe0/audio/common/all-versions/default/service/service.cpp)
  (use the branch link if a pinned revision is unavailable):
  [lineage-18.1](https://github.com/LineageOS/android_hardware_interfaces/blob/lineage-18.1/audio/common/all-versions/default/service/service.cpp).
* [LineageOS 18.1 Bluetooth parser](https://github.com/LineageOS/android_system_bt/blob/lineage-18.1/hci/src/hci_packet_parser.cc).
* [Sony Xperia L1 MT6737T tree](https://github.com/SonyMTKDev/android_device_sony_pine-deprecated/tree/a0fc73df002090629d12832ce3c8aae8980e4bf1).
* [Motorola MT6737 common tree](https://github.com/Motorola-MT6737/android_device_motorola_mt6737-common/tree/8622aa4d1d42e330edb50c49025cb4db637bdd90).
* [LineageOS MT6735 common tree](https://github.com/LineageOS/android_device_cyanogen_mt6735-common/tree/0033d5b1d2b2065adfb4a0b116db1c77e17fa302).

Older device trees establish MTK interfaces and service requirements; they are
not evidence that their blobs or framework patches are Android 11 compatible.
The existing `patches/` directory includes old framework paths and must not be
blindly applied to an Android 11 checkout.

## Lightweight validation

From an Android/project root:

```sh
python device/samsung/grandppltedx/tools/validate_configs.py
git -C device/samsung/grandppltedx diff --check
```

After building changed components on Linux, test Wi-Fi association/reconnection
first. Then test one subsystem at a time and retain before/after logs. Do not
publish raw bugreports, Wi-Fi configurations, location dumps, NVRAM, or EFS data.
