# -*- coding: utf-8 -*-
"""StFormatter – format and parse .st files.

The .st file format used by CDS_ST_SYNC is:

    <declaration text>
    // --- implementation ---
    <implementation text>

The marker line ``// --- implementation ---`` separates the two sections.
When there is no implementation (GVL, DUT, Interface) the marker is omitted.
"""
from __future__ import print_function

import os as _os
import sys as _sys

# Resolve the package path for src/ imports when running inside CodeSys.
_PKG_DIR = _os.path.dirname(_os.path.abspath(__file__))
_SRC_DIR = _os.path.dirname(_PKG_DIR)
if _SRC_DIR not in _sys.path:
    _sys.path.insert(0, _SRC_DIR)

from interfaces.extractor import ITextFormatter


class StFormatter(ITextFormatter):
    """Formats .st file content from declaration + implementation parts.

    The marker ``// --- implementation ---`` is only emitted when an
    implementation value is present and non-empty.
    """

    MARKER = '// --- implementation ---'

    # ── public API ────────────────────────────────────────────────────────

    def format_st(self, declaration, implementation):
        """Combine declaration and implementation into a .st file string.

        Args:
            declaration: str – VAR section text.
            implementation: str or None – body text.

        Returns:
            str – full .st file content with LF line endings.
        """
        # Normalise inputs
        decl = self._normalise_line_endings(str(declaration or ''))
        impl = self._normalise_line_endings(
            str(implementation) if implementation is not None else ''
        )

        decl_stripped = decl.strip()
        impl_stripped = impl.strip()

        # Only declaration
        if not impl_stripped:
            return decl_stripped + '\n'

        # Only implementation (rare, but handle gracefully)
        if not decl_stripped:
            return self.MARKER + '\n' + impl_stripped + '\n'

        # Both parts present
        return decl_stripped + '\n' + self.MARKER + '\n' + impl_stripped + '\n'

    def parse_st(self, content):
        """Split a .st file into (declaration, implementation) parts.

        The first occurrence of the exact marker string on its own line
        separates the two sections.  If the marker is missing the whole
        file is treated as declaration.

        Args:
            content: str – raw file content.

        Returns:
            tuple[str, str or None] – (declaration, implementation).
        """
        if content is None:
            return ('', None)

        text = self._normalise_line_endings(str(content))
        if not text.strip():
            return ('', None)

        # Locate the first marker line (exact match, not just a substring).
        marker = self.MARKER
        lines = text.split('\n')

        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped == marker:
                # This line is the marker – split here.
                decl_lines = lines[:idx]
                impl_lines = lines[idx + 1:]

                decl = '\n'.join(decl_lines).strip()
                impl = '\n'.join(impl_lines).strip()

                return (decl, impl if impl else None)

        # No marker found – everything is declaration.
        return (text.strip(), None)

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _normalise_line_endings(text):
        """Replace Windows/Mac line endings with LF."""
        return text.replace('\r\n', '\n').replace('\r', '\n')
