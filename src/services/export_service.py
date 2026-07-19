# -*- coding: utf-8 -*-
from __future__ import print_function

from interfaces.services import IExportService
from domain.models import Manifest, ObjectMeta, OperationResult


def _infer_kind(obj):
    """Infer object kind from its declaration text."""
    decl = getattr(obj, 'declaration_text', None) or ''
    if not decl:
        return None
    upper = decl.strip().upper()
    if 'VAR_GLOBAL' in upper:
        return 'gvl'
    if upper.startswith('TYPE'):
        return 'dut'
    if upper.startswith('INTERFACE'):
        return 'interface'
    if upper.startswith('FUNCTION_BLOCK'):
        return 'pou'
    if upper.startswith('FUNCTION'):
        return 'pou'
    if upper.startswith('PROGRAM'):
        return 'pou'
    return 'pou'


def _is_collapsed_parent(obj):
    """Return True if obj is a code object (POU/Interface/Property), not a folder."""
    native = getattr(obj, '_native', None)
    if native is None:
        return False
    return getattr(native, 'textual_implementation', None) is not None


class ExportService(IExportService):
    """Orchestrates ST code export: CodeSys objects -> .st files on disk."""

    def __init__(self, bridge, extractor, storage, formatter,
                 progress_callback=None, use_virtual_folders=False):
        self._bridge = bridge
        self._extractor = extractor
        self._storage = storage
        self._formatter = formatter
        self._progress = progress_callback
        self._use_virtual_folders = use_virtual_folders

    def export(self, filter_obj):
        """Run the export."""
        result = OperationResult()

        try:
            all_objects = self._bridge.get_all_objects()
        except Exception as exc:
            result.success = False
            result.add_error('', '', 'get_all_objects failed: ' + str(exc))
            return result

        textual = []
        for obj in all_objects:
            decl = getattr(obj, 'declaration_text', None)
            if decl is None:
                continue
            kind = _infer_kind(obj) or 'pou'
            textual.append((obj, kind))

        filtered = []
        skipped = 0
        for obj, kind in textual:
            meta = self._build_meta(obj, kind)
            if filter_obj.matches(meta):
                filtered.append((obj, kind, meta))
            else:
                skipped += 1

        total = len(filtered) + skipped
        result.total = total

        if not filtered:
            result.add_message('No textual objects match the filter.')
            self._storage.save_manifest(Manifest())
            result.success = True
            return result

        manifest = Manifest()
        completed = 0
        for idx, (obj, kind, meta) in enumerate(filtered, 1):
            try:
                declaration = self._extract_st_declaration(obj)
                implementation = self._extract_st_implementation(obj, kind)
                meta.compute_sha1(declaration, implementation)
                self._storage.save_object(meta, declaration, implementation)
                manifest.add_object(meta)
                completed += 1
                if self._progress:
                    self._progress(idx, total, meta.name)
            except Exception as exc:
                result.add_error(
                    getattr(meta, 'guid', ''),
                    getattr(meta, 'name', ''),
                    str(exc))
                if self._progress:
                    self._progress(idx, total,
                                   getattr(meta, 'name', '?') + ' (error)')

        if self._progress:
            for i in range(len(filtered) + 1, total + 1):
                self._progress(i, total, '(skipped)')

        try:
            self._storage.save_manifest(manifest)
        except Exception as exc:
            result.add_error('', '', 'save_manifest: ' + str(exc))
            return result

        result.success = len(result.errors) == 0
        result.completed = completed
        result.add_message('Exported {0} objects ({1} skipped)'.format(
            completed, skipped))
        return result

    # ── Path building ──────────────────────────────────────────────────

    def _build_meta(self, obj, kind):
        pou_kind = None
        if kind == 'pou':
            pou_kind = self._infer_pou_kind(obj)
        path, output_name = self._build_path_and_name(obj, kind)
        return ObjectMeta(
            guid=obj.guid,
            name=output_name or obj.name,
            obj_type=kind,
            path=path,
            pou_kind=pou_kind,
        )

    def _build_path_and_name(self, obj, kind):
        """Build path[] and optionally a flat name for POU children.

        Returns (path, output_name).
        """
        parts = []
        visited = set()
        output_name = None
        current = obj
        child_name = None

        while True:
            try:
                parent = current.parent
            except Exception:
                parent = None
            if parent is None:
                break

            parent_guid = getattr(parent, 'guid', None)
            if parent_guid is None:
                break
            pguid = str(parent_guid).strip('{}').lower()
            if pguid == '00000000-0000-0000-0000-000000000000':
                break
            if pguid in visited:
                break
            visited.add(pguid)

            pname = getattr(parent, 'name', '')
            if pname and 'Project(' not in str(pname) and 'stPath=' not in str(pname):
                if _is_collapsed_parent(parent):
                    if self._use_virtual_folders:
                        # Virtual folder: parent becomes a path component
                        parts.append(str(pname))
                    else:
                        # Flat: chain Parent.Child
                        cname = child_name or getattr(current, 'name', '')
                        if output_name:
                            output_name = str(pname) + '.' + output_name
                        else:
                            output_name = str(pname) + '.' + str(cname)
                else:
                    parts.append(str(pname))

            child_name = getattr(current, 'name', '')
            current = parent

        parts.reverse()

        # Virtual root: non-Device → POUs
        if parts:
            first = parts[0]
            if first != 'Device' and first != 'POUs':
                parts.insert(0, 'POUs')
        elif not output_name:
            virtual = {
                'pou': 'POUs',
                'gvl': 'Global Vars',
                'dut': 'Data Types',
                'interface': 'Interfaces',
            }.get(kind)
            if virtual:
                parts.append(virtual)


        # Virtual folders: POU itself goes inside its own folder
        if self._use_virtual_folders and not output_name:
            native = getattr(obj, '_native', None)
            if native is not None:
                has_impl = getattr(native, 'textual_implementation', None) is not None
                if has_impl:
                    parts.append(obj.name)
        return parts, output_name

    @staticmethod
    def _infer_pou_kind(obj):
        try:
            decl = obj.declaration_text
        except Exception:
            decl = None
        text = (decl or '').strip().upper()
        if text.startswith('FUNCTION_BLOCK'):
            return 'function_block'
        if text.startswith('FUNCTION'):
            return 'function'
        return 'program'

    def _extract_st_declaration(self, obj):
        text = self._extractor.extract_declaration(obj)
        return text or ''

    def _extract_st_implementation(self, obj, kind):
        if kind in ('gvl', 'dut', 'interface', 'persistent', 'task_local'):
            return None
        return self._extractor.extract_implementation(obj)
