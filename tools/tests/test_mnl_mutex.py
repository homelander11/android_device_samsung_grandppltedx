"""Check the exact candidate MNL blob; no production GPS process is started."""
import importlib.util
from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1]
VENDOR_ROOT = TOOLS.parents[3] / "vendor/samsung/grandppltedx"
spec = importlib.util.spec_from_file_location("fix_mnl_mutex", VENDOR_ROOT / "tools/fix_mnl_mutex.py")
fix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fix)


class MnlMutexTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patched = (VENDOR_ROOT / "proprietary/vendor/lib/libmnl.so").read_bytes()
        cls.original = (cls.patched[:fix.OFFSET] + fix.BEFORE
                        + cls.patched[fix.OFFSET + len(fix.AFTER):])

    def test_only_destroy_wrapper_changes_and_apply_is_idempotent(self):
        self.assertEqual(fix.hashlib.sha256(self.original).hexdigest(), fix.ORIGINAL)
        result = fix.corrected(self.original)
        self.assertEqual(result, self.patched)
        self.assertEqual(len(result), fix.SIZE)
        self.assertEqual(result[:fix.OFFSET], self.original[:fix.OFFSET])
        self.assertEqual(result[fix.OFFSET + 18:], self.original[fix.OFFSET + 18:])
        self.assertEqual(fix.corrected(result), result)

    def test_unknown_or_truncated_library_is_rejected(self):
        bad = bytearray(self.original)
        bad[-1] ^= 1
        for value in (bytes(bad), self.original[:-1]):
            with self.assertRaisesRegex(ValueError, "unknown"):
                fix.corrected(value)


if __name__ == "__main__":
    unittest.main()
