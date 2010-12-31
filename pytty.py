#!/usr/bin/python

import os
import sys
import log
import terminal
from PyQt4 import QtGui, QtCore
from config import SafeConfig

APP_NAME = "PyTTY"

class PyttyTabbar(QtGui.QTabBar):
    def tabSizeHint(self, index):
        '''Expand all tabs to equal width to size of window.'''
        if self.count() > 1:
            return QtCore.QSize(self.width() / self.count(), 
                                QtGui.QTabBar.tabSizeHint(self, 0).height())
        return QtGui.QTabBar.tabSizeHint(self, index)


class PyttyEventFilter(QtCore.QObject):
    def __init__(self, tabs):
        QtCore.QObject.__init__(self)
        self.tabs = tabs

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress:
            # Alt + [1-9] to select tab focus
            if event.key() >= QtCore.Qt.Key_1 and \
               event.key() <= QtCore.Qt.Key_9 and \
               event.modifiers() == QtCore.Qt.AltModifier:
                idx = event.key() - QtCore.Qt.Key_0 - 1
                self.tabs.setCurrentIndex(idx)
                return True

            # Shift + [Left|Right] to select tab focus
            if event.key() == QtCore.Qt.Key_Left and \
               event.modifiers() == QtCore.Qt.ShiftModifier:
                idx = self.tabs.currentIndex() - 1
                self.tabs.setCurrentIndex(idx)
                return True
            if event.key() == QtCore.Qt.Key_Right and \
               event.modifiers() == QtCore.Qt.ShiftModifier:
                idx = self.tabs.currentIndex() + 1
                self.tabs.setCurrentIndex(idx)
                return True

            # Ctrl + Shift + [W|T] to close/add tab
            if event.key() == QtCore.Qt.Key_T and \
               event.modifiers() == (QtCore.Qt.ControlModifier | \
                                     QtCore.Qt.ShiftModifier):
                self.tabs.add_new_tab()
                return True
            if event.key() == QtCore.Qt.Key_W and \
               event.modifiers() == (QtCore.Qt.ControlModifier | \
                                     QtCore.Qt.ShiftModifier):
                self.tabs.close_tab()
                return True
        return False

class PyttySavedList(QtGui.QListWidget):
    def __init__(self, group):
        QtGui.QListWidget.__init__(self)
        self.group = group

    def sizeHint(self):
        return QtCore.QSize(QtGui.QListWidget.sizeHint(self).width(),
                            self.group.height())


