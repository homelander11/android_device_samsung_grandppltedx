"""Execute the pinned ARM HAL selector and PCM/card parser without hardware I/O."""
import hashlib
from pathlib import Path
import struct
import sys

# Optional CPU verification: pip install unicorn (not needed by the correction).
# python tools/tests/check_audio_deep_buffer_arm.py ORIGINAL.so CORRECTED.so
TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import *
from elf32 import Elf32

import argparse
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('original', type=Path)
ap.add_argument('corrected', type=Path)
args = ap.parse_args()
ORIGINAL, CANDIDATE = args.original, args.corrected
manifest = __import__('json').loads((TOOLS / 'audio/deep-buffer-pcm.json').read_text())
assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == manifest['original_sha256']
assert hashlib.sha256(CANDIDATE.read_bytes()).hexdigest() == manifest['patched_sha256']
PCM = ['MultiMedia1_PLayback', 'MultiMedia1_Capture', 'Voice_MD1_PLayback',
       'HMDI_PLayback', 'ULDL_Loopback', 'I2S0_PLayback', 'MRGRX_PLayback',
       'MRGRX_CAPTURE', 'I2S0DL1_PLayback', 'DL1_AWB_Record',
       'Voice_MD1_BT_Playback', 'VOIP_Call_BT_Playback', 'VOIP_Call_BT_Capture',
       'TDM_Debug_Record', 'FM_MRGTX_Playback', 'MultiMediaData2_Capture',
       'I2S0AWB_Capture', 'Voice_MD2_PLayback', 'MultiMedia_Routing',
       'Voice_MD2_BT_Playback', 'HP_IMPEDANCE_Playback', 'FM_I2S_Playback',
       'FM_I2S_Capture', None, 'MultiMedia2_PLayback']


def fixture(path):
    data = path.read_bytes()
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x1000, 0x200000)
    u.mem_map(0x300000, 0x200000)
    phoff = struct.unpack_from('<I', data, 28)[0]
    entsize, count = struct.unpack_from('<HH', data, 42)
    segments = []
    for i in range(count):
        kind, offset, va, _, size, _, _, _ = struct.unpack_from('<8I', data, phoff + i * entsize)
        if kind == 1:
            u.mem_write(va, data[offset:offset + size])
            segments.append((offset, va, size))

    def word(address, value):
        u.mem_write(address, struct.pack('<I', value))

    def readword(address):
        return struct.unpack('<I', u.mem_read(address, 4))[0]

    def cstr(address):
        return bytes(u.mem_read(address, 256)).split(b'\0', 1)[0]

    def literal_va(literal):
        off = data.index(literal + b'\0')
        return next(va + off - base for base, va, size in segments if base <= off < base + size)

    # Two process-global String8 objects initialized by the real ELF constructors.
    word(0x161640, literal_va(b'I2S0DL1_PLayback'))
    word(0x1616cc, literal_va(b'MultiMedia2_PLayback' if path == CANDIDATE else b'Deep_Buffer_PLayback'))
    parser, vector = 0x420000, 0x421000
    descriptors = []
    for pcm, name in enumerate(PCM):
        if name is None:
            continue
        desc = 0x422000 + pcm * 0x100
        u.mem_write(desc + 0x20, name.encode() + b'\0')
        word(desc, desc + 0x20)
        word(desc + 8, 0)
        word(desc + 12, pcm)
        descriptors.append(desc)
    for i, desc in enumerate(descriptors):
        word(vector + i * 4, desc)
    word(parser + 4, vector)
    word(parser + 8, len(descriptors))
    # Compressed-device vector is deliberately empty; unknown PCM remains -1.
    word(parser + 0x18, 0)
    word(parser + 0x1c, 0)
    events = []

    def hook(cpu, pc, size, context):
        def ret(value=None):
            if value is not None:
                cpu.reg_write(UC_ARM_REG_R0, value & 0xffffffff)
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
        if pc == 0x41908:  # real isolated-deep-buffer flag helper
            cpu.reg_write(UC_ARM_REG_PC, 0x797c0)
        elif pc == 0x3fa6c:  # String8 copy: retain shared string pointer
            word(cpu.reg_read(UC_ARM_REG_R0), readword(cpu.reg_read(UC_ARM_REG_R1)))
            ret()
        elif pc == 0x3f97c:  # String8 destructor has no selector side effects
            ret()
        elif pc == 0x40a80:
            ret(parser)
        elif pc in (0x40a98, 0x40a8c):
            events.append(cstr(readword(cpu.reg_read(UC_ARM_REG_R1))).decode())
            cpu.reg_write(UC_ARM_REG_PC, 0xd1c2c if pc == 0x40a98 else 0xd1d28)
        elif pc == 0x3fa84:
            a = cstr(cpu.reg_read(UC_ARM_REG_R0))
            b = cstr(cpu.reg_read(UC_ARM_REG_R1))
            ret((a > b) - (a < b))
        elif pc == 0x3f538:
            ret(0)
    u.hook_add(UC_HOOK_CODE, hook)
    return u, word, events


def test(path, flags):
    u, word, events = fixture(path)
    word(0x410000 + 12, 0x410100)
    word(0x410100 + 8, flags)
    u.reg_write(UC_ARM_REG_R4, 0x410000)
    u.reg_write(UC_ARM_REG_SP, 0x30f000)
    # Start at flag selection; stop immediately before pcm_params_get().
    u.emu_start(0xa9a94, 0xa9b2c, count=100000)
    assert u.reg_read(UC_ARM_REG_PC) == 0xa9b2c
    assert u.reg_read(UC_ARM_REG_SP) == 0x30f000
    card, pcm = u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1)
    isolated = flags & 0xa == 8
    expected = (0, 24) if isolated and path == CANDIDATE else (0xffffffff, 0xffffffff) if isolated else (0, 8)
    assert (card, pcm) == expected, (path.name, flags, events, card, pcm)
    return {'flags': flags, 'name': events[0], 'card': card, 'pcm': pcm}


if __name__ == '__main__':
    before, after = Elf32(ORIGINAL), Elf32(CANDIDATE)
    assert before.symbols == after.symbols
    assert before.sections == after.sections
    assert before.needed == after.needed
    old, new = ORIGINAL.read_bytes(), CANDIDATE.read_bytes()
    assert len(old) == len(new)
    assert all(1185255 <= i < 1185275 for i, (a, b) in enumerate(zip(old, new)) if a != b)
    for flags in range(16):
        a, b = test(ORIGINAL, flags), test(CANDIDATE, flags)
        print(a, '=>', b)
    for path in (ORIGINAL, CANDIDATE):
        u, word, _ = fixture(path)
        u.mem_write(0x430004, b'Unknown_PCM\0')
        word(0x430000, 0x430004)
        u.reg_write(UC_ARM_REG_R0, 0x420000)
        u.reg_write(UC_ARM_REG_R1, 0x430000)
        u.reg_write(UC_ARM_REG_SP, 0x30f000)
        u.reg_write(UC_ARM_REG_LR, 0x300000)
        u.emu_start(0xd1c2c, 0x300000, count=100000)
        assert u.reg_read(UC_ARM_REG_R0) == 0xffffffff
    print('PASS: actual ARM flag selector, name selection and card/PCM parsers; no hardware operations')
    print('PASS: normal/fast/primary+deep unchanged, isolated deep -> card0/device24, unknown -> -1')
    print('PASS: ELF sections, symbols, dependencies and executable bytes unchanged')
