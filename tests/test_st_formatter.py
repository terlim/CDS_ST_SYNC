# -*- coding: utf-8 -*-
"""Tests for StFormatter."""
from __future__ import print_function

import os
import sys
import unittest

# Ensure src/ is on path when running from tests/
_SELF_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_SELF_DIR)
_SRC_DIR = os.path.join(_PROJECT_DIR, 'src')
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from infrastructure.st_formatter import StFormatter


class TestFormatSt(unittest.TestCase):
    """Tests for StFormatter.format_st()."""

    def setUp(self):
        self.fmt = StFormatter()

    # ── basic combinations ────────────────────────────────────────────────

    def test_both_present(self):
        """Declaration + implementation → string with marker."""
        result = self.fmt.format_st('VAR\nEND_VAR', 'x := 1;')
        self.assertEqual(
            result,
            'VAR\nEND_VAR\n// --- implementation ---\nx := 1;\n'
        )

    def test_only_declaration(self):
        """GVL / DUT style – no implementation, no marker."""
        result = self.fmt.format_st(
            'VAR_GLOBAL\n    g_x : INT;\nEND_VAR', None
        )
        self.assertEqual(result, 'VAR_GLOBAL\n    g_x : INT;\nEND_VAR\n')

    def test_only_declaration_empty_impl(self):
        """Empty implementation string is treated as absent."""
        result = self.fmt.format_st('VAR\nEND_VAR', '')
        self.assertEqual(result, 'VAR\nEND_VAR\n')

    def test_only_implementation(self):
        """Declaration absent, only implementation."""
        result = self.fmt.format_st('', 'x := 1;')
        self.assertEqual(
            result,
            '// --- implementation ---\nx := 1;\n'
        )

    def test_both_empty(self):
        """Edge: both are empty."""
        result = self.fmt.format_st('', '')
        self.assertEqual(result, '\n')

    def test_none_declaration(self):
        """None declaration → treated as ''."""
        result = self.fmt.format_st(None, 'x := 1;')
        self.assertEqual(
            result,
            '// --- implementation ---\nx := 1;\n'
        )

    # ── line endings ──────────────────────────────────────────────────────

    def test_crlf_normalisation(self):
        """Windows line endings → LF."""
        result = self.fmt.format_st('VAR\r\nEND_VAR', 'x := 1;\r\ny := 2;')
        self.assertEqual(
            result,
            'VAR\nEND_VAR\n// --- implementation ---\nx := 1;\ny := 2;\n'
        )

    def test_mixed_line_endings(self):
        """Mixed \\r\\n and bare \\r → all become LF."""
        result = self.fmt.format_st('VAR\r\n  a:INT;\r\nEND_VAR',
                                     'x := 1;\ry := 2;')
        self.assertNotIn('\r\n', result)
        self.assertNotIn('\r', result)

    # ── whitespace ────────────────────────────────────────────────────────

    def test_trailing_whitespace_trimmed(self):
        """Leading/trailing whitespace is trimmed for each section."""
        result = self.fmt.format_st('  VAR\n  END_VAR  ', '  x := 1;  ')
        self.assertEqual(
            result,
            'VAR\n  END_VAR\n// --- implementation ---\nx := 1;\n'
        )


