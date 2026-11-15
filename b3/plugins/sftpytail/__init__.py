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

import b3
import b3.plugin
import b3.output
import logging
import os.path
import time
import threading

from b3 import functions
from configparser import NoOptionError

try:
    import paramiko
except ImportError as ee:
    paramiko = None # just to remove a warning
    log = b3.output.getInstance()
    log.critical("Missing module paramiko. The paramiko module is required to connect with SFTP. "
                 "Install pycrypto from http://www.voidspace.org.uk/python/modules.shtml#pycrypto and "
                 "paramiko from http://www.lag.net/paramiko/")
    raise ee

__version__ = '1.4'
__author__ = 'Courgette'


class UnknownHostKeyError(paramiko.SSHException):
    """
    Raised when the SSH host key of the sFTP server cannot be found in the known_hosts file and
    connecting to hosts with an unknown key is not allowed.
    """
    pass


class SftpytailPlugin(b3.plugin.Plugin):

    requiresConfigFile = False
    default_connection_timeout = 30  # time (in sec) to wait before reconnecting after loosing FTP connection
    default_maxGap = 20480           # max gap in bytes between remote file and local file

    ####################################################################################################################
    #                                                                                                                  #
    #    STARTUP                                                                                                       #
    #                                                                                                                  #
    ####################################################################################################################

    def __init__(self, console, config=None):
        """
        Object constructor.
        :param console: The console instance
        :param config: The plugin configuration
        """
        b3.plugin.Plugin.__init__(self, console, config)
        self._maxGap = SftpytailPlugin.default_maxGap
        self._waitBeforeReconnect = 15
        self._connectionTimeout = SftpytailPlugin.default_connection_timeout
        self._nbConsecutiveConnFailure = 0
        self._logAppend = False
        self._publicIp = None
        self._remoteFileOffset = None
        self._sftpdelay = 0.150
        self.buffer = None
        self.file = None
        self.lgame_log = None
        self.sftpconfig = None
        self.known_hosts_file = None
        self.private_key_file = None
        self.allow_unknown_host_key = False

    def onStartup(self):
        """
        Initialize plugin.
        """
        if self.console.config.has_option('server', 'delay'):
            self._sftpdelay = self.console.config.getfloat('server', 'delay')
        
        if self.console.config.has_option('server', 'local_game_log'):
            self.lgame_log = self.console.config.getpath('server', 'local_game_log')
        else:
            self.lgame_log = os.path.normpath(os.path.expanduser(self.console.input.name))

        self.lgame_log = b3.getWritableFilePath(self.lgame_log)
        self.debug('local game log is: %s' % self.lgame_log)

        if self.console.config.get('server', 'game_log')[0:7] == 'sftp://':
            self.init_thread(self.console.config.get('server', 'game_log'))

        if self.console.config.has_option('server', 'log_append'):
            self._logAppend = self.console.config.getboolean('server', 'log_append')
        else:
            self._logAppend = False

        # get rid of "no handler found for paramiko.transport" errors
        paramiko_logger = logging.getLogger('paramiko')
        paramiko_logger.handlers = [logging.NullHandler()]
        paramiko_logger.propagate = False

    def onLoadConfig(self):
        """
        Load configuration file.
        """
        if self.config is None:
            return
        try:
            self._connectionTimeout = self.config.getint('settings', 'timeout')
            if self._connectionTimeout < 0:
                raise ValueError("timeout cannot be negative")
            self.debug('loaded settings/timeout: %s' % self._connectionTimeout)
        except NoOptionError:
            self.warning('could not find settings/timeout in config file, '
                         'using default: %s' % self._connectionTimeout)
        except ValueError as e:
            self._connectionTimeout = SftpytailPlugin.default_connection_timeout
            self.error('could not load settings/timeout config value: %s' % e)
            self.debug('using default value (%s) for settings/timeout' % self._connectionTimeout)

        try:
            self._maxGap = self.config.getint('settings', 'maxGapBytes')
            if self._maxGap < 0:
                raise ValueError("maxGapBytes cannot be negative")
            self.debug('loaded settings/maxGapBytes: %s' % self._maxGap)
        except NoOptionError:
            self.warning('could not find settings/maxGapBytes in config file, '
                         'using default: %s' % self._maxGap)
        except ValueError as e:
            self._maxGap = SftpytailPlugin.default_maxGap
            self.error('could not load settings/maxGapBytes config value: %s' % e)
            self.debug('using default value (%s) for settings/maxGapBytes' % self._maxGap)

        try:
            self.known_hosts_file = self.config.getpath('settings', 'known_hosts_file')
            if not os.path.isfile(self.known_hosts_file):
                raise ValueError("known_host file %r does not exists" % self.known_hosts_file)
            self.debug('loaded settings/known_hosts_file: %s' % self.known_hosts_file)
        except (NoOptionError, KeyError):
            pass
        except ValueError as e:
            self.known_hosts_file = None
            self.error('could not load settings/known_host config value: %s' % e)
            self.debug('known_host_file set to: %r' % self.known_hosts_file)

        try:
            self.private_key_file = self.config.getpath('settings', 'private_key_file')
            if not os.path.isfile(self.private_key_file):
                raise ValueError("private key file %r does not exists" % self.private_key_file)
            self.debug('loaded settings/private_key_file: %s' % self.private_key_file)
        except (NoOptionError, KeyError):
            pass
        except ValueError as e:
            self.private_key_file = None
            self.error('could not load settings/private_key_file config value: %s' % e)
            self.debug('private_key_file set to: %r' % self.private_key_file )

        try:
            self.allow_unknown_host_key = self.config.getboolean('settings', 'allow_unknown_host_key')
            self.debug('loaded settings/allow_unknown_host_key: %s' % self.allow_unknown_host_key)
        except (NoOptionError, KeyError):
            self.allow_unknown_host_key = False
        except ValueError as e:
            self.allow_unknown_host_key = False
            self.error('could not load settings/allow_unknown_host_key config value: %s' % e)
            self.debug('using default value (%s) for settings/allow_unknown_host_key' % self.allow_unknown_host_key)
        if self.allow_unknown_host_key:
            self.warning('settings/allow_unknown_host_key is enabled: the sFTP server identity will NOT be verified '
                         'when its host key is not in the known_hosts file (vulnerable to man-in-the-middle attacks)')

    def init_thread(self, ftpfiledsn):
        self.sftpconfig = functions.splitDSN(ftpfiledsn)
        thread1 = threading.Thread(target=self.update)
        self.info("starting sftpytail thread")
        thread1.start()
        return thread1

    ####################################################################################################################
    #                                                                                                                  #
    #    OTHER METHODS                                                                                                 #
    #                                                                                                                  #
    ####################################################################################################################

    def update(self):
        """
        Update the local log file.
        """
        def handle_download(block):
            self.verbose('received %s bytes' % len(block))
            self._remoteFileOffset += len(block)
            if self.buffer is None:
                self.buffer = block
            else:
                self.buffer = self.buffer + block
        transport = sftp = None
        rfile = None
        self.file = open(self.lgame_log, 'ab')
        self.file.write(b'\r\n')
        self.file.write(b'B3 has been restarted\r\n')
        self.file.write(b'\r\n')
        while self.console.working:
            try:
                if not sftp:
                    transport, sftp = self.sftpconnect()
                    rfile = None
                    self._nbConsecutiveConnFailure = 0
                try:
                    #self.verbose("Getting remote file size for %s" % self.sftpconfig['path'])
                    remotesize = sftp.stat(self.sftpconfig['path']).st_size
                    #self.verbose("Remote file size is %s" % remoteSize)
                except IOError as err:
                    # the file can be briefly missing while the game server rotates it: handled below
                    self.warning('cannot stat remote game log file %s: %s' % (self.sftpconfig['path'], err))
                    raise
                if self._remoteFileOffset is None:
                    self._remoteFileOffset = remotesize
                if remotesize < self._remoteFileOffset:
                    self.debug("remote file rotation detected")
                    self._remoteFileOffset = 0
                    # with rename based rotation the open handle still points to the old file: reopen it
                    if rfile is not None:
                        try:
                            rfile.close()
                        except Exception:
                            pass
                        rfile = None
                if remotesize > self._remoteFileOffset:
                    if (remotesize - self._remoteFileOffset) > self._maxGap:
                        gap = remotesize - self._remoteFileOffset
                        self.verbose('gap between local and remote file too large (%s bytes)', gap)
                        self.verbose('downloading only the last %s bytes' % self._maxGap)
                        self._remoteFileOffset = remotesize - self._maxGap
                    #self.debug('RETR from remote offset %s. (expecting to read at least %s bytes)' % (
                    #           self._remoteFileOffset, remoteSize - self._remoteFileOffset))
                    if not rfile:
                        self.debug('opening remote game log file %s for reading' % self.sftpconfig['path'])
                        rfile = sftp.open(self.sftpconfig['path'], 'rb')
                    rfile.seek(self._remoteFileOffset)
                    self.debug('reading remote game log file from offset %s' % self._remoteFileOffset)
                    handle_download(rfile.read())
                    if self.buffer:
                        self.file.write(self.buffer)
                        self.buffer = None
                        self.file.flush()
                    if self.console._paused:
                        self.console.unpause()
                        self.debug('Unpausing')
            except (paramiko.SSHException, EOFError, OSError) as err:
                # OSError (IOError, socket errors): remote file briefly missing (log rotation), dropped socket, ...
                if isinstance(err, UnknownHostKeyError):
                    self.error(str(err))
                else:
                    self.warning('%s: %s' % (err.__class__.__name__, err))
                self._nbConsecutiveConnFailure += 1
                self.verbose('lost connection to server: pausing until updated properly')
                if self.console._paused is False:
                    self.console.pause()
                self.file.close()
                if self._logAppend:
                    try:
                        self.file = open(self.lgame_log, 'ab')
                        self.file.write(b'\r\n')
                        self.file.write(b'B3 has restarted writing the log file\r\n')
                        self.file.write(b'\r\n')
                    except IOError:
                        self.file = open(self.lgame_log, 'wb')
                else:
                    self.file = open(self.lgame_log, 'wb')
                self.file.close()
                self.file = open(self.lgame_log, 'ab')
                for resource in (rfile, transport):
                    try:
                        if resource is not None:
                            resource.close()
                    except Exception:
                        pass
                self.debug('sFTP connection closed')
                rfile = None
                sftp = None
                transport = None
                
                if self._nbConsecutiveConnFailure <= 30:
                    time.sleep(1)
                else:
                    self.debug('too many failures: sleeping %s sec' % self._waitBeforeReconnect)
                    time.sleep(self._waitBeforeReconnect)
            time.sleep(self._sftpdelay)

        self.verbose("B3 is down: stopping sFtpytail thread")

        for resource in (rfile, transport, self.file):
            try:
                if resource is not None:
                    resource.close()
            except Exception:
                pass
    
    def sftpconnect(self):
        """
        Connect to the sFTP server.
        """
        hostname = self.sftpconfig['host']
        port = self.sftpconfig['port']
        username = self.sftpconfig['user']
        password = self.sftpconfig['password']
        
        # get host key: paramiko does not verify the server identity when no host key is given
        hostkey = self.get_host_key(hostname, port)
        if hostkey is None:
            if not self.allow_unknown_host_key:
                raise UnknownHostKeyError(
                    "refusing to connect to %(host)s: its SSH host key is not in the known_hosts file (%(file)s) so "
                    "the server identity cannot be verified. Add the server key to that file, for instance by running "
                    "'ssh-keyscan -p %(port)s %(host)s >> ~/.ssh/known_hosts' (then check the key fingerprint with the "
                    "server administrator) or by connecting once with the OpenSSH client, or set the known_hosts_file "
                    "setting of the sftpytail plugin. To connect anyway without verifying the server identity (NOT "
                    "recommended) set allow_unknown_host_key: yes in the sftpytail plugin config file" % {
                        'host': hostname, 'port': port, 'file': self.get_host_keys_file()})
            self.warning('SSH host key for %s is unknown: connecting WITHOUT verifying the server identity '
                         '(allow_unknown_host_key is enabled)' % self._known_hosts_name(hostname, port))

        self.info('connecting to %s ...', self.sftpconfig["host"])
        # now, connect and use paramiko Transport to negotiate SSH2 across the connection
        t = paramiko.Transport((hostname, port))
        try:
            private_key = self.get_private_key(password)
            if private_key is None:
                t.connect(username=username, password=password, hostkey=hostkey)
            else:
                t.connect(username=username, hostkey=hostkey, pkey=private_key)
        except Exception:
            t.close()
            raise
        sftp = paramiko.SFTPClient.from_transport(t)
        channel = sftp.get_channel()
        channel.settimeout(self._connectionTimeout)
        self.console.clients.sync()
        self.info("connection successful")
        return t, sftp

    @staticmethod
    def _known_hosts_name(hostname, port):
        """
        Return the name under which OpenSSH stores the key of a host in the known_hosts file.
        """
        if port is None or int(port) == 22:
            return hostname
        return '[%s]:%s' % (hostname, port)

    def get_host_key(self, hostname, port):
        """
        Return the known host key of the given host (or None if unknown).
        OpenSSH stores keys of hosts on non standard ports as '[host]:port'.
        """
        host_keys = self.get_host_keys()
        candidates = [self._known_hosts_name(hostname, port)]
        if candidates[0] != hostname:
            # compatibility: known_hosts entries without port written by hand for a non standard port
            candidates.append(hostname)
        for name in candidates:
            try:
                keys = host_keys[name]
            except KeyError:
                continue
            if keys:
                hostkeytype = next(iter(keys))
                self.info('using host key of type %s found for %s' % (hostkeytype, name))
                return keys[hostkeytype]
        return None

    def get_host_keys_file(self):
        """
        Get the path of the host keys file.
        The host key file can either be defined in the plugin config file or well known locations:
            ~/.ssh/known_hosts
            ~/ssh/known_hosts
        """
        host_keys_file = self.known_hosts_file
        for potential_location in ['~/.ssh/known_hosts', '~/ssh/known_hosts']:
            if host_keys_file is not None:
                break
            path = b3.getAbsolutePath(potential_location)
            if os.path.isfile(path):
                host_keys_file = path
        return host_keys_file

    def get_host_keys(self):
        host_keys_file = self.get_host_keys_file()
        host_keys = {}
        if host_keys_file is None:
            self.warning("no known_hosts file found: set the known_hosts_file setting of the sftpytail plugin")
            return host_keys
        try:
            host_keys = paramiko.util.load_host_keys(host_keys_file)
        except Exception as err:
            self.warning("cannot read host keys file: %r. " % host_keys_file, exc_info=err)
        return host_keys

    def get_private_key(self, password=None):
        if self.private_key_file is not None:
            with open(self.private_key_file, "r") as f:
                key_head = f.readline()
            if 'DSA' in key_head:
                # DSS keys support was dropped in recent paramiko versions
                key_types = [getattr(paramiko, 'DSSKey', None)]
            elif 'RSA' in key_head:
                key_types = [paramiko.RSAKey]
            elif 'EC' in key_head:
                key_types = [getattr(paramiko, 'ECDSAKey', None)]
            elif 'OPENSSH' in key_head:
                # new OpenSSH private key format: the key type is not part of the header
                key_types = [getattr(paramiko, name, None) for name in ('Ed25519Key', 'ECDSAKey', 'RSAKey', 'DSSKey')]
            else:
                key_types = []
            key_types = [x for x in key_types if x is not None]
            if not key_types:
                raise ValueError("can't identify private key type")
            last_error = paramiko.SSHException("could not load private key %s" % self.private_key_file)
            for key_type in key_types:
                try:
                    with open(self.private_key_file, "r") as f:
                        return key_type.from_private_key(f, password=password)
                except paramiko.SSHException as err:
                    last_error = err
            raise last_error