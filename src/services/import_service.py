# -*- coding: utf-8 -*-
from __future__ import print_function

from interfaces.services import IImportService
from domain.models import OperationResult
from domain.filter import classify_type_guid

# Sentinel GUID for the project root.
_ROOT_GUID = '00000000-0000-0000-0000-000000000000'


class ImportService(IImportService):
    """Orchestrates ST code import: .st files on disk → CodeSys objects.

    Dependencies (all through ABCs):
        bridge: ICodeSysBridge  – writes to CodeSys objects
        storage: IStorage – reads .st files and manifest.json
        formatter: ITextFormatter – parses .st file content

    Does NOT depend on CodeSys API directly – relies solely on the
    ICodeSysBridge abstraction so the service is testable in isolation.
    """

    def __init__(self, bridge, storage, formatter, progress_callback=None):
        """Initialise the import service.

        Args:
            bridge: ICodeSysBridge
            storage: IStorage
            formatter: ITextFormatter
            progress_callback: callable(current, total, message) or None.
                Called once per processed object.
        """
        self._bridge = bridge
        self._storage = storage
        self._formatter = formatter
        self._progress = progress_callback

    # ── Public API ──────────────────────────────────────────────────────

    def import_(self, filter_obj):
        """Run the import.

        Args:
            filter_obj: ObjectFilter

        Returns:
            OperationResult
        """
        result = OperationResult()

        # 1. Load manifest.
        try:
            manifest = self._storage.load_manifest()
        except Exception as exc:
            result.success = False
            result.add_error('', '', 'load_manifest failed: ' + str(exc))
            return result

        all_objects = manifest.objects
        if not all_objects:
            result.add_message('Manifest is empty – nothing to import.')
            result.success = True
            result.completed = 0
            result.total = 0
            return result

        # 2. Filter.
        filtered = [m for m in all_objects if filter_obj.matches(m)]
        skipped = len(all_objects) - len(filtered)
        total = len(all_objects)
        result.total = total

        if not filtered:
            result.add_message(
                'No objects match the filter ({0} skipped).'.format(skipped)
            )
            result.success = True
            result.completed = 0
            return result

        # 3. Process each object.
        updated = 0
        created = 0
        errors = 0

        for idx, meta in enumerate(filtered, 1):
            try:
                # 3a. Load .st file.
                declaration, implementation = self._storage.load_object(meta)

                # 3b. Ensure container exists.
                container_guid = self._ensure_container(meta)

                # 3c. Find or create the CodeSys object.
                obj = self._bridge.get_object_by_guid(meta.guid)
                is_new = obj is None

                if is_new:
                    obj = self._create_object(meta, declaration, container_guid)
                    created += 1
                else:
                    self._bridge.update_text(
                        meta.guid, declaration, implementation
                    )
                    updated += 1

                if self._progress:
                    self._progress(
                        idx, total,
                        meta.name + (' (created)' if is_new else ' (updated)')
                    )

            except Exception as exc:
                result.add_error(
                    meta.guid, meta.name,
                    str(exc)
                )
                errors += 1
                if self._progress:
                    self._progress(
                        idx, total,
                        meta.name + ' (error)'
                    )

        # 4. Emit progress for skipped objects.
        if self._progress:
            for i in range(len(filtered) + 1, total + 1):
                self._progress(i, total, '(skipped by filter)')

        result.success = errors == 0
        result.completed = updated + created
        result.add_message(
            'Updated: {0}, Created: {1}'.format(updated, created)
        )
        if skipped:
            result.add_message(
                'Skipped (filter): {0}'.format(skipped)
            )
        if errors:
            result.add_message(
                'Errors: {0}'.format(errors)
            )

        return result

    # ── Container helpers ───────────────────────────────────────────────

    def _ensure_container(self, meta):
        """Ensure the parent folder hierarchy exists for *meta*.

        Walks the object's `path` list, checking each folder by name.
        Missing folders are created via `bridge.create_folder()`.

        Args:
            meta: ObjectMeta
        Returns:
            str – GUID of the deepest container (or root GUID if path empty).
        """
        if not meta.path:
            return _ROOT_GUID

        # Build a lookup of existing objects by parent GUID.
        all_objs = self._bridge.get_all_objects()
        by_parent = {}
        for o in all_objs:
            pg = getattr(o, 'parent_guid', _ROOT_GUID) or _ROOT_GUID
            by_parent.setdefault(pg, {})[getattr(o, 'name', '').lower()] = o

        current_parent = _ROOT_GUID

        for folder_name in meta.path:
            key = str(folder_name).lower()
            children = by_parent.get(current_parent, {})

            if key in children:
                folder_obj = children[key]
                current_parent = folder_obj.guid
                # Refresh by_parent for the next level.
                grand = {}
                for o in all_objs:
                    pg = getattr(o, 'parent_guid', _ROOT_GUID) or _ROOT_GUID
                    grand.setdefault(pg, {})[getattr(o, 'name', '').lower()] = o
                by_parent = grand
            else:
                # Folder does not exist – create it.
                created = self._bridge.create_folder(folder_name, current_parent)
                if created is None:
                    raise RuntimeError(
                        'Failed to create folder "{0}" inside parent {1}'.format(
                            folder_name, current_parent
                        )
                    )
                current_parent = created.guid
                # After creation, refresh the object list so subsequent
                # lookups include the new folder.
                all_objs = self._bridge.get_all_objects()
                grand = {}
                for o in all_objs:
                    pg = getattr(o, 'parent_guid', _ROOT_GUID) or _ROOT_GUID
                    grand.setdefault(pg, {})[getattr(o, 'name', '').lower()] = o
                by_parent = grand

        return current_parent

    # ── Object creation ─────────────────────────────────────────────────

    def _create_object(self, meta, declaration, container_guid):
        """Create a new CodeSys object from manifest metadata.

        Args:
            meta: ObjectMeta
            declaration: str – full ST declaration text.
            container_guid: str – parent container GUID.
        Returns:
            ICodeSysObject
        """
        obj_type = str(meta.type or '').lower()

        if obj_type == 'pou':
            kind = str(meta.pou_kind or 'program').lower()
            # Canonicalise kind.
            if kind == 'functionblock':
                kind = 'function_block'
            if kind not in ('program', 'function_block', 'function'):
                kind = 'program'
            return self._bridge.create_pou(
                meta.name, kind, container_guid, declaration
            )

        if obj_type == 'gvl':
            return self._bridge.create_gvl(meta.name, container_guid)

        if obj_type == 'dut':
            # Default to 'structure' since we can't reliably determine alias/union
            # from declaration text without deeper parsing.
            return self._bridge.create_dut(
                meta.name, container_guid, 'structure'
            )

        if obj_type == 'interface':
            # Interfaces are created via create_child with the interface GUID.
            # Fallback: try create_pou with 'function' – some CODESYS versions
            # treat INTERFACE-blocks as POU-like.
            return self._bridge.create_pou(
                meta.name, 'function', container_guid, declaration
            )

        if obj_type == 'persistent':
            # Persistent Vars: create via create_child with persistent GUID.
            # The bridge may provide create_persistent, but it's uncommon.
            return self._bridge.create_dut(
                meta.name, container_guid, 'structure'
            )

        if obj_type == 'task_local':
            return self._bridge.create_gvl(meta.name, container_guid)

        raise RuntimeError(
            'Unsupported object type for creation: {0}'.format(meta.type)
        )
