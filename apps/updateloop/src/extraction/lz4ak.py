"""Support Arknights' LZ4AK Unity bundle blocks.

Arknights stores its post-2.5.04 LZ4 blocks with the literal and match
nibbles swapped in the sequence token and the match offset in big-endian
order. UnityPy labels these blocks as ``LZHAM`` because the numeric flag is
reused, so its normal decompressor rejects them.
"""

import lz4.block
from UnityPy.files.BundleFile import BundleFile

ARKNIGHTS_COMPRESSION_FLAGS = {4, 5}
_COMPRESSION_MASK = 0x3F
_EXTENDED_LENGTH = 0x0F
_MAX_LENGTH_BYTE = 0xFF
_MINIMUM_MATCH_LENGTH = 4


def _read_extra_length(
    data: bytes | bytearray | memoryview, position: int, end: int
) -> tuple[int, int]:
    """Read the variable-length suffix used by long literals and matches."""

    length = 0
    while position < end:
        value = data[position]
        length += value
        position += 1
        if value != _MAX_LENGTH_BYTE:
            break
    return length, position


def decompress_lz4ak(
    compressed_data: bytes | bytearray | memoryview, uncompressed_size: int
) -> bytes:
    """Decode one Arknights LZ4AK block into its standard LZ4 form."""

    data = bytearray(compressed_data)
    input_position = 0
    output_position = 0
    compressed_size = len(data)

    while input_position < compressed_size:
        token = data[input_position]
        literal_length = token & _EXTENDED_LENGTH
        match_length = (token >> 4) & _EXTENDED_LENGTH
        data[input_position] = (literal_length << 4) | match_length
        input_position += 1

        if literal_length == _EXTENDED_LENGTH:
            extra, input_position = _read_extra_length(data, input_position, compressed_size)
            literal_length += extra

        input_position += literal_length
        output_position += literal_length
        if output_position >= uncompressed_size:
            break
        if input_position + 1 >= compressed_size:
            raise ValueError("truncated LZ4AK match offset")

        # Arknights writes the two-byte match offset in big-endian order.
        offset = (data[input_position] << 8) | data[input_position + 1]
        data[input_position] = offset & 0xFF
        data[input_position + 1] = offset >> 8
        input_position += 2

        if match_length == _EXTENDED_LENGTH:
            extra, input_position = _read_extra_length(data, input_position, compressed_size)
            match_length += extra
        output_position += match_length + _MINIMUM_MATCH_LENGTH

    return lz4.block.decompress(data, uncompressed_size)


def patch_unitypy() -> None:
    """Make UnityPy use :func:`decompress_lz4ak` for Arknights blocks."""

    original = BundleFile.decompress_data
    if getattr(original, "_arkwaifu_lz4ak", False):
        return

    def decompress_data(self, compressed_data, uncompressed_size, flags, index=0):
        # Unity's bundle compression mask is the low six bits. Arknights uses
        # Unity's reserved compression 4/5 flags for LZ4AK.
        if (int(flags) & _COMPRESSION_MASK) in ARKNIGHTS_COMPRESSION_FLAGS:
            return decompress_lz4ak(compressed_data, uncompressed_size)
        return original(self, compressed_data, uncompressed_size, flags, index)

    decompress_data._arkwaifu_lz4ak = True
    BundleFile.decompress_data = decompress_data
