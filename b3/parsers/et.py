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
__version__ = '0.0.6'

import re
import b3
import b3.clients
import b3.events

from b3.functions import prefixText
from b3.parsers.punkbuster import PunkBuster
from b3.parsers.q3a.abstractParser import AbstractParser

class EtParser(AbstractParser):

    gameName = 'et'
    privateMsg = False
    PunkBuster = None

    _logSync = 2

    _commands = {
        'ban': 'banid %(cid)s %(reason)s',
        'kick': 'clientkick %(cid)s %(reason)s',
        'message': 'qsay %(message)s',
        'say': 'qsay %(message)s',
        'set': 'set %(name)s %(value)s',
        'tempban': 'clientkick %(cid)s %(reason)s'
    }

    _eventMap = {
        #'warmup' : b3.events.EVT_GAME_WARMUP,
        #'restartgame' : b3.events.EVT_GAME_ROUND_END
    }

    # remove the time off of the line
    _lineClear = re.compile(r'^(?:[0-9:.]+\s?)?')

    _lineFormats = (
        # 1579:03ConnectInfo: 0: E24F9B2702B9E4A1223E905BF597FA92: ^w[^2AS^w]^2Lead: 3: 3: 24.153.180.106:2794
        re.compile(r'^(?P<action>[a-z]+):\s*'
                   r'(?P<data>(?P<cid>[0-9]+):\s*'
                   r'(?P<pbid>[0-9A-Z]{32}):\s*'
                   r'(?P<name>[^:]+):\s*'
                   r'(?P<num1>[0-9]+):\s*'
                   r'(?P<num2>[0-9]+):\s*'
                   r'(?P<ip>[0-9.]+):'
                   r'(?P<port>[0-9]+))$', re.IGNORECASE),

        # 1536:17sayc: 0: ^w[^2AS^w]^2Lead:  sorry...
        # 1536:34sayteamc: 17: ^1[^7DP^1]^4Timekiller: ^4ammo ^2here !!!!!
        re.compile(r'^(?P<action>[a-z]+):\s*(?P<data>(?P<cid>[0-9]+):\s*(?P<name>.+):\s+(?P<text>.*))$', re.IGNORECASE),

        # 1536:37Kill: 1 18 9: ^1klaus killed ^1[pura]fox.nl by MOD_MP40
        re.compile(r'^(?P<action>[a-z]+):\s*'
                   r'(?P<data>'
                   r'(?P<cid>[0-9]+)\s'
                   r'(?P<acid>[0-9]+)\s'
                   r'(?P<aweap>[0-9]+):\s*'
                   r'(?P<text>.*))$', re.IGNORECASE),

        re.compile(r'^(?P<action>[a-z]+):\s*(?P<data>(?P<cid>[0-9]+):\s*(?P<text>.*))$', re.IGNORECASE),
        re.compile(r'^(?P<action>[a-z]+):\s*(?P<data>(?P<cid>[0-9]+)\s(?P<text>.*))$', re.IGNORECASE),
        # 1101:24 ClientDisconnect: 7 (vanilla ET 2.60b: ClientConnect, ClientBegin and ClientDisconnect)
        re.compile(r'^(?P<action>[a-z]+):\s*(?P<data>(?P<cid>[0-9]+))$', re.IGNORECASE),
        re.compile(r'^(?P<action>[a-z]+):\s*(?P<data>.*)$', re.IGNORECASE)
    )

    ####################################################################################################################
    #                                                                                                                  #
    #   PARSER INITIALIZATION                                                                                          #
    #                                                                                                                  #
    ####################################################################################################################

    def startup(self):
        """
        Called after the parser is created before run().
        """
        self.clients.newClient('-1', guid=self.gameName + ':WORLD', name='World', pbid='WORLD', hide=True)
        # PunkBuster only when the server runs it: on a server without it (vanilla 2.60b as LinuxGSM installs it) its
        # empty player list made every sync drop all the connected players
        sv_punkbuster = self.getCvar('sv_punkbuster')
        if sv_punkbuster and sv_punkbuster.getBoolean():
            self.info('PunkBuster is enabled on the server: using it for the player list')
            self.PunkBuster = PunkBuster(self)
        else:
            self.info('PunkBuster is not enabled on the server: using rcon status for the player list')
            self.PunkBuster = None
        self._eventMap['warmup'] = self.getEventID('EVT_GAME_WARMUP')
        self._eventMap['restartgame'] = self.getEventID('EVT_GAME_ROUND_END')

        # force g_logsync
        self.debug('Forcing server cvar g_logsync to %s' % self._logSync)
        self.setCvar('g_logsync', self._logSync)

    # rcon status without a guid column (vanilla 2.60b, and ETPro without PunkBuster):
    # num score ping name            lastmsg address               qport rate
    # --- ----- ---- --------------- ------- --------------------- ----- -----
    #   5     0   48 B3Tester^7            0 192.0.2.15:27970       1773 25000
    _regPlayerNoGuid = re.compile(AbstractParser._regPlayer.pattern.replace(r'(?P<guid>[0-9a-zA-Z]+)\s+', ''),
                                  re.IGNORECASE)

    _reGuid = re.compile(r'^[0-9A-F]{32}$', re.IGNORECASE)

    def getStatusRegex(self, status):
        """
        Pick the player line layout from the rcon status header.
        """
        for line in status.split('\n')[:3]:
            words = line.split()
            if 'num' in words and 'name' in words:
                return self._regPlayer if 'guid' in words else self._regPlayerNoGuid
        return self._regPlayer

    def parseUserInfo(self, info):
        """
        Parse an infostring. Vanilla ET 2.60b has no ConnectInfo line: the player's guid comes from cl_guid in the
        Userinfo line, stored with the same game prefix as ConnectInfo does.
        """
        data = AbstractParser.parseUserInfo(self, info)
        cl_guid = data.get('cl_guid', '')
        if self._reGuid.match(cl_guid):
            data['guid'] = data['pbid'] = self.gameName + ':' + cl_guid.upper()
        else:
            data.pop('pbid', None)
        return data

    ####################################################################################################################
    #                                                                                                                  #
    #   EVENT HANDLERS                                                                                                 #
    #                                                                                                                  #
    ####################################################################################################################

    def OnClientuserinfo(self, action, data, match=None):
        AbstractParser.OnClientuserinfo(self, action, data, match)
        # vanilla ET: the guid arrives with the Userinfo line, after the client was created without one
        cid = data.split(' ', 1)[0]
        client = self.clients.getByCID(cid)
        if client and client.guid and not client.authed:
            client.auth()
        return None

    def OnConnectinfo(self, action, data, match=None):
        # clients are stored with a game-prefixed guid (see below): compare against the same form
        guid = self.gameName + ':' + match.group('pbid')
        client = self.clients.getByCID(match.group('cid'))
        if client:
            if client.guid == guid:
                # this is the same player

                if client.name != self.stripColors(match.group('name')):
                    # the name setter strips the color codes and keeps the colored name in exactName
                    client.name = match.group('name')
                return self.getEvent('EVT_CLIENT_JOIN', client=client)
            else:
                # disconnect the existing client
                self.verbose('disconnect the existing client %s %s => %s %s', match.group('cid'), guid, client.cid, client)
                client.disconnect()

        self.clients.newClient(match.group('cid'), guid=guid, pbid=guid, ip=match.group('ip'),
                               name=match.group('name'), state=b3.STATE_ALIVE)

    def OnClientuserinfochangedguid(self, action, data, match=None):
        client = self.clients.getByCID(match.group('cid'))
        cid, pbid, data = data.split(' ', 2)
        bclient = self.parseUserInfo(cid + ' ' + data)
        if bclient and client:
            # update the existing client
            for k, v in bclient.items():
                setattr(client, k, v)

    def OnGib(self, action, data, match=None):
        victim = self.clients.getByCID(match.group('cid'))
        if not victim:
            self.debug('No victim')
            #self.OnJ(action, data, match)
            return None

        attacker = self.clients.getByCID(match.group('acid'))
        if not attacker:
            self.debug('No attacker')
            return None

        event_key = 'EVT_CLIENT_GIB'
        if attacker.cid == victim.cid:
            event_key = 'EVT_CLIENT_GIB_SELF'
        elif attacker.team != b3.TEAM_UNKNOWN and attacker.team == victim.team:
            event_key = 'EVT_CLIENT_GIB_TEAM'

        return self.getEvent(event_key, (100, match.group('aweap'), ''), attacker, victim)

    def OnKill(self, action, data, match=None):
        victim = self.clients.getByCID(match.group('cid'))
        if not victim:
            self.debug('No victim')
            #self.OnJ(action, data, match)
            return None

        attacker = self.clients.getByCID(match.group('acid'))
        if not attacker:
            self.debug('No attacker')
            return None

        event_key = 'EVT_CLIENT_KILL'
        if attacker.cid == victim.cid:
            event_key = 'EVT_CLIENT_SUICIDE'
        elif attacker.team != b3.TEAM_UNKNOWN and attacker.team == victim.team:
            event_key = 'EVT_CLIENT_KILL_TEAM'

        return self.getEvent(event_key, (100, match.group('aweap'), ''), attacker, victim)

    def OnSayteamc(self, action, data, match=None):
        #1536:34sayteamc: 17: ^1[^7DP^1]^4Timekiller: ^4ammo ^2here !!!!!
        client = self.clients.getByCID(match.group('cid'))
        if not client:
            self.debug('no client - attempt join')
            #self.OnJ(action, data, match)
            #client = self.clients.getByCID(match.group('cid'))
            #if not client:
            return None

        return self.getEvent('EVT_CLIENT_TEAM_SAY', match.group('text'), client)

    def OnSayc(self, action, data, match=None):
        #1536:17sayc: 0: ^w[^2AS^w]^2Lead:  sorry...
        client = self.clients.getByCID(match.group('cid'))
        if not client:
            self.debug('no client - attempt join')
            #self.OnJ(action, data, match)
            #client = self.clients.getByCID(match.group('cid'))
            #if not client:
            return None

        return self.getEvent('EVT_CLIENT_SAY', match.group('text'), client)

    ####################################################################################################################
    #                                                                                                                  #
    #   B3 PARSER INTERFACE IMPLEMENTATION                                                                             #
    #                                                                                                                  #
    ####################################################################################################################

    def message(self, client, text):
        """
        Send a private message to a client.
        :param client: The client to who send the message.
        :param text: The message to be sent.
        """
        if client is None:
            # do a normal say
            self.say(text)
            return

        if client.cid is None:
            # skip this message
            return

        lines = []
        message = prefixText([self.msgPrefix, self.pmPrefix], text)
        message = message.strip()
        for line in self.getWrap(message):
            lines.append(self.getCommand('message', message=line))
        self.writelines(lines)

    def getNextMap(self):
        pass