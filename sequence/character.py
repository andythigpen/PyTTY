from PyQt4 import QtGui
from sequencer import CSIEscapeSequence

class CharacterAttributeEscapeSequence(CSIEscapeSequence):
    MATCH = r'(?P<value>([0-9]+;*)+)*m'

    COLORS_256 = {}
    COLORS = {
        30: QtGui.QColor(0, 0, 0),
        31: QtGui.QColor(205, 0, 0),
        32: QtGui.QColor(0, 205, 0),
        33: QtGui.QColor(205, 205, 0),
        34: QtGui.QColor(0, 0, 238),
        35: QtGui.QColor(205, 0, 205),
        36: QtGui.QColor(0, 205, 205),
        37: QtGui.QColor(229, 229, 229),
        90: QtGui.QColor(127, 127, 127),
        91: QtGui.QColor(255, 0, 0),
        92: QtGui.QColor(0, 255, 0),
        93: QtGui.QColor(255, 255, 0),
        94: QtGui.QColor(92, 92, 255),
        95: QtGui.QColor(255, 0, 255),
        96: QtGui.QColor(0, 255, 255),
        97: QtGui.QColor(255, 255, 255),
    }

    def __init__(self, *args, **kwargs):
        CSIEscapeSequence.__init__(self, *args, **kwargs)
        self.__generate_256_colors()

    def process(self, data, match):
        values = match.group('value')
        self.trace.end("Character Attributes (SGR) [%s]" % values)
        cursor = self.screen.get_cursor()
        if not data: 
            self.log.debug("Resetting character attributes.")
            cursor.reset_attributes()
            return
        options = values.split(';')
        idx = 0
        while idx < len(options):
            option = options[idx]
            if int(option) == 0:
                self.log.debug("Resetting character attributes.")
                cursor.reset_attributes()
            elif int(option) == 1:
                self.log.debug("Set bold on")
                cursor.set_bold()
            elif int(option) == 4:
                self.log.debug("Set underline on")
                cursor.set_underline()
            elif int(option) == 7:
                self.log.debug("Set inverse on")
                cursor.set_inverse()
            elif int(option) == 27:
                self.log.debug("Set inverse off")
                cursor.set_inverse(False)
            elif int(option) >= 30 and int(option) <= 37:
                self.log.debug("Set foreground to %s" % option)
                cursor.set_cell_foreground(self.COLORS[int(option)])
            elif int(option) >= 40 and int(option) <= 47:
                self.log.debug("Set background to %s" % option)
                cursor.set_cell_background(self.COLORS[int(option) - 10])
            elif int(option) == 38 or int(option) == 48:
                idx += 1
                if not int(options[idx]) == 5:
                    self.log.warning("Unknown extended color: ", option)
                    idx += 1 
                    continue
                idx += 1
                if int(option) == 38:
                    self.log.debug("Set foreground to %s" % options[idx])
                    cursor.set_cell_foreground(
                            self.COLORS_256[int(options[idx])])
                else:
                    self.log.debug("Set background to %s" % options[idx])
                    cursor.set_cell_background(
                            self.COLORS_256[int(options[idx])])
            elif int(option) >= 90 and int(option) <= 97:
                self.log.debug("Set foreground to %s" % option)
                cursor.set_cell_foreground(self.COLORS[int(option)])
            elif int(option) >= 100 and int(option) <= 107:
                self.log.debug("Set background to %s" % option)
                cursor.set_cell_background(self.COLORS[int(option) - 10])
            idx += 1

    def __generate_256_colors(self):
        if self.COLORS_256.has_key(16):
            # we already generated it, no need to do it again
            return
        for jdx in range(0, 8):
            self.COLORS_256[jdx] = self.COLORS[jdx + 30]
        for jdx in range(0, 8):
            self.COLORS_256[8 + jdx] = self.COLORS[jdx + 90]
        idx = 16
        for r in range(0, 6):
            for g in range(0, 6):
                for b in range(0, 6):
                    red = 95 + (40 * (r - 1)) if r > 0 else 0
                    green = 95 + (40 * (g - 1)) if g > 0 else 0
                    blue = 95 + (40 * (b - 1)) if b > 0 else 0
                    self.COLORS_256[idx] = QtGui.QColor(red, green, blue)
                    idx += 1
        for idx in range(232, 256):
            grey = ((idx - 232) * 10) + 8
            self.COLORS_256[idx] = QtGui.QColor(grey, grey, grey)

