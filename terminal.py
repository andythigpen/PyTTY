#!/usr/bin/env python
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

import os
import sys
import log
import select
import paramiko
from PyQt4 import QtGui, QtCore
from config import TerminalConfig
from cursor import TerminalCursor
from sequencer import TerminalEscapeSequencer, ScrollDirection

class TerminalCell:
    def __init__(self):
        self.log = log.get_log(self)
        self.config = TerminalConfig()
        font_name = self.config.get("Display", "font", "Consolas")
        font_size = self.config.getint("Display", "fontsize", 11)
        self.font = QtGui.QFont(font_name, font_size)
        self.reset()

    def __str__(self):
        return self.ch or ""

    def __unicode__(self):
        return unicode(self.ch)

    def draw(self, painter, position, inverse=False):
        bgcolor = self.bgcolor if not inverse else self.fgcolor
        fgcolor = self.fgcolor if not inverse else self.bgcolor
        painter.fillRect(position, bgcolor)
        if self.ch:
            painter.setFont(self.font)
            painter.setPen(fgcolor)
            painter.drawText(position, QtCore.Qt.AlignLeft, self.ch)

    def draw_background(self, painter, position):
        painter.fillRect(position, self.bgcolor)

    def draw_text(self, painter, position, text):
        painter.setFont(self.font)
        painter.setPen(self.fgcolor)
        painter.drawText(position, QtCore.Qt.AlignLeft, text)

    def background_matches(self, cell):
        return cell.bgcolor == self.bgcolor

    def foreground_matches(self, cell):
        return cell.fgcolor == self.fgcolor and \
               cell.font == self.font
               #cell.font.bold() == self.font.bold() and \
               #cell.underline == self.underline

    def reset(self):
        #self.font = QtGui.QFont('Consolas', 11)
        self.fgcolor = QtGui.QColor(255, 255, 255)
        self.bgcolor = QtGui.QColor(0, 0, 0)
        self.ch = ''
        self.font.setBold(False)
        self.underline = False
        self.dirty = False
        self.selected = False
        self.has_data = False

    def set_font(self, font):
        self.font = QtGui.QFont(font)

    def set_fgcolor(self, color):
        self.fgcolor = color

    def set_bgcolor(self, color):
        self.bgcolor = color

    def get_fgcolor(self):
        return self.fgcolor

    def get_bgcolor(self):
        return self.bgcolor

    def set_underline(self, underline=True):
        self.underline = underline

    def set_bold(self, bold=True):
        self.font.setBold(True)

    def set_inverse(self):
        (self.fgcolor, self.bgcolor) = (self.bgcolor, self.fgcolor)

    def set_character(self, ch):
        self.ch = ch
        self.has_data = True

    def get_character(self):
        return self.ch

    def set_dirty(self, dirty=True):
        self.dirty = dirty

    def is_dirty(self):
        return self.dirty

    def toggle_selection(self):
        self.selected = not self.selected
        self.set_inverse()


class TerminalRow(list):
    def __init__(self, width, screen):
        list.__init__(self)
        self.log = log.get_log(self)
        self.width = width
        self.screen = screen
        cells = [TerminalCell() for x in xrange(0, self.width)]
        self.extend(cells)

    #FIXME optimize this function
    def expand(self, width):
        if width < len(self):
            # don't resize the row
            self.width = width
            return
        diff = width - len(self)
        #self.log.debug("Adding %s cells to row." % diff)
        for cnt in xrange(0, diff):
            self.append(TerminalCell())
        self.width = width

    def draw(self, painter, row):
        prev = self[0]
        rect = self.screen.create_rect_from_cell(row, 0)
        for col in xrange(1, self.width):
            cell = self[col]
            if cell.background_matches(prev):
                # merge the drawing of two cells
                new_rect = self.screen.create_rect_from_cell(row, col)
                rect = rect.unite(new_rect)
            else:
                # we encountered a new background color
                prev.draw_background(painter, rect)
                rect = self.screen.create_rect_from_cell(row, col)
            prev = cell
        prev.draw_background(painter, rect)

        prev = self[0]
        rect = self.screen.create_rect_from_cell(row, 0)
        text = unicode(self[0])
        for col in xrange(1, self.width):
            cell = self[col]
            if cell.foreground_matches(prev):
                # merge the drawing of two cells
                new_rect = self.screen.create_rect_from_cell(row, col)
                rect = rect.unite(new_rect)
                text += unicode(self[col])
            else:
                # we encountered a new foreground color
                prev.draw_text(painter, rect, text)
                rect = self.screen.create_rect_from_cell(row, col)
                text = unicode(self[col])
            prev = cell
        prev.draw_text(painter, rect, text)

    def reset(self):
        for cell in self:
            cell.reset()
            cell.dirty = True

    def set_dirty(self, dirty=True):
        def inner(x):
            x.dirty = dirty
        map(inner, self)
                

