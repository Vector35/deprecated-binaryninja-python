# Copyright (c) 2012-2015 Rusty Wagner
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

from PySide.QtCore import *
from PySide.QtGui import *


class ArchitectureDialog(QDialog):
	def __init__(self, parent):
		super(ArchitectureDialog, self).__init__(parent)

		self.setWindowTitle("Select Architecture")

		settings = QSettings("Binary Ninja", "Binary Ninja")

		layout = QVBoxLayout()

		self.arch = QComboBox()
		self.arch.setEditable(False)
		self.arch.addItems(["x86", "x86_64", "arm", "ppc", "quark"])

		lastArch = settings.value("disassemble/arch", "x86")
		lastArchIndex = self.arch.findText(lastArch)
		if lastArchIndex != -1:
			self.arch.setCurrentIndex(lastArchIndex)

		archLayout = QHBoxLayout()
		archLayout.setContentsMargins(0, 0, 0, 0)
		archLayout.addWidget(QLabel("Architecture:"))
		archLayout.addWidget(self.arch)
		layout.addLayout(archLayout)

		self.cancelButton = QPushButton("Cancel")
		self.cancelButton.clicked.connect(self.closeRequest)
		self.cancelButton.setAutoDefault(False)

		self.okButton = QPushButton("OK")
		self.okButton.clicked.connect(self.ok)
		self.okButton.setAutoDefault(True)

		buttonLayout = QHBoxLayout()
		buttonLayout.setContentsMargins(0, 0, 0, 0)
		buttonLayout.addStretch(1)
		buttonLayout.addWidget(self.cancelButton)
		buttonLayout.addWidget(self.okButton)
		layout.addLayout(buttonLayout)
		self.setLayout(layout)

	def saveSettings(self):
		settings = QSettings("Binary Ninja", "Binary Ninja")
		settings.setValue("disassemble/arch", self.arch.currentText())

	def ok(self):
		self.result = str(self.arch.currentText())
		self.saveSettings()
		self.accept()

	def closeRequest(self):
		self.result = None
		self.close()

