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

from sequencer import CSIEscapeSequence

class DECPrivateModeSetEscapeSequence(CSIEscapeSequence):
    MATCH = r'\?(?P<value>([0-9]+;*)+)h'

    def process(self, data, match):
        values = match.group('value')
        self.trace.end("DEC Private Mode Set (DECSET) [%s]" % values)
        for val in values.split(';'):
            if int(val) == 1:
                self.screen.set_cursor_keys(application=True)
            elif int(val) == 7:
                cursor = self.screen.get_cursor()
                cursor.set_wraparound(wrap=True)
            elif int(val) == 12:
                self.screen.blink_cursor(True)
            elif int(val) == 25:
                self.screen.show_cursor(True)
            elif int(val) == 1049:
                self.screen.save_cursor()
                self.screen.set_alternate_buffer(True)
            else:
                self.log.warning("Unknown DEC Private Mode Set value: %s" % \
                                 value)


class DECPrivateModeResetEscapeSequence(CSIEscapeSequence):
    MATCH = r'\?(?P<value>([0-9]+;*)+)l'

    def process(self, data, match):
        values = match.group('value')
        self.trace.end("DEC Private Mode Set (DECRST) [%s]" % values)
        for val in values.split(';'):
            if int(val) == 1:
                self.screen.set_cursor_keys(application=False)
            elif int(val) == 7:
                cursor = self.screen.get_cursor()
                cursor.set_wraparound(wrap=False)
            elif int(val) == 12:
                self.screen.blink_cursor(False)
            elif int(val) == 25:
                self.screen.show_cursor(False)
            elif int(val) == 1049:
                self.screen.set_alternate_buffer(False)
                self.screen.restore_cursor()
            else:
                self.log.warning("Unknown DEC Private Mode Reset value: %s" % \
                                 value)

