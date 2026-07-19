# -*- coding: utf-8 -*-
from __future__ import print_function
"""
Project_export.py — export ST code from CodeSys to .st files.

Run from CodeSys: Tools → Scripting → Scripts → P → Project_export

Reads settings from .cds-st-sync.json (configured by Project_options),
then exports all textual objects to ST files preserving the CodeSys
folder hierarchy.
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

# Import from scripts (same project)
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
    from src.domain.settings import SyncSettings
except ImportError:
    from infrastructure.codesys_bridge import CodeSysBridge
    from infrastructure.text_extractor import TextExtractor
    from infrastructure.st_formatter import StFormatter
    from infrastructure.file_storage import FileSystemStorage
    from services.export_service import ExportService
    from domain.settings import SyncSettings


_SETTINGS_FILENAME = '.cds-st-sync.json'


def main():
    """Entry point — called by CodeSys ScriptEngine."""
    print('=' * 50)
    print('  CDS_ST_SYNC — Export ST Code')
    print('=' * 50)
    print('')

    # ── Locate the sync directory ─────────────────────────────────────────
    sync_dir = _find_sync_dir()

    if not sync_dir:
        system.ui.error(
            'Sync directory not configured.\n'
            'Run Project_options first to set the sync directory.'
        )
        return

    print('Sync directory: {0}'.format(sync_dir))

    # ── Load settings ─────────────────────────────────────────────────────
    settings = _load_settings(sync_dir)
    filt = settings.filter

    print('Types: POU={pou}, GVL={gvl}, DUT={dut}, Interface={itf}'.format(
        pou=filt.include_pou,
        gvl=filt.include_gvl,
        dut=filt.include_dut,
        itf=filt.include_interface,
    ))
    print('')

    # ── Build services via DI ─────────────────────────────────────────────
    try:
        project = projects.primary
        bridge = CodeSysBridge(project)
    except Exception as exc:
        system.ui.error(
            'Could not access the CodeSys project.\n'
            'Error: {0}'.format(str(exc))
        )
        return

    extractor = TextExtractor()
    formatter = StFormatter()
    storage = FileSystemStorage(sync_dir)

    progress_lines = []

    def progress_callback(current, total, name):
        line = '  [{0}/{1}] {2}'.format(current, total, name)
        progress_lines.append(line)
        print(line)

    export_svc = ExportService(
        bridge,
        extractor,
        storage,
        formatter,
        progress_callback=progress_callback,
    )

    # ── Execute ───────────────────────────────────────────────────────────
    print('Exporting...')
    print('')

    result = export_svc.export(filt)

    # ── Report ────────────────────────────────────────────────────────────
    print('')
    print('─' * 50)
    print('Export finished.')
    print('  Total objects in project: {0}'.format(result.total))
    print('  Exported successfully:   {0}'.format(result.completed))

    if result.errors:
        print('  Errors:                  {0}'.format(len(result.errors)))
        for err in result.errors:
            print('    * {name}: {error}'.format(
                name=err.get('name', '?'),
                error=err.get('error', ''),
            ))

    manifest_path = os.path.join(sync_dir, 'manifest.json')
    print('  Manifest: {0}'.format(manifest_path))

    if result.success:
        system.ui.info(
            'Export completed!\n'
            'Objects: {0}\n'
            'Directory: {1}\n'
            'Manifest: manifest.json'.format(result.completed, sync_dir)
        )
    else:
        system.ui.error(
            'Export finished with errors.\n'
            'Succeeded: {0} / {1}\n'
            'Errors: {2}'.format(
                result.completed, result.total, len(result.errors))
        )


def _find_sync_dir():
    """Find the sync directory by searching for .cds-st-sync.json."""
    candidates = _candidate_dirs()

    for candidate_dir in candidates:
        settings_path = os.path.join(candidate_dir, _SETTINGS_FILENAME)
        if os.path.exists(settings_path):
            return candidate_dir

    if candidates:
        default_dir = candidates[0]
        sync_dir = os.path.join(default_dir, 'sync')
        settings_path = os.path.join(sync_dir, _SETTINGS_FILENAME)
        if os.path.exists(settings_path):
            return sync_dir

    return None


def _candidate_dirs():
    """Return candidate directories that might contain settings."""
    dirs = []
    try:
        proj_str = str(projects.primary)
        if ':' in proj_str:
            _, path_part = proj_str.split(':', 1)
            proj_path = path_part.strip()
            proj_dir = os.path.dirname(proj_path)
            if proj_dir and os.path.isabs(proj_dir):
                dirs.append(proj_dir)
    except Exception:
        pass

    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir not in dirs:
            dirs.append(script_dir)
    except Exception:
        pass

    return dirs


if __name__ == '__main__':
    main()
