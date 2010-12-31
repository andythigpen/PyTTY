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

