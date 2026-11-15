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

__version__ = '1.2'

import logging
import time
import asyncore
import socket
import threading
import hashlib

from struct import pack
from struct import unpack


def EncodeHeader(isFromServer, isResponse, sequence):
    header = sequence & 0x3fffffff
    if isFromServer:
        header += 0x80000000
    if isResponse:
        header += 0x40000000
    return pack('<I', header)


def DecodeHeader(data):
    [header] = unpack('<I', data[0 : 4])
    return [header & 0x80000000, header & 0x40000000, header & 0x3fffffff]


def EncodeInt32(size):
    return pack('<I', size)


def DecodeInt32(data):
    return unpack('<I', data[0 : 4])[0]
    
    
# The Frostbite protocol transports words as UTF-8 encoded bytes. Inside B3 words are always str: they are
# encoded right before being put on the wire and decoded right after being read from it.
WORD_ENCODING = 'UTF-8'


def EncodeWord(word):
    """
    Return the given word as bytes, ready to be sent to the Frostbite server.
    """
    if isinstance(word, (bytes, bytearray)):
        return bytes(word)
    return str(word).encode(WORD_ENCODING)


def DecodeWord(data):
    """
    Return the given raw word (bytes) received from the Frostbite server as a str.
    """
    return bytes(data).decode(WORD_ENCODING, 'replace')


def EncodeWords(words):
    size = 0
    encodedWords = b''
    for word in words:
        bytesWord = EncodeWord(word)
        encodedWords += EncodeInt32(len(bytesWord))
        encodedWords += bytesWord
        encodedWords += b'\x00'
        size += len(bytesWord) + 5
    
    return size, encodedWords


def DecodeWords(size, data):
    words = []
    offset = 0
    while offset < size:
        wordLen = DecodeInt32(data[offset : offset + 4])        
        word = data[offset + 4 : offset + 4 + wordLen]
        words.append(DecodeWord(word))
        offset += wordLen + 5

    return words


def EncodePacket(isFromServer, isResponse, sequence, words):
    encodedHeader = EncodeHeader(isFromServer, isResponse, sequence)
    encodedNumWords = EncodeInt32(len(words))
    [wordsSize, encodedWords] = EncodeWords(words)
    encodedSize = EncodeInt32(wordsSize + 12)
    return encodedHeader + encodedSize + encodedNumWords + encodedWords


def DecodePacket(data):
    """
    Decode a request or response packet
    Return format is:
    [is_from_server, is_response, sequence, words]
    where
    is_from_server = the command in this command/response packet pair originated on the server
        is_response = True if this is a response, False otherwise
        sequence = sequence number
        words = list of words
    """
    [isFromServer, isResponse, sequence] = DecodeHeader(data)
    wordsSize = DecodeInt32(data[4:8]) - 12
    words = DecodeWords(wordsSize, data[12:])
    return [isFromServer, isResponse, sequence, words]


clientSequenceNr = 0
_clientSequenceLock = threading.Lock()


def nextClientSequence():
    """
    Return the sequence number to use for the next client request (thread safe: commands are sent from several
    threads and two requests sharing a sequence number would get each other's response).
    """
    global clientSequenceNr
    with _clientSequenceLock:
        sequence = clientSequenceNr
        clientSequenceNr = (clientSequenceNr + 1) & 0x3fffffff
    return sequence


def EncodeClientRequest(words):
    """
    Encode a request packet.
    """
    return EncodePacket(False, False, nextClientSequence(), words)

    
def EncodeClientResponse(sequence, words):
    """
    Encode a response packet.
    """
    return EncodePacket(True, True, sequence, words)


def printPacket(packet):
    """
    Display contents of packet in user-friendly format, useful for debugging purposes.
    """
    if packet[0]:
        print("IsFromServer, ", end=' ')
    else:
        print("IsFromClient, ", end=' ')
    
    if packet[1]:
        print("Response, ", end=' ')
    else:
        print("Request, ", end=' ')

    print("Sequence: " + str(packet[2]), end=' ')

    if packet[3]:
        print(" Words:", end=' ')
        for word in packet[3]:
            print("\"" + word + "\"", end=' ')

    print("")


