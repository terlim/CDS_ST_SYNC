# -*- coding: utf-8 -*-
from __future__ import print_function

import re as _re


# ── Module-level helpers ─────────────────────────────────────────────────

def _safe_name(native_obj):
    """Safely extract object name from a CodeSys native object."""
    name = getattr(native_obj, 'name', None)
    if name and isinstance(name, str) and name.strip():
        return name.strip()
    try:
        name = native_obj.get_name()
        if name and isinstance(name, str) and name.strip():
            return name.strip()
    except Exception:
        pass
    try:
        name = str(native_obj)
        if name.strip():
            return name.strip()
    except Exception:
        pass
    return 'unnamed'


def _to_guid_str(raw_guid):
    """Convert System.Guid or string to lowercase guid without braces."""
    if raw_guid is None:
        return None
    return str(raw_guid).replace('{', '').replace('}', '').strip().lower()


_FUNCTION_RETURN_RE = _re.compile(
    r'^\s*FUNCTION\s+\w+\s*:\s*(.+?)\s*$', _re.IGNORECASE
)


def _extract_return_type(declaration):
    """Extract return type from a FUNCTION header line, or None."""
    text = str(declaration or '')
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('{') or line.startswith('//') or line.startswith('(*'):
            continue
        match = _FUNCTION_RETURN_RE.match(line)
        if match is None:
            return None
        return_type = match.group(1)
        for marker in ('//', '(*'):
            idx = return_type.find(marker)
            if idx != -1:
                return_type = return_type[:idx]
        return_type = return_type.strip()
        return return_type or None
    return None


def _find_pou_type_enum():
    """Locate PouType enum from CodeSys globals or ScriptEngine."""
    import __main__
    enum = getattr(__main__, 'PouType', None)
    if enum is not None:
        return enum
    try:
        from ScriptEngine import PouType as enum
        return enum
    except Exception:
        return None


def _find_dut_type_enum():
    """Locate DutType enum from CodeSys globals or ScriptEngine."""
    try:
        from ScriptEngine import DutType
        return DutType
    except Exception:
        pass
    import __main__
    return getattr(__main__, 'DutType', None)


def _to_system_guid(guid_string):
    """Convert a GUID string to System.Guid for IronPython .NET APIs."""
    try:
        import System
        return System.Guid(guid_string.strip('{}'))
    except Exception:
        return guid_string


# ── CodeSysObjectProxy ───────────────────────────────────────────────────

from interfaces.bridge import ICodeSysObject


class CodeSysObjectProxy(ICodeSysObject):
    """Thin wrapper around a native CodeSys script object."""

    def __init__(self, native_object):
        self._native = native_object
        self._guid = None
        self._name = None
        self._type_guid = None

    @property
    def guid(self):
        if self._guid is None:
            raw = getattr(self._native, 'guid', None)
            self._guid = _to_guid_str(raw) if raw is not None else ''
        return self._guid

    @property
    def name(self):
        if self._name is None:
            self._name = _safe_name(self._native)
        return self._name

    @property
    def parent_guid(self):
        parent = getattr(self._native, 'parent', None)
        if parent is None:
            return ''
        raw = getattr(parent, 'guid', None)
        return _to_guid_str(raw) if raw is not None else ''

    @property
    def type_guid(self):
        if self._type_guid is None:
            raw = getattr(self._native, 'type_guid', None)
            self._type_guid = _to_guid_str(raw) if raw is not None else ''
        return self._type_guid

    @property
    def declaration_text(self):
        doc = getattr(self._native, 'textual_declaration', None)
        if doc is None:
            return None
        text = getattr(doc, 'text', None)
        if text is None:
            return None
        text = str(text)
        return text.replace('\r\n', '\n').strip() if text else ''

    @property
    def implementation_text(self):
        doc = getattr(self._native, 'textual_implementation', None)
        if doc is None:
            return None
        text = getattr(doc, 'text', None)
        if text is None:
            return None
        text = str(text)
        text = text.replace('\r\n', '\n').strip()
        return text if text else None

    @property
    def children(self):
        try:
            native_children = self._native.get_children(False)
        except Exception:
            return []
        return [CodeSysObjectProxy(child) for child in (native_children or [])]

    @property
    def parent(self):
        """Return parent proxy or None for root objects."""
        native_parent = getattr(self._native, 'parent', None)
        if native_parent is None:
            return None
        return CodeSysObjectProxy(native_parent)

    def __repr__(self):
        return 'CodeSysObjectProxy(name={0.name!r}, guid={0.guid!r})'.format(self)

    def __eq__(self, other):
        if isinstance(other, CodeSysObjectProxy):
            return self.guid == other.guid
        return False

    def __hash__(self):
        return hash(self.guid)
