# -*- coding: utf-8 -*-
from __future__ import print_function
"""
Project_import.py — import ST code from .st files back into CodeSys.

Run from CodeSys: Tools → Scripting → Scripts → P → Project_import
"""

import os
import sys as _sys

# ── Resolve project root ──────────────────────────────────────────
_script_file = os.path.abspath(__file__)
_project_root = os.path.dirname(os.path.dirname(_script_file))
if not os.path.isfile(os.path.join(_project_root, 'cds_bootstrap.py')):
    _project_root = os.path.dirname(_script_file)

if _project_root not in _sys.path:
    _sys.path.insert(0, _project_root)
_src = os.path.join(_project_root, 'src')
if os.path.isdir(_src) and _src not in _sys.path:
    _sys.path.insert(0, _src)

import cds_bootstrap  # noqa

_scripts_dir = os.path.join(_project_root, 'scripts')
if os.path.isdir(_scripts_dir) and _scripts_dir not in _sys.path:
    _sys.path.insert(0, _scripts_dir)

from Project_options import _load_settings, _get_project_dir

try:
    from src.infrastructure.codesys_bridge import CodeSysBridge
    from src.infrastructure.st_formatter import StFormatter
    from src.infrastructure.file_storage import FileSystemStorage
    from src.services.import_service import ImportService
except ImportError:
    from infrastructure.codesys_bridge import CodeSysBridge
    from infrastructure.st_formatter import StFormatter
    from infrastructure.file_storage import FileSystemStorage
    from services.import_service import ImportService


def _resolve_sync_dir(sync_dir):
    """Resolve sync_dir: absolute path stays, relative resolved to project dir."""
    if os.path.isabs(sync_dir):
        return sync_dir
    proj_dir = _get_project_dir()
    if proj_dir:
        return os.path.normpath(os.path.join(proj_dir, sync_dir))
    return os.path.abspath(sync_dir)


def main():
    """Entry point — called by CodeSys ScriptEngine."""
    print('=' * 50)
    print('  CDS_ST_SYNC — Import ST Code')
    print('=' * 50)
    print('')

    settings = _load_settings()
    sync_dir = settings.sync_dir

    if not sync_dir:
        system.ui.error(
            'Sync directory not configured.\n'
            'Run Project_options first to set the sync directory.'
        )
        return

    sync_dir = _resolve_sync_dir(sync_dir)
    print('Sync directory: {0}'.format(sync_dir))

    manifest_path = os.path.join(sync_dir, 'manifest.json')
    if not os.path.exists(manifest_path):
        system.ui.error(
            'No manifest.json found.\n'
            'Run Project_export first.\n'
            'Directory: {0}'.format(sync_dir))
        return

    filt = settings.filter
    print('Types: POU={pou}, GVL={gvl}, DUT={dut}, Interface={itf}'.format(
        pou=filt.include_pou, gvl=filt.include_gvl,
        dut=filt.include_dut, itf=filt.include_interface))
    print('')

    try:
        import __main__ as _main
        project = _main.projects.primary
        bridge = CodeSysBridge(project)
    except Exception as exc:
        system.ui.error('Cannot access project: {0}'.format(str(exc)))
        return

    formatter = StFormatter()
    storage = FileSystemStorage(sync_dir)

    def progress_callback(current, total, name):
        print('  [{0}/{1}] {2}'.format(current, total, name))

    import_svc = ImportService(bridge, storage, formatter,
                               progress_callback=progress_callback)

    print('Importing...')
    print('')
    result = import_svc.import_(filt)

    print('')
    print('-' * 50)
    print('Import finished.')
    print('  Objects processed: {0}'.format(result.completed))
    created = getattr(result, 'created', 0)
    if created:
        print('  Created (new):     {0}'.format(created))
    if result.errors:
        print('  Errors:            {0}'.format(len(result.errors)))
        for err in result.errors:
            print('    * {name}: {error}'.format(
                name=err.get('name', '?'), error=err.get('error', '')))

    if result.success:
        msg = 'Import completed!\nObjects updated: {0}'.format(
            result.completed)
        if created:
            msg += '\nObjects created: {0}'.format(created)
        system.ui.info(msg)
    else:
        system.ui.error(
            'Import finished with errors.\n'
            'Succeeded: {0} / {1}\n'
            'Errors: {2}'.format(
                result.completed, result.total, len(result.errors)))


if __name__ == '__main__':
    main()
