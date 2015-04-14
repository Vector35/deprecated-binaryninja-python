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
from Fonts import *


class PreferencesDialog(QDialog):
	def __init__(self, parent = None):
		super(PreferencesDialog, self).__init__(parent)
		self.setWindowTitle("Preferences")

		layout = QVBoxLayout()

		group = QGroupBox("Monospace font")
		groupLayout = QVBoxLayout()

		hlayout = QHBoxLayout()
		hlayout.setContentsMargins(0, 0, 0, 0)
		self.font = getMonospaceFont()
		hlayout.addWidget(QLabel("Font: "))
		self.fontLabel = QLabel("%s %d" % (self.font.family(), self.font.pointSize()))
		self.fontLabel.setFont(self.font)
		hlayout.addWidget(self.fontLabel, 1)
		selectFontButton = QPushButton("Select...")
		selectFontButton.clicked.connect(self.selectFont)
		hlayout.addWidget(selectFontButton)
		groupLayout.addLayout(hlayout)

		self.allowBold = QCheckBox("Allow bold fonts")
		self.allowBold.setChecked(allowBoldFonts())
		groupLayout.addWidget(self.allowBold)

		hlayout = QHBoxLayout()
		hlayout.addWidget(QLabel("Line spacing:"))
		self.lineSpacing = QSpinBox()
		self.lineSpacing.setMinimum(0)
		self.lineSpacing.setMaximum(4)
		self.lineSpacing.setValue(getExtraFontSpacing())
		hlayout.addWidget(self.lineSpacing)
		hlayout.addWidget(QLabel("pixels"))
		groupLayout.addLayout(hlayout)

		group.setLayout(groupLayout)
		layout.addWidget(group)

		hlayout = QHBoxLayout()
		defaults_button = QPushButton("Use defaults")
		defaults_button.clicked.connect(self.defaults)
		save_button = QPushButton("Save")
		save_button.clicked.connect(self.save)
		save_button.setDefault(True)
		close_button = QPushButton("Cancel")
		close_button.clicked.connect(self.close)
		hlayout.addWidget(defaults_button)
		hlayout.addStretch(1)
		hlayout.addWidget(close_button)
		hlayout.addWidget(save_button)
		layout.addLayout(hlayout)

		self.setLayout(layout)

	def save(self):
		setMonospaceFont(self.font)
		setExtraFontSpacing(self.lineSpacing.value())
		setAllowBoldFonts(self.allowBold.isChecked())
		self.accept()

	def selectFont(self):
		# The docs and actual behavior conflict here, it might break if we don't be very very
		# careful and paranoid, handling either return value order
		first, second = QFontDialog.getFont(self.font)

		if first and second:
			if hasattr(first, 'family'):
				self.font = first
			else:
				self.font = second
			self.fontLabel.setText("%s %d" % (self.font.family(), self.font.pointSize()))
			self.fontLabel.setFont(self.font)

	def defaults(self):
		setMonospaceFont(None)
		setExtraFontSpacing(None)
		setAllowBoldFonts(None)

		self.font = getMonospaceFont()
		self.fontLabel.setText("%s %d" % (self.font.family(), self.font.pointSize()))
		self.fontLabel.setFont(self.font)
		self.lineSpacing.setValue(getExtraFontSpacing())
		self.allowBold.setChecked(allowBoldFonts())

