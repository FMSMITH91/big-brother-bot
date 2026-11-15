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

from textwrap import dedent
from unittest.mock import Mock
from unittest.mock import patch

from b3.config import CfgConfigParser
from b3.plugins.translator import TranslatorPlugin
from tests.plugins.translator import TranslatorTestCase


class Test_service(TranslatorTestCase):

    def init(self, settings):
        self.conf = CfgConfigParser()
        self.conf.loadFromString(dedent("[settings]\n" + settings + "\n[commands]\ntranslate: reg\n"))
        self.p = TranslatorPlugin(self.console, self.conf)
        self.p.onLoadConfig()

    def test_google_is_the_default(self):
        self.init("")
        self.assertEqual('google', self.p.settings['service'])

    @patch('b3.plugins.translator.requests.post')
    def test_libretranslate(self, post):
        # chat text can stay on the server: LibreTranslate is self-hostable
        self.init("service: libretranslate\nlibretranslate_url: http://127.0.0.1:5000/\nlibretranslate_api_key: k3y")
        post.return_value = Mock(status_code=200, json=Mock(return_value={'translatedText': 'Test message'}))
        self.assertEqual('Test message', self.p.translate('Messaggio di prova', 'it', 'en-EN'))
        post.assert_called_once_with('http://127.0.0.1:5000/translate', timeout=10, json={
            'q': 'Messaggio di prova', 'source': 'it', 'target': 'en', 'format': 'text', 'api_key': 'k3y'})

    @patch('b3.plugins.translator.requests.post')
    def test_libretranslate_error(self, post):
        self.init("service: libretranslate\nlibretranslate_url: https://lt.example.com")
        post.return_value = Mock(status_code=400, json=Mock(return_value={'error': 'bad language'}))
        self.assertIsNone(self.p.translate('Messaggio di prova', 'xx', 'en'))
        self.assertNotIn('api_key', post.call_args[1]['json'])

    def test_warns_about_plain_http_to_another_host(self):
        with patch.object(TranslatorPlugin, 'warning') as warning:
            self.init("service: libretranslate\nlibretranslate_url: http://lt.example.com")
        self.assertIn('https', warning.call_args[0][0])
