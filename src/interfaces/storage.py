# -*- coding: utf-8 -*-
from __future__ import print_function

from abc import ABC, abstractmethod


class IStorage(ABC):
    """Storage abstraction for .st files and manifest.json.

    Implementations can write to the local file system, in-memory
    (for testing), or remote stores.
    """

    @abstractmethod
    def save_object(self, meta, declaration, implementation):
        """Persist a single text object.

        Args:
            meta: ObjectMeta – object metadata (used for path resolution).
            declaration: str – declaration text.
            implementation: str or None – implementation text (POU only).
        """

    @abstractmethod
    def load_object(self, meta):
        """Load the ST text for a single object.

        Args:
            meta: ObjectMeta
        Returns:
            tuple[str, str or None] – (declaration, implementation).
        """

    @abstractmethod
    def save_manifest(self, manifest):
        """Persist a Manifest.

        Args:
            manifest: Manifest
        """

    @abstractmethod
    def load_manifest(self):
        """Load and return the current Manifest stored by this IStorage.

        Returns:
            Manifest
        """

    @abstractmethod
    def watch_changes(self, callback):
        """Register a callback to be invoked when files change on disk.

        Args:
            callback: callable(str) – receives the changed file path.

        The callback may be called from a background thread; implementations
        should document threading guarantees.

        For implementations that cannot watch (e.g. in-memory), this is a
        no-op.
        """
