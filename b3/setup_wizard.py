# -*- coding: utf-8 -*-

# ################################################################### #
#                                                                     #
#  BigBrotherBot(B3) (www.bigbrotherbot.net)                          #
#                                                                     #
#  This program is free software; you can redistribute it and/or      #
#  modify it under the terms of the GNU General Public License        #
#  as published by the Free Software Foundation; either version 2     #
#  of the License, or (at your option) any later version.             #
#                                                                     #
#  This program is distributed in the hope that it will be useful,    #
#  but WITHOUT ANY WARRANTY; without even the implied warranty of     #
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the       #
#  GNU General Public License for more details.                       #
#                                                                     #
#  You should have received a copy of the GNU General Public License  #
#  along with this program; if not, write to the Free Software        #
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA      #
#  02110-1301, USA.                                                   #
#                                                                     #
# ################################################################### #

"""
Console setup wizard: asks a few questions and writes a working b3.ini from the sample configuration
(b3/conf/b3.distribution.ini), keeping its comments. Run with: b3_run --setup (b3.cmd --setup on Windows).

It replaces the web config generator of the original project (config.bigbrotherbot.net), which is gone.
"""

import getpass
import os
import re
import shutil
import sys
import tempfile

import b3

# (parser, game, default port or None, reads a game log file, usual log file name)
GAMES = [
    ('cod', 'Call of Duty', 28960, True, 'games_mp.log'),
    ('cod2', 'Call of Duty 2', 28960, True, 'games_mp.log'),
    ('cod4', 'Call of Duty 4: Modern Warfare', 28960, True, 'games_mp.log'),
    ('cod4gr', 'Call of Duty 4 (GameRanger)', 28960, True, 'games_mp.log'),
    ('cod5', 'Call of Duty: World at War', 28960, True, 'games_mp.log'),
    ('cod6', 'Call of Duty: Modern Warfare 2', 28960, True, 'games_mp.log'),
    ('cod7', 'Call of Duty: Black Ops', 3074, True, 'games_mp.log'),
    ('cod8', 'Call of Duty: Modern Warfare 3', 27015, True, 'games_mp.log'),
    ('iourt41', 'Urban Terror 4.1', 27960, True, 'games.log'),
    ('iourt42', 'Urban Terror 4.2', 27960, True, 'games.log'),
    ('iourt43', 'Urban Terror 4.3', 27960, True, 'games.log'),
    ('et', 'Wolfenstein: Enemy Territory', 27960, True, 'etconsole.log'),
    ('etpro', 'Enemy Territory (ETPro mod)', 27960, True, 'etpro.log'),
    ('sof2', 'Soldier of Fortune 2', 20100, True, 'games.log'),
    ('sof2pm', 'Soldier of Fortune 2 (1fx mod)', 20100, True, 'games.log'),
    ('oa081', 'OpenArena 0.8.1', 27960, True, 'games.log'),
    ('q3', 'Quake 3 Arena', 27960, True, 'games.log'),
    ('smg', "Smokin' Guns", 27960, True, 'games.log'),
    ('smg11', "Smokin' Guns 1.1", 27960, True, 'games.log'),
    ('wop', 'World of Padman', 27960, True, 'games.log'),
    ('wop15', 'World of Padman 1.5', 27960, True, 'games.log'),
    ('altitude', 'Altitude', 27276, True, 'log.txt'),
    ('csgo', 'Counter-Strike: Global Offensive', 27015, True, None),
    ('insurgency', 'Insurgency', 27015, True, None),
    ('bfbc2', 'Battlefield: Bad Company 2', 48888, False, None),
    ('bf3', 'Battlefield 3', 47200, False, None),
    ('bf4', 'Battlefield 4', 47200, False, None),
    ('bfh', 'Battlefield Hardline', 47200, False, None),
    ('moh', 'Medal of Honor (2010)', 48888, False, None),
    ('mohw', 'Medal of Honor: Warfighter', 47200, False, None),
    ('arma2', 'Arma 2', 2302, False, None),
    ('arma3', 'Arma 3', 2302, False, None),
    ('chiv', 'Chivalry: Medieval Warfare', 27960, False, None),
    ('homefront', 'Homefront', 27960, False, None),
    ('ravaged', 'Ravaged', 27960, False, None),
    ('ro2', 'Red Orchestra 2', 8080, False, None),
]

DATABASES = [
    ('sqlite', 'SQLite: a file on this computer, nothing to install (recommended to start)'),
    ('mysql', 'MySQL / MariaDB server'),
    ('postgresql', 'PostgreSQL server'),
]

SAMPLE = '@b3/conf/b3.distribution.ini'


class WizardAbort(Exception):
    pass


