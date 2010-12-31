#!/usr/bin/python

import os
import sys
import log
import fcntl
import types
import terminal
from PyQt4 import QtGui, QtCore
from sequencer import EscapeSequence, EncounteredEscapeException, UnsupportedEscapeException

class BreakpointEncountered(Exception):
    pass

class BreakpointSequence(EscapeSequence):
    MATCH = r'\x1b\x1F'

    def process(self, data, match=None):
        raise BreakpointEncountered()


class QWidgetLogHandler(log.LogHandler):
    def __init__(self, widget):
        log.LogHandler.__init__(self)
        self.widget = widget
        self._format = u"%(message)s\n"

    def handle_log(self, modulename, level, *args, **kargs):
        if modulename != "Sequence":
            return
        log.LogHandler.handle_log(self, modulename, level, *args, **kargs)

    def _safe_flush(self):
        self.widget.setText(self._buffer)

    def __eq__(self, handler):
        return self.__class__.__name__ == handler.__class__.__name__

class XTermPlaybackTerminalWidget(terminal.TerminalWidget):
    def write(self, data):
        self.end_of_data_block = False
        idx = 0
        idx = self.sequencer.process_until_escape(data)
        self.screen.repaint_dirty_cells()
        return idx

class XTermPlayback(QtGui.QWidget):
    def __init__(self, fname):
        QtGui.QWidget.__init__(self)
        self.fname = fname

        layout = QtGui.QVBoxLayout()
        label = QtGui.QLabel("Playback file: %s" % fname)
        self.start_button = QtGui.QPushButton("&Start")
        self.next_button = QtGui.QPushButton("&Next")
        self.continue_button = QtGui.QPushButton("&Continue")
        self.dump_button = QtGui.QPushButton("&Dump Screen Buffer")
        self.clear_button = QtGui.QPushButton("C&lear Screen")
        self.log_textedit = QtGui.QTextEdit()

        def get_log(modulename):
            if type(modulename) == types.ClassType:            # class type
                modulename = modulename.__name__
            elif type(modulename) == types.InstanceType:       # old-style class
                modulename = modulename.__class__.__name__
            elif str(type(modulename)).startswith("<class '"): # new-style class
                modulename = modulename.__class__.__name__
            else:
                modulename = str(modulename)                   # don't know...
            logg = log.Log.get_log(modulename)
            logg.remove_handler(log.Log.DEFAULT_HANDLER)
            logg.add_handler(log.FileLogHandler('output.log'))  #TODO remove this...
            logg.add_handler(QWidgetLogHandler(self.log_textedit))
            return logg
        log.get_log = get_log

        self.log = log.get_log(self)
        self.trace = log.get_log("Sequence")

        layout.addWidget(label)
        layout.addWidget(self.start_button)
        layout.addWidget(self.next_button)
        layout.addWidget(self.continue_button)
        layout.addWidget(self.dump_button)
        layout.addWidget(self.clear_button)
        layout.addWidget(self.log_textedit)
        self.setLayout(layout)

        self.start_button.clicked.connect(self.start)
        self.next_button.clicked.connect(self.next_sequence_pressed)
        self.continue_button.clicked.connect(self.continue_sequence)
        self.dump_button.clicked.connect(self.dump_buffer)
        self.clear_button.clicked.connect(self.clear)

        self.next_button.setDisabled(True)
        self.continue_button.setDisabled(True)
        self.dump_button.setDisabled(True)
        self.clear_button.setDisabled(True)

        self.channel = terminal.TerminalChannel()

    def __del__(self):
        if hasattr(self, 'f') and self.f is not None:
            self.f.close()

    def closeEvent(self, event):
        if hasattr(self, 'term'):
            self.term.close()
        return QtGui.QWidget.closeEvent(self, event)

    def _setup_terminal(self):
        self.term = XTermPlaybackTerminalWidget(self.channel)
        self.term.show()
        # set stdin non-blocking
        fd = sys.stdin.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    def start(self, checked=False):
        self._setup_terminal()
        self.f = open(self.fname, 'r')
        self.next_button.setEnabled(True)
        self.continue_button.setEnabled(True)
        self.dump_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.data = ""
        self.clear()
        try:
            self.next_sequence()
        except BreakpointEncountered:
            self._find_and_remove_breakpoint()

    def _read_data(self):
        if not self.data:
            data = self.f.read(512)
            if not data:
                self.log.warning("End of file")
                self.trace.info("End of file")
                return False
            self.data = data
        return True

    def next_sequence_pressed(self, checked=False):
        try:
            self.next_sequence()
        except BreakpointEncountered:
            self.trace.info("Breakpoint encountered")
            self._find_and_remove_breakpoint()
            self.term.repaint()

    def next_sequence(self, repaint=True):
        found_escape = False
        while not found_escape:
            if not self._read_data():
                return False
            try:
                idx = self.term.write(self.data)
            except EncounteredEscapeException as e:
                idx = e.index
                self.log.debug("set idx to ", idx)
                found_escape = True
            except UnsupportedEscapeException as e:
                idx = e.index
                self.trace.info(str(e))
                found_escape = True
                raise e
            sys.stdout.write(self.data[:idx])
            sys.stdout.flush()
            try:
                output = sys.stdin.read()
            except IOError:
                output = None
            if output:
                self.log.warning("xterm replied: %s" % output)
            self.data = self.data[idx:]
            self.log.debug("self.data = ", self.data.replace('\x1b', '\\x1b'))
            self.log.debug("idx = ", idx)
        if repaint:
            self.term.repaint()
        return True

    def continue_sequence(self, checked=False):
        found_breakpoint = False
        while not found_breakpoint:
            try:
                if not self.next_sequence(repaint=False):
                    return 
            except BreakpointEncountered:
                found_breakpoint = True
                self._find_and_remove_breakpoint()
        self.term.repaint()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_F5:
            self.next_sequence()
        elif event.key() == QtCore.Qt.Key_F7:
            self.dump_buffer()
        elif event.key() == QtCore.Qt.Key_F8:
            self.continue_sequence()

    def dump_buffer(self):
        buf = self.term.screen.get_buffer()
        bottom = len(buf)
        debug = u""
        for row in range(0, bottom):
            debug += u"%03d: " % row
            for col in range(0, self.term.screen.width):
                debug += unicode(buf[row][col])
            debug += u"\n"
        self.trace.info("Screen buffer contents:\n%s" % debug)

    def clear(self, checked=False):
        sys.stdout.write("\x1b[2J\x1b[1;1H")     # erase terminal display
        sys.stdout.flush()

    def _find_and_remove_breakpoint(self):
        idx = self.data.find("\x1b\x1f")
        self.log.debug("Found breakpoint at %s, data = %s" % (idx, 
                        self.data.replace('\x1b', '\\x1b')))
        self.data = self.data[idx + len("\x1b\x1f"):]


if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-r", "--record", dest="record", action="store",
                      type="string",
                      help="record terminal sequences for playback later.")
    parser.add_option("-p", "--playback", dest="playback", action="store",
                      type="string",
                      help="Use this as a playback file.")
    (options, args) = parser.parse_args()

    if not options.playback:
        print "Playback file required."
        sys.exit(-1)

    app = QtGui.QApplication(sys.argv)
    pb = XTermPlayback(options.playback)
    pb.show()

    sys.exit(app.exec_())


