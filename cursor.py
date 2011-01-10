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

import log
from PyQt4 import QtGui, QtCore
from sequencer import ScrollScreenException, ScrollDirection

class TerminalCursor:
    CURSOR_COLOR = QtGui.QColor(0, 255, 0)

    def __init__(self, parent, font_name='Consolas', font_size=11):
        self.log = log.get_log(self)
        self.row = 0
        self.col = 0
        self.parent = parent
        self.set_font(font_name, font_size)
        self.reset_attributes()
        self._cursor_pos_stack = []
        self.replace_mode = True
        if self.parent is not None:
            self.widget = self.parent.get_widget()

    def set_font(self, name, size=10):
        self.font = QtGui.QFont(name, size)
        self._calculate_font_metrics()

    def get_font(self):
        return self.font

    def _calculate_font_metrics(self):
        metrics = QtGui.QFontMetrics(self.font)
        self.col_size = metrics.width('a')
        self.row_size = metrics.height()
        self.log.debug("Font metrics: (%s, %s)" % \
                (self.col_size, self.row_size))

    def get_font_metrics(self):
        return (self.col_size, self.row_size)

    def set_cell_foreground(self, color):
        self.fgcolor = color

    def set_cell_background(self, color):
        self.bgcolor = color

    def set_bold(self, bold=True):
        self.font.setBold(bold)

    def set_underline(self, underline=True):
        self.underline = underline

    def set_inverse(self, inverse=True):
        self.inverse = inverse

    def set_wraparound(self, wrap=True):
        self.wrap = wrap

    def set_replace_mode(self, replace=True):
        self.replace_mode = replace

    def reset_attributes(self):
        self.fgcolor = QtGui.QColor(255, 255, 255)
        self.bgcolor = QtGui.QColor(0, 0, 0)
        self.font.setBold(False)
        self.underline = False
        self.inverse = False
        self.wrap = True

    def reset_cell(self):
        cell = self.get_cell()
        cell.reset()
        self.widget.update(self.position())

    def previous_column(self, scroll=True):
        old_pos = self.position()
        self.col -= 1
        (width, height) = self.parent.get_size()
        if self.col < 0:
            if self.wrap:
                self.col = width - 1
                self.previous_row(scroll=scroll)
            else:
                self.col = 0
        new_pos = self.position()
        self.widget.update(old_pos)
        self.widget.update(new_pos)

    def previous_row(self, scroll=True, reset_col=False):
        old_pos = self.position()
        self.row -= 1
        if reset_col:
            self.col = 0
        scroll_top = self.parent.get_scroll_top()
        if scroll and self.row < scroll_top:
            if self.row < 0:
                self.row = 0
            raise ScrollScreenException(direction=ScrollDirection.UP)
        if self.row < 0:
            self.row = 0
        new_pos = self.position()
        self.parent.get_widget().update(old_pos)
        self.parent.get_widget().update(new_pos)

    def advance_column(self, scroll=True):
        old_pos = self.position()
        self.col += 1
        (width, height) = self.parent.get_size()
        if self.col >= width:
            if self.wrap:
                self.col = 0
                self.advance_row(scroll=scroll)
            else:
                self.col = width - 1
        new_pos = self.position()
        self.widget.update(old_pos)
        self.widget.update(new_pos)

    def advance_row(self, scroll=True, reset_col=True):
        old_pos = self.position()
        self.row += 1
        if reset_col:
            self.col = 0
        scroll_bottom = self.parent.get_scroll_bottom()
        self.log.debug("Advance row: scroll_bottom=%s, row=%s, scroll=%s" % \
                (scroll_bottom, self.row, scroll))
        if scroll and self.row >= scroll_bottom: #(base + height):
            buffer_size = self.parent.get_buffer_size()
            if self.row >= buffer_size:
                self.row = buffer_size - 1
            raise ScrollScreenException()
        new_pos = self.position()
        self.widget.update(old_pos)
        self.widget.update(new_pos)

    def up(self, num=1):
        self.parent.reset_blink_timer()
        if self.row == 0:
            return
        old_pos = self.position()
        self.row -= num
        new_pos = self.position()
        self.widget.update(old_pos)
        self.widget.update(new_pos)

    def down(self, num=1):
        self.parent.reset_blink_timer()
        (width, height) = self.parent.get_size()
        base = self.parent.get_base_row()
        if self.row + num >= (base + height):
            self.row = (base + height) - 1
            return
        old_pos = self.position()
        self.row += num
        new_pos = self.position()
        self.widget.update(old_pos)
        self.widget.update(new_pos)

    def left(self, num=1):
        self.parent.reset_blink_timer()
        if self.col == 0:
            return
        old_pos = self.position()
        self.col -= num
        new_pos = self.position()
        self.widget.update(old_pos)
        self.widget.update(new_pos)

    def right(self, num=1):
        self.parent.reset_blink_timer()
        (width, height) = self.parent.get_size()
        if self.col + num >= width:
            self.col = width - 1 
            return
        old_pos = self.position()
        self.col += num
        new_pos = self.position()
        self.widget.update(old_pos)
        self.widget.update(new_pos)

    def set_row_col(self, row, col):
        old_pos = self.position()
        self.col = col
        self.row = row
        new_pos = self.position()
        self.widget.update(old_pos)
        self.widget.update(new_pos)

    def get_row_col(self):
        return (self.row, self.col)

    def reset_position(self):
        if self.parent.is_alternate_buffer():
            old_pos = self.position()
            self.row = 0
            self.col = 0
            new_pos = self.position()
            self.widget.update(old_pos)
            self.widget.update(new_pos)
        else:
            times = self.row - self.parent.get_base_row()
            self.parent.scroll(times=times)

    def reset_col(self):
        old_pos = self.position()
        self.col = 0
        new_pos = self.position()
        self.widget.update(old_pos)
        self.widget.update(new_pos)

    def reset_row(self):
        old_pos = self.position()
        self.row = 0
        new_pos = self.position()
        self.widget.update(old_pos)
        self.widget.update(new_pos)

    def position(self):
        base = self.parent.get_base_row()
        return QtCore.QRect(self.col * self.col_size, 
                            (self.row - base) * self.row_size,
                            self.col_size, self.row_size)

    def write(self, ch, advance=True):
        if not self.replace_mode:
            self.log.warning("Inserting cell")
            self.parent.insert_cell(self.row, self.col)
        cell = self.get_cell() 
        cell.set_fgcolor(self.fgcolor)
        cell.set_bgcolor(self.bgcolor)
        cell.set_character(ch)
        cell.set_font(self.font)
        if self.inverse:
            cell.set_inverse()
        self.widget.update(self.position())
        if cell.selected:
            self.parent.clear_selection()
            cell.toggle_selection()
        self.log.debug("Writing '%s' to (%s, %s)" % \
                        (ch, self.row, self.col))
        if advance:
            self.log.none("Advancing column after write.")
            self.advance_column()

    def get_cell(self):
        return self.parent.get_cell(self.row, self.col)

    def draw(self, painter):
        position = self.position()
        cell = self.get_cell()
        cell.draw(painter, position, inverse=True)

    def save_row_col(self):
        self._cursor_pos_stack.append((self.row, self.col))

    def restore_row_col(self):
        if len(self._cursor_pos_stack) == 0:
            self.log.warning("Trying to restore unsaved cursor position!")
            return
        (self.row, self.col) = self._cursor_pos_stack.pop()

