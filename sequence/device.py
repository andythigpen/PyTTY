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

from c1control import CSIEscapeSequence

class SendPrimaryDeviceAttributesEscapeSequence(CSIEscapeSequence):
    MATCH = r'>(?P<value>[0-1]*)c'

    VT100 = 0
    VT220 = 1

    def process(self, data, match):
        value = match.group('value') or 0
        self.trace.end("Send Primary Device Attributes (Secondary DA): %s" % \
                       value)
        if int(value) == 0:
            self.channel.send_keypress("\x1b[>1;2600;0c")

