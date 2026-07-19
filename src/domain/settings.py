# -*- coding: utf-8 -*-
from __future__ import print_function

from .filter import ObjectFilter


class SyncSettings(object):
    """Persistent synchronisation settings.

    Stored as .cds-st-sync.json (CodeSys side) or QSettings (GUI side).

    Attributes:
        sync_dir: str – absolute or relative path to the sync root.
        filter: ObjectFilter – which object types to include.
        pipe_name: str – Named Pipe name.
        pipe_timeout: int – connection timeout in seconds.
        live_sync_enabled: bool – start live-sync on connect.
        poll_interval: int – daemon poll interval in seconds.
        conflict_strategy: str – 'last_write_wins'.
    """

    DEFAULT_PIPE_NAME = 'cds-st-sync-default'
    DEFAULT_PIPE_TIMEOUT = 30
    DEFAULT_POLL_INTERVAL = 2

    def __init__(self, sync_dir='', filter_obj=None,
                 pipe_name=None, pipe_timeout=None,
                 live_sync_enabled=False, poll_interval=None,
                 conflict_strategy='last_write_wins'):
        self.sync_dir = sync_dir or './sync/'
        self.filter = filter_obj if filter_obj is not None else ObjectFilter()
        self.pipe_name = pipe_name or self.DEFAULT_PIPE_NAME
        self.pipe_timeout = (
            pipe_timeout if pipe_timeout is not None
            else self.DEFAULT_PIPE_TIMEOUT
        )
        self.live_sync_enabled = bool(live_sync_enabled)
        self.poll_interval = (
            poll_interval if poll_interval is not None
            else self.DEFAULT_POLL_INTERVAL
        )
        self.conflict_strategy = conflict_strategy or 'last_write_wins'

    # ── serialisation ─────────────────────────────────────────────────

    def to_dict(self):
        """Return a JSON-serialisable dict."""
        return {
            'sync_dir': self.sync_dir,
            'filter': {
                'include_pou': self.filter.include_pou,
                'include_gvl': self.filter.include_gvl,
                'include_dut': self.filter.include_dut,
                'include_interface': self.filter.include_interface,
                'include_persistent': self.filter.include_persistent,
                'include_task_local': self.filter.include_task_local,
            },
            'pipe_name': self.pipe_name,
            'pipe_timeout': self.pipe_timeout,
            'live_sync_enabled': self.live_sync_enabled,
            'poll_interval': self.poll_interval,
            'conflict_strategy': self.conflict_strategy,
        }

    @classmethod
    def from_dict(cls, data):
        """Create SyncSettings from a JSON-loaded dict."""
        filter_data = data.get('filter', {})
        filter_obj = ObjectFilter(
            include_pou=filter_data.get('include_pou', True),
            include_gvl=filter_data.get('include_gvl', True),
            include_dut=filter_data.get('include_dut', True),
            include_interface=filter_data.get('include_interface', True),
            include_persistent=filter_data.get('include_persistent', False),
            include_task_local=filter_data.get('include_task_local', False),
        )
        return cls(
            sync_dir=data.get('sync_dir', './sync/'),
            filter_obj=filter_obj,
            pipe_name=data.get('pipe_name'),
            pipe_timeout=data.get('pipe_timeout'),
            live_sync_enabled=data.get('live_sync_enabled', False),
            poll_interval=data.get('poll_interval'),
            conflict_strategy=data.get('conflict_strategy', 'last_write_wins'),
        )

    def __repr__(self):
        return ('SyncSettings(sync_dir={0!r}, pipe={1!r}, '
                'live_sync={2})').format(
            self.sync_dir, self.pipe_name, self.live_sync_enabled)
