# -*- coding: utf-8 -*-
"""
b3 --check-config: validate b3.ini and the plugin configuration files without connecting to the game server or the
database, so a front-end can refuse a bad setting before it restarts B3.

Output: "OK: <file>" and exit status 0, or one "ERROR: <reason>" line per problem (the first is the main reason) and
exit status b3.exitcodes.CONFIG (230).
"""

import glob
import os
import sys

import b3
import b3.config
import b3.exitcodes
import b3.functions
from b3.health import parse_mode


def _plugin_class(name, path, external_dir):
    """
    Import the plugin module the way Parser.pluginImport does and return its class.
    """
    if path:
        mod = b3.functions.load_module_from_paths(name, [b3.getAbsolutePath(path, True)])
    else:
        try:
            mod = b3.functions.load_module_from_paths(name, [os.path.join(b3.getB3Path(True), 'plugins')])
        except ImportError:
            mod = b3.functions.load_module_from_paths(name, [external_dir])
    return getattr(mod, '%sPlugin' % name.title())


def _check_plugin(p, external_dir):
    """
    Return the problems found for one [plugins] entry.
    """
    name = p['name']
    try:
        clazz = _plugin_class(name, p['path'], external_dir)
    except Exception as e:
        return ['plugin %s cannot be loaded: %s' % (name, e)]

    conf = p['conf']
    if conf:
        path = b3.getAbsolutePath(conf, True)
        if not os.path.isfile(path):
            if clazz.requiresConfigFile:
                return ['plugin %s: configuration file not found: %s' % (name, path)]
            return []
        try:
            b3.config.load(path)
        except Exception as e:
            return ['plugin %s: invalid configuration file %s: %s' % (name, path, e)]
        return []

    if clazz.requiresConfigFile:
        # B3 then looks for a file named after the plugin in @conf, then in the external plugin directory
        found = glob.glob(os.path.join(b3.getAbsolutePath('@conf', True), '*%s*' % name))
        if external_dir:
            found += glob.glob(os.path.join(b3.getAbsolutePath(external_dir, True), name, 'conf', '*%s*' % name))
        if not found:
            return ['plugin %s needs a configuration file and none is set or found' % name]
    return []


def check_config(filename):
    """
    Validate a B3 main configuration file and the plugin configuration files it names.
    :param filename: path of b3.ini (or b3.xml)
    :return: a list of problems, empty when the configuration is valid
    """
    path = b3.getAbsolutePath(filename, True)
    if not os.path.isfile(path):
        return ['configuration file not found: %s' % path]
    try:
        config = b3.config.MainConfig(b3.config.load(path))
    except Exception as e:
        return ['cannot read %s: %s' % (path, e)]

    # the paths in the plugin settings (@conf) are relative to the main configuration file
    b3.confdir = os.path.dirname(path)

    problems = list(config.analyze())

    # read without a default when B3 starts: missing, B3 stops with a traceback
    for section, option in (('b3', 'bot_prefix'), ('b3', 'logfile'), ('b3', 'log_level'), ('b3', 'time_format'),
                            ('server', 'port')):
        if not config.has_option(section, option):
            problems.append('missing configuration value %s::%s' % (section, option))

    def _typed(section, option, cast, kind):
        if config.has_option(section, option):
            value = config.get(section, option)
            try:
                cast(value)
            except (TypeError, ValueError):
                problems.append('%s::%s must be %s (found %r)' % (section, option, kind, value))

    _typed('b3', 'log_level', int, 'a number')
    _typed('b3', 'logsize', b3.functions.getBytes, 'a size such as 10MB')
    _typed('b3', 'health_interval', int, 'a number of seconds')
    _typed('b3', 'purge_aliases_days', int, 'a number of days (0 or empty: off)')
    _typed('b3', 'events_max_size', b3.functions.getBytes, 'a size such as 1MB')
    _typed('b3', 'events_file_mode', parse_mode, 'an octal mode such as 640 (read/write bits only)')
    _typed('b3', 'health_file_mode', parse_mode, 'an octal mode such as 640 (read/write bits only)')
    _typed('server', 'port', int, 'a port number')
    _typed('server', 'rcon_port', int, 'a port number')
    _typed('server', 'rcon_timeout', float, 'a number of seconds')

    if config.has_option('b3', 'control_socket'):
        sock = (config.get('b3', 'control_socket') or '').strip()
        if sock.lower() not in ('', 'off', 'no', 'none', 'false', '0'):
            full = b3.getAbsolutePath(sock, True)
            if len(full.encode('utf-8')) > 100:
                problems.append('b3::control_socket path is too long for a Unix socket (at most 100 bytes): %s' % full)
            elif not os.path.isdir(os.path.dirname(full)):
                problems.append('b3::control_socket folder does not exist: %s' % os.path.dirname(full))

    if config.has_option('b3', 'parser'):
        try:
            parser = b3.loadParser(config.get('b3', 'parser'))
        except Exception:
            parser = None  # already reported by analyze()
        if parser is not None:
            from b3.parsers.q3a.abstractParser import AbstractParser
            if getattr(parser, 'gameName', None) != 'bf3' and not config.has_option('server', 'public_ip'):
                problems.append('missing configuration value server::public_ip')
            if issubclass(parser, AbstractParser) and not config.has_option('server', 'game_log'):
                problems.append("missing configuration value server::game_log (the %s parser reads the game log)"
                                % config.get('b3', 'parser'))

    try:
        external_dir = config.get_external_plugins_dir()
    except Exception:
        external_dir = None
    for p in config.get_plugins():
        if p.get('disabled') and p['name'] != 'admin':
            continue
        problems.extend(_check_plugin(p, external_dir))

    return problems


def main(filename):
    """
    Run the check, print the result and exit.
    """
    if not filename:
        print('ERROR: no configuration file given (use --check-config -c b3.ini)')
        raise SystemExit(b3.exitcodes.CONFIG)
    problems = check_config(filename)
    if problems:
        for problem in problems:
            print('ERROR: %s' % ' '.join(str(problem).split()))
        sys.stdout.flush()
        raise SystemExit(b3.exitcodes.CONFIG)
    print('OK: %s' % b3.getAbsolutePath(filename, True))
    raise SystemExit(b3.exitcodes.OK)
