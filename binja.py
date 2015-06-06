#!/usr/bin/env python
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

import sys
import os
import httplib
import hashlib
import base64
import zlib
import stat
import thread
import Threads
from PySide.QtCore import *
from PySide.QtGui import *
from View import *
from BinaryData import *
from HexEditor import *
from TextEditor import *
from TextLines import *
from ElfFile import *
from PEFile import *
from MachOFile import *
from DisassemblerView import *
from Util import *
from HelpView import *
from TerminalView import *
from AssembleDialog import *
from Preferences import *
import Transform
import PythonHighlight
import CHighlight


def loadPixmap(path):
	return QPixmap(os.path.join(os.path.dirname(os.path.realpath(__file__)),path))

class AboutDialog(QDialog):
	def __init__(self, parent=None):
		super(AboutDialog, self).__init__(parent)
		self.setWindowTitle("About Binary Ninja")

		# Paint background as a QPicture so that it renders at HiDPI on Macs that support it
		back = QPicture()
		p = QPainter()
		p.begin(back)
		p.drawPixmap(QRect(0, 0, 725, 280), loadPixmap("images/aboutback.png"))
		p.end()

		self.background = QLabel(self)
		self.background.setPicture(back)
		self.background.setGeometry(0, 0, 725, 280)

		if sys.platform == 'darwin':
			font_list = "\"Monaco\", Monospace"
		elif sys.platform.find('linux') != -1:
			font_list = "Monospace"
		elif sys.platform.find('freebsd') != -1:
			font_list = "\"Bitstream Vera Sans Mono\", Monospace"
		else:
			font_list = "\"Consolas\", \"Lucida Console\", Monospace"

		self.info = QLabel("<p style='font-size:16px; color:#64cd4c; font-family: " + font_list + "'>Copyright &copy; 2011-2013 Rusty Wagner<br/>" +
			"<a href=\"http://binary.ninja\" style=\"color:white\">Visit binary.ninja for news</a></p>", self)
		self.info.setGeometry(300, 60, 468, 210)
		self.info.setOpenExternalLinks(True)

		self.closeButton = QPushButton("Close")
		self.closeButton.clicked.connect(self.close)
		self.closeButton.setAutoDefault(True)

		layout = QVBoxLayout()
		buttonLayout = QHBoxLayout()
		buttonLayout.addStretch(1)
		buttonLayout.addWidget(self.closeButton)
		layout.addStretch(1)
		layout.addLayout(buttonLayout)
		self.setLayout(layout)

		self.setMinimumSize(725, 280)
		self.setMaximumSize(725, 280)
		self.setSizeGripEnabled(False)


