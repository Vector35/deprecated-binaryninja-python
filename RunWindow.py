# Copyright (c) 2012 Rusty Wagner
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

import shlex
from PySide.QtCore import *
from PySide.QtGui import *
from TerminalView import *


class RunWindow(QWidget):
	def __init__(self, parent, view, cmd):
		super(RunWindow, self).__init__(parent)
		self.view = view
		self.cmd = cmd

		vlayout = QVBoxLayout()
		vlayout.setContentsMargins(0, 0, 0, 0)
		vlayout.setSpacing(0)

		hlayout = QHBoxLayout()
		hlayout.setContentsMargins(4, 0, 4, 4)
		hlayout.addWidget(QLabel("Command arguments:"))
		hlayout.setSpacing(4)

		self.commandLine = QLineEdit()
		self.commandLine.returnPressed.connect(self.run)
		hlayout.addWidget(self.commandLine, 1)

		self.runButton = QPushButton("Run")
		self.runButton.clicked.connect(self.run)
		self.runButton.setAutoDefault(True)
		self.closeButton = QPushButton("Close")
		self.closeButton.clicked.connect(self.closePanel)
		self.closeButton.setAutoDefault(False)
		hlayout.addWidget(self.runButton)
		hlayout.addWidget(self.closeButton)

		vlayout.addLayout(hlayout)

		self.term = TerminalView(None, "", view, self)
		self.reinit = False

		vlayout.addWidget(self.term, 1)
		self.setLayout(vlayout)

	def run(self):
		if self.reinit:
			self.term.reinit()
			self.reinit = False
			return

		cmdLine = self.commandLine.text()
		args = [i.decode("string_escape") for i in shlex.split(cmdLine.encode('utf8'))]
		self.term.restart(self.cmd + args)

	def closePanel(self):
		self.term.closeRequest()
		self.view.terminal_closed()
		self.reinit = True

	def closeRequest(self):
		self.term.closeRequest()