def set_ini_value(content, section, key, value):
    """
    Set "key: value" in the given section of an ini text, keeping every comment and the other lines as they are.
    The key is added at the end of the section when missing.
    :return: the new text
    """
    newline = '\r\n' if '\r\n' in content else '\n'
    lines = content.split(newline)
    header = re.compile(r'^\s*\[([^\]]+)\]\s*$')
    keyline = re.compile(r'^\s*%s\s*[:=]' % re.escape(key), re.IGNORECASE)
    in_section = False
    last_entry = None
    section_found = False
    for i, line in enumerate(lines):
        m = header.match(line)
        if m:
            if in_section:
                break
            in_section = m.group(1).strip().lower() == section.lower()
            if in_section:
                section_found = True
                last_entry = i
            continue
        if in_section:
            if keyline.match(line):
                lines[i] = '%s: %s' % (key, value)
                return newline.join(lines)
            if line.strip() and not line.lstrip().startswith(('#', ';')):
                last_entry = i
    if not section_found:
        lines += ['', '[%s]' % section, '%s: %s' % (key, value)]
    else:
        lines.insert(last_entry + 1, '%s: %s' % (key, value))
    return newline.join(lines)


def sqlite_dsn(path):
    return 'sqlite://' + os.path.abspath(path).replace('\\', '/')


def server_dsn(protocol, user, password, host, port, name):
    for label, value in (('user name', user), ('password', password), ('database name', name)):
        if any(c in value for c in '@/:'):
            raise ValueError('the database %s cannot contain @, / or :' % label)
    return '%s://%s:%s@%s:%s/%s' % (protocol, user, password, host, port, name)


def build_config(sample_text, answers):
    """
    Return the b3.ini text for the given answers (a dict), based on the sample configuration text.
    """
    text = sample_text
    values = [
        ('b3', 'parser', answers['parser']),
        ('b3', 'database', answers['database']),
        ('b3', 'bot_name', answers.get('bot_name') or 'b3'),
        ('b3', 'time_zone', answers.get('time_zone') or 'auto'),
        # next to b3.ini: the sample's relative b3.log ends up in whatever folder B3 starts in (on Windows, the
        # install folder)
        ('b3', 'logfile', '@home/b3.log'),
        ('server', 'public_ip', answers['public_ip']),
        ('server', 'port', str(answers['port'])),
        ('server', 'rcon_ip', answers['rcon_ip']),
        ('server', 'rcon_password', answers['rcon_password']),
        ('server', 'punkbuster', 'on' if answers.get('punkbuster') else 'off'),
    ]
    if answers.get('game_log'):
        values.append(('server', 'game_log', answers['game_log']))
    for section, key, value in values:
        text = set_ini_value(text, section, key, value)
    if not answers.get('punkbuster'):
        # the punkbuster plugin only logs a warning without PunkBuster: do not load it
        text = re.sub(r'(?m)^(punkbuster:\s*@)', r'# \1', text)
    return text


def validate(text):
    """
    Run B3's own configuration checks on the given b3.ini text.
    :return: the list of problems found
    """
    import b3.config
    fd, path = tempfile.mkstemp(suffix='.ini')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
        return b3.config.MainConfig(b3.config.load(path)).analyze()
    finally:
        os.remove(path)


