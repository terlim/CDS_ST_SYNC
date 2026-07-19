# -*- coding: utf-8 -*-
from __future__ import print_function
"""
Project_options.py — configure CDS_ST_SYNC synchronisation settings.

Run from CodeSys: Tools → Scripting → Scripts → P → Project_options
Stores settings in .cds-st-sync.json inside the configured sync directory.
"""

import os
import sys as _sys
import json

# ── Resolve project root ──────────────────────────────────────────
# __file__ → .../CDS_ST_SYNC/scripts/Project_options.py (go up 2)
# Fallback: may be directly in project root if copied flat.
_script_file = os.path.abspath(__file__)
_project_root = os.path.dirname(os.path.dirname(_script_file))
if not os.path.isfile(os.path.join(_project_root, 'cds_bootstrap.py')):
    _project_root = os.path.dirname(_script_file)

# Add project root + src/ to sys.path
if _project_root not in _sys.path:
    _sys.path.insert(0, _project_root)
_src = os.path.join(_project_root, 'src')
if os.path.isdir(_src) and _src not in _sys.path:
    _sys.path.insert(0, _src)

import cds_bootstrap  # noqa

# Import from src/ — fall back to bare package if src/ was added directly
try:
    from src.domain.settings import SyncSettings
    from src.domain.filter import ObjectFilter
except ImportError:
    from domain.settings import SyncSettings
    from domain.filter import ObjectFilter


_SETTINGS_FILENAME = '.cds-st-sync.json'


def main():
    """Entry point — called by CodeSys ScriptEngine."""
    print('=' * 50)
    print('  CDS_ST_SYNC — Configure Synchronisation')
    print('=' * 50)
    print('')

    settings = _load_settings()

    # 1. Sync directory
    current = settings.sync_dir or os.path.dirname(
        str(projects.primary).replace('Project: ', '')
    )
    new_dir = system.ui.query_string(
        'Sync directory (relative to project folder):',
        current
    )
    if new_dir and new_dir.strip():
        settings.sync_dir = new_dir.strip()

    # 2. Object types — quick or detailed
    choice = system.ui.prompt(
        'Export object types:\n'
        '  Yes = ALL textual types (POU, GVL, DUT, Interface)\n'
        '  No  = choose individually',
        PromptChoice.YesNo,
        PromptResult.Yes
    )

    if choice == PromptResult.Yes:
        settings.filter = ObjectFilter.all_on()
    else:
        filt = ObjectFilter()
        for label, attr in [
            ('POU (Programs, Function Blocks, Functions)', 'include_pou'),
            ('GVL (Global Variable Lists)', 'include_gvl'),
            ('DUT (Data Unit Types)', 'include_dut'),
            ('Interface', 'include_interface'),
            ('Persistent Variables', 'include_persistent'),
            ('Task-local GVL', 'include_task_local'),
        ]:
            ans = system.ui.prompt(
                'Include {0}?'.format(label),
                PromptChoice.YesNo,
                PromptResult.Yes
            )
            setattr(filt, attr, ans == PromptResult.Yes)
        settings.filter = filt

    # 3. Summary
    _save_settings(settings)
    msg = (
        'Settings saved.\n\n'
        'Sync directory: {0}\n'
        'Object filter: POU={1}, GVL={2}, DUT={3}, Interface={4}'
    ).format(
        settings.sync_dir,
        settings.filter.include_pou,
        settings.filter.include_gvl,
        settings.filter.include_dut,
        settings.filter.include_interface,
    )
    system.ui.info(msg)


def _load_settings():
    """Read .cds-st-sync.json from the project folder, or return defaults."""
    try:
        proj_path = str(projects.primary)
        proj_dir = os.path.dirname(proj_path.replace('Project: ', ''))
    except Exception:
        proj_dir = os.getcwd()

    path = os.path.join(proj_dir, _SETTINGS_FILENAME)
    if os.path.isfile(path):
        try:
            with open(path, 'r') as fh:
                data = json.load(fh)
            return SyncSettings.from_dict(data)
        except Exception:
            pass
    return SyncSettings()


def _save_settings(settings):
    """Write .cds-st-sync.json to the project folder."""
    try:
        proj_path = str(projects.primary)
        proj_dir = os.path.dirname(proj_path.replace('Project: ', ''))
    except Exception:
        proj_dir = os.getcwd()

    if not os.path.isdir(proj_dir):
        os.makedirs(proj_dir)

    path = os.path.join(proj_dir, _SETTINGS_FILENAME)
    data = settings.to_dict()
    with open(path, 'w') as fh:
        json.dump(data, fh, indent=2)


if __name__ == '__main__':
    main()
