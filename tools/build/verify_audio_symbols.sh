#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Run after tools/build/run.sh audio. Checks symbol isolation and emits the
# actual ARM conversion disassembly for inspection; it is not a device test.
set -euo pipefail
client=out/soong/.intermediates/hardware/interfaces/audio/common/all-versions/default/android.hardware.audio.common@4.0-util/android_arm_armv8-a_shared/unstripped/android.hardware.audio.common@4.0-util.so
server=out/soong/.intermediates/hardware/interfaces/audio/core/all-versions/default/android.hardware.audio@4.0-impl/android_arm_armv8-a_shared/unstripped/android.hardware.audio@4.0-impl.so
objdump=${LLVM_OBJDUMP:-prebuilts/clang/host/linux-x86/clang-r383902b1/bin/llvm-objdump}
output=${1:-out/grandppltedx-audio-abi}
mkdir -p "$output"
readelf --wide -d "$server" > "$output/server-dependencies.txt"
if grep -q 'android.hardware.audio.common@4.0-util.so' "$output/server-dependencies.txt"; then
  echo 'FAIL: server still links the normal conversion utility'; exit 1
fi
for side in client server; do
  binary=${!side}
  nm --defined-only "$binary" | grep 'audioPortConfigToHal' > "$output/$side-symbol.txt"
  symbol=$(awk '{print $3}' "$output/$side-symbol.txt")
  "$objdump" -d --disassemble-functions="$symbol" "$binary" > "$output/$side-conversion.asm"
done
grep -q 'GrandppltedxHidlUtils' "$output/server-symbol.txt"
if grep -q 'GrandppltedxHidlUtils' "$output/client-symbol.txt"; then
  echo 'FAIL: framework utility uses legacy class'; exit 1
fi
readelf --wide --dyn-syms "$server" > "$output/server-dynamic-symbols.txt"
if grep -q 'GrandppltedxHidlUtils' "$output/server-dynamic-symbols.txt"; then
  echo 'FAIL: private conversion symbols are externally visible'; exit 1
fi
grep -E 'str.*#(176|180)|str.*0x(b0|b4)' "$output/client-conversion.asm" "$output/server-conversion.asm"
echo AUDIO_CONVERSION_ISOLATION_PASS
