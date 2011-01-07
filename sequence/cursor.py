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

class CursorUpEscapeSequence(CSIEscapeSequence):
    MATCH = r'[0-9]*A'

    def process(self, data, match=None):
        times = 1
        if data:
            times = int(data)
        self.trace.end("Cursor Up (CUU) [%s]" % times)
        cursor = self.screen.get_cursor()
        cursor.up(times)

class CursorDownEscapeSequence(CSIEscapeSequence):
    MATCH = r'[0-9]*B'

    def process(self, data, match=None):
        times = 1
        if data:
            times = int(data)
        self.trace.end("Cursor Down (CUD) [%s]" % times)
        cursor = self.screen.get_cursor()
        cursor.down(times)

class CursorRightEscapeSequence(CSIEscapeSequence):
    MATCH = r'[0-9]*C'

    def process(self, data, match=None):
        times = 1
        if data:
            times = int(data)
        self.trace.end("Cursor Right (CUF) [%s]" % times)
        cursor = self.screen.get_cursor()
        cursor.right(times)

class CursorLeftEscapeSequence(CSIEscapeSequence):
    MATCH = r'[0-9]*D'

    def process(self, data, match=None):
        times = 1
        if data:
            times = int(data)
        self.trace.end("Cursor Left (CUB) [%s]" % times)
        cursor = self.screen.get_cursor()
        cursor.left(times)

class CursorPositionEscapeSequence(CSIEscapeSequence):
    MATCH = r'((?P<row>[0-9]+);(?P<col>[0-9]+))*H'

    def process(self, data, match=None):
        row = match.group('row') or 1
        col = match.group('col') or 1
        self.trace.end("Cursor Position (CUP) (%s, %s)" % (row, col))
        cursor = self.screen.get_cursor()
        if row == 1 and col == 1:
            cursor.reset_position()
        else:
            cursor.set_row_col(int(row) - 1, int(col) - 1)

class CursorCharacterAbsoluteEscapeSequence(CSIEscapeSequence):
    MATCH = r'[0-9]*G'

    def process(self, data, match=None):
        col = 1
        if data:
            col = int(data)
        self.trace.end("Cursor Character Absolute (CHA) (%s)" % col)
        cursor = self.screen.get_cursor()
        (row, old_col) = cursor.get_row_col()
        cursor.set_row_col(row, col - 1)