class ScreenBuffer:
    def __init__(self, width=80, height=24, parent=None):
        self.log = log.get_log(self)
        self.width = width      # in cells, not pixels
        self.height = height
        self.parent = parent
        self.config = TerminalConfig()
        self.font_name = self.config.get("Display", "font", "Consolas")
        self.font_size = self.config.getint("Display", "fontsize", 11)
        self.cursor = TerminalCursor(self, self.font_name, self.font_size)
        self.scrollback = self.config.getint("Display", "scrollback", 100)
        self.base = 0
        self.alternate_active = False
        self.create_buffer()
        self.create_alternate_buffer()
        self.setup_timer_events()
        (self.col_size, self.row_size) = self.cursor.get_font_metrics()

    @staticmethod
    def get_default_size():
        config = TerminalConfig()
        font_name = config.get("Display", "font", "Consolas")
        font_size = config.getint("Display", "fontsize", 11)
        cursor = TerminalCursor(None, font_name, font_size)
        (col_size, row_size) = cursor.get_font_metrics()
        return (80 * col_size, 24 * row_size)

    def setup_timer_events(self):
        self.blink_cursor_timer = QtCore.QTimer()
        self.blink_cursor_timer.timeout.connect(self.blink_cursor_cb)
        self.blink_cursor_active = True
        self.draw_cursor = True
        self.blink_speed = self.config.getint("Cursor", "blinkms", 600)
        self.blink_cursor_timer.start(self.blink_speed)

    def blink_cursor_cb(self):
        if not self.blink_cursor_active:
            return
        self.draw_cursor = not self.draw_cursor
        position = self.cursor.position()
        self.parent.update(position)

    def blink_cursor(self, blink=True):
        self.blink_cursor_active = blink
        self.draw_cursor = True
        position = self.cursor.position()
        self.parent.update(position)
        self.reset_blink_timer()

    def show_cursor(self, show=True):
        self.blink_cursor_active = show
        self.draw_cursor = show
        position = self.cursor.position()
        self.parent.update(position)
        self.reset_blink_timer()

    def reset_blink_timer(self):
        self.blink_cursor_timer.start(self.blink_speed)

    def get_widget(self):
        return self.parent

    def create_buffer(self):
        self.buffer = []
        for row in xrange(0, self.height + self.scrollback):
            self.buffer.append(TerminalRow(self.width, self))
        self.log.debug("Buffer size = %s" % len(self.buffer))

    def create_alternate_buffer(self):
        self.alternate = []
        for row in xrange(0, self.height):
            self.alternate.append(TerminalRow(self.width, self))
        self.set_buffer_scroll_range(0, self.height)

    def insert_row(self, num=1):
        buf = self.get_buffer()
        (row, col) = self.cursor.get_row_col()
        new_rows = [TerminalRow(self.width, self) for x in xrange(0, num)]
        buf.insert(row, '')
        buf[row:row + 1] = new_rows
        self.log.debug("Inserted %s row(s): %s" % (num, len(buf)))

        # delete rows that are greater than the scroll_bottom
        scroll_top = self.get_scroll_top()
        scroll_bottom = self.get_scroll_bottom()
        del buf[scroll_bottom:scroll_bottom + num]
        self.parent.update()

    def delete_row(self, num=1):
        buf = self.get_buffer()
        (row, col) = self.cursor.get_row_col()
        del buf[row:row + num]
        self.log.debug("Deleted %s row(s): %s" % (num, len(buf)))

        # insert new blank rows
        scroll_bottom = self.get_scroll_bottom() - num
        new_rows = [TerminalRow(self.width, self) for x in xrange(0, num)]
        buf.insert(scroll_bottom, '')
        buf[scroll_bottom:scroll_bottom + 1] = new_rows
        self.parent.update()

    def get_buffer(self):
        if self.alternate_active:
            return self.alternate
        return self.buffer

    def is_alternate_buffer(self):
        return self.alternate_active

    def resize(self, width, height):
        '''Width and height in cells, not pixels. May change this...'''
        #FIXME creating new rows/cells when the height/width changes is
        # very expensive...investigate other methods of resizing the buffers
        # without having to create new objects each time...
        self.log.debug("Resizing screen to %s, %s" % (width, height))
        if height > self.height:
            diff = height - self.height
            for cnt in xrange(0, diff):
                self.buffer.append(TerminalRow(width, self))
            self.log.debug("Resized buffer size = %s" % len(self.buffer))

        if width > self.width:
            self.log.debug("Increasing width of screen buffer to %s." % width)
            for row in xrange(0, height + self.scrollback):
                self.buffer[row].expand(width)

        if height < len(self.alternate):
            diff = len(self.alternate) - height 
            del self.alternate[-diff:]
            self.log.debug("Deleted %s rows from alt buffer, len = %s" % \
                              (diff, len(self.alternate)))
        elif height > len(self.alternate):
            diff = height - len(self.alternate)
            for cnt in xrange(0, diff):
                self.alternate.append(TerminalRow(width, self))
            self.log.debug("Added %s rows to alt buffer, len = %s" % \
                             (diff, len(self.alternate)))

        if width < len(self.alternate[0]):
            diff = len(self.alternate[0]) - width
            for row in xrange(0, len(self.alternate)):
                del self.alternate[row][-diff:]
                self.alternate[row].width = width
            self.log.debug("Deleted %s cols from alt buffer, len = %s" % \
                              (diff, len(self.alternate[0])))
        elif width > len(self.alternate[0]):
            diff = width - len(self.alternate[0])
            for row in xrange(0, len(self.alternate)):
                self.alternate[row].expand(width)
            self.log.debug("Added %s cols to alt buffer, len = %s" % \
                             (diff, len(self.alternate[0])))

        self.width = width
        self.height = height
        self.buffer_scroll_top = 0
        self.buffer_scroll_bottom = height

    def get_cursor(self):
        return self.cursor

    def save_cursor(self):
        self.saved_cursor = self.cursor     # DECSC
        self.cursor = TerminalCursor(self, self.font_name, self.font_size)

    def restore_cursor(self):
        if not hasattr(self, 'saved_cursor'):
            self.log.warning("Trying to restore unsaved cursor!!!")
            return
        cell = self.cursor.get_cell()
        cell.set_dirty()
        self.cursor = self.saved_cursor
        del self.saved_cursor       # DECRC
        cell = self.cursor.get_cell()
        cell.set_dirty()

    def get_size(self):
        return (self.width, self.height)

    def get_pixel_size(self):
        return (self.width * self.col_size, self.height * self.row_size)

    def get_cells_from_rect(self, rect):
        (top, left) = (rect.top(), rect.left())
        (bottom, right) = (rect.bottom(), rect.right())
        x = left / self.col_size
        y = (top / self.row_size)
        y += self.base
        dx = (right / self.col_size) + 1
        dy = (bottom / self.row_size) + 1
        dy += self.base
        buf = self.get_buffer()
        if dy > len(buf):
            dy = len(buf)
        return (y, x, dy, dx)

    def get_cell_from_point(self, point):
        x = point.x()
        y = point.y()
        ret = (self.base + int(y / self.row_size), int(x / self.col_size))
        if ret[0] < 0:
            ret = (0, ret[1])
        if ret[1] < 0:
            ret = (ret[0], 0)
        return ret

    def create_rect_from_cell(self, row, col):
        top = (row - self.base) * self.row_size
        left = col * self.col_size
        return QtCore.QRect(left, top, self.col_size, self.row_size)

    def draw(self, painter, event):
        (top, left, bottom, right) = self.get_cells_from_rect(event.rect())
        self.log.debug("Redrawing (%s,%s) to (%s,%s)" % (top, left, 
                                                         bottom, right))
        row_range = range(top, bottom)
        row_range.reverse()
        buf = self.get_buffer()
        for row in row_range:
            buf[row].draw(painter, row)

        cursor_pos = self.cursor.position()
        if self.draw_cursor and cursor_pos.intersects(event.rect()):
            self.cursor.draw(painter)

    def is_rect_adjacent(r1, r2):
        if 0 <= r1.top() - r2.bottom() <= 1:
            return True
        if 0 <= r2.top() - r1.bottom() <= 1:
            return True
        if 0 <= r1.left() - r2.right() <= 1:
            return True
        if 0 <= r2.left() - r1.right() <= 1:
            return True
        return False
    is_rect_adjacent = staticmethod(is_rect_adjacent)

    def repaint_dirty_cells(self):
        rect = None
        top = self.base
        buf_size = self.get_buffer_size()
        bottom = top + self.height
        buf_size = self.get_buffer_size()
        if bottom > buf_size:
            bottom = buf_size
        buf = self.get_buffer()
        for row in xrange(top, bottom):
            for col in xrange(0, self.width):
                try:
                    cell = buf[row][col]
                except:
                    self.log.exception()
                    self.log.error("row = %s, col = %s" % (row, col))
                    return
                if not cell.dirty:
                    continue
                cell.dirty = False
                if rect is None:
                    rect = self.create_rect_from_cell(row, col)
                else:
                    new_rect = self.create_rect_from_cell(row, col)
                    if new_rect.intersects(rect) or \
                       ScreenBuffer.is_rect_adjacent(rect, new_rect):
                        rect = rect.unite(new_rect)
                    else:
                        self.parent.update(rect)
                        rect = new_rect
        if rect is not None:
            self.parent.update(rect)

    def set_window_title(self, title):
        if self.parent is None:
            return
        self.parent.setWindowTitle(title)

    def get_cell(self, row, col):
        '''Retrieves a TerminalCell object from this screen buffer.'''
        buf = self.get_buffer()
        try:
            return buf[row][col]
        except IndexError as e:
            self.log.error("IndexError (%s,%s)" % (row, col))
            raise e

    def scroll(self, direction=ScrollDirection.DOWN, times=1):
        if direction == ScrollDirection.DOWN:
            self.scroll_down(times)
        elif direction == ScrollDirection.UP:
            self.scroll_up(times)
        else:
            self.log.error("Unknown scroll direction")

    def scroll_up(self, times=1):
        if self.alternate_active:
            scroll_top = self.get_scroll_top()
            scroll_bottom = self.get_scroll_bottom()
            buf = self.get_buffer()
            first = scroll_top
            last = scroll_bottom - 1

            rows = [TerminalRow(self.width, self) for x in range(0, times)]
            del buf[last:last + times]
            buf.insert(first, '')
            buf[first:first + 1] = rows

            self.parent.update()
            return

        self.base -= times
        if self.base < 0:
            self.base = 0
        self.log.debug("Scrolling screen buffer, base = %s, row = %s" % \
                       (self.base, self.cursor.row))
        self.parent.update()
        self.parent.set_scroll_value(self.base)

    def scroll_down(self, times=1):
        if self.alternate_active:
            scroll_top = self.get_scroll_top()
            scroll_bottom = self.get_scroll_bottom()
            buf = self.get_buffer()
            first = scroll_top
            last = scroll_bottom - 1

            rows = [TerminalRow(self.width, self) for x in xrange(0, times)]
            del buf[first:first + times]
            buf.insert(last, '')
            buf[last:last + 1] = rows

            repaint_buf = buf[first:last + 1]
            self.parent.update()
            return

        self.base += times
        self.log.debug("Scrolling screen buffer, base = %s, row = %s" % \
                       (self.base, self.cursor.row))
        if (self.base - times) >= self.scrollback:
            self.log.debug("Scrollback exceeded...rolling over buffer.")
            self.base -= times
            del self.buffer[0:times]
            rows = [TerminalRow(self.width, self) for x in xrange(0, times)]
            self.buffer.extend(rows)
        self.parent.set_scroll_value(self.base)
        self.parent.update()

    def set_buffer_scroll_range(self, top, bottom):
        '''Do not use this to set scroll ranges for the widget. 
           This is used by the sequencer to manipulate text in the buffer.
           It does not affect the graphical scroll bar at all.
           top, bottom should not be zero-offset. 
        '''
        self.buffer_scroll_top = top
        self.buffer_scroll_bottom = bottom

    def clear_screen(self):
        if self.alternate_active:
            for row in self.alternate:
                row.reset()
            return
        self.log.debug("Clear Screen")
        #self.scroll_bar.setRange(0, self.base)
        #self.scroll_bar.setValue(self.base)
        (row, col) = self.cursor.get_row_col()
        times = row - self.base
        if self.base >= self.scrollback:
            self.scroll_down(times)
            self.log.debug("Setting cursor to (%s, %s)" % (row, col))
            self.cursor.set_row_col(self.base, col)
        else:
            self.scroll_down(times)
        #self.parent.set_scroll_value(self.base)

    def get_base_row(self):
        return self.base

    def get_buffer_size(self):
        if self.alternate_active:
            return len(self.alternate)
        # buffer size may actually be larger than height + scrollback...
        return self.height + self.scrollback

    def get_scroll_bottom(self):
        if self.alternate_active:
            if hasattr(self, "buffer_scroll_bottom"):
                return self.buffer_scroll_bottom
        screen_bottom = self.base + self.height
        buf_size = self.get_buffer_size()
        if screen_bottom > buf_size:
            return buf_size
        return buf_size

    def get_scroll_top(self):
        if self.alternate_active:
            if hasattr(self, "buffer_scroll_top"):
                return self.buffer_scroll_top
        return self.base

    def set_alternate_buffer(self, alternate=True):
        self.log.debug("Set alternate buffer: %s" % alternate)
        self.alternate_active = alternate
        if alternate:
            self.saved_scroll_values = self.parent.get_scroll_value()
            self.saved_base = self.base
            self.base = 0
        elif hasattr(self, 'saved_scroll_values'):
            self.parent.set_scroll_value(*self.saved_scroll_values)
            del self.saved_scroll_values
            self.base = self.saved_base
            del self.saved_base
        self.parent.update()

    def print_debug(self):
        # this is an expensive function, so we skip it if we are not logging 
        # debug anyway
        if self.log.get_level() > log.Log.DEBUG:
            return
        debug = ""
        buff = self.buffer if not self.alternate_active else self.alternate
        bottom = len(buff)
        for row in xrange(0, bottom):
            debug += u"%03d: " % row
            for col in xrange(0, self.width):
                debug += unicode(buff[row][col]) or u' '
            debug += u"\n"
        self.log.debug("Screen buffer contents:\n%s" % debug)

    def set_cursor_keys(self, application=True):
        self.application_cursor_keys = application

    def process_keypress(self, event):
        if hasattr(self, 'application_cursor_keys') and \
           self.application_cursor_keys:
            return self.__process_application_cursor_keys(event)
        else:
            return self.__process_normal_cursor_keys(event)

    def __process_normal_cursor_keys(self, event):
        if event.key() == QtCore.Qt.Key_Up:
            return '\x1b[A'
        elif event.key() == QtCore.Qt.Key_Down:
            return '\x1b[B'
        elif event.key() == QtCore.Qt.Key_Right:
            return '\x1b[C'
        elif event.key() == QtCore.Qt.Key_Left:
            return '\x1b[D'
        elif event.key() == QtCore.Qt.Key_Home:
            return '\x1b[H'
        elif event.key() == QtCore.Qt.Key_End:
            return '\x1b[F'
        return False
 
    def __process_application_cursor_keys(self, event):
        if event.key() == QtCore.Qt.Key_Up:
            return '\x1bOA'
        elif event.key() == QtCore.Qt.Key_Down:
            return '\x1bOB'
        elif event.key() == QtCore.Qt.Key_Right:
            return '\x1bOC'
        elif event.key() == QtCore.Qt.Key_Left:
            return '\x1bOD'
        elif event.key() == QtCore.Qt.Key_Home:
            return '\x1bOH'
        elif event.key() == QtCore.Qt.Key_End:
            return '\x1bOF'
        return False

    def clear_selection(self):
        if hasattr(self, 'selection_start'):
            del self.selection_start
        buf = self.get_buffer()
        for row in xrange(0, len(buf)):
            for col in xrange(0, len(buf[row])):
                cell = buf[row][col]
                if cell.selected:
                    cell.toggle_selection()
                    rect = self.create_rect_from_cell(row, col)
                    self.parent.update(rect)

    def set_selection_start(self, top, left):
        self.clear_selection()
        cell = self.get_cell(top, left)
        cell.toggle_selection()
        rect = self.create_rect_from_cell(top, left)
        self.parent.update(rect)
        self.selection_start = (top, left)

    def set_selection_to_cell(self, top, left):
        if not hasattr(self, 'selection_start'):
            return
        self.cursor.save_row_col()
        self.cursor.set_row_col(*self.selection_start)
        while self.cursor.get_row_col() != (top, left):
            cell = self.cursor.get_cell()
            if not cell.selected:
                cell.toggle_selection()
                self.parent.update(self.cursor.position())
            if (top == self.selection_start[0] and \
               left >= self.selection_start[1]) or \
               top > self.selection_start[0]:
                self.cursor.advance_column(scroll=False)
            else:
                self.cursor.previous_column(scroll=False)
        cell = self.cursor.get_cell()
        if not cell.selected:
            cell.toggle_selection()
            self.parent.update(self.cursor.position())
        self.cursor.restore_row_col()

    def get_selection_text(self):
        text = ""
        buf = self.get_buffer()
        cell = None
        for row in xrange(0, len(buf)):
            for col in xrange(0, len(buf[row])):
                cell = buf[row][col]
                if cell.selected:
                    text += cell.ch
            if cell and cell.selected and not cell.has_data:
                text += '\n'
        return text

    def find_word(self, top, left):
        word_separators = [' ', ':', '.', ',', '[', ']', '(', ')', '<', 
                           '>', '!', '`']
        cell = self.get_cell(top, left)
        first = (top, left)
        last = (top, left)
        if cell.ch in word_separators:
            return (first, last)

        (row, col) = (top, left)
        is_eol = not self.get_cell(row, col).has_data
        while first > (self.base, 0):
            col -= 1
            if col < 0:
                col = self.width - 1
                row -= 1
            if row < self.base:
                row = self.base
                col = 0
                break
            cell = self.get_cell(row, col)
            if not is_eol and not cell.has_data:
                col = 0
                row += 1
                break
            if cell.ch in word_separators:
                col += 1
                break
            while not cell.has_data and col > 0:
                is_eol = True
                col -= 1
                cell = self.get_cell(row, col)
                if cell.has_data:
                    col += 1
            if is_eol:
                break
        first = (row, col)

        (row, col) = (top, left)
        is_eol = not self.get_cell(row, col).has_data
        while last < (self.base + self.height - 1, self.width - 1):
            col += 1
            cell = self.get_cell(row, col)
            if cell.ch in word_separators:
                col -= 1
                break
            if not cell.has_data and not is_eol:
                col -= 1
                break
            while not cell.has_data and col < self.width - 1:
                col += 1
                cell = self.get_cell(row, col)
            if not cell.has_data:
                break
        last = (row, col)
        return (first, last)


