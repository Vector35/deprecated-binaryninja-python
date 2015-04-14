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

import sys
from PySide.QtCore import *
from PySide.QtGui import *
from TerminalProcess import *
from Fonts import *


class TerminalData:
	def __init__(self, cmd, auto_close, notify_start = False):
		self.cmd = cmd
		self.auto_close = auto_close
		self.notify_start = notify_start

	def is_modified(self):
		return False

	def commit_undo(self, before_loc, after_loc):
		pass

	def undo(self):
		return None

	def redo(self):
		return None


class TerminalView(QAbstractScrollArea):
	def __init__(self, data, filename, view, parent):
		super(TerminalView, self).__init__(parent)

		self.view = view
		view.setTabName("Terminal")
		self.setFrameStyle(QFrame.NoFrame)

		if data is None:
			self.proc = TerminalProcess(None)
			self.auto_close = False
		elif hasattr(data, "raw_debug"):
			self.proc = TerminalProcess(data.cmd, data.raw_debug)
			self.auto_close = data.auto_close
		else:
			self.proc = TerminalProcess(data.cmd)
			self.auto_close = data.auto_close

		self.proc.term.update_callback = self.updateLines
		self.proc.term.title_callback = self.updateWindowTitle

		self.proc.exit_callback = self.processExit
		self.proc.start_monitoring()

		self.setCursor(Qt.IBeamCursor)
		self.verticalScrollBar().setCursor(Qt.ArrowCursor)

		# Get font and compute character sizes
		self.initFont()
		self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

		# Initialize scroll bars
		self.historySize = 0
		self.resizeDisabled = False
		areaSize = self.viewport().size()
		self.adjustSize(areaSize.width(), areaSize.height())

		# Give a small black border around the terminal
		self.setViewportMargins(2, 2, 2, 2)
		pal = QPalette(self.palette())
		pal.setColor(QPalette.Background, Qt.black)
		self.setPalette(pal)
		self.setAutoFillBackground(True)

		self.cursorTimer = QTimer()
		self.cursorTimer.setInterval(500)
		self.cursorTimer.setSingleShot(False)
		self.cursorTimer.timeout.connect(self.cursorTimerEvent)
		self.cursorTimer.start()

		self.cursorY = 0
		self.caretVisible = False
		self.caretBlink = True

		self.selection = False
		self.selectionStartX = 0
		self.selectionStartY = 0
		self.selectionEndX = 0
		self.selectionEndY = 0

		# Control means control
		if sys.platform == 'darwin':
			self.ctrl = Qt.MetaModifier
			self.command = Qt.ControlModifier
			self.ctrl_hotkey = Qt.META
		else:
			self.ctrl = Qt.ControlModifier
			self.command = Qt.ControlModifier
			self.ctrl_hotkey = Qt.CTRL

		self.setFocusPolicy(Qt.StrongFocus)

		if (sys.platform.find('linux') != -1) or (sys.platform.find('freebsd') != -1):
			self.x11 = True
		else:
			self.x11 = False

		# System colors
		dim_colors = [Qt.black, QColor(135, 0, 0), QColor(0, 135, 0), QColor(135, 135, 0),
			QColor(0, 0, 135), QColor(135, 0, 135), QColor(0, 135, 135), QColor(135, 135, 135)]
		normal_colors = [QColor(46, 52, 54), QColor(204, 0, 0), QColor(78, 154, 6), QColor(196, 160, 0),
			QColor(52, 101, 164), QColor(117, 80, 123), QColor(6, 152, 154), QColor(211, 215, 207)]
		bright_colors = [QColor(85, 87, 83), QColor(239, 41, 41), QColor(138, 226, 52), QColor(252, 233, 79),
			QColor(114, 159, 207), QColor(173, 127, 168), QColor(52, 226, 226), Qt.white]

		# Create color arrays for normal mode
		self.fore_colors = [Qt.white] + dim_colors + normal_colors + bright_colors + bright_colors
		self.back_colors = [Qt.black] + normal_colors + bright_colors

		# Create color array for 256-color mode
		self.colors = normal_colors + bright_colors

		values = [0x00, 0x5f, 0x87, 0xaf, 0xd7, 0xff]
		for red in values:
			for green in values:
				for blue in values:
					color = QColor(red, green, blue)
					self.colors.append(color)

		values = [0x08, 0x12, 0x1c, 0x26, 0x30, 0x3a, 0x44, 0x4e, 0x58, 0x62, 0x6c, 0x76, 0x80, 0x8a, 0x94, 0x9e,
			0xa8, 0xb2, 0xbc, 0xc6, 0xd0, 0xda, 0xe4, 0xee]
		for gray in values:
			color = QColor(gray, gray, gray)
			self.colors.append(color)

	def initFont(self):
		self.font = getMonospaceFont()
		self.font.setKerning(False)
		self.baseline = int(QFontMetricsF(self.font).ascent())

		self.bold_font = QFont(self.font)
		if allowBoldFonts():
			self.bold_font.setBold(True)

		self.underline_font = QFont(self.font)
		self.underline_font.setUnderline(True)

		# Compute width and ensure width is an integer (otherwise there will be rendering errors)
		self.charWidth = QFontMetricsF(self.font).width('X')
		if (self.charWidth % 1.0) < 0.5:
			self.font.setLetterSpacing(QFont.AbsoluteSpacing, -(self.charWidth % 1.0))
			self.bold_font.setLetterSpacing(QFont.AbsoluteSpacing, -(self.charWidth % 1.0))
			self.underline_font.setLetterSpacing(QFont.AbsoluteSpacing, -(self.charWidth % 1.0))
			self.charWidth -= self.charWidth % 1.0
		else:
			self.font.setLetterSpacing(QFont.AbsoluteSpacing, 1.0 - (self.charWidth % 1.0))
			self.bold_font.setLetterSpacing(QFont.AbsoluteSpacing, 1.0 - (self.charWidth % 1.0))
			self.underline_font.setLetterSpacing(QFont.AbsoluteSpacing, 1.0 - (self.charWidth % 1.0))
			self.charWidth += 1.0 - (self.charWidth % 1.0)

		self.charHeight = int(QFontMetricsF(self.font).height()) + getExtraFontSpacing()
		self.charOffset = getFontVerticalOffset()

	def adjustSize(self, width, height):
		# Compute number of rows and columns
		self.cols = int(width / self.charWidth)
		if self.cols < 4:
			self.cols = 4
		self.rows = int(height / self.charHeight)
		if self.rows < 4:
			self.rows = 4

		# Update scroll bar information
		self.verticalScrollBar().setPageStep(self.rows)
		self.verticalScrollBar().setRange(-self.historySize, 0)

	def resizeEvent(self, event):
		if self.resizeDisabled:
			return

		# Window was resized, adjust scroll bar
		self.adjustSize(event.size().width(), event.size().height())

		# Tell the terminal that the window size has changed
		self.proc.resize(self.rows, self.cols)

	def disableResize(self):
		self.resizeDisabled = True

	def enableResize(self):
		self.resizeDisabled = False

	def paintEvent(self, event):
		# Initialize painter
		p = QPainter(self.viewport())
		p.setFont(self.font)

		# Paint background
		p.fillRect(event.rect(), Qt.black)

		# Compute range that needs to be updated
		yofs = self.verticalScrollBar().value()
		topY = event.rect().y()
		botY = topY + event.rect().height()
		topY = topY / self.charHeight
		botY = (botY / self.charHeight) + 1

		screen = self.proc.term.screen
		renditions = self.proc.term.rendition

		# Compute selection range
		selectionStart = (self.selectionStartY * self.cols) + self.selectionStartX
		selectionEnd = (self.selectionEndY * self.cols) + self.selectionEndX
		if selectionStart > selectionEnd:
			selectionStart, selectionEnd = selectionEnd, selectionStart

		# Paint each line
		for y in range(topY, botY):
			# Skip if line is invalid
			if (y + yofs) < -self.historySize:
				continue
			if (y + yofs) >= self.rows:
				continue

			# Grab the line data
			if (y + yofs) < 0:
				line = self.proc.term.history_screen[y + yofs + self.historySize]
				renditionLine = self.proc.term.history_rendition[y + yofs + self.historySize]
			else:
				line = screen[y + yofs]
				renditionLine = renditions[y + yofs]

			# First paint the background
			x = 0
			cur_length = 0
			cur_rendition = None
			back_color = Qt.black
			fore_color = Qt.white

			for i in xrange(0, self.cols):
				if i < len(renditionLine):
					rendition = renditionLine[i]
				else:
					rendition = 0

				if self.caretBlink and self.caretVisible and self.proc.term.cursor_visible and (self.proc.term.cursor_row == y + yofs) and (self.proc.term.cursor_col == i):
					rendition ^= TerminalEmulator.RENDITION_INVERSE

				ofs = ((y + yofs) * self.cols) + i
				if self.selection and (ofs >= selectionStart) and (ofs < selectionEnd):
					rendition ^= TerminalEmulator.RENDITION_INVERSE

				if rendition != cur_rendition:
					if cur_length > 0:
						p.fillRect(x * self.charWidth, y * self.charHeight,
							cur_length * self.charWidth, self.charHeight, back_color)
						x += cur_length
						cur_length = 0

					cur_rendition = rendition

					if rendition & TerminalEmulator.RENDITION_BACKGROUND_256:
						back_color = self.colors[(rendition >> 24) & 0xff]
					else:
						back_color = self.back_colors[(rendition >> 24) & 0x1f]

					if rendition & TerminalEmulator.RENDITION_FOREGROUND_256:
						if ((rendition >> 16) & 0xff) < 16:
							if rendition & TerminalEmulator.RENDITION_BOLD:
								fore_color = self.fore_colors[((rendition >> 16) & 7) + 17]
							else:
								fore_color = self.fore_colors[((rendition >> 16) & 0xf) + 9]
						else:
							fore_color = self.colors[(rendition >> 16) & 0xff]
					elif (rendition & 0x1f0000 == 0) or (rendition & TerminalEmulator.RENDITION_DIM):
						fore_color = self.fore_colors[(rendition >> 16) & 0x1f]
					elif rendition & TerminalEmulator.RENDITION_BOLD:
						fore_color = self.fore_colors[((rendition >> 16) & 0x1f) + 16]
					else:
						fore_color = self.fore_colors[((rendition >> 16) & 0x1f) + 8]

					if rendition & TerminalEmulator.RENDITION_INVERSE:
						fore_color, back_color = back_color, fore_color

				cur_length += 1

			if cur_length > 0:
				p.fillRect(x * self.charWidth, y * self.charHeight,
					cur_length * self.charWidth, self.charHeight, back_color)

			# Now paint the foreground
			x = 0
			cur_text = ""
			cur_rendition = None
			back_color = Qt.black
			fore_color = Qt.white

			for i in xrange(0, len(line)):
				rendition = renditionLine[i]

				if self.caretBlink and self.caretVisible and self.proc.term.cursor_visible and (self.proc.term.cursor_row == y + yofs) and (self.proc.term.cursor_col == i):
					rendition ^= TerminalEmulator.RENDITION_INVERSE

				ofs = ((y + yofs) * self.cols) + i
				if self.selection and (ofs >= selectionStart) and (ofs < selectionEnd):
					rendition ^= TerminalEmulator.RENDITION_INVERSE

				if rendition != cur_rendition:
					if len(cur_text) > 0:
						p.setPen(fore_color)
						p.drawText(x * self.charWidth, y * self.charHeight +
							self.charOffset + self.baseline, cur_text)
						x += len(cur_text)
						cur_text = ""

					cur_rendition = rendition

					if rendition & TerminalEmulator.RENDITION_BOLD:
						p.setFont(self.bold_font)
					elif rendition & TerminalEmulator.RENDITION_UNDERLINE:
						p.setFont(self.underline_font)
					else:
						p.setFont(self.font)

					if rendition & TerminalEmulator.RENDITION_BACKGROUND_256:
						back_color = self.colors[(rendition >> 24) & 0xff]
					else:
						back_color = self.back_colors[(rendition >> 24) & 0x1f]

					if rendition & TerminalEmulator.RENDITION_FOREGROUND_256:
						if ((rendition >> 16) & 0xff) < 16:
							if rendition & TerminalEmulator.RENDITION_BOLD:
								fore_color = self.fore_colors[((rendition >> 16) & 7) + 17]
							else:
								fore_color = self.fore_colors[((rendition >> 16) & 0xf) + 9]
						else:
							fore_color = self.colors[(rendition >> 16) & 0xff]
					elif (rendition & 0x1f0000 == 0) or (rendition & TerminalEmulator.RENDITION_DIM):
						fore_color = self.fore_colors[(rendition >> 16) & 0x1f]
					elif rendition & TerminalEmulator.RENDITION_BOLD:
						fore_color = self.fore_colors[((rendition >> 16) & 0x1f) + 16]
					else:
						fore_color = self.fore_colors[((rendition >> 16) & 0x1f) + 8]

					if rendition & TerminalEmulator.RENDITION_INVERSE:
						fore_color, back_color = back_color, fore_color

				cur_text += line[i]

			if len(cur_text) > 0:
				p.setPen(fore_color)
				p.drawText(x * self.charWidth, y * self.charHeight + self.charOffset + self.baseline, cur_text)

			if (not self.caretVisible) and (self.proc.term.cursor_row == (y + yofs)):
				# Caret not active, draw rectangle with foreground color
				x = self.proc.term.cursor_col
				rendition = renditionLine[x]

				ofs = ((y + yofs) * self.cols) + x
				if self.selection and (ofs >= selectionStart) and (ofs < selectionEnd):
					rendition ^= TerminalEmulator.RENDITION_INVERSE

				if rendition & TerminalEmulator.RENDITION_BACKGROUND_256:
					back_color = self.colors[(rendition >> 24) & 0xff]
				else:
					back_color = self.back_colors[(rendition >> 24) & 0x1f]

				if rendition & TerminalEmulator.RENDITION_FOREGROUND_256:
					if ((rendition >> 16) & 0xff) < 16:
						if rendition & TerminalEmulator.RENDITION_BOLD:
							fore_color = self.fore_colors[((rendition >> 16) & 7) + 17]
						else:
							fore_color = self.fore_colors[((rendition >> 16) & 0xf) + 9]
					else:
						fore_color = self.colors[(rendition >> 16) & 0xff]
				elif (rendition & 0x1f0000 == 0) or (rendition & TerminalEmulator.RENDITION_DIM):
					fore_color = self.fore_colors[(rendition >> 16) & 0x1f]
				elif rendition & TerminalEmulator.RENDITION_BOLD:
					fore_color = self.fore_colors[((rendition >> 16) & 0x1f) + 16]
				else:
					fore_color = self.fore_colors[((rendition >> 16) & 0x1f) + 8]

				if rendition & TerminalEmulator.RENDITION_INVERSE:
					fore_color, back_color = back_color, fore_color

				p.setPen(fore_color)
				p.drawRect(x * self.charWidth, y * self.charHeight, self.charWidth - 1, self.charHeight - 1)

	def send(self, data):
		self.proc.send_input(data)
		self.verticalScrollBar().setValue(0)
		self.selectNone()

	def modifier_string(self, mod):
		if (mod & (self.ctrl | Qt.ShiftModifier | Qt.AltModifier)) == (Qt.ShiftModifier):
			return ";2"
		if (mod & (self.ctrl | Qt.ShiftModifier | Qt.AltModifier)) == (Qt.AltModifier):
			return ";3"
		if (mod & (self.ctrl | Qt.ShiftModifier | Qt.AltModifier)) == (Qt.ShiftModifier | Qt.AltModifier):
			return ";4"
		if (mod & (self.ctrl | Qt.ShiftModifier | Qt.AltModifier)) == (self.ctrl):
			return ";5"
		if (mod & (self.ctrl | Qt.ShiftModifier | Qt.AltModifier)) == (Qt.ShiftModifier | self.ctrl):
			return ";6"
		if (mod & (self.ctrl | Qt.ShiftModifier | Qt.AltModifier)) == (Qt.AltModifier | self.ctrl):
			return ";7"
		if (mod & (self.ctrl | Qt.ShiftModifier | Qt.AltModifier)) == (Qt.ShiftModifier | Qt.AltModifier | self.ctrl):
			return ";8"
		return ""

	def keyPressEvent(self, event):
		if event.key() == Qt.Key_Up:
			if event.modifiers() & (self.ctrl | Qt.ShiftModifier | Qt.AltModifier):
				self.send("\0331" + self.modifier_string(event.modifiers()) + "A")
			elif self.proc.term.application_cursor_keys:
				self.send("\033OA")
			else:
				self.send("\033[A")
		elif event.key() == Qt.Key_Down:
			if event.modifiers() & (self.ctrl | Qt.ShiftModifier | Qt.AltModifier):
				self.send("\033[1" + self.modifier_string(event.modifiers()) + "B")
			elif self.proc.term.application_cursor_keys:
				self.send("\033OB")
			else:
				self.send("\033[B")
		elif event.key() == Qt.Key_Right:
			if (event.modifiers() & self.ctrl) and (not self.proc.term.application_cursor_keys):
				self.send("\033f")
			elif event.modifiers() & (self.ctrl | Qt.ShiftModifier | Qt.AltModifier):
				self.send("\033[1" + self.modifier_string(event.modifiers()) + "C")
			elif self.proc.term.application_cursor_keys:
				self.send("\033OC")
			else:
				self.send("\033[C")
		elif event.key() == Qt.Key_Left:
			if (event.modifiers() & self.ctrl) and (not self.proc.term.application_cursor_keys):
				self.send("\033b")
			elif event.modifiers() & (self.ctrl | Qt.ShiftModifier | Qt.AltModifier):
				self.send("\033[1" + self.modifier_string(event.modifiers()) + "D")
			elif self.proc.term.application_cursor_keys:
				self.send("\033OD")
			else:
				self.send("\033[D")
		elif event.key() == Qt.Key_Home:
			if event.modifiers() & Qt.ShiftModifier:
				self.verticalScrollBar().setValue(self.verticalScrollBar().minimum())
			else:
				self.send("\033OH")
		elif event.key() == Qt.Key_End:
			if event.modifiers() & Qt.ShiftModifier:
				self.verticalScrollBar().setValue(0)
			else:
				self.send("\033OF")
		elif event.key() == Qt.Key_PageUp:
			if event.modifiers() & Qt.ShiftModifier:
				self.verticalScrollBar().setValue(self.verticalScrollBar().value() - self.rows)
			elif event.modifiers() & (self.ctrl | Qt.AltModifier):
				self.send("\033[5" + self.modifier_string(event.modifiers()) + "~")
			else:
				self.send("\033[5~")
		elif event.key() == Qt.Key_PageDown:
			if event.modifiers() & Qt.ShiftModifier:
				self.verticalScrollBar().setValue(self.verticalScrollBar().value() + self.rows)
			elif event.modifiers() & (self.ctrl | Qt.ShiftModifier | Qt.AltModifier):
				self.send("\033[6" + self.modifier_string(event.modifiers()) + "~")
			else:
				self.send("\033[6~")
		elif event.key() == Qt.Key_F1:
			if event.modifiers() & (self.ctrl | Qt.ShiftModifier | Qt.AltModifier):
				self.send("\033[O1" + self.modifier_string(event.modifiers()) + "P")
			else:
				self.send("\033OP")
		elif event.key() == Qt.Key_F2:
			if event.modifiers() & (self.ctrl | Qt.ShiftModifier | Qt.AltModifier):
				self.send("\033[O1" + self.modifier_string(event.modifiers()) + "Q")
			else:
				self.send("\033OQ")
		elif event.key() == Qt.Key_F3:
			if event.modifiers() & (self.ctrl | Qt.ShiftModifier | Qt.AltModifier):
				self.send("\033[O1" + self.modifier_string(event.modifiers()) + "R")
			else:
				self.send("\033OR")
		elif event.key() == Qt.Key_F4:
			if event.modifiers() & (self.ctrl | Qt.ShiftModifier | Qt.AltModifier):
				self.send("\033[O1" + self.modifier_string(event.modifiers()) + "S")
			else:
				self.send("\033OS")
		elif event.key() == Qt.Key_F5:
			self.send("\033[15" + self.modifier_string(event.modifiers()) + "~")
		elif event.key() == Qt.Key_F6:
			self.send("\033[17" + self.modifier_string(event.modifiers()) + "~")
		elif event.key() == Qt.Key_F7:
			self.send("\033[18" + self.modifier_string(event.modifiers()) + "~")
		elif event.key() == Qt.Key_F8:
			self.send("\033[19" + self.modifier_string(event.modifiers()) + "~")
		elif event.key() == Qt.Key_F9:
			self.send("\033[20" + self.modifier_string(event.modifiers()) + "~")
		elif event.key() == Qt.Key_F10:
			self.send("\033[21" + self.modifier_string(event.modifiers()) + "~")
		elif event.key() == Qt.Key_F11:
			self.send("\033[23" + self.modifier_string(event.modifiers()) + "~")
		elif event.key() == Qt.Key_F12:
			self.send("\033[24" + self.modifier_string(event.modifiers()) + "~")
		elif event.key() == Qt.Key_Delete:
			self.send("\033[3" + self.modifier_string(event.modifiers()) + "~")
		elif event.key() == Qt.Key_Backspace:
			self.send("\x7f")
		elif event.key() == Qt.Key_Tab:
			self.send("\t")
		elif event.key() == Qt.Key_Backtab:
			self.send("\033[Z")
		elif (event.key() >= Qt.Key_A) and (event.key() <= Qt.Key_Z) and ((event.modifiers() & (self.ctrl | Qt.AltModifier | Qt.ShiftModifier)) == self.ctrl):
			self.send(chr((event.key() - Qt.Key_A) + 1))
		elif len(event.text()) > 0:
			if (len(event.text()) == 1) and (event.text() >= ' ') and (event.text() <= '~') and (event.modifiers() & Qt.AltModifier):
				self.send("\033" + event.text().encode("utf8"))
			else:
				self.send(event.text().encode("utf8"))

	def event(self, event):
		if (event.type() == QEvent.KeyPress) and ((event.key() == Qt.Key_Tab) or (event.key() == Qt.Key_Backtab)):
			# Intercept tab events
			self.keyPressEvent(event)
			return True
		if (event.type() == QEvent.ShortcutOverride) and (event.key() >= Qt.Key_A) and (event.key() <= Qt.Key_Z) and ((event.modifiers() & (self.ctrl | Qt.AltModifier | Qt.ShiftModifier)) == self.ctrl):
			# Intercept Ctrl+<alpha> events
			event.accept()
			return True
		return super(TerminalView, self).event(event)

	def selectAll(self):
		self.selection = True
		self.selectionStartX = 0
		self.selectionStartY = -self.historySize
		self.selectionEndX = self.cols
		self.selectionEndY = self.rows - 1
		self.viewport().update()

	def selectNone(self):
		if self.selection:
			self.selection = False
			self.viewport().update()

	def mousePressEvent(self, event):
		if event.button() == Qt.RightButton:
			# Bring up context menu
			popup = QMenu()

			action_table = {}

			copy_action = popup.addAction("&Copy")
			copy_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_C))
			action_table[copy_action] = self.copy
			paste_action = popup.addAction("&Paste")
			paste_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_V))
			action_table[paste_action] = self.paste
			popup.addSeparator()

			select_all_action = popup.addAction("Select &all", self.selectAll)
			select_all_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_A))
			action_table[select_all_action] = self.selectAll
			action_table[popup.addAction("Select &none")] = self.selectNone
			popup.addSeparator()

			action = popup.exec_(QCursor.pos())
			if action in action_table:
				action_table[action]()
			return

		if event.button() == Qt.MiddleButton:
			self.paste()
			return

		if event.button() != Qt.LeftButton:
			return

		# Compute which location was clicked
		x = int((event.x() + (self.charWidth / 2)) / self.charWidth)
		y = int(event.y() / self.charHeight)
		self.lastMouseX = x
		self.lastMouseY = y
		if y < 0:
			y = 0
		if x < 0:
			x = 0

		xofs = self.horizontalScrollBar().value()
		yofs = self.verticalScrollBar().value()
		x += xofs
		y += yofs

		if y < self.rows:
			# Detect last meaningful character in line so that anything after it will include the newline
			if y < 0:
				line = self.proc.term.history_screen[y + self.historySize]
				renditions = self.proc.term.history_rendition[y + self.historySize]
			else:
				line = self.proc.term.screen[y]
				renditions = self.proc.term.rendition[y]

			lastX = 0
			for i in xrange(self.cols - 1, -1, -1):
				if (line[i] != u' ') or (renditions[i] & TerminalEmulator.RENDITION_WRITTEN_CHAR):
					lastX = i + 1
					break

			if x > lastX:
				x = self.cols

		# Update position
		if y >= self.rows:
			# Position after end
			self.selectionEndY = self.rows - 1
			self.selectionEndX = self.cols
		else:
			self.selectionEndY = y
			self.selectionEndX = x

		if not (event.modifiers() & Qt.ShiftModifier):
			self.selectionStartX = self.selectionEndX
			self.selectionStartY = self.selectionEndY

		self.selection = (self.selectionStartX != self.selectionEndX) or (self.selectionStartY != self.selectionEndY)
		self.viewport().update()

		self.left_button_down = True

	def mouseMoveEvent(self, event):
		if not self.left_button_down:
			return

		x = int((event.x() + (self.charWidth / 2)) / self.charWidth)
		y = int(event.y() / self.charHeight)
		if (x == self.lastMouseX) and (y == self.lastMouseY):
			# Mouse has not moved to another character
			return
		self.lastMouseX = x
		self.lastMouseY = y

		# Compute new position of mouse
		if y < 0:
			y = 0
		if x < 0:
			x = 0

		xofs = self.horizontalScrollBar().value()
		yofs = self.verticalScrollBar().value()
		x += xofs
		y += yofs

		if y < self.rows:
			# Detect last meaningful character in line so that anything after it will include the newline
			if y < 0:
				line = self.proc.term.history_screen[y + self.historySize]
				renditions = self.proc.term.history_rendition[y + self.historySize]
			else:
				line = self.proc.term.screen[y]
				renditions = self.proc.term.rendition[y]

			lastX = 0
			for i in xrange(self.cols - 1, -1, -1):
				if (line[i] != u' ') or (renditions[i] & TerminalEmulator.RENDITION_WRITTEN_CHAR):
					lastX = i + 1
					break

			if x > lastX:
				x = self.cols

		# Update position
		if y >= self.rows:
			# Position after end
			self.selectionEndY = self.rows - 1
			self.selectionEndX = self.cols
		else:
			self.selectionEndY = y
			self.selectionEndX = x

		self.selection = (self.selectionStartX != self.selectionEndX) or (self.selectionStartY != self.selectionEndY)
		self.viewport().update()

	def mouseReleaseEvent(self, event):
		if event.button() != Qt.LeftButton:
			return
		self.left_button_down = False

	def mouseDoubleClickEvent(self, event):
		if event.button() != Qt.LeftButton:
			return

		# Compute which location was clicked
		x = int(event.x() / self.charWidth)
		y = int(event.y() / self.charHeight)
		self.lastMouseX = x
		self.lastMouseY = y
		if y < 0:
			y = 0
		if x < 0:
			x = 0

		xofs = self.horizontalScrollBar().value()
		yofs = self.verticalScrollBar().value()
		x += xofs
		y += yofs

		if (x < 0) or (x >= self.cols) or (y < -self.historySize) or (y >= self.rows):
			# Out of bounds
			self.selectNone()
			return

		# Get line data for click location
		if y < 0:
			line = self.proc.term.history_screen[y + self.historySize]
		else:
			line = self.proc.term.screen[y]

		if x >= len(line):
			# Out of bounds
			self.selectNone()
			return

		# Find bounds of "word", anything outside 7-bit ascii or (a-z,A-Z,0-9,_,.) counts
		firstX = x
		lastX = x
		for i in xrange(x, -1, -1):
			ch = line[i]
			if not (((ch >= u'0') and (ch <= u'9')) or ((ch >= u'a') and (ch <= u'z')) or ((ch >= u'A') and (ch <= u'Z')) or (ch == u'_') or (ch == u'.') or (ord(ch) >= 0x80)):
				break
			firstX = i
		for i in xrange(x, self.cols, 1):
			ch = line[i]
			if not (((ch >= u'0') and (ch <= u'9')) or ((ch >= u'a') and (ch <= u'z')) or ((ch >= u'A') and (ch <= u'Z')) or (ch == u'_') or (ch == u'.') or (ord(ch) >= 0x80)):
				break
			lastX = i

		# Update selection
		self.selectionStartX = firstX
		self.selectionStartY = y
		self.selectionEndX = lastX + 1
		self.selectionEndY = y
		self.selection = (self.selectionStartX != self.selectionEndX) or (self.selectionStartY != self.selectionEndY)
		self.viewport().update()

	def focusInEvent(self, event):
		self.caretVisible = True
		self.caretBlink = True
		self.cursorTimer.stop()
		self.cursorTimer.start()
		self.updateCaret()

	def focusOutEvent(self, event):
		self.caretVisible = False
		self.updateCaret()

	def updateCaret(self):
		yofs = self.verticalScrollBar().value()
		self.viewport().update(0, (self.cursorY - yofs) * self.charHeight,
			self.viewport().size().width(), self.charHeight)
		self.cursorY = self.proc.term.cursor_row
		self.viewport().update(0, (self.cursorY - yofs) * self.charHeight,
			self.viewport().size().width(), self.charHeight)

	def cursorTimerEvent(self):
		self.caretBlink = not self.caretBlink
		self.updateCaret()

	def updateLines(self):
		if len(self.proc.term.history_screen) != self.historySize:
			# History size changed
			delta = len(self.proc.term.history_screen) - self.historySize
			self.historySize = len(self.proc.term.history_screen)
			self.verticalScrollBar().setMinimum(-self.historySize)

			if self.verticalScrollBar().value() < 0:
				# Not scrolled to bottom, ensure screen is left at its current position
				self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta)

			# Ensure selection stays in the same place
			self.selectionStartY -= delta
			self.selectionEndY -= delta

		changes = self.proc.term.get_dirty_lines()

		if len(changes) > 5:
			self.viewport().update()
		else:
			yofs = self.verticalScrollBar().value()
			for y in changes:
				self.viewport().update(0, (y - yofs) * self.charHeight,
					self.viewport().size().width(), self.charHeight)

		self.updateCaret()
		self.caretBlink = True
		self.cursorTimer.stop()
		self.cursorTimer.start()

	def updateWindowTitle(self, title):
		self.view.setTabName(title)

	def processExit(self, ok):
		if self.auto_close:
			self.view.force_close()
		else:
			self.view.terminal_process_exit()

	def closeRequest(self):
		self.proc.kill()
		return True

	def restart(self, cmd):
		self.proc.restart(cmd)

	def write(self, data):
		self.send(data.encode("string_escape").replace("\"", "\\\""))
		return True

	def copy(self):
		if not self.selection:
			return

		# Determine selection range
		startX, startY = self.selectionStartX, self.selectionStartY
		endX, endY = self.selectionEndX, self.selectionEndY
		if (startY > endY) or ((startY == endY) and (startX > endX)):
			startX, endX = endX, startX
			startY, endY = endY, startY

		# Construct string for selection
		data = u""
		for y in xrange(startY, endY + 1):
			if (y == startY) and (y == endY):
				lineStartX = startX
				lineEndX = endX
			elif y == startY:
				lineStartX = startX
				lineEndX = self.cols
			elif y == endY:
				lineStartX = 0
				lineEndX = endX
			else:
				lineStartX = 0
				lineEndX = self.cols

			if y < 0:
				line = self.proc.term.history_screen[y + self.historySize]
				renditions = self.proc.term.history_rendition[y + self.historySize]
			else:
				line = self.proc.term.screen[y]
				renditions = self.proc.term.rendition[y]

			# Process characters from right to left so that line endings can be detected
			lineText = u""
			nonemptyFound = (lineEndX != self.cols)
			trailingEmpty = 0
			for x in xrange(lineEndX - 1, lineStartX - 1, -1):
				# Get next character and ignore it if it is a trailing space
				if x >= len(line):
					trailingEmpty += 1
					continue
				ch = line[x]
				rendition = renditions[x]
				if (not nonemptyFound) and (ch == u' ') and ((rendition & TerminalEmulator.RENDITION_WRITTEN_CHAR) == 0):
					trailingEmpty += 1
					continue
				nonemptyFound = True

				lineText = ch + lineText

			# Don't insert a newline if this is the last line, or if text is wrapping to the next line
			if (y != endY) and ((lineEndX != self.cols) or (trailingEmpty > 0)):
				lineText += u'\n'
			data += lineText

		# Write text to clipboard
		clipboard = QApplication.clipboard()
		clipboard.clear()
		mime = QMimeData()
		mime.setText(data)
		clipboard.setMimeData(mime)

	def paste(self):
		# Get clipboard contents
		clipboard = QApplication.clipboard()
		mime = clipboard.mimeData()
		binary = False
		if mime.hasFormat("application/octet-stream"):
			data = mime.data("application/octet-stream").data()
			binary = True
		elif mime.hasText():
			data = mime.text().encode("utf8")
		else:
			QMessageBox.critical(self, "Error", "Clipboard is empty or does not have valid contents")
			return

		# Write clipboard contents to the terminal
		if binary:
			data = data.encode("string_escape").replace("\"", "\\\"")
		self.send(data)

	def reinit(self):
		self.proc.reinit()
		self.proc.term.update_callback = self.updateLines
		self.proc.term.title_callback = self.updateWindowTitle

		self.historySize = 0
		self.cursorY = 0
		self.selection = False
		self.verticalScrollBar().setMinimum(0)

		self.proc.resize(self.rows, self.cols)
		areaSize = self.viewport().size()
		self.adjustSize(areaSize.width(), areaSize.height())

		self.viewport().update()

	def fontChanged(self):
		self.initFont()

		areaSize = self.viewport().size()
		self.adjustSize(areaSize.width(), areaSize.height())

		# Terminal size may have changed
		self.proc.resize(self.rows, self.cols)

		self.viewport().update()

	def getPriority(data, filename):
		# Never use this view unless explicitly needed
		return -1
	getPriority = staticmethod(getPriority)

	def getViewName():
		return "Terminal"
	getViewName = staticmethod(getViewName)

	def getShortViewName():
		return "Terminal"
	getShortViewName = staticmethod(getShortViewName)

