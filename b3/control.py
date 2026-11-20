# -*- coding: utf-8 -*-
"""
The local control socket: a Unix socket (never a network listener) through which a control panel running as the same
account asks B3 to act, so it does not edit B3's tables behind its back.

Off by default: b3::control_socket names the socket (e.g. @conf/b3.sock). The socket is mode 0600 and B3 also checks the
peer's uid (SO_PEERCRED, Linux) is its own. One JSON request per connection, at most 4 KB, answered with one JSON line:

    {"id": 7, "cmd": "unban", "args": {"client_id": 12, "reason": "appeal accepted"}}
    {"id": 7, "ok": true, "result": {...}}  /  {"id": 7, "ok": false, "error": "invalid_args", "message": "..."}

Commands (an allow-list; every argument is validated, unknown fields are refused, nothing is half-done):
    ping                                      -> {"version", "commit"}
    list_penalties  client_id                 -> {"penalties": [...]} (active ones: bans, tempbans, warnings, kicks, notices)
    unban           client_id, reason?        -> {"client_id", "bans_lifted"}
    kick            cid, reason?              -> {"cid", "client_id"}
    warn            cid, reason               -> {"cid", "client_id"}
    reload_plugins                            -> {"reloaded": [...], "failed": {name: reason}}
Every request is logged in b3.log and in the event feed (control_command), refused ones included.
"""

import json
import os
import re
import socket
import stat
import struct
import sys
import threading

import b3

MAX_REQUEST = 4096
TIMEOUT = 5.0
MAX_REASON = 100
_reCID = re.compile(r'[0-9]{1,3}')


class Refused(Exception):
    def __init__(self, error, message):
        Exception.__init__(self, message)
        self.error = error
        self.message = message


def _reason(value, required=False):
    """
    A reason: a string of at most 100 printable characters (no control character, no colour code).
    """
    if value is None or value == '':
        if required:
            raise Refused('invalid_args', 'reason is required')
        return ''
    if not isinstance(value, str):
        raise Refused('invalid_args', 'reason must be a string')
    if len(value) > MAX_REASON:
        raise Refused('invalid_args', 'reason is longer than %s characters' % MAX_REASON)
    if any(ord(c) < 32 or ord(c) == 127 for c in value) or '^' in value:
        raise Refused('invalid_args', 'reason has control characters or colour codes')
    return value.strip()


def _client_id(value):
    # bool is an int in Python: refuse it explicitly
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value < 2 ** 31:
        raise Refused('invalid_args', 'client_id must be a positive integer')
    return value


def _cid(value):
    if not isinstance(value, str) or not _reCID.fullmatch(value):
        raise Refused('invalid_args', 'cid must be a slot number as a string, e.g. "3"')
    return value


# command -> {argument: (validator, required)}
SCHEMA = {
    'ping': {},
    'reload_plugins': {},
    'list_penalties': {'client_id': (_client_id, True)},
    'unban': {'client_id': (_client_id, True), 'reason': (_reason, False)},
    'kick': {'cid': (_cid, True), 'reason': (_reason, False)},
    'warn': {'cid': (_cid, True), 'reason': (lambda v: _reason(v, True), True)},
}


