#!/usr/bin/env python3
"""Build the static ARM helper with the existing Windows Android SDK and LLVM.

Requires llvmlite (LLVM20) and keystone-engine. Emits only local component files.
The assembly object retains an R_ARM_CALL relocation for wrapper_start; the
placeholder BL encodes the standard -8 addend for an ARM REL call relocation.
"""
import argparse
from pathlib import Path
import subprocess
import re
import struct
import llvmlite.binding as llvm
from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM, KS_MODE_LITTLE_ENDIAN

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build-tools', type=Path, required=True)
parser.add_argument('--out-dir', type=Path, required=True)
parser.add_argument('--fixtures', action='store_true', help='also build RAM-only test variants')
args = parser.parse_args()
src = Path(__file__).resolve().parent
out = args.out_dir.resolve()
out.mkdir(parents=True, exist_ok=True)
sdk = args.build_tools.resolve()
llvm.initialize_all_targets()
llvm.initialize_all_asmprinters()
tm = llvm.Target.from_triple('armv7-none-linux-gnueabi').create_target_machine(cpu='cortex-a53', reloc='static')
a = re.sub(r'/\*.*?\*/', '', (src / 'start.S').read_text(), flags=re.S)
a = '\n'.join(l for l in a.splitlines() if not l.strip().startswith('.'))
a = a.replace('bl wrapper_start', 'bl #4').replace('b .', 'b #16')
a = a.replace('1:', 'memcpy_loop:').replace('1b', 'memcpy_loop')
a = a.replace('2:', 'memset_loop:').replace('2b', 'memset_loop')
ks = Ks(KS_ARCH_ARM, KS_MODE_ARM | KS_MODE_LITTLE_ENDIAN)
code = bytes(ks.asm(a, addr=0)[0])
assert code[4:8] == struct.pack('<I', 0xebfffffe)
names = ['_start', 'raw6', 'memcpy', 'memset', '__aeabi_memclr']
values = {}
for name in names:
    before = a.split(name + ':')[0]
    values[name] = len(ks.asm(before, addr=0)[0]) if before.strip() else 0
aliases = {'__aeabi_memcpy': 'memcpy', '__aeabi_memcpy4': 'memcpy', '__aeabi_memcpy8': 'memcpy',
           '__aeabi_memclr4': '__aeabi_memclr', '__aeabi_memclr8': '__aeabi_memclr'}
values.update({k: values[v] for k, v in aliases.items()})
strings = bytearray(b'\0')
stnames = {}
for name in [*values, 'wrapper_start']:
    stnames[name] = len(strings)
    strings.extend(name.encode() + b'\0')
symbols = bytearray(16)
for name, val in values.items():
    symbols.extend(struct.pack('<IIIBBH', stnames[name], val, 0, 0x12, 0, 1))
wrapper_index = len(symbols) // 16
symbols.extend(struct.pack('<IIIBBH', stnames['wrapper_start'], 0, 0, 0x12, 0, 0))
rel = struct.pack('<II', 4, (wrapper_index << 8) | 28)
shnames = bytearray(b'\0')
shoffnames = {}
for name in ('.text', '.rel.text', '.symtab', '.strtab', '.note.GNU-stack', '.shstrtab'):
    shoffnames[name] = len(shnames)
    shnames.extend(name.encode() + b'\0')
sections = [('.text', 1, 6, code, 0, 0, 4, 0), ('.rel.text', 9, 0, rel, 3, 1, 4, 8),
            ('.symtab', 2, 0, bytes(symbols), 4, 1, 4, 16), ('.strtab', 3, 0, bytes(strings), 0, 0, 1, 0),
            ('.note.GNU-stack', 1, 0, b'', 0, 0, 1, 0), ('.shstrtab', 3, 0, bytes(shnames), 0, 0, 1, 0)]
obj = bytearray(52)
headers = [b'\0' * 40]
for name, typ, flags, data, link, info, align, entsize in sections:
    obj.extend(b'\0' * ((-len(obj)) % align))
    offset = len(obj)
    obj.extend(data)
    headers.append(struct.pack('<10I', shoffnames[name], typ, flags, 0, offset, len(data), link, info, align, entsize))
obj.extend(b'\0' * ((-len(obj)) % 4))
sho = len(obj)
obj.extend(b''.join(headers))
ident = b'\x7fELF\x01\x01\x01' + b'\0' * 9
obj[:52] = struct.pack('<16sHHIIIIIHHHHHH', ident, 1, 40, 1, 0, 0, sho, 0x05000000, 52, 0, 0, 40, len(headers), 6)
(out / 'start.o').write_bytes(obj)
source = (src / 'init_wrapper.c').read_text()
for fixture in ((0, 1, 2) if args.fixtures else (0,)):
    c = '#pragma version(1)\n#pragma rs java_package_name(j2prime.diagnostics)\n#define J2PRIME_RS_FRONTEND 1\n#define DIAG_FIXTURE ' + str(fixture) + '\n' + source
    (out / 'wrapper.c').write_bytes(c.encode())
    r = subprocess.run([str(sdk / 'llvm-rs-cc.exe'), '-emit-llvm', '-O2', '-target-api', '18',
                        '-I', str(sdk / 'renderscript/include'), '-I', str(sdk / 'renderscript/clang-include'),
                        '-o', '.', 'wrapper.c'], cwd=out, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout, r.stderr)
        r.check_returncode()
    m = llvm.parse_assembly((out / 'wrapper.ll').read_text())
    m.triple = 'armv7-none-linux-gnueabi'
    m.data_layout = str(tm.target_data)
    m.get_function('wrapper_start').linkage = 'external'
    m.verify()
    (out / 'wrapper.o').write_bytes(tm.emit_object(m))
    dest = out / ('init-wrapper' if fixture == 0 else f'init-fixture-{fixture}')
    r = subprocess.run([str(sdk / 'lld-bin/lld.exe'), '-flavor', 'gnu', '-m', 'armelf_linux_eabi',
                        '-static', '-e', '_start', '-z', 'noexecstack', '--build-id=none',
                        str(out / 'start.o'), str(out / 'wrapper.o'), '-o', str(dest)], capture_output=True, text=True)
    if r.returncode:
        print(r.stdout, r.stderr)
        r.check_returncode()
    print('BUILT', dest.name, dest.stat().st_size)
print('ASM SYMBOLS', values)
