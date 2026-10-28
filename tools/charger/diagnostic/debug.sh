#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Only the existing permissive/debuggable ROM is supported. No charge-control,
# calibration, boot partition, persistent USB property or authentication writes.
mode=$(getprop ro.bootmode)
lp=$(cat /sys/class/power_supply/battery/batt_lp_charging 2>/dev/null)
if [ "$mode" != charger ] && [ "$lp" != 1 ]; then
    exit 0
fi

# Reuse the ROM's existing insecure-debug configuration; do not weaken it.
if [ "$(getprop ro.debuggable)" = 1 ] && [ "$(getprop ro.adb.secure)" = 0 ]; then
    setprop sys.usb.config none
    sleep 1
    setprop sys.usb.config adb
    setprop ctl.start adbd
fi
setprop ctl.start logd

block=/dev/block/platform/mtk-msdc.0/11230000.msdc0/by-name/cache
if ! grep -q ' /cache ' /proc/mounts; then
    test -b "$block" || exit 2
    mount -t ext4 -o nosuid,nodev,noatime "$block" /cache || exit 3
fi
test ! -L /cache || exit 4
dir=/cache/j2prime-charger-debug
test ! -L "$dir" || exit 4
umask 077
mkdir -p "$dir" || exit 4
chmod 0700 "$dir" || exit 4
log=$dir/latest.txt
test ! -L "$log" || exit 4
: > "$log" || exit 4
chmod 0600 "$log"

snapshot() {
    {
        echo "=== CHARGER DEBUG: $1 ==="
        cat /proc/uptime
        for prop in ro.bootmode ro.boot.bootreason hwservicemanager.ready init.svc.vendor.lpm init.svc.hwservicemanager init.svc.servicemanager init.svc.adbd sys.usb.config sys.usb.state; do
            echo "$prop=$(getprop "$prop")"
        done
        for node in status capacity voltage_now temp batt_lp_charging; do
            echo "battery/$node=$(cat /sys/class/power_supply/battery/$node 2>/dev/null)"
        done
        echo "--- mounts ---"
        cat /proc/mounts
        echo "--- process state ---"
        ps -A
        for pid in $(pidof charger); do
            echo "--- charger PID $pid ---"
            cat /proc/$pid/status /proc/$pid/wchan /proc/$pid/stack 2>/dev/null
        done
        echo "--- kernel log ---"
        dmesg
        echo "--- Android log ---"
        timeout 2 logcat -b all -d -v threadtime -t 300
    } >> "$log" 2>&1
    sync
}
snapshot initial
sleep 5
snapshot after_5_seconds
sleep 10
snapshot after_15_seconds
sleep 20
snapshot after_35_seconds
exit 0
