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

from PySide.QtCore import *
from PySide.QtGui import *
from Fonts import *
from TextEditor import *
import nasm


class AssembleDialog(QDialog):
	def __init__(self, parent):
		super(AssembleDialog, self).__init__(parent)

		self.setWindowTitle("Assemble")

		settings = QSettings("Binary Ninja", "Binary Ninja")

		layout = QVBoxLayout()

		self.data = BinaryData(settings.value("assemble/text", ""))
		self.edit = ViewFrame(TextEditor, self.data, "", [TextEditor])
		self.edit.setMinimumSize(512, 384)
		layout.addWidget(self.edit, 1)

		self.closeButton = QPushButton("Close")
		self.closeButton.clicked.connect(self.closeRequest)
		self.closeButton.setAutoDefault(False)

		self.assembleButton = QPushButton("Assemble")
		self.assembleButton.clicked.connect(self.assemble)
		self.assembleButton.setAutoDefault(True)

		buttonLayout = QHBoxLayout()
		buttonLayout.setContentsMargins(0, 0, 0, 0)
		buttonLayout.addStretch(1)
		buttonLayout.addWidget(self.assembleButton)
		buttonLayout.addWidget(self.closeButton)
		layout.addLayout(buttonLayout)
		self.setLayout(layout)

	def saveSettings(self):
		settings = QSettings("Binary Ninja", "Binary Ninja")
		settings.setValue("assemble/text", self.data.read(0, len(self.data)))

	def assemble(self):
		data, error = nasm.assemble(str(self.data.read(0, len(self.data))))
		if error is not None:
			QMessageBox.critical(self, "Assemble Failed", error, QMessageBox.Ok)
			return

		self.output = data
		self.saveSettings()
		self.accept()

	def closeRequest(self):
		self.saveSettings()
		self.close()

