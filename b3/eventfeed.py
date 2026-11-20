# -*- coding: utf-8 -*-
"""
The event feed: one JSON line per penalty and admin command in events.jsonl (next to b3.ini by default), so a control
panel can raise alerts and keep an audit trail without reading b3.log or B3's tables.

b3::events_file (path, "off" to disable), b3::events_max_size (default 1MB: then events.jsonl becomes events.jsonl.1,
one copy kept), b3::events_file_mode (default 640). No IP address, guid or password is ever written; the arguments of
commands are kept only for the admin commands of ARGS_KEPT (null for rcon, cvar setters, password commands...), and the
configured RCON and database passwords are replaced in every text field.
"""

import datetime
import json
import os
import threading

import b3
import b3.functions
from b3.health import DEFAULT_MODE, parse_mode

SCHEMA = 1
DEFAULT_MAX_SIZE = 1024 * 1024
MIN_MAX_SIZE = 16 * 1024
MAX_TEXT = 200

EVENTS = {
    'EVT_CLIENT_BAN': 'ban',
    'EVT_CLIENT_BAN_TEMP': 'tempban',
    'EVT_CLIENT_UNBAN': 'unban',
    'EVT_CLIENT_KICK': 'kick',
    'EVT_CLIENT_WARN': 'warn',
    'EVT_ADMIN_COMMAND': 'admin_command',
}


# admin commands whose arguments are kept in the feed (an allow-list: a player name, a reason, a duration, a group, a
# map). Any other command (rcon, cvar setters, password commands, plugin commands...) gets "args": null.
ARGS_KEPT = frozenset((
    'ban', 'b', 'permban', 'pb', 'tempban', 'tb', 'kick', 'k', 'kickall', 'warn', 'w', 'warnclear', 'wc',
    'warnremove', 'wr', 'warntest', 'warninfo', 'wi', 'unban', 'clear', 'kcl', 'notice', 'spank', 'spankall', 'slap',
    'nuke', 'mute', 'kill', 'putgroup', 'ungroup', 'mask', 'unmask', 'map', 'maprotate', 'nextmap', 'lookup', 'l',
    'find', 'aliases', 'alias', 'seen', 'leveltest', 'lt', 'admins', 'list', 'status', 'help', 'h', 'baninfo', 'bi',
    'lastbans', 'time', 'iamgod', 'regtest', 'rules', 'r', 'scream', 'say', 'longlist', 'poke', 'spam', 'pause',
))


def _keeps_args(name):
    return (name or '').lower() in ARGS_KEPT


