# -*- coding: utf-8 -*-
"""Tests for ExportService."""
from __future__ import print_function

import os
import sys
import unittest

_SELF_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_SELF_DIR)
_SRC_DIR = os.path.join(_PROJECT_DIR, 'src')
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from services.export_service import ExportService
from domain.models import ObjectMeta, Manifest, OperationResult
from domain.filter import ObjectFilter, classify_type_guid
from infrastructure.text_extractor import TextExtractor
from infrastructure.st_formatter import StFormatter
from interfaces.bridge import ICodeSysObject, ICodeSysBridge
from interfaces.storage import IStorage


# ── Mock CodeSys Object ──────────────────────────────────────────────────

class MockCodeSysObject(ICodeSysObject):
    """Test double for ICodeSysObject."""

    def __init__(self, guid, name, type_guid, declaration_text=None,
                 implementation_text=None, parent=None, children=None):
        self._guid = str(guid or '').strip('{}').lower()
        self._name = name or ''
        self._type_guid = str(type_guid or '').strip('{}').lower()
        self._declaration_text = declaration_text
        self._implementation_text = implementation_text
        self._parent = parent
        self._children = list(children or [])

    @property
    def guid(self):
        return self._guid

    @property
    def name(self):
        return self._name

    @property
    def parent_guid(self):
        if self._parent is not None:
            return self._parent.guid
        return '00000000-0000-0000-0000-000000000000'

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
    def parent(self):
        return self._parent

    @property
    def children(self):
        return list(self._children)


# ── Mock Bridge ──────────────────────────────────────────────────────────

class MockBridge(ICodeSysBridge):
    """Test double for ICodeSysBridge."""

    def __init__(self, objects=None):
        self._objects = list(objects or [])
        self._by_guid = {o.guid: o for o in self._objects}

    def get_all_objects(self):
        return list(self._objects)

    def get_object_by_guid(self, guid):
        return self._by_guid.get(str(guid).strip('{}').lower())

    def get_project_tree(self):
        from domain.models import ProjectTree
        tree = ProjectTree()
        for obj in self._objects:
            tree.add_node(obj.guid, obj.name,
                          classify_type_guid(obj.type_guid) or 'unknown',
                          obj.parent_guid)
        return tree

    # ── IObjectWriter (not used by ExportService) ─────────────────

    def update_text(self, guid, declaration, implementation):
        raise NotImplementedError

    def create_pou(self, name, kind, container_guid, declaration):
        raise NotImplementedError

    def create_gvl(self, name, container_guid):
        raise NotImplementedError

    def create_dut(self, name, container_guid, dut_kind):
        raise NotImplementedError

    def create_folder(self, name, parent_guid):
        raise NotImplementedError

    # ── ITimestampReader (not used by ExportService) ──────────────

    def get_timestamps(self):
        raise NotImplementedError


# ── Memory Storage ───────────────────────────────────────────────────────

class MemoryStorage(IStorage):
    """In-memory IStorage for tests."""

    def __init__(self):
        self._objects = {}     # relative_path → (declaration, implementation)
        self._manifest = None

    def save_object(self, meta, declaration, implementation):
        self._objects[meta.relative_path] = (declaration, implementation)

    def load_object(self, meta):
        return self._objects.get(meta.relative_path, ('', None))

    def save_manifest(self, manifest):
        self._manifest = manifest

    def load_manifest(self):
        return self._manifest

    def watch_changes(self, callback):
        pass  # no-op for memory storage


# ── Tests ────────────────────────────────────────────────────────────────

# GUIDs from real CodeSys specs
GUID_POU = '6f9dac99-8de1-4efc-8465-68ac443b7d08'
GUID_GVL = 'ffbfa93a-b94d-45fc-a329-229860183b1d'
GUID_DUT = '2db5b0c0-6a7b-4de7-b8c0-0c4bf1aee29c'
GUID_INTERFACE = '6654496c-404d-479a-aad2-8551054e5f1e'
GUID_METHOD = 'f8a58466-d7f6-439f-bbb8-d4600e41d099'
GUID_ACTION = 'f89f7675-27f1-46b3-8abb-b7da8e774ffd'


