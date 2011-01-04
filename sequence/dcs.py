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
    #MATCH = r'(?P<value>([0-9]+;*)+)*m'
    MATCH = r'\+q(?P<one>[0-9a-fA-F]{2})(?P<two>[0-9a-fA-F]{2})'

    def process(self, data, match):
        terminfo = binascii.a2b_hex(match.group('one')) + \
                   binascii.a2b_hex(match.group('two'))
        self.__process_request(terminfo)

    def __process_request(self, terminfo):
        if terminfo == 'Co':
            # colors
            pass