class TestParseSt(unittest.TestCase):
    """Tests for StFormatter.parse_st()."""

    def setUp(self):
        self.fmt = StFormatter()

    # ── basic cases ───────────────────────────────────────────────────────

    def test_full_file(self):
        """Declaration + marker + implementation."""
        decl, impl = self.fmt.parse_st(
            'PROGRAM PLC_PRG\nVAR\nEND_VAR\n'
            '// --- implementation ---\n'
            'x := 1;\n'
        )
        self.assertEqual(decl, 'PROGRAM PLC_PRG\nVAR\nEND_VAR')
        self.assertEqual(impl, 'x := 1;')

    def test_only_declaration(self):
        """No marker → everything is declaration."""
        decl, impl = self.fmt.parse_st(
            'VAR_GLOBAL CONSTANT\n    c_x : INT := 1;\nEND_VAR\n'
        )
        self.assertEqual(
            decl,
            'VAR_GLOBAL CONSTANT\n    c_x : INT := 1;\nEND_VAR'
        )
        self.assertIsNone(impl)

    def test_empty_file(self):
        """Empty string → empty declaration, no implementation."""
        decl, impl = self.fmt.parse_st('')
        self.assertEqual(decl, '')
        self.assertIsNone(impl)

    def test_none_content(self):
        """None input → empty declaration, no implementation."""
        decl, impl = self.fmt.parse_st(None)
        self.assertEqual(decl, '')
        self.assertIsNone(impl)

    def test_whitespace_only(self):
        """Whitespace-only file → empty declaration."""
        decl, impl = self.fmt.parse_st('   \n  \n  ')
        self.assertEqual(decl, '')
        self.assertIsNone(impl)

    # ── marker edge cases ─────────────────────────────────────────────────

    def test_implementation_without_declaration(self):
        """Marker at the very start → empty declaration, has implementation."""
        decl, impl = self.fmt.parse_st(
            '// --- implementation ---\n'
            'x := 1;\n'
        )
        self.assertEqual(decl, '')
        self.assertEqual(impl, 'x := 1;')

    def test_multiple_markers(self):
        """Only the first marker is considered."""
        decl, impl = self.fmt.parse_st(
            'DECL\n'
            '// --- implementation ---\n'
            'impl1\n'
            '// --- implementation ---\n'
            'impl2\n'
        )
        self.assertEqual(decl, 'DECL')
        self.assertEqual(impl, 'impl1\n// --- implementation ---\nimpl2')

    def test_marker_in_code_not_counted(self):
        """Marker as part of a code line, not a standalone line."""
        decl, impl = self.fmt.parse_st(
            'VAR\nEND_VAR\n'
            '// --- implementation --- is just a comment here\n'
            'x := 1;\n'
        )
        # The line is "// --- implementation --- is just a comment here"
        # which has extra text → does NOT match the exact marker.
        self.assertIsNone(impl)
        self.assertIn('VAR', decl)

    def test_marker_indented(self):
        """Marker with leading spaces is still recognised."""
        decl, impl = self.fmt.parse_st(
            'DECL\n'
            '   // --- implementation ---   \n'
            'impl\n'
        )
        self.assertEqual(decl, 'DECL')
        self.assertEqual(impl, 'impl')

    # ── line endings ──────────────────────────────────────────────────────

    def test_crlf_normalisation(self):
        """Windows line endings are normalised."""
        decl, impl = self.fmt.parse_st(
            'VAR\r\nEND_VAR\r\n'
            '// --- implementation ---\r\n'
            'x := 1;\r\n'
        )
        self.assertEqual(decl, 'VAR\nEND_VAR')
        self.assertEqual(impl, 'x := 1;')

    def test_mixed_line_endings_parse(self):
        """Mixed \\r\\n and \\r in file."""
        decl, impl = self.fmt.parse_st(
            'VAR\r\n  a:INT;\rEND_VAR\n'
            '// --- implementation ---\n'
            'x := 1;\ry := 2;\r\nz := 3;'
        )
        self.assertIsNotNone(decl)
        self.assertIsNotNone(impl)

    # ── trailing newline ──────────────────────────────────────────────────

    def test_trailing_newline_stripped(self):
        """Trailing empty lines are stripped from both sections."""
        decl, impl = self.fmt.parse_st(
            'VAR\nEND_VAR\n\n\n'
            '// --- implementation ---\n'
            'x := 1;\n\n\n'
        )
        self.assertEqual(decl, 'VAR\nEND_VAR')
        self.assertEqual(impl, 'x := 1;')

    # ── empty sections around marker ──────────────────────────────────────

    def test_empty_implementation(self):
        """Marker present but no implementation text after it."""
        decl, impl = self.fmt.parse_st(
            'DECL\n'
            '// --- implementation ---\n'
            '\n'
        )
        self.assertEqual(decl, 'DECL')
        self.assertIsNone(impl)


class TestRoundtrip(unittest.TestCase):
    """format_st → parse_st should return the original parts."""

    def setUp(self):
        self.fmt = StFormatter()

    def _assert_roundtrip(self, decl, impl):
        """Assert that format_st(decl, impl) → parse_st → (decl, impl)."""
        formatted = self.fmt.format_st(decl, impl)
        parsed_decl, parsed_impl = self.fmt.parse_st(formatted)
        self.assertEqual(parsed_decl, decl)
        self.assertEqual(parsed_impl, impl)

    def test_both_present(self):
        self._assert_roundtrip('VAR\nEND_VAR', 'x := 1;')

    def test_only_declaration(self):
        self._assert_roundtrip(
            'VAR_GLOBAL CONSTANT\n    c_x : INT := 1;\nEND_VAR',
            None
        )

    def test_multiline(self):
        self._assert_roundtrip(
            'PROGRAM Main\nVAR\n    x : INT;\nEND_VAR',
            'x := x + 1;\nIF x > 10 THEN\n    x := 0;\nEND_IF'
        )

    def test_empty_declaration(self):
        self._assert_roundtrip('', 'impl text')

    def test_unicode_identifiers(self):
        """Russian identifiers are preserved through roundtrip."""
        self._assert_roundtrip(
            u'PROGRAM \u041f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0430\nVAR\nEND_VAR',
            u'x := 1;'
        )


if __name__ == '__main__':
    unittest.main()
