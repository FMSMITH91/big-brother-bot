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

import logging
import unittest
from b3.clients import Client
from b3.parser import Parser


class DummyParser(Parser):

    gameName = "dummy"

    def __init__(self):
        pass # skip parent class constructor
        self.log = logging.getLogger("output")


class Test_getMessage(unittest.TestCase):

    def setUp(self):
        self.parser = DummyParser()
        self.parser._messages = {}

    def test_unknown_msg__falls_back_on_default(self):
        self.parser._messages = {}
        self.parser._messages_default = {"f00": "lorem ipsum"}
        self.assertEqual("lorem ipsum", self.parser.getMessage("f00"))

    def test_no_parameter(self):
        self.parser._messages['f00'] = "bar"
        self.assertEqual("bar", self.parser.getMessage('f00'))

    def test_with_parameter(self):
        self.parser._messages['f00'] = "bar %s"
        self.assertEqual("bar joe", self.parser.getMessage('f00', 'joe'))

    def test_with_unexpected_parameter(self):
        self.parser._messages['f00'] = "bar"
        self.assertRaises(TypeError, self.parser.getMessage, 'f00', 'joe')

    def test_with_dict_parameter(self):
        self.parser._messages['f00'] = "bar %(p1)s"
        self.assertEqual("bar joe", self.parser.getMessage('f00', {'p1': 'joe'}))

    def test_with_missing_dict_parameter(self):
        self.parser._messages['f00'] = "bar %(p1)s"
        self.assertRaises(KeyError, self.parser.getMessage, 'f00', {'p2': 'joe'})

    def test_with_unicode_dict_parameter(self):
        self.parser._messages['f00'] = "bar %(p1)s"
        self.assertEqual("bar joéÄ", self.parser.getMessage('f00', {'p1': 'joéÄ'}))



class Test_getMessageVariables(unittest.TestCase):

    def setUp(self):
        self.parser = DummyParser()

    def test_with_parameters(self):
        client = Client(name="Jack")
        rv = self.parser.getMessageVariables(client)
        self.assertDictContainsSubset({'name': client.name}, rv, rv)

    def test_with_named_parameters(self):
        client = Client(name="Jack")
        self.assertDictContainsSubset({'clientname': client.name, 'reason': 'this is a good reason'}, self.parser.getMessageVariables(client=client, reason="this is a good reason"))

    def test_with_named_parameters__unicode(self):
        client = Client(name="ÄÖé")
        self.assertDictContainsSubset({'clientname':client.name, 'reason': 'this is a good reason'}, self.parser.getMessageVariables(client=client, reason="this is a good reason"))


