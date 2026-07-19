# -*- coding: utf-8 -*-
from __future__ import print_function

from abc import ABCMeta, abstractmethod


# ── Sync actions for conflict resolution ──────────────────────────────

class SyncAction(object):
    __metaclass__ = ABCMeta
    """Enumeration of possible sync conflict actions."""

    EXPORT_TO_FILE = 'export_to_file'
    IMPORT_TO_IDE = 'import_to_ide'
    SKIP = 'skip'

    _ALL = frozenset([EXPORT_TO_FILE, IMPORT_TO_IDE, SKIP])

    @classmethod
    def is_valid(cls, value):
        """Return True if value is a recognised SyncAction constant."""
        return value in cls._ALL


# ── Service interfaces ────────────────────────────────────────────────

class IExportService(object):
    __metaclass__ = ABCMeta
    """Exports textual CodeSys objects to .st files on disk."""

    @abstractmethod
    def export(self, filter_obj):
        """Run the export operation.

        Args:
            filter_obj: ObjectFilter
        Returns:
            OperationResult
        """


class IImportService(object):
    __metaclass__ = ABCMeta
    """Imports .st files from disk back into CodeSys objects."""

    @abstractmethod
    def import_(self, filter_obj):
        """Run the import operation.

        Args:
            filter_obj: ObjectFilter
        Returns:
            OperationResult
        """


class IConflictResolver(object):
    __metaclass__ = ABCMeta
    """Resolves conflicts between IDE and file versions."""

    @abstractmethod
    def resolve(self, meta, ide_timestamp_ms, file_mtime):
        """Decide which direction to sync.

        Args:
            meta: ObjectMeta
            ide_timestamp_ms: int – timestamp from CodeSys object.
            file_mtime: float – os.path.getmtime of the .st file.
        Returns:
            str – one of SyncAction constants.
        """


class ILiveSyncService(object):
    __metaclass__ = ABCMeta
    """Continuous auto-sync between CodeSys and file system."""

    @abstractmethod
    def start(self):
        """Start the live-sync monitoring loop."""

    @abstractmethod
    def stop(self):
        """Stop live-sync."""

    @abstractmethod
    def is_running(self):
        """Return True if live-sync is currently active.

        Returns:
            bool
        """
