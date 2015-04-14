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
import re
import sys


class FindDialog(QDialog):
	SEARCH_ASCII = "ASCII"
	SEARCH_UTF16 = "UTF-16"
	SEARCH_UTF32 = "UTF-32"
	SEARCH_HEX = "Hex"
	SEARCH_REGEX = "Regular expression"

	def __init__(self, default_type, parent = None):
		super(FindDialog, self).__init__(parent)
		self.setWindowTitle("Find")

		layout = QVBoxLayout()

		hlayout = QHBoxLayout()
		hlayout.addWidget(QLabel("Search type:"))

		self.type_list = QComboBox()
		items = [FindDialog.SEARCH_ASCII, FindDialog.SEARCH_UTF16,
			FindDialog.SEARCH_UTF32, FindDialog.SEARCH_HEX,
			FindDialog.SEARCH_REGEX]
		for i in range(0, len(items)):
			self.type_list.addItem(items[i])
			if items[i] == default_type:
				self.type_list.setCurrentIndex(i)
		hlayout.addWidget(self.type_list)
		layout.addLayout(hlayout)

		hlayout = QHBoxLayout()
		hlayout.addWidget(QLabel("Search string:"))

		self.data = QLineEdit()
		self.data.setMinimumSize(QSize(400, 0))
		hlayout.addWidget(self.data)
		layout.addLayout(hlayout)

		hlayout = QHBoxLayout()
		find_button = QPushButton("Find")
		find_button.clicked.connect(self.find)
		find_button.setDefault(True)
		close_button = QPushButton("Close")
		close_button.clicked.connect(self.close)
		hlayout.addStretch(1)
		hlayout.addWidget(find_button)
		hlayout.addWidget(close_button)
		layout.addLayout(hlayout)

		self.setLayout(layout)
		self.data.setFocus(Qt.OtherFocusReason)

	def find(self):
		if self.search_regex() == None:
			return
		self.accept()

	def search_regex(self):
		try:
			if self.type_list.currentText() == FindDialog.SEARCH_REGEX:
				regex = self.data.text()
			else:
				if self.type_list.currentText() == FindDialog.SEARCH_HEX:
					string = self.data.text().replace(" ", "").replace("\t", "").decode("hex")
				elif self.type_list.currentText() == FindDialog.SEARCH_ASCII:
					string = self.data.text().encode("utf8")
				elif self.type_list.currentText() == FindDialog.SEARCH_UTF16:
					string = self.data.text().encode("utf-16le")
				elif self.type_list.currentText() == FindDialog.SEARCH_UTF32:
					string = self.data.text().encode("utf-32le")

				regex = ""
				for ch in string:
					if ((ch >= '0') and (ch <= '9')) or ((ch >= 'A') and (ch <= 'Z')) or ((ch >= 'a') and (ch <= 'z')):
						regex += ch
					else:
						regex += "\\x%.2x" % ord(ch)

			return re.compile(regex)
		except:
			QMessageBox.critical(self, "Error", "Invalid search string: " + str(sys.exc_info()[1]))
			return None

	def search_type(self):
		return self.type_list.currentText()

