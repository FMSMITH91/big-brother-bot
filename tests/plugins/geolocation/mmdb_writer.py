# -*- coding: utf-8 -*-
"""
A minimal MaxMind DB (.mmdb) writer for the tests: an IPv6 tree (IPv4 under ::/96), 24 bit records, and data made of
maps, short strings and unsigned integers. Format: https://maxmind.github.io/MaxMind-DB/
"""

import ipaddress
import struct

METADATA_MARKER = b'\xab\xcd\xefMaxMind.com'


class U32(int):
    """an integer always written as uint32 (libmaxminddb checks the metadata types)"""


class U64(int):
    """an integer always written as uint64"""


def _encode(value):
    if isinstance(value, dict):
        out = _ctrl(7, len(value))
        for k, v in value.items():
            out += _encode(str(k)) + _encode(v)
        return out
    if isinstance(value, (list, tuple)):
        return _ctrl(11, len(value)) + b''.join(_encode(v) for v in value)
    if isinstance(value, str):
        raw = value.encode('utf-8')
        return _ctrl(2, len(raw)) + raw
    if isinstance(value, int):
        raw = value.to_bytes((value.bit_length() + 7) // 8, 'big') if value else b''
        if isinstance(value, U64):
            kind = 9
        elif isinstance(value, U32):
            kind = 6
        else:
            kind = 5 if value < 1 << 16 else 6 if value < 1 << 32 else 9
        return _ctrl(kind, len(raw)) + raw
    raise TypeError(type(value))


def _ctrl(kind, size):
    assert size < 29, 'keep test values short'
    if kind <= 7:
        return bytes([(kind << 5) | size])
    return bytes([size, kind - 7])  # extended type


def write_mmdb(path, networks, database_type='DBIP-Country-Lite', build_epoch=1700000000):
    """
    :param networks: {'81.0.0.0/8': {...record...}, '2001:db8::/32': {...}}
    """
    data = b''
    root = [None, None]
    for cidr, record in networks.items():
        offset = len(data)
        data += _encode(record)
        net = ipaddress.ip_network(cidr)
        if net.version == 4:
            bits, length = int(net.network_address), 96 + net.prefixlen
        else:
            bits, length = int(net.network_address), net.prefixlen
        node = root
        for i in range(length):
            bit = (bits >> (127 - i)) & 1 if net.version == 6 else ((bits >> (31 - (i - 96))) & 1 if i >= 96 else 0)
            if i == length - 1:
                node[bit] = ('data', offset)
            else:
                if not isinstance(node[bit], list):
                    node[bit] = [None, None]
                node = node[bit]
    # number the nodes breadth first
    nodes, queue = [], [root]
    while queue:
        n = queue.pop(0)
        nodes.append(n)
        queue.extend(c for c in n if isinstance(c, list))
    index = {id(n): i for i, n in enumerate(nodes)}
    count = len(nodes)

    def record_value(child):
        if child is None:
            return count  # no data
        if isinstance(child, list):
            return index[id(child)]
        return count + 16 + child[1]

    tree = b''.join(struct.pack('>I', record_value(n[0]))[1:] + struct.pack('>I', record_value(n[1]))[1:]
                    for n in nodes)
    metadata = {
        'node_count': U32(count),
        'record_size': 24,
        'ip_version': 6,
        'database_type': database_type,
        'languages': ['en'],
        'binary_format_major_version': 2,
        'binary_format_minor_version': 0,
        'build_epoch': U64(build_epoch),
        'description': {'en': 'B3 test database'},
    }
    with open(path, 'wb') as f:
        f.write(tree + b'\x00' * 16 + data + METADATA_MARKER + _encode(metadata))
