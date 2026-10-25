# Device Tree for Samsung Galaxy J2 Prime

-----
CURRENTLY NOT WORKING / BUGGY: 
* Most of the device functions do not work


DEVELOPMENT IN PROGRESS, MAY EAT YOUR CAT.

See [hardware bring-up notes](docs/HARDWARE_BRINGUP.md) for the Android 11 fixes,
source-patch instructions, measured failures, and required device tests.
The [GPS initialization fix](docs/GNSS_BOOT_FIX.md) permits normal boot;
the user confirms Wi-Fi and speaker playback. The latest tested correction is
the [screen wake/backlight fix](docs/BACKLIGHT_WAKE_FIX.md). Microphone recording
is silent, and the remaining hardware still needs testing.

SPECSHEET

Component | Details
---------:|:-------------------------
CPU       | MediaTek MT6737T
GPU       | Mali-T720MP2
RAM       | 1.5 GB
Storage   | 8 GB, 16 GB
Battery   | 2600 mAh
Display   | 540 x 960, 16:9 ratio
Rear Cam  | 8MP, Sony imx219 (selected kernel driver)
Front Cam | 5MP, Samsung s5k5e3yx (selected kernel driver)
