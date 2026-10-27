#!/system/bin/sh
# Recover the known third-party camera failure without changing firmware/data.
set -eu
mode=${1:---check}
case "$mode" in --check|--restart) ;; *) echo 'Use --check or --restart';exit 2;; esac
test "$(id -u)" = 0
test "$(getprop ro.product.model)" = SM-G532G
test "$(getprop ro.product.device)" = grandppltedx
test "$(getprop ro.hardware)" = mt6735
test "$(getprop ro.build.version.sdk)" = 30
test "$(getprop sys.boot_completed)" = 1
test "$(getprop init.svc.bootanim)" = stopped
echo "Camera provider: $(getprop init.svc.vendor.camera-provider-2-4)"
old=$(pidof android.hardware.camera.provider@2.4-service || true)
echo "Previous provider PID: $old"
[ "$mode" = --restart ] || exit 0
timeout -s KILL 4 cmd activity force-stop com.photo.android.camera || true
timeout -s KILL 4 cmd activity force-stop org.lineageos.snap || true
setprop ctl.restart vendor.camera-provider-2-4
for attempt in 1 2 3 4 5 6 7 8; do
 sleep 1
 current=$(pidof android.hardware.camera.provider@2.4-service || true)
 if [ -n "$current" ] && [ "$current" != "$old" ] &&
    [ "$(getprop init.svc.vendor.camera-provider-2-4)" = running ]; then
  echo "Camera provider restarted: $current"
  exit 0
 fi
done
echo 'Camera provider restart not confirmed' >&2
exit 1