class PyttyPage(QtGui.QWidget):
    def __init__(self, tabs):
        QtGui.QWidget.__init__(self)
        self.tabs = tabs
        self.connection_threads = []
        self.show_connection_page()

    def sizeHint(self):
        (width, height) = terminal.TerminalWidget.get_default_size()
        return QtCore.QSize(width, height)

    def sizePolicy(self):
        return QtGui.QSizePolicy.MinimumExpanding

    def set_connection_name(self):
        host = str(self.host_edit.text())
        user = str(self.username_edit.text())
        name = "%s@%s" % (user, host)
        self.connection_name_edit.setText(name)

    def load_saved_items(self):
        self.saved_items.clear()
        config = SafeConfig(os.path.join(sys.path[0], 'saved.ini'))
        for sect in config.sections():
            d = {}
            item = QtGui.QListWidgetItem(sect)
            d['username'] = config.get(sect, 'username')
            d['password'] = config.get(sect, 'password')
            d['host'] = config.get(sect, 'host')
            d['port'] = config.getint(sect, 'port')
            item.setData(QtCore.Qt.UserRole, d)
            self.saved_items.addItem(item)

    def changed_saved(self, current, previous):
        if current is None:
            return
        d = current.data(QtCore.Qt.UserRole).toMap()
        username = d[QtCore.QString('username')].toString()
        password = d[QtCore.QString('password')].toString()
        host = d[QtCore.QString('host')].toString()
        port = d[QtCore.QString('port')].toString()
        self.username_edit.setText(username)
        self.password_edit.setText(password)
        self.host_edit.setText(host)
        self.port_edit.setText(port)

    def save_entry(self):
        name = str(self.connection_name_edit.text())
        if not name:
            return
        config = SafeConfig(os.path.join(sys.path[0], 'saved.ini'))
        if not config.has_section(name):
            config.add_section(name)

        username = str(self.username_edit.text())
        password = ""
        if self.save_password_check.isChecked():
            password = str(self.password_edit.text())
        host = str(self.host_edit.text())
        port = int(self.port_edit.text())

        config.set(name, 'username', username)
        config.set(name, 'password', password)
        config.set(name, 'host', host)
        config.set(name, 'port', port)
        config.write()
        self.load_saved_items()

    def remove_entry(self):
        items = self.saved_items.selectedItems()
        for item in items:
            print item.text()
            config = SafeConfig(os.path.join(sys.path[0], 'saved.ini'))
            config.remove_section(str(item.text()))
            config.write()
            self.load_saved_items()

    def clear_saved_selection(self, text):
        self.saved_items.setCurrentRow(-1)

    def show_connection_page(self):
        page_hlayout = QtGui.QHBoxLayout()
        page_vlayout = QtGui.QVBoxLayout()
        page_layout = QtGui.QGridLayout()
        new_group = QtGui.QGroupBox("New Connection")
        layout = QtGui.QFormLayout()

        self.host_edit = QtGui.QLineEdit()
        self.host_edit.returnPressed.connect(self.connect)
        self.host_edit.editingFinished.connect(self.set_connection_name)
        self.host_edit.textChanged.connect(self.clear_saved_selection)
        layout.addRow("&Host:", self.host_edit)

        self.port_edit = QtGui.QLineEdit("22")
        self.port_edit.returnPressed.connect(self.connect)
        self.port_edit.textChanged.connect(self.clear_saved_selection)
        validator = QtGui.QIntValidator(0, 65535, self)
        self.port_edit.setValidator(validator)
        layout.addRow("&Port:", self.port_edit)

        self.username_edit = QtGui.QLineEdit()
        self.username_edit.returnPressed.connect(self.connect)
        self.username_edit.editingFinished.connect(self.set_connection_name)
        self.username_edit.textChanged.connect(self.clear_saved_selection)
        layout.addRow("&Username:", self.username_edit)

        self.password_edit = QtGui.QLineEdit()
        self.password_edit.setEchoMode(QtGui.QLineEdit.Password)
        self.password_edit.returnPressed.connect(self.connect)
        self.password_edit.textChanged.connect(self.clear_saved_selection)
        layout.addRow("&Password:", self.password_edit)

        # for debugging
        #self.record_check = QtGui.QCheckBox()
        #layout.addRow("Record:", self.record_check)

        self.status_label = QtGui.QLabel("")
        layout.addRow(self.status_label)

        fname = os.path.join(sys.path[0], "icons", "login.png")
        self.login_button = QtGui.QPushButton(QtGui.QIcon(fname), "&Login")
        self.login_button.clicked.connect(self.connect)
        layout.addWidget(self.login_button)
        new_group.setLayout(layout)
        new_group.setMinimumWidth(250)

        # saved connection group
        saved_group = QtGui.QGroupBox("Saved Connection")
        saved_layout = QtGui.QGridLayout()
        self.saved_items = PyttySavedList(new_group)
        self.saved_items.setResizeMode(QtGui.QListView.Fixed)
        self.saved_items.currentItemChanged.connect(self.changed_saved)
        saved_layout.addWidget(self.saved_items, 0, 0, 1, 3)

        self.load_saved_items()

        self.connection_name_edit = QtGui.QLineEdit()
        saved_layout.addWidget(self.connection_name_edit, 1, 0, 1, 3)

        self.save_password_check = QtGui.QCheckBox("Save Password")
        saved_layout.addWidget(self.save_password_check, 2, 0)

        fname = os.path.join(sys.path[0], "icons", "save.png")
        save_button = QtGui.QPushButton(QtGui.QIcon(fname), "")
        save_button.setToolTip("Save")
        save_button.clicked.connect(self.save_entry)
        saved_layout.addWidget(save_button, 2, 1)
        
        fname = os.path.join(sys.path[0], "icons", "remove.png")
        remove_button = QtGui.QPushButton(QtGui.QIcon(fname), "")
        remove_button.setToolTip("Remove")
        remove_button.clicked.connect(self.remove_entry)
        saved_layout.addWidget(remove_button, 2, 2)
        saved_group.setLayout(saved_layout)

        page_hlayout.addStretch()
        page_hlayout.addWidget(saved_group)
        page_hlayout.addWidget(new_group)
        page_hlayout.addStretch()

        page_vlayout.addStretch()
        page_vlayout.addLayout(page_hlayout)
        page_vlayout.addStretch()

        self.setLayout(page_vlayout)

    def connect(self):
        self.status_label.setText("")
        username = str(self.username_edit.text())
        password = str(self.password_edit.text())
        host = str(self.host_edit.text())
        port = int(self.port_edit.text())

        self.login_button.setDisabled(True)
        idx = self.tabs.currentIndex()
        fname = os.path.join(sys.path[0], "icons", "loading.gif")
        self.tabs.setTabIcon(idx, QtGui.QIcon(fname))
        term = terminal.SSHTerminalWidget(username, password, host, port)

        # for debugging
        if hasattr(self, 'record_check') and self.record_check.isChecked():
            term.recorder = open('recorder', 'w')

        class ConnectionThread(QtCore.QThread):
            def __init__(self, terminal):
                QtCore.QThread.__init__(self)
                self.terminal = terminal
                
            def run(self):
                self.terminal.connect()

        th = ConnectionThread(term)

        def connection_finished():
            term = th.terminal
            if term.channel.is_connected():
                self.tabs.removeTab(idx)
                self.tabs.add_new_tab(term, index=idx)
            else:
                if term.channel.authentication_error:
                    self.status_label.setText("Authentication Error.")
                else:
                    self.status_label.setText("Unable to connect.")
                self.login_button.setDisabled(False)
                del term
            self.connection_threads.remove(th)


        th.finished.connect(connection_finished)
        th.start()
        self.connection_threads.append(th)

        #self.tabs.add_new_tab(term, 'PyTTY', idx)
        term.titleChanged.connect(self.change_tab_title)
        term.closing.connect(self.close_tab)


    def change_tab_title(self, title):
        sender = self.sender()
        for idx in range(0, self.tabs.count()):
            if self.tabs.widget(idx) == sender:
                self.tabs.setTabText(idx, title)
                break

    def close_tab(self):
        sender = self.sender()
        for idx in range(0, self.tabs.count()):
            widget = self.tabs.widget(idx)
            if widget == sender: #or widget is None:
                self.tabs.close_tab(idx)


