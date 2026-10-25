#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Run inside the Ubuntu 20.04 build container from the Android source root.
set -eo pipefail

target=${1:-nothing}
jobs=${BUILD_JOBS:-16}
case "$target" in
    audio) targets=(android.hardware.audio.common@4.0-util android.hardware.audio@4.0-impl) ;;
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
python3 "$device/tools/validate_configs.py"
python3 "$device/tools/apply_android11_patches.py" --source-root "$PWD" --apply
source build/envsetup.sh
lunch lineage_grandppltedx-userdebug
printf 'BUILD_START %s target=%s jobs=%s\n' "$(date -u --iso-8601=seconds)" "$target" "$jobs"
m -j"$jobs" "${targets[@]}"
printf 'BUILD_DONE %s target=%s\n' "$(date -u --iso-8601=seconds)" "$target"
