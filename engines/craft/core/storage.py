"""File access. Originals are read-only; every output is a new key.

ARCHITECTURE.md 7: an uploaded file is never modified. There is no write path
here that can overwrite an existing key -- `write` refuses.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

from .errors import InvalidInput


class Storage(Protocol):
    def read(self, key: str) -> bytes: ...
    def write(self, key: str, data: bytes) -> str: ...
    def exists(self, key: str) -> bool: ...


class LocalStorage:
    """Filesystem-backed. Used by tests and local development."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _p(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise InvalidInput(f"Key escapes the storage root: {key!r}")
        return p

    def read(self, key: str) -> bytes:
        p = self._p(key)
        if not p.is_file():
            raise InvalidInput(f"No such object: {key}")
        return p.read_bytes()

    def exists(self, key: str) -> bool:
        return self._p(key).is_file()

    def write(self, key: str, data: bytes) -> str:
        p = self._p(key)
        if p.exists():
            # Outputs are new versions, never overwrites.
            raise InvalidInput(f"Refusing to overwrite an existing object: {key}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
