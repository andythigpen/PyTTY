'''
    Copyright 2010, Andrew Thigpen

    This file is part of PyTTY.

    PyTTY is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    PyTTY is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with PyTTY.  If not, see <http://www.gnu.org/licenses/>.
'''

import binascii
from c1control import DCSEscapeSequence

class DCSRequestEscapeSequence(DCSEscapeSequence):
    MATCH = r'\+q(?P<total>(?P<one>[0-9a-fA-F]{2})(?P<two>[0-9a-fA-F]{2}))'

    __terminfo = {
        'ku' : '\x1bOA',
        'kd' : '\x1bOB',
        'kr' : '\x1bOC',
        'kl' : '\x1bOD',
        'k1' : '\x1bOP',
        'k2' : '\x1bOQ',
        'k3' : '\x1bOR',
        'k4' : '\x1bOS',
        'k5' : '\x1b[15~',
        'k6' : '\x1b[17~',
        'k7' : '\x1b[18~',
        'k8' : '\x1b[19~',
        'k9' : '\x1b[20~',
        'kP' : '\x1b[5~',
        'kN' : '\x1b[6~',
    }

    def __init__(self, *args, **kwargs):
        DCSEscapeSequence.__init__(self, *args, **kwargs)
        self.colors = self.config.get("Display", "colors", '256')

    def process(self, data, match):
        terminfo = binascii.a2b_hex(match.group('one')) + \
                   binascii.a2b_hex(match.group('two'))
        response = '\x1bP'
        if terminfo == 'Co':
            response += '1+r%s=%s\x1b\\' % (match.group('total'), 
                        binascii.b2a_hex(self.colors))
        elif terminfo in self.__terminfo:
            response += '1+r%s=%s\x1b\\' % (match.group('total'),
                        binascii.b2a_hex(self.__terminfo[terminfo]))
        else:
            self.log.warning("Unknown DCS code [%s]: %s" % (terminfo, 
                             data.replace('\x1b', '\\x1b')))
            response += '0+r%s\x1b\\' % match.group('total')
        self.channel.send_keypress(response)

