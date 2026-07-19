# -*- coding: utf-8 -*-
"""Tests for ImportService."""
from __future__ import print_function

import os
import sys
import unittest

_SELF_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_SELF_DIR)
_SRC_DIR = os.path.join(_PROJECT_DIR, 'src')
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from services.import_service import ImportService
from domain.models import ObjectMeta, Manifest, OperationResult
from domain.filter import ObjectFilter
from infrastructure.st_formatter import StFormatter
from interfaces.bridge import ICodeSysObject, ICodeSysBridge
from interfaces.storage import IStorage

# ── GUID constants ──────────────────────────────────────────────────────

GUID_POU = '6f9dac99-8de1-4efc-8465-68ac443b7d08'
GUID_GVL = 'ffbfa93a-b94d-45fc-a329-229860183b1d'
GUID_DUT = '2db5b0c0-6a7b-4de7-b8c0-0c4bf1aee29c'
GUID_ITF = '6654496c-404d-479a-aad2-8551054e5f1e'
GUID_FOLDER = '738bea1e-99bb-4f04-90bb-a7a567e74e3a'
GUID_PERSIST = '3183921b-cc91-4712-9781-c3b6555122b5'


# ── Helpers ─────────────────────────────────────────────────────────────

def _make_program(guid, name, decl, impl):
    """Create a MockCodeSysObject for a PROGRAM."""
    return MockCodeSysObject(
        guid=guid, name=name, type_guid=GUID_POU,
        declaration_text=decl, implementation_text=impl,
    )


def _make_gvl(guid, name, decl):
    """Create a MockCodeSysObject for a GVL."""
    return MockCodeSysObject(
        guid=guid, name=name, type_guid=GUID_GVL,
        declaration_text=decl, implementation_text=None,
    )


def _make_dut(guid, name, decl):
    """Create a MockCodeSysObject for a DUT."""
    return MockCodeSysObject(
        guid=guid, name=name, type_guid=GUID_DUT,
        declaration_text=decl, implementation_text=None,
    )


def _make_folder(guid, name):
    """Create a MockCodeSysObject for a folder."""
    return MockCodeSysObject(
        guid=guid, name=name, type_guid=GUID_FOLDER,
        declaration_text=None, implementation_text=None,
    )


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

    def __repr__(self):
        return 'MockCodeSysObject({!r}, {!r})'.format(self._guid, self._name)


# ── Mock Bridge ──────────────────────────────────────────────────────────

class MockBridge(ICodeSysBridge):
    """Test double for ICodeSysBridge."""

    def __init__(self, objects=None):
        self._objects = list(objects or [])
        self._by_guid = {o.guid: o for o in self._objects}
        self._text_updates = []       # list of (guid, decl, impl)
        self._created_folders = []    # list of (name, parent_guid)
        self._created_pous = []       # list of (name, kind, container, decl)
        self._created_gvls = []       # list of (name, container)
        self._created_duts = []       # list of (name, container, kind)
        self._update_errors = {}      # guid → Exception
        self._next_folder_guid = 1000

    # ── IObjectReader ──────────────────────────────────────────────────

    def get_all_objects(self):
        return list(self._objects)

    def get_object_by_guid(self, guid):
        key = str(guid or '').strip('{}').lower()
        return self._by_guid.get(key)

    def get_project_tree(self):
        from domain.models import ProjectTree
        tree = ProjectTree()
        for obj in self._objects:
            tree.add_node(obj.guid, obj.name, 'object', obj.parent_guid)
        return tree

    # ── IObjectWriter ──────────────────────────────────────────────────

    def update_text(self, guid, declaration, implementation):
        key = str(guid or '').strip('{}').lower()
        if key in self._update_errors:
            raise self._update_errors[key]
        self._text_updates.append((key, declaration, implementation))
        obj = self._by_guid.get(key)
        if obj is not None:
            # Reflect the update for subsequent get_object_by_guid.
            obj._declaration_text = declaration
            obj._implementation_text = implementation
        return OperationResult(success=True)

    def create_pou(self, name, kind, container_guid, declaration):
        self._created_pous.append((name, kind, container_guid, declaration))
        g = str(self._next_folder_guid)
        self._next_folder_guid += 1
        obj = _make_program(g, name, declaration, '')
        obj._parent = self._by_guid.get(container_guid)
        self._objects.append(obj)
        self._by_guid[g] = obj
        return obj

    def create_gvl(self, name, container_guid):
        self._created_gvls.append((name, container_guid))
        g = str(self._next_folder_guid)
        self._next_folder_guid += 1
        obj = _make_gvl(g, name, 'VAR_GLOBAL\nEND_VAR\n')
        obj._parent = self._by_guid.get(container_guid)
        self._objects.append(obj)
        self._by_guid[g] = obj
        return obj

    def create_dut(self, name, container_guid, dut_kind):
        self._created_duts.append((name, container_guid, dut_kind))
        g = str(self._next_folder_guid)
        self._next_folder_guid += 1
        obj = _make_dut(g, name, 'TYPE {0} :\nSTRUCT\nEND_STRUCT\nEND_TYPE\n'.format(name))
        obj._parent = self._by_guid.get(container_guid)
        self._objects.append(obj)
        self._by_guid[g] = obj
        return obj

    def create_folder(self, name, parent_guid):
        self._created_folders.append((name, parent_guid))
        g = str(self._next_folder_guid)
        self._next_folder_guid += 1
        obj = _make_folder(g, name)
        obj._parent = self._by_guid.get(parent_guid)
        self._objects.append(obj)
        self._by_guid[g] = obj
        return obj

    # ── ITimestampReader ───────────────────────────────────────────────

    def get_timestamps(self):
        return {}


