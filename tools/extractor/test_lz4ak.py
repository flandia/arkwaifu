import unittest

from lz4ak import decompress_lz4ak


class LZ4AKTest(unittest.TestCase):
    def test_literal_only_block(self):
        # AK token: literal length in the low nibble.
        self.assertEqual(decompress_lz4ak(b"\x05hello", 5), b"hello")

    def test_match_offset_is_big_endian(self):
        # An LZ4 match with offset three, followed by a literal-only tail.
        self.assertEqual(
            decompress_lz4ak(
                bytes.fromhex("c36162630003056263616263"),
                24,
            ),
            b"abcabcabcabcabcabcabcabc",
        )


if __name__ == "__main__":
    unittest.main()
