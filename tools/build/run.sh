#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Run inside the Ubuntu 20.04 build container from the Android source root.
set -eo pipefail

target=${1:-nothing}
jobs=${BUILD_JOBS:-16}
case "$target" in
    audio) targets=(android.hardware.audio.common@4.0-util android.hardware.audio@4.0-impl) ;;
    lights) targets=(android.hardware.light@2.0-service android.hardware.light@2.0-impl
        out/target/product/grandppltedx/system/vendor/lib/hw/lights.mt6735.so
        out/target/product/grandppltedx/system/vendor/etc/init/zz-grandppltedx-lights.rc
        out/soong/.intermediates/device/samsung/grandppltedx/tools/device-probe/grandppltedx_light_probe/android_arm_armv8-a/grandppltedx_light_probe) ;;
    # Uninstalled Soong binaries have no named Make target. Request its output.
    graphics) targets=(libshim_gui
        out/soong/.intermediates/device/samsung/grandppltedx/tools/device-probe/grandppltedx_hal_link_probe/android_arm_armv8-a/grandppltedx_hal_link_probe) ;;
    nothing|bacon|bootimage|recoveryimage) targets=("$target") ;;
    *) echo "Unsupported build target: $target" >&2; exit 2 ;;
esac
case "$jobs" in
    ''|*[!0-9]*) echo "BUILD_JOBS must be a positive integer" >&2; exit 2 ;;
esac
if [ "$jobs" -lt 1 ]; then exit 2; fi

export BUILD_USERNAME=ubuntu
export BUILD_HOSTNAME=j2prime-builder
export USE_CCACHE=0
export CCACHE_DISABLE=1
export GIT_TERMINAL_PROMPT=0
export TZ=UTC

device=device/samsung/grandppltedx
python3 - <<'PY'
from pathlib import Path
import sys
import zipfile
apk = Path("external/chromium-webview/prebuilt/arm/webview.apk")
if not zipfile.is_zipfile(apk):
    sys.exit("WebView APK is missing/invalid (possibly a Git LFS pointer). "
             "Initialize repo with --git-lfs and run git -C "
             "external/chromium-webview/prebuilt/arm lfs pull.")
PY
python3 "$device/tools/validate_configs.py"
python3 "$device/tools/validate_audio_nvram.py" vendor/samsung/grandppltedx/proprietary/vendor
python3 "$device/tools/validate_gnss_socket.py" vendor/samsung/grandppltedx/proprietary/vendor --source
python3 "$device/tools/apply_android11_patches.py" --source-root "$PWD" --apply
source build/envsetup.sh
lunch lineage_grandppltedx-userdebug
printf 'BUILD_START %s target=%s jobs=%s\n' "$(date -u --iso-8601=seconds)" "$target" "$jobs"
m -j"$jobs" "${targets[@]}"
case "$target" in
    graphics|bacon) python3 "$device/tools/verify_graphics_shim.py" out/target/product/grandppltedx ;;
esac
case "$target" in
    lights|bacon) python3 "$device/tools/verify_lights.py" out/target/product/grandppltedx ;;
esac
if [ "$target" = bacon ]; then
    python3 "$device/tools/validate_gnss_socket.py" out/target/product/grandppltedx/system/vendor
fi
printf 'BUILD_DONE %s target=%s\n' "$(date -u --iso-8601=seconds)" "$target"