def generatePasswordHash(salt, password):
    """
    Compute the hash expected by the login.hashed command.
    :param salt: the salt as bytes (as obtained by decoding the hex string sent by the server)
    :param password: the rcon password
    """
    if isinstance(salt, str):
        salt = salt.encode(WORD_ENCODING)
    if isinstance(password, str):
        password = password.encode(WORD_ENCODING)
    m = hashlib.new('md5')
    m.update(salt)
    m.update(password)
    return m.digest()

def containsCompletePacket(data):
    if len(data) < 8:
        return False
    if len(data) < DecodeInt32(data[4:8]):
        return False
    return True


def receivePacket(_socket, receiveBuffer):
    """
    Wait until the local receive buffer contains a full packet (appending data from the network socket),
    then split receive buffer into first packet and remaining buffer data
    """
    while not containsCompletePacket(receiveBuffer):
        data = _socket.recv(4096) #was 16384
        # make sure we raise a socket error when the socket is hanging
        # on a loose end (receiving no data after server restart)
        if not data:
            raise socket.error('no data received - Remote end unexpectedly closed socket')
        receiveBuffer += data

    packetSize = DecodeInt32(receiveBuffer[4:8])

    packet = receiveBuffer[0:packetSize]
    receiveBuffer = receiveBuffer[packetSize:len(receiveBuffer)]

    return [packet, receiveBuffer]


class FrostbiteError(Exception):
    @property
    def message(self):
        # Python 2 BaseException.message compatibility
        return self.args[0] if len(self.args) == 1 else ''

    pass


class CommandError(FrostbiteError):
    pass


class CommandTimeoutError(CommandError):
    pass


class CommandFailedError(CommandError):
    pass


class CommandDisallowedError(CommandError):
    pass


class CommandUnknownCommandError(CommandError):
    pass


class NetworkError(FrostbiteError):
    pass


class ThreadSafeDispatcherWithSend(asyncore.dispatcher_with_send):
    """
    asyncore.dispatcher_with_send which can be written to from threads other than the one running the asyncore loop.
    Without the lock, send() (caller thread: out_buffer = out_buffer + data) and initiate_send() (asyncore thread:
    out_buffer = out_buffer[num_sent:]) can interleave and drop or duplicate outgoing data.
    """

    def __init__(self, sock=None, map=None):
        self._send_lock = threading.RLock()
        asyncore.dispatcher_with_send.__init__(self, sock, map)

    def initiate_send(self):
        with self._send_lock:
            asyncore.dispatcher_with_send.initiate_send(self)

    def send(self, data):
        with self._send_lock:
            asyncore.dispatcher_with_send.send(self, data)


