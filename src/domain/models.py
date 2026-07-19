# -*- coding: utf-8 -*-
from __future__ import print_function

import hashlib
import json
import os
import time

# ── Safe file-name characters ──────────────────────────────────────────
_UNSAFE_RE = None  # compiled lazily


def _get_unsafe_re():
    """Compile the unsafe-filename regex once."""
    global _UNSAFE_RE
    if _UNSAFE_RE is None:
        import re as _re
        _UNSAFE_RE = _re.compile(r'[<>:"/\\|?*]')
    return _UNSAFE_RE


def safe_filename(name):
    """Replace filesystem-unsafe characters with '_'."""
    return _get_unsafe_re().sub('_', name or 'object').strip(' .') or 'object'


def _sha1_hex(value):
    """Return hex digest of SHA-1 for a string."""
    if value is None:
        return None
    return hashlib.sha1(value.encode('utf-8')).hexdigest()


def _drop_none(adict):
    """Remove keys with None values from a dict (shallow)."""
    return {k: v for k, v in adict.items() if v is not None}


class ObjectMeta(object):
    """Metadata for one CodeSys textual object.

    Attributes:
        guid: str – unique object GUID (without braces).
        name: str – object name.
        type: str – semantic type (pou | gvl | dut | interface | persistent
              | task_local).
        pou_kind: str or None – for type=='pou': program | function_block |
                  function.
        path: list[str] – folder hierarchy e.g. ['Device','Plc Logic',...].
        relative_path: str – computed relative file path ending in .st.
        sha1: str or None – hex digest of the .st file content.
        ide_timestamp_ms: int or None – CODESYS MetaObject.Timestamp.
        file_mtime: float or None – os.path.getmtime value.
    """

    def __init__(self, guid, name, obj_type, path=None, pou_kind=None,
                 sha1=None, ide_timestamp_ms=None, file_mtime=None):
        self.guid = guid
        self.name = name
        self.type = obj_type
        self.path = path or []
        self.pou_kind = pou_kind
        self.sha1 = sha1
        self.ide_timestamp_ms = ide_timestamp_ms
        self.file_mtime = file_mtime

    # ── computed ──────────────────────────────────────────────────────

    @property
    def relative_path(self):
        """Filesystem path relative to sync root, ending with .st."""
        parts = self.path + [self.name]
        safe_parts = [safe_filename(p) for p in parts]
        safe_parts[-1] = safe_parts[-1] + '.st'
        return os.path.join(*safe_parts)

    # ── serialisation helpers ─────────────────────────────────────────

    def to_dict(self):
        """Return a JSON-serialisable dict (excludes computed fields)."""
        d = {
            'guid': self.guid,
            'name': self.name,
            'type': self.type,
            'path': self.path,
            'file': self.relative_path,
        }
        if self.pou_kind:
            d['pou_kind'] = self.pou_kind
        if self.sha1:
            d['sha1'] = self.sha1
        if self.ide_timestamp_ms is not None:
            d['ide_timestamp_ms'] = self.ide_timestamp_ms
        if self.file_mtime is not None:
            d['file_mtime'] = self.file_mtime
        return d

    @classmethod
    def from_dict(cls, data):
        """Create ObjectMeta from a JSON-loaded dict."""
        return cls(
            guid=data['guid'],
            name=data['name'],
            obj_type=data['type'],
            path=data.get('path', []),
            pou_kind=data.get('pou_kind'),
            sha1=data.get('sha1'),
            ide_timestamp_ms=data.get('ide_timestamp_ms'),
            file_mtime=data.get('file_mtime'),
        )

    # ── hash / equality ───────────────────────────────────────────────

    def compute_sha1(self, declaration, implementation=None):
        """Compute and set sha1 from the given ST parts."""
        content = declaration
        if implementation:
            content = content + '\n// --- implementation ---\n' + implementation
        self.sha1 = _sha1_hex(content)
        return self.sha1

    def __eq__(self, other):
        if not isinstance(other, ObjectMeta):
            return False
        return self.guid == other.guid

    def __hash__(self):
        return hash(self.guid)

    def __repr__(self):
        return 'ObjectMeta(guid={0!r}, name={1!r}, type={2!r})'.format(
            self.guid, self.name, self.type)


