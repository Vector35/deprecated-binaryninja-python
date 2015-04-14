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
from Fonts import *
from View import *
from BinaryData import *
from Util import *
from FindDialog import *
import Transform


class HexEditorHistoryEntry:
	def __init__(self, view):
		self.addr = view.data.start() + (view.cursorY * view.cols) + int(view.cursorX / 2)
		self.xofs = view.cursorX % 2
		self.ascii = view.cursorAscii

class HexEditor(QAbstractScrollArea):
	statusUpdated = Signal(QWidget, name="statusUpdated")

	def __init__(self, data, filename, view, parent):
		super(HexEditor, self).__init__(parent)
		self.data = data
		self.data.add_callback(self)
		self.view = view

		self.setCursor(Qt.IBeamCursor)
		self.verticalScrollBar().setCursor(Qt.ArrowCursor)

		self.initFont()
		self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

		# Initialize cursor state
		self.prevCursorY = 0
		self.cursorX = 0
		self.cursorY = 0
		self.selectionStartX = 0
		self.selectionStartY = 0
		self.selectionVisible = False
		self.cursorAscii = False
		self.caretVisible = False
		self.caretBlink = True
		self.insertMode = False
		self.left_button_down = False
		self.status = "Cursor: 0x%.8x" % self.data.start()
		self.cols = 8

		# Initialize scroll bars
		areaSize = self.viewport().size()
		self.adjustSize(areaSize.width(), areaSize.height())

		self.cursorTimer = QTimer()
		self.cursorTimer.setInterval(500)
		self.cursorTimer.setSingleShot(False)
		self.cursorTimer.timeout.connect(self.cursorTimerEvent)
		self.cursorTimer.start()

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

		# Setup navigation
		self.view.register_navigate("hex", self, self.navigate)

		self.search_regex = None
		self.last_search_type = FindDialog.SEARCH_HEX

	def initFont(self):
		# Get font and compute character sizes
		self.font = getMonospaceFont()
		self.font.setKerning(False)
		self.baseline = int(QFontMetricsF(self.font).ascent())

		# Compute width and ensure width is an integer (otherwise there will be rendering errors)
		self.charWidth = QFontMetricsF(self.font).width('X')
		if (self.charWidth % 1.0) < 0.5:
			self.font.setLetterSpacing(QFont.AbsoluteSpacing, -(self.charWidth % 1.0))
			self.charWidth -= self.charWidth % 1.0
		else:
			self.font.setLetterSpacing(QFont.AbsoluteSpacing, 1.0 - (self.charWidth % 1.0))
			self.charWidth += 1.0 - (self.charWidth % 1.0)

		self.charHeight = int(QFontMetricsF(self.font).height()) + getExtraFontSpacing()
		self.charOffset = getFontVerticalOffset()

	def adjustSize(self, width, height):
		# Get absolute position of caret
		ofs = (self.cursorY * self.cols) + int(self.cursorX / 2)
		xofs = self.cursorX % 2
		selOfs = (self.selectionStartY * self.cols) + int(self.selectionStartX / 2)
		selXOfs = self.selectionStartX % 2

		# Compute number of rows and columns
		self.size = len(self.data)
		self.cols = max(8, int((((width - 4) / self.charWidth) - 11) / (4 * 8)) * 8)
		if self.cols < 8:
			self.cols = 8
		self.rows = int(((self.size + 1) + (self.cols - 1)) / self.cols)
		self.visibleRows = int((height - 4) / self.charHeight)

		# Update scroll bar information
		self.verticalScrollBar().setPageStep(self.visibleRows)
		self.verticalScrollBar().setRange(0, self.rows - self.visibleRows)

		# Ensure caret is at same location as before
		self.cursorY = int(ofs / self.cols)
		self.cursorX = (ofs - (self.cursorY * self.cols)) * 2 + xofs
		self.selectionStartY = int(selOfs / self.cols)
		self.selectionStartX = (selOfs - (self.selectionStartY * self.cols)) * 2 + selXOfs

	def resizeEvent(self, event):
		# Window was resized, adjust scroll bar
		self.adjustSize(event.size().width(), event.size().height())
		self.repositionCaret()

	def get_cursor_pos_relative(self):
		return (self.cursorY * self.cols) + int(self.cursorX / 2)

	def get_cursor_pos(self):
		return (self.cursorY * self.cols) + int(self.cursorX / 2) + self.data.start()

	def set_cursor_pos(self, pos):
		self.navigate(pos)

	def get_selection_range_relative(self):
		# Compute selection range
		selStart = (self.selectionStartY * self.cols) + int(self.selectionStartX / 2)
		selEnd = (self.cursorY * self.cols) + int(self.cursorX / 2)
		if selEnd < selStart:
			t = selEnd
			selEnd = selStart
			selStart = t
		return (selStart, selEnd)

	def get_selection_range(self):
		start, end = self.get_selection_range_relative()
		return (start + self.data.start(), end + self.data.start())

	def set_selection_range(self, begin, end):
		if begin > end:
			tmp = begin
			begin = end
			end = tmp

		self.navigate(begin)
		begin = self.get_cursor_pos_relative()
		self.selectionStartX = self.cursorX
		self.selectionStartY = self.cursorY

		ofs = end - self.data.start()
		if end < begin:
			return
		if end > len(self.data):
			end = len(self.data)
		self.cursorY = int(ofs / self.cols)
		self.cursorX = (ofs - (self.cursorY * self.cols)) * 2

		self.viewport().update()

	def is_selection_active(self):
		selStart, selEnd = self.get_selection_range()
		return selStart != selEnd

	def paintEvent(self, event):
		# Initialize painter
		p = QPainter(self.viewport())
		p.setFont(self.font)

		yofs = self.verticalScrollBar().value()

		# Compute range that needs to be updated
		topY = event.rect().y()
		botY = topY + event.rect().height()
		topY = (topY - 2) / self.charHeight
		botY = ((botY - 2) / self.charHeight) + 1

		# Compute selection range
		selection = False
		selStart, selEnd = self.get_selection_range_relative()
		if selEnd != selStart:
			selection = True

		if selection:
			# Find extents of selection rectangle
			startY = int(selStart / self.cols)
			startX = selStart - (startY * self.cols)
			endY = int(selEnd / self.cols)
			endX = selEnd - (endY * self.cols)
			startY -= yofs
			endY -= yofs

			# Draw selection on hex side
			if not self.cursorAscii:
				# Cursor on hex side, draw filled background
				p.setPen(QColor(192, 192, 192))
				p.setBrush(QColor(192, 192, 192))
				if startY == endY:
					p.drawRect(2 + (10 + startX * 3) * self.charWidth, 1 + startY * self.charHeight,
						(((endX - startX) * 3) - 1) * self.charWidth, self.charHeight + 1)
				else:
					p.drawRect(2 + (10 + startX * 3) * self.charWidth, 1 + startY * self.charHeight,
						(((self.cols - startX) * 3) - 1) * self.charWidth, self.charHeight + 1)
					if endX > 0:
						p.drawRect(2 + 10 * self.charWidth, 1 + endY * self.charHeight,
							((endX * 3) - 1) * self.charWidth, self.charHeight + 1)
				if (endY - startY) > 1:
					p.drawRect(2 + 10 * self.charWidth, 1 + (startY + 1) * self.charHeight,
						((self.cols * 3) - 1) * self.charWidth, ((endY - startY) - 1) * self.charHeight + 1)
			else:
				# Cursor on ascii side, draw box around selection
				p.setPen(QColor(128, 128, 128))
				p.setBrush(Qt.NoBrush)
				if startY == endY:
					p.drawRect(1 + (10 + startX * 3) * self.charWidth, 1 + startY * self.charHeight,
						1 + (((endX - startX) * 3) - 1) * self.charWidth, self.charHeight + 1)
				elif (endY == (startY + 1)) and (endX <= startX):
					p.drawRect(1 + (10 + startX * 3) * self.charWidth, 1 + startY * self.charHeight,
						1 + (((self.cols - startX) * 3) - 1) * self.charWidth, self.charHeight + 1)
					if endX > 0:
						p.drawRect(1 + 10 * self.charWidth, 1 + endY * self.charHeight,
							1 + ((endX * 3) - 1) * self.charWidth, self.charHeight + 1)
				else:
					pts = [QPoint(1 + 10 * self.charWidth, 1 + (startY + 1) * self.charHeight),
						QPoint(1 + (10 + startX * 3) * self.charWidth, 1 + (startY + 1) * self.charHeight),
						QPoint(1 + (10 + startX * 3) * self.charWidth, 1 + startY * self.charHeight),
						QPoint(2 + (9 + self.cols * 3) * self.charWidth, 1 + startY * self.charHeight),
						QPoint(2 + (9 + self.cols * 3) * self.charWidth, 2 + (startY + 1) * self.charHeight)]
					p.drawPolyline(pts)
					if endX > 0:
						pts = [QPoint(1 + 10 * self.charWidth, 2 + endY * self.charHeight),
							QPoint(1 + 10 * self.charWidth, 2 + (endY + 1) * self.charHeight),
							QPoint(2 + (9 + endX * 3) * self.charWidth, 2 + (endY + 1) * self.charHeight),
							QPoint(2 + (9 + endX * 3) * self.charWidth, 2 + endY * self.charHeight),
							QPoint(2 + (9 + self.cols * 3) * self.charWidth, 2 + endY * self.charHeight)]
					else:
						pts = [QPoint(1 + 10 * self.charWidth, 2 + endY * self.charHeight),
							QPoint(2 + (9 + self.cols * 3) * self.charWidth, 2 + endY * self.charHeight)]
					p.drawPolyline(pts)
				if (endY - startY) > 1:
					p.drawLine(1 + 10 * self.charWidth, 1 + (startY + 1) * self.charHeight,
						1 + 10 * self.charWidth, 2 + endY * self.charHeight)
					p.drawLine(2 + (9 + self.cols * 3) * self.charWidth, 2 + (startY + 1) * self.charHeight,
						2 + (9 + self.cols * 3) * self.charWidth, 2 + endY * self.charHeight)

			# Draw selection on ascii side
			if self.cursorAscii:
				# Cursor on ascii side, draw filled background
				p.setPen(QColor(192, 192, 192))
				p.setBrush(QColor(192, 192, 192))
				if startY == endY:
					p.drawRect(2 + (11 + startX + self.cols * 3) * self.charWidth, 1 + startY * self.charHeight,
						(endX - startX) * self.charWidth, self.charHeight + 1)
				else:
					p.drawRect(2 + (11 + startX + self.cols * 3) * self.charWidth, 1 + startY * self.charHeight,
						(self.cols - startX) * self.charWidth, self.charHeight + 1)
					if endX > 0:
						p.drawRect(2 + (11 + self.cols * 3) * self.charWidth, 1 + endY * self.charHeight,
							endX * self.charWidth, self.charHeight + 1)
				if (endY - startY) > 1:
					p.drawRect(2 + (11 + self.cols * 3) * self.charWidth, 1 + (startY + 1) * self.charHeight,
						self.cols * self.charWidth, ((endY - startY) - 1) * self.charHeight + 1)
			else:
				# Cursor on hex side, draw box around selection
				p.setPen(QColor(128, 128, 128))
				p.setBrush(Qt.NoBrush)
				if startY == endY:
					p.drawRect(1 + (11 + startX + self.cols * 3) * self.charWidth, 1 + startY * self.charHeight,
						1 + (endX - startX) * self.charWidth, self.charHeight + 1)
				elif (endY == (startY + 1)) and (endX < startX):
					p.drawRect(1 + (11 + startX + self.cols * 3) * self.charWidth, 1 + startY * self.charHeight,
						1 + (self.cols - startX) * self.charWidth, self.charHeight + 1)
					if endX > 0:
						p.drawRect(1 + (11 + self.cols * 3) * self.charWidth, 1 + endY * self.charHeight,
							1 + endX * self.charWidth, self.charHeight + 1)
				else:
					pts = [QPoint(1 + (11 + self.cols * 3) * self.charWidth, 1 + (startY + 1) * self.charHeight),
						QPoint(1 + (11 + startX + self.cols * 3) * self.charWidth, 1 + (startY + 1) * self.charHeight),
						QPoint(1 + (11 + startX + self.cols * 3) * self.charWidth, 1 + startY * self.charHeight),
						QPoint(2 + (11 + self.cols * 4) * self.charWidth, 1 + startY * self.charHeight),
						QPoint(2 + (11 + self.cols * 4) * self.charWidth, 2 + (startY + 1) * self.charHeight)]
					p.drawPolyline(pts)
					if endX > 0:
						pts = [QPoint(1 + (11 + self.cols * 3) * self.charWidth, 2 + endY * self.charHeight),
							QPoint(1 + (11 + self.cols * 3) * self.charWidth, 2 + (endY + 1) * self.charHeight),
							QPoint(2 + (11 + endX + self.cols * 3) * self.charWidth, 2 + (endY + 1) * self.charHeight),
							QPoint(2 + (11 + endX + self.cols * 3) * self.charWidth, 2 + endY * self.charHeight),
							QPoint(2 + (11 + self.cols * 4) * self.charWidth, 2 + endY * self.charHeight)]
					else:
						pts = [QPoint(1 + (11 + self.cols * 3) * self.charWidth, 2 + endY * self.charHeight),
							QPoint(2 + (11 + self.cols * 4) * self.charWidth, 2 + endY * self.charHeight)]
					p.drawPolyline(pts)
				if (endY - startY) > 1:
					p.drawLine(1 + (11 + self.cols * 3) * self.charWidth, 1 + (startY + 1) * self.charHeight,
						1 + (11 + self.cols * 3) * self.charWidth, 2 + endY * self.charHeight)
					p.drawLine(2 + (11 + self.cols * 4) * self.charWidth, 2 + (startY + 1) * self.charHeight,
						2 + (11 + self.cols * 4) * self.charWidth, 2 + endY * self.charHeight)

			self.selectionVisible = True

		# Paint each line
		for y in range(topY, botY):
			# Skip if line is invalid
			if (y + yofs) < 0:
				continue
			lineAddr = ((y + yofs) * self.cols) + self.data.start()
			if lineAddr > self.data.end():
				break

			# Draw address
			p.setPen(QColor(0, 128, 128))
			p.drawText(2, 2 + y * self.charHeight + self.charOffset + self.baseline, "%.8x" % lineAddr)

			if lineAddr == self.data.end():
				break

			# Get data for the line
			bytes = self.data.read(lineAddr, self.cols)
			modifications = self.data.get_modification(lineAddr, self.cols)

			lineStr = ""
			ascii = ""
			paintOfs = 0

			last_color = None
			orig_color = Qt.black
			changed_color = Qt.red
			insert_color = Qt.blue
			not_present_color = Qt.gray

			if (len(bytes) != self.cols) or (len(modifications) != self.cols):
				# Construct string for line byte by byte
				for x in range(0, self.cols):
					if (lineAddr + x) >= self.data.end():
						lineStr += "   "
					else:
						try:
							byte = self.data.read_uint8(lineAddr + x)
							modification = self.data.get_modification(lineAddr + x, 1)[0]

							if modification == DATA_ORIGINAL:
								color = orig_color
							elif modification == DATA_CHANGED:
								color = changed_color
							elif modification == DATA_INSERTED:
								color = insert_color
							if (color != last_color) and (last_color != None):
								p.setPen(last_color)
								p.drawText(2 + (10 + paintOfs * 3) * self.charWidth,
									2 + y * self.charHeight + self.charOffset +
									self.baseline, lineStr)
								p.drawText(2 + (11 + paintOfs + self.cols * 3) * self.charWidth,
									2 + y * self.charHeight + self.charOffset +
									self.baseline, ascii)
								paintOfs = x
								lineStr = ""
								ascii = ""
							last_color = color

							lineStr += "%.2x" % byte
							if (byte >= 0x20) and (byte <= 0x7e):
								ascii += chr(byte)
							else:
								ascii += "."
						except:
							color = not_present_color
							if (color != last_color) and (last_color != None):
								p.setPen(last_color)
								p.drawText(2 + (10 + paintOfs * 3) * self.charWidth,
									2 + y * self.charHeight + self.charOffset +
									self.baseline, lineStr)
								p.drawText(2 + (11 + paintOfs + self.cols * 3) * self.charWidth,
									2 + y * self.charHeight + self.charOffset +
									self.baseline, ascii)
								paintOfs = x
								lineStr = ""
								ascii = ""
							last_color = color

							lineStr += "??"
							ascii += "?"

						if ((x + 1) < self.cols) and ((x % 8) == 7) and ((lineAddr + x + 1) < self.data.end()):
							lineStr += "-"
						else:
							lineStr += " "
			else:
				# Construct string for line using data buffers read above
				for x in range(0, self.cols):
					if (lineAddr + x) >= self.data.end():
						lineStr += "   "
					else:
						byte = ord(bytes[x])
						modification = modifications[x]

						if modification == DATA_ORIGINAL:
							color = orig_color
						elif modification == DATA_CHANGED:
							color = changed_color
						elif modification == DATA_INSERTED:
							color = insert_color
						if (color != last_color) and (last_color != None):
							p.setPen(last_color)
							p.drawText(2 + (10 + paintOfs * 3) * self.charWidth,
								2 + y * self.charHeight + self.charOffset + self.baseline, lineStr)
							p.drawText(2 + (11 + paintOfs + self.cols * 3) * self.charWidth,
								2 + y * self.charHeight + self.charOffset + self.baseline, ascii)
							paintOfs = x
							lineStr = ""
							ascii = ""
						last_color = color

						lineStr += "%.2x" % byte
						if (byte >= 0x20) and (byte <= 0x7e):
							ascii += chr(byte)
						else:
							ascii += "."

						if ((x + 1) < self.cols) and ((x % 8) == 7) and ((lineAddr + x + 1) < self.data.end()):
							lineStr += "-"
						else:
							lineStr += " "

			# Draw line
			if last_color != None:
				p.setPen(last_color)
				if paintOfs == 0:
					p.drawText(2 + 10 * self.charWidth, 2 + y * self.charHeight + self.charOffset + self.baseline,
						lineStr + " " + ascii)
				else:
					p.drawText(2 + (10 + paintOfs * 3) * self.charWidth,
						2 + y * self.charHeight + self.charOffset + self.baseline, lineStr)
					p.drawText(2 + (11 + paintOfs + self.cols * 3) * self.charWidth,
						2 + y * self.charHeight + self.charOffset + self.baseline, ascii)

		# Draw caret if visible
		if self.caretVisible and not selection:
			# Draw caret on hex side
			if self.cursorAscii:
				# Cursor is on ascii side, render a gray box around hex byte
				p.setCompositionMode(QPainter.CompositionMode_SourceOver)
				p.setPen(QColor(128, 128, 128))
				p.setBrush(Qt.NoBrush)
				p.drawRect(1 + (10 + (int(self.cursorX / 2) * 3)) * self.charWidth,
					1 + (self.cursorY - yofs) * self.charHeight, (self.charWidth * 2) + 1, self.charHeight + 1)
			elif self.caretBlink:
				# Cursor is on hex side, draw inverted caret over selected character
				if self.x11:
					p.setCompositionMode(QPainter.RasterOp_SourceXorDestination)
				else:
					p.setCompositionMode(QPainter.CompositionMode_Difference)
				p.setPen(Qt.NoPen)
				p.setBrush(Qt.white)
				caret_width = self.charWidth
				caret_ofs = 0
				if self.insertMode:
					caret_width = 2
					caret_ofs = -1
				p.drawRect(2 + (10 + (int(self.cursorX / 2) * 3) + (self.cursorX % 2)) * self.charWidth + caret_ofs,
					1 + (self.cursorY - yofs) * self.charHeight, caret_width, self.charHeight + 1)

			# Draw caret on ascii side
			if not self.cursorAscii:
				# Cursor is on hex side, render a gray box around ascii character
				p.setCompositionMode(QPainter.CompositionMode_SourceOver)
				p.setPen(QColor(128, 128, 128))
				p.setBrush(Qt.NoBrush)
				p.drawRect(1 + (11 + (self.cols * 3) + (self.cursorX / 2)) * self.charWidth,
					1 + (self.cursorY - yofs) * self.charHeight, self.charWidth + 1, self.charHeight + 1)
			elif self.caretBlink:
				# Cursor is on ascii side, draw inverted caret over selected character
				if self.x11:
					p.setCompositionMode(QPainter.RasterOp_SourceXorDestination)
				else:
					p.setCompositionMode(QPainter.CompositionMode_Difference)
				p.setPen(Qt.NoPen)
				p.setBrush(Qt.white)
				caret_width = self.charWidth
				caret_ofs = 0
				if self.insertMode:
					caret_width = 2
					caret_ofs = -1
				p.drawRect(2 + (11 + (self.cols * 3) + (self.cursorX / 2)) * self.charWidth + caret_ofs,
					1 + (self.cursorY - yofs) * self.charHeight, caret_width, self.charHeight + 1)

			self.prevCursorY = self.cursorY

	def updateCaret(self):
		# Rerender both the old caret position and the new caret position
		yofs = self.verticalScrollBar().value()
		self.viewport().update(0, 1 + (self.prevCursorY - yofs) * self.charHeight,
			self.viewport().size().width(), self.charHeight + 2)
		self.viewport().update(0, 1 + (self.cursorY - yofs) * self.charHeight,
			self.viewport().size().width(), self.charHeight + 2)

	def repositionCaret(self):
		 # Ensure new caret position is visible
		yofs = self.verticalScrollBar().value()
		if self.cursorY < yofs:
			self.verticalScrollBar().setValue(self.cursorY)
		elif self.cursorY >= (yofs + self.visibleRows):
			self.verticalScrollBar().setValue(self.cursorY - (self.visibleRows - 1))

		# Force caret to be visible and repaint
		self.caretBlink = True
		self.cursorTimer.stop()
		self.cursorTimer.start()
		self.updateCaret()

		self.status = "Cursor: 0x%.8x" % (self.data.start() + (self.cursorY * self.cols) + int(self.cursorX / 2))
		self.statusUpdated.emit(self)

	def focusInEvent(self, event):
		self.caretVisible = True
		self.updateCaret()

	def focusOutEvent(self, event):
		self.caretVisible = False
		self.updateCaret()

	def cursorTimerEvent(self):
		self.caretBlink = not self.caretBlink
		self.updateCaret()

	def go_to_address(self, selection):
		addr_str, ok = QInputDialog.getText(self, "Go To Address", "Address:", QLineEdit.Normal)
		if ok:
			try:
				addr = int(addr_str, 16)
				if (addr < self.data.start()) or (addr > self.data.end()):
					if hasattr(self.data, "symbols_by_name") and (addr_str in self.data.symbols_by_name):
						addr = self.data.symbols_by_name[addr_str]
					else:
						QMessageBox.critical(self, "Error", "Address out of range")
						ok = False
			except:
				if hasattr(self.data, "symbols_by_name") and (addr_str in self.data.symbols_by_name):
					addr = self.data.symbols_by_name[addr_str]
				elif (addr_str[0] == '@') and hasattr(self.data, "symbols_by_name") and (addr_str[1:] in self.data.symbols_by_name):
					addr = self.data.symbols_by_name[addr_str[1:]]
				else:
					QMessageBox.critical(self, "Error", "Invalid address or symbol")
					ok = False

			if ok:
				self.cursorY = int((addr - self.data.start()) / self.cols)
				self.cursorX = int((addr - self.data.start()) % self.cols) * 2

		if not selection:
			self.deselect()

	def show_disassembly(self):
		ofs = self.data.start() + (self.cursorY * self.cols) + int(self.cursorX / 2)
		if not self.view.navigate("disassembler", ofs):
			QMessageBox.critical(self, "Cursor Not Within Function", "The position of the cursor " \
				"is not within any function.  This is either because the analysis has not completed " \
				"yet, or the cursor is not within recognized code.  Use the 'P' hotkey to force " \
				"a function to start at the current position of the cursor, or select 'Disassembler' " \
				"from the view list to show the last disassembled location.")

	def make_proc(self):
		ofs = self.data.start() + (self.cursorY * self.cols) + int(self.cursorX / 2)
		self.view.navigate("make_proc", ofs)

	def input_hex_digit(self, digit):
		self.view.begin_undo()

		if self.is_selection_active():
			# Selection active, delete selection
			selStart, selEnd = self.get_selection_range_relative()
			self.data.remove(selStart + self.data.start(), selEnd - selStart)
			self.cursorY = int(selStart / self.cols)
			self.cursorX = (selStart - (self.cursorY * self.cols)) * 2

		ofs = self.data.start() + (self.cursorY * self.cols) + int(self.cursorX / 2)
		if (ofs == self.data.end()) or (self.insertMode and (not self.cursorX & 1)):
			value = 0
		else:
			value = self.data.read_uint8(ofs)
		if self.cursorX & 1:
			# Low 4 bits
			value = (value & 0xf0) | digit
		else:
			# High 4 bits
			value = (value & 0xf) | (digit << 4)
		if self.insertMode and (not self.cursorX & 1):
			self.data.insert(ofs, chr(value))
		else:
			self.data.write_uint8(ofs, value)

		self.cursorX += 1
		if self.cursorX >= (self.cols * 2):
			self.cursorX = 0
			self.cursorY += 1
		self.deselect()

		self.view.commit_undo()

	def input_byte(self, value):
		self.view.begin_undo()

		if self.is_selection_active():
			# Selection active, delete selection
			selStart, selEnd = self.get_selection_range_relative()
			self.data.remove(selStart + self.data.start(), selEnd - selStart)
			self.cursorY = int(selStart / self.cols)
			self.cursorX = (selStart - (self.cursorY * self.cols)) * 2

		ofs = self.data.start() + (self.cursorY * self.cols) + int(self.cursorX / 2)
		if self.insertMode:
			self.data.insert(ofs, chr(value))
		else:
			self.data.write_uint8(ofs, value)

		self.cursorX += 2
		if self.cursorX >= (self.cols * 2):
			self.cursorX = 0
			self.cursorY += 1
		self.deselect()

		self.view.commit_undo()

	def deselect(self):
		self.selectionStartX = self.cursorX
		self.selectionStartY = self.cursorY
		if self.selectionVisible:
			self.viewport().update()

	def write(self, data):
		insert = self.insertMode
		selStart, selEnd = self.get_selection_range_relative()
		if selEnd != selStart:
			# Always use insert mode when overwriting a region with paste
			insert = True

		self.view.begin_undo()

		if insert and (selEnd - selStart) == len(data):
			# Overwriting data with the same size buffer, just write it (if this is not done, you will
			# not be able to transform in place inside an ELF binary
			insert = False
		elif selEnd != selStart:
			self.data.remove(selStart + self.data.start(), selEnd - selStart)

		if insert:
			written = self.data.insert(selStart + self.data.start(), data)
			if written != len(data):
				return False
		else:
			written = self.data.write(selStart + self.data.start(), data)
			if written != len(data):
				return False

		self.cursorY = int((selStart + written) / self.cols)
		self.cursorX = ((selStart + written) - (self.cursorY * self.cols)) * 2
		self.deselect()
		self.repositionCaret()
		self.view.commit_undo()
		return True

	def follow_pointer(self):
		if self.data.architecture() == "x86_64":
			value = self.data.read(self.get_cursor_pos(), 8)
			if len(value) < 8:
				QMessageBox.critical(self, "Follow Pointer", "Unable to read pointer at cursor location.")
				return
			ptr = struct.unpack("<Q", value)[0]
		else:
			value = self.data.read(self.get_cursor_pos(), 4)
			if len(value) < 4:
				QMessageBox.critical(self, "Follow Pointer", "Unable to read pointer at cursor location.")
				return
			ptr = struct.unpack("<I", value)[0]

		self.view.add_history_entry()
		if not self.navigate(ptr):
			QMessageBox.critical(self, "Follow Pointer", "Address not valid.")

	def keyPressEvent(self, event):
		if event.key() == Qt.Key_Left:
			count = 1
			if event.modifiers() & self.ctrl:
				# If control is held, move 8 bytes at a time
				if self.cursorAscii or (event.modifiers() & Qt.ShiftModifier):
					count = 8
				else:
					count = 16

			if self.cursorAscii or (event.modifiers() & Qt.ShiftModifier):
				step = 2
				self.cursorX &= ~1
			else:
				step = 1

			for i in range(0, count):
				if self.cursorX > 0:
					# Movement within a line
					self.cursorX -= step
				elif self.cursorY > 0:
					# Move to previous line
					self.cursorX = (self.cols * 2) - step
					self.cursorY -= 1

			if not (event.modifiers() & Qt.ShiftModifier):
				self.deselect()
		elif event.key() == Qt.Key_Right:
			count = 1
			if event.modifiers() & self.ctrl:
				# If control is held, move 8 bytes at a time
				if self.cursorAscii or (event.modifiers() & Qt.ShiftModifier):
					count = 8
				else:
					count = 16

			if self.cursorAscii or (event.modifiers() & Qt.ShiftModifier):
				step = 2
				self.cursorX &= ~1
			else:
				step = 1

			for i in range(0, count):
				# Ensure cursor is not at end of file
				rowStart = self.cursorY * self.cols
				if (rowStart + (self.cursorX / 2)) < self.size:
					if self.cursorX < ((self.cols * 2) - step):
						# Movement within a line
						self.cursorX += step
					else:
						# Move to next line
						self.cursorX = 0
						self.cursorY += 1

			if not (event.modifiers() & Qt.ShiftModifier):
				self.deselect()
		elif event.key() == Qt.Key_Up:
			if event.modifiers() & Qt.ShiftModifier:
				self.cursorX &= ~1

			if self.cursorY > 0:
				# Not at start of file
				self.cursorY -= 1
			else:
				# Position at start of file
				self.cursorX = 0

			if not (event.modifiers() & Qt.ShiftModifier):
				self.deselect()
		elif event.key() == Qt.Key_Down:
			if event.modifiers() & Qt.ShiftModifier:
				self.cursorX &= ~1

			if self.cursorY < (self.rows - 1):
				# Not at end of file
				self.cursorY += 1
				rowStart = self.cursorY * self.cols
				if ((rowStart + (self.cursorX / 2)) > self.size) or (((rowStart + (self.cursorX / 2)) == self.size) and
					((self.cursorX % 2) != 0)):
					# End of line is before new position
					self.cursorX = (self.size - rowStart) * 2
			else:
				# Position at end of file
				rowStart = self.cursorY * self.cols
				self.cursorX = (self.size - rowStart) * 2

			if not (event.modifiers() & Qt.ShiftModifier):
				self.deselect()
		elif event.key() == Qt.Key_PageUp:
			if event.modifiers() & Qt.ShiftModifier:
				self.cursorX &= ~1

			if self.cursorY >= self.visibleRows:
				# Not at start of file, move up a page
				self.cursorY -= self.visibleRows
				yofs = self.verticalScrollBar().value()
				yofs -= self.visibleRows
				if yofs < 0:
					# Ensure view start is within bounds
					yofs = 0
				self.verticalScrollBar().setValue(yofs)
			else:
				# Position at start of file
				self.cursorX = 0
				self.cursorY = 0

			if not (event.modifiers() & Qt.ShiftModifier):
				self.deselect()
		elif event.key() == Qt.Key_PageDown:
			if event.modifiers() & Qt.ShiftModifier:
				self.cursorX &= ~1

			if self.cursorY < (self.rows - self.visibleRows - 1):
				# Not at end of file, move down a page
				self.cursorY += self.visibleRows
				yofs = self.verticalScrollBar().value()
				yofs += self.visibleRows
				if yofs > (self.rows - self.visibleRows):
					# Ensure view start is within bounds
					yofs = self.rows - self.visibleRows
				self.verticalScrollBar().setValue(yofs)
			elif self.cursorY == (self.rows - self.visibleRows - 1):
				# Cursor will be on last line
				self.cursorY += self.visibleRows
				rowStart = self.cursorY * self.cols
				if ((rowStart + (self.cursorX / 2)) > self.size) or (((rowStart + (self.cursorX / 2)) == self.size) and
					((self.cursorX % 2) != 0)):
					# End of line is before new cursor position
					self.cursorX = (self.size - rowStart) * 2
			else:
				# Position at end of file
				self.cursorY = self.rows - 1
				rowStart = self.cursorY * self.cols
				self.cursorX = (self.size - rowStart) * 2

			if not (event.modifiers() & Qt.ShiftModifier):
				self.deselect()
		elif event.key() == Qt.Key_Home:
			if event.modifiers() & self.ctrl:
				# Ctrl+Home positions cursor to start of file
				self.cursorY = 0
			self.cursorX = 0

			if not (event.modifiers() & Qt.ShiftModifier):
				self.deselect()
		elif event.key() == Qt.Key_End:
			if event.modifiers() & self.ctrl:
				# Ctrl+End positions cursor to end of file
				self.cursorY = self.rows - 1
				rowStart = self.cursorY * self.cols
				self.cursorX = (self.size - rowStart) * 2
			elif self.cursorY == (self.rows - 1):
				# Last line of file
				rowStart = self.cursorY * self.cols
				self.cursorX = (self.size - rowStart) * 2
			else:
				# Not last line of file, position at last character
				if self.cursorAscii or (event.modifiers() & Qt.ShiftModifier):
					self.cursorX = (self.cols * 2) - 2
				else:
					self.cursorX = (self.cols * 2) - 1

			if not (event.modifiers() & Qt.ShiftModifier):
				self.deselect()
		elif event.key() == Qt.Key_Tab:
			# Tab switches between hex and ascii
			self.cursorAscii = not self.cursorAscii
			if self.cursorAscii:
				self.cursorX &= ~1
		elif event.key() == Qt.Key_Backspace:
			self.view.begin_undo()
			if self.is_selection_active():
				# Selection active, delete selection
				selStart, selEnd = self.get_selection_range_relative()
				self.data.remove(selStart + self.data.start(), selEnd - selStart)
				self.cursorY = int(selStart / self.cols)
				self.cursorX = (selStart - (self.cursorY * self.cols)) * 2
			else:
				# No selection, save offset and move cursor to the left
				ofs = self.data.start() + (self.cursorY * self.cols) + int(self.cursorX / 2)
				oldCursorX = self.cursorX
				if self.cursorX > 0:
					self.cursorX -= 1
				elif self.cursorY > 0:
					self.cursorX = (self.cols * 2) - 1
					self.cursorY -= 1
				if self.cursorAscii:
					self.cursorX &= ~1
				# If on the ascii side or backspacing over first character, delete the byte
				if self.cursorAscii:
					if ofs > 0:
						self.data.remove(ofs - 1, 1)
				elif oldCursorX & 1:
					self.data.remove(ofs, 1)
			self.deselect()
			self.view.commit_undo()
		elif event.key() == Qt.Key_Delete:
			self.view.begin_undo()
			if self.is_selection_active():
				# Selection active, delete selection
				selStart, selEnd = self.get_selection_range_relative()
				self.data.remove(selStart + self.data.start(), selEnd - selStart)
				self.cursorY = int(selStart / self.cols)
				self.cursorX = (selStart - (self.cursorY * self.cols)) * 2
			else:
				# No selection, delete current byte
				ofs = self.data.start() + (self.cursorY * self.cols) + int(self.cursorX / 2)
				self.data.remove(ofs, 1)
			self.deselect()
			self.view.commit_undo()
		elif (event.key() == Qt.Key_G) and ((event.modifiers() & self.ctrl) or (event.modifiers() & self.command)):
			self.go_to_address(event.modifiers() & Qt.ShiftModifier)
		elif (event.key() == Qt.Key_H) and ((event.modifiers() & self.ctrl) or (event.modifiers() & self.command)):
			self.show_disassembly()
		elif (event.key() == Qt.Key_I) and ((event.modifiers() & self.ctrl) or (event.modifiers() & self.command)):
			self.insertMode = not self.insertMode
		elif (event.key() == Qt.Key_N) and ((event.modifiers() & self.ctrl) or (event.modifiers() & self.command)):
			self.find_next()
		elif (event.key() == Qt.Key_P) and ((event.modifiers() & self.ctrl) or (event.modifiers() & self.command)):
			self.make_proc()
		elif (event.key() == Qt.Key_Slash) and ((event.modifiers() & self.ctrl) or (event.modifiers() & self.command)):
			dlg = FindDialog(FindDialog.SEARCH_REGEX, self)
			if dlg.exec_() == QDialog.Accepted:
				self.perform_find(dlg)
		elif (event.key() == Qt.Key_Asterisk) and ((event.modifiers() & self.ctrl) or (event.modifiers() & self.command)):
			self.follow_pointer()
		elif not self.cursorAscii:
			# Not in ASCII mode, check for hex digits or non-modifier versions of commands
			if event.key() == Qt.Key_0:
				self.input_hex_digit(0)
			elif event.key() == Qt.Key_1:
				self.input_hex_digit(1)
			elif event.key() == Qt.Key_2:
				self.input_hex_digit(2)
			elif event.key() == Qt.Key_3:
				self.input_hex_digit(3)
			elif event.key() == Qt.Key_4:
				self.input_hex_digit(4)
			elif event.key() == Qt.Key_5:
				self.input_hex_digit(5)
			elif event.key() == Qt.Key_6:
				self.input_hex_digit(6)
			elif event.key() == Qt.Key_7:
				self.input_hex_digit(7)
			elif event.key() == Qt.Key_8:
				self.input_hex_digit(8)
			elif event.key() == Qt.Key_9:
				self.input_hex_digit(9)
			elif event.key() == Qt.Key_A:
				self.input_hex_digit(0xa)
			elif event.key() == Qt.Key_B:
				self.input_hex_digit(0xb)
			elif event.key() == Qt.Key_C:
				self.input_hex_digit(0xc)
			elif event.key() == Qt.Key_D:
				self.input_hex_digit(0xd)
			elif event.key() == Qt.Key_E:
				self.input_hex_digit(0xe)
			elif event.key() == Qt.Key_F:
				self.input_hex_digit(0xf)
			elif event.key() == Qt.Key_G:
				self.go_to_address(event.modifiers() & Qt.ShiftModifier)
			elif event.key() == Qt.Key_H:
				self.show_disassembly()
			elif event.key() == Qt.Key_I:
				self.insertMode = not self.insertMode
			elif event.key() == Qt.Key_N:
				self.find_next()
			elif event.key() == Qt.Key_P:
				self.make_proc()
			elif event.key() == Qt.Key_Slash:
				dlg = FindDialog(FindDialog.SEARCH_REGEX, self)
				if dlg.exec_() == QDialog.Accepted:
					self.perform_find(dlg)
			elif event.key() == Qt.Key_Asterisk:
				self.follow_pointer()
			else:
				# Pass unhandled key to parent
				super(HexEditor, self).keyPressEvent(event)
		else:
			# Ascii mode, look for a valid ASCII character
			if (len(event.text()) == 1) and (event.text() >= ' ') and (event.text() <= '~'):
				self.input_byte(ord(event.text()))
			else:
				# Pass unhandled key to parent
				super(HexEditor, self).keyPressEvent(event)

		self.repositionCaret()
		if self.selectionVisible or event.modifiers() & Qt.ShiftModifier:
			self.viewport().update()

	def keyReleaseEvent(self, event):
		# Pass unhandled key to parent
		super(HexEditor, self).keyReleaseEvent(event)

	def event(self, event):
		# Intercept tab events
		if (event.type() == QEvent.KeyPress) and (event.key() == Qt.Key_Tab):
			self.keyPressEvent(event)
			return True
		return super(HexEditor, self).event(event)

	def write_range_to_clipboard(self, selStart, selEnd, encoder, binary):
		data = self.data.read(selStart + self.data.start(), selEnd - selStart)
		if len(data) != (selEnd - selStart):
			QMessageBox.critical(self, "Error", "Unable to read entire selected range")
			return False

		if encoder:
			try:
				data = encoder(data)
			except CancelException:
				return
			except:
				QMessageBox.critical(self, "Error", "Encoding failed: " + str(sys.exc_info()[1]))
				return False

		clipboard = QApplication.clipboard()
		clipboard.clear()
		mime = QMimeData()
		if binary:
			mime.setText(data.encode("string_escape").replace("\"", "\\\""))
			mime.setData("application/octet-stream", QByteArray(data))
		else:
			mime.setText(data)
		clipboard.setMimeData(mime)
		return True

	def selectAll(self):
		self.selectionStartX = 0
		self.selectionStartY = 0
		self.cursorY = int(self.size / self.cols)
		self.cursorX = (self.size - (self.cursorY * self.cols)) * 2
		self.viewport().update()

	def selectNone(self):
		self.deselect()
		self.repositionCaret()
		self.viewport().update()

	def cut(self):
		selStart, selEnd = self.get_selection_range_relative()
		if selEnd == selStart:
			return
		if self.write_range_to_clipboard(selStart, selEnd, None, True):
			self.view.begin_undo()
			self.data.remove(selStart + self.data.start(), selEnd - selStart)
			self.cursorY = int(selStart / self.cols)
			self.cursorX = (selStart - (self.cursorY * self.cols)) * 2
			self.deselect()
			self.repositionCaret()
			self.view.commit_undo()

	def copy(self):
		# Compute selection range
		selStart, selEnd = self.get_selection_range_relative()
		if selEnd == selStart:
			return
		self.write_range_to_clipboard(selStart, selEnd, None, True)

	def copy_as(self, encoder, binary):
		# Compute selection range
		selStart, selEnd = self.get_selection_range_relative()
		if selEnd == selStart:
			return
		self.write_range_to_clipboard(selStart, selEnd, encoder, binary)

	def copy_address(self):
		selStart, selEnd = self.get_selection_range()
		clipboard = QApplication.clipboard()
		clipboard.clear()
		mime = QMimeData()
		mime.setText("0x%x" % selStart)
		clipboard.setMimeData(mime)

	def paste(self):
		self.paste_from(None)

	def paste_from(self, decoder):
		insert = self.insertMode
		selStart, selEnd = self.get_selection_range_relative()
		if selEnd != selStart:
			# Always use insert mode when overwriting a region with paste
			insert = True

		# Get clipboard contents
		clipboard = QApplication.clipboard()
		mime = clipboard.mimeData()
		if mime.hasFormat("application/octet-stream"):
			data = mime.data("application/octet-stream").data()
		elif mime.hasText():
			data = mime.text().encode("utf8")
		else:
			QMessageBox.critical(self, "Error", "Clipboard is empty or does not have valid contents")
			return

		if decoder:
			try:
				data = str(decoder(data))
			except CancelException:
				return
			except:
				QMessageBox.critical(self, "Error", "Decoding failed: " + str(sys.exc_info()[1]))
				return

		# Write clipboard contents to the file
		self.view.begin_undo()
		if selEnd != selStart:
			self.data.remove(selStart + self.data.start(), selEnd - selStart)
		if insert:
			written = self.data.insert(selStart + self.data.start(), data)
			if written != len(data):
				QMessageBox.critical(self, "Error", "Unable to paste entire contents")
		else:
			written = self.data.write(selStart + self.data.start(), data)
			if written != len(data):
				QMessageBox.critical(self, "Error", "Unable to paste entire contents")

		self.cursorY = int((selStart + written) / self.cols)
		self.cursorX = ((selStart + written) - (self.cursorY * self.cols)) * 2
		self.deselect()
		self.repositionCaret()
		self.view.commit_undo()

	def perform_find(self, dlg):
		self.search_regex = dlg.search_regex()
		self.search_start = (self.data.start() + (self.cursorY * self.cols) + int(self.cursorX / 2))

		found_loc = self.data.find(self.search_regex, self.search_start)
		if found_loc != -1:
			self.view.add_history_entry()
			self.navigate(found_loc)
			self.search_pos = found_loc + 1
			return

		found_loc = self.data.find(self.search_regex, self.data.start())
		if (found_loc != -1) and (found_loc < self.search_start):
			self.view.add_history_entry()
			self.navigate(found_loc)
			self.search_pos = found_loc + 1
			return

		QMessageBox.information(self, "Not Found", "Search string not found.")

	def find(self):
		dlg = FindDialog(self.last_search_type, self)
		if dlg.exec_() == QDialog.Accepted:
			self.last_search_type = dlg.search_type()
			self.perform_find(dlg)

	def find_next(self):
		if self.search_regex == None:
			QMessageBox.critical(self, "Error", "No active search")
			return

		found_loc = self.data.find(self.search_regex, self.search_pos)
		if self.search_pos >= self.search_start:
			if found_loc != -1:
				self.view.add_history_entry()
				self.navigate(found_loc)
				self.search_pos = found_loc + 1
				return
			self.search_pos = 0
		else:
			if (found_loc != -1) and (found_loc < self.search_start):
				self.view.add_history_entry()
				self.navigate(found_loc)
				self.search_pos = found_loc + 1
				return

			QMessageBox.information(self, "End of Search", "No additional matches found.")
			self.search_pos = self.search_start
			return

		found_loc = self.data.find(self.search_regex, self.search_pos)
		if found_loc < self.search_start:
			self.view.add_history_entry()
			self.navigate(found_loc)
			self.search_pos = found_loc + 1
			return

		QMessageBox.information(self, "End of Search", "No additional matches found.")
		self.search_pos = self.search_start

	def mousePressEvent(self, event):
		if event.button() == Qt.RightButton:
			# Bring up context menu
			popup = QMenu()

			action_table = {}

			cut_action = popup.addAction("C&ut")
			cut_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_X))
			action_table[cut_action] = self.cut
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

			populate_copy_as_menu(popup.addMenu("Copy &as"), self, action_table)
			popup.addAction("Copy address", self.copy_address)
			populate_paste_from_menu(popup.addMenu("Paste &from"), self, action_table)
			Transform.populate_transform_menu(popup.addMenu("&Transform"), self, action_table)
			popup.addSeparator()

			show_disasm_action = popup.addAction("View in &disassembler")
			if self.cursorAscii:
				show_disasm_action.setShortcut(QKeySequence(self.ctrl_hotkey + Qt.Key_H))
			else:
				show_disasm_action.setShortcut(QKeySequence(Qt.Key_H))
			action_table[show_disasm_action] = self.show_disassembly
			make_proc_action = popup.addAction("Make &function at this address")
			if self.cursorAscii:
				make_proc_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_P))
			else:
				make_proc_action.setShortcut(QKeySequence(Qt.Key_P))
			action_table[make_proc_action] = self.make_proc

			action = popup.exec_(QCursor.pos())
			if action in action_table:
				action_table[action]()
			return

		if event.button() != Qt.LeftButton:
			return

		# Compute which location was clicked
		x = int((event.x() - 2) / self.charWidth)
		y = int((event.y() - 2) / self.charHeight)
		self.lastMouseX = x
		self.lastMouseY = y
		if y < 0:
			y = 0
		if x < 10:
			x = 0
			ascii = False
		elif x < (11 + (3 * self.cols)):
			if ((x - 10) % 3) == 2:
				x = (((x - 10) / 3) * 2) + 2
			else:
				x = (((x - 10) / 3) * 2) + ((x - 10) % 3)
			if x >= (self.cols * 2):
				if event.modifiers() & Qt.ShiftModifier:
					x = 0
					y += 1
				else:
					x = (self.cols * 2) - 1
			ascii = False
		else:
			x = (x - (11 + (3 * self.cols))) * 2
			if x >= (self.cols * 2):
				if event.modifiers() & Qt.ShiftModifier:
					x = 0
					y += 1
				else:
					x = (self.cols * 2) - 2
			ascii = True

		# Update position
		yofs = self.verticalScrollBar().value()
		if (y + yofs) >= self.rows:
			# Position after end of file
			self.cursorY = self.rows - 1
			rowStart = self.cursorY * self.cols
			self.cursorX = (self.size - rowStart) * 2
		elif (y + yofs) == (self.rows - 1):
			# Last row of file
			self.cursorY = y + yofs
			self.cursorX = x
			rowStart = self.cursorY * self.cols
			if ((rowStart + (self.cursorX / 2)) > self.size) or (((rowStart + (self.cursorX / 2)) == self.size) and
				((self.cursorX % 2) != 0)):
				# End of line is before new cursor position
				self.cursorX = (self.size - rowStart) * 2
		else:
			# Full line
			self.cursorX = x
			self.cursorY = y + yofs
		self.cursorAscii = ascii

		if not (event.modifiers() & Qt.ShiftModifier):
			self.deselect()
		else:
			self.cursorX &= ~1

		self.repositionCaret()
		if event.modifiers() & Qt.ShiftModifier:
			self.viewport().update()

		self.left_button_down = True

	def mouseMoveEvent(self, event):
		if not self.left_button_down:
			return

		x = int((event.x() - 2) / self.charWidth)
		y = int((event.y() - 2) / self.charHeight)
		if (x == self.lastMouseX) and (y == self.lastMouseY):
			# Mouse has not moved to another character
			return
		self.lastMouseX = x
		self.lastMouseY = y

		# Compute new position of mouse
		if y < 0:
			y = 0
		if self.cursorAscii:
			x = (x - (11 + (3 * self.cols))) * 2
			if x < 0:
				x = 0
			if x >= (self.cols * 2):
				x = 0
				y += 1
		else:
			if x < 10:
				x = 10
			if ((x - 10) % 3) == 2:
				x = (((x - 10) / 3) * 2) + 2
			else:
				x = (((x - 10) / 3) * 2) + ((x - 10) % 3)
			if x >= (self.cols * 2):
				x = 0
				y += 1

		# Update position
		yofs = self.verticalScrollBar().value()
		if (y + yofs) >= self.rows:
			# Position after end of file
			self.cursorY = self.rows - 1
			rowStart = self.cursorY * self.cols
			self.cursorX = (self.size - rowStart) * 2
		elif (y + yofs) == (self.rows - 1):
			# Last row of file
			self.cursorY = y + yofs
			self.cursorX = x
			rowStart = self.cursorY * self.cols
			if ((rowStart + (self.cursorX / 2)) > self.size) or (((rowStart + (self.cursorX / 2)) == self.size) and
				((self.cursorX % 2) != 0)):
				# End of line is before new cursor position
				self.cursorX = (self.size - rowStart) * 2
		else:
			# Full line
			self.cursorX = x
			self.cursorY = y + yofs
		self.cursorX &= ~1

		self.repositionCaret()
		self.viewport().update()

	def mouseReleaseEvent(self, event):
		if event.button() != Qt.LeftButton:
			return
		self.left_button_down = False

	def notify_data_write(self, data, ofs, contents):
		self.viewport().update()

	def notify_data_insert(self, data, ofs, contents):
		areaSize = self.viewport().size()
		self.adjustSize(areaSize.width(), areaSize.height())
		self.viewport().update()

	def notify_data_remove(self, data, ofs, size):
		areaSize = self.viewport().size()
		self.adjustSize(areaSize.width(), areaSize.height())

		# If cursor is now positioned after the end of the file, move the cursor
		ofs = self.data.start() + (self.cursorY * self.cols) + int(self.cursorX / 2)
		if ofs == self.data.end():
			self.cursorX &= ~1
			self.repositionCaret()
		elif ofs > self.data.end():
			self.cursorY = self.rows - 1
			rowStart = self.cursorY * self.cols
			self.cursorX = (self.size - rowStart) * 2
			self.deselect()
			self.repositionCaret()

		self.viewport().update()

	def closeRequest(self):
		self.data.remove_callback(self)
		return True

	def navigate(self, addr):
		ofs = addr - self.data.start()
		if ofs < 0:
			return False
		if ofs > len(self.data):
			return False
		self.cursorY = int(ofs / self.cols)
		self.cursorX = (ofs - (self.cursorY * self.cols)) * 2
		self.deselect()
		self.repositionCaret()
		return True

	def get_history_entry(self):
		return HexEditorHistoryEntry(self)

	def navigate_to_history_entry(self, entry):
		ofs = entry.addr - self.data.start()
		if ofs < 0:
			ofs = 0
		if ofs > len(self.data):
			ofs = len(self.data)
		self.cursorY = int(ofs / self.cols)
		self.cursorX = (ofs - (self.cursorY * self.cols)) * 2 + entry.xofs
		self.cursorAscii = entry.ascii
		self.deselect()
		self.repositionCaret()

	def notify_save(self):
		# Repaint as the existing modification colors are no longer valid
		self.viewport().update()

	def transform(self, func):
		data = self.data
		range = self.get_selection_range()
		if (range[1] - range[0]) == 0:
			QMessageBox.critical(self, "Invalid Selection", "No bytes are selected for transformation.", QMessageBox.Ok)
			return
		value = data.read(range[0], range[1] - range[0])

		try:
			value = func(value)
		except:
			QMessageBox.critical(self, "Error", sys.exc_info()[1].args[0])

		if not self.write(value):
			QMessageBox.critical(self, "Error", "Unable to modify contents")

	def transform_with_key(self, func):
		data = self.data
		range = self.get_selection_range()
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

		if not self.write(value):
			QMessageBox.critical(self, "Error", "Unable to modify contents")

	def transform_with_key_and_iv(self, func):
		data = self.data
		range = self.get_selection_range()
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

		if not self.write(value):
			QMessageBox.critical(self, "Error", "Unable to modify contents")

	def fontChanged(self):
		self.initFont()
		areaSize = self.viewport().size()
		self.adjustSize(areaSize.width(), areaSize.height())
		self.repositionCaret()
		self.viewport().update()

	def getPriority(data, ext):
		return 10
	getPriority = staticmethod(getPriority)

	def getViewName():
		return "Hex editor"
	getViewName = staticmethod(getViewName)

	def getShortViewName():
		return "Hex"
	getShortViewName = staticmethod(getShortViewName)

	def handlesNavigationType(name):
		return name == "hex"
	handlesNavigationType = staticmethod(handlesNavigationType)

ViewTypes += [HexEditor]

