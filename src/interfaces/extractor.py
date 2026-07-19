# -*- coding: utf-8 -*-
from __future__ import print_function

from abc import ABC, abstractmethod


class ITextExtractor(ABC):
    """Extract Structured Text from a CodeSys object."""

    @abstractmethod
    def extract_declaration(self, obj):
        """Return the declaration section of a text object.

        Args:
            obj: ICodeSysObject
        Returns:
            str – declaration text (VAR section).
        """

    @abstractmethod
    def extract_implementation(self, obj):
        """Return the implementation section of a text object.

        Args:
            obj: ICodeSysObject
        Returns:
            str or None – implementation text, or None if the object has
            no implementation (GVL, DUT, Interface).
        """


class ITextFormatter(ABC):
    """Format and parse .st file content."""

    @abstractmethod
    def format_st(self, declaration, implementation):
        """Combine declaration and implementation into a single .st string.

        Args:
            declaration: str
            implementation: str or None
        Returns:
            str – full .st file content.
        """

    @abstractmethod
    def parse_st(self, content):
        """Split a .st file back into declaration and implementation.

        Args:
            content: str – raw .st file content.
        Returns:
            tuple[str, str or None] – (declaration, implementation).
        """
