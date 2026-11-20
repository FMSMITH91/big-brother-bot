# -*- coding: utf-8 -*-
"""
The health file: a small JSON document B3 rewrites every `health_interval` seconds (and when it starts and stops) so a
front-end can show "healthy" or the real reason without reading b3.log.

Written next to b3.ini by default (b3::health_file, "off" to disable), atomically (temporary file + rename), with the
process umask's permissions like b3.log: it never holds a password, an IP address or a player name. See README "Running B3 as a service".
"""

import datetime
import json
import logging
import os
import re
from secrets import token_hex
import threading
import time

import b3
import b3.functions

SCHEMA = 1
DEFAULT_INTERVAL = 60
MIN_INTERVAL = 5
# replies of the Quake 3 engine family to a wrong or missing RCON password
BAD_RCON_REPLIES = ('Bad rconpassword.', 'Invalid password.', 'No rconpassword set on the server.')
# the game log loop runs several times a second: no read for this long means it is stuck or stopped
READ_STALE_SECONDS = 120

_reIPv4 = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?\b')
_reIPv6 = re.compile(r'(?<![0-9A-Za-z:])(?=[0-9A-Fa-f:]*::|(?:[0-9A-Fa-f]{1,4}:){4})[0-9A-Fa-f]{0,4}(?::[0-9A-Fa-f]{0,4}){2,7}'
                     r'(?![0-9A-Za-z:])')
_reURL = re.compile(r'[a-z][a-z0-9+.-]*://\S+', re.IGNORECASE)


def utc_iso(timestamp):
    """
    Return a Unix time as ISO 8601 UTC ("2026-11-19T17:27:49Z"), or None.
    """
    if timestamp is None:
        return None
    return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sanitize(message, secrets=()):
    """
    Make a log message safe for the health file: one line, at most 300 characters, URL passwords, IP addresses and the
    given secrets replaced.
    """
    text = ' '.join(str(message).split())
    text = _reURL.sub(lambda m: b3.functions.hide_url_password(m.group(0)), text)
    for secret in secrets:
        if secret and len(secret) >= 3:
            text = text.replace(secret, '******')
    text = _reIPv4.sub('<ip>', text)
    text = _reIPv6.sub('<ip>', text)
    return text[:297] + '...' if len(text) > 300 else text


class _ErrorHandler(logging.Handler):
    """
    Keep the last ERROR (or CRITICAL) log record for the health file.
    """

    def __init__(self, health):
        logging.Handler.__init__(self, logging.ERROR)
        self.health = health

    def emit(self, record):
        try:
            self.health.record_error(record.getMessage())
        except Exception:
            pass  # never let the health file break logging


