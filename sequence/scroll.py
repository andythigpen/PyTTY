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

class ScrollingRegionEscapeSequence(CSIEscapeSequence):
    MATCH = r'((?P<top>[0-9]+);(?P<bottom>[0-9]+))*r'

    def process(self, data, match):
        top = match.group('top') 
        bottom = match.group('bottom')
        self.trace.end("Set scrolling region (%s, %s)" % (top, bottom))
        (width, height) = self.screen.get_size()
        if top is None and bottom is None:
            self.screen.set_buffer_scroll_range(0, height)
        else:
            self.screen.set_buffer_scroll_range(int(top), int(bottom))
        cursor = self.screen.get_cursor()
        cursor.reset_position()

