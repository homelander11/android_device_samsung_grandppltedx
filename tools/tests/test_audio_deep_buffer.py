"""Verify the paired HAL's kernel-name correction and reject foreign inputs."""
import hashlib
from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import fix_audio_deep_buffer as fix
from elf32 import Elf32

HAL = TOOLS.parents[3] / "vendor/samsung/grandppltedx/proprietary/vendor/lib/hw/audio.primary.mt6737t.so"


class AudioDeepBufferTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = HAL.read_bytes()
        original = bytearray(data)
        if hashlib.sha256(data).hexdigest() == fix.MANIFEST["patched_sha256"]:
            offset = fix.MANIFEST["offset"]
            old = bytes.fromhex(fix.MANIFEST["original"])
            original[offset:offset + len(old)] = old
        cls.original = bytes(original)

    def test_only_pinned_pcm_name_changes(self):
        result = fix.corrected(self.original)
        offset = fix.MANIFEST["offset"]
        size = len(bytes.fromhex(fix.MANIFEST["original"]))
        self.assertEqual(len(result), len(self.original))
        self.assertEqual(result[:offset], self.original[:offset])
        self.assertEqual(result[offset + size:], self.original[offset + size:])
        self.assertEqual(result[offset:offset + size], b"MultiMedia2_PLayback\0")
        self.assertEqual(fix.corrected(result), result)
        # Kernel's ordinary I2S0/DL1 selection remains present, unchanged.
        self.assertEqual(result.count(b"I2S0DL1_PLayback\0"),
                         self.original.count(b"I2S0DL1_PLayback\0"))

    def test_elf_abi_and_executable_sections_unchanged(self):
        result = fix.corrected(self.original)
        elf = Elf32(HAL)
        for section in elf.sections:
            if section[2] & 4:  # SHF_EXECINSTR
                begin, end = section[4], section[4] + section[5]
                self.assertEqual(result[begin:end], self.original[begin:end])

    def test_unknown_hal_rejected_without_modification(self):
        bad = bytearray(self.original)
        bad[-1] ^= 1
        before = bytes(bad)
        with self.assertRaisesRegex(ValueError, "unknown audio HAL"):
            fix.corrected(bad)
        self.assertEqual(before, bytes(bad))


if __name__ == "__main__":
    unittest.main()