class TerminalWidget(QtGui.QWidget):
    DEBUG_MARK = 1

    # signals
    titleChanged = QtCore.pyqtSignal(str)
    closing = QtCore.pyqtSignal()

    def __init__(self, channel, parent=None):
        '''channel should be a TerminalChannel object.'''
        QtGui.QWidget.__init__(self, parent)
        self.log = log.get_log(self)
        self.config = TerminalConfig()
        self.scroll_bar_width = self.config.getint("Display", 
                                                   "scrollbarsize", 14)
        self.focus_on_output = self.config.getboolean("Cursor",
                                                      "focusonoutput", True)
        #self.setWindowTitle(APP_NAME)
        self.screen = ScreenBuffer(parent=self)
        self.scroll_bar = QtGui.QScrollBar(self)
        self.scroll_bar.valueChanged.connect(self.scrollEvent)
        (width, height) = self.screen.get_pixel_size()
        self.resize(width + self.scroll_bar_width, height)
        self.channel = channel 
        self.channel.dataReceived.connect(self.write)
        self.channel.endOfDataBlock.connect(self.mark_end_of_data)
        self.channel.endOfFile.connect(self.close)
        self.sequencer = TerminalEscapeSequencer(self.screen, self.channel)
        self.dirty = False
        cursor = self.screen.get_cursor()
        (self.col_size, self.row_size) = cursor.get_font_metrics()
        self.setCursor(QtCore.Qt.IBeamCursor)
        self.clipboard = QtGui.QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.clipboard_changed)
        self.word_select_mode = False

    @staticmethod
    def get_default_size():
        config = TerminalConfig()
        scroll_bar_width = config.getint("Display", "scrollbarsize", 14)
        (width, height) = ScreenBuffer.get_default_size()
        width += scroll_bar_width
        return (width, height)

    def close(self):
        self.log.debug("End of file received")
        self.closing.emit()
        QtGui.QWidget.close(self)

    def write(self, data):
        self.end_of_data_block = False
        if hasattr(self, "recorder"):
            self.recorder.write(data)
        self.sequencer.process(data)
        self.screen.repaint_dirty_cells()

        if self.focus_on_output:
            cursor = self.screen.get_cursor()
            (row, col) = cursor.get_row_col()
            (width, height) = self.screen.get_size()
            base = self.screen.base
            if row >= base + height:
                self.screen.scroll_down(row - (base + height) + 1)

    def mark_end_of_data(self):
        self.end_of_data_block = True
        self.screen.blink_cursor()          # start blinking again
        if hasattr(self, 'dirty') and self.dirty:
            self.update()
            self.dirty = False
        else:
            self.screen.repaint_dirty_cells()

    def set_dirty(self):
        '''Means that the display needs to be completely repainted.'''
        if self.end_of_data_block:
            self.update()
            self.dirty = False
        else:
            self.dirty = True

    def event(self, event):
        if event.type() == QtCore.QEvent.KeyPress:
            if event.key() == QtCore.Qt.Key_Tab or \
               event.key() == QtCore.Qt.Key_Backtab:
                self.log.debug("Tab button pressed")
                event.accept()
                self.keyPressEvent(event)
                return True
        return QtGui.QWidget.event(self, event)

    def keyPressEvent(self, event):
        processed = self.screen.process_keypress(event)
        if processed:
            self.channel.send_keypress(processed)
        elif event.key() == QtCore.Qt.Key_F5:
            self.repaint()
        elif event.key() == QtCore.Qt.Key_F6:
            self.screen.print_debug()
        elif event.key() == QtCore.Qt.Key_F7:
            self.log.debug("======== Mark %s ========" % self.DEBUG_MARK)
            self.DEBUG_MARK += 1
        elif event.key() == QtCore.Qt.Key_F8:   # insert a breakpoint
            if hasattr(self, "recorder"):
                self.recorder.write('\x1b\x1F')
        elif event.key() == QtCore.Qt.Key_V and \
             event.modifiers() == (QtCore.Qt.ShiftModifier | \
                                   QtCore.Qt.ControlModifier):
            self.log.warning("paste")
            self.channel.send_keypress(str(self.clipboard.text()))
        else:
            self.log.debug("Keypress: %s" % event.text())
            self.channel.send_keypress(event.text())
        self.screen.blink_cursor(False)     # stop blinking while keypress
        #self.scroll_to(-1)

    def mousePressEvent(self, event):
        self.mouse_selection_start = event.pos()
        self.screen.clear_selection()

    def mouseReleaseEvent(self, event):
        if self.mouse_selection_start != event.pos():
            self.clipboard.setText(self.screen.get_selection_text())
        self.word_select_mode = False

    def mouseDoubleClickEvent(self, event):
        self.mouse_select_start = event.pos()
        (top, left) = self.screen.get_cell_from_point(event.pos())
        (first, last) = self.screen.find_word(top, left)
        self.screen.set_selection_start(*first)
        self.screen.set_selection_to_cell(*last)
        self.clipboard.setText(self.screen.get_selection_text())
        self.word_select_mode = True

    def mouseMoveEvent(self, event):
        start = self.mouse_selection_start
        diff = start - event.pos()
        if abs(diff.x()) >= (self.col_size / 2) or \
           abs(diff.y()) >= (self.row_size / 2): 
            (top, left) = self.screen.get_cell_from_point(start)
            cell = self.screen.get_cell(top, left)
            if not cell.has_data or self.word_select_mode:
                (top, left) = self.screen.find_word(top, left)[0]
            self.screen.set_selection_start(top, left)
        (top, left) = self.screen.get_cell_from_point(event.pos())
        cell = self.screen.get_cell(top, left)
        if not cell.has_data or self.word_select_mode:
            num = 1 if diff.y() < 0 else 0
            (top, left) = self.screen.find_word(top, left)[num]
        self.screen.set_selection_to_cell(top, left)

    def clipboard_changed(self):
        if self.clipboard.ownsClipboard():
            return
        self.screen.clear_selection()

    def paintEvent(self, event):
        painter = QtGui.QPainter()
        if not painter.begin(self):
            self.log.warning("paintEvent...Unable to paint widget!!!")
            return
        try:
            cursor = self.screen.get_cursor()
            painter.fillRect(event.rect(), cursor.bgcolor)
            self.screen.draw(painter, event)
        except:
            self.log.exception()
            self.screen.print_debug()
        painter.end()

    def resizeEvent(self, event):
        self.scroll_bar.resize(self.scroll_bar_width, self.height())
        self.scroll_bar.move(self.width() - self.scroll_bar.width(),
                             self.height() - self.scroll_bar.height())
        self.scroll_bar.setRange(0, self.screen.base) 
        cursor = self.screen.get_cursor()
        (col_size, row_size) = cursor.get_font_metrics()
        cols = (self.width() - self.scroll_bar.width()) / col_size
        rows = self.height() / row_size
        self.log.debug("Resizing to (%s, %s)" % (rows, cols))
        self.screen.resize(cols, rows)
        self.channel.resize(cols, rows)
        (row, col) = cursor.get_row_col()
        bottom = self.screen.base + rows
        if row >= bottom:
            self.screen.base += (row - bottom + 1)
        self.update()

    def wheelEvent(self, event):
        self.scroll_bar.wheelEvent(event)

    def scrollEvent(self, value):
        self.screen.base = value
        self.update()

    def set_scroll_value(self, maximum, value=None):
        self.log.debug("Setting scroll range to (0, %s)" % maximum)
        self.scroll_bar.setRange(0, maximum)
        if value is None:
            value = maximum
        self.log.debug("Setting scroll value to (%s)" % value)
        self.scroll_bar.setValue(value)

    def get_scroll_value(self):
        maximum = self.scroll_bar.maximum()
        value = self.scroll_bar.value()
        return (maximum, value)

    def setWindowTitle(self, title):
        self.titleChanged.emit(title)
        return QtGui.QWidget.setWindowTitle(self, title)


