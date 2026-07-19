# -*- coding: utf-8 -*-
"""TextExtractor – extracts Structured Text from CodeSys objects.

Works against the ICodeSysObject interface, not against any specific
CodeSys API implementation.  Only depends on the domain interfaces.
"""
from __future__ import print_function

import os as _os
import sys as _sys

# Resolve the package path for src/ imports when running inside CodeSys.
_PKG_DIR = _os.path.dirname(_os.path.abspath(__file__))
_SRC_DIR = _os.path.dirname(_PKG_DIR)
if _SRC_DIR not in _sys.path:
    _sys.path.insert(0, _SRC_DIR)

from interfaces.extractor import ITextExtractor


class TextExtractor(ITextExtractor):
    """Extracts declaration and implementation text from ICodeSysObject.

    Handles normalisation of line endings and whitespace so callers always
    receive clean, predictable ST text regardless of how CodeSys stores it.
    """

    # ── public API ────────────────────────────────────────────────────────

    def extract_declaration(self, obj):
        """Return the VAR section text of *obj*.

        Args:
            obj: ICodeSysObject

        Returns:
            str – normalised declaration text.  Never returns None;
            absent declarations are represented as an empty string.
        """
        if obj is None:
            return ''
        raw = obj.declaration_text
        return self._normalise(raw, allow_empty=True)

    def extract_implementation(self, obj):
        """Return the implementation body of *obj*.

        Args:
            obj: ICodeSysObject

        Returns:
            str or None – normalised implementation text, or None when the
            object has no implementation (GVL, DUT, Interface, etc.).
        """
        if obj is None:
            return None
        raw = obj.implementation_text
        return self._normalise(raw, allow_empty=False)

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _normalise(raw, allow_empty):
        """Normalise raw text from CodeSys.

        - Convert None to '' (when allow_empty) or None.
        - Replace Windows line endings with LF.
        - Strip leading/trailing whitespace.
        - If allow_empty is False and result is empty, return None.
        """
        if raw is None:
            return '' if allow_empty else None
        # coerce to str (IronPython may give unicode)
        text = str(raw)
        # normalise line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = text.strip()
        if not allow_empty and not text:
            return None
        return text
