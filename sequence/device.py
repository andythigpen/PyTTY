from sequencer import CSIEscapeSequence

class SendPrimaryDeviceAttributesEscapeSequence(CSIEscapeSequence):
    MATCH = r'>(?P<value>[0-1]*)c'

    VT100 = 0
    VT220 = 1

    def process(self, data, match):
        value = match.group('value') or 0
        self.trace.end("Send Primary Device Attributes (Secondary DA): %s" % \
                       value)
        if int(value) == 0:
            self.channel.send_keypress("\x1b[>1;2600;0c")

