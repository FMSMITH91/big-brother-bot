# -*- coding: utf-8 -*-
"""
B3's process exit codes. Service managers and front-ends (the linuxgsm-panel add-on) map them to a reason, so a code
keeps its meaning across releases: add new ones, never reuse one.

A bad RCON password does not stop B3 (it keeps reading the game log, and RCON also fails for a moment on a map change):
it is reported in the health file instead.
"""

OK = 0              # normal stop (including SIGTERM) or --check-config found no problem
CRITICAL = 220      # a fatal error with no more specific code below
RESTART = 221       # restart requested (!restart): the auto-restart loop starts B3 again
SHUTDOWN = 222      # shutdown requested (!die)
UNHANDLED = 223     # unexpected exception during startup
CONFIG = 230        # invalid configuration: b3.ini or a plugin configuration file (also --check-config)
GAME_LOG = 231      # the game log cannot be opened or read
RCON = 232          # the RCON connection cannot be set up (socket, address)
DATABASE = 233      # the database cannot be set up or reached at startup

# the codes that end the auto-restart loop (any other code restarts B3)
FINAL = (OK, CRITICAL, SHUTDOWN, UNHANDLED, 224, CONFIG, GAME_LOG, RCON, DATABASE)

DESCRIPTIONS = {
    OK: 'normal shutdown',
    CRITICAL: 'B3 error (check log file)',
    RESTART: 'restart requested',
    SHUTDOWN: 'shutdown requested',
    UNHANDLED: 'B3 error (check log file)',
    CONFIG: 'invalid configuration',
    GAME_LOG: 'cannot read the game log',
    RCON: 'cannot set up RCON',
    DATABASE: 'cannot reach the database',
}