def parse_request(raw):
    """
    Parse and validate a request.
    :return: (id, cmd, args) with validated args
    :raise Refused: on anything that is not exactly a valid request
    """
    if len(raw) > MAX_REQUEST:
        raise Refused('too_large', 'requests are limited to %s bytes' % MAX_REQUEST)
    try:
        req = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        raise Refused('bad_json', 'the request is not a JSON object')
    if not isinstance(req, dict):
        raise Refused('bad_json', 'the request is not a JSON object')
    unknown = set(req) - {'id', 'cmd', 'args'}
    if unknown:
        raise Refused('invalid_request', 'unknown fields: %s' % ', '.join(sorted(unknown)))
    rid = req.get('id')
    if rid is not None and (isinstance(rid, bool) or not isinstance(rid, (int, str)) or
                            (isinstance(rid, str) and len(rid) > 64)):
        raise Refused('invalid_request', 'id must be an integer or a short string')
    cmd = req.get('cmd')
    if not isinstance(cmd, str) or cmd not in SCHEMA:
        raise Refused('unknown_command', 'cmd must be one of: %s' % ', '.join(sorted(SCHEMA)))
    args = req.get('args', {})
    if not isinstance(args, dict):
        raise Refused('invalid_args', 'args must be an object')
    spec = SCHEMA[cmd]
    unknown = set(args) - set(spec)
    if unknown:
        raise Refused('invalid_args', 'unknown arguments: %s' % ', '.join(sorted(unknown)))
    clean = {}
    for name, (check, required) in spec.items():
        if name not in args:
            if required:
                raise Refused('invalid_args', '%s is required' % name)
            continue
        clean[name] = check(args[name])
    return rid, cmd, clean


def peer_uid(conn):
    """
    The uid of the process on the other end (Linux SO_PEERCRED), or None where the platform cannot tell.
    """
    if not hasattr(socket, 'SO_PEERCRED'):
        return None
    creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i'))
    return struct.unpack('3i', creds)[1]


