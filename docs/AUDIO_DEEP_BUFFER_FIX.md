# Deep-buffer playback on the MT6737T kernel

The legacy primary audio HAL selects `Deep_Buffer_PLayback` for isolated
`AUDIO_OUTPUT_FLAG_DEEP_BUFFER` output. This device's kernel has no PCM with
that name. `AudioALSADeviceParser` consequently returns -1, and playback tries
to open `/dev/snd/pcmC0D4294967295p`. The HAL subsequently writes with a null
PCM handle. Video players can stay on one frame and produce no sound while
other clips/output paths work.

The kernel already implements DL2 playback as `MultiMedia2_PLayback`, exposed
on the tested phone as card 0, device 24. See
`sound/soc/mediatek/mt_soc_audio_v3/AudDrv_Def.h` (`MT_SOC_DL2_STREAM_NAME`) and
`mt_soc_pcm_dl2.c` for the DL2 PCM, formats, rate constraints and DAC routing.
Correct only the deep-buffer name in the matching vendor HAL. Both strings
occupy 20 bytes including NUL. No kernel rebuild or Android build is needed
for this exact vendor-library correction.

## Reproduction and scope

`tools/fix_audio_deep_buffer.py ORIGINAL.so --output CORRECTED.so` accepts only
the pinned original or already-corrected hash. `tools/audio/deep-buffer-pcm.json`
records the exact offset, bytes and SHA-256 values. The paired vendor tree
contains the corrected HAL and `audio-deep-buffer-provenance.json`.

Original SHA-256:
`c4f37051f521c4fffd7eb13f9016cda9df528fdabdba42386e87f6b5e32419e6`.
Corrected SHA-256:
`59d5372430377c26724e24077b6ad70a3a3dc3272b82528da720958462debdb6`.

All executable bytes, ELF layout, symbols and dependencies remain identical.
Ordinary/fast/primary playback still selects `I2S0DL1_PLayback` (device 8).
This does not add a global fallback for unknown PCM names. Microphone recording
selectors, audio calibration, Wi-Fi, boot, recovery and graphics are unchanged.

## Validation on 2026-10-27

- Execute the actual ARM flag helper, normal-handler selection and PCM/card
  parsers in Unicorn for every flags value 0 through 15. Original isolated
  deep-buffer output returns card/PCM -1; the correction selects 0/24. Ordinary
  paths stay at 0/8. Unknown names still return -1. No hardware call is executed.
  Reproduce with `python tools/tests/check_audio_deep_buffer_arm.py ORIGINAL.so
  CORRECTED.so` (optional `unicorn` package).
- Regression tests verify the exact changed slot, unchanged executable sections,
  idempotence and unknown-input rejection. The complete 19-test host suite and
  21 XML/configuration checks pass.
- Load the correction through a temporary bind mount, restarting only the
  audio HAL and audioserver. Logs show successful PCM device 24 opening; ALSA
  reports RUNNING with an advancing hardware pointer.
- User confirms moving synthetic patterns with a steady tone, repeated playback
  of the previously frozen front-camera clip and another existing clip.
- With the camera compatibility candidate active as well, user confirms new
  rear/front recordings, moving playback with sound, and closing/reopening
  Camera. Default codec selection and normal hardware composition are retained.

The temporary mount has an independent rollback timer and exact-original
restore verification. Permanent installation/reboot, long playback, headphones,
Bluetooth audio and telephone calls remain to be tested. A nonfatal
`setInterruptRate` -22 diagnostic still occurs; successful short playback does
not establish every power/rate transition. No persistent GPU/codec workaround
is justified by these tests. GPS investigation remains paused.

## Recovery update

`tools/build/create_camera_fix.py` now includes this exact primary-HAL
correction in the combined `grandppltedx-20261027-camera-audio-fix.zip` and
restores the original HAL in its paired undo. The camera package's old
original-only audio dependency check becomes a payload preflight accepting
only the pinned original/corrected hashes. All preflight checks precede writes.

The unchanged updater binary and payloads pass install/reinstall/exact undo,
ownership/mode/SELinux labels, unknown camera-library rejection, unknown
primary-HAL rejection and symlink rejection on a 64 MiB ext4 RAM fixture.
Only block/mount/verifier/shell paths differ in that fixture. The actual
system partition has not been written by these tests. TWRP installation and
post-reboot camera/audio operation remain pending.
