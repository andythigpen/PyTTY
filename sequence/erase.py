import terminal
from sequencer import CSIEscapeSequence

class EraseInDisplayEscapeSequence(CSIEscapeSequence):
    MATCH = r'[0-3]*J'

    ERASE_BELOW = 0     # default
    ERASE_ABOVE = 1
    ERASE_ALL   = 2
    ERASE_SAVED = 3

    def process(self, data, match=None):
        value = self.ERASE_BELOW
        if data:
            value = int(data)
        self.trace.end("Erase in display (ED) [%s]" % value)
        if value == self.ERASE_BELOW:
            self.erase_below()
        elif value == self.ERASE_ABOVE:
            self.erase_above()
        elif value == self.ERASE_ALL:
            self.erase_all()
        elif value == self.ERASE_SAVED:
            self.erase_saved_lines()
            

    def erase_below(self):
        self.log.warning("Erase below not yet implemented!")

    def erase_above(self):
        self.log.warning("Erase above not yet implemented!")

    def erase_all(self):
        self.screen.clear_screen()

    def erase_saved_lines(self):
        self.log.warning("Erase saved lines not yet implemented!")
        

class EraseInLineEscapeSequence(CSIEscapeSequence):
    MATCH = r'[0-2]*K'

    ERASE_RIGHT = 0     # default
    ERASE_LEFT  = 1
    ERASE_ALL   = 2

    def process(self, data, match=None):
        value = self.ERASE_RIGHT
        if data:
            value = int(data)
        self.trace.end("Erase in Line (EL) [%s]" % value)
        if value == self.ERASE_RIGHT:
            self.erase_right()
        elif value == self.ERASE_LEFT:
            self.erase_left()
        elif value == self.ERASE_ALL:
            self.erase_all()

    def erase_right(self):
        self.log.debug("Erase to right of cursor.")
        cursor = self.screen.get_cursor()
        (row, col) = cursor.get_row_col()
        (width, height) = self.screen.get_size()
        for idx in range(col, width):
            cell = self.screen.get_cell(row, idx)
            cell.reset()
            cell.set_dirty()

    def erase_left(self):
        self.log.warning("Erase left not yet implemented.")

    def erase_all(self):
        self.log.warning("Erase left not yet implemented.")


class DeleteCharactersEscapeSequence(CSIEscapeSequence):
    MATCH = r'[0-9]*P'

    def process(self, data, match):
        times = 1
        if data:
            times = int(data)
        self.trace.end("Delete characters (DCH) [%s]" % times)
        cursor = self.screen.get_cursor()
        (row, col) = cursor.get_row_col()
        buf = self.screen.get_buffer()
        cells = buf[row][col:col + times]
        del buf[row][col:col + times]
        for cell in cells:
            cell.reset()
        buf[row].extend(cells)
        (width, height) = self.screen.get_size()
        for idx in range(col, width):
            buf[row][idx].set_dirty()


class InsertCharacterEscapeSequence(CSIEscapeSequence):
    MATCH = r'[0-9]*@'

    def process(self, data, match):
        characters = 1
        if data:
            characters = int(data)
        cursor = self.screen.get_cursor()
        (row, col) = cursor.get_row_col()
        buf = self.screen.get_buffer()
        self.log.debug("Inserting cells at %s" % col)
        cells = [buf[row].insert(col, terminal.TerminalCell()) \
                 for x in range(0, characters)]
        (width, height) = self.screen.get_size()
        cols = len(buf[row])
        if cols >= width:
            del buf[row][width:cols + 1]
        for idx in range(col, width):
            buf[row][idx].set_dirty()


class InsertLinesEscapeSequence(CSIEscapeSequence):
    MATCH = r'[0-9]*L'

    def process(self, data, match):
        lines = 1
        if data:
            lines = int(data)
        self.trace.end("Insert lines (IL) [%s]" % lines)
        self.screen.insert_row(lines)


class DeleteLinesEscapeSequence(CSIEscapeSequence):
    MATCH = r'[0-9]*M'

    def process(self, data, match):
        lines = 1
        if data:
            lines = int(data)
        self.trace.end("Delete lines (DL) [%s]" % lines)
        self.screen.delete_row(lines)