class Wizard(object):

    def __init__(self, ask=input, ask_secret=None, say=print):
        self.ask_raw = ask
        if ask_secret is None:
            # getpass reads the console itself (not stdin): fall back to plain input when the answers are piped in
            interactive = sys.stdin is not None and sys.stdin.isatty()
            ask_secret = getpass.getpass if interactive else ask
        self.ask_secret_raw = ask_secret
        self.say = say

    def ask(self, question, default=None, validate=None):
        prompt = '%s [%s]: ' % (question, default) if default not in (None, '') else '%s: ' % question
        while True:
            try:
                answer = self.ask_raw(prompt).strip()
            except EOFError:
                raise WizardAbort()
            if not answer and default not in (None, ''):
                answer = str(default)
            if not answer:
                self.say('  please type a value')
                continue
            if validate:
                error = validate(answer)
                if error:
                    self.say('  %s' % error)
                    continue
            return answer

    def ask_secret(self, question):
        while True:
            try:
                answer = self.ask_secret_raw('%s (not shown while you type): ' % question)
            except EOFError:
                raise WizardAbort()
            if answer:
                return answer
            self.say('  please type a value')

    def yes(self, question, default=False):
        answer = self.ask('%s (y/n)' % question, 'y' if default else 'n',
                          lambda a: None if a.lower() in ('y', 'yes', 'n', 'no') else 'answer y or n')
        return answer.lower() in ('y', 'yes')

    def choose(self, question, options):
        """
        options: list of (value, label); returns the chosen value (by number or by value)
        """
        for i, (value, label) in enumerate(options, 1):
            self.say('  %2d) %s' % (i, label))
        values = [v for v, _ in options]

        def check(answer):
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return None
            return None if answer.lower() in values else 'type a number from the list'

        answer = self.ask(question, None, check)
        return options[int(answer) - 1][0] if answer.isdigit() else answer.lower()

    def ask_game(self):
        self.say('\nWhich game does your server run?')
        parser = self.choose('Game number', [(g[0], '%s (%s)' % (g[1], g[0])) for g in GAMES])
        return next(g for g in GAMES if g[0] == parser)

    def ask_server(self, game, answers):
        parser, name, default_port, reads_log, log_name = game
        self.say('\nGame server')
        same_box = self.yes('Is B3 running on the same computer as the game server?', True)
        answers['public_ip'] = self.ask('Public IP address of the game server (what players connect to)',
                                        '127.0.0.1' if same_box else None, check_ip)
        answers['port'] = int(self.ask('Game server port', default_port, check_port))
        answers['rcon_ip'] = '127.0.0.1' if same_box else self.ask('IP address B3 sends RCON commands to',
                                                                   answers['public_ip'], check_ip)
        answers['rcon_password'] = self.ask_secret('RCON password of the game server')
        if reads_log:
            self.say('\nB3 reads the game log to see what happens in game (chat, kills, players joining).')
            if log_name:
                self.say('For %s it is usually called %s, in the game folder (main/ or the mod folder).'
                         % (name, log_name))
            self.say('A remote log works too: ftp://user:password@host/path/%s (or sftp://, http://)'
                     % (log_name or 'games.log'))
            answers['game_log'] = self.ask('Full path of the game log file')
            if '://' not in answers['game_log'] and not os.path.isfile(answers['game_log']):
                self.say('  note: %s does not exist yet: check the path if B3 sees nothing happening in game'
                         % answers['game_log'])
        answers['punkbuster'] = self.yes('Does the server run PunkBuster?', False)

    def ask_database(self, home):
        self.say('\nDatabase (stores players, admins, warnings, bans)')
        protocol = self.choose('Database number', DATABASES)
        if protocol == 'sqlite':
            path = self.ask('Database file', os.path.join(home, 'b3.db'))
            return sqlite_dsn(path)
        while True:
            host = self.ask('Database server address', 'localhost')
            port = self.ask('Database server port', 3306 if protocol == 'mysql' else 5432, check_port)
            name = self.ask('Database name', 'b3')
            user = self.ask('Database user name', 'b3')
            password = self.ask_secret('Database password')
            try:
                return server_dsn(protocol, user, password, host, port, name)
            except ValueError as e:
                self.say('  %s: please use other values' % e)

    def run(self, path=None, confirm_replace=True):
        """
        Ask the questions and write the configuration file.
        :param confirm_replace: ask before replacing an existing file (a backup is kept either way)
        :return: the path of the written file, or None if the user stopped
        """
        home = b3.HOMEDIR
        path = os.path.abspath(path or os.path.join(home, 'b3.ini'))
        self.say('BigBrotherBot (B3) setup: answer a few questions to create %s' % path)
        self.say('(press Enter to accept the value in [brackets]; Ctrl+C to stop)')
        try:
            if confirm_replace and os.path.isfile(path) and not self.yes('\n%s already exists: replace it? (a backup copy is kept)'
                                                     % path, False):
                self.say('Nothing changed.')
                return None
            game = self.ask_game()
            answers = {'parser': game[0]}
            self.ask_server(game, answers)
            answers['database'] = self.ask_database(home)
            answers['bot_name'] = self.ask('\nName of the bot (shown in game)', 'b3')
        except (WizardAbort, KeyboardInterrupt):
            self.say('\nSetup stopped: nothing changed.')
            return None

        with open(b3.getAbsolutePath(SAMPLE), encoding='utf-8') as f:
            text = build_config(f.read(), answers)
        problems = validate(text)
        if problems:
            # should not happen: every value comes from the checks above
            self.say('\nThe configuration is not valid:\n' + '\n'.join('  >>> %s' % p for p in problems))
            return None

        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.isfile(path):
            shutil.copy2(path, path + '.bak')
            self.say('\nThe previous file was saved as %s.bak' % path)
        write_private(path, text)
        self.say('\nSaved %s' % path)
        self.say('Start B3 now. In game, type !iamgod in the chat to become super admin (works once, on a new '
                 'database).')
        self.say('Every other setting (plugins, messages, time format...) is in that file, with comments.')
        return path


def write_private(path, text):
    """
    Write the configuration readable by its owner only: B3 needs the RCON and database passwords in clear to log
    in (as in any b3.ini), so the file itself is protected. On Windows the file lives in the user's profile.
    """
    if os.path.exists(path):
        os.chmod(path, 0o600)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(text)


def check_ip(answer):
    if re.match(r'^[A-Za-z0-9.\-:]+$', answer):
        return None
    return 'type an IP address or a host name'


def check_port(answer):
    if answer.isdigit() and 0 < int(answer) < 65536:
        return None
    return 'type a port number (1-65535)'


def run_wizard(path=None):
    """
    Entry point for b3_run --setup.
    """
    return Wizard().run(path)
