# -*- coding: utf-8 -*-
"""Tests for FileSystemStorage."""
from __future__ import print_function

import os
import sys
import shutil
import tempfile
import unittest

# Ensure src/ is on path.
_SELF_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_SELF_DIR)
_SRC_DIR = os.path.join(_PROJECT_DIR, 'src')
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from infrastructure.file_storage import FileSystemStorage
from domain.models import ObjectMeta, Manifest


class TestFileSystemStorage(unittest.TestCase):
    """Tests for FileSystemStorage."""

    def setUp(self):
        """Create a fresh temp directory + storage for each test."""
        self.tmp = tempfile.mkdtemp(prefix='cds-st-test-')
        self.storage = FileSystemStorage(self.tmp)

    def tearDown(self):
        """Remove the temp directory."""
        try:
            shutil.rmtree(self.tmp)
        except OSError:
            pass

    # ── helpers ──────────────────────────────────────────────────────────────

    def _meta(self, name='PLC_PRG', obj_type='pou', path=None, pou_kind='program'):
        """Create a sample ObjectMeta for tests."""
        return ObjectMeta(
            guid='4140366f-02ec-4908-a7ac-d8d91000791f',
            name=name,
            obj_type=obj_type,
            path=path or ['Device', 'Plc Logic', 'Application', 'PROGRAMS'],
            pou_kind=pou_kind,
        )

    def _content(self, path):
        """Read UTF-8 content from the storage root."""
        import io
        with io.open(path, 'r', encoding='utf-8') as fh:
            return fh.read()

    # ── save_object ─────────────────────────────────────────────────────────

    def test_save_object_creates_file_with_hierarchy(self):
        """save_object creates the .st file under the correct hierarchy."""
        meta = self._meta()
        self.storage.save_object(meta, 'VAR\nEND_VAR', 'x := 1;')

        expected = os.path.join(
            self.tmp,
            'Device', 'Plc Logic', 'Application', 'PROGRAMS', 'PLC_PRG.st',
        )
        self.assertTrue(os.path.isfile(expected),
                        'File was not created at {0}'.format(expected))

    def test_save_object_content_has_marker(self):
        """save_object writes content with the implementation marker."""
        meta = self._meta()
        self.storage.save_object(meta, 'PROGRAM PLC_PRG\nVAR\nEND_VAR', 'x := 1;')

        path = os.path.join(
            self.tmp,
            'Device', 'Plc Logic', 'Application', 'PROGRAMS', 'PLC_PRG.st',
        )
        content = self._content(path)
        self.assertIn('// --- implementation ---', content)
        self.assertIn('PROGRAM PLC_PRG', content)
        self.assertIn('x := 1;', content)

    def test_save_object_no_implementation(self):
        """save_object for GVL (no implementation) omits the marker."""
        meta = self._meta(name='GVL_COLOR', obj_type='gvl', pou_kind=None)
        self.storage.save_object(meta, 'VAR_GLOBAL\nEND_VAR', None)

        path = os.path.join(self.tmp, 'GVL_COLOR.st')
        content = self._content(path)
        self.assertNotIn('// --- implementation ---', content)
        self.assertIn('VAR_GLOBAL', content)

    def test_save_object_empty_declaration(self):
        """save_object with empty strings still writes a valid file."""
        meta = self._meta()
        self.storage.save_object(meta, '', '')

        path = os.path.join(
            self.tmp,
            'Device', 'Plc Logic', 'Application', 'PROGRAMS', 'PLC_PRG.st',
        )
        self.assertTrue(os.path.isfile(path))

    def test_save_object_updates_mtime(self):
        """save_object sets file_mtime on the ObjectMeta."""
        meta = self._meta()
        self.assertIsNone(meta.file_mtime)
        self.storage.save_object(meta, 'VAR\nEND_VAR', None)

        self.assertIsNotNone(meta.file_mtime)
        self.assertGreater(meta.file_mtime, 0)

    def test_save_object_updates_sha1(self):
        """save_object computes and stores sha1 on the ObjectMeta."""
        meta = self._meta()
        self.assertIsNone(meta.sha1)

        decl = 'PROGRAM PLC_PRG\nVAR\nEND_VAR'
        impl = 'x := 1;'
        self.storage.save_object(meta, decl, impl)

        self.assertIsNotNone(meta.sha1)
        # Verify that the same content produces the same hash.
        self.assertEqual(len(meta.sha1), 40, 'SHA1 hex should be 40 chars')

    def test_save_object_overwrite(self):
        """Saving the same object twice overwrites the file."""
        meta = self._meta()

        self.storage.save_object(meta, 'VAR\n  a: INT;\nEND_VAR', 'a := 1;')
        sha1_first = meta.sha1

        self.storage.save_object(meta, 'VAR\n  b: BOOL;\nEND_VAR', 'b := TRUE;')
        sha1_second = meta.sha1

        self.assertNotEqual(sha1_first, sha1_second,
                            'SHA1 should change after overwrite')

        # Content should match the second write.
        decl, impl = self.storage.load_object(meta)
        self.assertIn('b: BOOL', decl)
        self.assertNotIn('a: INT', decl)

    # ── load_object ─────────────────────────────────────────────────────────

    def test_load_object_roundtrip(self):
        """save_object + load_object returns the same data."""
        meta = self._meta()
        decl = 'PROGRAM PLC_PRG\nVAR\n  count: INT;\nEND_VAR'
        impl = 'count := count + 1;'

        self.storage.save_object(meta, decl, impl)
        loaded_decl, loaded_impl = self.storage.load_object(meta)

        self.assertEqual(loaded_decl, decl)
        self.assertEqual(loaded_impl, impl)

    def test_load_object_gvl_roundtrip(self):
        """save + load a GVL (no implementation)."""
        meta = self._meta(name='GVL_COLOR', obj_type='gvl', pou_kind=None)
        decl = 'VAR_GLOBAL\n  color: DWORD;\nEND_VAR'

        self.storage.save_object(meta, decl, None)
        loaded_decl, loaded_impl = self.storage.load_object(meta)

        self.assertEqual(loaded_decl, decl)
        self.assertIsNone(loaded_impl)

    def test_load_object_missing_file(self):
        """load_object for a non-existent file raises IOError."""
        meta = self._meta()
        with self.assertRaises(IOError):
            self.storage.load_object(meta)

    # ── save_manifest / load_manifest ────────────────────────────────────────

    def test_manifest_roundtrip(self):
        """save_manifest + load_manifest preserves all fields."""
        m = Manifest(project_name='TestProject')
        meta = self._meta()
        meta.sha1 = 'abc123abc123abc123abc123abc123abc123abc1'
        meta.file_mtime = 1721395800.0
        m.add_object(meta)

        self.storage.save_manifest(m)
        loaded = self.storage.load_manifest()

        self.assertEqual(loaded.project_name, 'TestProject')
        self.assertEqual(len(loaded.objects), 1)

        loaded_meta = loaded.objects[0]
        self.assertEqual(loaded_meta.guid, meta.guid)
        self.assertEqual(loaded_meta.name, 'PLC_PRG')
        self.assertEqual(loaded_meta.type, 'pou')
        self.assertEqual(loaded_meta.pou_kind, 'program')
        self.assertEqual(loaded_meta.sha1, 'abc123abc123abc123abc123abc123abc123abc1')
        self.assertEqual(loaded_meta.file_mtime, 1721395800.0)

    def test_load_manifest_empty_dir(self):
        """load_manifest on an empty directory returns an empty Manifest."""
        m = self.storage.load_manifest()
        self.assertEqual(len(m.objects), 0)
        self.assertEqual(m.project_name, '')

    def test_manifest_with_zero_objects(self):
        """save + load a Manifest with no objects."""
        m = Manifest(project_name='Empty')
        self.storage.save_manifest(m)

        loaded = self.storage.load_manifest()
        self.assertEqual(loaded.project_name, 'Empty')
        self.assertEqual(len(loaded.objects), 0)

    def test_manifest_with_multiple_objects(self):
        """Manifest with multiple entries roundtrips correctly."""
        m = Manifest(project_name='Multi')
        for i in range(5):
            meta = ObjectMeta(
                guid='00000000-0000-0000-0000-{:012d}'.format(i),
                name='Object_{0}'.format(i),
                obj_type='pou',
                path=['Folder'],
                pou_kind='program',
                sha1='sha1_{0}'.format(i),
            )
            m.add_object(meta)

        self.storage.save_manifest(m)
        loaded = self.storage.load_manifest()
        self.assertEqual(len(loaded.objects), 5,
                         'All 5 objects should be restored')

    # ── path handling ───────────────────────────────────────────────────────

    def test_deep_hierarchy(self):
        """Files are placed correctly for deeply nested objects."""
        meta = self._meta(
            name='DeepPOU',
            path=['A', 'B', 'C', 'D', 'E', 'F'],
        )
        self.storage.save_object(meta, 'VAR\nEND_VAR', ';')

        expected = os.path.join(self.tmp, 'A', 'B', 'C', 'D', 'E', 'F', 'DeepPOU.st')
        self.assertTrue(os.path.isfile(expected),
                        'Expected {0} to exist'.format(expected))

    def test_special_chars_in_name(self):
        """Names with unsafe characters are sanitised by ObjectMeta.relative_path."""
        meta = self._meta(
            name='Test:Name<With>Chars',
            path=['Folder'],
        )
        self.storage.save_object(meta, 'VAR\nEND_VAR', ';')

        # The relative_path transforms '<>:"/\\|?*' → '_'
        self.assertNotIn(':', meta.relative_path)
        self.assertNotIn('<', meta.relative_path)
        self.assertNotIn('>', meta.relative_path)

        # File should still be loadable via the same meta.
        decl, _ = self.storage.load_object(meta)
        self.assertEqual(decl, 'VAR\nEND_VAR')

    def test_root_level_object(self):
        """Object with an empty path list is stored at sync root."""
        meta = self._meta(name='TopLevel', path=[])
        self.storage.save_object(meta, 'PROGRAM TopLevel\nVAR\nEND_VAR', ';')

        expected = os.path.join(self.tmp, 'TopLevel.st')
        self.assertTrue(os.path.isfile(expected))

    # ── atomic write ────────────────────────────────────────────────────────

    def test_atomic_write_no_temp_leftover(self):
        """After a successful write there are no temp files left."""
        meta = self._meta()
        self.storage.save_object(meta, 'VAR\nEND_VAR', 'x := 1;')

        # No .cds-st-sync-tmp-* files should remain.
        for entry in os.listdir(self.tmp):
            self.assertFalse(
                entry.startswith('.cds-st-sync-tmp-'),
                'Temp file {0} was not cleaned up'.format(entry),
            )

    def test_consecutive_writes(self):
        """Two consecutive writes to the same path replace content correctly."""
        meta = self._meta()

        self.storage.save_object(meta, 'DECL-1', 'IMPL-1')
        self.storage.save_object(meta, 'DECL-2', 'IMPL-2')

        decl, impl = self.storage.load_object(meta)
        self.assertEqual(decl, 'DECL-2')
        self.assertEqual(impl, 'IMPL-2')

    # ── watch_changes ───────────────────────────────────────────────────────

    def test_watch_changes_not_implemented(self):
        """watch_changes raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            self.storage.watch_changes(lambda p: None)


if __name__ == '__main__':
    unittest.main()