class FrostbiteDispatcher(ThreadSafeDispatcherWithSend):

    def __init__(self, host, port):
        """
        Object constructor.
        :param host: The Frostbite2 server host
        :param port: The Frostbite2 server port
        """
        ThreadSafeDispatcherWithSend.__init__(self)
        self._buffer_in = b''
        self.getLogger().info("connecting")
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        asyncore.dispatcher_with_send.connect(self, (host, port))
        self._frostbite_event_handler = None
        self._frostbite_command_response_handler = None

    ####################################################################################################################
    #                                                                                                                  #
    #   PUBLIC API                                                                                                     #
    #                                                                                                                  #
    ####################################################################################################################

    def set_frostbite_event_hander(self, func):
        """
        Register a function that will be called when the Frosbite server sends us a game event.
        """
        self._frostbite_event_handler = func

    def set_frostbite_command_response_handler(self, func):
        """
        Register a function that will be called when the Frosbite server sends us a command reply.
        """
        self._frostbite_command_response_handler = func
        
    def send_command(self, *command, **kwargs):
        """
        Send a command to the Frosbite server and return the command
        id which can be used to find the matching reply later on.
        :param before_send: optional function called with the command id before the request is sent (so that the
                            caller can get ready for a response which could come in before this method returns)
        """
        before_send = kwargs.get('before_send')
        self.getLogger().info("command : %s " % repr(command))
        if len(command) == 1 and type(command[0]) == tuple:
            words = command[0]
        else:
            words = command

        request = EncodeClientRequest(words)
        [sequence, words] = DecodePacket(request)[2:]

        if before_send is not None:
            before_send(sequence)

        self.getLogger().debug("sending command request #%i: %s " % (sequence, words))
        self.send(request)

        return sequence

    ####################################################################################################################
    #                                                                                                                  #
    #   OTHER METHODS                                                                                                  #
    #                                                                                                                  #
    ####################################################################################################################

    def getLogger(self):
        return logging.getLogger("FrostbiteDispatcher")
    
    def handle_connect(self):
        self.getLogger().debug("handle_connect")
    
    def handle_close(self):
        """
        Called when the socket is closed.
        """
        self.getLogger().debug("handle_close")
        self.close()

    def handle_read(self):
        """
        Called when the asynchronous loop detects that a read() call on the channel's socket will succeed.
        """
        # received raw data
        data = self.recv(8192)
        self._buffer_in += data
        self.getLogger().debug('read %s char from Frostbite2 gameserver' % len(data))

        # cook it into Frosbite packets
        while containsCompletePacket(self._buffer_in):
            packetSize = DecodeInt32(self._buffer_in[4:8])
            packet = self._buffer_in[0:packetSize]
            self._buffer_in = self._buffer_in[packetSize:len(self._buffer_in)]
            self.handle_packet(packet)
            
    def handle_packet(self, packet):
        """
        Called when a full Frosbite packet has been received.
        """
        [originServer, isResponse, sequence, words] = DecodePacket(packet)
        self.getLogger().info("handle_packet(%s)" % repr([originServer, isResponse, sequence, words]))
        if not isResponse:
            # acknowledge the server
            self.send(EncodePacket(originServer, True, sequence, ("OK",)))
        if originServer:
            if isResponse:
                self.getLogger().warning("received a bad packet from frosbite server pretending being a "
                                      "response for a server request: %s" % repr(packet))
            else:
                self.handle_frostbite_event(words)
        else:
            if isResponse:
                self.handle_frostbite_command_response(sequence, words)
            else:
                self.getLogger().warning("received a bad packet from frosbite server pretending "
                                      "being a request from us: %s" % repr(DecodePacket(packet)))

    def handle_frostbite_event(self, words):
        self.getLogger().debug("received a game event from frosbite server: %s" % repr(words))
        if self._frostbite_event_handler is not None:
            self._frostbite_event_handler(words)

    def handle_frostbite_command_response(self, command_id, words):
        self.getLogger().debug("received a response for command #%i from frosbite server: %s" % (command_id, repr(words)))
        if self._frostbite_command_response_handler is not None:
            self._frostbite_command_response_handler(command_id, words)
    

