# -*- coding: utf-8 -*-
from __future__ import print_function
"""
Project_options.py — configure CDS_ST_SYNC synchronisation settings.

Run from CodeSys: Tools → Scripting → Scripts → P → Project_options
Stores settings in .cds-st-sync.json.
"""

import os
import sys as _sys
import json

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

try:
    from src.domain.settings import SyncSettings
    from src.domain.filter import ObjectFilter
except ImportError:
    from domain.settings import SyncSettings
    from domain.filter import ObjectFilter


_SETTINGS_FILENAME = '.cds-st-sync.json'


def _choose_folder_dialog(title):
    """Open a folder browser dialog and return the selected path, or None."""
    try:
        import clr
        clr.AddReference('System.Windows.Forms')
        from System.Windows.Forms import FolderBrowserDialog, DialogResult
        dialog = FolderBrowserDialog()
        dialog.Description = title
        dialog.ShowNewFolderButton = True
        result = dialog.ShowDialog()
        if result == DialogResult.OK:
            return dialog.SelectedPath
    except Exception:
        pass
    return None


def _get_project_dir():
    """Return the directory containing the open CodeSys project, or None."""
    # 'projects' is a CodeSys global — access via __main__
    import __main__
    proj = getattr(__main__, 'projects', None)
    if proj is None:
        # Also try direct global access
        try:
            proj = projects
        except NameError:
            pass
    if proj is None:
        return None
    proj = proj.primary
    if proj is None:
        return None
    # Try direct .path attribute (most reliable)
    for attr in ('path', 'file_path', 'project_path', 'project_file'):
        val = getattr(proj, attr, None)
        if val and isinstance(val, (str, unicode)):
            d = os.path.dirname(val)
            if os.path.isdir(d):
                return d
    # Try get_project_info()
    try:
        info = proj.get_project_info()
        vals = getattr(info, 'values', info)
        for key in ('ProjectPath', 'FilePath', 'Path', 'project_path'):
            p = vals.get(key) if hasattr(vals, 'get') else getattr(vals, key, None)
            if p:
                p = str(p)
                if os.path.isfile(p):
                    return os.path.dirname(p)
                if os.path.isdir(p):
                    return p
    except Exception:
        pass
    return None


def _load_settings():
    """Read .cds-st-sync.json, or return defaults."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    proj_dir = _get_project_dir()
    for base in (proj_dir, script_dir, os.path.dirname(script_dir)):
        if base is None:
            continue
        path = os.path.join(base, _SETTINGS_FILENAME)
        if os.path.isfile(path):
            try:
                with open(path, 'r') as fh:
                    data = json.load(fh)
                return SyncSettings.from_dict(data)
            except Exception:
                pass
    return SyncSettings()


def _save_settings(settings):
    """Write .cds-st-sync.json next to the CodeSys project file."""
    proj_dir = _get_project_dir()
    if proj_dir is None:
        # Fallback: save next to scripts
        proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(proj_dir, _SETTINGS_FILENAME)
    data = settings.to_dict()
    with open(path, 'w') as fh:
        json.dump(data, fh, indent=2)


def main():
    """Entry point — called by CodeSys ScriptEngine."""
    print('=' * 50)
    print('  CDS_ST_SYNC — Configure Synchronisation')
    print('=' * 50)
    print('')

    settings = _load_settings()

    # 1. Sync directory
    current = settings.sync_dir or os.path.join(
        _get_project_dir() or os.getcwd(), 'sync'
    )
    new_dir = system.ui.query_string(
        'Sync directory path:\n'
        '(press OK to use default, or type a path)',
        current
    )
    if new_dir and new_dir.strip():
        settings.sync_dir = new_dir.strip()
    else:
        # Try folder browser
        folder = _choose_folder_dialog('Select sync directory')
        if folder:
            settings.sync_dir = folder

    # 2. Object types
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
        ]:
            ans = system.ui.prompt(
                'Include {0}?'.format(label),
                PromptChoice.YesNo,
                PromptResult.Yes
            )
            setattr(filt, attr, ans == PromptResult.Yes)
        settings.filter = filt

    # 3. Save
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


if __name__ == '__main__':
    main()
