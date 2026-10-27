#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Unactivated experiment; not installed by the product or camera ZIP.
# Android 11 SurfaceFlinger 1008 selects client/GPU composition. Keep legacy
# MDP video blits out of the playback path while their ION import is unresolved.
set -eu
mode=$(/system/bin/getprop persist.vendor.j2prime.gpu_composition)
case "$mode" in
    ''|1) mode=1 ;;
    0) mode=0 ;;
    *) echo 'Invalid J2 Prime composition mode' >&2; exit 1 ;;
esac
if [ "${1:-}" = --check ]; then
    echo "GPU_COMPOSITION_MODE=$mode"
    exit 0
fi
attempt=0
while [ "$attempt" -lt 20 ]; do
    if /system/bin/service check SurfaceFlinger | /system/bin/grep -q ': found'; then
        exec /system/bin/service call SurfaceFlinger 1008 i32 "$mode"
    fi
    attempt=$((attempt + 1))
    /system/bin/sleep 1
done
echo 'SurfaceFlinger unavailable; composition setting not applied' >&2
exit 1