class FrostbiteServer(threading.Thread):
    """
    Thread opening a connection to a Frostbite game server and providing
    means of observing Frostbite events and sending commands
    """
    def __init__(self, host, port, password=None, command_timeout=5.0):
        threading.Thread.__init__(self, name="FrosbiteServerThread")
        self.daemon = True
        self.test_connectivity(host, port)
        self.frostbite_dispatcher = FrostbiteDispatcher(host, port)
        self._stopEvent = threading.Event()
        self.password = password
        self.command_timeout = command_timeout
        self.frostbite_dispatcher.set_frostbite_event_hander(self._on_event)
        self.frostbite_dispatcher.set_frostbite_command_response_handler(self._on_command_response)
        self.pending_commands = {}
        self.__command_reply_event = threading.Event()
        self.observers = set()
        # ok start working
        self.start()
        time.sleep(1.5)

    ####################################################################################################################
    #                                                                                                                  #
    #   PUBLIC API                                                                                                     #
    #                                                                                                                  #
    ####################################################################################################################

    def subscribe(self, func):
        """
        Add func from Frosbite events listeners.
        """
        self.observers.add(func)
        
    def unsubscribe(self, func):
        """
        Remove func from Frosbite events listeners.
        """
        self.observers.remove(func)

    def command(self, *command):
        """
        Send command to the Frostbite server in a synchronous way.
        Calling this method will block until we receive the reply packet from the
        game server or until we reach the timeout.
        """
        if not self.connected:
            raise NetworkError("not connected")
        
        self.getLogger().info("command : %s " % repr(command))
        if command is None:
            return None

        registered_ids = []

        def register_pending_command(command_id):
            # must be done before the request is sent or a fast response would be dropped as unexpected
            self.pending_commands[command_id] = None
            registered_ids.append(command_id)

        try:
            command_id = self.frostbite_dispatcher.send_command(*command, before_send=register_pending_command)
        except Exception:
            for command_id in registered_ids:
                self.pending_commands.pop(command_id, None)
            raise
        self.getLogger().debug("command #%i sent. %s " % (command_id, repr(command)))
        
        response = self._wait_for_response(command_id)
        if response[0] in ('CommandDisallowedOnRanked', 'CommandDisallowedOnOfficial'):
            raise CommandDisallowedError(response)
        elif response[0] == 'UnknownCommand':
            raise CommandUnknownCommandError(response)
        elif response[0] != "OK":
            raise CommandFailedError(response)
        else:
            return response[1:]

    def auth(self):
        """
        Authenticate on the Frosbite server with given password.
        """
        self.getLogger().info("starting authentication")
        hash_token = self.command('login.hashed')
        # Given the salt and the password, combine them and compute hash value
        salt = bytes.fromhex(hash_token[0])
        passwordHash = generatePasswordHash(salt, self.password)
        passwordHashHexString = passwordHash.hex().upper()
        # Send password hash to server
        self.command("login.hashed", passwordHashHexString)
        self.getLogger().info("authentication done")

    def close(self):
        self.frostbite_dispatcher.close()

    def stop(self):
        self._stopEvent.set()
        self.close()
    
    ####################################################################################################################
    #                                                                                                                  #
    #   OTHER METHODS                                                                                                  #
    #                                                                                                                  #
    ####################################################################################################################

    @staticmethod
    def test_connectivity(host, port):
        sock = socket.create_connection((host, port), timeout=2)
        sock.close()
    
    def __getattr__(self, name):
        if name == 'connected':
            return self.frostbite_dispatcher.connected
        else:
            raise AttributeError

    def getLogger(self):
        return logging.getLogger("FrostbiteServer")

    def isStopped(self):
        return self._stopEvent.is_set()

    def run(self):
        """
        Threaded code.
        """
        self.getLogger().info('start loop')
        try:
            while not self.isStopped():
                asyncore.loop(count=1, timeout=1)
        except KeyboardInterrupt:
            pass
        finally:
            self.frostbite_dispatcher.close()
        self.getLogger().info('end loop')

    def _on_event(self, words):
        self.getLogger().debug("received Frostbite event : %s" % repr(words))
        for func in self.observers:
            func(words)

    def _on_command_response(self, command_id, words):
        self.getLogger().debug("received Frostbite command #%i response: %s" % (command_id, repr(words)))
        if command_id not in self.pending_commands:
            self.getLogger().warning("dropping Frostbite command #%i response as we are not waiting for it anymore" % command_id)
        else:
            self.pending_commands[command_id] = words
            self.__command_reply_event.set()

    def _wait_for_response(self, command_id):
        """
        Block until response to for given command_id has been received or until timeout is reached.
        """
        expire_time = time.time() + self.command_timeout
        while not self.isStopped() and command_id in self.pending_commands and self.pending_commands[command_id] is None:
            if not self.connected:
                raise NetworkError("Lost connection to Frostbite2 server")
            if time.time() >= expire_time:
                del self.pending_commands[command_id]
                raise CommandTimeoutError("did not receive any response for sequence #%i" % command_id)
            self.getLogger().debug("waiting for some command reply #%i: %r " % (command_id, self.pending_commands))
            self.__command_reply_event.clear()
            self.__command_reply_event.wait(self.command_timeout)
        try:
            response = self.pending_commands[command_id]
            del self.pending_commands[command_id]
            return response
        except KeyError:
            raise CommandTimeoutError("did not receive any response for sequence #%i" % command_id)

