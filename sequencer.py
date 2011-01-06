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
import log
from config import TerminalConfig
from PyQt4 import QtGui, QtCore

class ScrollScreenException(Exception):
    '''Thrown when the terminal needs to scroll.'''
    pass

class IncompleteEscapeException(Exception):
    '''Thrown when an incomplete escape sequence was received.'''
    pass

class UnsupportedEscapeException(Exception):
    '''Thrown when encountering an unknown escape sequence.'''
    def __init__(self, index, value):
        Exception.__init__(self, "Unsupported escape sequence: %s" % \
                           value.replace('\x1b', '\\x1b'))
        self.index = index

class EncounteredEscapeException(Exception):
    '''Thrown when encountering an escape while processing text.'''
    def __init__(self, index):
        Exception.__init__(self)
        self.index = index


class TraceEndSequence(Exception):
    '''Throw this when a sequence has been interpretted, but the action
       should not be performed...This is for debugging purposes only.'''
    pass

class TraceSequence:
    def __init__(self, fall_through=False):
        self.log = log.get_log("Sequence")
        self.fall_through = fall_through

    def end(self, *arg, **kwarg):
        self.log.info(*arg, **kwarg)
        if not self.fall_through:
            raise TraceEndSequence()


class EscapeSequence(object):
    REQUIRED_ATTRS = ["MATCH"]
    def __init__(self, screen, channel):
        self.log = log.get_log(self)
        self.trace = TraceSequence(fall_through=True) #TODO change fall_through 
        self.screen = screen
        self.channel = channel
        for attr in self.REQUIRED_ATTRS:
            if not hasattr(self, attr):
                raise AttributeError("Escape sequence %s missing %s" + \
                                     "attribute" % (self, attr))

    def process(self, data, match=None):
        '''Subclasses should implement this.'''
        self.log.warning("Process not implemented.")


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
        self.log.warning("DCS escape codes not implemented yet: %s" % \
                         data[:m.end()].replace('\x1b', '\\x1b'))
        return length


class NormalKeypadEscapeSequence(EscapeSequence):
    MATCH = r'\x1b>'
    
    def process(self, data, match=None):
        self.log.debug("Normal Keypad DECPNM")
        self.trace.end("Normal Keypad DECPNM")
        self.screen.set_cursor_keys(application=False)
        return 0


class ApplicationKeypadEscapeSequence(EscapeSequence):
    MATCH = r'\x1b='

    def process(self, data, match=None):
        self.log.debug("Application Keypad DECPAM")
        self.trace.end("Application Keypad DECPAM")
        self.screen.set_cursor_keys(application=True)
        return 0

            
import sequence

class TerminalEscapeSequencer:
    def __init__(self, screen, channel):
        self.log = log.get_log(self)
        self.trace = TraceSequence(fall_through=True) #TODO change fall_through 
        self.screen = screen
        self.channel = channel
        self.__previous_sequence = ""
        self.config = TerminalConfig()
        self.encoding = self.config.get("Sequencer", "encoding", "utf-8")
        self.__sequences = []
        sequences = EscapeSequence.__subclasses__()
        for seq in sequences:
            inst = seq(screen, channel)
            self.__sequences.append(inst)

    def process(self, data):
        data = unicode(data, encoding=self.encoding)
        if self.__previous_sequence:
            data = self.__previous_sequence + data
            self.__previous_sequence = ""
        idx = 0
        self.log.debug("Processing input len = %s" % len(data))
        while idx < len(data):
            try:
                idx += self._process_text(data[idx:])
            except EncounteredEscapeException as e:
                idx += e.index
                self.log.debug("Found escape at %s" % idx)
                try:
                    idx += self._process_escape(data[idx:])
                except UnsupportedEscapeException as ee:
                    self.log.error(str(ee))
                    idx += ee.index

    def process_until_escape(self, data):
        data = unicode(data, encoding=self.encoding)
        prev_len = len(self.__previous_sequence)
        if self.__previous_sequence:
            data = self.__previous_sequence + data
            self.log.debug("Prepending incomplete sequence: %s" % \
                           data.replace('\x1b', '\\x1b'))
            self.__previous_sequence = ""
        idx = 0
        try:
            start = idx
            idx += self._process_text(data[idx:])
            self.trace.end("Wrote '%s'" % data[start:idx])
        except EncounteredEscapeException as e:
            idx += e.index
            self.trace.end("Wrote '%s'" % data[start:idx])
            try:
                idx += self._process_escape(data[idx:])
            except UnsupportedEscapeException as ee:
                self.log.error(str(ee))
                idx += ee.index
            e.index = idx - prev_len
            raise e
        return idx

    def _process_escape(self, data):
        self.log.debug("ESC ", data.replace('\x1b', '\\x1b'))
        processed = False
        for escape in self.__sequences:
            m = re.match(escape.MATCH, data)
            if not m:
                self.log.debug("no match %s" % escape.MATCH)
                continue
            self.log.debug("matched %s" % escape.MATCH)
            idx = m.end()
            processed = True
            self.log.debug("Processing escape with: %s" % \
                           escape.__class__.__name__)
            try:
                idx += escape.process(data[idx:], match=m)
            except UnsupportedEscapeException as e:
                self.log.exception()
                idx += e.index       # end of unsupported sequence
            except IncompleteEscapeException:
                self.log.debug("incomplete sequence: %s" % \
                               data.replace('\x1b', '\\x1b'))
                self.__previous_sequence = data
                idx += len(data)     # end of input
            break
        if data == "\x1b":
            self.log.debug("Escape at end of data buffer: %s" % \
                           data.replace('\x1b', '\\x1b'))
            self.__previous_sequence = data
            idx = len(data)
        elif not processed:
            next_escape = data[1:].find('\x1b')
            if next_escape < 0:
                next_escape = len(data)
            raise UnsupportedEscapeException(next_escape, data)
        return idx

    def _process_text(self, data):
        self.log.debug("TXT")
        cursor = self.screen.get_cursor()
        idx = 0
        for ch in data:
            idx += 1
            if ch == '\x1b':
                raise EncounteredEscapeException(idx - 1)
            if ch == '\n':
                self.log.debug("LF")
                try:
                    cursor.advance_row()
                except ScrollScreenException:
                    self.screen.scroll()
                continue
            elif ch == '\r':
                self.log.debug("CR")
                cursor.reset_col()
                continue
            elif ch == '\x07':
                self.log.debug("BEL")
                continue
            elif ch == '\x08':
                cursor.left()
                continue
            try:
                cursor.write(ch)
            except ScrollScreenException:
                self.screen.scroll()
        return idx