class Health(object):
    """
    Collects B3's state and writes the health file.
    """

    def __init__(self, console, path, interval=DEFAULT_INTERVAL):
        self.console = console
        self.path = path
        self.interval = max(MIN_INTERVAL, interval)
        self.lock = threading.Lock()
        self.state = 'starting'
        self.started_at = time.time()
        self.exit_code = None
        self.last_read_at = None
        self.last_line_at = None
        self.lines_parsed = 0
        self.rcon_ok = None
        self.rcon_last_ok_at = None
        self.rcon_last_error = None
        self.rcon_last_error_at = None
        self.last_error = None
        self.last_error_at = None
        self._stop = threading.Event()
        self._thread = None
        self._handler = _ErrorHandler(self)
        log = getattr(console, 'log', None)
        if isinstance(log, logging.Logger):
            log.addHandler(self._handler)

    # ---- recording ---------------------------------------------------------------------------------------------------

    def secrets(self):
        secrets = [getattr(self.console, '_rconPassword', None)]
        try:
            dsn = b3.functions.splitDSN(self.console.config.get('b3', 'database'))
            secrets.append(dsn.get('password') if dsn else None)
        except Exception:
            pass
        return [s for s in secrets if s]

    def record_read(self):
        first = self.last_read_at is None
        self.last_read_at = time.time()
        if first and self.state == 'running':
            self.write()  # do not report "not read" for a whole interval after the start

    def record_line(self):
        self.last_line_at = time.time()
        self.lines_parsed += 1

    def record_rcon(self, reply=None, error=None):
        """
        :param reply: what the game server answered (None: nothing to judge by)
        :param error: an exception raised while sending, or a message
        """
        now = time.time()
        before = self.rcon_ok
        with self.lock:
            if error is not None:
                self.rcon_ok = False
                self.rcon_last_error = sanitize(error, self.secrets()) or error.__class__.__name__
                self.rcon_last_error_at = now
            elif isinstance(reply, str) and reply.strip() in BAD_RCON_REPLIES:
                self.rcon_ok = False
                self.rcon_last_error = 'bad RCON password'
                self.rcon_last_error_at = now
            elif reply:
                self.rcon_ok = True
                self.rcon_last_ok_at = now
        if self.rcon_ok != before and self.state == 'running':
            self.write()  # a change of verdict is shown at once

    def record_error(self, message):
        with self.lock:
            self.last_error = sanitize(message, self.secrets())
            self.last_error_at = time.time()

    # ---- the document ------------------------------------------------------------------------------------------------

    def players(self):
        humans = bots = 0
        try:
            for c in self.console.clients.getList():
                if getattr(c, 'bot', False):
                    bots += 1
                else:
                    humans += 1
        except Exception:
            pass
        return humans, bots

    def database_ok(self):
        storage = getattr(self.console, 'storage', None)
        if storage is None:
            return None
        try:
            return bool(storage.status())
        except Exception:
            return False

    def snapshot(self):
        now = time.time()
        reading = self.last_read_at is not None and now - self.last_read_at < READ_STALE_SECONDS
        humans, bots = self.players()
        database = self.database_ok()
        commit = b3.getB3commit()

        if self.state != 'running':
            reason = {'starting': 'B3 is starting', 'stopped': 'B3 is stopped'}.get(self.state, self.state)
        elif not reading:
            reason = 'the game log is not being read'
        elif self.rcon_ok is False:
            reason = 'RCON: %s' % self.rcon_last_error
        elif database is False:
            reason = 'the database connection is lost'
        else:
            reason = None

        with self.lock:
            return {
                'schema': SCHEMA,
                'written_at': utc_iso(now),
                'healthy': reason is None,
                'reason': reason,
                'state': self.state,
                'exit_code': self.exit_code,
                'b3': {
                    'version': b3.__version__,
                    'commit': commit or None,
                    'parser': getattr(self.console, 'gameName', None),
                    'started_at': utc_iso(self.started_at),
                },
                'game_log': {
                    'ok': reading,
                    'last_read_at': utc_iso(self.last_read_at),
                    'last_line_at': utc_iso(self.last_line_at),
                    'lines_parsed': self.lines_parsed,
                },
                'rcon': {
                    'ok': self.rcon_ok,
                    'last_ok_at': utc_iso(self.rcon_last_ok_at),
                    'last_error': self.rcon_last_error,
                    'last_error_at': utc_iso(self.rcon_last_error_at),
                },
                'database': {'ok': database},
                'players': {'humans': humans, 'bots': bots},
                'last_error': {'message': self.last_error, 'at': utc_iso(self.last_error_at)} if self.last_error else None,
            }

    def write(self):
        """
        Write the health file atomically. Errors are logged at warning level, never raised.
        """
        try:
            data = json.dumps(self.snapshot(), indent=1, sort_keys=True)
            folder = os.path.dirname(self.path) or '.'
            tmp = os.path.join(folder, '.health.%s.tmp' % token_hex(8))
            # created like b3.log: the permissions come from the process umask (no chmod wider than that), O_EXCL so a
            # file or link planted under the temporary name is never written through
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
            fd = os.open(tmp, flags, 0o666)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(data + '\n')
                os.replace(tmp, self.path)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except Exception as e:
            try:
                self.console.warning('Could not write the health file %s: %s', self.path, e)
            except Exception:
                pass

    # ---- lifecycle ---------------------------------------------------------------------------------------------------

    def start(self):
        self.write()
        self._thread = threading.Thread(target=self._loop, name='b3-health', daemon=True)
        self._thread.start()

    def running(self):
        self.state = 'running'
        self.write()

    def _loop(self):
        while not self._stop.wait(self.interval):
            self.write()

    def stop(self, exit_code=None):
        if self.state == 'stopped':
            return
        self._stop.set()
        self.state = 'stopped'
        self.exit_code = exit_code if exit_code is not None else 0
        self.write()
        log = getattr(self.console, 'log', None)
        if isinstance(log, logging.Logger):
            log.removeHandler(self._handler)


def from_config(console):
    """
    Return a started Health for this console, or None when b3::health_file is "off".
    """
    config = console.config
    path = '@conf/health.json'
    if config.has_option('b3', 'health_file'):
        path = (config.get('b3', 'health_file') or '').strip()
        if path.lower() in ('', 'off', 'no', 'none', 'false', '0'):
            return None
    interval = DEFAULT_INTERVAL
    if config.has_option('b3', 'health_interval'):
        try:
            interval = int(config.get('b3', 'health_interval'))
        except ValueError:
            console.warning('b3::health_interval must be a number of seconds: using %s', DEFAULT_INTERVAL)
    health = Health(console, b3.getAbsolutePath(path, True), interval)
    health.start()
    return health
