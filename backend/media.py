"""Private raster attachments with fixed IDs, byte limits and structural checks."""
from __future__ import annotations

import os
from pathlib import Path
import re
import struct
import threading
import uuid
import zlib

MAX_UPLOAD = 8 * 1024 * 1024
MAX_IMAGE = 20 * 1024 * 1024
MIMES = {"image/png", "image/jpeg", "image/webp"}


def image_info(data: bytes):
    """Read bounded raster headers, rejecting truncated containers and huge canvases."""
    width = height = 0
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime, pos, ended, pixels = "image/png", 8, False, []
        depth = color = interlace = 0
        while pos + 12 <= len(data):
            length = int.from_bytes(data[pos:pos + 4], "big")
            kind = data[pos + 4:pos + 8]
            end = pos + 12 + length
            if end > len(data) or length > MAX_IMAGE:
                raise ValueError("PNG 图片不完整")
            chunk = data[pos + 8:pos + 8 + length]
            if zlib.crc32(kind + chunk) & 0xffffffff != int.from_bytes(data[end - 4:end], "big"):
                raise ValueError("PNG 图片校验失败")
            if pos == 8:
                if kind != b"IHDR" or length != 13:
                    raise ValueError("PNG 图片格式不正确")
                width, height = struct.unpack(">II", chunk[:8])
                depth, color, compression, filtering, interlace = chunk[8:]
                allowed = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
                if depth not in allowed.get(color, ()) or compression or filtering or interlace not in (0, 1):
                    raise ValueError("PNG 图片格式不正确")
                if not (1 <= width <= 8192 and 1 <= height <= 8192 and width * height <= 24_000_000):
                    raise ValueError("图片尺寸无效或过大")
            elif kind == b"IHDR":
                raise ValueError("PNG 图片格式不正确")
            if kind == b"IDAT":
                pixels.append(chunk)
            pos = end
            if kind == b"IEND":
                ended = length == 0 and end == len(data)
                break
        if not ended or not pixels:
            raise ValueError("PNG 图片不完整")
        channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
        passes = [(0, 0, 1, 1)] if not interlace else [(0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2)]
        rows = []
        for x, y, dx, dy in passes:
            pw, ph = max(0, (width - x + dx - 1) // dx), max(0, (height - y + dy - 1) // dy)
            if pw and ph:
                rows.extend([1 + (pw * channels * depth + 7) // 8] * ph)
        expected = sum(rows)
        try:
            decoder = zlib.decompressobj()
            raw = decoder.decompress(b"".join(pixels), expected + 1)
        except zlib.error:
            raise ValueError("PNG 像素数据损坏") from None
        if len(raw) != expected or not decoder.eof or decoder.unused_data:
            raise ValueError("PNG 像素数据不完整")
        position = 0
        for size in rows:
            if raw[position] > 4:
                raise ValueError("PNG 像素滤波格式不正确")
            position += size
    elif data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9"):
        mime, pos, scanned = "image/jpeg", 2, False
        while pos + 4 <= len(data):
            if data[pos] != 255:
                raise ValueError("JPEG 图片格式不正确")
            while pos < len(data) and data[pos] == 255:
                pos += 1
            if pos >= len(data):
                break
            marker = data[pos]
            pos += 1
            if marker == 0xda:
                length = int.from_bytes(data[pos:pos + 2], "big")
                scanned = length >= 6 and pos + length < len(data) - 2
                break
            if marker == 0xd9:
                break
            if marker in (0x01, *range(0xd0, 0xd8)):
                continue
            length = int.from_bytes(data[pos:pos + 2], "big")
            if length < 2 or pos + length > len(data):
                raise ValueError("JPEG 图片不完整")
            if marker in (0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf):
                if length < 8:
                    raise ValueError("JPEG 图片格式不正确")
                height, width = struct.unpack(">HH", data[pos + 3:pos + 7])
            pos += length
        if not scanned:
            raise ValueError("JPEG 缺少像素数据")
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        mime, pos, pixels = "image/webp", 12, False
        if len(data) < 30 or int.from_bytes(data[4:8], "little") + 8 != len(data):
            raise ValueError("WebP 图片不完整")
        while pos + 8 <= len(data):
            kind = data[pos:pos + 4]
            length = int.from_bytes(data[pos + 4:pos + 8], "little")
            end = pos + 8 + length
            if end > len(data):
                raise ValueError("WebP 图片不完整")
            chunk = data[pos + 8:end]
            if kind == b"VP8X" and length == 10:
                if chunk[0] & 2:
                    raise ValueError("请上传静态图片，暂不支持动态 WebP")
                width = 1 + int.from_bytes(chunk[4:7], "little")
                height = 1 + int.from_bytes(chunk[7:10], "little")
            elif kind == b"VP8 " and length > 10 and chunk[3:6] == b"\x9d\x01\x2a":
                pixels = True
                if not width:
                    width, height = (n & 0x3fff for n in struct.unpack("<HH", chunk[6:10]))
            elif kind == b"VP8L" and length > 5 and chunk[0] == 0x2f:
                pixels = True
                if not width:
                    bits = int.from_bytes(chunk[1:5], "little")
                    width, height = 1 + (bits & 0x3fff), 1 + ((bits >> 14) & 0x3fff)
            pos = end + length % 2
        if pos != len(data) or not pixels:
            raise ValueError("WebP 图片格式不正确")
    else:
        raise ValueError("仅支持 PNG、JPEG 和 WebP 图片")
    if not (1 <= width <= 8192 and 1 <= height <= 8192 and width * height <= 24_000_000):
        raise ValueError("图片尺寸无效或过大，请缩小至 2400 万像素以内")
    return mime, width, height


class MediaStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def add(self, data, mime=None, *, generated=False):
        if not data or len(data) > (MAX_IMAGE if generated else MAX_UPLOAD):
            raise ValueError("单张上传图片不能超过 8 MiB；生成图片不能超过 20 MiB")
        actual, width, height = image_info(data)
        if mime is not None and mime != actual:
            raise ValueError("图片内容与文件类型不一致")
        with self.lock:
            files = [p for p in self.directory.iterdir() if re.fullmatch(r"[a-f0-9]{32}", p.name) and p.is_file()]
            if len(files) >= 1000 or sum(p.stat().st_size for p in files) + len(data) > 512 * 1024 * 1024:
                raise ValueError("图片存储已达上限，请在本机整理 .tavern/media 后重试")
            identifier = uuid.uuid4().hex
            with (self.directory / identifier).open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        return {"id": identifier, "url": "/media/" + identifier, "mime": actual, "width": width, "height": height}

    def path(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-f0-9]{32}", identifier):
            raise ValueError("图片编号无效")
        path = self.directory / identifier
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()) or not path.is_file() or path.resolve().parent != self.directory.resolve():
            raise ValueError("图片不存在，请重新上传")
        return path

    def read(self, identifier):
        path = self.path(identifier)
        if path.stat().st_size > MAX_IMAGE:
            raise ValueError("图片过大")
        data = path.read_bytes()
        mime, width, height = image_info(data)
        return {"id": identifier, "url": "/media/" + identifier, "mime": mime, "width": width, "height": height}, data

    def attachments(self, identifiers):
        if not isinstance(identifiers, list) or len(identifiers) > 4:
            raise ValueError("每条消息最多附加 4 张图片")
        if any(not isinstance(item, str) for item in identifiers) or len(set(identifiers)) != len(identifiers):
            raise ValueError("图片编号无效或重复")
        return [self.read(item)[0] for item in identifiers]