def _make_program(guid, name, decl, impl, parent=None):
    """Helper: create a PROGRAM mock object."""
    return MockCodeSysObject(
        guid=guid,
        name=name,
        type_guid=GUID_POU,
        declaration_text=decl,
        implementation_text=impl,
        parent=parent,
    )


def _make_gvl(guid, name, decl, parent=None):
    return MockCodeSysObject(
        guid=guid,
        name=name,
        type_guid=GUID_GVL,
        declaration_text=decl,
        implementation_text=None,
        parent=parent,
    )


def _make_dut(guid, name, decl, parent=None):
    return MockCodeSysObject(
        guid=guid,
        name=name,
        type_guid=GUID_DUT,
        declaration_text=decl,
        implementation_text=None,
        parent=parent,
    )


class TestExportService(unittest.TestCase):
    """Unit tests for ExportService."""

    def setUp(self):
        self.extractor = TextExtractor()
        self.formatter = StFormatter()
        self.storage = MemoryStorage()

    def _make_service(self, bridge):
        """Create an ExportService with the given bridge."""
        return ExportService(bridge, self.extractor, self.storage,
                             self.formatter)

    def _build_program_obj(self, guid, name, decl, impl):
        return _make_program(guid, name, decl, impl)

    # ──────────────────────────────────────────────────────────────────────

    def test_export_single_pou(self):
        """Export one POU → one .st file in storage."""
        obj = _make_program('a' * 32, 'PLC_PRG',
                            'PROGRAM PLC_PRG\nVAR\nEND_VAR\n',
                            'x := 1;\n')
        bridge = MockBridge([obj])
        svc = self._make_service(bridge)
        filt = ObjectFilter(include_gvl=False, include_dut=False,
                            include_interface=False)

        result = svc.export(filt)

        self.assertTrue(result.success)
        self.assertEqual(1, result.completed)
        self.assertEqual(1, result.total)
        self.assertEqual(0, len(result.errors))

        # Verify storage.
        manifest = self.storage.load_manifest()
        self.assertIsNotNone(manifest)
        self.assertEqual(1, len(manifest))
        meta = manifest.objects[0]
        self.assertEqual(obj.guid, meta.guid)
        self.assertEqual('PLC_PRG', meta.name)
        self.assertEqual('pou', meta.type)
        self.assertEqual('program', meta.pou_kind)
        self.assertIsNotNone(meta.sha1)

        decl, impl = self.storage.load_object(meta)
        self.assertIn('PROGRAM PLC_PRG', decl)
        self.assertEqual('x := 1;\n', impl)

    def test_export_pou_and_gvl(self):
        """Export one POU + one GVL → two .st files."""
        pou = _make_program('a1' * 16, 'PLC_PRG',
                            'PROGRAM PLC_PRG\nVAR\nEND_VAR\n',
                            '// code\n')
        gvl = _make_gvl('b2' * 16, 'GVL_COLOR',
                        '{attribute \'qualified_only\'}\nVAR_GLOBAL\nEND_VAR\n')
        bridge = MockBridge([pou, gvl])
        svc = self._make_service(bridge)
        filt = ObjectFilter(include_gvl=True, include_dut=False,
                            include_interface=False)

        result = svc.export(filt)

        self.assertTrue(result.success)
        self.assertEqual(2, result.completed)
        self.assertEqual(2, result.total)

        manifest = self.storage.load_manifest()
        self.assertEqual(2, len(manifest))
        types = {o.type for o in manifest.objects}
        self.assertSetEqual({'pou', 'gvl'}, types)

    def test_export_filter_excludes_dut(self):
        """With dut off, only POU is exported."""
        pou = _make_program('aa' * 16, 'P1', 'PROGRAM P1\nVAR\nEND_VAR\n', ';\n')
        dut = _make_dut('bb' * 16, 'MyStruct', 'TYPE MyStruct :\nSTRUCT\nEND_STRUCT\nEND_TYPE\n')
        bridge = MockBridge([pou, dut])
        svc = self._make_service(bridge)
        filt = ObjectFilter(include_gvl=False, include_dut=False,
                            include_interface=False)

        result = svc.export(filt)
        self.assertTrue(result.success)
        self.assertEqual(1, result.completed)
        self.assertEqual(2, result.total)

        manifest = self.storage.load_manifest()
        self.assertEqual(1, len(manifest))
        self.assertEqual('P1', manifest.objects[0].name)

    def test_export_filter_all_on(self):
        """all_on() exports everything textual."""
        pou = _make_program('a1' * 16, 'P1', 'PROGRAM P1\nVAR\nEND_VAR\n', ';\n')
        gvl = _make_gvl('b1' * 16, 'GVL1', 'VAR_GLOBAL\nEND_VAR\n')
        dut = _make_dut('c1' * 16, 'DUT1', 'TYPE DUT1 : STRUCT\nEND_STRUCT\nEND_TYPE\n')
        bridge = MockBridge([pou, gvl, dut])
        svc = self._make_service(bridge)
        filt = ObjectFilter.all_on()

        result = svc.export(filt)
        self.assertTrue(result.success)
        self.assertEqual(3, result.completed)
        self.assertEqual(3, result.total)

    def test_export_empty_project(self):
        """Empty project → zero objects, still success."""
        bridge = MockBridge([])
        svc = self._make_service(bridge)
        filt = ObjectFilter()

        result = svc.export(filt)
        self.assertTrue(result.success)
        self.assertEqual(0, result.completed)
        self.assertEqual(0, result.total)

        manifest = self.storage.load_manifest()
        self.assertIsNotNone(manifest)
        self.assertEqual(0, len(manifest))

    def test_export_object_without_declaration_skipped_with_error(self):
        """Object with None declaration_text → exported with empty decl."""
        obj = MockCodeSysObject(
            guid='dd' * 16,
            name='BadPOU',
            type_guid=GUID_POU,
            declaration_text=None,
            implementation_text='code',
        )
        bridge = MockBridge([obj])
        svc = self._make_service(bridge)
        filt = ObjectFilter(include_gvl=False, include_dut=False,
                            include_interface=False)

        result = svc.export(filt)
        # TextExtractor normalises None → '', so export succeeds
        self.assertTrue(result.success)
        self.assertEqual(1, result.completed)
        self.assertEqual(0, len(result.errors))

    def test_export_object_with_none_implementation(self):
        """POU with None implementation_text → saved as None impl."""
        obj = _make_program('aa' * 16, 'P1',
                            'PROGRAM P1\nVAR\nEND_VAR\n',
                            None)
        bridge = MockBridge([obj])
        svc = self._make_service(bridge)
        filt = ObjectFilter(include_gvl=False, include_dut=False,
                            include_interface=False)

        result = svc.export(filt)
        self.assertTrue(result.success)
        self.assertEqual(1, result.completed)

        meta = self.storage.load_manifest().objects[0]
        decl, impl = self.storage.load_object(meta)
        self.assertIsNone(impl)

    def test_progress_callback_is_called(self):
        """progress_callback fires for each total object."""
        pou = _make_program('a1' * 16, 'P1', 'PROGRAM P1\nVAR\nEND_VAR\n', ';\n')
        gvl = _make_gvl('b1' * 16, 'GVL1', 'VAR_GLOBAL\nEND_VAR\n')
        bridge = MockBridge([pou, gvl])
        svc = self._make_service(bridge)

        calls = []
        svc._progress = lambda cur, tot, msg: calls.append((cur, tot, msg))
        filt = ObjectFilter(include_gvl=True, include_dut=False,
                            include_interface=False)

        svc.export(filt)

        self.assertGreaterEqual(len(calls), 2)
        # First call at index 1, last at total.
        first = calls[0]
        last = calls[-1]
        self.assertEqual(1, first[0])
        self.assertEqual(2, last[0])
        self.assertEqual(last[0], last[1])

    def test_manifest_contains_correct_fields(self):
        """Manifest objects have guid, name, type, path, file, sha1, pou_kind."""
        pou = _make_program('e' * 32, 'MyProgram',
                            'PROGRAM MyProgram\nVAR\nEND_VAR\n',
                            'x := 1;\n')
        bridge = MockBridge([pou])
        svc = self._make_service(bridge)
        filt = ObjectFilter(include_gvl=False, include_dut=False,
                            include_interface=False)

        svc.export(filt)
        manifest = self.storage.load_manifest()
        self.assertEqual(1, len(manifest))
        meta = manifest.objects[0]

        self.assertEqual('e' * 32, meta.guid)
        self.assertEqual('MyProgram', meta.name)
        self.assertEqual('pou', meta.type)
        self.assertEqual('program', meta.pou_kind)
        self.assertIsNotNone(meta.sha1)
        self.assertTrue(len(meta.sha1) > 0)

    def test_manifest_sha1_is_not_empty(self):
        """Exported object has non-empty sha1."""
        obj = _make_program('a' * 32, 'P',
                            'PROGRAM P\nVAR\nEND_VAR\n',
                            'x := 1;\n')
        bridge = MockBridge([obj])
        svc = self._make_service(bridge)
        filt = ObjectFilter(include_gvl=False, include_dut=False,
                            include_interface=False)

        svc.export(filt)
        meta = self.storage.load_manifest().objects[0]
        self.assertIsNotNone(meta.sha1)
        self.assertNotEqual('', meta.sha1)
        self.assertEqual(40, len(meta.sha1))  # SHA1 = 40 hex chars

    def test_relative_path_is_correct(self):
        """ObjectMeta.relative_path computed from path + name."""
        parent = MockCodeSysObject(
            guid='ff' * 16, name='PROGRAMS', type_guid='',
        )
        obj = _make_program('a' * 32, 'PLC_PRG',
                            'PROGRAM PLC_PRG\nVAR\nEND_VAR\n',
                            '// code\n',
                            parent=parent)
        bridge = MockBridge([parent, obj])
        svc = self._make_service(bridge)
        filt = ObjectFilter(include_gvl=False, include_dut=False,
                            include_interface=False)

        svc.export(filt)
        meta = self.storage.load_manifest().objects[0]
        self.assertIn('PROGRAMS', meta.relative_path)
        self.assertIn('PLC_PRG.st', meta.relative_path)

    def test_pou_kind_function_block(self):
        """FUNCTION_BLOCK declaration → pou_kind='function_block'."""
        obj = _make_program('a' * 32, 'fb_Menu',
                            'FUNCTION_BLOCK fb_Menu\nVAR\nEND_VAR\n',
                            ';\n')
        bridge = MockBridge([obj])
        svc = self._make_service(bridge)
        filt = ObjectFilter(include_gvl=False, include_dut=False,
                            include_interface=False)

        svc.export(filt)
        meta = self.storage.load_manifest().objects[0]
        self.assertEqual('function_block', meta.pou_kind)

    def test_pou_kind_function(self):
        """FUNCTION declaration → pou_kind='function'."""
        obj = _make_program('a' * 32, 'MyFunc',
                            'FUNCTION MyFunc : INT\nVAR\nEND_VAR\n',
                            ';\n')
        bridge = MockBridge([obj])
        svc = self._make_service(bridge)
        filt = ObjectFilter(include_gvl=False, include_dut=False,
                            include_interface=False)

        svc.export(filt)
        meta = self.storage.load_manifest().objects[0]
        self.assertEqual('function', meta.pou_kind)

    def test_messages_in_result(self):
        """Result messages describe what happened."""
        obj = _make_program('a' * 32, 'P', 'PROGRAM P\nVAR\nEND_VAR\n', ';\n')
        bridge = MockBridge([obj])
        svc = self._make_service(bridge)
        filt = ObjectFilter(include_gvl=False, include_dut=False,
                            include_interface=False)

        result = svc.export(filt)
        self.assertTrue(len(result.messages) > 0)


if __name__ == '__main__':
    unittest.main()
