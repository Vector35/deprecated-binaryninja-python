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
from PySide.QtCore import *
from PySide.QtGui import *
from PySide.QtWebKit import *
from PySide.QtNetwork import *
from View import *


class HelpView(QWebView):
	def __init__(self, data, filename, view, parent):
		super(HelpView, self).__init__(parent)

		self.data = data

		# Set contents
		self.setUrl(QUrl.fromLocalFile(str(self.data)))

	def closeRequest(self):
		return True

	def getPriority(data, filename):
		# Never use this view unless explicitly needed
		return -1
	getPriority = staticmethod(getPriority)

	def getViewName():
		return "Help viewer"
	getViewName = staticmethod(getViewName)

	def getShortViewName():
		return "Help"
	getShortViewName = staticmethod(getShortViewName)

ViewTypes += [HelpView]

