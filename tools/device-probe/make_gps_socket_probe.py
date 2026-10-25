#!/usr/bin/env python3
"""Emit a tiny static ARM EABI socket diagnostic, using no Android libraries.

Run as root only after verifying both hardcoded probe paths are absent. Drops
to the GNSS service's exact UID/GID/groups; creates/removes diagnostic sockets
only. Does not load a HAL, start GPS, or access calibration data. Success is
old-parent EACCES + GPS-owned-parent bind/unlink success. SELinux is inherited.
Syscall numbers match arch/arm/include/uapi/asm/unistd.h in this device kernel.
"""
import argparse
from pathlib import Path
import struct

OLD = "/data/misc/j2prime-gnss-bind-test.sock"
NEW = "/data/gps_mnl/j2prime-gnss-bind-test.sock"
BASE, START = 0x10000, 0x100


def build():
    code, labels, branches, loads = [], {}, [], []
    data = {
        "groups": struct.pack("<4I", 1000, 1021, 1001, 3003),
        "old": struct.pack("<H", 1) + OLD.encode() + b"\0",
        "new": struct.pack("<H", 1) + NEW.encode() + b"\0",
        "pass": b"PASS uid=1021: old parent bind EACCES; GPS-owned parent bind/unlink OK\n",
        "fail": b"FAIL GPS socket diagnostic\n",
    }

    def emit(word):
        code.append(word)

    def mov(reg, value):
        if value < 256:
            emit(0xe3a00000 | reg << 12 | value)
        else:
            assert value in (281, 282, 1021)
            mov(reg, value >> 8)
            emit(0xe1a00400 | reg << 12 | reg)  # mov rd, rd, lsl #8
            emit(0xe2800000 | reg << 16 | reg << 12 | (value & 255))

    def address(reg, name):
        loads.append((len(code), reg, name))
        emit(0)

    def branch(name, condition=14):
        branches.append((len(code), name, condition))
        emit(0)

    def syscall(number):
        mov(7, number)
        emit(0xef000000)  # svc #0

    def require_zero():
        emit(0xe3500000)  # cmp r0, #0
        branch("fail", 1)

    syscall(199)  # getuid32
    require_zero()
    mov(0, 4)
    address(1, "groups")
    syscall(206)  # setgroups32
    require_zero()
    mov(0, 1021)
    syscall(214)  # setgid32
    require_zero()
    mov(0, 1021)
    syscall(213)  # setuid32: drops root and capabilities
    require_zero()
    for name in ("old", "new"):
        mov(0, 1)  # AF_UNIX
        mov(1, 1)  # SOCK_STREAM
        mov(2, 0)
        syscall(281)  # socket
        emit(0xe3500000)  # cmp r0, #0
        branch("fail", 11)  # blt
        emit(0xe1a04000)  # mov r4, r0 (fd)
        address(1, name)
        mov(2, len(data[name]))
        syscall(282)  # bind
        emit(0xe1a05000)  # mov r5, r0 (bind result)
        emit(0xe1a00004)  # mov r0, r4
        syscall(6)  # close
        if name == "old":
            emit(0xe3550000)  # cmp r5, #0
            branch("old_denied", 1)
            address(0, "old_path")
            syscall(10)  # clean up even if old parent unexpectedly permits bind
            labels["old_denied"] = len(code)
            emit(0xe375000d)  # cmn r5, #13: expected -EACCES
            branch("fail", 1)
        else:
            emit(0xe3550000)  # cmp r5, #0
            branch("fail", 1)
            address(0, "new_path")
            syscall(10)  # unlink
            require_zero()
    branch("pass")
    for name, status in (("fail", 1), ("pass", 0)):
        labels[name] = len(code)
        mov(0, 1)
        address(1, name)
        mov(2, len(data[name]))
        syscall(4)  # write stdout
        mov(0, status)
        syscall(1)  # exit

    # LDR instructions load absolute addresses from a literal pool after code.
    pool = len(code)
    code.extend([0] * len(loads))
    payload, offsets = bytearray(), {}
    for name, value in data.items():
        offsets[name] = BASE + START + len(code) * 4 + len(payload)
        payload += value
    offsets["new_path"] = offsets["new"] + 2
    offsets["old_path"] = offsets["old"] + 2
    for index, (at, reg, name) in enumerate(loads):
        delta = (pool + index - at - 2) * 4
        assert 0 <= delta < 4096
        code[at] = 0xe59f0000 | reg << 12 | delta
        code[pool + index] = offsets[name]
    for at, name, condition in branches:
        delta = labels[name] - at - 2
        code[at] = condition << 28 | 0x0a000000 | (delta & 0xffffff)
    body = struct.pack("<" + "I" * len(code), *code) + payload
    size = START + len(body)
    header = b"\x7fELF\x01\x01\x01" + bytes(9)
    header += struct.pack("<HHIIIIIHHHHHH", 2, 40, 1, BASE + START,
                          52, 0, 0x05000000, 52, 32, 1, 0, 0, 0)
    segment = struct.pack("<8I", 1, 0, BASE, BASE, size, size, 5, 4096)
    return (header + segment).ljust(START, b"\0") + body


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_bytes(build())
    print(args.output, "created; run only after checking both probe paths are absent")
