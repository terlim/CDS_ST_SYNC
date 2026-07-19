# -*- coding: utf-8 -*-
from __future__ import print_function

# ── Type-guid map: semantic kind → set of GUID strings (lowercase) ────

_TEXTUAL_TYPE_GUIDS = frozenset([
    # POU / Program / FunctionBlock / Function
    '6f9dac99-8de1-4efc-8465-68ac443b7d08',
    # GVL
    'ffbfa93a-b94d-45fc-a329-229860183b1d',
    # DUT
    '2db5b0c0-6a7b-4de7-b8c0-0c4bf1aee29c',
    # Interface
    '6654496c-404d-479a-aad2-8551054e5f1e',
    # Property
    '5a3b8626-d3e9-4f37-98b5-66420063d91e',
    # Method
    'f8a58466-d7f6-439f-bbb8-d4600e41d099',
    # Action
    'f89f7675-27f1-46b3-8abb-b7da8e774ffd',
    # Persistent Variables
    '3183921b-cc91-4712-9781-c3b6555122b5',
    '261bd6e6-249c-4232-bb6f-84c2fbeef430',
    # Task-local GVL
    'c2cda7a9-0ba4-4146-b563-22a42fa0eb72',
])

_TYPE_MAP = {
    'pou': frozenset([
        '6f9dac99-8de1-4efc-8465-68ac443b7d08',
        'f8a58466-d7f6-439f-bbb8-d4600e41d099',   # method
        'f89f7675-27f1-46b3-8abb-b7da8e774ffd',   # action
        '5a3b8626-d3e9-4f37-98b5-66420063d91e',   # property
    ]),
    'gvl': frozenset([
        'ffbfa93a-b94d-45fc-a329-229860183b1d',
    ]),
    'dut': frozenset([
        '2db5b0c0-6a7b-4de7-b8c0-0c4bf1aee29c',
    ]),
    'interface': frozenset([
        '6654496c-404d-479a-aad2-8551054e5f1e',
    ]),
    'persistent': frozenset([
        '3183921b-cc91-4712-9781-c3b6555122b5',
        '261bd6e6-249c-4232-bb6f-84c2fbeef430',
    ]),
    'task_local': frozenset([
        'c2cda7a9-0ba4-4146-b563-22a42fa0eb72',
    ]),
}


def is_textual_type(type_guid):
    """Return True if the given type_guid is a known textual CodeSys type.

    Args:
        type_guid: str – GUID with or without braces.
    """
    key = str(type_guid or '').strip('{}').lower()
    return key in _TEXTUAL_TYPE_GUIDS


def classify_type_guid(type_guid):
    """Return the semantic kind (str) for a type_guid, or None.

    Args:
        type_guid: str – GUID with or without braces.
    Returns:
        str: one of 'pou', 'gvl', 'dut', 'interface', 'persistent',
             'task_local', or None.
    """
    key = str(type_guid or '').strip('{}').lower()
    for kind, guid_set in _TYPE_MAP.items():
        if key in guid_set:
            return kind
    return None


class ObjectFilter(object):
    """Filter for selecting which CodeSys object types to include.

    Attributes:
        include_pou: bool – include Programs, FunctionBlocks, Functions.
        include_gvl: bool – include Global Variable Lists.
        include_dut: bool – include Data Unit Types (structs, enums, aliases).
        include_interface: bool – include Interfaces.
        include_persistent: bool – include Persistent Variable Lists.
        include_task_local: bool – include Task-local GVLs.
        specific_guids: list[str] or None – if set, only these GUIDs are
                        considered (overrides type filters). None = all.
    """

    def __init__(self, include_pou=True, include_gvl=True, include_dut=True,
                 include_interface=True, include_persistent=False,
                 include_task_local=False, specific_guids=None):
        self.include_pou = include_pou
        self.include_gvl = include_gvl
        self.include_dut = include_dut
        self.include_interface = include_interface
        self.include_persistent = include_persistent
        self.include_task_local = include_task_local
        self.specific_guids = specific_guids  # None or list[str]

    def matches(self, meta):
        """Return True if the ObjectMeta passes this filter.

        Args:
            meta: ObjectMeta
        """
        # specific_guids takes priority
        if self.specific_guids is not None:
            return meta.guid in self.specific_guids

        obj_type = str(meta.type or '').lower()
        mapping = {
            'pou': self.include_pou,
            'gvl': self.include_gvl,
            'dut': self.include_dut,
            'interface': self.include_interface,
            'persistent': self.include_persistent,
            'task_local': self.include_task_local,
        }
        return bool(mapping.get(obj_type, False))

    @classmethod
    def all_on(cls):
        """Return a filter with everything enabled (including persistent)."""
        return cls(
            include_pou=True,
            include_gvl=True,
            include_dut=True,
            include_interface=True,
            include_persistent=True,
            include_task_local=True,
        )

    def __repr__(self):
        flags = ', '.join(
            '{}={}'.format(k, getattr(self, k))
            for k in ('include_pou', 'include_gvl', 'include_dut',
                      'include_interface', 'include_persistent',
                      'include_task_local')
        )
        return 'ObjectFilter({0})'.format(flags)
