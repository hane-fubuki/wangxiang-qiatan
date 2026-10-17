"""Serve only the verified portable package named by the local release manifest."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat

MAX_RELEASE_BYTES = 128 * 1024 * 1024
RELEASE_FILENAME = r"(?:wangxiang-qiatan|wisdom-tavern)-[0-9]{8}-windows-x64\.zip"


class ReleaseUnavailable(ValueError):
    pass


def _regular_path(path: Path, *, directory=False):
    # OneDrive files can have a reparse attribute without being links. Reject
    # actual symlinks/junctions, including directories, without blocking those.
    for part in (path, *path.parents):
        tag = getattr(part.lstat(), "st_reparse_tag", 0)
        if part.is_symlink() or tag in {0xA0000003, 0xA000000C}:
            raise ReleaseUnavailable()
    info = path.stat()
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ReleaseUnavailable()
    return info


class Releases:
    def __init__(self, directory):
        self.directory = Path(directory).absolute()

    def open_latest(self):
        """Return safe public metadata and an open verified file at position 0."""
        stream = None
        try:
            _regular_path(self.directory, directory=True)
            manifest = self.directory / "latest.json"
            if _regular_path(manifest).st_size > 4096:
                raise ReleaseUnavailable()
            with manifest.open("rb") as source:
                data = json.loads(source.read(4097))
            if not isinstance(data, dict):
                raise ReleaseUnavailable()
            filename, version = data.get("filename"), data.get("version")
            size, checksum = data.get("size"), data.get("sha256")
            if (not isinstance(filename, str) or not re.fullmatch(RELEASE_FILENAME, filename)
                    or not isinstance(version, str) or not re.fullmatch(r"[0-9]{4}\.[0-9]{2}\.[0-9]{2}(?:\.[0-9]+)?", version)
                    or type(size) is not int or not 4 <= size <= MAX_RELEASE_BYTES
                    or not isinstance(checksum, str) or not re.fullmatch(r"[a-f0-9]{64}", checksum)):
                raise ReleaseUnavailable()
            target = self.directory / filename
            before = _regular_path(target)
            if target.resolve().parent != self.directory.resolve() or before.st_size != size:
                raise ReleaseUnavailable()
            stream = target.open("rb")
            opened = os.fstat(stream.fileno())
            if (before.st_dev, before.st_ino, before.st_size) != (opened.st_dev, opened.st_ino, opened.st_size):
                raise ReleaseUnavailable()
            digest = hashlib.sha256()
            if stream.read(4) != b"PK\x03\x04":
                raise ReleaseUnavailable()
            stream.seek(0)
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
            if stream.tell() != size or digest.hexdigest() != checksum:
                raise ReleaseUnavailable()
            stream.seek(0)
            return {"filename": filename, "version": version, "size": size, "sha256": checksum,
                    "url": "/downloads/latest.zip"}, stream
        except (OSError, ValueError, TypeError, RecursionError):
            if stream is not None:
                stream.close()
            raise ReleaseUnavailable("下载包暂未准备好，请稍后再试。") from None
