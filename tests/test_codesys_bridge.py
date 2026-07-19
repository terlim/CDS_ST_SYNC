# -*- coding: utf-8 -*-
"""Tests for CodeSysObjectProxy and CodeSysBridge.

These tests use unittest.mock to simulate CodeSys native objects
and verify the proxy/bridge behaviour without a real IDE.
"""
from __future__ import print_function

import json
import os
import sys
import tempfile
import unittest

# Make src/ importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import MagicMock, PropertyMock, patch

from src.infrastructure.codesys_object import CodeSysObjectProxy, _safe_name
from src.infrastructure.codesys_bridge import CodeSysBridge
from src.domain.models import OperationResult, ProjectTree


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_mock_obj(guid, name, type_guid, decl=None, impl=None,
                   children=None, parent=None):
    """Build a MagicMock simulating a single CodeSys native object."""
    obj = MagicMock()
    obj.guid = guid
    obj.name = name
    obj.type_guid = type_guid
    obj.parent = parent

    if decl is not None:
        decl_mock = MagicMock()
        decl_mock.text = decl
        type(obj).textual_declaration = PropertyMock(return_value=decl_mock)
    else:
        type(obj).textual_declaration = PropertyMock(return_value=None)

    if impl is not None:
        impl_mock = MagicMock()
        impl_mock.text = impl
        type(obj).textual_implementation = PropertyMock(return_value=impl_mock)
    else:
        type(obj).textual_implementation = PropertyMock(return_value=None)

    if children is not None:
        obj.get_children.return_value = children
    else:
        obj.get_children.return_value = []

    return obj


# ── Tests: CodeSysObjectProxy ────────────────────────────────────────────

class TestCodeSysObjectProxy(unittest.TestCase):

    def test_guid(self):
        native = _make_mock_obj('{4140366f-02ec-4908-a7ac-d8d91000791f}',
                                'PLC_PRG', '6f9dac99')
        proxy = CodeSysObjectProxy(native)
        self.assertEqual(proxy.guid,
                         '4140366f-02ec-4908-a7ac-d8d91000791f')

    def test_name(self):
        native = _make_mock_obj('g1', 'MyPOU', 't1')
        proxy = CodeSysObjectProxy(native)
        self.assertEqual(proxy.name, 'MyPOU')

    def test_name_get_name_fallback(self):
        native = MagicMock()
        del native.name
        native.get_name.return_value = 'FallbackName'
        proxy = CodeSysObjectProxy(native)
        self.assertEqual(proxy.name, 'FallbackName')

    def test_name_str_fallback(self):
        native = MagicMock()
        del native.name
        native.get_name.side_effect = Exception('no get_name')
        native.__str__.return_value = 'StrName'
        proxy = CodeSysObjectProxy(native)
        self.assertEqual(proxy.name, 'StrName')

    def test_name_unnamed_fallback(self):
        native = MagicMock()
        del native.name
        native.get_name.side_effect = Exception('')
        native.__str__.side_effect = Exception('')
        proxy = CodeSysObjectProxy(native)
        self.assertEqual(proxy.name, 'unnamed')

    def test_parent_guid(self):
        parent = _make_mock_obj('parent-guid', 'Parent', 't')
        native = _make_mock_obj('child', 'Child', 't', parent=parent)
        proxy = CodeSysObjectProxy(native)
        self.assertEqual(proxy.parent_guid, 'parent-guid')

    def test_parent_guid_none(self):
        native = _make_mock_obj('child', 'Child', 't', parent=None)
        proxy = CodeSysObjectProxy(native)
        self.assertEqual(proxy.parent_guid, '')

    def test_type_guid(self):
        native = _make_mock_obj('g', 'n', '{6f9dac99-8de1-4efc-8465-68ac443b7d08}')
        proxy = CodeSysObjectProxy(native)
        self.assertEqual(proxy.type_guid,
                         '6f9dac99-8de1-4efc-8465-68ac443b7d08')

    def test_declaration_text(self):
        native = _make_mock_obj('g', 'n', 't',
                                decl='VAR\r\n  x : INT;\r\nEND_VAR\r\n')
        proxy = CodeSysObjectProxy(native)
        self.assertEqual(proxy.declaration_text, 'VAR\n  x : INT;\nEND_VAR')

    def test_declaration_text_none(self):
        native = _make_mock_obj('g', 'n', 't', decl=None)
        proxy = CodeSysObjectProxy(native)
        self.assertIsNone(proxy.declaration_text)

    def test_implementation_text(self):
        native = _make_mock_obj('g', 'n', 't',
                                impl='x := 1;\r\n')
        proxy = CodeSysObjectProxy(native)
        self.assertEqual(proxy.implementation_text, 'x := 1;')

    def test_implementation_text_none(self):
        native = _make_mock_obj('g', 'n', 't', impl=None)
        proxy = CodeSysObjectProxy(native)
        self.assertIsNone(proxy.implementation_text)

    def test_children(self):
        child1 = _make_mock_obj('c1', 'Child1', 't')
        child2 = _make_mock_obj('c2', 'Child2', 't')
        native = _make_mock_obj('g', 'Parent', 't',
                                children=[child1, child2])
        proxy = CodeSysObjectProxy(native)
        kids = proxy.children
        self.assertEqual(len(kids), 2)
        self.assertEqual(kids[0].guid, 'c1')
        self.assertEqual(kids[1].guid, 'c2')

    def test_children_empty(self):
        native = _make_mock_obj('g', 'n', 't', children=[])
        proxy = CodeSysObjectProxy(native)
        self.assertEqual(proxy.children, [])

    def test_children_exception(self):
        native = _make_mock_obj('g', 'n', 't')
        native.get_children.side_effect = RuntimeError('no access')
        proxy = CodeSysObjectProxy(native)
        self.assertEqual(proxy.children, [])

    def test_equality(self):
        n1 = _make_mock_obj('g1', 'A', 't')
        n2 = _make_mock_obj('g1', 'A', 't')
        n3 = _make_mock_obj('g2', 'B', 't')
        p1 = CodeSysObjectProxy(n1)
        p2 = CodeSysObjectProxy(n2)
        p3 = CodeSysObjectProxy(n3)
        self.assertEqual(p1, p2)
        self.assertNotEqual(p1, p3)

    def test_hash(self):
        n1 = _make_mock_obj('g1', 'A', 't')
        n2 = _make_mock_obj('g1', 'A', 't')
        self.assertEqual(hash(CodeSysObjectProxy(n1)),
                         hash(CodeSysObjectProxy(n2)))

    def test_repr(self):
        native = _make_mock_obj('my-guid', 'PLC_PRG', 't')
        proxy = CodeSysObjectProxy(native)
        r = repr(proxy)
        self.assertIn('PLC_PRG', r)
        self.assertIn('my-guid', r)


