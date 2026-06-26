import struct
import zlib

from django.core.files.uploadedfile import SimpleUploadedFile

_PNG_HEADER = b"\x89PNG\r\n\x1a\n"


def _make_png_bytes() -> bytes:
    raw = zlib.compress(b"\x00\x00\x00\x00\x00")
    chunk = (
        struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        + struct.pack(
            ">I",
            zlib.crc32(b"IHDR" + struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) & 0xFFFFFFFF,
        )
    )
    idat = (
        struct.pack(">I", len(raw))
        + b"IDAT"
        + raw
        + struct.pack(">I", zlib.crc32(b"IDAT" + raw) & 0xFFFFFFFF)
    )
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
    return _PNG_HEADER + chunk + idat + iend


def _make_image(name: str = "test.png") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, _make_png_bytes(), content_type="image/png")
