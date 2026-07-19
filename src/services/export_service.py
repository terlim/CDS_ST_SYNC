# -*- coding: utf-8 -*-
from __future__ import print_function

from interfaces.services import IExportService
from domain.models import Manifest, ObjectMeta, OperationResult
from domain.filter import classify_type_guid



def _infer_kind(obj):
    """Infer object kind from its declaration text rather than type_guid.

    type_guid is not directly accessible on IronPython CodeSys objects.
    Instead we inspect the declaration_text content.
    """
    decl = getattr(obj, 'declaration_text', None) or ""
    if not decl:
        return None
    upper = decl.strip().upper()
    if 'VAR_GLOBAL' in upper or 'VAR_GLOBAL CONSTANT' in upper:
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
    return 'pou'  # default

class ExportService(IExportService):
    """Orchestrates ST code export: CodeSys objects → .st files on disk.

    Dependencies (all through ABCs):
        bridge: ICodeSysBridge  – reads CodeSys objects
        extractor: ITextExtractor – extracts declaration/implementation text
        storage: IStorage – persists .st files and manifest.json
        formatter: ITextFormatter – formats .st file content

    Does NOT depend on CodeSys API directly – relies solely on the
    ICodeSysBridge abstraction so the service is testable in isolation.
    """

    def __init__(self, bridge, extractor, storage, formatter,
                 progress_callback=None):
        """Initialise the export service.

        Args:
            bridge: ICodeSysBridge
            extractor: ITextExtractor
            storage: IStorage
            formatter: ITextFormatter
            progress_callback: callable(current, total, message) or None.
                Called once per processed object (including skipped ones).
        """
        self._bridge = bridge
        self._extractor = extractor
        self._storage = storage
        self._formatter = formatter
        self._progress = progress_callback

    # ── Public API ──────────────────────────────────────────────────────

    def export(self, filter_obj):
        """Run the export."""
        result = OperationResult()

        try:
            all_objects = self._bridge.get_all_objects()
        except Exception as exc:
            result.success = False
            result.add_error('', '', 'bridge.get_all_objects() failed: ' + str(exc))
            return result

        # Classify: keep objects that have textual_declaration
        textual = []
        for obj in all_objects:
            decl = getattr(obj, 'declaration_text', None)
            # Also try direct attribute check on underlying object
            if decl is None:
                continue
            kind = _infer_kind(obj)
            if kind is None:
                kind = 'pou'  # fallback
            textual.append((obj, kind))

        # 3. Apply filter.
        filtered = []
        skipped_by_filter = 0
        for obj, kind in textual:
            meta = self._build_meta(obj, kind)
            if filter_obj.matches(meta):
                filtered.append((obj, kind, meta))
            else:
                skipped_by_filter += 1

        total = len(filtered) + skipped_by_filter
        result.total = total

        if not filtered:
            result.add_message('No textual objects match the filter.')
            # Still save an empty manifest so the sync root is initialised.
            manifest = Manifest()
            self._storage.save_manifest(manifest)
            result.success = True
            result.completed = 0
            return result

        # 4. Export each matching object.
        manifest = Manifest()
        completed = 0
        for idx, (obj, kind, meta) in enumerate(filtered, 1):
            try:
                # 4a. Extract text.
                declaration = self._extract_st_declaration(obj)
                implementation = self._extract_st_implementation(obj, kind)

                # 4b. Compute sha1 + save to storage.
                content = self._formatter.format_st(declaration, implementation)
                meta.compute_sha1(declaration, implementation)
                self._storage.save_object(meta, declaration, implementation)

                # 4c. Record in manifest.
                manifest.add_object(meta)
                completed += 1

                if self._progress:
                    self._progress(idx, total, meta.name)

            except Exception as exc:
                result.add_error(
                    getattr(meta, 'guid', ''),
                    getattr(meta, 'name', ''),
                    str(exc)
                )
                if self._progress:
                    self._progress(idx, total,
                                   getattr(meta, 'name', '?') + ' (error)')

        # 5. Emit progress for skipped objects.
        if self._progress:
            for i in range(len(filtered) + 1, total + 1):
                self._progress(i, total, '(skipped by filter)')

        # 6. Persist manifest.
        try:
            self._storage.save_manifest(manifest)
        except Exception as exc:
            result.add_error('', '', 'save_manifest failed: ' + str(exc))
            return result

        result.success = len(result.errors) == 0
        result.completed = completed
        result.add_message(
            'Exported {0} objects to manifest ({1} skipped by filter)'.format(
                completed, skipped_by_filter
            )
        )

        return result

    # ── ObjectMeta construction ──────────────────────────────────────────

    def _build_meta(self, obj, kind):
        """Create ObjectMeta from an ICodeSysObject and its type kind.

        Args:
            obj: ICodeSysObject
            kind: str – one of 'pou', 'gvl', 'dut', ...
        Returns:
            ObjectMeta
        """
        pou_kind = None
        if kind == 'pou':
            pou_kind = self._infer_pou_kind(obj)

        path = self._build_path(obj)

        return ObjectMeta(
            guid=obj.guid,
            name=obj.name,
            obj_type=kind,
            path=path,
            pou_kind=pou_kind,
        )

    def _build_path(self, obj):
        """Build the folder path list by walking up parent references.

        The list goes from the project root to the direct parent of *obj*.
        The object's own name is not included.

        Args:
            obj: ICodeSysObject
        Returns:
            list[str]
        """
        parts = []
        visited = set()
        current = obj
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
            if pname:
                parts.append(str(pname))

            current = parent

        parts.reverse()
        return parts

    @staticmethod
    def _infer_pou_kind(obj):
        """Infer the POU kind from the declaration text.

        Returns 'program', 'function_block', 'function', or 'program' as
        a safe default.
        """
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

    # ── Text extraction helpers ──────────────────────────────────────────

    def _extract_st_declaration(self, obj):
        """Extract and normalise the declaration text.

        Returns an empty string when the extractor returns None.
        """
        text = self._extractor.extract_declaration(obj)
        return text or ''

    def _extract_st_implementation(self, obj, kind):
        """Extract the implementation text.

        Returns None for object kinds that do not have implementations
        (gvl, dut, interface, persistent, task_local).
        """
        if kind in ('gvl', 'dut', 'interface', 'persistent', 'task_local'):
            return None
        return self._extractor.extract_implementation(obj)
