# -*- coding: utf-8 -*-
"""
A fake rcon for the Quake 3 engine family whose dumpuser looks players up by NAME only (Quake 3 1.32 and ET 2.60b
sv_ccmds.c, ET: Legacy 2.86 SV_GetPlayerByName): the raw name or the Q_CleanStr'd one, compared case-insensitively.
"dumpuser 4" answers "Player 4 is not on the server", as the live servers do (linuxgsm-panel round D, F-D1).
"""


def q_cleanstr(name):
    out, i = [], 0
    while i < len(name):
        if name[i] == '^' and i + 1 < len(name) and name[i + 1] != '^':
            i += 2
            continue
        if ' ' <= name[i] <= '~':
            out.append(name[i])
        i += 1
    return ''.join(out)


def dumpuser_reply(userinfo, width=20):
    return 'userinfo\n--------\n' + ''.join('%s%s\n' % (k.ljust(width), v) for k, v in userinfo.items())


def fake_rcon(status, players, width=20, sent=None):
    """
    :param status: the rcon status text
    :param players: [userinfo dict, ...] in slot order; each has at least 'name'
    :param sent: a list that collects every command written
    """
    def write(cmd, *args, **kwargs):
        if sent is not None:
            sent.append(cmd)
        if cmd == 'status':
            return status
        if cmd.startswith('dumpuser '):
            arg = cmd[len('dumpuser '):]
            if arg.startswith('"') and arg.endswith('"'):
                arg = arg[1:-1]
            for p in players:
                if p['name'].lower() == arg.lower() or q_cleanstr(p['name']).lower() == arg.lower():
                    return dumpuser_reply(p, width)
            return 'Player %s is not on the server\n' % arg
        return ''
    return write