# ── Tests: CodeSysBridge ─────────────────────────────────────────────────

class TestCodeSysBridge(unittest.TestCase):

    def _make_project(self, objects=None):
        """Build a MagicMock project with get_children returning objects."""
        project = MagicMock()
        project.get_children.return_value = list(objects or [])
        return project

    def test_get_all_objects(self):
        n1 = _make_mock_obj('g1', 'PLC_PRG', '6f9dac99')
        n2 = _make_mock_obj('g2', 'GVL_COLOR', 'ffbfa93a')
        project = self._make_project([n1, n2])
        bridge = CodeSysBridge(project)
        objs = bridge.get_all_objects()
        self.assertEqual(len(objs), 2)
        self.assertEqual(objs[0].name, 'PLC_PRG')

    def test_get_all_objects_empty_project(self):
        bridge = CodeSysBridge(None)
        self.assertEqual(bridge.get_all_objects(), [])

    def test_get_object_by_guid(self):
        n1 = _make_mock_obj('aaa-bbb', 'MyPOU', '6f9dac99')
        n2 = _make_mock_obj('ccc-ddd', 'Other', 'ffbfa93a')
        project = self._make_project([n1, n2])
        bridge = CodeSysBridge(project)
        found = bridge.get_object_by_guid('aaa-bbb')
        self.assertIsNotNone(found)
        self.assertEqual(found.name, 'MyPOU')
        not_found = bridge.get_object_by_guid('zzz')
        self.assertIsNone(not_found)

    def test_get_object_by_guid_case_insensitive(self):
        n1 = _make_mock_obj('AAA-BBB', 'POU', 't')
        project = self._make_project([n1])
        bridge = CodeSysBridge(project)
        self.assertIsNotNone(bridge.get_object_by_guid('aaa-bbb'))

    def test_get_project_tree(self):
        n1 = _make_mock_obj('g1', 'Device', '738bea1e')
        n2 = _make_mock_obj('g2', 'PLC_PRG', '6f9dac99', parent=n1)
        project = self._make_project([n1, n2])
        bridge = CodeSysBridge(project)
        tree = bridge.get_project_tree()
        self.assertEqual(len(tree), 2)

    def test_update_text_success(self):
        native = _make_mock_obj('g1', 'PLC_PRG', '6f9dac99',
                                decl='VAR\nEND_VAR',
                                impl='// code')
        project = self._make_project([native])
        bridge = CodeSysBridge(project)

        result = bridge.update_text('g1', 'VAR\n  x:INT;\nEND_VAR', 'x:=1;')
        self.assertEqual(result.completed, 1)
        self.assertIn('Updated', result.messages[0])

    def test_update_text_not_found(self):
        project = self._make_project([])
        bridge = CodeSysBridge(project)
        result = bridge.update_text('no-such-guid', '', None)
        self.assertIn('not found', result.errors[0]['error'])

    def test_create_pou_program(self):
        container = _make_mock_obj('cont', 'Application', 't')
        container.create_pou.return_value = _make_mock_obj(
            'new-pou', 'MyProg', '6f9dac99', decl='PROGRAM MyProg\nVAR\nEND_VAR'
        )
        project = self._make_project([container])

        bridge = CodeSysBridge(project)
        with patch(
            'src.infrastructure.codesys_bridge._find_pou_type_enum'
        ) as mock_enum:
            mock_pt = MagicMock()
            mock_pt.Program = 'ProgramEnum'
            mock_pt.FunctionBlock = 'FBEnum'
            mock_pt.Function = 'FuncEnum'
            mock_enum.return_value = mock_pt

            result = bridge.create_pou('MyProg', 'program', 'cont',
                                       'PROGRAM MyProg\nVAR\nEND_VAR')
            self.assertEqual(result.name, 'MyProg')

    def test_create_folder(self):
        parent = _make_mock_obj('folder-guid', 'MyFolder', '738bea1e')
        parent.create_folder.return_value = _make_mock_obj(
            'sub-guid', 'SubFolder', '738bea1e'
        )
        project = self._make_project([parent])
        bridge = CodeSysBridge(project)

        result = bridge.create_folder('SubFolder', 'folder-guid')
        self.assertEqual(result.name, 'SubFolder')

    def test_create_folder_create_child_fallback(self):
        parent = _make_mock_obj('folder-guid', 'MyFolder', '738bea1e')
        del parent.create_folder
        parent.create_child.return_value = _make_mock_obj(
            'sub-guid', 'SubFolder', '738bea1e'
        )
        project = self._make_project([parent])
        bridge = CodeSysBridge(project)

        with patch(
            'src.infrastructure.codesys_bridge._to_system_guid',
            return_value='GuidObj'
        ):
            result = bridge.create_folder('SubFolder', 'folder-guid')
            self.assertEqual(result.name, 'SubFolder')

    def test_create_folder_not_found(self):
        project = self._make_project([])
        bridge = CodeSysBridge(project)
        with self.assertRaises(ValueError):
            bridge.create_folder('X', 'no-such-guid')

    def test_get_timestamps(self):
        """Simulate get_timestamps by mocking export_native + XML output."""
        n1 = _make_mock_obj('g1', 'A', 't')
        n2 = _make_mock_obj('g2', 'B', 't')
        project = self._make_project([n1, n2])

        xml_content = (
            '<?xml version="1.0"?>'
            '<ExportFile>'
            '<StructuredView Guid="{sv}">'
            '<Single xml:space="preserve">'
            '<Null Name="Profile"/>'
            '<List2 Name="EntryList">'
            '<Single Type="{entry}" Method="IArchivable">'
            '<Single Name="MetaObject">'
            '<Single Name="Guid" Type="System.Guid">g1</Single>'
            '<Single Name="Timestamp" Type="long">100</Single>'
            '</Single>'
            '</Single>'
            '<Single Type="{entry}" Method="IArchivable">'
            '<Single Name="MetaObject">'
            '<Single Name="Guid" Type="System.Guid">g2</Single>'
            '<Single Name="Timestamp" Type="long">200</Single>'
            '</Single>'
            '</Single>'
            '</List2>'
            '</Single>'
            '</StructuredView>'
            '</ExportFile>'
        )

        # We need to write actual file for ET.parse to work
        def export_side_effect(objects, path, recursive):
            with open(path, 'w') as f:
                f.write(xml_content)

        project.export_native.side_effect = export_side_effect

        bridge = CodeSysBridge(project)
        stamps = bridge.get_timestamps()
        self.assertEqual(stamps.get('g1'), 100)
        self.assertEqual(stamps.get('g2'), 200)

    def test_get_timestamps_empty_project(self):
        bridge = CodeSysBridge(None)
        self.assertEqual(bridge.get_timestamps(), {})


if __name__ == '__main__':
    unittest.main()