class MainWindow(QMainWindow):
	def __init__(self, parent=None):
		global highlightTypes

		super(MainWindow, self).__init__(parent)
		self.setWindowTitle("Binary Ninja")

		action_table = {}
		highlightNames = highlightTypes.keys()
		highlightNames.sort()

		self.fileMenu = QMenu("&File", self)
		new_menu = self.fileMenu.addMenu("&New")
		new_binary_action = new_menu.addAction("&Binary data", self.new)
		new_binary_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_N))
		for name in highlightNames:
			cls = highlightTypes[name]
			new_menu.addAction(name, self.create_new_callback(cls))
		open_action = self.fileMenu.addAction("&Open...", self.open)
		open_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_O))
		save_action = self.fileMenu.addAction("&Save", self.save)
		save_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_S))
		self.fileMenu.addAction("Save &As...", self.saveAs)
		close_action = self.fileMenu.addAction("&Close", self.closeTab)
		close_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_W))
		self.fileMenu.addSeparator()
		self.fileMenu.addAction("&Preferences...", self.preferences)
		self.fileMenu.addSeparator()
		self.fileMenu.addAction("&Quit", self.quit)
		self.menuBar().addMenu(self.fileMenu)

		self.editMenu = QMenu("&Edit", self)
		undo_action = self.editMenu.addAction("&Undo", self.undo)
		undo_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_Z))
		redo_action = self.editMenu.addAction("&Redo", self.redo)
		redo_action.setShortcut(QKeySequence(Qt.CTRL + Qt.SHIFT + Qt.Key_Z))
		self.editMenu.addSeparator()
		select_all_action = self.editMenu.addAction("Select &all", self.selectAll)
		select_all_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_A))
		self.editMenu.addAction("Select &none", self.selectNone)
		self.editMenu.addSeparator()
		cut_action = self.editMenu.addAction("C&ut", self.cut)
		cut_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_X))
		copy_action = self.editMenu.addAction("&Copy", self.copy)
		copy_action.setShortcuts([QKeySequence(Qt.CTRL + Qt.Key_C), QKeySequence(Qt.CTRL + Qt.SHIFT + Qt.Key_C)])
		paste_action = self.editMenu.addAction("&Paste", self.paste)
		paste_action.setShortcuts([QKeySequence(Qt.CTRL + Qt.Key_V), QKeySequence(Qt.CTRL + Qt.SHIFT + Qt.Key_V)])
		self.editMenu.addSeparator()
		populate_copy_as_menu(self.editMenu.addMenu("Copy &as"), self, action_table)
		copy_address_action = self.editMenu.addAction("Copy address", self.copy_address)
		copy_address_action.setShortcut(QKeySequence(Qt.CTRL + Qt.SHIFT + Qt.Key_A))
		populate_paste_from_menu(self.editMenu.addMenu("Paste &from"), self, action_table)
		Transform.populate_transform_menu(self.editMenu.addMenu("&Transform"), self, action_table)
		self.editMenu.addSeparator()
		assemble_action = self.editMenu.addAction("Assemble...", self.assemble)
		assemble_action.setShortcut(QKeySequence(Qt.CTRL + Qt.ALT + Qt.Key_A))
		follow_ptr_action = self.editMenu.addAction("Follow pointer", self.follow_pointer)
		follow_ptr_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_Asterisk))
		self.editMenu.addSeparator()
		find_action = self.editMenu.addAction("Find...", self.find)
		find_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_F))
		find_next_action = self.editMenu.addAction("Find next", self.find_next)
		find_next_action.setShortcut(QKeySequence(Qt.Key_F3))
		self.menuBar().addMenu(self.editMenu)

		self.viewMenu = QMenu("&View", self)
		self.viewMenu.addAction("&Single view", self.split_single)
		horiz_split_action = self.viewMenu.addAction("Split &horizontally", self.split_horizontal)
		horiz_split_action.setShortcut(QKeySequence(Qt.CTRL + Qt.SHIFT + Qt.Key_T))
		vert_split_action = self.viewMenu.addAction("Split &vertically", self.split_vertical)
		vert_split_action.setShortcut(QKeySequence(Qt.CTRL + Qt.SHIFT + Qt.Key_Y))
		self.viewMenu.addSeparator()
		move_pane_action = self.viewMenu.addAction("&Move tab to other pane", self.split_move)
		move_pane_action.setShortcut(QKeySequence(Qt.CTRL + Qt.SHIFT + Qt.Key_M))
		self.viewMenu.addSeparator()
		next_tab_action = self.viewMenu.addAction("&Next tab", self.next_tab)
		prev_tab_action = self.viewMenu.addAction("&Previous tab", self.prev_tab)
		if sys.platform == 'darwin':
			next_tab_action.setShortcut(QKeySequence(Qt.META + Qt.Key_Tab))
			prev_tab_action.setShortcut(QKeySequence(Qt.META + Qt.SHIFT + Qt.Key_Tab))
		else:
			next_tab_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_Tab))
			prev_tab_action.setShortcut(QKeySequence(Qt.CTRL + Qt.SHIFT + Qt.Key_Tab))
		other_pane_action = self.viewMenu.addAction("Select &other pane", self.other_pane)
		other_pane_action.setShortcut(QKeySequence(Qt.ALT + Qt.Key_QuoteLeft))
		self.viewMenu.addSeparator()
		syntax_menu = self.viewMenu.addMenu("&Syntax highlighting")
		syntax_menu.addAction("None", self.highlight_none)
		for name in highlightNames:
			cls = highlightTypes[name]
			syntax_menu.addAction(name, self.create_highlight_callback(cls))
		self.menuBar().addMenu(self.viewMenu)

		self.toolsMenu = QMenu("&Tools", self)
		python_console_action = self.toolsMenu.addAction("&Python console", self.python_console)
		python_console_action.setShortcuts([QKeySequence(Qt.CTRL + Qt.Key_QuoteLeft), QKeySequence(Qt.Key_QuoteLeft)])
		if os.name != "nt":
			python_exec_action = self.toolsMenu.addAction("&Run Python script", self.python_run)
			python_exec_action.setShortcuts([QKeySequence(Qt.Key_F5), QKeySequence(Qt.CTRL + Qt.Key_R)])
			self.toolsMenu.addSeparator()
			shell_action = self.toolsMenu.addAction("&Shell", self.shell)
			shell_action.setShortcut(QKeySequence(Qt.CTRL + Qt.SHIFT + Qt.Key_N))
		self.menuBar().addMenu(self.toolsMenu)

		self.helpMenu = QMenu("&Help", self)
		self.helpMenu.addAction("&About...", self.about)
		self.helpMenu.addSeparator()
		self.helpMenu.addAction("&Python console API", self.python_console_api)
		self.menuBar().addMenu(self.helpMenu)

		for action in action_table.keys():
			action.triggered.connect(action_table[action])

		self.viewLabel = QLabel("View:")
		self.viewLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
		self.viewLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

		self.views = QComboBox()
		self.views.setMinimumSize(QSize(300, 0))
		self.views.setEnabled(False)
		self.views.currentIndexChanged.connect(self.setView)
		self.disableViewChange = False

		self.tools = QToolBar(self)
		self.tools.setIconSize(QSize(16, 16))
		self.newAction = self.tools.addAction(QIcon(loadPixmap("images/new.xpm")), "New")
		self.newAction.triggered.connect(self.new_button)
		self.tools.addAction(QIcon(loadPixmap("images/open.xpm")), "Open").triggered.connect(self.open)
		self.tools.addAction(QIcon(loadPixmap("images/save.xpm")), "Save").triggered.connect(self.save)
		self.tools.addSeparator()
		self.tools.addAction(QIcon(loadPixmap("images/cut.xpm")), "Cut").triggered.connect(self.cut)
		self.tools.addAction(QIcon(loadPixmap("images/copy.xpm")), "Copy").triggered.connect(self.copy)
		self.tools.addAction(QIcon(loadPixmap("images/paste.xpm")), "Paste").triggered.connect(self.paste)
		self.tools.addSeparator()
		self.tools.addWidget(self.viewLabel)
		self.tools.addWidget(self.views)
		self.splitAction = self.tools.addAction(QIcon(loadPixmap("images/split.xpm")), "New view of file")
		self.splitAction.triggered.connect(self.split)
		self.splitAction.setEnabled(False)
		self.addToolBar(self.tools)
		self.setUnifiedTitleAndToolBarOnMac(True)

		self.splitter = QSplitter()

		self.tab = QTabWidget(self)
		self.tab.setDocumentMode(True)
		self.tab.setTabsClosable(True)
		self.tab.setMovable(True)
		self.tab.tabCloseRequested.connect(self.mainTabCloseRequested)
		self.tab.currentChanged.connect(self.currentMainTabChanged)
		self.splitter.addWidget(self.tab)
		self.focus_tab = self.tab

		self.split_tab = QTabWidget(self)
		self.split_tab.setDocumentMode(True)
		self.split_tab.setTabsClosable(True)
		self.split_tab.setMovable(True)
		self.split_tab.tabCloseRequested.connect(self.splitTabCloseRequested)
		self.split_tab.currentChanged.connect(self.currentSplitTabChanged)
		self.split_tab.hide()
		self.splitter.addWidget(self.split_tab)

		self.setCentralWidget(self.splitter)

		self.setAcceptDrops(True)

		self.status = QStatusBar(self)
		self.status_text = QLabel(self)
		self.status_text.setFont(getMonospaceFont())
		self.status.addWidget(self.status_text, 1)
		self.setStatusBar(self.status)

		QApplication.instance().focusChanged.connect(self.focusChanged)

		self.raise_()
		self.show()

		bad_files = []
		end_of_options = False
		for i in xrange(1, len(sys.argv)):
			if not end_of_options:
				if sys.argv[i] == "--":
					end_of_options = True
				if sys.argv[i][0] == '-':
					continue

			try:
				data = BinaryFile(sys.argv[i])
				self.create_tab(data, sys.argv[i])
			except:
				bad_files.append(sys.argv[i])

		if len(bad_files) == 1:
			QMessageBox.critical(self, "Error", "The file '%s' could not be opened." % bad_files[0])
		elif len(bad_files) > 1:
			msg = "The following files could not be opened:\n\n"
			for i in bad_files:
				msg += "%s\n" % i
			QMessageBox.critical(self, "Error", msg)

	def sizeHint(self):
		return QSize(800, 600)

	def quit(self):
		self.close()

	def about(self):
		about = AboutDialog()
		about.exec_()

	def create_tab(self, data, filename, forced_view = None):
		# Pick the view with the highest priority
		best = None
		bestScore = -1
		available = []
		for i in ViewTypes:
			priority = i.getPriority(data, filename)
			if priority > bestScore:
				best = i
				bestScore = priority
			if priority >= 0:
				available += [i]

		if forced_view:
			best = forced_view

		# Create view and add it as a tab
		frame = ViewFrame(best, data, filename, available)
		frame.statusUpdated.connect(self.statusUpdated)
		frame.viewChanged.connect(self.viewChanged)
		frame.closeRequest.connect(self.forceClose)
		index = self.focus_tab.addTab(frame, frame.getTabName())
		self.focus_tab.setCurrentIndex(index)
		frame.view.setFocus(Qt.OtherFocusReason)

		# For text files, don't force save as when trying to save
		if (best == TextEditor) and (len(filename) > 0):
			frame.new_filename = True

		return frame

	def create_tab_from_data(self, data):
		self.create_tab(BinaryData(data), "")

	def dragEnterEvent(self, event):
		if event.mimeData().hasFormat("text/uri-list"):
			event.acceptProposedAction()

	def dropEvent(self, event):
		for i in event.mimeData().urls():
			if (sys.platform=="darwin" and (i.toLocalFile().find('/.file/id=') == 0)):
				try:
					from Foundation import NSURL
				except ImportError:
					sys.path.append('/System/Library/Frameworks/Python.framework/Versions/2.7/Extras/lib/python/PyObjC')
					from Foundation import NSURL
				url = NSURL.URLWithString_(i.toString()).path()
				self.open_name(str(url))
			else:
				if (not i.isLocalFile()):
					return
				self.open_name(i.toLocalFile())
		event.accept()

	def new(self):
		self.create_tab(BinaryData(), "")

	def new_text(self, cls):
		self.create_tab(BinaryData(), "", TextEditor).view.set_highlight_type(cls)

	def create_new_callback(self, cls):
		return lambda: self.new_text(cls)

	def new_button(self):
		global highlightTypes
		highlightNames = highlightTypes.keys()
		highlightNames.sort()

		# Let the user choose which type of file to create
		popup = QMenu()
		popup.addAction("&Binary data", self.new)
		for name in highlightNames:
			action = popup.addAction(name).triggered.connect(
				self.create_new_callback(highlightTypes[name]))
		popup.exec_(self.tools.widgetForAction(self.newAction).mapToGlobal(QPoint(0,
			self.tools.widgetForAction(self.newAction).size().height())))

	def open(self):
		name = QFileDialog.getOpenFileName(self, "Select file to open", None, "All files (*)")
		if len(name[0]) != 0:
			data = BinaryFile(name[0])
			self.create_tab(data, name[0])

	def open_name(self, name):
		if len(name) != 0:
			data = BinaryFile(name)
			self.create_tab(data, name)

	def save_tab(self, index):
		if self.focus_tab.widget(index).isNewFileName() and self.focus_tab.widget(index).save(self.focus_tab.widget(index).filename):
			self.focus_tab.setTabText(index, self.focus_tab.widget(index).getTabName())
			for i in range(0, self.tab.count()):
				if i == index:
					continue
				if self.tab.widget(i).data == self.tab.widget(index).data:
					self.tab.widget(i).notify_save(name[0])
					self.tab.setTabText(i, self.tab.widget(i).getTabName())
			for i in range(0, self.split_tab.count()):
				if i == index:
					continue
				if self.split_tab.widget(i).data == self.split_tab.widget(index).data:
					self.split_tab.widget(i).notify_save(name[0])
					self.split_tab.setTabText(i, self.split_tab.widget(i).getTabName())
			return True
		else:
			return self.save_tab_as(index)

	def save_tab_as(self, index):
		old_name = None
		if not self.focus_tab.widget(index).isUntitled():
			old_name = self.focus_tab.widget(index).filename
		name = QFileDialog.getSaveFileName(self, "Choose new filename", old_name, "All files (*)")
		if len(name[0]) != 0:
			if self.focus_tab.widget(index).save(name[0]):
				self.focus_tab.setTabText(index, self.focus_tab.widget(index).getTabName())
				for i in range(0, self.tab.count()):
					if i == index:
						continue
					if self.tab.widget(i).data == self.tab.widget(index).data:
						self.tab.widget(i).notify_save(name[0])
						self.tab.setTabText(i, self.tab.widget(i).getTabName())
				for i in range(0, self.split_tab.count()):
					if i == index:
						continue
					if self.split_tab.widget(i).data == self.split_tab.widget(index).data:
						self.split_tab.widget(i).notify_save(name[0])
						self.split_tab.setTabText(i, self.split_tab.widget(i).getTabName())
				return True
		return False

	def save(self):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		self.save_tab(index)

	def saveAs(self):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		self.save_tab_as(index)

	def closeTab(self):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		self.tabCloseRequested(self.focus_tab, index)

	def undo(self):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not hasattr(self.focus_tab.widget(index).view, "undo"):
			self.focus_tab.widget(index).undo()
			return
		self.focus_tab.widget(index).view.undo()

	def redo(self):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not hasattr(self.focus_tab.widget(index).view, "redo"):
			self.focus_tab.widget(index).redo()
			return
		self.focus_tab.widget(index).view.redo()

	def selectAll(self):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not hasattr(self.focus_tab.widget(index).view, "selectAll"):
			return
		self.focus_tab.widget(index).view.selectAll()

	def selectNone(self):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not hasattr(self.focus_tab.widget(index).view, "selectNone"):
			return
		self.focus_tab.widget(index).view.selectNone()

	def cut(self):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not hasattr(self.focus_tab.widget(index).view, "cut"):
			return
		self.focus_tab.widget(index).view.cut()

	def copy(self):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not hasattr(self.focus_tab.widget(index).view, "copy"):
			return
		self.focus_tab.widget(index).view.copy()

	def copy_as(self, encoder, binary = False):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not hasattr(self.focus_tab.widget(index).view, "copy_as"):
			return
		self.focus_tab.widget(index).view.copy_as(encoder, binary)

	def copy_address(self):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not hasattr(self.focus_tab.widget(index).view, "copy_address"):
			return
		self.focus_tab.widget(index).view.copy_address()

	def paste(self):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not hasattr(self.focus_tab.widget(index).view, "paste"):
			return
		self.focus_tab.widget(index).view.paste()

	def paste_from(self, decoder):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not hasattr(self.focus_tab.widget(index).view, "paste_from"):
			return
		self.focus_tab.widget(index).view.paste_from(decoder)

	def transform(self, func):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not hasattr(self.focus_tab.widget(index).view, "write"):
			return
		if not hasattr(self.focus_tab.widget(index).view, "get_selection_range"):
			return

		data = self.focus_tab.widget(index).view.data
		range = self.focus_tab.widget(index).view.get_selection_range()
		if (range[1] - range[0]) == 0:
			QMessageBox.critical(self, "Invalid Selection", "No bytes are selected for transformation.", QMessageBox.Ok)
			return
		value = data.read(range[0], range[1] - range[0])

		try:
			value = func(value)
		except:
			QMessageBox.critical(self, "Error", sys.exc_info()[1].args[0])

		if not self.focus_tab.widget(index).view.write(value):
			QMessageBox.critical(self, "Error", "Unable to modify contents")

	def transform_with_key(self, func):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not hasattr(self.focus_tab.widget(index).view, "write"):
			return
		if not hasattr(self.focus_tab.widget(index).view, "get_selection_range"):
			return

		data = self.focus_tab.widget(index).view.data
		range = self.focus_tab.widget(index).view.get_selection_range()
		if (range[1] - range[0]) == 0:
			QMessageBox.critical(self, "Invalid Selection", "No bytes are selected for transformation.", QMessageBox.Ok)
			return
		value = data.read(range[0], range[1] - range[0])

		dlg = Transform.KeyDialog(self)
		if dlg.exec_() == QDialog.Rejected:
			return

		try:
			value = func(value, dlg.key[:])
		except:
			QMessageBox.critical(self, "Error", sys.exc_info()[1].args[0])

		if not self.focus_tab.widget(index).view.write(value):
			QMessageBox.critical(self, "Error", "Unable to modify contents")

	def transform_with_key_and_iv(self, func):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not hasattr(self.focus_tab.widget(index).view, "write"):
			return
		if not hasattr(self.focus_tab.widget(index).view, "get_selection_range"):
			return

		data = self.focus_tab.widget(index).view.data
		range = self.focus_tab.widget(index).view.get_selection_range()
		if (range[1] - range[0]) == 0:
			QMessageBox.critical(self, "Invalid Selection", "No bytes are selected for transformation.", QMessageBox.Ok)
			return
		value = data.read(range[0], range[1] - range[0])

		dlg = Transform.KeyDialog(self, True)
		if dlg.exec_() == QDialog.Rejected:
			return

		try:
			value = func(value, dlg.key[:], dlg.iv[:])
		except:
			QMessageBox.critical(self, "Error", sys.exc_info()[1].args[0])

		if not self.focus_tab.widget(index).view.write(value):
			QMessageBox.critical(self, "Error", "Unable to modify contents")

	def find(self):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not hasattr(self.focus_tab.widget(index).view, "find"):
			return
		self.focus_tab.widget(index).view.find()

	def find_next(self):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not hasattr(self.focus_tab.widget(index).view, "find_next"):
			return
		self.focus_tab.widget(index).view.find_next()

	def createSplitView(self, data, type, filename, available):
		frame = ViewFrame(type, data, filename, available)
		frame.statusUpdated.connect(self.statusUpdated)
		frame.viewChanged.connect(self.viewChanged)
		frame.closeRequest.connect(self.forceClose)
		index = self.focus_tab.addTab(frame, frame.getTabName())
		self.focus_tab.setCurrentIndex(index)
		frame.view.setFocus(Qt.OtherFocusReason)

	def createSplitViewCallback(self, data, type, filename, available):
		return lambda : self.createSplitView(data, type, filename, available)

	def split(self):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not self.focus_tab.widget(index).splittable:
			return

		# Get information from existing tab
		data = self.focus_tab.widget(index).data
		filename = self.focus_tab.widget(index).filename
		available = self.focus_tab.widget(index).available

		# Let the user choose which view to create
		popup = QMenu()
		for type in available:
			action = popup.addAction(type.getViewName()).triggered.connect(
				self.createSplitViewCallback(data, type, filename, available))
		popup.exec_(self.tools.widgetForAction(self.splitAction).mapToGlobal(QPoint(0,
			self.tools.widgetForAction(self.splitAction).size().height())))

	def save_prompt(self, tab, index):
		response = QMessageBox.question(self, "File Modified", "File " + tab.widget(index).getShortFileName() +
			" has been modified.  Do you want to save it before closing?", QMessageBox.Save |
			QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel)
		if response == QMessageBox.Cancel:
			return False
		elif response == QMessageBox.Save:
			if not self.save_tab(index):
				return False
		return True

	def tabCloseRequested(self, tab, index):
		# Count the number of views open for this file
		view_count = 0
		for i in range(0, self.tab.count()):
			if self.tab.widget(i).data == tab.widget(index).data:
				view_count += 1
		for i in range(0, self.split_tab.count()):
			if self.split_tab.widget(i).data == tab.widget(index).data:
				view_count += 1

		# If this is the last view for this file and it has been modified, prompt for saving
		if (view_count == 1) and tab.widget(index).is_modified():
			if not self.save_prompt(tab, index):
				return

		# Ask view if it is OK to close, and if it is complete the close
		widget = tab.widget(index)
		if widget.view.closeRequest():
			widget.closing()
			if tab.widget(index) == widget:
				tab.removeTab(index)
			if tab.currentIndex() != -1:
				tab.currentWidget().view.setFocus(Qt.OtherFocusReason)
			self.evaluate_split_state()

	def mainTabCloseRequested(self, index):
		self.tabCloseRequested(self.tab, index)

	def splitTabCloseRequested(self, index):
		self.tabCloseRequested(self.split_tab, index)

	def closeEvent(self, event):
		seen = []
		for i in range(0, self.tab.count()):
			# Only ask once for each unique file
			if self.tab.widget(i).data in seen:
				continue
			seen.append(self.tab.widget(i).data)

			# If file has been modified, prompt for saving
			if self.tab.widget(i).is_modified():
				if not self.save_prompt(self.tab, i):
					event.ignore()
					return
		for i in range(0, self.split_tab.count()):
			# Only ask once for each unique file
			if self.split_tab.widget(i).data in seen:
				continue
			seen.append(self.split_tab.widget(i).data)

			# If file has been modified, prompt for saving
			if self.split_tab.widget(i).is_modified():
				if not self.save_prompt(self.split_tab, i):
					event.ignore()
					return

		# Going to exit, close tabs cleanly
		for i in range(0, self.tab.count()):
			self.tab.widget(i).closing()
			if not self.tab.widget(i).view.closeRequest():
				event.ignore()
				return
		for i in range(0, self.split_tab.count()):
			self.split_tab.widget(i).closing()
			if not self.split_tab.widget(i).view.closeRequest():
				event.ignore()
				return

		event.accept()
		sys.exit(0)

	def currentTabChanged(self, tab, index):
		index = tab.currentIndex()
		if index == -1:
			self.views.clear()
			self.views.setEnabled(False)
			self.splitAction.setEnabled(False)
			self.status_text.setText("")
			return

		types = tab.widget(index).available
		types.sort(key=lambda type:type.getViewName())

		self.disableViewChange = True
		self.views.clear()
		for i in range(0, len(types)):
			type = types[i]
			self.views.addItem(type.getViewName(), type)
			if tab.widget(index).view.__class__ == type:
				self.views.setCurrentIndex(i)
		self.views.setEnabled(True)
		self.splitAction.setEnabled(tab.widget(index).splittable)
		self.disableViewChange = False

		self.status_text.setText(tab.widget(index).getStatus())

		if tab != self.focus_tab:
			tab.widget(index).setFocus(Qt.OtherFocusReason)

	def currentMainTabChanged(self, index):
		self.currentTabChanged(self.tab, index)

	def currentSplitTabChanged(self, index):
		self.currentTabChanged(self.split_tab, index)

	def focusChanged(self, old, new):
		focus_tab = self.focus_tab
		if self.tab.isAncestorOf(new):
			focus_tab = self.tab
		elif self.split_tab.isAncestorOf(new):
			focus_tab = self.split_tab

		if focus_tab != self.focus_tab:
			self.focus_tab = focus_tab
			self.currentTabChanged(self.focus_tab, self.focus_tab.currentIndex())

	def setView(self, text):
		if self.disableViewChange:
			return

		index = self.views.currentIndex()
		if index == -1:
			return

		type = self.views.itemData(index)
		if type != self.focus_tab.widget(self.focus_tab.currentIndex()).view.__class__:
			self.focus_tab.widget(self.focus_tab.currentIndex()).add_history_entry()
			self.focus_tab.widget(self.focus_tab.currentIndex()).setViewType(type)

		self.focus_tab.widget(self.focus_tab.currentIndex()).view.setFocus(Qt.OtherFocusReason)
		self.focus_tab.setTabText(self.focus_tab.currentIndex(), self.focus_tab.widget(self.focus_tab.currentIndex()).getTabName())

	def statusUpdated(self, tab):
		if self.focus_tab.currentIndex() == -1:
			return
		if self.focus_tab.widget(self.focus_tab.currentIndex()) == tab:
			self.status_text.setText(tab.getStatus())

		# Ensure tab name stays up to date
		i = self.tab.indexOf(tab)
		if i != -1:
			if tab.getTabName() != self.tab.tabText(i):
				self.tab.setTabText(i, tab.getTabName())
		i = self.split_tab.indexOf(tab)
		if i != -1:
			if tab.getTabName() != self.split_tab.tabText(i):
				self.split_tab.setTabText(i, tab.getTabName())

	def viewChanged(self, tab):
		if self.focus_tab.currentIndex() == -1:
			return
		if self.focus_tab.widget(self.focus_tab.currentIndex()) == tab:
			# Update view selection and ensure current view has focus
			types = tab.available
			types.sort(key=lambda type:type.getViewName())
			for i in range(0, len(types)):
				type = types[i]
				if tab.view.__class__ == type:
					self.views.setCurrentIndex(i)
			tab.view.setFocus(Qt.OtherFocusReason)

	def python_console(self):
		if self.focus_tab.currentIndex() == -1:
			return
		self.focus_tab.widget(self.focus_tab.currentIndex()).toggle_python_console()

	def python_run(self):
		# Must save file before running it
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not self.save_tab(index):
			return
		if os.name != "nt":
			self.focus_tab.widget(index).run_in_terminal(["/usr/bin/env", "python", self.focus_tab.widget(index).filename])

	def python_console_api(self):
		if sys.executable.lower().find('python') == -1:
			base_path = os.path.dirname(sys.executable)
		else:
			base_path = os.path.dirname(__file__)
		path = os.path.abspath(os.path.join(base_path, 'docs/python_api.html'))
		data = BinaryData(path)
		frame = ViewFrame(HelpView, data, "Python Console API", [HelpView])
		frame.statusUpdated.connect(self.statusUpdated)
		frame.viewChanged.connect(self.viewChanged)
		frame.closeRequest.connect(self.forceClose)
		index = self.focus_tab.addTab(frame, frame.getTabName())
		self.focus_tab.setCurrentIndex(index)
		frame.view.setFocus(Qt.OtherFocusReason)

	def event(self, event):
		if event.type() == QEvent.User:
			try:
				event.result = event.code()
			except:
				event.exception = sys.exc_info()
			event.event.set()
			return True
		return super(MainWindow, self).event(event)

	def assemble(self):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not hasattr(self.focus_tab.widget(index).view, "write"):
			return

		dlg = AssembleDialog(self)
		if dlg.exec_() == QDialog.Rejected:
			return

		data = dlg.output
		if not self.focus_tab.widget(index).view.write(data):
			QMessageBox.critical(self, "Error", "Unable to write entire contents")

	def follow_pointer(self):
		index = self.focus_tab.currentIndex()
		if index == -1:
			return
		if not hasattr(self.focus_tab.widget(index).view, "follow_pointer"):
			return
		self.focus_tab.widget(index).view.follow_pointer()

	def create_split_tabs(self):
		index = self.tab.currentIndex()
		if index == -1:
			QMessageBox.critical(self, "Error", "No views active")
			return

		self.split_tab.show()

		if self.tab.count() == 1:
			# Only one tab open, create a cloned view in the other tab space
			frame = ViewFrame(type(self.tab.widget(index).view), self.tab.widget(index).data,
				self.tab.widget(index).filename, self.tab.widget(index).available)
			frame.statusUpdated.connect(self.statusUpdated)
			frame.viewChanged.connect(self.viewChanged)
			frame.closeRequest.connect(self.forceClose)
		else:
			# More than one tab open, move current view to other tab space
			if self.tab.currentIndex() == -1:
				frame = self.tab.widget(self.tab.count() - 1)
			else:
				frame = self.tab.widget(self.tab.currentIndex())

		index = self.split_tab.addTab(frame, frame.getTabName())
		self.split_tab.setCurrentIndex(index)
		frame.view.setFocus(Qt.OtherFocusReason)

		self.splitter.setSizes([1, 1])

	def split_single(self):
		# Determine the active tab so it can be preserved
		active_tab = None
		if self.focus_tab == self.tab:
			if self.tab.currentIndex() != -1:
				active_tab = self.tab.widget(self.tab.currentIndex())
		else:
			if self.split_tab.currentIndex() != -1:
				active_tab = self.split_tab.widget(self.split_tab.currentIndex())

		self.split_tab.hide()

		# Move any remaining tabs over to the main pane
		tabs = []
		for i in xrange(0, self.split_tab.count()):
			tabs.append(self.split_tab.widget(i))
		for tab in tabs:
			self.tab.addTab(tab, tab.getTabName())

		# Reactivate tab that was active before
		for i in xrange(0, self.tab.count()):
			if self.tab.widget(i) == active_tab:
				self.tab.setCurrentIndex(i)
				active_tab.view.setFocus(Qt.OtherFocusReason)
				break

	def split_horizontal(self):
		self.splitter.setOrientation(Qt.Horizontal)
		if self.split_tab.isHidden():
			self.create_split_tabs()

	def split_vertical(self):
		self.splitter.setOrientation(Qt.Vertical)
		if self.split_tab.isHidden():
			self.create_split_tabs()

	def split_move(self):
		if self.split_tab.isHidden() and (self.tab.count() <= 1):
			return
		if self.focus_tab.count() == 0:
			return
		if self.focus_tab.currentIndex() == -1:
			return
		if self.split_tab.isHidden():
			self.split_tab.show()
			self.splitter.setSizes([1, 1])

		tab = self.focus_tab.widget(self.focus_tab.currentIndex())
		if self.focus_tab == self.tab:
			index = self.split_tab.addTab(tab, tab.getTabName())
			self.split_tab.setCurrentIndex(index)
			tab.view.setFocus(Qt.OtherFocusReason)
		else:
			index = self.tab.addTab(tab, tab.getTabName())
			self.tab.setCurrentIndex(index)
			tab.view.setFocus(Qt.OtherFocusReason)

		self.evaluate_split_state()

	def evaluate_split_state(self):
		if self.split_tab.isHidden():
			return
		if self.split_tab.count() == 0:
			# No tabs left in split pane, go back to single view
			self.split_single()
		if self.tab.count() == 0:
			# No tabs left in default pane, go back to single view and move all tabs over
			# to the default pane
			self.split_single()

	def highlight_none(self):
		index = self.views.currentIndex()
		if index == -1:
			return

		self.focus_tab.widget(self.focus_tab.currentIndex()).add_history_entry()
		self.focus_tab.widget(self.focus_tab.currentIndex()).setViewType(TextEditor)
		self.focus_tab.widget(self.focus_tab.currentIndex()).view.set_highlight_type(None)
		self.focus_tab.widget(self.focus_tab.currentIndex()).view.setFocus(Qt.OtherFocusReason)
		self.focus_tab.setTabText(self.focus_tab.currentIndex(), self.focus_tab.widget(self.focus_tab.currentIndex()).getTabName())

	def set_highlight(self, cls):
		index = self.views.currentIndex()
		if index == -1:
			return

		self.focus_tab.widget(self.focus_tab.currentIndex()).add_history_entry()
		self.focus_tab.widget(self.focus_tab.currentIndex()).setViewType(TextEditor)
		self.focus_tab.widget(self.focus_tab.currentIndex()).view.set_highlight_type(cls)
		self.focus_tab.widget(self.focus_tab.currentIndex()).view.setFocus(Qt.OtherFocusReason)
		self.focus_tab.setTabText(self.focus_tab.currentIndex(), self.focus_tab.widget(self.focus_tab.currentIndex()).getTabName())

	def create_highlight_callback(self, cls):
		return lambda: self.set_highlight(cls)

	def shell(self):
		if sys.platform == 'darwin':
			data = TerminalData([os.environ.get('SHELL', '/bin/bash'), "-i", "-l"], True)
		else:
			data = TerminalData([os.environ.get('SHELL', '/bin/bash'), "-i"], True)
		frame = ViewFrame(TerminalView, data, "Terminal", [TerminalView])
		frame.allow_title_change = True
		frame.custom_tab_name = "Terminal"
		frame.statusUpdated.connect(self.statusUpdated)
		frame.viewChanged.connect(self.viewChanged)
		frame.closeRequest.connect(self.forceClose)
		index = self.focus_tab.addTab(frame, frame.getTabName())
		self.focus_tab.setCurrentIndex(index)
		frame.view.setFocus(Qt.OtherFocusReason)

	def forceClose(self, tab):
		i = self.tab.indexOf(tab)
		if i != -1:
			self.tabCloseRequested(self.tab, i)
		else:
			i = self.split_tab.indexOf(tab)
			if i != -1:
				self.tabCloseRequested(self.split_tab, i)

	def next_tab(self):
		if self.focus_tab.count() == 0:
			return
		if self.focus_tab.currentIndex() == -1:
			return
		i = self.focus_tab.currentIndex() + 1
		if i >= self.focus_tab.count():
			i = 0
		self.focus_tab.setCurrentIndex(i)

	def prev_tab(self):
		if self.focus_tab.count() == 0:
			return
		if self.focus_tab.currentIndex() == -1:
			return
		i = self.focus_tab.currentIndex() - 1
		if i < 0:
			i = self.focus_tab.count() - 1
		self.focus_tab.setCurrentIndex(i)

	def other_pane(self):
		if self.split_tab.isHidden():
			return
		if self.focus_tab == self.tab:
			tab = self.split_tab
		else:
			tab = self.tab
		if tab.currentIndex() == -1:
			return
		tab.widget(tab.currentIndex()).view.setFocus(Qt.OtherFocusReason)

	def preferences(self):
		if PreferencesDialog(self).exec_() == QDialog.Accepted:
			for i in xrange(0, self.tab.count()):
				self.tab.widget(i).font_changed()
			for i in xrange(0, self.split_tab.count()):
				self.split_tab.widget(i).font_changed()


if __name__ == "__main__":
	app = QApplication(sys.argv)
	app.setWindowIcon(QIcon(loadPixmap("images/icon.png")))
	Threads.gui_thread = thread.get_ident()
	Threads.main_window = MainWindow()
	app.exec_()

