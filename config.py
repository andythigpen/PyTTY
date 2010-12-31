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

