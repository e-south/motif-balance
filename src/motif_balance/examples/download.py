"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/examples/download.py

Fetch one pinned publisher archive and reuse its checked local cache.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

import hashlib
import os
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen

from motif_balance.formats.structured import read_bounded_regular_file

MAX_ARCHIVE_BYTES = 32 * 1024 * 1024


def default_cache() -> Path:
    """Keep downloaded inputs outside projects and installed package files."""
    if os.environ.get("XDG_CACHE_HOME"):
        root = Path(os.environ["XDG_CACHE_HOME"])
    elif sys.platform == "darwin":
        root = Path.home() / "Library/Caches"
    else:
        root = Path.home() / ".cache"
    return root / "motif-balance"


def archive_bytes(url: str, digest: str, cache: Path) -> bytes:
    """Never use unchecked cached bytes or replace a corrupt cache silently."""
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Invalid publisher archive checksum")
    if not url.startswith("https://"):
        raise ValueError("Publisher download requires HTTPS")
    path = cache / f"{digest}.zip"
    if os.path.lexists(path):
        data = read_bounded_regular_file(path, max_bytes=MAX_ARCHIVE_BYTES)
    else:
        with urlopen(url, timeout=60) as response:
            data = response.read(MAX_ARCHIVE_BYTES + 1)
        if len(data) > MAX_ARCHIVE_BYTES:
            raise ValueError("Publisher archive exceeds the size limit")
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("Publisher archive checksum differs from the source record")
    if not os.path.lexists(path):
        cache.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".download-", dir=cache)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
            try:
                os.link(temporary, path, follow_symlinks=False)
            except FileExistsError:
                # A concurrent preparation may have cached the same download.
                existing = read_bounded_regular_file(path, max_bytes=MAX_ARCHIVE_BYTES)
                if hashlib.sha256(existing).hexdigest() != digest:
                    raise ValueError("Concurrent cache entry has a different checksum") from None
        finally:
            temporary.unlink(missing_ok=True)
    return data