class Test_getWrap(unittest.TestCase):

    def setUp(self):
        self.parser = DummyParser()

    def test_wrapped_initialized(self):
        self.parser._use_color_codes = False
        self.parser._line_length = 40
        self.parser._line_color_prefix = ''
        wrapped_text = self.parser.getWrap("TEST")
        self.assertIsNotNone(self.parser.wrapper)

    def test_with_invalid_input(self):
        self.parser._use_color_codes = False
        self.parser._line_length = 40
        self.parser._line_color_prefix = ''
        wrapped_text = self.parser.getWrap(None)
        self.assertListEqual(wrapped_text, [])

    def test_with_empty_string(self):
        self.parser._use_color_codes = False
        self.parser._line_length = 40
        self.parser._line_color_prefix = ''
        wrapped_text = self.parser.getWrap(None)
        self.assertListEqual(wrapped_text, [])

    def test_no_color_codes(self):
        self.parser._use_color_codes = False
        self.parser._line_length = 40
        self.parser._line_color_prefix = ''
        wrapped_text = self.parser.getWrap("Lorem ipsum dolor sit amet, consectetur adipisci elit, sed eiusmod tempor incidunt ut labore et dolore magna aliqua.")
        self.assertIsInstance(wrapped_text, list)
        self.assertListEqual(wrapped_text, ["Lorem ipsum dolor sit amet, consectetur",
                                            ">adipisci elit, sed eiusmod tempor",
                                            ">incidunt ut labore et dolore magna",
                                            ">aliqua."])

    def test_no_color_codes_with_color_prefix_set(self):
        self.parser._use_color_codes = False
        self.parser._line_length = 40
        self.parser._line_color_prefix = '^5'
        wrapped_text = self.parser.getWrap("Lorem ipsum dolor sit amet, consectetur adipisci elit, sed eiusmod tempor incidunt ut labore et dolore magna aliqua.")
        self.assertIsInstance(wrapped_text, list)
        self.assertListEqual(wrapped_text, ["Lorem ipsum dolor sit amet, consectetur",
                                            ">adipisci elit, sed eiusmod tempor",
                                            ">incidunt ut labore et dolore magna",
                                            ">aliqua."])

    def test_with_color_codes_and_color_prefix(self):
        self.parser._use_color_codes = True
        self.parser._line_length = 40
        self.parser._line_color_prefix = '^7'
        wrapped_text = self.parser.getWrap("Lorem ipsum dolor sit ^2amet, consectetur adipisci elit, ^1sed eiusmod ^7tempor incidunt ut ^8labore et dolore magna ^2aliqua.")
        self.assertIsInstance(wrapped_text, list)
        self.assertListEqual(wrapped_text, ["^7Lorem ipsum dolor sit ^2amet,",
                                            "^3>^2consectetur adipisci elit, ^1sed eiusmod",
                                            "^3>^1^7tempor incidunt ut ^8labore et dolore",
                                            "^3>^8magna ^2aliqua."])

    def test_with_color_codes_and_no_color_prefix(self):
        self.parser._use_color_codes = True
        self.parser._line_length = 40
        self.parser._line_color_prefix = ''
        wrapped_text = self.parser.getWrap("Lorem ipsum dolor sit ^2amet, consectetur adipisci elit, ^1sed eiusmod ^7tempor incidunt ut ^8labore et dolore magna ^2aliqua.")
        self.assertIsInstance(wrapped_text, list)
        self.assertListEqual(wrapped_text, ["Lorem ipsum dolor sit ^2amet,",
                                            "^3>^2consectetur adipisci elit, ^1sed eiusmod",
                                            "^3>^1^7tempor incidunt ut ^8labore et dolore",
                                            "^3>^8magna ^2aliqua."])

    def test_with_short_message_length(self):
        self.parser._use_color_codes = False
        self.parser._line_length = 40
        self.parser._line_color_prefix = ''
        wrapped_text = self.parser.getWrap("Lorem ipsum dolor sit amet")
        self.assertIsInstance(wrapped_text, list)
        self.assertListEqual(wrapped_text, ["Lorem ipsum dolor sit amet"])


if __name__ == '__main__':
    unittest.main()


from tests import B3TestCase


class Test_read_game_log(B3TestCase):
    """
    The game server may still be writing the last line when B3 reads the log: that fragment must be held back
    and joined with the rest on the next read, not parsed as two broken lines.
    """

    def setUp(self):
        import tempfile
        B3TestCase.setUp(self)
        self.console.encoding = 'utf-8'
        fd, self.path = tempfile.mkstemp()
        os_module = __import__('os')
        os_module.close(fd)
        self.addCleanup(os_module.remove, self.path)
        self.console.input = open(self.path, 'rb')
        self.addCleanup(self.console.input.close)

    def append(self, data):
        with open(self.path, 'ab') as f:
            f.write(data)

    def test_partial_line_with_split_utf8_character(self):
        self.append('L 1: say "hello"\nL 2: say "Pl'.encode('utf-8') + b'\xc3')  # half of the 2-byte 'ä'
        self.assertEqual(['L 1: say "hello"\n'], self.console.read())
        self.assertEqual([], self.console.read())  # nothing new: the fragment stays buffered
        self.append(b'\xa4yer"\n')
        self.assertEqual(['L 2: say "Pl\u00e4yer"\n'], self.console.read())

    def test_complete_lines_are_returned_immediately(self):
        self.append(b'a\nb\n')
        self.assertEqual(['a\n', 'b\n'], self.console.read())

    def test_str_input_still_supported(self):
        # FakeConsole and older code paths feed str lines
        self.assertEqual(['x\n'], self.console.completeLines(['x\n', 'partial']))
        self.assertEqual(['partial rest\n'], self.console.completeLines([' rest\n']))