########################################################################################################################
# EXAMPLE PROGRAM                                                                                                      #
########################################################################################################################
#
# if __name__ == '__main__':
#     from getopt import getopt
#     import sys
#
#     print "Remote administration event listener for Frosbite"
#     # history_file = os.path.join( os.environ["HOME"], ".bfbc2_rcon_history" )
#
#     host = None
#     port = None
#     pw = None
#     serverSocket = None
#
#     opts, args = getopt(sys.argv[1:], 'h:p:e:a:')
#     for k, v in opts:
#         if k == '-h':
#             host = v
#         elif k == '-p':
#             port = int(v)
#         elif k == '-a':
#             pw = v
#
#     if not host:
#         host = raw_input('Enter game server host IP/name: ')
#     if not port:
#         port = int(raw_input('Enter host port: '))
#     if not pw:
#         pw = raw_input('Enter password: ')
#
#
#     def run_low_level():
#         try:
#             serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#
#             print 'Connecting to port: %s:%d...' % ( host, port )
#             serverSocket.connect( ( host, port ) )
#             serverSocket.setblocking(1)
#             receiveBuffer = ''
#
#             print 'Logging in - 1: retrieving salt...'
#
#             # Retrieve this connection's 'salt' (magic value used when encoding password) from server
#             getPasswordSaltRequest = EncodeClientRequest( [ "login.hashed" ] )
#             serverSocket.send(getPasswordSaltRequest)
#
#             [getPasswordSaltResponse, receiveBuffer] = receivePacket(serverSocket, receiveBuffer)
#             printPacket(DecodePacket(getPasswordSaltResponse))
#
#             [isResponse, sequence, words] = DecodePacket(getPasswordSaltResponse)[1:]
#
#             # if the server doesn't understand "login.hashed" command, abort
#             if words[0] != "OK":
#                 sys.exit(0)
#
#             print 'Received salt: ' + words[1]
#
#             # Given the salt and the password, combine them and compute hash value
#             salt = words[1].decode("hex")
#             passwordHash = generatePasswordHash(salt, pw)
#             passwordHashHexString = passwordHash.encode("hex").upper()
#
#             print 'Computed password hash: ' + passwordHashHexString
#
#             # Send password hash to server
#             print 'Logging in - 2: sending hash...'
#
#             loginRequest = EncodeClientRequest( [ "login.hashed", passwordHashHexString ] )
#             serverSocket.send(loginRequest)
#
#             [loginResponse, receiveBuffer] = receivePacket(serverSocket, receiveBuffer)
#
#             printPacket(DecodePacket(loginResponse))
#
#             [isResponse, sequence, words] = DecodePacket(loginResponse)[1:]
#
#             # if the server didn't like our password, abort
#             if words[0] != "OK":
#                 sys.exit(0)
#
#             print 'Logged in.'
#
#             print 'Enabling events...'
#
#             enableEventsRequest = EncodeClientRequest(("admin.eventsEnabled", "true"))
#             serverSocket.send(enableEventsRequest)
#
#             [enableEventsResponse, receiveBuffer] = receivePacket(serverSocket, receiveBuffer)
#             printPacket(DecodePacket(enableEventsResponse))
#
#             [isResponse, sequence, words] = DecodePacket(enableEventsResponse)[1:]
#
#             # if the server didn't know about the command, abort
#             if words[0] != "OK":
#                 sys.exit(0)
#
#             print 'Now waiting for events.'
#
#             while True:
#                 # Wait for packet from server
#                 [packet, receiveBuffer] = receivePacket(serverSocket, receiveBuffer)
#
#                 [isResponse, sequence, words] = DecodePacket(packet)[1:]
#
#                 # If this was a command from the server, we should respond to it
#                 # For now, we always respond with an "OK"
#                 if not isResponse:
#                     response = EncodeClientResponse(sequence, ["OK"])
#                     serverSocket.send(response)
#                 else:
#                     print 'Received an unexpected response packet from server, ignoring:'
#
#                 printPacket(DecodePacket(packet))
#
#
#         except socket.error, detail:
#             print 'Network error:', detail[1]
#
#         except (EOFError, KeyboardInterrupt):
#             pass
#
#         except:
#             raise
#
#
#     def run_FrosbiteServer():
#         from b3.output import OutputHandler
#
#         FORMAT = "%(name)-20s [%(thread)-4d] %(threadName)-15s %(levelname)-8s %(message)s"
#         handler = logging.StreamHandler()
#         formatter = logging.Formatter(FORMAT)
#         handler.setFormatter(formatter)
#
#         myConsole = OutputHandler('console')
#         myConsole.addHandler(handler)
#         myConsole.setLevel(logging.NOTSET)
#
#         #logging.getLogger('FrostbiteServer').addHandler(handler)
#         #logging.getLogger('FrostbiteDispatcher').addHandler(handler)
#
#         def frosbiteEventListener(words):
#             myConsole.console(">>> %s" % words)
#
#
#         from random import sample, random
#         class CommandRequester(threading.Thread):
#             _stop = threading.Event()
#             nb_instances = 0
#             def __init__(self, frostbite_server, commands=('serverInfo',), delay=5):
#                 self.__class__.nb_instances += 1
#                 threading.Thread.__init__(self, name="CommandRequester%s" % self.__class__.nb_instances)
#                 self.frostbite_server = frostbite_server
#                 self.commands = commands
#                 self.delay = delay
#
#             def getLogger(self):
#                 return logging.getLogger("CommandRequester")
#
#             def run(self):
#                 self.getLogger().info("starting spamming commands")
#                 while not self.__class__._stop.is_set():
#                     cmd = sample(self.commands, 1)[0]
#                     self.getLogger().info("###\trequesting \t%s" % repr(cmd))
#                     try:
#                         response = self.frostbite_server.command(cmd)
#                         self.getLogger().info("###\treceived \t%s" % repr(response))
#                     except CommandFailedError, err:
#                         self.getLogger().info("###\treceived \t%s" % repr(err.message))
#                     time.sleep(self.delay + random())
#                 self.getLogger().info("stopped spamming commands")
#
#             @classmethod
#             def stopAll(cls):
#                 cls._stop.set()
#
#         logging.basicConfig(level=logging.NOTSET, format=FORMAT)
#         logging.info("here we go")
#
#         t_conn = FrostbiteServer(host, port, pw)
#         t_conn.subscribe(frosbiteEventListener)
#
#         try:
#             t_conn.auth()
#             t_conn.command('admin.eventsEnabled', 'true')
#         except FrostbiteError, err:
#             logging.error(err)
#
#         time.sleep(1)
#         CommandRequester(t_conn).start()
#         time.sleep(.5)
#         CommandRequester(t_conn, ('version', ('listPlayers', 'all'), 'serverInfo', 'login.plainText')).start()
#
#         time.sleep(5)
#         t_conn.stop()
#         CommandRequester.stopAll()
#         logging.info("here we die")
#
#     #run_low_level()
#     run_FrosbiteServer()
    