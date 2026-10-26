"""Regression checks against the paired vendor snapshot; no device/NVRAM I/O."""
import importlib.util
from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from validate_recording_nvram import validate

VENDOR_ROOT = TOOLS.parents[3] / "vendor/samsung/grandppltedx"
VENDOR = VENDOR_ROOT / "proprietary/vendor"
spec = importlib.util.spec_from_file_location(
    "fix_recording_lids", VENDOR_ROOT / "tools/fix_recording_lids.py")
fix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fix)


class RecordingNvramTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patched = (VENDOR / "lib/libaudiocustparam_vendor.so").read_bytes()
        before = bytearray(cls.patched)
        for offset, old, _ in fix.CHANGES:
            before[offset] = old
        cls.original = bytes(before)

    def test_original_selects_wrong_records(self):
        self.assertEqual(fix.digest(self.original), fix.ORIGINAL)
        with self.assertRaisesRegex(ValueError, "Audio_Buffer_DC_Calibration_Param"):
            validate(VENDOR, self.original)

    def test_correction_preserves_every_other_byte_and_is_idempotent(self):
        result = fix.corrected(self.original)
        self.assertEqual(result, self.patched)
        self.assertEqual(fix.corrected(result), result)
        differences = [i for i, (a, b) in enumerate(zip(self.original, result)) if a != b]
        self.assertEqual(differences, [offset for offset, _, _ in fix.CHANGES])
        self.assertEqual(len(result), len(self.original))
        self.assertEqual([(r[1], r[3]) for r in validate(VENDOR, result)],
                         [(63, 4054), (63, 4054), (64, 135), (64, 135)])

    def test_regressed_setter_is_rejected(self):
        bad = bytearray(self.patched)
        bad[13948] = 65
        with self.assertRaisesRegex(ValueError, "SetHdRecordParamToNV"):
            validate(VENDOR, bytes(bad))

    def test_unknown_library_is_rejected_before_modification(self):
        bad = bytearray(self.original)
        bad[-1] ^= 1
        unchanged = bytes(bad)
        with self.assertRaisesRegex(ValueError, "unknown"):
            fix.corrected(bad)
        self.assertEqual(bytes(bad), unchanged)


if __name__ == "__main__":
    unittest.main()