class TerminalChannel(QtCore.QObject):
    '''Terminal channels should subclass this and emit dataReceived when 
       data is sent to the terminal and endOfFile when the terminal wants to
       exit.'''
    dataReceived = QtCore.pyqtSignal(str)
    endOfDataBlock = QtCore.pyqtSignal()
    endOfFile = QtCore.pyqtSignal()

    def __init__(self):
        QtCore.QObject.__init__(self)
        self.log = log.get_log(self)

    def resize(self, width, height):
        '''Subclasses should implement.'''
        pass

    def send_keypress(self, key):
        '''Subclasses should implement.'''
        pass


class SSHConnection(TerminalChannel):
    def __init__(self, addr, port, name, passwd):
        TerminalChannel.__init__(self)
        self.addr = addr
        self.port = port
        self.name = name
        self.passwd = passwd
        self.connected = False
        self.authentication_error = False
        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(paramiko.WarningPolicy())
        self.config = TerminalConfig()

    def connect(self):
        try:
            self.client.connect(self.addr, self.port, self.name, self.passwd)
            self.connected = True
        except paramiko.AuthenticationException:
            self.connected = False
            self.authentication_error = True
        except Exception:
            self.log.exception()
            self.connected = False
        del self.addr
        del self.port
        del self.name
        del self.passwd

    def is_connected(self):
        return self.connected
        
    def __del__(self):
        if hasattr(self, 'channel'):
            self.channel.close()
        if hasattr(self, 'client'):
            self.client.close()

    def resize(self, width, height):
        if not self.connected:
            self.log.error("Trying to resize, but not yet connected.")
            return
        self.channel.resize_pty(width, height)

    def send_keypress(self, key):
        if not self.connected:
            self.log.error("Trying to send keypress, but not yet connected.")
            return
        try:
            #self.log.debug("Sending %s" % key)
            self.channel.send(key)
        except EOFError:
            pass

    class SSHConnectionThread(QtCore.QThread):
        def __init__(self, parent, sock, term):
            QtCore.QThread.__init__(self)
            self.log = log.get_log(self)
            self.parent = parent
            self.sock = sock
            self.term = term

        def run(self):
            self.log.debug("Running connection thread")
            received = False
            while True:
                (rlist, wlist, xlist) = select.select([self.sock], [], [], 0.05)
                if self.sock in rlist:
                    data = self.sock.recv(4096)
                    if not data:
                        self.log.info("*** EOF ***")
                        self.parent.endOfFile.emit()
                        break
                    self.log.debug("Received: %s" % data.replace('\x1b', 
                                   '\\x1b'))
                    self.parent.dataReceived.emit(data)
                    received = True
                elif received:
                    self.parent.endOfDataBlock.emit()
                    received = False

    def start_shell(self, term):
        if not self.connected:
            self.log.error("Trying to start shell, but not yet connected.")
            return
        self.log.debug("Starting connection thread")
        term_name = self.config.get("Sequencer", "type", "xterm")
        self.channel = self.client.invoke_shell(term=term_name)
        self.connection_thread = SSHConnection.SSHConnectionThread(self, 
                                                        self.channel, term)
        self.connection_thread.start()


class SSHTerminalWidget(TerminalWidget):
    def __init__(self, username, password, host, port=22, parent=None):
        channel = SSHConnection(host, port, username, password)
        TerminalWidget.__init__(self, channel, parent)

    def connect(self):
        self.log.debug("Connection attempt initiated.")
        self.channel.connect()
        if not self.channel.is_connected():
            self.log.warning("Unable to connect.")
            return
        self.log.debug("Starting shell.")
        self.channel.start_shell(self)


'''
if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-r", "--record", dest="record", action="store",
                      type="string",
                      help="record terminal sequences for playback later.")
    (options, args) = parser.parse_args()

    print "Starting pytty"
    try:
        os.remove('output.log')
    except OSError:
        pass
    config = TerminalConfig()

    # set the application wide default log level
    log_level = config.get("Log", "level", "none")
    log.Log.DEFAULT_LOG_LEVEL = log.Log.LEVELS[log_level]

    # start the application
    app = QtGui.QApplication(sys.argv)
    widget = SSHTerminalWidget('andyt', 'mnkey3', 'localhost')
    if options.record:
        widget.recorder = open(options.record, 'w')
    widget.show()
    sys.exit(app.exec_())
'''
