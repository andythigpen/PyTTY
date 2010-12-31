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

import datetime
import threading
import atexit
import traceback
import sys
import types

def safe_unicode(obj):
    try:
        return unicode(obj)
    except UnicodeDecodeError:
        ascii_text = str(obj).encode('string_escape')
        return unicode(ascii_text)

def safe_str(obj):
    try:
        return str(obj)
    except UnicodeEncodeError:
        return unicode(obj).encode('unicode_escape')

class LogHandler:
    def __init__(self):
        self._format = u"%(time)s: %(level)s - [%(modulename)s] %(message)s\n"
        self._time_format = u"%m/%d/%y %H:%M:%S."
        self._handle_mutex = threading.RLock()
        self._buffer = u""
        self._flush_limit = 0

    def _create_message_dict(self, modulename, level, *args, **kargs):
        d = dict()
        d.update(kargs)
        now = datetime.datetime.now()
        d['time'] = now.strftime(self._time_format)
        # Python 2.3 doesn't support %f flag
        d['time'] += u"%06d" % now.microsecond   
        d['modulename'] = modulename
        d['level'] = Log.get_log_level_name(level).upper()
        d['message'] = u""
        if level == Log.EXCEPTION: 
            (exc_type, exc_value, exc_tb) = sys.exc_info()
            d['message'] += u"\n%s\n" % \
                "".join(traceback.format_exception(exc_type, exc_value, 
                                                   exc_tb))    
        else:
            for arg in args:
                d['message'] += safe_unicode(arg)
        return d

    def _construct_message(self, modulename, level, *args, **kargs):
        d = self._create_message_dict(modulename, level, *args, **kargs)
        return self._format % d

    def set_format(self, format):
        self._format = format

    def set_time_format(self, time_format):
        self._time_format = time_format

    def handle_log(self, modulename, level, *args, **kargs):
        self._handle_mutex.acquire()
        self._buffer += self._construct_message(modulename, level, 
                                                *args, **kargs)
        self._handle_mutex.release()
        if len(self._buffer) > self._flush_limit:
            self.flush()

    def close(self):
        self.flush()

    def flush(self):
        if len(self._buffer) == 0:
            return
        self._handle_mutex.acquire()
        self._safe_flush()
        self._buffer = u""
        self._handle_mutex.release()

    def _safe_flush(self):
        '''Override in derived classes.'''
        pass


class ConsoleLogHandler(LogHandler):
    def __init__(self):
        LogHandler.__init__(self)
        self._flush_limit = 0

    def _safe_flush(self):
        print self._buffer[:-1]     # Removes newline at end 
                                    # of formatted message
                                    
    def __eq__(self, handler):
        return handler.__class__.__name__ == self.__class__.__name__

class FileLogHandler(LogHandler):

    def __init__(self, filename, mode='a'):
        LogHandler.__init__(self)
        self.filename = filename
        self.mode = mode
        self.fobj = None
        self._flush_limit = 0

    def close(self):
        LogHandler.close(self)
        if self.fobj != None:
            self.fobj.close()

    def _safe_flush(self):
        self.fobj = open(self.filename, self.mode)
        self.fobj.write(safe_str(self._buffer))
        self.fobj.close()

    def __eq__(self, handler):
        '''Only allow one FileLogHandler at once per file.'''
        return hasattr(handler, "filename") \
               and self.filename == handler.filename

class WindowsEventLogHandler(LogHandler):
    def _safe_flush(self):
        import servicemanager
        servicemanager.LogInfoMsg(self._buffer)
        
    def __eq__(self, handler):
        '''Only allow one WindowsEventLogHandler at once.'''
        return self.__class__.__name__ == handler.__class__.__name__


class Log:
    __logs = {}

    LEVELS = {'none'     : 0,
              'debug'    : 10,
              'status'   : 15,
              'info'     : 20,
              'warning'  : 30,
              'error'    : 40,
              'critical' : 50,
              'exception': 60}

    def __init__(self, modulename):
        self.__handlers = []
        self.__level  = Log.DEFAULT_LOG_LEVEL
        self.__modulename = modulename
        atexit.register(self.close)
        self.add_handler(Log.DEFAULT_HANDLER)

    #def __del__(self):
        #self.flush()
        #self.__handlers = []

    def flush(self):
        for handler in self.__handlers:
            handler.flush()

    def close(self):
        for handler in self.__handlers:
            handler.close()

    def set_level(self, level):
        self.__level = level

    def get_level(self):
        return self.__level

    def add_handler(self, handler):
        for hnd in self.__handlers:
            if handler == hnd:
                return
        self.__handlers.append(handler)
        
    def remove_handler(self, handler):
        try:
            self.__handlers.remove(handler)
            return True
        except ValueError:
            return False

    def __getattr__(self, name):
        def decorator(*args, **kargs):
            return self.__log(name, *args, **kargs)

        if name in Log.LEVELS:
            return decorator
        else:
            raise AttributeError("%s does not exist" % name)

    def __log(self, name, *args, **kargs):
        if name in Log.LEVELS:
            level = Log.LEVELS[name]
        else:
            level = 0

        if   level < self.__level \
          or self.__level == 0:
            return

        for handler in self.__handlers:
            handler.handle_log(self.__modulename, level, *args, **kargs)

    DEBUG     = LEVELS['debug']
    STATUS    = LEVELS['status']
    INFO      = LEVELS['info']
    WARNING   = LEVELS['warning']
    ERROR     = LEVELS['error']
    CRITICAL  = LEVELS['critical']
    EXCEPTION = LEVELS['exception']

    DEFAULT_LOG_LEVEL = DEBUG
    DEFAULT_HANDLER = ConsoleLogHandler()

    def get_log_level_name(level):
        for value in Log.LEVELS.keys():
            if Log.LEVELS[value] == level:
                return value
        return 'none'
    get_log_level_name = staticmethod(get_log_level_name)

    def get_log(modulename):
        if not modulename in Log.__logs:
            Log.__logs[modulename] = Log(modulename)
        return Log.__logs[modulename]
    get_log = staticmethod(get_log)

def get_log(modulename):
    if type(modulename) == types.ClassType:             # class type
        modulename = modulename.__name__
    elif type(modulename) == types.InstanceType:        # old-style class
        modulename = modulename.__class__.__name__
    elif str(type(modulename)).startswith("<class '"):  # new-style class
        modulename = modulename.__class__.__name__
    else:
        modulename = str(modulename)                    # don't know...
    logg = Log.get_log(modulename)
    logg.add_handler(FileLogHandler('output.log'))  #TODO remove this...
    return logg

