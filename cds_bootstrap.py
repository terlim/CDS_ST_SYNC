# -*- coding: utf-8 -*-
from __future__ import print_function
"""Bootstrap loader for CDS_ST_SYNC scripts inside CodeSys.

Usage inside a script (e.g. scripts/Project_export.py):

    import os, sys
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, _PROJECT_ROOT)
    import cds_bootstrap  # noqa — this import is a no-op after sys.path is set

All script imports then resolve relative to the project root:
    from src.domain.models import ObjectMeta
    from src.services.export_service import ExportService
"""

import os
import sys


def _script_dir():
    """Return the absolute directory containing this bootstrap file."""
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()


def setup_path(root=None):
    """Add the project root to sys.path.

    Args:
        root: str or None. If None, auto-detect from this file's location.
              Scripts inside subdirectories MUST pass their own root.
    """
    if root is None:
        root = _script_dir()
    if root and root not in sys.path:
        sys.path.insert(0, root)
    # Also add the src/ directory as a fallback for direct imports
    src_dir = os.path.join(root, 'src')
    if os.path.isdir(src_dir) and src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    return root


# Ensure the project-root path is added when this module is first imported
# (best-effort; scripts should still set sys.path before importing us).
_root = _script_dir()
if _root not in sys.path:
    sys.path.insert(0, _root)
_src = os.path.join(_root, 'src')
if os.path.isdir(_src) and _src not in sys.path:
    sys.path.insert(0, _src)
