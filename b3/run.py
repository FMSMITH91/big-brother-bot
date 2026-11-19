# -*- coding: utf-8 -*-

# ################################################################### #
#                                                                     #
#  BigBrotherBot(B3) (www.bigbrotherbot.net)                          #
#  Copyright (C) 2005 Michael "ThorN" Thornton                        #
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

__author__  = 'ThorN'
__version__ = '1.8'

import b3
import b3.config
import b3.exitcodes
import os
import sys
import argparse
from . import pkg_handler
import traceback

from b3 import HOMEDIR, config_help
from b3.functions import main_is_frozen, console_exit
from b3.update import DBUpdate
from time import sleep

modulePath = pkg_handler.resource_directory(__name__)


def autorestart_command(args=None):
    """
    Return the command (as an argument list, so paths and options containing spaces need no quoting)
    used to run the B3 child process in auto-restart mode.
    :param args: Extra command line arguments
    """
    command = [sys.executable]
    if not main_is_frozen():
        # running from sources: run the B3 script with the current interpreter
        # (the frozen application is the executable itself, so there is no script to pass)
        script = os.path.join(modulePath[:-3], 'b3_run.py')
        if not os.path.isfile(script):
            # must be running from the wheel, so there is no b3_run
            script = os.path.join(modulePath[:-3], 'b3', 'run.py')
        command.append(script)
    return command + list(args or []) + ['--autorestart']


def run_autorestart(args=None):
    """
    Run B3 in auto-restart mode.
    """
    restart_num = 0
    command = autorestart_command(args)

    while True:

        try:

            import subprocess
            status = subprocess.call(command)

            sys.stdout.write('Exited with status: %s ... ' % status)
            sys.stdout.flush()
            sleep(2)

            if status == 221:
                restart_num += 1
                sys.stdout.write('restart requested (%s)\n' % restart_num)
                sys.stdout.flush()
            elif status == 222:
                sys.stdout.write('shutdown requested!\n')
                sys.stdout.flush()
                break
            elif status == 220 or status == 223:
                sys.stdout.write('B3 error (check log file)\n')
                sys.stdout.flush()
                break
            elif status == 224:
                sys.stdout.write('B3 error (check console)\n')
                sys.stdout.flush()
                break
            elif status in b3.exitcodes.FINAL:
                sys.stdout.write('%s (check log file)\n' % b3.exitcodes.DESCRIPTIONS[status])
                sys.stdout.flush()
                break
            elif status == 256:
                sys.stdout.write('python error, (check log file)\n')
                sys.stdout.flush()
                break
            elif status == 0:
                sys.stdout.write('normal shutdown\n')
                sys.stdout.flush()
                break
            elif status == 1:
                sys.stdout.write('general error (check console)\n')
                sys.stdout.flush()
                break
            else:
                restart_num += 1
                sys.stdout.write('unknown exit code (%s), restarting (%s)...\n' % (status, restart_num))
                sys.stdout.flush()

            sleep(4)

        except KeyboardInterrupt:
            print('Quit')
            break


def run_update(config=None):
    """
    Run the B3 update.
    :param config: The B3 configuration file instance
    """
    update = DBUpdate(config)
    update.run()


def offer_setup_wizard(reason, config=None):
    """
    When B3 runs in a terminal, offer to create the configuration file with the setup wizard.
    :return: True if the wizard wrote a configuration file
    """
    if not (sys.stdin and sys.stdin.isatty() and sys.stdout.isatty()):
        return False
    from b3.setup_wizard import Wizard, WizardAbort
    wizard = Wizard()
    try:
        if reason:
            print(reason)
        question = 'Replace %s with one made by the setup wizard? (a backup copy is kept)' % config if config \
            else 'Create the configuration file now with the setup wizard?'
        if not wizard.yes(question, True):
            return False
    except (WizardAbort, KeyboardInterrupt):
        return False
    if not wizard.run(config, confirm_replace=False):
        return False
    print('\nStart B3 again to use it.')
    return True


