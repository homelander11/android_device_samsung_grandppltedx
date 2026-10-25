// SPDX-License-Identifier: Apache-2.0
// Compile with g++ -m32 -std=c++17 -fsyntax-only and the Android audio/cutils
// include directories, both with and without the device layout macro.
#include <string.h>
#include <system/audio.h>
#include <stddef.h>

#ifdef GRANDPPLTEDX_LEGACY_AUDIO_PORT_LAYOUT
static_assert(offsetof(audio_port_config, ext.mix.handle) == 0xb0,
              "MTK primary HAL reads the mix handle at 0xb0");
#else
static_assert(offsetof(audio_port_config, ext.mix.handle) == 0xb4,
              "Default framework layout must remain unchanged");
#endif

static_assert(AUDIO_STREAM_CALL_ASSISTANT == 14,
              "Keep framework stream declarations available");
static_assert(AUDIO_USAGE_NOTIFICATION_EVENT == 10,
              "Keep framework usage declarations available");
