"""Read dependency/symbol metadata from the device's little-endian ARM ELF files.

This is a static inventory, not a replacement for Android linker validation.
Uses only Python's standard library; no host cross-toolchain is required.
"""
import struct
from pathlib import Path


class Elf32:
    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        if self.data[:6] != b"\x7fELF\x01\x01":
            raise ValueError(f"{path}: expected ELF32 little-endian")
        header = struct.unpack_from("<HHIIIIIHHHHHH", self.data, 16)
        self.machine = header[1]
        self.sections = [struct.unpack_from("<IIIIIIIIII", self.data,
                         header[5] + i * header[10]) for i in range(header[11])]
        self.needed = []
        self.symbols = {}
        for section in self.sections:
            if section[1] not in (6, 11):
                continue
            if not section[9]:
                raise ValueError(f"{path}: zero ELF entry size")
            strings = self.section_data(section[6])
            for offset in range(section[4], section[4] + section[5], section[9]):
                if section[1] == 6:  # SHT_DYNAMIC
                    tag, value = struct.unpack_from("<iI", self.data, offset)
                    if tag == 1:  # DT_NEEDED
                        self.needed.append(self.string(strings, value))
                else:  # SHT_DYNSYM
                    name, value, size, info, _, index = struct.unpack_from(
                        "<IIIBBH", self.data, offset)
                    if name:
                        self.symbols[self.string(strings, name)] = {
                            "value": value, "size": size, "section": index,
                            "binding": info >> 4, "type": info & 15}

    @staticmethod
    def string(data, offset):
        return data[offset:data.index(b"\0", offset)].decode("utf-8", "replace")

    def section_data(self, index):
        section = self.sections[index]
        return self.data[section[4]:section[4] + section[5]]

    def symbol_data(self, name):
        symbol = self.symbols[name]
        section = self.sections[symbol["section"]]
        # Thumb function symbols have their low address bit set.
        address = symbol["value"] & ~1 if symbol["type"] == 2 else symbol["value"]
        offset = section[4] + address - section[3]
        return self.data[offset:offset + symbol["size"]]

    def exports(self, name):
        return name in self.symbols and self.symbols[name]["section"] != 0
