# Fixed Samsung logo: display loader failure (2026-10-25)

The user installed v2 and reached the Lineage animation. The next failure is a
missing Light HAL blocking brightness initialization; see `LIGHTS_BOOT_FIX.md`.
Reaching the animation does not yet establish full boot.

The user flashed `lineage-18.1-20261025-UNOFFICIAL-grandppltedx.zip`; the fixed
Samsung J2 Ace logo never changed to the Lineage animation. TWRP's saved install
log reports exit 0. A read-only capture confirms the flashed boot payload is
byte-identical to the built image. Pstore is mounted but empty; last_kmsg has
only a MediaTek console header. These observations do not prove a kernel panic.

Useful Android logs survived in `/data/local/tmp/bootlog.txt` and its numbered
rotations. SurfaceFlinger repeatedly waits for the composer, whose load fails
on the old `GraphicBufferMapper::lock` ABI. The framebuffer fallback also fails.

## Cause and correction

The composer already has `libshim_gui.so` in DT_NEEDED. Recursive vendor copying
overwrote the source-built shim with a stale 15,904-byte prebuilt. That prebuilt
imports the old unsigned mapper-lock symbol instead of implementing it; the
existing source shim implements it by passing null for Android 11's two extra
optional pixel/stride pointers.

* Exclude only `lib/libshim_gui.so` from raw vendor copying. Retain the original
  in Git for provenance and the undo ZIP.
* Add legacy `GraphicBuffer::lock(unsigned int, void**)`, preserving `this` and
  forwarding to Android 11 with null optional output pointers. `libcam_utils`
  and `libmmsdkservice.feature` import this symbol.
* Link the shim with `libutilscallstack`, supplying the CallStack constructor,
  update, log and destructor imported by `libcam_utils`.
* Check required exports/imports and installed-versus-built bytes after the
  targeted `graphics` and full `bacon` builds to catch future overwrites.

The new stripped ARM shim is 5,888 bytes, SHA-256
`c52b763c485f0613b5d95047d0d993a04f23f6429f37143172d46de2f20cb362`.
Original SHA-256:
`45191a874d9c61979a2e7236ca654c4a78b4d1e09e21d88ba08689d4871fb93d`.

## Validation and limits

The targeted build succeeds; this one-library update needs no full ROM rebuild.
Static inspection finds no unresolved strong symbols in composer, Mali EGL and
camera dependency closures with the new shim.

Tests used the installed Android filesystem mounted read-only with journal
replay disabled, and its matching APEX libraries temporarily bound in RAM.
Before replacement, `dlopen(RTLD_NOW)` reproduces the composer mapper-lock error
and camera CallStack error. With only the new shim temporarily bound over the
old file, composer, camera and Mali EGL load successfully. The probe calls no
HAL open, camera enumeration or EGL initialization; ELF constructors do run.
No installed library, boot or calibration is changed by these tests.

An initial probe explicitly unloaded the composer and hit a vendor singleton
mutex destructor abort. The final probe keeps DSOs loaded, as HAL services do,
and uses `_exit` after reporting the load result. Safe explicit HAL unloading
remains unverified. Recovery runs a different kernel: this proves library
resolution, not working hardware or successful normal boot.

An early Mali initialization failure is followed by successful Mali-T720/OpenGL
ES 3.1 initialization in the same boot log. No GPU driver swap is made based on
that transient error. Full boot/display, camera preview/capture and all previous
Wi-Fi, audio, Bluetooth and GNSS checks remain required.

## Small recovery update

`tools/build/create_display_fix.py` makes fix and undo ZIPs using the diagnosed
ROM's update-binary. It pins the input ROM/original shim hashes and checks the
new ELF. On-device scripts require Android 11, the exact Lineage version and
either known shim hash before writing. They replace only
`/system/vendor/lib/libshim_gui.so`, preserve ownership/mode/SELinux label and
verify the output SHA-256. Boot, userdata, calibration and Wi-Fi files are untouched.

The first ZIP was rejected before execution because Android 11's updater does
not register `apply_patch_check` (nor `sha1_check`). Version 2 uses the supported
`run_program` function to invoke a bundled SHA-256 verifier through TWRP's
`/sbin/sh`. The exact updater successfully parses the complete v2 script in a
test that aborts before all installation commands. RAM-only integration tests
also verify `run_program` status handling, both known hashes and rejection of
an incorrect hash. These tests do not constitute an actual installation.

Install `grandppltedx-20261025-display-fix-v2.zip` in TWRP with ZIP signature
verification off, then reboot System. No wipe is needed for this library update.
`grandppltedx-20261025-display-undo-v2.zip` restores the original library, including
its loader bug. These unsigned development ZIPs target this exact base ROM.
Reflashing the original complete ROM requires reapplying the fix afterwards.

If boot still fails, return to TWRP and save `/data/local/tmp/bootlog.txt*` before
further attempts rotate the bounded logs. Raw phone logs remain private.
