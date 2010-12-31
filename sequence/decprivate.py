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

