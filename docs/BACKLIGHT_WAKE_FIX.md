# Dark screen after wake: brightness conversion (October 26, 2026)

The user confirms normal boot, Wi-Fi and speaker playback. After screen-off,
power/home initially left the panel dark or appeared to wake it after several
seconds. Key layouts already mark both keys WAKE. Fresh logs show prompt key
dispatch, HWC power-on and panel resume, but actual brightness remains zero.

## Cause and correction

The Samsung `lights.mt6735.so` BACKLIGHT callback at Thumb `0x1665` loads the
entire `light_state_t.color` word and sends it to a signed-decimal sysfs writer.
Android 11 encodes brightness as `0xffBBBBBB`; its standard HIDL wrapper
preserves that color. For example, level 144 becomes a negative signed number
instead of 144. The kernel rejects it. HWC still turns the panel off, but wake
can restore brightness zero. Root writing the existing configured level (102)
immediately restores LED, panel and actual brightness to 102.

Replace `ldr r5, [r1]` with `ldrb r5, [r1]` at file offset 5736 (`0x1668`):
`0d68` becomes `0d78`. Only byte 5737 differs. On little-endian ARM, B equals
the brightness because Android repeats it in R/G/B. All 256 grayscale levels
decode exactly. This follows the framework brightness contract; it does not
implement weighted luminance for arbitrary nongray BACKLIGHT colors. Other
callbacks and notification colors are unchanged.

The earlier unused RIL dependency removal remains. Relative to that driver,
all other code, ELF headers/symbols/dependencies and the 22,196-byte size are
identical. This update changes no Wi-Fi, audio, GPS, boot image or calibration.

* Input SHA-256: `d83f7a9ed24076fc5d953ec964f5b2e698c342a4ac8acd18980feae60fe36be0`
* Corrected SHA-256: `9d2a8737e6ee146cdf7e74b0233fc38efd614d0a9e6d79832688a2cce2b81b75`

Vendor `lights-brightness-provenance.json` records exact scope/provenance.
`tools/fix_lights_brightness.py LIBRARY --apply` accepts the pinned pristine
blob, dependency-corrected blob or its own output; unknown inputs are rejected.
The dependency helper recognizes the final blob without reverting brightness.
New `lights`/`bacon` builds use `verify_lights.py --require-brightness-fix`.
The default checker still supports reproducing the historical first Light ZIP.

## Validation

A temporary file bind and restart of only the Light service loaded the corrected
driver on the running phone. Android set level 128 and restored the user's 102.
Three sleep/wake cycles passed; actual brightness was 102 at every 0.5-second
post-wake check. The user independently confirmed power/home now wake normally.

The overlay was detached afterward with lazy unmount because the driver remains
mapped. The tested process keeps its mapping until it exits; the underlying
installed driver still hashes to the old input. This live correction therefore
disappears on reboot or Light-service restart until the persistent ZIP is
installed. No firmware partition was remounted writable or flashed in this test.

The full native updater passed install, reinstall, exact-original undo,
0644/root ownership/vendor_file labeling and unknown-input rejection on a
16 MiB ext4 RAM fixture under Android. Test substitutions were the verified
RAM loop device, `/data/local/tmp` for recovery's `/tmp`, and `/system/bin/sh`
for `/sbin/sh`. All validation/extraction/metadata operations ran. This differs
from testing the unchanged ZIP in TWRP. Android loop attachments autoclear on
unmount; the harness reattached and verified the same RAM image at each step.
Host checks cover exact byte scope, 256 grayscale values, ELF metadata, helper
idempotence/rejection and strict packaged Light checks. No build/VPS was used.

## Persistent update and remaining tests

`create_backlight_fix.py BASE_ROM PATCHED_HAL PREVIOUS_LIGHT_HAL --out-dir DIR`
generates `grandppltedx-20261026-backlight-fix.zip` and its undo, verifying input
hashes. The ZIP pins the 20261025 ROM/API 30, display shim, Light service, GNSS
init files and corrected GPS module. Only the Light driver is replaced.

Install after display v2, Light and GPS boot updates, with TWRP ZIP signature
verification off, then reboot System; no wipe. Undo restores the earlier Light
driver and its backlight bug while keeping the service/other boot fixes.
Historical GPS/Light undo ZIPs pin earlier driver versions; undo this backlight
update first if those older development packages are needed.

Persistent install/reboot is pending. Afterward test power/home repeatedly,
brightness slider/dimming, screen timeout, suspend/resume and charging.
Microphone recording remains silent; calls, GNSS positioning, Bluetooth pairing
and camera operation remain unverified.

References: [Android 11 grayscale encoding](https://github.com/LineageOS/android_frameworks_base/blob/lineage-18.1/services/core/java/com/android/server/lights/LightsService.java),
[JNI service lookup](https://github.com/LineageOS/android_frameworks_base/blob/lineage-18.1/services/core/jni/com_android_server_lights_LightsService.cpp),
[HIDL color forwarding](https://github.com/LineageOS/android_hardware_interfaces/blob/lineage-18.1/light/2.0/default/Light.cpp).
