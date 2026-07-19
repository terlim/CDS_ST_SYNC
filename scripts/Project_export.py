# -*- coding: utf-8 -*-
from __future__ import print_function
"""
Project_export.py — export ST code from CodeSys to .st files.

Run from CodeSys: Tools → Scripting → Scripts → P → Project_export
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

from Project_options import _load_settings

try:
    from src.infrastructure.codesys_bridge import CodeSysBridge
    from src.infrastructure.text_extractor import TextExtractor
    from src.infrastructure.st_formatter import StFormatter
    from src.infrastructure.file_storage import FileSystemStorage
    from src.services.export_service import ExportService
except ImportError:
    from infrastructure.codesys_bridge import CodeSysBridge
    from infrastructure.text_extractor import TextExtractor
    from infrastructure.st_formatter import StFormatter
    from infrastructure.file_storage import FileSystemStorage
    from services.export_service import ExportService


def main():
    """Entry point — called by CodeSys ScriptEngine."""
    print('=' * 50)
    print('  CDS_ST_SYNC — Export ST Code')
    print('=' * 50)
    print('')

    # Load settings
    settings = _load_settings()
    sync_dir = settings.sync_dir

    if not sync_dir:
        system.ui.error(
            'Sync directory not configured.\n'
            'Run Project_options first to set the sync directory.'
        )
        return

    print('Sync directory: {0}'.format(sync_dir))
    filt = settings.filter
    print('Types: POU={pou}, GVL={gvl}, DUT={dut}, Interface={itf}'.format(
        pou=filt.include_pou, gvl=filt.include_gvl,
        dut=filt.include_dut, itf=filt.include_interface))
    print('')

    # Build services
    try:
        project = projects.primary
        bridge = CodeSysBridge(project)
    except Exception as exc:
        system.ui.error('Cannot access project: {0}'.format(str(exc)))
        return

    extractor = TextExtractor()
    formatter = StFormatter()
    storage = FileSystemStorage(sync_dir)

    def progress_callback(current, total, name):
        print('  [{0}/{1}] {2}'.format(current, total, name))

    export_svc = ExportService(bridge, extractor, storage, formatter,
                               progress_callback=progress_callback)

    print('Exporting...')
    print('')
    result = export_svc.export(filt)

    # Report
    print('')
    print('-' * 50)
    print('Export finished.')
    print('  Objects exported: {0}'.format(result.completed))
    if result.errors:
        print('  Errors: {0}'.format(len(result.errors)))
        for err in result.errors:
            print('    * {name}: {error}'.format(
                name=err.get('name', '?'), error=err.get('error', '')))

    if result.success:
        system.ui.info(
            'Export completed!\n'
            'Objects: {0}\n'
            'Directory: {1}'.format(result.completed, sync_dir))
    else:
        system.ui.error(
            'Export finished with errors.\n'
            'Succeeded: {0} / {1}\n'
            'Errors: {2}'.format(
                result.completed, result.total, len(result.errors)))


if __name__ == '__main__':
    main()
