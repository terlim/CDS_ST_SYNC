# -*- coding: utf-8 -*-
"""FileSystemStorage – filesystem-backed IStorage implementation for CDS_ST_SYNC.

Stores .st files and manifest.json under a configurable sync root directory.
Every write is atomic (temp file + rename) to avoid partial writes from
crashing the system.

Compatible with IronPython 2.7 and CPython 3.
"""
from __future__ import print_function

import io
import os
import tempfile
import sys as _sys

# Ensure src/ is importable when running inside CodeSys.
_SELF_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.dirname(_SELF_DIR)  # src/ directory
if _SRC_DIR not in _sys.path:
    _sys.path.insert(0, _SRC_DIR)

from interfaces.storage import IStorage
from infrastructure.st_formatter import StFormatter


class FileSystemStorage(IStorage):
    """Filesystem-backed storage for .st files and manifest.json.

    Directory layout::

        sync_dir/
        ├── manifest.json
        ├── Device/
        │   └── Plc Logic/
        │       └── Application/
        │           └── PROGRAMS/
        │               └── PLC_PRG.st

    Every ``save_*`` method writes atomically via a temp file so that
    readers never observe a half-written file.
    """

    # ── lifecycle ────────────────────────────────────────────────────────────

    def __init__(self, sync_dir):
        """Initialise with an absolute or relative sync root.

        Args:
            sync_dir: str – root directory for all sync artefacts.
        """
        self._sync_dir = os.path.abspath(str(sync_dir or './sync/'))
        self._formatter = StFormatter()

    # ── IStorage implementation ──────────────────────────────────────────────

    def save_object(self, meta, declaration, implementation):
        """Persist a single .st file for *meta*.

        Steps:
        1. Resolve the target path via ``meta.relative_path``.
        2. Ensure parent directories exist.
        3. Format the ST content with ``StFormatter.format_st``.
        4. Write atomically (temp file + rename).
        5. Update ``meta.file_mtime`` and ``meta.sha1``.

        Args:
            meta: ObjectMeta
            declaration: str
            implementation: str or None
        """
        target = self._object_path(meta)
        self._ensure_dir(os.path.dirname(target))

        content = self._formatter.format_st(declaration, implementation)
        self._atomic_write(target, content)

        # Update metadata after successful write.
        try:
            meta.file_mtime = os.path.getmtime(target)
        except OSError:
            meta.file_mtime = None
        meta.compute_sha1(declaration, implementation)

    def load_object(self, meta):
        """Load the ST text for a single object.

        Args:
            meta: ObjectMeta

        Returns:
            tuple[str, str or None] – (declaration, implementation).

        Raises:
            IOError – if the file cannot be read.
        """
        path = self._object_path(meta)
        if not os.path.isfile(path):
            raise IOError('File not found: {0}'.format(path))

        content = self._read_utf8(path)
        return self._formatter.parse_st(content)

    def save_manifest(self, manifest):
        """Atomically persist *manifest* to ``sync_dir/manifest.json``."""
        target = self._manifest_path()
        self._ensure_dir(os.path.dirname(target))
        self._atomic_write(target, manifest.to_json())

    def load_manifest(self):
        """Load Manifest from disk.

        Returns an empty Manifest when no file exists on disk yet.
        """
        path = self._manifest_path()
        if not os.path.isfile(path):
            # Return a fresh empty manifest.
            from domain.models import Manifest
            return Manifest()

        text = self._read_utf8(path)
        from domain.models import Manifest
        return Manifest.from_json(text)

    def watch_changes(self, callback):
        """Not available in IronPython – use QFileSystemWatcher in GUI.

        Raises NotImplementedError with a guidance message.
        """
        raise NotImplementedError(
            'watch_changes is not available in IronPython 2.7. '
            'Use QFileSystemWatcher in the Python 3 GUI process instead.'
        )

    # ── private helpers ──────────────────────────────────────────────────────

    def _object_path(self, meta):
        """Return the absolute path for *meta*'s .st file."""
        return os.path.join(self._sync_dir, meta.relative_path)

    def _manifest_path(self):
        """Return the absolute path for manifest.json."""
        return os.path.join(self._sync_dir, 'manifest.json')

    @staticmethod
    def _ensure_dir(dirpath):
        """Create directory tree if it does not exist.

        Handles both Python 3 (``exist_ok``) and IronPython 2.7 (try/except).
        """
        if not dirpath:
            return
        if not os.path.isdir(dirpath):
            try:
                os.makedirs(dirpath)
            except OSError:
                # Race: another thread/process created the directory between
                # the isdir check and the makedirs call.  If it is now a
                # directory we are fine; otherwise re-raise.
                if not os.path.isdir(dirpath):
                    raise

    @staticmethod
    def _read_utf8(path):
        """Read the full content of *path* as a UTF-8 string."""
        with io.open(path, 'r', encoding='utf-8') as handle:
            return handle.read()

    def _atomic_write(self, path, content):
        """Write *content* atomically via a temp-file-then-rename strategy.

        The temp file is created in the same directory as *path* so that
        ``os.rename`` stays on the same filesystem (guaranteed atomic on
        POSIX; best-effort on Windows).
        """
        parent = os.path.dirname(path) or '.'
        fd, tmp_path = tempfile.mkstemp(
            prefix='.cds-st-sync-tmp-',
            dir=parent,
        )
        try:
            os.close(fd)
            # On Windows, mkstemp leaves the file handle open; close it
            # before writing.
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            # Write directly to the temp path.
            with io.open(tmp_path, 'w', encoding='utf-8') as handle:
                handle.write(content)
            # Atomically replace the target.
            if os.path.exists(path):
                os.remove(path)
            os.rename(tmp_path, path)
        except Exception:
            # Clean up the temp file on failure.
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise
