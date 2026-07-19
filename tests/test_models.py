# -*- coding: utf-8 -*-
"""Tests for domain models: ObjectMeta, Manifest, ManifestDiff, ObjectFilter,
OperationResult, ProjectTree, SyncSettings."""

from __future__ import print_function

import json
import os
import tempfile
import time

import pytest

# Ensure the src directory is on sys.path (tests run from repo root).
import sys as _sys
_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.normpath(os.path.join(_here, '..'))
if _root not in _sys.path:
    _sys.path.insert(0, _root)

from src.domain.models import (   # noqa: E402
    ObjectMeta, Manifest, ManifestDiff, ProjectTree, OperationResult,
    safe_filename,
)
from src.domain.filter import (   # noqa: E402
    ObjectFilter, is_textual_type, classify_type_guid,
)
from src.domain.settings import SyncSettings  # noqa: E402


# ══════════════════════════════════════════════════════════════════════
# ObjectMeta
# ══════════════════════════════════════════════════════════════════════

class TestObjectMeta(object):
    """Tests for ObjectMeta."""

    def test_basic_construction(self):
        meta = ObjectMeta(
            guid='guid-001',
            name='PLC_PRG',
            obj_type='pou',
            path=['Device', 'Plc Logic', 'Application', 'PROGRAMS'],
            pou_kind='program',
        )
        assert meta.guid == 'guid-001'
        assert meta.name == 'PLC_PRG'
        assert meta.type == 'pou'
        assert meta.pou_kind == 'program'
        assert meta.path == ['Device', 'Plc Logic', 'Application', 'PROGRAMS']
        assert meta.sha1 is None
        assert meta.ide_timestamp_ms is None
        assert meta.file_mtime is None

    def test_defaults(self):
        meta = ObjectMeta(guid='g1', name='X', obj_type='gvl')
        assert meta.path == []
        assert meta.pou_kind is None
        assert meta.sha1 is None
        assert meta.ide_timestamp_ms is None
        assert meta.file_mtime is None

    def test_relative_path(self):
        meta = ObjectMeta(
            guid='g1', name='PLC_PRG', obj_type='pou',
            path=['Device', 'Plc Logic', 'Application', 'PROGRAMS'],
        )
        expected = os.path.join(
            'Device', 'Plc Logic', 'Application', 'PROGRAMS', 'PLC_PRG.st',
        )
        assert meta.relative_path == expected

    def test_relative_path_special_chars(self):
        meta = ObjectMeta(
            guid='g1', name='fb:Menu*Item', obj_type='pou',
            path=['CORE<test>'],
        )
        rp = meta.relative_path
        assert ':' not in rp
        assert '*' not in rp
        assert '<' not in rp
        assert '>' not in rp

    def test_to_dict_roundtrip(self):
        meta = ObjectMeta(
            guid='guid-x', name='fb_Menu', obj_type='pou',
            path=['Core', 'Class'], pou_kind='function_block',
            sha1='deadbeef', ide_timestamp_ms=123456, file_mtime=789.0,
        )
        d = meta.to_dict()
        restored = ObjectMeta.from_dict(d)
        assert restored.guid == meta.guid
        assert restored.name == meta.name
        assert restored.type == meta.type
        assert restored.path == meta.path
        assert restored.pou_kind == meta.pou_kind
        assert restored.sha1 == meta.sha1
        assert restored.ide_timestamp_ms == meta.ide_timestamp_ms
        assert restored.file_mtime == meta.file_mtime

    def test_compute_sha1(self):
        meta = ObjectMeta(guid='g', name='n', obj_type='pou')
        sha1 = meta.compute_sha1('DECL', 'IMPL')
        assert sha1 is not None
        assert len(sha1) == 40
        # same input → same hash
        sha2 = meta.compute_sha1('DECL', 'IMPL')
        assert sha1 == sha2
        # different input → different hash
        sha3 = meta.compute_sha1('DECL', 'OTHER')
        assert sha1 != sha3

    def test_equality(self):
        a = ObjectMeta(guid='x', name='a', obj_type='pou')
        b = ObjectMeta(guid='x', name='b', obj_type='gvl')
        assert a == b   # equality by guid only
        assert hash(a) == hash(b)

        c = ObjectMeta(guid='y', name='a', obj_type='pou')
        assert a != c


# ══════════════════════════════════════════════════════════════════════
# Manifest
# ══════════════════════════════════════════════════════════════════════

def _make_meta(guid, name='o', obj_type='pou'):
    return ObjectMeta(guid=guid, name=name, obj_type=obj_type)


class TestManifest(object):
    """Tests for Manifest."""

    def test_empty_manifest(self):
        m = Manifest(project_name='Test')
        assert m.version == 1
        assert m.project_name == 'Test'
        assert len(m) == 0
        assert m.objects == []

    def test_add_and_get(self):
        m = Manifest()
        a = _make_meta('a')
        b = _make_meta('b')
        m.add_object(a)
        m.add_object(b)
        assert len(m) == 2
        assert m.get_by_guid('a') is a
        assert m.get_by_guid('b') is b
        assert m.get_by_guid('c') is None

    def test_get_by_path(self):
        m = Manifest()
        a = ObjectMeta('g1', 'X', 'pou', path=['A', 'B'])
        b = ObjectMeta('g2', 'Y', 'gvl', path=['A'])
        m.add_object(a)
        m.add_object(b)
        assert m.get_by_path(['A', 'B']) is a
        assert m.get_by_path(['A']) is b
        assert m.get_by_path(['C']) is None

    def test_replace_by_guid(self):
        m = Manifest()
        a1 = _make_meta('x', name='first')
        a2 = _make_meta('x', name='second')
        m.add_object(a1)
        m.add_object(a2)   # should replace
        assert len(m) == 1
        assert m.get_by_guid('x').name == 'second'

    def test_diff_added(self):
        old = Manifest()
        new = Manifest()
        new.add_object(_make_meta('a'))
        d = new.diff(old)
        assert d.has_changes
        assert len(d.added) == 1
        assert d.added[0].guid == 'a'
        assert len(d.removed) == 0
        assert len(d.changed) == 0

    def test_diff_removed(self):
        old = Manifest()
        old.add_object(_make_meta('a'))
        new = Manifest()
        d = new.diff(old)
        assert len(d.removed) == 1
        assert d.removed[0].guid == 'a'

    def test_diff_changed(self):
        old = Manifest()
        old.add_object(ObjectMeta('a', 'X', 'pou', sha1='111'))
        new = Manifest()
        new.add_object(ObjectMeta('a', 'X', 'pou', sha1='222'))
        d = new.diff(old)
        assert len(d.changed) == 1
        assert len(d.unchanged) == 0

    def test_diff_unchanged(self):
        old = Manifest()
        old.add_object(ObjectMeta('a', 'X', 'pou', sha1='111'))
        new = Manifest()
        new.add_object(ObjectMeta('a', 'X', 'pou', sha1='111'))
        d = new.diff(old)
        assert len(d.unchanged) == 1
        assert not d.has_changes

    def test_to_dict_roundtrip(self):
        m = Manifest(project_name='P')
        m.add_object(ObjectMeta(
            'g', 'n', 'pou', path=['D'], pou_kind='program',
            sha1='abc', ide_timestamp_ms=1, file_mtime=2.0,
        ))
        d = m.to_dict()
        restored = Manifest.from_dict(d)
        assert restored.project_name == 'P'
        assert len(restored) == 1
        r = restored.get_by_guid('g')
        assert r.name == 'n'
        assert r.sha1 == 'abc'

    def test_json_roundtrip(self):
        m = Manifest(project_name='JsonTest')
        m.add_object(_make_meta('g1'))
        j = m.to_json()
        restored = Manifest.from_json(j)
        assert restored.project_name == 'JsonTest'
        assert len(restored) == 1


# ══════════════════════════════════════════════════════════════════════
# ManifestDiff
# ══════════════════════════════════════════════════════════════════════

class TestManifestDiff(object):
    def test_empty(self):
        d = ManifestDiff()
        assert not d.has_changes
        assert d.added == []
        assert d.removed == []
        assert d.changed == []
        assert d.unchanged == []

    def test_with_changes(self):
        d = ManifestDiff(added=[_make_meta('a')])
        assert d.has_changes


# ══════════════════════════════════════════════════════════════════════
# ProjectTree
# ══════════════════════════════════════════════════════════════════════

class TestProjectTree(object):
    def test_build_flat_tree(self):
        t = ProjectTree()
        t.add_node('1', 'Root', 'folder')
        t.add_node('2', 'Child', 'pou')
        result = t.to_nested_list()
        assert len(result) == 2
        names = {n['name'] for n in result}
        assert names == {'Root', 'Child'}

    def test_build_nested_tree(self):
        t = ProjectTree()
        t.add_node('1', 'Device', 'folder')
        t.add_node('2', 'Plc', 'folder', parent_guid='1')
        t.add_node('3', 'PLC_PRG', 'pou', parent_guid='2')
        result = t.to_nested_list()
        assert len(result) == 1
        root = result[0]
        assert root['name'] == 'Device'
        assert len(root['children']) == 1
        child = root['children'][0]
        assert child['name'] == 'Plc'
        assert len(child['children']) == 1
        assert child['children'][0]['name'] == 'PLC_PRG'

    def test_zero_guid_is_root(self):
        t = ProjectTree()
        t.add_node('1', 'X', 'folder',
                   parent_guid='00000000-0000-0000-0000-000000000000')
        roots = t.to_nested_list()
        assert len(roots) == 1


# ══════════════════════════════════════════════════════════════════════
# OperationResult
# ══════════════════════════════════════════════════════════════════════

class TestOperationResult(object):
    def test_success_default(self):
        r = OperationResult()
        assert r.success
        assert r.total == 0
        assert r.completed == 0
        assert r.errors == []
        assert r.messages == []

    def test_add_error(self):
        r = OperationResult(total=5, completed=4)
        r.add_error('g1', 'obj1', 'something went wrong')
        assert not r.success
        assert len(r.errors) == 1
        assert r.errors[0]['guid'] == 'g1'
        assert r.errors[0]['object'] == 'obj1'

    def test_add_message(self):
        r = OperationResult()
        r.add_message('hello')
        assert 'hello' in r.messages


# ══════════════════════════════════════════════════════════════════════
# ObjectFilter
# ══════════════════════════════════════════════════════════════════════

class TestObjectFilter(object):
    def test_include_pou(self):
        f = ObjectFilter(include_pou=True, include_gvl=False, include_dut=False,
                         include_interface=False)
        pou = ObjectMeta('g', 'n', 'pou')
        gvl = ObjectMeta('g', 'n', 'gvl')
        assert f.matches(pou)
        assert not f.matches(gvl)

    def test_specific_guids_overrides(self):
        f = ObjectFilter(
            include_pou=False, include_gvl=False,
            specific_guids=['abc'],
        )
        meta = ObjectMeta('abc', 'n', 'pou')      # pou excluded by type
        assert f.matches(meta)                    # but included specifically

    def test_specific_guids_none_means_all(self):
        f = ObjectFilter(specific_guids=None, include_pou=True)
        assert f.matches(ObjectMeta('any', 'n', 'pou'))

    def test_all_on(self):
        f = ObjectFilter.all_on()
        for t in ('pou', 'gvl', 'dut', 'interface', 'persistent', 'task_local'):
            assert f.matches(ObjectMeta('g', 'n', t))

    def test_default_is_textual_only(self):
        f = ObjectFilter()
        assert f.matches(ObjectMeta('g', 'n', 'pou'))
        assert f.matches(ObjectMeta('g', 'n', 'gvl'))
        assert f.matches(ObjectMeta('g', 'n', 'dut'))
        assert f.matches(ObjectMeta('g', 'n', 'interface'))
        assert not f.matches(ObjectMeta('g', 'n', 'persistent'))
        assert not f.matches(ObjectMeta('g', 'n', 'task_local'))


# ══════════════════════════════════════════════════════════════════════
# Type helpers
# ══════════════════════════════════════════════════════════════════════

class TestTypeHelpers(object):
    def test_is_textual_type_known(self):
        assert is_textual_type('{6f9dac99-8de1-4efc-8465-68ac443b7d08}')
        assert is_textual_type('6f9dac99-8de1-4efc-8465-68ac443b7d08')
        assert is_textual_type('FFBFA93A-B94D-45FC-A329-229860183B1D')

    def test_is_textual_type_unknown(self):
        assert not is_textual_type('{00000000-0000-0000-0000-000000000000}')

    def test_classify_type_guid(self):
        assert classify_type_guid('6f9dac99-8de1-4efc-8465-68ac443b7d08') == 'pou'
        assert classify_type_guid('ffbfa93a-b94d-45fc-a329-229860183b1d') == 'gvl'
        assert classify_type_guid('2db5b0c0-6a7b-4de7-b8c0-0c4bf1aee29c') == 'dut'
        assert classify_type_guid('6654496c-404d-479a-aad2-8551054e5f1e') == 'interface'
        assert classify_type_guid('{3183921b-cc91-4712-9781-c3b6555122b5}') == 'persistent'
        assert classify_type_guid('c2cda7a9-0ba4-4146-b563-22a42fa0eb72') == 'task_local'
        assert classify_type_guid('00000000-0000-0000-0000-000000000000') is None


# ══════════════════════════════════════════════════════════════════════
# SyncSettings
# ══════════════════════════════════════════════════════════════════════

class TestSyncSettings(object):
    def test_defaults(self):
        s = SyncSettings()
        assert s.sync_dir == './sync/'
        assert isinstance(s.filter, ObjectFilter)
        assert s.pipe_name == 'cds-st-sync-default'
        assert s.pipe_timeout == 30
        assert not s.live_sync_enabled
        assert s.poll_interval == 2
        assert s.conflict_strategy == 'last_write_wins'

    def test_custom_values(self):
        f = ObjectFilter(include_pou=False)
        s = SyncSettings(
            sync_dir='/tmp/x', filter_obj=f,
            pipe_name='mypipe', pipe_timeout=60,
            live_sync_enabled=True, poll_interval=5,
            conflict_strategy='last_write_wins',
        )
        assert s.sync_dir == '/tmp/x'
        assert not s.filter.include_pou
        assert s.pipe_name == 'mypipe'
        assert s.pipe_timeout == 60
        assert s.live_sync_enabled
        assert s.poll_interval == 5

    def test_to_dict_roundtrip(self):
        s = SyncSettings(
            sync_dir='/syncdir',
            filter_obj=ObjectFilter(include_gvl=False, include_dut=False),
            pipe_name='p', pipe_timeout=10,
            live_sync_enabled=True,
        )
        restored = SyncSettings.from_dict(s.to_dict())
        assert restored.sync_dir == '/syncdir'
        assert restored.filter.include_gvl is False
        assert restored.filter.include_dut is False
        assert restored.pipe_timeout == 10
        assert restored.live_sync_enabled is True


# ══════════════════════════════════════════════════════════════════════
# safe_filename helper
# ══════════════════════════════════════════════════════════════════════

class TestSafeFilename(object):
    def test_preserve_plain(self):
        assert safe_filename('PLC_PRG') == 'PLC_PRG'

    def test_replace_special(self):
        assert ':' not in safe_filename('fb:Menu')
        assert '*' not in safe_filename('test*name')

    def test_strip_dots_spaces(self):
        assert safe_filename('  name.  ') == 'name'

    def test_empty_becomes_object(self):
        assert safe_filename('') == 'object'
