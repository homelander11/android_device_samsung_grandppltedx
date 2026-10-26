"""Check the exact sensor guards against the paired vendor snapshot."""
from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import fix_camera_sensor_startup as fix

VENDOR = TOOLS.parents[3] / "vendor/samsung/grandppltedx/proprietary/vendor/lib"


class CameraSensorStartupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.listener = (VENDOR / "libcam.utils.sensorlistener.so").read_bytes()
        original = bytearray((VENDOR / "libfeatureio.so").read_bytes())
        if fix.digest(original) == fix.MANIFEST["patched_sha256"]:
            for item in fix.MANIFEST["changes"]:
                old = bytes.fromhex(item["original"])
                original[item["offset"]:item["offset"] + len(old)] = old
        cls.original = bytes(original)

    def test_guards_are_scoped_and_idempotent(self):
        self.assertEqual(fix.digest(self.original), fix.MANIFEST["original_sha256"])
        result = fix.corrected(self.original, self.listener)
        self.assertEqual(fix.digest(result), fix.MANIFEST["patched_sha256"])
        self.assertEqual(len(result), len(self.original))
        allowed = set()
        for item in fix.MANIFEST["changes"]:
            allowed.update(range(item["offset"], item["offset"] + len(bytes.fromhex(item["original"]))))
        changed = {i for i, (a, b) in enumerate(zip(self.original, result)) if a != b}
        self.assertTrue(changed)
        self.assertLessEqual(changed, allowed)
        self.assertEqual(fix.corrected(result, self.listener), result)

    def test_unknown_feature_library_is_rejected(self):
        bad = bytearray(self.original)
        bad[-1] ^= 1
        unchanged = bytes(bad)
        with self.assertRaisesRegex(ValueError, "unknown feature"):
            fix.corrected(bad, self.listener)
        self.assertEqual(bytes(bad), unchanged)

    def test_different_listener_is_rejected_even_for_patched_input(self):
        result = fix.corrected(self.original, self.listener)
        with self.assertRaisesRegex(ValueError, "unknown SensorListener"):
            fix.corrected(result, self.listener + b"changed")


if __name__ == "__main__":
    unittest.main()
