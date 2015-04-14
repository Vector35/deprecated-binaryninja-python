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
from PySide.QtCore import *
from PySide.QtGui import *

monospaceFont = None
lineSpacing = None
allowBold = None


def getDefaultMonospaceFont():
	if sys.platform == 'darwin':
		font = QFont('Monaco', 12)
	elif sys.platform.find('linux') != -1:
		font = QFont('Monospace', 10)
	elif sys.platform.find('freebsd') != -1:
		font = QFont('Bitstream Vera Sans Mono', 10)
	else:
		font = QFont('Courier', 10)
	return font

def getMonospaceFont():
	global monospaceFont
	if monospaceFont is None:
		settings = QSettings("Binary Ninja", "Binary Ninja")
		monospaceFont = settings.value("font", getDefaultMonospaceFont())
	font = QFont(monospaceFont)
	font.setFixedPitch(True)
	font.setStyleHint(QFont.Courier)
	return font

def setMonospaceFont(font):
	global monospaceFont
	if font is None:
		font = getDefaultMonospaceFont()
	monospaceFont = font
	settings = QSettings("Binary Ninja", "Binary Ninja")
	settings.setValue("font", monospaceFont)

def getDefaultExtraFontSpacing():
	if sys.platform == 'darwin':
		return 1
	if sys.platform.find('freebsd') != -1:
		return 2
	return 0

def getExtraFontSpacing():
	global lineSpacing
	if lineSpacing is None:
		settings = QSettings("Binary Ninja", "Binary Ninja")
		lineSpacing = int(settings.value("spacing", getDefaultExtraFontSpacing()))
	return lineSpacing

def setExtraFontSpacing(spacing):
	global lineSpacing
	if spacing is None:
		spacing = getDefaultExtraFontSpacing()
	lineSpacing = spacing
	settings = QSettings("Binary Ninja", "Binary Ninja")
	settings.setValue("spacing", lineSpacing)

def getFontVerticalOffset():
	spacing = getExtraFontSpacing()
	return int((spacing + 1) / 2)

def allowBoldFonts():
	global allowBold
	if allowBold is None:
		settings = QSettings("Binary Ninja", "Binary Ninja")
		allowBold = int(settings.value("allow_bold", 1)) != 0
	return allowBold

def setAllowBoldFonts(allow):
	global allowBold
	if allow is None:
		allow = True
	allowBold = allow
	settings = QSettings("Binary Ninja", "Binary Ninja")
	if allowBold:
		settings.setValue("allow_bold", 1)
	else:
		settings.setValue("allow_bold", 0)

