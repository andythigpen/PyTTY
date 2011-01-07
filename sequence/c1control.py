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

import re
from sequencer import EscapeSequence, IncompleteEscapeException, UnsupportedEscapeException, TraceEndSequence, ScrollScreenException

class CSIEscapeSequence(EscapeSequence):
    MATCH = r'\x1b\['

    def __init__(self, screen, channel):
        EscapeSequence.__init__(self, screen, channel)
        self.__sequences = {}
        for subclass in self.__class__.__subclasses__():
            inst = subclass(screen, channel)
            last_ch = inst.MATCH[-1]
            if not last_ch in self.__sequences:
                self.__sequences[last_ch] = []
            self.__sequences[last_ch].append(inst)

    def process(self, data, match=None):
        m = re.match("(?P<value>[^@-~]*)(?P<postfix>[@-~]{1})", data)
        if not m:
            raise IncompleteEscapeException()
        postfix = m.group('postfix')
        self.log.debug("CSI postfix: %s" % postfix)
        if postfix in self.__sequences:
            for seq in self.__sequences[postfix]:
                seq_m = re.match(seq.MATCH, m.group(0))
                if seq_m:
                    self.log.debug("Processing CSI escape with: %s" % \
                                   seq.__class__.__name__)
                    try:
                        seq.process(m.group('value'), match=seq_m)
                    except TraceEndSequence:
                        pass
                    return len(m.group(0))
        self.log.error("Did not find matching sequence for %s" % m.group(0))
        raise UnsupportedEscapeException(m.end(), data[:m.end()])


class OSCEscapeSequence(EscapeSequence):
    MATCH = r'\x1b\]'

    def process(self, data, match=None):
        self.log.debug("OSC")
        m = re.match(r"(?P<value>.*?)(\x07|\x1b\\)", data)
        if not m:
            raise IncompleteEscapeException()
        value = m.group('value')
        length = len(m.group(0))
        if not value:
            self.log.warning("Missing value for OSC escape: %s" % \
                             value.replace('\x1b', '\\x1b'))
            return length
        options = value.split(';')
        if len(options) != 2:
            self.log.error("Unknown OSC sequence: ", 
                           value.replace('\x1b', '\\x1b'))
            return length
        if options[0] == '0' or options[0] == '2':
            self.log.debug("Setting window title to: %s" % options[1])
            self.screen.set_window_title(options[1])
        return length


class DCSEscapeSequence(EscapeSequence):
    MATCH = r'\x1bP'

    def __init__(self, screen, channel):
        EscapeSequence.__init__(self, screen, channel)
        self.__sequences = [] 
        for subclass in self.__class__.__subclasses__():
            inst = subclass(screen, channel)
            self.__sequences.append(inst)

    def process(self, data, match=None):
        self.log.debug("DCS")
        m = re.match(r"(?P<value>.*?)(\x07|\x1b\\)", data)
        if not m:
            raise IncompleteEscapeException()
        value = m.group('value')
        length = len(m.group(0))
        if not value:
            self.log.warning("Missing value for OSC escape: %s" % \
                             value.replace('\x1b', '\\x1b'))
            return length
        for seq in self.__sequences:
            seq_m = re.match(seq.MATCH, m.group('value'))
            if seq_m:
                seq.process(m.group('value'), seq_m)
                return length
        self.log.warning("DCS escape codes not implemented yet: %s" % \
                         data[:m.end()].replace('\x1b', '\\x1b'))
        return length


class ReverseIndexEscapeSequence(EscapeSequence):
    MATCH = r'\x1bM'

    def process(self, data, match=None):
        self.log.debug("Reverse index")
        cursor = self.screen.get_cursor()
        try:
            cursor.previous_row()
        except ScrollScreenException as e:
            self.screen.scroll(e.direction)
        return 0


