"""Reject damaged payloads and layouts before distributing boot images."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import unittest


spec = importlib.util.spec_from_file_location(
    "boot_image", Path(__file__).resolve().parents[1] / "verify_boot_image.py")
boot_image = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot_image)


class BootImageTest(unittest.TestCase):
    def setUp(self):
        self.dt = b"test device tree"
        header = bytearray(2048)
        header[:8] = b"ANDROID!"
        struct.pack_into("<10I", header, 8, 32, 0x40004000, 16, 0x44000000,
                         0, 0, 0x4e000000, 2048, len(self.dt), 0)
        header[48:64] = b"SRPPI01A000KU\0\0\0"
        digest = hashlib.sha1()
        self.image = header
        for payload in (b"K" * 32, b"R" * 16, b"", self.dt):
            digest.update(payload)
            digest.update(struct.pack("<I", len(payload)))
            self.image += payload
            self.image += b"\0" * (-len(self.image) % 2048)
        self.image[576:596] = digest.digest()

    def test_valid_legacy_image_and_optional_trailer(self):
        result = boot_image.verify(self.image, self.dt)
        self.assertFalse(result["samsung_marker_at_payload_end"])
        result = boot_image.verify(self.image + b"SEANDROIDENFORCE", self.dt)
        self.assertTrue(result["samsung_marker_at_payload_end"])

    def test_payload_corruption(self):
        self.image[2050] ^= 1
        with self.assertRaisesRegex(ValueError, "SHA-1"):
            boot_image.verify(self.image, self.dt)

    def test_mismatched_device_tree(self):
        with self.assertRaisesRegex(ValueError, "DT does not match"):
            boot_image.verify(self.image, b"X" * len(self.dt))

    def test_truncated_payload(self):
        with self.assertRaisesRegex(ValueError, "truncated"):
            boot_image.verify(self.image[:4100], self.dt)

    def test_wrong_load_address(self):
        struct.pack_into("<I", self.image, 12, 0x10008000)
        with self.assertRaisesRegex(ValueError, "load addresses"):
            boot_image.verify(self.image, self.dt)


if __name__ == "__main__":
    unittest.main()
