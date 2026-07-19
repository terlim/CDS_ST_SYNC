# -*- coding: utf-8 -*-
"""Tests for TextExtractor."""
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

from infrastructure.text_extractor import TextExtractor


# ── Stub ICodeSysObject ───────────────────────────────────────────────────

class StubObject(object):
    """Minimal stub implementing ICodeSysObject for testing TextExtractor."""

    def __init__(self, guid='stub-1', name='Stub', parent_guid=None,
                 type_guid='ffbfa93a-b94d-45fc-a329-229860183b1d',
                 declaration_text=None, implementation_text=None,
                 children=None):
        self._guid = guid
        self._name = name
        self._parent_guid = parent_guid or '00000000-0000-0000-0000-000000000000'
        self._type_guid = type_guid
        self._declaration_text = declaration_text
        self._implementation_text = implementation_text
        self._children = children or []

    @property
    def guid(self):
        return self._guid

    @property
    def name(self):
        return self._name

    @property
    def parent_guid(self):
        return self._parent_guid

    @property
    def type_guid(self):
        return self._type_guid

    @property
    def declaration_text(self):
        return self._declaration_text

    @property
    def implementation_text(self):
        return self._implementation_text

    @property
    def children(self):
        return self._children


# ── Tests ─────────────────────────────────────────────────────────────────

class TestExtractDeclaration(unittest.TestCase):
    """Tests for TextExtractor.extract_declaration()."""

    def setUp(self):
        self.extractor = TextExtractor()

    def test_normal_text(self):
        obj = StubObject(declaration_text='VAR\n    x : INT;\nEND_VAR')
        result = self.extractor.extract_declaration(obj)
        self.assertEqual(result, 'VAR\n    x : INT;\nEND_VAR')

    def test_none_text(self):
        """None declaration → empty string."""
        obj = StubObject(declaration_text=None)
        result = self.extractor.extract_declaration(obj)
        self.assertEqual(result, '')

    def test_none_object(self):
        """None object → empty string (safe guard)."""
        result = self.extractor.extract_declaration(None)
        self.assertEqual(result, '')

    def test_crlf_normalisation(self):
        """Windows line endings → LF."""
        obj = StubObject(declaration_text='VAR\r\n    x : INT;\r\nEND_VAR')
        result = self.extractor.extract_declaration(obj)
        self.assertNotIn('\r\n', result)
        self.assertNotIn('\r', result)
        self.assertEqual(result, 'VAR\n    x : INT;\nEND_VAR')

    def test_strip_whitespace(self):
        """Leading/trailing whitespace removed."""
        obj = StubObject(declaration_text='  \n  VAR\nEND_VAR  \n  ')
        result = self.extractor.extract_declaration(obj)
        self.assertEqual(result, 'VAR\nEND_VAR')

    def test_empty_string(self):
        obj = StubObject(declaration_text='')
        result = self.extractor.extract_declaration(obj)
        self.assertEqual(result, '')

    def test_unicode_text(self):
        """Unicode characters preserved."""
        obj = StubObject(
            declaration_text=u'PROGRAM \u041f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0430\nVAR\nEND_VAR'
        )
        result = self.extractor.extract_declaration(obj)
        self.assertIn(u'\u041f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0430', result)


class TestExtractImplementation(unittest.TestCase):
    """Tests for TextExtractor.extract_implementation()."""

    def setUp(self):
        self.extractor = TextExtractor()

    def test_normal_text(self):
        obj = StubObject(implementation_text='x := 1;\ny := 2;')
        result = self.extractor.extract_implementation(obj)
        self.assertEqual(result, 'x := 1;\ny := 2;')

    def test_none_text(self):
        """None implementation (GVL/DUT) → None."""
        obj = StubObject(implementation_text=None)
        result = self.extractor.extract_implementation(obj)
        self.assertIsNone(result)

    def test_none_object(self):
        """None object → None."""
        result = self.extractor.extract_implementation(None)
        self.assertIsNone(result)

    def test_empty_text(self):
        """Empty implementation string → None (treated as absent)."""
        obj = StubObject(implementation_text='')
        result = self.extractor.extract_implementation(obj)
        self.assertIsNone(result)

    def test_whitespace_only(self):
        """Whitespace-only implementation → None."""
        obj = StubObject(implementation_text='   \n  \n   ')
        result = self.extractor.extract_implementation(obj)
        self.assertIsNone(result)

    def test_crlf_normalisation(self):
        """Windows line endings → LF."""
        obj = StubObject(implementation_text='x := 1;\r\ny := 2;\r\n')
        result = self.extractor.extract_implementation(obj)
        self.assertNotIn('\r\n', result)
        self.assertNotIn('\r', result)
        self.assertEqual(result, 'x := 1;\ny := 2;')

    def test_trailing_newlines_stripped(self):
        obj = StubObject(implementation_text='  x := 1;\n\n  ')
        result = self.extractor.extract_implementation(obj)
        self.assertEqual(result, 'x := 1;')

    def test_unicode_text(self):
        """Unicode in implementation preserved."""
        obj = StubObject(
            implementation_text=u'// \u043a\u043e\u043c\u043c\u0435\u043d\u0442\u0430\u0440\u0438\u0439\nx := 1;'
        )
        result = self.extractor.extract_implementation(obj)
        self.assertIn(u'\u043a\u043e\u043c\u043c\u0435\u043d\u0442\u0430\u0440\u0438\u0439', result)


if __name__ == '__main__':
    unittest.main()