class Manifest(object):
    """Inventory of all sync objects.

    Attributes:
        version: int – manifest format version.
        project_name: str – CODESYS project name.
        exported_at: str – ISO-8601 timestamp of export.
        objects: list[ObjectMeta]
    """

    VERSION = 1

    def __init__(self, project_name='', exported_at=None, objects=None):
        self.version = self.VERSION
        self.project_name = project_name or ''
        self.exported_at = exported_at or time.strftime('%Y-%m-%dT%H:%M:%S')
        self._objects = []           # ordered list
        self._by_guid = {}           # guid → ObjectMeta
        if objects:
            for obj in objects:
                self.add_object(obj)

    # ── collection management ─────────────────────────────────────────

    def add_object(self, meta):
        """Add or replace an ObjectMeta entry."""
        if meta.guid in self._by_guid:
            idx = next(i for i, o in enumerate(self._objects)
                       if o.guid == meta.guid)
            self._objects[idx] = meta
        else:
            self._objects.append(meta)
        self._by_guid[meta.guid] = meta

    def get_by_guid(self, guid):
        """Return ObjectMeta by guid, or None."""
        return self._by_guid.get(guid)

    def get_by_path(self, path_list):
        """Return first ObjectMeta whose path list matches, or None.

        Args:
            path_list: list[str] – the CodeSys folder hierarchy to match.
        """
        for obj in self._objects:
            if obj.path == path_list:
                return obj
        return None

    @property
    def objects(self):
        """Return the ordered list of ObjectMeta."""
        return list(self._objects)

    # ── diff ──────────────────────────────────────────────────────────

    def diff(self, other):
        """Compute a ManifestDiff against another manifest."""
        other_guids = {o.guid for o in other.objects}
        self_guids = {o.guid for o in self._objects}

        added = [o for o in self._objects if o.guid not in other_guids]
        removed = [o for o in other.objects if o.guid not in self_guids]

        changed = []
        unchanged = []
        for o in self._objects:
            if o.guid in other_guids:
                oth = other.get_by_guid(o.guid)
                if oth is not None and oth.sha1 != o.sha1:
                    changed.append(o)
                else:
                    unchanged.append(o)

        return ManifestDiff(
            added=added,
            removed=removed,
            changed=changed,
            unchanged=unchanged,
        )

    # ── serialisation ─────────────────────────────────────────────────

    def to_dict(self):
        """Return a JSON-serialisable dict."""
        return {
            'version': self.version,
            'project': self.project_name,
            'exported_at': self.exported_at,
            'objects': [o.to_dict() for o in self._objects],
        }

    @classmethod
    def from_dict(cls, data):
        """Create Manifest from a JSON-loaded dict."""
        m = cls(
            project_name=data.get('project', ''),
            exported_at=data.get('exported_at', ''),
        )
        m.version = data.get('version', cls.VERSION)
        for entry in data.get('objects', []):
            m.add_object(ObjectMeta.from_dict(entry))
        return m

    def to_json(self):
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, text):
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(text))

    def __len__(self):
        return len(self._objects)

    def __repr__(self):
        return 'Manifest(project={0!r}, objects={1})'.format(
            self.project_name, len(self._objects))


class ManifestDiff(object):
    """Result of comparing two manifests.

    Attributes:
        added: list[ObjectMeta]
        removed: list[ObjectMeta]
        changed: list[ObjectMeta]
        unchanged: list[ObjectMeta]
    """

    def __init__(self, added=None, removed=None, changed=None, unchanged=None):
        self.added = list(added or [])
        self.removed = list(removed or [])
        self.changed = list(changed or [])
        self.unchanged = list(unchanged or [])

    @property
    def has_changes(self):
        """True if there are any differences."""
        return bool(self.added or self.removed or self.changed)

    def __repr__(self):
        return ('ManifestDiff(added={0}, removed={1}, changed={2}, '
                'unchanged={3})').format(
            len(self.added), len(self.removed),
            len(self.changed), len(self.unchanged))


# ── ProjectTree ───────────────────────────────────────────────────────────

class _TreeNode(object):
    """Internal tree node."""
    __slots__ = ('guid', 'name', 'obj_type', 'parent_guid', 'children')

    def __init__(self, guid, name, obj_type, parent_guid):
        self.guid = guid
        self.name = name
        self.obj_type = obj_type
        self.parent_guid = parent_guid
        self.children = []

    def to_nested_dict(self):
        """Return nested dict suitable for JSON serialisation."""
        result = {
            'guid': self.guid,
            'name': self.name,
            'type': self.obj_type,
        }
        if self.children:
            result['children'] = [c.to_nested_dict() for c in self.children]
        return result


class ProjectTree(object):
    """Hierarchical representation of CodeSys objects for display.

    Usage::

        tree = ProjectTree()
        tree.add_node(guid, name, obj_type, parent_guid)
        ...
        nested = tree.to_nested_list()  # list of root-level dicts
    """

    def __init__(self):
        self._nodes = {}        # guid → _TreeNode
        self._roots = []        # ordered list of root-level _TreeNode
        self._root_order = []   # ordered root guids

    def add_node(self, guid, name, obj_type, parent_guid=None):
        """Add a node to the tree.

        Args:
            guid: str – node GUID.
            name: str – display name.
            obj_type: str – semantic type (pou, gvl, dut, folder, ...).
            parent_guid: str or None – parent GUID. None = root level.
        """
        node = _TreeNode(guid, name, obj_type, parent_guid)
        self._nodes[guid] = node

        if parent_guid is None or parent_guid == '00000000-0000-0000-0000-000000000000':
            self._roots.append(node)
            self._root_order.append(guid)
        else:
            parent = self._nodes.get(parent_guid)
            if parent is not None:
                parent.children.append(node)
            else:
                # Orphan – place at root temporarily
                self._roots.append(node)
                self._root_order.append(guid)

    def to_nested_list(self):
        """Return a list of root-level dicts, each with optional 'children'."""
        result = []
        seen = set()
        for guid in self._root_order:
            node = self._nodes.get(guid)
            if node is None or node.guid in seen:
                continue
            seen.add(node.guid)
            result.append(node.to_nested_dict())
        return result

    def __len__(self):
        return len(self._nodes)


# ── OperationResult ───────────────────────────────────────────────────────

class OperationResult(object):
    """Outcome of a batch operation (export / import).

    Attributes:
        success: bool
        total: int
        completed: int
        errors: list[dict] – each has keys guid, object, error.
        messages: list[str] – informational messages.
    """

    def __init__(self, success=True, total=0, completed=0,
                 errors=None, messages=None):
        self.success = success
        self.total = total
        self.completed = completed
        self.errors = list(errors or [])
        self.messages = list(messages or [])

    def add_error(self, guid, obj_name, error_msg):
        """Record an error for a specific object."""
        self.errors.append({
            'guid': guid,
            'object': obj_name,
            'error': error_msg,
        })
        self.success = False

    def add_message(self, message):
        """Add an informational message."""
        self.messages.append(message)

    def __repr__(self):
        return ('OperationResult(success={0}, total={1}, completed={2}, '
                'errors={3})').format(self.success, self.total,
                                      self.completed, len(self.errors))
