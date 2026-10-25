# LineageOS 18.1 build environment

Use a Linux filesystem for the complete Android checkout. The Windows project
holds the device/vendor/kernel repositories and audit tools; it cannot host a
complete case-sensitive Android/kernel checkout reliably.

The tested remote environment has 20 vCPUs, 62 GiB RAM and a 493 GB ext4 disk.
It runs Ubuntu 24.04 with compilation isolated in Ubuntu 20.04. No credentials
are required inside the container: all source repositories are public.

## Setup

Install and configure Git LFS **before** syncing. Initialize LineageOS 18.1 with
a pinned `repo` launcher (v2.45 was used), `--git-lfs`, shallow history and Linux
projects. Add this device, vendor and kernel at reviewed
revisions to `.repo/local_manifests/`. Copy `android11-manifest.xml` there too,
then sync. It pins the APN snapshot before a new Python/YAML dependency absent
from the Android 11 manifest. Do not run the old `patches/install.sh`.

If a checkout already contains a 133-byte WebView pointer instead of the APK,
run `git -C external/chromium-webview/prebuilt/arm lfs pull`. The ARM prebuilt is
its own Git project; its parent `external/chromium-webview` is not. The runner
checks that the APK is a real ZIP before starting compilation.

Use a workspace layout with `lineage/` for sources and `home/` for container
user data. Both must be writable by UID/GID 1000. From that workspace:

```sh
docker build -t j2prime-lineage18.1 \
  lineage/device/samsung/grandppltedx/tools/build
docker run --init --rm --name j2prime-build --user 1000:1000 \
  -v "$PWD:/work" -v /usr/local/bin/repo:/usr/local/bin/repo:ro \
  -e BUILD_JOBS=16 j2prime-lineage18.1 \
  bash device/samsung/grandppltedx/tools/build/run.sh nothing
```

`nothing` checks the complete build graph. Replace it with `bacon` for the ROM,
`audio` for the framework conversion and 4.0 HAL implementation, or
`bootimage` / `recoveryimage` for those images. The runner validates device
configuration, applies the scoped Android 11 patches idempotently, and selects
`lineage_grandppltedx-userdebug`. It disables ccache for the initial build to
limit disk use. Preserve `out/` for subsequent incremental builds; changing a
configuration or source file does not normally require a clean build.

`graphics` builds only the GUI shim and an uninstalled HAL linker diagnostic.
The `graphics` and `bacon` targets then verify that the installed shim is the
source-built file and supplies the required Android 11 compatibility symbols.
See `docs/DISPLAY_BOOT_FIX.md` for the first flashed build's display-loader
failure and a reproducible single-library recovery update:

```sh
python3 device/samsung/grandppltedx/tools/build/create_display_fix.py \
  /path/to/original-20261025-rom.zip \
  out/target/product/grandppltedx/system/vendor/lib/libshim_gui.so \
  vendor/samsung/grandppltedx/proprietary/vendor/lib/libshim_gui.so \
  --out-dir /path/to/artifacts
```

Capture each invocation's output in a separate log and record its exit status.

The `lights` target builds the standard 2.0 service/wrapper, copies the corrected
legacy driver and backlight init rule, builds an uninstalled enumeration probe,
and checks the packaged service/init/VINTF. It needs the matching vendor fix
for the driver's unused RIL-client dependency. `docs/LIGHTS_BOOT_FIX.md` records
the animation-hang diagnosis and normal-boot test requirements.

`create_lights_fix.py BASE_ROM PRODUCT --original-driver ORIGINAL_HAL --out-dir DIR`
packages the targeted recovery fix and undo. Obtain ORIGINAL_HAL from the pinned
vendor revision in `lights-dependency-provenance.json`; the generator verifies
its exact hash. The local/remote product staging directory must contain the
service, wrapper, original interface library, corrected driver, both init files
and merged VINTF manifest. No full ROM rebuild is needed for this update.
Save a pinned `repo manifest -r` and all platform patch files with the result.
Build completion is separate from boot, Wi-Fi and hardware validation on a
physical device. Do not flash merely because compilation succeeds.

Check a built boot image with
`python3 device/samsung/grandppltedx/tools/verify_boot_image.py out/target/product/grandppltedx/boot.img`.
This validates the legacy header, load addresses, exact DT and payload checksum;
it does not establish successful boot.

The audio layout probe can be checked in the container from the Android root:

```sh
for layout in '' '-DGRANDPPLTEDX_LEGACY_AUDIO_PORT_LAYOUT'; do
  g++ -m32 -std=c++17 $layout -Isystem/media/audio/include \
    -Isystem/core/libcutils/include -fsyntax-only \
    device/samsung/grandppltedx/tools/build/audio_port_layout_probe.cpp || exit
done
```

After an `audio` build, run `bash device/samsung/grandppltedx/tools/build/verify_audio_symbols.sh`.
It rejects a HAL still linked to the normal conversion library, checks private
symbol isolation, and saves ARM conversion disassembly for inspection. In the
mix-port branch, the framework handle must remain at `0xb4` and the private HAL
handle must use `0xb0`. This supplements the C++ layout probe and device tests.

The GPS worker socket correction needs no compilation. Source and full-image
build checks run `validate_gnss_socket.py` to verify its pinned blob/init pair.
`create_gnss_fix.py BASE_ROM PATCHED_HAL ORIGINAL_HAL --out-dir DIR` packages
the fix and undo using the original updater, with version/hash prerequisites.
See `docs/GNSS_BOOT_FIX.md`; preserve the earlier display and Light updates.

## Paid VM budget

Set a wall-clock cutoff before starting a paid build, allowing time to copy
artifacts off the VM. A host timer that explicitly stops the named container
also covers a lost SSH connection. A build timeout or Ubuntu shutdown does not
establish that provider billing has stopped; check the provider's instance
controls and storage charges separately. Keep source/output directories until
artifacts and required incremental-build state have been preserved.