class EventFeed(object):

    def __init__(self, console, path, max_size=DEFAULT_MAX_SIZE, mode=DEFAULT_MODE):
        self.console = console
        self.path = path
        self.max_size = max(MIN_MAX_SIZE, max_size)
        self.mode = mode & 0o666
        self.lock = threading.Lock()

    # ---- building a line ---------------------------------------------------------------------------------------------

    def secrets(self):
        """
        The configured RCON and database passwords: replaced in every text field as a backstop.
        """
        found = [getattr(self.console, '_rconPassword', None)]
        try:
            dsn = b3.functions.splitDSN(self.console.config.get('b3', 'database'))
            found.append(dsn.get('password') if dsn else None)
        except Exception:
            pass
        return [s for s in found if s and len(s) >= 3]

    def text(self, value):
        if value is None:
            return None
        text = ' '.join(self.console.stripColors(str(value)).split())
        for secret in self.secrets():
            text = text.replace(secret, '******')
        return text[:MAX_TEXT]

    def person(self, client):
        """
        {"id": database id, "cid": slot, "name": clean name}: never the IP or the guid.
        """
        if client is None or not hasattr(client, 'cid'):
            return None
        return {'id': getattr(client, 'id', None) or None, 'cid': getattr(client, 'cid', None),
                'name': self.text(getattr(client, 'name', None))}

    def line(self, event_name, event):
        kind = EVENTS[event_name]
        data = event.data
        doc = {'schema': SCHEMA, 'event': kind, 'time': datetime.datetime.now(datetime.timezone.utc)
               .strftime('%Y-%m-%dT%H:%M:%SZ'), 'target': None, 'admin': None, 'reason': None,
               'duration_minutes': None}

        if kind == 'admin_command':
            doc['admin'] = self.person(event.client)
            command, args = (data[0], data[1]) if isinstance(data, (tuple, list)) and len(data) >= 2 else (None, None)
            name = getattr(command, 'command', None)
            doc['command'] = name
            doc['args'] = self.text(args) if _keeps_args(name) else None
            return doc

        doc['target'] = self.person(event.client)
        if isinstance(data, dict):
            doc['reason'] = self.text(data.get('reason'))
            doc['admin'] = self.person(data.get('admin'))
            duration = data.get('duration')
            if duration is not None:
                try:
                    doc['duration_minutes'] = int(b3.functions.time2minutes(duration))
                except Exception:
                    doc['duration_minutes'] = None
        elif hasattr(data, 'cid'):
            doc['admin'] = self.person(data)  # some parsers pass the admin as the unban data
        elif data:
            doc['reason'] = self.text(data)
        return doc

    # ---- writing -----------------------------------------------------------------------------------------------------

    def handle(self, event):
        """
        Write the event when it is one of EVENTS. Never raises.
        """
        try:
            event_name = self.console.getEventKey(event.type)
        except Exception:
            return
        if event_name not in EVENTS:
            return
        try:
            self.append(json.dumps(self.line(event_name, event), sort_keys=True, ensure_ascii=False))
        except Exception as e:
            try:
                self.console.warning('Could not write to the event feed %s: %s', self.path, e)
            except Exception:
                pass

    def record(self, kind, **fields):
        """
        A line for a B3 event of its own (config_reload...). Never raises.
        """
        doc = dict(fields, schema=SCHEMA, event=kind,
                   time=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        try:
            self.append(json.dumps(doc, sort_keys=True, ensure_ascii=False))
        except Exception as e:
            try:
                self.console.warning('Could not write to the event feed %s: %s', self.path, e)
            except Exception:
                pass

    def control(self, cmd, args, ok, error=None, actor=None):
        """
        A line for a control socket request (b3/control.py), refused ones included. actor is the caller's own label,
        not checked by B3.
        """
        args = {k: self.text(v) if isinstance(v, str) else v for k, v in (args or {}).items()}
        doc = {'schema': SCHEMA, 'event': 'control_command', 'time': datetime.datetime.now(datetime.timezone.utc)
               .strftime('%Y-%m-%dT%H:%M:%SZ'), 'command': cmd, 'args': args, 'ok': bool(ok), 'error': error,
               'actor': actor}
        try:
            self.append(json.dumps(doc, sort_keys=True, ensure_ascii=False))
        except Exception as e:
            try:
                self.console.warning('Could not write to the event feed %s: %s', self.path, e)
            except Exception:
                pass

    def append(self, text):
        data = (text + '\n').encode('utf-8')
        with self.lock:
            try:
                if os.path.getsize(self.path) + len(data) > self.max_size:
                    os.replace(self.path, self.path + '.1')
            except FileNotFoundError:
                pass
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, 'O_NOFOLLOW', 0)
            fd = os.open(self.path, flags, self.mode)
            try:
                os.write(fd, data)
            finally:
                os.close(fd)


def from_config(console):
    """
    Return the EventFeed for this console, or None when b3::events_file is "off".
    """
    config = console.config
    path = '@conf/events.jsonl'
    if config.has_option('b3', 'events_file'):
        path = (config.get('b3', 'events_file') or '').strip()
        if path.lower() in ('', 'off', 'no', 'none', 'false', '0'):
            return None
    max_size = DEFAULT_MAX_SIZE
    if config.has_option('b3', 'events_max_size'):
        try:
            max_size = b3.functions.getBytes(config.get('b3', 'events_max_size'))
        except (TypeError, ValueError):
            console.warning('b3::events_max_size must be a size such as 1MB: using 1MB')
    mode = DEFAULT_MODE
    if config.has_option('b3', 'events_file_mode'):
        try:
            mode = parse_mode(config.get('b3', 'events_file_mode'))
        except ValueError:
            console.warning('b3::events_file_mode must be an octal mode such as 640: using %o', DEFAULT_MODE)
    return EventFeed(console, b3.getAbsolutePath(path, True), max_size, mode)
