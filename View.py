# Copyright (c) 2011-2015 Rusty Wagner
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
from PySide.QtCore import *
from PySide.QtGui import *
from PythonConsole import *

ViewTypes = []

from RunWindow import *


class HistoryEntry:
	def __init__(self, type, data):
		self.type = type
		self.data = data

class ViewFrame(QWidget):
	statusUpdated = Signal(QWidget)
	viewChanged = Signal(QWidget)
	closeRequest = Signal(QWidget)

	def __init__(self, type, data, filename, viewList):
		super(ViewFrame, self).__init__(None)

		self.navigation = {}
		self.back = []
		self.forward = []
		self.undo_buffer = []
		self.redo_buffer = []
		self.undo_location = None
		self.python_console = None
		self.terminal = None
		self.allow_title_change = False

		self.splitter = QSplitter(Qt.Vertical, self)
		self.main_area = QWidget()
		size_policy = self.main_area.sizePolicy()
		size_policy.setVerticalStretch(3)
		self.main_area.setSizePolicy(size_policy)
		self.splitter.addWidget(self.main_area)
		parent_layout = QVBoxLayout()
		parent_layout.setContentsMargins(0, 0, 0, 0)
		parent_layout.setSpacing(0)
		parent_layout.addWidget(self.splitter)
		self.setLayout(parent_layout)

		self.data = data
		self.exe = data
		self.view = type(data, filename, self, self.main_area)
		self.filename = filename
		self.new_filename = False
		self.custom_tab_name = None
		self.available = viewList
		self.splittable = True
		self.cache = {type : self.view}
		self.status = {self.view : ""}
		if hasattr(self.view, "statusUpdated"):
			self.status[self.view] = self.view.status
			self.view.statusUpdated.connect(self.viewStatusUpdated)

		self.layout = QVBoxLayout()
		self.layout.addWidget(self.view)
		self.layout.setContentsMargins(0, 0, 0, 0)
		self.layout.setSpacing(0)
		self.main_area.setLayout(self.layout)

		self.grabGesture(Qt.SwipeGesture)

	def createView(self, type):
		view = type(self.data, self.filename, self, self.main_area)
		view.setVisible(False)
		self.status[view] = ""
		if hasattr(view, "statusUpdated"):
			self.status[view] = view.status
			view.statusUpdated.connect(self.viewStatusUpdated)
		self.cache[type] = view
		self.layout.addWidget(view)
		return view

	def setViewType(self, type):
		self.view.setVisible(False)

		if self.cache.has_key(type):
			view = self.cache[type]
		else:
			view = self.createView(type)
		self.view = view
		self.view.setVisible(True)

		self.viewChanged.emit(self)
		self.statusUpdated.emit(self)

		self.view.setFocus(Qt.OtherFocusReason)

	def getTabName(self):
		if self.custom_tab_name:
			return self.custom_tab_name
		if self.filename == "":
			return "Untitled" + " (" + self.view.__class__.getShortViewName() + ")"
		return os.path.basename(self.filename) + " (" + self.view.__class__.getShortViewName() + ")"

	def setTabName(self, name):
		if not self.allow_title_change:
			return
		self.custom_tab_name = name
		self.statusUpdated.emit(self)

	def getShortFileName(self):
		if self.filename == "":
			return "Untitled"
		return os.path.basename(self.filename)

	def isUntitled(self):
		return self.filename == ""

	def isNewFileName(self):
		return self.new_filename

	def getStatus(self):
		return self.status[self.view]

	def viewStatusUpdated(self, view):
		self.status[view] = view.status
		if self.view == view:
			self.statusUpdated.emit(self)

	def register_navigate(self, name, view, func):
		self.navigation[name] = [view.__class__, func]

	def navigate(self, name, ofs):
		entry = self.get_history_entry()

		# If view is already open, navigate now
		if name in self.navigation:
			if not self.navigation[name][1](ofs):
				return False
			self.setViewType(self.navigation[name][0])
			self.back += [entry]
			self.forward = []
			self.view.setFocus(Qt.OtherFocusReason)
			return True

		# Look for a valid view type that handles this navigation
		for type in self.available:
			if type in self.cache:
				continue
			if hasattr(type, "handlesNavigationType"):
				if type.handlesNavigationType(name):
					view = self.createView(type)
					if not self.navigation[name][1](ofs):
						self.view.setFocus(Qt.OtherFocusReason)
						return False
					self.setViewType(type)
					self.back += [entry]
					self.forward = []
					self.view.setFocus(Qt.OtherFocusReason)
					return True

		return False

	def get_history_entry(self):
		if hasattr(self.view, "get_history_entry"):
			data = self.view.get_history_entry()
		else:
			data = None
		return HistoryEntry(self.view.__class__, data)

	def add_history_entry(self):
		entry = self.get_history_entry()
		self.back += [entry]
		self.forward = []

	def go_back(self):
		if len(self.back) > 0:
			entry = self.back.pop()
			self.forward += [self.get_history_entry()]
			self.setViewType(entry.type)
			if entry.data != None:
				self.view.navigate_to_history_entry(entry.data)

	def go_forward(self):
		if len(self.forward) > 0:
			entry = self.forward.pop()
			self.back += [self.get_history_entry()]
			self.setViewType(entry.type)
			if entry.data != None:
				self.view.navigate_to_history_entry(entry.data)

	def keyPressEvent(self, event):
		if event.key() == Qt.Key_Escape:
			self.go_back()
		elif event.key() == Qt.Key_Back:
			self.go_back()
		elif event.key() == Qt.Key_Forward:
			self.go_forward()
		else:
			super(ViewFrame, self).keyPressEvent(event)

	def event(self, event):
		if event.type() == QEvent.Gesture:
			gesture = event.gesture(Qt.SwipeGesture)
			if (gesture != None) and (gesture.state() == Qt.GestureFinished):
				if gesture.horizontalDirection() == QSwipeGesture.Left:
					self.go_back()
					return True
				elif gesture.horizontalDirection() == QSwipeGesture.Right:
					self.go_forward()
					return True
		return super(ViewFrame, self).event(event)

	def save(self, filename):
		try:
			self.data.save(filename)
		except IOError as (errno, msg):
			QMessageBox.critical(self, "Error", "Unable to save: " + msg)
			return False
		self.notify_save(filename)
		return True

	def notify_save(self, filename):
		self.filename = filename
		self.new_filename = True
		for view in self.cache.values():
			if hasattr(view, "notify_save"):
				view.notify_save()

	def is_modified(self):
		return self.data.is_modified()

	def begin_undo(self):
		self.undo_location = self.get_history_entry()

	def commit_undo(self):
                self.data.commit_undo(self.undo_location, self.get_history_entry())

	def undo(self):
		# Ensure any pending undo actions are accounted for
		self.commit_undo()

		entry = self.data.undo()
		if entry:
			self.setViewType(entry.type)
			if entry.data != None:
				self.view.navigate_to_history_entry(entry.data)

	def redo(self):
		# Ensure any pending undo actions are accounted for
		self.commit_undo()

		entry = self.data.redo()
		if entry:
			self.setViewType(entry.type)
			if entry.data != None:
				self.view.navigate_to_history_entry(entry.data)

	def toggle_python_console(self):
		if self.python_console:
			if self.python_console.isVisible():
				self.python_console.hide()
				self.view.setFocus(Qt.OtherFocusReason)
			else:
				self.python_console.show()
				self.python_console.input.setFocus(Qt.OtherFocusReason)
		else:
			self.python_console = PythonConsole(self)
			self.splitter.addWidget(self.python_console)
			self.python_console.input.setFocus(Qt.OtherFocusReason)

	def run_in_terminal(self, cmd):
		if self.terminal:
			if not self.terminal.isVisible():
				self.terminal.show()
				self.terminal.run()
				self.terminal.commandLine.setFocus(Qt.OtherFocusReason)
			else:
				self.terminal.run()
				self.terminal.term.setFocus(Qt.OtherFocusReason)
		else:
			self.terminal = RunWindow(self, self, cmd)
			self.splitter.addWidget(self.terminal)
			self.terminal.commandLine.setFocus(Qt.OtherFocusReason)

	def terminal_process_exit(self):
		if self.terminal:
			# Terminal process exited, set focus to view
			self.view.setFocus(Qt.OtherFocusReason)

	def terminal_closed(self):
		self.terminal.hide()
		self.view.setFocus(Qt.OtherFocusReason)

	def closing(self):
		if self.python_console:
			self.python_console.stop()
		if self.terminal:
			self.terminal.closeRequest()

	def force_close(self):
		self.closeRequest.emit(self)

	def font_changed(self):
		for view in self.cache.values():
			if hasattr(view, "fontChanged"):
				view.fontChanged()