class ControlServer(object):

    def __init__(self, console, path):
        self.console = console
        self.path = path
        self.sock = None
        self.thread = None
        self.running = False

    # ---- lifecycle ---------------------------------------------------------------------------------------------------

    def start(self):
        if not hasattr(socket, 'AF_UNIX'):
            self.console.warning('Control socket: Unix sockets are not available on this platform: not started')
            return False
        try:
            st = os.lstat(self.path)
        except FileNotFoundError:
            pass
        else:
            if not stat.S_ISSOCK(st.st_mode):
                self.console.error('Control socket: %s exists and is not a socket: not started', self.path)
                return False
            os.unlink(self.path)  # a socket left by a previous run
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        old = os.umask(0o177)  # the socket file is created 0600: only this account can connect
        try:
            sock.bind(self.path)
        finally:
            os.umask(old)
        os.chmod(self.path, 0o600)
        sock.listen(4)
        sock.settimeout(1.0)
        self.sock = sock
        self.running = True
        self.thread = threading.Thread(target=self._loop, name='b3-control', daemon=True)
        self.thread.start()
        self.console.bot('Control socket listening on %s (mode 0600, own account only)', self.path)
        return True

    def stop(self):
        self.running = False
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None
            try:
                if stat.S_ISSOCK(os.lstat(self.path).st_mode):
                    os.unlink(self.path)
            except OSError:
                pass

    def _loop(self):
        while self.running:
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                try:
                    self.serve(conn)
                except Exception as e:
                    self.console.error('Control socket: %s', e)

    # ---- one connection ----------------------------------------------------------------------------------------------

    def serve(self, conn):
        conn.settimeout(TIMEOUT)
        uid = peer_uid(conn)
        if uid is not None and uid != os.getuid():
            self.audit(None, None, None, False, 'forbidden', uid)
            self.reply(conn, None, error=Refused('forbidden', 'only the account running B3 may use this socket'))
            return
        raw = b''
        while len(raw) <= MAX_REQUEST and not raw.endswith(b'\n'):
            chunk = conn.recv(1024)
            if not chunk:
                break
            raw += chunk
        try:
            rid, cmd, args = parse_request(raw.strip())
        except Refused as e:
            self.audit(None, None, None, False, e.error, uid)
            self.reply(conn, None, error=e)
            return
        try:
            result = self.run(cmd, args)
        except Refused as e:
            self.audit(cmd, args, rid, False, e.error, uid)
            self.reply(conn, rid, error=e)
            return
        except Exception as e:
            self.audit(cmd, args, rid, False, 'failed', uid)
            self.reply(conn, rid, error=Refused('failed', 'the command failed: %s' % e.__class__.__name__))
            raise
        self.audit(cmd, args, rid, True, None, uid)
        self.reply(conn, rid, result=result)

    def reply(self, conn, rid, result=None, error=None):
        doc = {'id': rid, 'ok': error is None}
        if error is None:
            doc['result'] = result
        else:
            doc['error'] = error.error
            doc['message'] = error.message
        try:
            conn.sendall((json.dumps(doc, sort_keys=True) + '\n').encode('utf-8'))
        except OSError:
            pass

    def audit(self, cmd, args, rid, ok, error, uid):
        """
        Log every request (OWASP Logging Cheat Sheet: admin actions and validation/authorization failures).
        """
        shown = json.dumps(args, sort_keys=True) if args else '{}'
        self.console.bot('Control socket: %s %s (uid %s): %s', cmd or '(refused request)', shown, uid,
                         'ok' if ok else 'refused: %s' % error)
        feed = getattr(self.console, 'eventFeed', None)
        if feed:
            feed.control(cmd, args, ok, error)

    # ---- the commands ------------------------------------------------------------------------------------------------

    def run(self, cmd, args):
        return getattr(self, 'cmd_' + cmd)(**args)

    def cmd_ping(self):
        return {'version': b3.__version__, 'commit': b3.getB3commit() or None}

    def cmd_reload_plugins(self):
        return self.console.reloadPluginConfigs()

    def stored_client(self, client_id):
        from b3.clients import Client
        client = Client(console=self.console, id=client_id)
        try:
            self.console.storage.getClient(client)
        except KeyError:
            raise Refused('not_found', 'no client with id %s' % client_id)
        return client

    def connected_client(self, cid):
        client = self.console.clients.getByCID(cid)
        if client is None or client.hide:
            raise Refused('not_found', 'no player on slot %s' % cid)
        return client

    def cmd_list_penalties(self, client_id):
        client = self.stored_client(client_id)
        penalties = []
        for kind in ('Ban', 'TempBan', 'Warning', 'Kick', 'Notice'):
            for p in self.console.storage.getClientPenalties(client, type=kind):
                penalties.append({'id': p.id, 'type': p.type, 'reason': self.console.stripColors(p.reason or ''),
                                  'keyword': p.keyword or None, 'admin_id': p.adminId or None,
                                  'time_add': p.timeAdd, 'time_expire': p.timeExpire, 'duration': p.duration})
        penalties.sort(key=lambda p: p['time_add'], reverse=True)
        return {'client_id': client_id, 'penalties': penalties}

    def cmd_unban(self, client_id, reason=''):
        client = self.stored_client(client_id)
        bans = client.bans
        client.unban(reason or 'unbanned from the control panel', admin=None, silent=True)
        return {'client_id': client_id, 'bans_lifted': len(bans)}

    def cmd_kick(self, cid, reason=''):
        client = self.connected_client(cid)
        client.kick(reason, keyword='control', admin=None, silent=False)
        return {'cid': cid, 'client_id': client.id or None}

    def cmd_warn(self, cid, reason):
        client = self.connected_client(cid)
        admin_plugin = self.console.getPlugin('admin')
        if admin_plugin is not None and hasattr(admin_plugin, 'warnClient'):
            admin_plugin.warnClient(client, reason, admin=None)
        else:
            client.warn(60, reason, keyword='control', admin=None)
        return {'cid': cid, 'client_id': client.id or None}


def from_config(console):
    """
    Return a started ControlServer, or None when b3::control_socket is not set (the default) or "off".
    """
    config = console.config
    if not config.has_option('b3', 'control_socket'):
        return None
    path = (config.get('b3', 'control_socket') or '').strip()
    if path.lower() in ('', 'off', 'no', 'none', 'false', '0'):
        return None
    if sys.platform == 'win32':
        console.warning('Control socket: not available on Windows')
        return None
    server = ControlServer(console, b3.getAbsolutePath(path, True))
    try:
        if not server.start():
            return None
    except OSError as e:
        console.error('Control socket: cannot listen on %s: %s', server.path, e)
        return None
    return server