class PyttyAddButton(QtGui.QPushButton):
    def __init__(self, tabbar):
        fname = os.path.join(sys.path[0], "icons", "plus.png")
        QtGui.QPushButton.__init__(self, QtGui.QIcon(fname), "")
        self.tabbar = tabbar

    def sizeHint(self):
        size = self.tabbar.height()
        return QtCore.QSize(size, size)


class PyttyTabWidget(QtGui.QTabWidget):
    def __init__(self):
        QtGui.QTabWidget.__init__(self)
        bar = PyttyTabbar()
        self.setTabBar(bar)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        self.setElideMode(QtCore.Qt.ElideRight)

        button = PyttyAddButton(self.tabBar())
        button.clicked.connect(self.add_tab_button_clicked)
        self.setCornerWidget(button)

        self.setup_events()
        
    def setup_events(self):
        self.tabCloseRequested.connect(self.close_tab)
        self.currentChanged.connect(self.focus_current)

    def focus_current(self, index):
        widget = self.currentWidget()
        if widget:
            widget.setFocus()

    def add_new_tab(self, widget=None, title='PyTTY', index=-1):
        if widget is None:
            widget = PyttyPage(self)
        if index < 0:
            idx = self.addTab(widget, title)
        else:
            idx = self.insertTab(index, widget, title)
        self.setCurrentIndex(idx)
        if hasattr(widget, 'host_edit'):
            widget.host_edit.setFocus()

    def close_tab(self, index=-1):
        if index < 0:
            index = self.currentIndex()
        if self.count() == 1:
            return QtCore.QCoreApplication.exit(0)
        self.removeTab(index)

    def add_tab_button_clicked(self, clicked):
        self.add_new_tab()


class Pytty(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        self.setWindowTitle(APP_NAME)

        self.tabs = PyttyTabWidget()
        self.setCentralWidget(self.tabs)
        self.tabs.add_new_tab()


if __name__ == "__main__":
    base_dir = sys.path[0]
    app = QtGui.QApplication(sys.argv)
    config = terminal.TerminalConfig()

    # set the application wide default log level
    log_level = config.get("Log", "level", "none")
    log.Log.DEFAULT_LOG_LEVEL = log.Log.LEVELS[log_level]

    widget = Pytty()
    event_filter = PyttyEventFilter(widget.tabs)
    QtCore.QCoreApplication.instance().installEventFilter(event_filter)
    widget.show()
    sys.exit(app.exec_())