class Test_getWrap_only_color_codes(unittest.TestCase):
    """
    Text made only of color codes (or whitespace) wraps to nothing: on parsers which strip color codes
    (csgo, insurgency, ravaged...) this used to raise IndexError.
    """

    def setUp(self):
        self.parser = DummyParser()
        self.parser._line_length = 40
        self.parser._line_color_prefix = ''

    def test_only_color_codes_without_color_codes_support(self):
        self.parser._use_color_codes = False
        self.assertListEqual([], self.parser.getWrap('^7'))
        self.assertListEqual([], self.parser.getWrap('   '))

    def test_only_color_codes_without_color_codes_support_multiline(self):
        self.parser._use_color_codes = False
        self.parser._multiline = True
        self.assertListEqual([], self.parser.getWrap('^7'))


class Test_formatTime(B3TestCase):

    def setUp(self):
        B3TestCase.setUp(self)
        self.console.config._config_parser.add_section('b3')
        self.console.config._config_parser.set('b3', 'time_format', '%Y-%m-%d %H:%M')

    def test_numeric_offset_is_in_hours(self):
        # !time +4 at 1970-01-01 00:00 UTC
        self.assertEqual('1970-01-01 04:00', self.console.formatTime(0, '+4'))
        self.assertEqual('1970-01-01 05:30', self.console.formatTime(0, '5.5'))
        self.assertEqual('1969-12-31 21:00', self.console.formatTime(0, '-3'))

    def test_timezone_name(self):
        self.assertEqual('1970-01-01 01:00', self.console.formatTime(0, 'CET'))


class Test_load_config_delays(B3TestCase):

    def setUp(self):
        B3TestCase.setUp(self)
        self.console.config._config_parser.add_section('server')

    def load(self, delay):
        self.console.config._config_parser.set('server', 'delay', delay)
        self.console.load_config_delays()
        return self.console.delay

    def test_valid_delay(self):
        self.assertEqual(0.5, self.load('0.5'))

    def test_negative_delay_falls_back_to_default(self):
        # time.sleep(-1) would crash the main loop
        self.assertEqual(Parser.delay, self.load('-1'))

    def test_zero_delay_falls_back_to_default(self):
        # the main loop would busy-spin
        self.assertEqual(Parser.delay, self.load('0'))


class Test_critical(unittest.TestCase):
    """
    Parser.critical() must shut down B3 properly before exiting: the logger used to call sys.exit() itself so
    shutdown()/finalize() never ran.
    """

    def test_output_handler_critical_does_not_exit(self):
        import b3.output
        logger = b3.output.OutputHandler('test_critical')
        logger.addHandler(logging.NullHandler())
        logger.critical('something bad happened')  # must not raise SystemExit

    def test_parser_critical_shuts_down(self):
        from unittest.mock import patch
        import b3.output
        parser = DummyParser()
        parser.log = b3.output.OutputHandler('test_parser_critical')
        parser.log.addHandler(logging.NullHandler())
        with patch.object(parser, 'shutdown') as shutdown_mock, \
                patch.object(parser, 'finalize') as finalize_mock, \
                patch('b3.parser.time.sleep'):
            with self.assertRaises(SystemExit) as ctx:
                parser.critical('something bad happened')
        self.assertEqual(220, ctx.exception.code)
        self.assertEqual(220, parser.exitcode)
        shutdown_mock.assert_called_once_with()
        finalize_mock.assert_called_once_with()
