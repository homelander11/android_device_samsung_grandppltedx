# Scoped LineageOS 18.1 compatibility patches

Apply from the root of a **Linux LineageOS 18.1 source checkout**:

```sh
python3 device/samsung/grandppltedx/tools/apply_android11_patches.py --check
python3 device/samsung/grandppltedx/tools/apply_android11_patches.py --apply
```

All patches are checked before any source is modified. Already applied patches
are skipped. No commits, resets, or source downloads are performed by this tool.
These patches target the published LineageOS 18.1 source, not the obsolete
`media/libaudiohal/2.0` paths in the older sibling patch collection. They do not
replace the remaining platform/graphics compatibility work required by this port.

* `system/bt`: add an optional device limit on extended feature page discovery.
  `bdroid_buildcfg.h` sets the limit to 1. Captured MT6737T HCI responses show
  pages 0 and 1 succeed; page 2 returns status `0x30` and aborts the stack.
  Other products keep the previous default limit.
* `hardware/interfaces`: apply `AUDIO_NO_SYSTEM_DECLARATIONS` to both audio HIDL
  utility and implementation compilation when the device's Soong option is set.
  The non-Treble image loads system variants of these libraries. Their default
  `audio_port_config` contains an extra framework-only flags field that shifts
  the vendor HAL's mix handle/device type by four bytes. No VNDK level change or
  downgrade of the HAL version is needed.

Preflight and ABI/HCI evidence do not substitute for compiling these components
and testing speaker/microphone routes and Bluetooth on a newly built image.
