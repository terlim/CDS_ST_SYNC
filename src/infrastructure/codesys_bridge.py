# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import tempfile
import xml.etree.ElementTree as ET

from interfaces.bridge import ICodeSysBridge
from infrastructure.codesys_object import (
    CodeSysObjectProxy,
    _to_guid_str,
    _to_system_guid,
    _find_pou_type_enum,
    _find_dut_type_enum,
    _extract_return_type,
)
from domain.models import ProjectTree, OperationResult
from domain.filter import classify_type_guid


class CodeSysBridge(ICodeSysBridge):
    """Sole class that directly interacts with CodeSys ScriptEngine API.

    Implements the full ICodeSysBridge interface (IObjectReader +
    IObjectWriter + ITimestampReader).  All application services depend
    on this interface — never on the native objects.

    Args:
        project: the CodeSys project object (projects.primary) or None
                 to auto-detect from __main__.projects.primary.
    """

    def __init__(self, project=None):
        if project is None:
            import __main__
            projects = getattr(__main__, 'projects', None)
            project = projects.primary if projects is not None else None
        self._project = project
        self._guid_map = None

    # ═══════════════════════════════════════════════════════════════════
    # IObjectReader
    # ═══════════════════════════════════════════════════════════════════

    def get_all_objects(self):
        """Return flat list of all CodeSysObjectProxy in the project."""
        if self._project is None:
            print('[bridge] project is None'); return []
        try:
            natives = self._project.get_children(recursive=True)
            print('[bridge] get_children returned {0} objects'.format(len(natives) if natives else 0))
        except Exception as exc:
            print('[bridge] get_children failed: ' + str(exc)); return []
        return [CodeSysObjectProxy(obj) for obj in (natives or [])]

    def get_object_by_guid(self, guid):
        """Find an object by GUID.  Builds and caches a guid→proxy map."""
        if self._guid_map is None:
            self._build_guid_map()
        key = str(guid or '').replace('{', '').replace('}', '').lower()
        return self._guid_map.get(key)

    def get_project_tree(self):
        """Build a ProjectTree from the live CodeSys project."""
        objects = self.get_all_objects()
        tree = ProjectTree()
        for obj in objects:
            obj_type = classify_type_guid(obj.type_guid) or 'folder'
            tree.add_node(obj.guid, obj.name, obj_type, obj.parent_guid)
        return tree

    # ═══════════════════════════════════════════════════════════════════
    # IObjectWriter
    # ═══════════════════════════════════════════════════════════════════

    def update_text(self, guid, declaration, implementation):
        result = OperationResult()
        result.total = 1

        obj = self.get_object_by_guid(guid)
        if obj is None:
            result.add_error(guid, None, 'Object not found: {0}'.format(guid))
            return result

        native = obj._native
        updated = False

        if declaration is not None:
            doc = getattr(native, 'textual_declaration', None)
            if doc is not None:
                try:
                    _set_text_document(doc, declaration)
                    updated = True
                except Exception as exc:
                    result.add_error(guid, obj.name, 'declaration update: {0}'.format(exc))
                    return result

        if implementation is not None:
            doc = getattr(native, 'textual_implementation', None)
            if doc is not None:
                try:
                    _set_text_document(doc, implementation)
                    updated = True
                except Exception as exc:
                    result.add_error(guid, obj.name, 'implementation update: {0}'.format(exc))
                    return result

        if updated:
            result.completed = 1
            result.add_message('Updated: {0}'.format(obj.name))
        else:
            result.add_message('No changes for {0}'.format(obj.name))

        return result

    def create_pou(self, name, kind, container_guid, declaration):
        container = self.get_object_by_guid(container_guid)
        if container is None:
            raise ValueError('Container not found: {0}'.format(container_guid))
        return self._create_pou_impl(container._native, name, kind, declaration)

    def create_gvl(self, name, container_guid):
        container = self.get_object_by_guid(container_guid)
        if container is None:
            raise ValueError('Container not found: {0}'.format(container_guid))
        native = self._create_textual_child(container._native, name, 'create_gvl')
        if native is None:
            raise RuntimeError('create_gvl returned None for {0}'.format(name))
        return CodeSysObjectProxy(native)

    def create_dut(self, name, container_guid, dut_kind='structure'):
        container = self.get_object_by_guid(container_guid)
        if container is None:
            raise ValueError('Container not found: {0}'.format(container_guid))
        native = self._create_dut_impl(container._native, name, dut_kind)
        if native is None:
            raise RuntimeError('create_dut returned None for {0}'.format(name))
        return CodeSysObjectProxy(native)

    def create_folder(self, name, parent_guid):
        parent = self.get_object_by_guid(parent_guid)
        if parent is None:
            raise ValueError('Parent not found: {0}'.format(parent_guid))

        native_parent = parent._native

        # Prefer create_folder
        if hasattr(native_parent, 'create_folder'):
            try:
                result = native_parent.create_folder(name)
                if result is not None:
                    return CodeSysObjectProxy(result)
            except Exception as exc:
                pass

        # Fallback: create_child with folder type GUID
        folder_guid = '738bea1e-99bb-4f04-90bb-a7a567e74e3a'
        if hasattr(native_parent, 'create_child'):
            try:
                guid_obj = _to_system_guid(folder_guid)
                result = native_parent.create_child(name, guid_obj)
                if result is not None:
                    return CodeSysObjectProxy(result)
            except Exception as exc:
                pass

        raise RuntimeError('Cannot create folder: {0}'.format(name))

    # ═══════════════════════════════════════════════════════════════════
    # ITimestampReader
    # ═══════════════════════════════════════════════════════════════════

    def get_timestamps(self):
        result = {}
        if self._project is None:
            return result

        try:
            objects = self._project.get_children(recursive=True)
        except Exception as exc:
            return result

        if not objects:
            return result

        tmp_fd, tmp_path = tempfile.mkstemp(prefix='cds_ts_', suffix='.xml')
        try:
            os.close(tmp_fd)
            os.remove(tmp_path)
            self._project.export_native(objects, tmp_path, recursive=False)

            tree = ET.parse(tmp_path)
            root = tree.getroot()

            for meta in root.iter('Single'):
                if meta.get('Name') != 'MetaObject':
                    continue
                guid_text = None
                ts_text = None
                for child in meta:
                    child_name = child.get('Name', '')
                    if child_name == 'Guid' and child.text:
                        guid_text = str(child.text).replace('{', '').replace('}', '')
                    elif child_name == 'Timestamp' and child.text:
                        try:
                            ts_text = int(child.text)
                        except Exception as exc:
                            pass
                if guid_text and ts_text is not None:
                    result[guid_text] = ts_text
        except Exception as exc:
            pass
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception as exc:
                    pass

        return result

    # ═══════════════════════════════════════════════════════════════════
    # Private helpers
    # ═══════════════════════════════════════════════════════════════════

    def _build_guid_map(self):
        self._guid_map = {}
        for obj in self.get_all_objects():
            if obj.guid:
                self._guid_map[obj.guid] = obj

    def _create_pou_impl(self, container_native, name, kind, declaration):
        pou_type_enum = _find_pou_type_enum()
        if pou_type_enum is None:
            raise RuntimeError('PouType enum not found')

        pou_type = {
            'program': getattr(pou_type_enum, 'Program', None),
            'function_block': getattr(pou_type_enum, 'FunctionBlock', None)
                             or getattr(pou_type_enum, 'Function_Block', None),
            'function': getattr(pou_type_enum, 'Function', None),
        }.get(kind)

        if pou_type is None:
            raise ValueError('Unknown POU kind: {0}'.format(kind))

        if kind == 'function':
            return_type = _extract_return_type(declaration)
            if not return_type:
                raise ValueError(
                    'Cannot create FUNCTION without return type. '
                    'Declaration must contain "FUNCTION name : TYPE"'
                )
            native = _call_create_pou(container_native, name, pou_type, return_type)
        else:
            native = _call_create_pou(container_native, name, pou_type)

        if native is None:
            raise RuntimeError('create_pou returned None for {0}'.format(name))
        return CodeSysObjectProxy(native)

    def _create_textual_child(self, container_native, name, method_name):
        method = getattr(container_native, method_name, None)
        if method is None:
            # Walk up to find a container that supports this method
            current = container_native
            while current is not None:
                method = getattr(current, method_name, None)
                if method is not None:
                    break
                current = getattr(current, 'parent', None)
            if method is None:
                raise RuntimeError('Method {0} not found'.format(method_name))
        return method(name)

    def _create_dut_impl(self, container_native, name, dut_kind):
        method = getattr(container_native, 'create_dut', None)
        if method is None:
            return self._create_textual_child(container_native, name, 'create_dut')

        if dut_kind == 'structure':
            return method(name)

        dut_type_enum = _find_dut_type_enum()
        if dut_type_enum is not None:
            dt = {
                'alias': getattr(dut_type_enum, 'Alias', None),
                'union': getattr(dut_type_enum, 'Union', None),
            }.get(dut_kind)
            if dt is not None:
                return method(name, dt)

        return method(name)


# ═══════════════════════════════════════════════════════════════════════
# Module-level helpers
# ═══════════════════════════════════════════════════════════════════════

def _set_text_document(doc, value):
    """Set the text content of an ITextDocument, trying .text then .replace."""
    if hasattr(doc, 'text'):
        try:
            doc.text = value
            return
        except Exception as exc:
            pass
    if hasattr(doc, 'replace'):
        doc.replace(value)
        return
    raise RuntimeError('Cannot write to text document')


def _call_create_pou(container, name, pou_type, return_type=None):
    """Call container.create_pou trying positional then keyword args."""
    if return_type is None:
        return container.create_pou(name, pou_type)
    try:
        return container.create_pou(name, pou_type, return_type)
    except TypeError:
        return container.create_pou(name, pou_type, return_type=return_type)
