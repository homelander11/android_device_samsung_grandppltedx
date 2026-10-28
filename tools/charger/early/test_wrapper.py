#!/usr/bin/env python3
"""Execute the production ARM ELF in Unicorn; all syscalls stay inside the VM.

Checks exact PID 1 argv/env handoff, charger-only fork, diagnostic failures and
the non-PID1 guard. Hardware/kernel behavior is a separate device test.
"""
import argparse
from pathlib import Path
import struct

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2
from unicorn.arm_const import UC_ARM_REG_R3, UC_ARM_REG_R7, UC_ARM_REG_SP


def run(binary, command, charged=False, pid=1, fail_proc=False, fail_fork=False):
    words = struct.unpack_from("<HHIIIIIHHHHHH", binary, 16)
    assert binary[:6] == b"\x7fELF\x01\x01" and words[:2] == (2, 40)
    segments = [struct.unpack_from("<8I", binary, words[4] + i * words[8])
                for i in range(words[9])]
    assert not any(s[0] in (2, 3) for s in segments), "must be static, without interpreter"
    loads = [s for s in segments if s[0] == 1]
    first = min(s[2] for s in loads) & ~4095
    end = (max(s[2] + s[5] for s in loads) + 4095) & ~4095
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.mem_map(first, end - first)
    for s in loads:
        uc.mem_write(s[2], binary[s[1]:s[1] + s[4]])
    base, size = 0x7f000000, 0x10000
    uc.mem_map(base, size)
    pointer = base + 1024

    def store(text):
        nonlocal pointer
        pos = pointer
        raw = text.encode() + b"\0"
        uc.mem_write(pos, raw)
        pointer += len(raw)
        return pos

    args = ["/init", "kernel-test-token", "unchanged"]
    envs = ["HOME=/", "TERM=linux", "DIAGNOSTIC_TEST=1"]
    av, ev = [store(s) for s in args], [store(s) for s in envs]
    sp = base + size - 1024
    vector = [len(args), *av, 0, *ev, 0]
    uc.mem_write(sp, struct.pack("<" + "I" * len(vector), *vector))
    uc.reg_write(UC_ARM_REG_SP, sp)
    events = []
    finished = []

    def string(addr):
        raw = bytearray()
        while True:
            b = bytes(uc.mem_read(addr + len(raw), 1))
            if b == b"\0":
                return raw.decode()
            raw += b
            assert len(raw) < 8192

    def vector_strings(addr):
        result = []
        for i in range(32):
            p = struct.unpack("<I", uc.mem_read(addr + 4 * i, 4))[0]
            if not p:
                return result
            result.append(string(p))
        raise AssertionError("unterminated argv/env")

    def syscall(vm, interrupt, _):
        number = vm.reg_read(UC_ARM_REG_R7)
        a, b, c, d = (vm.reg_read(r) for r in
                      (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3))
        events.append(number)
        result = 0
        if number == 20:
            result = pid
        elif number == 21:
            assert string(a) == "proc" and string(b) == "/proc" and string(c) == "proc"
            assert d == 14
            result = -1 if fail_proc else 0
        elif number == 5:
            assert string(a) == "/proc/cmdline" and b == 0
            result = -2 if fail_proc else 8
        elif number == 3:
            assert a == 8 and c == 4095
            raw = command.encode()[:c]
            vm.mem_write(b, raw)
            result = len(raw)
        elif number == 6:
            assert a == 8
        elif number == 52:
            assert string(a) == "/proc" and b == 2 and not fail_proc
        elif number == 2:
            assert charged, "must never fork during normal boot"
            result = -11 if fail_fork else 123
        elif number == 11:
            assert string(a) == "/init.real"
            assert b == sp + 4 and c == sp + (len(args) + 2) * 4
            assert vector_strings(b) == args and vector_strings(c) == envs
            finished.append("exec")
            vm.emu_stop()
        elif number == 4:
            assert pid != 1 and a == 2
        elif number == 1:
            assert pid != 1 and a == 78
            finished.append("refused")
            vm.emu_stop()
        else:
            raise AssertionError(f"unexpected syscall {number}")
        vm.reg_write(UC_ARM_REG_R0, result & 0xffffffff)

    uc.hook_add(UC_HOOK_INTR, syscall)
    uc.emu_start(words[3], 0, count=1000000)
    assert finished == (["exec"] if pid == 1 else ["refused"]), finished
    if pid == 1:
        assert (2 in events) == charged
    if fail_proc:
        assert 52 not in events, "must not unmount a proc mount it did not create"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    args = parser.parse_args()
    binary = args.elf.read_bytes()
    cases = [
        ("normal handoff", "androidboot.mode=unknown", {}),
        ("normal substring rejected", "xandroidboot.mode=charger", {}),
        ("normal similar value rejected", "androidboot.mode=charging", {}),
        ("charger handoff", "a=1 androidboot.mode=charger b=2", {"charged": True}),
        ("Samsung charger prefix", "androidboot.mode=charger_extra", {"charged": True}),
        ("proc unavailable still boots", "", {"fail_proc": True}),
        ("fork failure still boots", "androidboot.mode=charger", {"charged": True, "fail_fork": True}),
        ("non-PID1 execution refused", "", {"pid": 200}),
    ]
    for name, command, options in cases:
        run(binary, command, **options)
        print("PASS", name)
    print("ARM execution tests only; real PID 1 and charging boot remain unverified.")


if __name__ == "__main__":
    main()
