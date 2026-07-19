# -*- coding: utf-8 -*-
from __future__ import print_function

from abc import ABCMeta, abstractmethod


class ICodeSysObject(object):
    __metaclass__ = ABCMeta
    """Interface for a single CodeSys project object.

    Attributes (read-only):
        guid: str
        name: str
        parent_guid: str or '00000000-...'
        type_guid: str – CodeSys type GUID.
        declaration_text: str or None
        implementation_text: str or None
        children: list[ICodeSysObject]
    """

    @property
    @abstractmethod
    def guid(self):
        """Return the object GUID as a lowercase string without braces."""

    @property
    @abstractmethod
    def name(self):
        """Return the object name."""

    @property
    @abstractmethod
    def parent_guid(self):
        """Return the parent GUID or zero-GUID string."""

    @property
    @abstractmethod
    def type_guid(self):
        """Return the CodeSys type GUID as a lowercase string without braces."""

    @property
    @abstractmethod
    def declaration_text(self):
        """Return textual_declaration content, or None."""

    @property
    @abstractmethod
    def implementation_text(self):
        """Return textual_implementation content, or None."""

    @property
    @abstractmethod
    def children(self):
        """Return a list of immediate child ICodeSysObject instances."""


class IObjectReader(object):
    __metaclass__ = ABCMeta
    """Read-only access to the CodeSys project tree."""

    @abstractmethod
    def get_all_objects(self):
        """Return a flat list of all ICodeSysObject in the project."""

    @abstractmethod
    def get_object_by_guid(self, guid):
        """Return an ICodeSysObject by GUID, or None.

        Args:
            guid: str – GUID without braces, case-insensitive.
        """

    @abstractmethod
    def get_project_tree(self):
        """Return a ProjectTree representing the full hierarchy."""


class IObjectWriter(object):
    __metaclass__ = ABCMeta
    """Write access to the CodeSys project."""

    @abstractmethod
    def update_text(self, guid, declaration, implementation):
        """Update the text content of an existing object.

        Args:
            guid: str – target object GUID.
            declaration: str – new declaration text.
            implementation: str or None – new implementation text (POU only).
        Returns:
            OperationResult
        """

    @abstractmethod
    def create_pou(self, name, kind, container_guid, declaration):
        """Create a new POU.

        Args:
            name: str – object name.
            kind: str – 'program' | 'function_block' | 'function'.
            container_guid: str – parent container GUID.
            declaration: str – full declaration text (including VAR block).
        Returns:
            ICodeSysObject – the created object.
        """

    @abstractmethod
    def create_gvl(self, name, container_guid):
        """Create a new Global Variable List.

        Args:
            name: str.
            container_guid: str – parent container GUID.
        Returns:
            ICodeSysObject
        """

    @abstractmethod
    def create_dut(self, name, container_guid, dut_kind):
        """Create a new DUT.

        Args:
            name: str.
            container_guid: str – parent container GUID.
            dut_kind: str – 'structure' | 'alias' | 'union'.
        Returns:
            ICodeSysObject
        """

    @abstractmethod
    def create_folder(self, name, parent_guid):
        """Create a new folder.

        Args:
            name: str.
            parent_guid: str – parent container GUID.
        Returns:
            ICodeSysObject
        """


class ITimestampReader(object):
    __metaclass__ = ABCMeta
    """Time-stamp reading for live-sync."""

    @abstractmethod
    def get_timestamps(self):
        """Return a dict mapping guid (str) → timestamp_ms (int)."""


class ICodeSysBridge(IObjectReader, IObjectWriter, ITimestampReader):
    """Aggregate interface for all CodeSys interactions.

    Implementations of this interface are the ONLY place where CodeSys API
    calls are made.  All application services depend on this interface,
    enabling unit testing with mock bridges.
    """
    pass
