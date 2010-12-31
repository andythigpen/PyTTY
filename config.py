import os
import sys
from ConfigParser import RawConfigParser

CONFIG_FILE = "config.ini"

class SafeConfig(RawConfigParser):
    def __init__(self, fname):
        RawConfigParser.__init__(self)
        self.fname = fname
        self.read(fname)

    def get(self, section, option, default=None):
        try:
            return RawConfigParser.get(self, section, option)
        except:
            return default

    def getint(self, section, option, default=None):
        try:
            return RawConfigParser.getint(self, section, option)
        except:
            return default

    def getfloat(self, section, option, default=None):
        try:
            return RawConfigParser.getfloat(self, section, option)
        except:
            return default

    def getboolean(self, section, option, default=None):
        try:
            return RawConfigParser.getboolean(self, section, option)
        except:
            return default

    def write(self):
        f = open(self.fname, 'w')
        RawConfigParser.write(self, f)
        f.close()


class TerminalConfig(SafeConfig):
    __shared_state = {}
    def __init__(self, name=CONFIG_FILE):
        self.__dict__ = self.__shared_state
        if len(TerminalConfig.__shared_state) == 0:
            fname = os.path.join(sys.path[0], name)
            SafeConfig.__init__(self, fname)

