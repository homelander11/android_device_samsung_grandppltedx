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
* `hardware/interfaces` and `system/media`: select
  `GRANDPPLTEDX_LEGACY_AUDIO_PORT_LAYOUT` inside the 4.0 HAL implementation and
  its private static conversion utility when the device's Soong option is set.
  The normal shared conversion library remains unchanged for framework clients.
  The private copy uses a distinct `GrandppltedxHidlUtils` C++ class and hidden
  symbols to prevent interposition with the normal utility. Its legacy
  `audio_port_config` omits the framework-only flags field that shifts the MTK
  HAL's mix handle/device type by four bytes. No VNDK level change or HAL
  downgrade is needed. The dedicated header guard retains framework enums;
  defining `AUDIO_NO_SYSTEM_DECLARATIONS` directly hides required stream/usage
  values and breaks Android 11 HIDL compilation.

If an earlier revision of the audio patch was already applied, reverse that
revision's `hardware/interfaces` patch before updating this device tree. Then
run the installer again. Do not force a new patch onto partially modified files.

Preflight and ABI/HCI evidence do not substitute for compiling these components
and testing speaker/microphone routes and Bluetooth on a newly built image.
