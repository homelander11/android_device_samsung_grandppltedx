#!/system/bin/sh
# One-time orderly recovery reboot for the diagnosed Android 11 bring-up ROM.
# No firmware write: BCB and fstab overlay exist only in /dev tmpfs until reboot.
set -eu

mode=${1:---check}
case "$mode" in --check|--reboot) ;; *) echo 'Use --check or --reboot'; exit 2 ;; esac
test "$(id -u)" = 0
test "$(getprop ro.lineage.version)" = 18.1-20261025-UNOFFICIAL-grandppltedx
test "$(getprop ro.product.model)" = SM-G532G
test "$(getprop ro.hardware)" = mt6735
test "$(getprop ro.build.version.sdk)" = 30
test "$(getenforce)" = Permissive
test "$(readlink /proc/1/ns/mnt)" = "$(readlink /proc/$$/ns/mnt)"
grep -q '^tmpfs /dev tmpfs ' /proc/mounts

fstab=/vendor/etc/fstab.mt6735
bcb=/dev/j2prime-recovery-bcb
ramfstab=/dev/j2prime-recovery-fstab
original=275a7f6554834a787f23e122786d6e3f8afd324b5bb53810fe75d81636ce31a1
test "$(sha256sum "$fstab" | cut -d' ' -f1)" = "$original"
test ! -e /system/bin/recovery
test ! -e /etc/recovery.fstab
test ! -e /odm/etc/fstab.mt6735
test ! -d /proc/device-tree/firmware/android/fstab
test ! -e "$bcb" && test ! -e "$ramfstab"
test -b /dev/block/platform/mtk-msdc.0/11230000.msdc0/by-name/recovery
test "$(blockdev --getsize64 /dev/block/platform/mtk-msdc.0/11230000.msdc0/by-name/recovery)" = 16777216
echo 'PASS: pinned ROM/fstab, Samsung device, no misc, RAM paths free'
[ "$mode" = --reboot ] || exit 0

bound=0
cleanup() {
    set +e
    [ "$bound" = 0 ] || umount "$fstab" || umount -l "$fstab"
    rm -f "$bcb" "$ramfstab"
}
trap cleanup EXIT
# libbootloader_message accepts a regular file; no real partition is aliased.
dd if=/dev/zero of="$bcb" bs=4096 count=1
chmod 0600 "$bcb"
cat "$fstab" > "$ramfstab"
printf '\n%s /misc emmc defaults defaults\n' "$bcb" >> "$ramfstab"
chmod 0644 "$ramfstab"
chcon u:object_r:vendor_file:s0 "$ramfstab"
mount -o bind "$ramfstab" "$fstab"
bound=1
echo 'Requesting normal init shutdown with recovery reboot reason; RAM BCB only'
setprop sys.powerctl reboot,recovery
# Keep the overlay present until init finishes its BCB check and begins shutdown.
# If init refuses the request, restore everything instead of leaving an overlay.
sleep 15
echo 'ERROR: reboot did not start; restoring original fstab'
exit 1