# ── Memory Storage ──────────────────────────────────────────────────────

class MemoryStorage(IStorage):
    """In-memory IStorage for testing."""

    def __init__(self, objects_dict=None, manifest=None):
        """*objects_dict*: {guid: (declaration, implementation)}."""
        self._objects = dict(objects_dict or {})
        self._manifest = manifest or Manifest()

    def save_object(self, meta, declaration, implementation):
        self._objects[meta.guid] = (declaration, implementation)

    def load_object(self, meta):
        return self._objects.get(meta.guid, ('', None))

    def save_manifest(self, manifest):
        self._manifest = manifest

    def load_manifest(self):
        return self._manifest

    def watch_changes(self, callback):
        pass  # no-op for memory storage


# ── Test Cases ──────────────────────────────────────────────────────────

class ImportServiceTest(unittest.TestCase):

    def setUp(self):
        self.formatter = StFormatter()
        self.storage = MemoryStorage()

    def _make_service(self, bridge):
        return ImportService(bridge, self.storage, self.formatter)

    # ── basic import ──────────────────────────────────────────────────

    def test_import_existing_pou_updated(self):
        """Import an existing POU → update_text called, updated=1."""
        obj = _make_program('aa' * 16, 'PLC_PRG',
                            'PROGRAM PLC_PRG\nVAR\nEND_VAR\n',
                            'x := 2;\n')
        bridge = MockBridge([obj])

        meta = ObjectMeta(guid='aa' * 16, name='PLC_PRG',
                          path=[], obj_type='pou', pou_kind='program')
        self.storage.save_object(meta, 'PROGRAM PLC_PRG\nVAR\nEND_VAR\n',
                                'x := 2;\n')
        manifest = Manifest(project_name='Test')
        manifest.add_object(meta)
        self.storage.save_manifest(manifest)

        svc = self._make_service(bridge)
        result = svc.import_(ObjectFilter())

        self.assertTrue(result.success)
        self.assertEqual(1, result.completed)
        self.assertEqual(1, len(bridge._text_updates))
        self.assertIn('Updated: 1', result.messages[0])

    def test_import_new_pou_created(self):
        """Import a non-existing POU → create_pou called, created=1."""
        bridge = MockBridge([])

        meta = ObjectMeta(guid='bb' * 16, name='NewPOU',
                          path=[], obj_type='pou', pou_kind='program')
        decl = 'PROGRAM NewPOU\nVAR\nEND_VAR\n'
        impl = ';\n'
        self.storage.save_object(meta, decl, impl)
        manifest = Manifest(project_name='Test')
        manifest.add_object(meta)
        self.storage.save_manifest(manifest)

        svc = self._make_service(bridge)
        result = svc.import_(ObjectFilter())

        self.assertTrue(result.success)
        self.assertEqual(1, result.completed)
        self.assertEqual(1, len(bridge._created_pous))
        self.assertIn('Created: 1', result.messages[0])

    def test_import_existing_gvl_updated(self):
        """Import an existing GVL → update_text called."""
        obj = _make_gvl('cc' * 16, 'GVL_Colors',
                        'VAR_GLOBAL\n\tcRed : INT;\nEND_VAR\n')
        bridge = MockBridge([obj])

        meta = ObjectMeta(guid='cc' * 16, name='GVL_Colors',
                          path=[], obj_type='gvl')
        self.storage.save_object(meta,
                                'VAR_GLOBAL\n\tcRed : INT;\nEND_VAR\n',
                                None)
        manifest = Manifest(project_name='Test')
        manifest.add_object(meta)
        self.storage.save_manifest(manifest)

        svc = self._make_service(bridge)
        result = svc.import_(ObjectFilter())

        self.assertTrue(result.success)
        self.assertEqual(1, result.completed)
        self.assertEqual(1, len(bridge._text_updates))

    def test_import_new_gvl_created(self):
        """Import a new GVL → create_gvl called."""
        bridge = MockBridge([])

        meta = ObjectMeta(guid='dd' * 16, name='GVL_New',
                          path=[], obj_type='gvl')
        self.storage.save_object(meta,
                                'VAR_GLOBAL\nEND_VAR\n',
                                None)
        manifest = Manifest(project_name='Test')
        manifest.add_object(meta)
        self.storage.save_manifest(manifest)

        svc = self._make_service(bridge)
        result = svc.import_(ObjectFilter())

        self.assertTrue(result.success)
        self.assertEqual(1, result.completed)
        self.assertEqual(1, len(bridge._created_gvls))

    def test_import_new_dut_created(self):
        """Import a new DUT → create_dut called."""
        bridge = MockBridge([])

        meta = ObjectMeta(guid='ee' * 16, name='MyStruct',
                          path=[], obj_type='dut')
        decl = 'TYPE MyStruct :\nSTRUCT\n\tx : INT;\nEND_STRUCT\nEND_TYPE\n'
        self.storage.save_object(meta, decl, None)
        manifest = Manifest(project_name='Test')
        manifest.add_object(meta)
        self.storage.save_manifest(manifest)

        svc = self._make_service(bridge)
        result = svc.import_(ObjectFilter())

        self.assertTrue(result.success)
        self.assertEqual(1, result.completed)
        self.assertEqual(1, len(bridge._created_duts))

    # ── folder creation ────────────────────────────────────────────────

    def test_import_with_missing_folder_creates_it(self):
        """Import a POU whose parent folder does not exist → folder created."""
        bridge = MockBridge([])

        meta = ObjectMeta(guid='ff' * 16, name='MyPOU',
                          path=['Device', 'Plc Logic', 'Application'],
                          obj_type='pou', pou_kind='program')
        decl = 'PROGRAM MyPOU\nVAR\nEND_VAR\n'
        impl = ';\n'
        self.storage.save_object(meta, decl, impl)
        manifest = Manifest(project_name='Test')
        manifest.add_object(meta)
        self.storage.save_manifest(manifest)

        svc = self._make_service(bridge)
        result = svc.import_(ObjectFilter())

        self.assertTrue(result.success)
        self.assertEqual(1, result.completed)
        # Three folders should have been created.
        self.assertEqual(3, len(bridge._created_folders))
        self.assertEqual(
            [('Device', 1), ('Plc Logic', 2), ('Application', 3)],
            [(name, len(str(parent_guid))) for name, parent_guid in bridge._created_folders]
        )

    def test_import_with_existing_folders_does_not_duplicate(self):
        """Import with pre-existing folder hierarchy → no duplicate folders."""
        # Pre-populate the bridge with Device and Plc Logic folders.
        root = MockCodeSysObject(
            '00000000-0000-0000-0000-000000000000', '', GUID_FOLDER,
        )
        dev = _make_folder('dev', 'Device')
        dev._parent = root
        plc = _make_folder('plc', 'Plc Logic')
        plc._parent = dev
        app = _make_folder('app', 'Application')
        app._parent = plc

        bridge = MockBridge([root, dev, plc, app])

        meta = ObjectMeta(guid='99' * 16, name='MyPOU',
                          path=['Device', 'Plc Logic', 'Application'],
                          obj_type='pou', pou_kind='program')
        decl = 'PROGRAM MyPOU\nVAR\nEND_VAR\n'
        impl = ';\n'
        self.storage.save_object(meta, decl, impl)
        manifest = Manifest(project_name='Test')
        manifest.add_object(meta)
        self.storage.save_manifest(manifest)

        svc = self._make_service(bridge)
        result = svc.import_(ObjectFilter())

        self.assertTrue(result.success)
        self.assertEqual(1, result.completed)
        # No new folders created – all already exist.
        self.assertEqual(0, len(bridge._created_folders))
        # The POU was created (not updated – it didn't exist).
        self.assertEqual(1, len(bridge._created_pous))

    # ── filter ─────────────────────────────────────────────────────────

    def test_import_with_filter_only_pou(self):
        """Filter: only POU from manifest containing POU+GVL."""
        pou_obj = _make_program('a1' * 16, 'P1',
                                'PROGRAM P1\nVAR\nEND_VAR\n', ';\n')
        gvl_obj = _make_gvl('b1' * 16, 'G1', 'VAR_GLOBAL\nEND_VAR\n')
        bridge = MockBridge([pou_obj, gvl_obj])

        pou_meta = ObjectMeta(guid='a1' * 16, name='P1',
                              path=[], obj_type='pou', pou_kind='program')
        gvl_meta = ObjectMeta(guid='b1' * 16, name='G1',
                              path=[], obj_type='gvl')
        self.storage.save_object(pou_meta, 'PROGRAM P1\nVAR\nEND_VAR\n', ';\n')
        self.storage.save_object(gvl_meta, 'VAR_GLOBAL\nEND_VAR\n', None)
        manifest = Manifest(project_name='Test')
        manifest.add_object(pou_meta)
        manifest.add_object(gvl_meta)
        self.storage.save_manifest(manifest)

        svc = self._make_service(bridge)
        filt = ObjectFilter(include_gvl=False, include_dut=False,
                            include_interface=False)
        result = svc.import_(filt)

        self.assertTrue(result.success)
        self.assertEqual(1, result.completed)
        # Only one text update (the POU); GVL was skipped.
        self.assertEqual(1, len(bridge._text_updates))

    # ── empty manifest ─────────────────────────────────────────────────

    def test_import_empty_manifest(self):
        """Empty manifest → zero objects, still success."""
        bridge = MockBridge([])
        self.storage.save_manifest(Manifest(project_name='Test'))

        svc = self._make_service(bridge)
        result = svc.import_(ObjectFilter())

        self.assertTrue(result.success)
        self.assertEqual(0, result.completed)
        self.assertEqual(0, result.total)

    # ── errors ─────────────────────────────────────────────────────────

    def test_import_with_update_error_recorded(self):
        """Error during update_text → error recorded, other objects proceed."""
        good_obj = _make_program('g1' * 16, 'Good',
                                 'PROGRAM Good\nVAR\nEND_VAR\n', ';\n')
        bad_obj = _make_program('b1' * 16, 'Bad',
                                'PROGRAM Bad\nVAR\nEND_VAR\n', ';\n')
        bridge = MockBridge([good_obj, bad_obj])
        bridge._update_errors['b1' * 16] = RuntimeError('simulated')

        for g, n, d, i in [
            ('g1', 'Good', 'PROGRAM Good\nVAR\nEND_VAR\n', ';\n'),
            ('b1', 'Bad', 'PROGRAM Bad\nVAR\nEND_VAR\n', ';\n'),
        ]:
            meta = ObjectMeta(guid=g * 16, name=n,
                              path=[], obj_type='pou', pou_kind='program')
            self.storage.save_object(meta, d, i)

        manifest = Manifest(project_name='Test')
        manifest.add_object(ObjectMeta(guid='g1' * 16, name='Good',
                                       path=[], obj_type='pou', pou_kind='program'))
        manifest.add_object(ObjectMeta(guid='b1' * 16, name='Bad',
                                       path=[], obj_type='pou', pou_kind='program'))
        self.storage.save_manifest(manifest)

        svc = self._make_service(bridge)
        result = svc.import_(ObjectFilter())

        # One object failed.
        self.assertFalse(result.success)
        self.assertEqual(1, result.completed)
        self.assertEqual(1, len(result.errors))
        self.assertEqual('b1' * 16, result.errors[0]['guid'])

    # ── progress callback ──────────────────────────────────────────────

    def test_progress_callback_is_called(self):
        """progress_callback fires for each object in the manifest."""
        for g, n, d, i in [
            ('p1', 'P1', 'PROGRAM P1\nVAR\nEND_VAR\n', ';\n'),
            ('g1', 'G1', 'VAR_GLOBAL\nEND_VAR\n', None),
        ]:
            meta = ObjectMeta(guid=g * 16, name=n,
                              path=[], obj_type='pou' if n == 'P1' else 'gvl',
                              pou_kind='program' if n == 'P1' else None)
            self.storage.save_object(meta, d, i)

        manifest = Manifest(project_name='Test')
        manifest.add_object(ObjectMeta(guid='p1' * 16, name='P1',
                                       path=[], obj_type='pou', pou_kind='program'))
        manifest.add_object(ObjectMeta(guid='g1' * 16, name='G1',
                                       path=[], obj_type='gvl'))
        self.storage.save_manifest(manifest)

        pou_obj = _make_program('p1' * 16, 'P1',
                                'PROGRAM P1\nVAR\nEND_VAR\n', 'old')
        gvl_obj = _make_gvl('g1' * 16, 'G1', 'old')
        bridge = MockBridge([pou_obj, gvl_obj])

        calls = []
        svc = ImportService(bridge, self.storage, self.formatter,
                            progress_callback=lambda cur, tot, msg: calls.append((cur, tot, msg)))
        filt = ObjectFilter()
        svc.import_(filt)

        self.assertGreaterEqual(len(calls), 2)
        first = calls[0]
        last = calls[-1]
        self.assertEqual(1, first[0])
        self.assertEqual(2, last[0])
        self.assertEqual(last[0], last[1])

    # ── messages ───────────────────────────────────────────────────────

    def test_result_messages_contain_updated_created(self):
        """OperationResult.messages includes 'Updated'/'Created' summary."""
        exist_obj = _make_program('e1' * 16, 'Existing',
                                  'PROGRAM Existing\nVAR\nEND_VAR\n', 'old')
        bridge = MockBridge([exist_obj])

        exist_meta = ObjectMeta(guid='e1' * 16, name='Existing',
                                path=[], obj_type='pou', pou_kind='program')
        new_meta = ObjectMeta(guid='n1' * 16, name='NewOne',
                              path=[], obj_type='pou', pou_kind='program')
        self.storage.save_object(exist_meta,
                                'PROGRAM Existing\nVAR\nEND_VAR\n', 'new')
        self.storage.save_object(new_meta,
                                'PROGRAM NewOne\nVAR\nEND_VAR\n', ';\n')
        manifest = Manifest(project_name='Test')
        manifest.add_object(exist_meta)
        manifest.add_object(new_meta)
        self.storage.save_manifest(manifest)

        svc = self._make_service(bridge)
        result = svc.import_(ObjectFilter())

        self.assertTrue(result.success)
        self.assertEqual(2, result.completed)
        all_msgs = ' '.join(result.messages)
        self.assertIn('Updated: 1', all_msgs)
        self.assertIn('Created: 1', all_msgs)


if __name__ == '__main__':
    unittest.main()