def run(options):
    """
    Run B3 in console.
    :param options: command line options
    """
    analysis = None     # main config analysis result
    printexit = False   # whether the exit message has been printed alreadty or not

    try:

        if options.config:
            config = b3.getAbsolutePath(options.config, True)
            if not os.path.isfile(config):
                printexit = True
                console_exit('ERROR: configuration file not found (%s).\n%s' % (config, config_help()), b3.exitcodes.CONFIG)
        else:
            config = None
            for p in ('b3.%s', 'conf/b3.%s', 'b3/conf/b3.%s',
                      os.path.join(HOMEDIR, 'b3.%s'), os.path.join(HOMEDIR, 'conf', 'b3.%s'),
                      os.path.join(HOMEDIR, 'b3', 'conf', 'b3.%s'), '@b3/conf/b3.%s'):
                for e in ('ini', 'cfg', 'xml'):
                    path = b3.getAbsolutePath(p % e, True)
                    if os.path.isfile(path):
                        print("Using configuration file: %s" % path)
                        config = path
                        sleep(3)
                        break

            if not config:
                printexit = True
                if offer_setup_wizard('B3 could not find a configuration file.'):
                    raise SystemExit(0)
                console_exit('ERROR: could not find any valid configuration file.\n%s' % config_help(), b3.exitcodes.CONFIG)

        # LOADING MAIN CONFIGURATION
        main_config = b3.config.MainConfig(b3.config.load(config))
        analysis = main_config.analyze()
        if analysis:
            raise b3.config.ConfigFileNotValid('invalid configuration file specified')

        # START B3
        b3.start(main_config, options)

    except b3.config.ConfigFileNotValid:
        if analysis:
            print('CRITICAL: invalid configuration file specified:\n')
            for problem in analysis:
                print("  >>> %s\n" % problem)
        else:
            print('CRITICAL: invalid configuration file specified!')
        print('Edit %s to fix this, then start B3 again: the comments in the file explain each setting.' % config)
        if offer_setup_wizard('', config):
            raise SystemExit(0)
        raise SystemExit(b3.exitcodes.CONFIG)
    except SystemExit as msg:
        if not printexit and main_is_frozen():
            if sys.stdout != sys.__stdout__:
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
            print(msg)
            input("press any key to continue...")
        raise
    except:
        if sys.stdout != sys.__stdout__:
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
        traceback.print_exc()
        if sys.stdin and sys.stdin.isatty():
            input("press any key to continue...")
        # without a terminal (service, container) waiting for a key raised EOFError and B3 exited with status 1
        raise SystemExit(b3.exitcodes.UNHANDLED)


def main():
    """
    Main execution.
    """
    p = argparse.ArgumentParser()
    p.add_argument('-c', '--config', dest='config', default=None, metavar='b3.ini', help='B3 config file. Example: -c b3.ini')
    p.add_argument('-r', '--restart', action='store_true', dest='restart', default=False, help='Auto-restart B3 on crash')
    p.add_argument('-s', '--setup',  action='store_true', dest='setup', default=False, help='Create the b3.ini config file with the setup wizard')
    p.add_argument('-u', '--update', action='store_true', dest='update', default=False, help='Update B3 database to latest version')
    p.add_argument('-v', '--version', action='version', default=False, version=b3.getB3versionString(), help='Show B3 version and exit')
    p.add_argument('--check-config', action='store_true', dest='check_config', default=False,
                   help='Check b3.ini and the plugin configuration files without connecting, then exit '
                        '(status 0 if valid, 230 otherwise)')
    p.add_argument('-a', '--autorestart', action='store_true', dest='autorestart', default=False, help=argparse.SUPPRESS)

    (options, args) = p.parse_known_args()

    if not options.config and len(args) == 1:
        options.config = args[0]

    if options.check_config:
        ## CONFIGURATION CHECK => CONSOLE
        from b3.checkconfig import main as check_config
        check_config(options.config)

    if options.setup:
        ## SETUP WIZARD => CONSOLE
        from b3.setup_wizard import run_wizard
        raise SystemExit(0 if run_wizard(options.config) else 1)

    if options.update:
        ## UPDATE => CONSOLE
        run_update(config=options.config)

    if options.restart:
        ## AUTORESTART => CONSOLE
        if options.config:
            run_autorestart(['--config', options.config] + args)
        else:
            run_autorestart([])
    else:
        run(options)

if __name__ == '__main__':
    main()
