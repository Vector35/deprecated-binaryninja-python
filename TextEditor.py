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
from Fonts import *
from View import *
from BinaryData import *
from TextLines import *
from FindDialog import *
import PythonHighlight
import CHighlight


textExtensions = ['.txt', '.py', '.pyw', '.rb', '.c', '.cc', '.cpp', '.cxx', '.h', '.hh', '.hpp', '.m', '.mm', '.mk']

highlighters = {".py": PythonHighlight.PythonHighlight, ".pyw": PythonHighlight.PythonHighlight,
	".c": CHighlight.CHighlight, ".cc": CHighlight.CHighlight, ".cpp": CHighlight.CHighlight,
	".cxx": CHighlight.CHighlight, ".h": CHighlight.CHighlight, ".hh": CHighlight.CHighlight,
	".hpp": CHighlight.CHighlight, ".m": CHighlight.CHighlight, ".mm": CHighlight.CHighlight}


class TextEditorHistoryEntry:
	def __init__(self, view):
		self.addr = view.data.start() + view.text.lines[view.cursorY].offset + view.cursorX
		self.xofs = view.cursorX


class TextEditor(QAbstractScrollArea):
	statusUpdated = Signal(QWidget, name="statusUpdated")

	def __init__(self, data, filename, view, parent):
		super(TextEditor, self).__init__(parent)

		self.data = data
		self.view = view

		highlight = None
		ext = os.path.splitext(filename)[1].lower()
		if ext in highlighters:
			highlight = highlighters[ext](data)

		self.text = TextLines(data, 4, highlight)
		self.text.add_callback(self)

		self.setCursor(Qt.IBeamCursor)
		self.horizontalScrollBar().setCursor(Qt.ArrowCursor)
		self.verticalScrollBar().setCursor(Qt.ArrowCursor)

		self.initFont()
		self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

		# Initialize cursor state
		self.prevCursorY = 0
		self.cursorX = 0
		self.cursorCol = 0
		self.cursorY = 0
		self.selectionStartX = 0
		self.selectionStartY = 0
		self.selectionVisible = False
		self.caretVisible = False
		self.caretBlink = True
		self.left_button_down = False
		self.status = "Cursor: Line %d, Col %d, Offset 0x%.8x" % (1, 1, self.data.start())

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
		self.view.register_navigate("text", self, self.navigate)

		self.search_regex = None
		self.last_search_type = FindDialog.SEARCH_ASCII

	def initFont(self):
		self.font = getMonospaceFont()
		self.font.setKerning(False)
		self.baseline = int(QFontMetricsF(self.font).ascent())

		self.boldFont = QFont(self.font)
		if allowBoldFonts():
			self.boldFont.setBold(True)

		# Compute width and ensure width is an integer (otherwise there will be rendering errors)
		self.charWidth = QFontMetricsF(self.font).width('X')
		if (self.charWidth % 1.0) < 0.5:
			self.font.setLetterSpacing(QFont.AbsoluteSpacing, -(self.charWidth % 1.0))
			self.boldFont.setLetterSpacing(QFont.AbsoluteSpacing, -(self.charWidth % 1.0))
			self.charWidth -= self.charWidth % 1.0
		else:
			self.font.setLetterSpacing(QFont.AbsoluteSpacing, 1.0 - (self.charWidth % 1.0))
			self.boldFont.setLetterSpacing(QFont.AbsoluteSpacing, 1.0 - (self.charWidth % 1.0))
			self.charWidth += 1.0 - (self.charWidth % 1.0)

		self.charHeight = int(QFontMetricsF(self.font).height()) + getExtraFontSpacing()
		self.charOffset = getFontVerticalOffset()

	def set_highlight_type(self, highlight):
		if highlight is None:
			self.text.set_highlight(None)
		else:
			self.text.set_highlight(highlight(self.data))

	def adjustSize(self, width, height):
		# Compute number of rows and columns
		self.rows = len(self.text.lines)
		self.cols = self.text.max_line_width + 1
		self.visibleRows = int((height - 4) / self.charHeight)
		self.visibleCols = int((width - 4) / self.charWidth) - 7

		# Update scroll bar information
		self.verticalScrollBar().setPageStep(self.visibleRows)
		self.verticalScrollBar().setRange(0, self.rows - self.visibleRows)
		self.horizontalScrollBar().setPageStep(self.visibleCols)
		self.horizontalScrollBar().setRange(0, self.cols - self.visibleCols)

	def resizeEvent(self, event):
		# Window was resized, adjust scroll bar
		self.adjustSize(event.size().width(), event.size().height())
		self.repositionCaret()

	def get_cursor_pos_relative(self):
		return self.text.lines[self.cursorY].offset + self.cursorX

	def get_cursor_pos(self):
		return (self.text.lines[self.cursorY].offset + self.cursorX) + self.data.start()

	def set_cursor_pos(self, pos):
		self.navigate(pos)

	def get_selection_range_relative(self):
		# Compute selection range
		selStart = (self.text.lines[self.selectionStartY].offset + self.selectionStartX)
		selEnd = (self.text.lines[self.cursorY].offset + self.cursorX)
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
		self.cursorY = self.text.offset_to_line(ofs)
		self.cursorX = ofs - self.text.lines[self.cursorY].offset
		self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)

		self.viewport().update()

	def is_selection_active(self):
		selStart, selEnd = self.get_selection_range()
		return selStart != selEnd

	def paintEvent(self, event):
		# Initialize painter
		p = QPainter(self.viewport())
		p.setFont(self.font)

		xofs = self.horizontalScrollBar().value()
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
			startY = self.text.offset_to_line(selStart)
			startX = selStart - self.text.lines[startY].offset
			startCol = self.text.lines[startY].offset_to_col(startX)
			endY = self.text.offset_to_line(selEnd)
			endX = selEnd - self.text.lines[endY].offset
			endCol = self.text.lines[endY].offset_to_col(endX)
			startCol -= xofs
			endCol -= xofs
			startY -= yofs
			endY -= yofs

			if startCol < 0:
				startCol = 0
			if endCol < 0:
				endCol = 0

			# Cursor on hex side, draw filled background
			p.setPen(QColor(192, 192, 192))
			p.setBrush(QColor(192, 192, 192))
			if startY == endY:
				p.drawRect(2 + (7 + startCol) * self.charWidth, 1 + startY * self.charHeight,
					(endCol - startCol) * self.charWidth, self.charHeight + 1)
			else:
				p.drawRect(2 + (7 + startCol) * self.charWidth, 1 + startY * self.charHeight,
					(event.rect().x() + event.rect().width()) - startCol * self.charWidth, self.charHeight + 1)
				if endCol > 0:
					p.drawRect(2 + 7 * self.charWidth, 1 + endY * self.charHeight,
						endCol * self.charWidth, self.charHeight + 1)
			if (endY - startY) > 1:
				p.drawRect(2 + 7 * self.charWidth, 1 + (startY + 1) * self.charHeight,
					event.rect().x() + event.rect().width(), ((endY - startY) - 1) * self.charHeight + 1)

			self.selectionVisible = True

		p.setPen(QColor(0, 128, 128))
		p.drawLine(5 + 5 * self.charWidth, event.rect().y(), 5 + 5 * self.charWidth, event.rect().y() + event.rect().height())

		# Paint each line
		for y in range(topY, botY):
			# Skip if line is invalid
			if (y + yofs) < 0:
				continue
			if (y + yofs) >= len(self.text.lines):
				continue
			lineAddr = self.text.lines[y + yofs].offset + self.data.start()
			if lineAddr > self.data.end():
				break

			# Draw line number
			p.setPen(QColor(0, 128, 128))
			p.drawText(2, 2 + y * self.charHeight + self.charOffset + self.baseline, "%5d" % (y + yofs + 1))

			if lineAddr == self.data.end():
				break

			# Get data for the line
			bytes = self.data.read(lineAddr, self.text.lines[y + yofs].length)
			modifications = self.data.get_modification(lineAddr, self.text.lines[y + yofs].length)

			modification = DATA_ORIGINAL
			for char_mod in modifications:
				if (char_mod == DATA_INSERTED) and (modification == DATA_ORIGINAL):
					modification = DATA_INSERTED
				elif char_mod == DATA_CHANGED:
					modification = DATA_CHANGED

			style = HIGHLIGHT_NONE
			p.setPen(Qt.black)
			tokens = self.text.lines[y + yofs].tokens
			cur_token = ""
			col = 0

			# Paint line
			for i in xrange(0, len(bytes)):
				char_style = HIGHLIGHT_NONE
				for token in tokens:
					if (i >= token.start) and (i < (token.start + token.length)):
						char_style = token.state.style
						break

				if char_style != style:
					# Style changed, first render queued text
					if len(cur_token) > 0:
						if col < xofs:
							# This token is scrolled off the screen to the left
							if (xofs - col) >= len(cur_token):
								col += len(cur_token)
								cur_token = ""
							else:
								cur_token = cur_token[xofs - col:]
								col = xofs
						p.drawText(2 + (7 + col - xofs) * self.charWidth, 2 + y *
							self.charHeight + self.charOffset + self.baseline, cur_token)
						col += len(cur_token)
						cur_token = ""

					style = char_style

					# Set up for rendering with the new style
					if style == HIGHLIGHT_COMMENT:
						p.setPen(QColor(0, 0, 255))
						p.setFont(self.font)
					elif style == HIGHLIGHT_KEYWORD:
						p.setPen(QColor(192, 0, 0))
						p.setFont(self.boldFont)
					elif style == HIGHLIGHT_IDENTIFIER:
						p.setPen(QColor(0, 128, 128))
						p.setFont(self.font)
					elif style == HIGHLIGHT_STRING:
						p.setPen(QColor(128, 128, 0))
						p.setFont(self.font)
					elif style == HIGHLIGHT_ESCAPE:
						p.setPen(QColor(255, 0, 0))
						p.setFont(self.font)
					elif style == HIGHLIGHT_VALUE:
						p.setPen(QColor(0, 128, 0))
						p.setFont(self.font)
					elif style == HIGHLIGHT_DIRECTIVE:
						p.setPen(QColor(128, 0, 128))
						p.setFont(self.boldFont)
					else:
						p.setPen(Qt.black)
						p.setFont(self.font)

				if bytes[i] == '\t':
					cur_token += ' ' * (self.text.tab_width - ((col + len(cur_token)) % self.text.tab_width))
				elif bytes[i] == '\x00':
					# Null bytes will terminate the string when attempting to render, replace with a space
					cur_token += ' '
				else:
					cur_token += bytes[i]

			if len(cur_token) != 0:
				if col < xofs:
					# This token is scrolled off the screen to the left
					if (xofs - col) >= len(cur_token):
						col += len(cur_token)
						cur_token = ""
					else:
						cur_token = cur_token[xofs - col:]
						col = xofs
				p.drawText(2 + (7 + col - xofs) * self.charWidth, 2 + y * self.charHeight +
					self.charOffset + self.baseline, cur_token)

			p.setFont(self.font)

		# Draw caret if visible
		if self.caretVisible and not selection:
			if self.caretBlink:
				# Draw inverted caret over selected character
				if self.x11:
					p.setCompositionMode(QPainter.RasterOp_SourceXorDestination)
				else:
					p.setCompositionMode(QPainter.CompositionMode_Difference)
				p.setPen(Qt.NoPen)
				p.setBrush(Qt.white)
				caret_width = 2
				caret_ofs = -1
				p.drawRect(2 + (7 + self.cursorCol - xofs) * self.charWidth + caret_ofs,
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
		xofs = self.horizontalScrollBar().value()
		if self.cursorCol < xofs:
			self.horizontalScrollBar().setValue(self.cursorCol)
		elif self.cursorCol >= (xofs + self.visibleCols):
			self.horizontalScrollBar().setValue(self.cursorCol - (self.visibleCols - 1))

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

		self.status = "Cursor: Line %d, Col %d, Offset 0x%.8x" % (self.cursorY + 1, self.cursorCol + 1,
			self.data.start() + self.text.lines[self.cursorY].offset + self.cursorX)
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

	def deselect(self):
		self.selectionStartX = self.cursorX
		self.selectionStartY = self.cursorY
		if self.selectionVisible:
			self.viewport().update()

	def write_range_to_clipboard(self, selStart, selEnd):
		data = self.data.read(selStart + self.data.start(), selEnd - selStart)
		if len(data) != (selEnd - selStart):
			QMessageBox.critical(self, "Error", "Unable to read entire selected range")
			return False

		clipboard = QApplication.clipboard()
		clipboard.clear()
		mime = QMimeData()
		mime.setText(data)
		clipboard.setMimeData(mime)
		return True

	def selectAll(self):
		self.selectionStartX = 0
		self.selectionStartY = 0
		self.cursorY = self.rows - 1
		self.cursorX = self.text.lines[self.cursorY].length
		self.cursorCol = self.text.lines[self.cursorY].width
		self.viewport().update()

	def selectNone(self):
		self.deselect()
		self.repositionCaret()
		self.viewport().update()

	def cut(self):
		selStart, selEnd = self.get_selection_range_relative()
		if selEnd == selStart:
			return
		if self.write_range_to_clipboard(selStart, selEnd):
			self.view.begin_undo()
			self.data.remove(selStart + self.data.start(), selEnd - selStart)
			self.cursorY = self.text.offset_to_line(selStart)
			self.cursorX = selStart - self.text.lines[self.cursorY].offset
			self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
			self.deselect()
			self.repositionCaret()
			self.view.commit_undo()

	def copy(self):
		# Compute selection range
		selStart, selEnd = self.get_selection_range_relative()
		if selEnd == selStart:
			return
		self.write_range_to_clipboard(selStart, selEnd)

	def copy_address(self):
		selStart, selEnd = self.get_selection_range()
		clipboard = QApplication.clipboard()
		clipboard.clear()
		mime = QMimeData()
		mime.setText("0x%x" % selStart)
		clipboard.setMimeData(mime)

	def format_binary_string(self, data):
		indented_col = self.text.lines[self.cursorY].leading_whitespace_width(self.data, self.text.tab_width)
		indented_tabs = self.text.lines[self.cursorY].leading_tab_width(self.data, self.text.tab_width)
		if indented_tabs == indented_col:
			indented_tabs += self.text.tab_width
		indented_col += self.text.tab_width

		first_width = 78 - self.cursorCol
		rest_width = 79 - indented_col
		if first_width < 20:
			first_width = 20
		if rest_width < 20:
			rest_width = 20

		text = "\""
		cur_width = 1
		max_width = first_width
		first = True
		multiple_lines = False

		for ch in data:
			escaped_char = ch.encode("string_escape").replace("\"", "\\\"")
			if cur_width + len(escaped_char) > max_width:
				if first:
					text = "(" + text
					first = False
				text += "\"\n"
				text += "\t" * int(indented_tabs / self.text.tab_width)
				text += " " * (indented_col - indented_tabs)
				text += "\""
				cur_width = 1
				max_width = rest_width
				multiple_lines = True
			text += escaped_char
			cur_width += len(escaped_char)

		text += "\""
		if multiple_lines:
			text += ")"
		return text

	def paste(self):
		selStart, selEnd = self.get_selection_range_relative()

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

		# Write clipboard contents to the file
		self.view.begin_undo()
		if selEnd != selStart:
			self.data.remove(selStart + self.data.start(), selEnd - selStart)

		if binary:
			data = self.format_binary_string(data)
		written = self.data.insert(selStart + self.data.start(), data)
		if written != len(data):
			QMessageBox.critical(self, "Error", "Unable to paste entire contents")

		self.cursorY = self.text.offset_to_line(selStart + written)
		self.cursorX = (selStart + written) - self.text.lines[self.cursorY].offset
		self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
		self.deselect()
		self.repositionCaret()
		self.view.commit_undo()

	def write(self, data):
		self.view.begin_undo()

		selStart, selEnd = self.get_selection_range_relative()
		if selEnd != selStart:
			self.data.remove(selStart + self.data.start(), selEnd - selStart)

		data = self.format_binary_string(data)
		written = self.data.insert(selStart + self.data.start(), data)

		self.cursorY = self.text.offset_to_line(selStart + written)
		self.cursorX = (selStart + written) - self.text.lines[self.cursorY].offset
		self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
		self.deselect()
		self.repositionCaret()
		self.view.commit_undo()

		return written == len(data)

	def input_text(self, value):
		self.view.begin_undo()

		if self.is_selection_active():
			# Selection active, delete selection
			selStart, selEnd = self.get_selection_range_relative()
			self.data.remove(selStart + self.data.start(), selEnd - selStart)
			self.cursorY = self.text.offset_to_line(selStart)
			self.cursorX = selStart - self.text.lines[self.cursorY].offset
			self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)

		if self.cursorCol > self.text.lines[self.cursorY].offset_to_col(self.cursorX):
			# Cursor is positioned with virtual indentation, make the indentation real
			# before inserting the character.  First determine the number of leading
			# tabs on the previous line
			rightmost_col = self.text.lines[self.cursorY].offset_to_col(self.cursorX)

			leading_tab_width = -1 
			if self.cursorX != 0:
				leading_tab_width = 0
			elif self.cursorY > 0:
				leading_tab_width = self.text.lines[self.cursorY - 1].leading_tab_width(self.data, self.text.tab_width)
				if leading_tab_width == self.text.lines[self.cursorY - 1].width:
					leading_tab_width = -1

			if (leading_tab_width > (self.cursorCol - rightmost_col)) or (leading_tab_width == -1):
				tabs = int((self.cursorCol - rightmost_col) / self.text.tab_width)
			else:
				tabs = int(leading_tab_width / self.text.tab_width)

			indent = '\t' * tabs
			indent += ' ' * ((self.cursorCol - rightmost_col) - (tabs * self.text.tab_width))

			ofs = self.data.start() + self.text.lines[self.cursorY].offset + self.cursorX
			self.data.insert(ofs, indent)
			self.cursorX += len(indent)
			self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)

		ofs = self.data.start() + self.text.lines[self.cursorY].offset + self.cursorX
		self.data.insert(ofs, value)

		self.cursorX += len(value)
		self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
		self.deselect()

		self.view.commit_undo()

	def input_newline(self):
		self.view.begin_undo()

		if self.is_selection_active():
			# Selection active, delete selection
			selStart, selEnd = self.get_selection_range_relative()
			self.data.remove(selStart + self.data.start(), selEnd - selStart)
			self.cursorY = self.text.offset_to_line(selStart)
			self.cursorX = selStart - self.text.lines[self.cursorY].offset
			self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)

		ofs = self.data.start() + self.text.lines[self.cursorY].offset + self.cursorX
		self.data.insert(ofs, self.text.default_newline)

		self.cursorY += 1
		self.cursorX = 0

		# If not splitting a line, place cursor at same column as the end of the leading
		# whitespace from the previous line, or if inputting a blank line, use existing column
		if self.text.lines[self.cursorY].length != 0:
			self.cursorCol = 0
		elif self.text.lines[self.cursorY - 1].length != 0:
			self.cursorCol = self.text.lines[self.cursorY - 1].leading_whitespace_width(self.data, self.text.tab_width)

		self.deselect()

		self.view.commit_undo()

	def indent_selection(self):
		selStart, selEnd = self.get_selection_range_relative()
		startY = self.text.offset_to_line(selStart)
		endY = self.text.offset_to_line(selEnd)
		if self.text.lines[endY].offset == selEnd:
			# Ended on newline, fix up ending row
			endY -= 1

		self.view.begin_undo()
		for i in xrange(startY, endY + 1):
			self.data.insert(self.text.lines[i].offset, '\t')
		self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
		self.view.commit_undo()

	def unindent_selection(self):
		selStart, selEnd = self.get_selection_range_relative()
		startY = self.text.offset_to_line(selStart)
		endY = self.text.offset_to_line(selEnd)
		if self.text.lines[endY].offset == selEnd:
			# Ended on newline, fix up ending row
			endY -= 1

		self.view.begin_undo()

		for i in xrange(startY, endY + 1):
			ch = self.data.read(self.text.lines[i].offset, 1)
			if ch == '\t':
				self.data.remove(self.text.lines[i].offset, 1)
			elif ch == ' ':
				ch = self.data.read(self.text.lines[i].offset, self.text.tab_width)
				width = 1
				while width < len(ch):
					if ch[width] != ' ':
						break
					width += 1
				self.data.remove(self.text.lines[i].offset, width)

		if self.selectionStartX > self.text.lines[self.selectionStartY].length:
			self.selectionStartX = self.text.lines[self.selectionStartY].length
		if self.cursorX > self.text.lines[self.cursorY].length:
			self.cursorX = self.text.lines[self.cursorY].length
		self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)

		self.view.commit_undo()

	def keyPressEvent(self, event):
		if event.key() == Qt.Key_Left:
			count = 1
			if event.modifiers() & self.ctrl:
				# If control is held, move a word at a time
				ofs = self.text.lines[self.cursorY].offset + self.cursorX
				nonwhitespace = False
				while ofs > 0:
					ch = self.data.read(ofs - 1, 1)
					if (ch != ' ') and (ch != '\t') and (ch != '\r') and (ch != '\n'):
						if not (ch.isalnum() or (ch == '_')):
							if not nonwhitespace:
								# Just whitespace before symbol, place cursor on symbol
								ofs -= 1
							break
						nonwhitespace = True
					elif nonwhitespace:
						break
					ofs -= 1
				self.cursorY = self.text.offset_to_line(ofs)
				self.cursorX = ofs - self.text.lines[self.cursorY].offset
				self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
			else:
				for i in range(0, count):
					if self.cursorX > 0:
						# Movement within a line
						self.cursorX -= 1
						self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
					elif self.cursorY > 0:
						# Move to previous line
						self.cursorY -= 1
						self.cursorX = self.text.lines[self.cursorY].length
						self.cursorCol = self.text.lines[self.cursorY].width

			if not (event.modifiers() & Qt.ShiftModifier):
				self.deselect()
		elif event.key() == Qt.Key_Right:
			count = 1
			if event.modifiers() & self.ctrl:
				# If control is held, move a word at a time
				ofs = self.text.lines[self.cursorY].offset + self.cursorX
				start_ofs = ofs
				whitespace = False
				while ofs < len(self.data):
					ch = self.data.read(ofs, 1)
					if (ch == ' ') or (ch == '\t') or (ch == '\r') or (ch == '\n'):
						whitespace = True
					elif whitespace:
						break
					elif not (ch.isalnum() or (ch == '_')):
						if ofs == start_ofs:
							# Cursor started on symbol, break on next non-whitespace character
							whitespace = True
						else:
							break
					ofs += 1
				self.cursorY = self.text.offset_to_line(ofs)
				self.cursorX = ofs - self.text.lines[self.cursorY].offset
				self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
			else:
				for i in range(0, count):
					# Ensure cursor is not at end of file
					if (self.cursorY < (len(self.text.lines) - 1)) or (self.cursorX < self.text.lines[self.cursorY].length):
						if self.cursorX < self.text.lines[self.cursorY].length:
							# Movement within a line
							self.cursorX += 1
							self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
						else:
							# Move to next line
							self.cursorX = 0
							self.cursorCol = 0
							self.cursorY += 1

			if not (event.modifiers() & Qt.ShiftModifier):
				self.deselect()
		elif event.key() == Qt.Key_Up:
			if self.cursorY > 0:
				# Not at start of file
				orig_col = self.cursorCol
				self.cursorY -= 1
				self.cursorX = self.text.lines[self.cursorY].col_to_offset(self.cursorCol)
				self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
				if (self.cursorX == 0) and (self.text.lines[self.cursorY].length == 0) and (self.cursorCol < orig_col):
					whitespace = 0
					if (self.cursorY > 0):
						whitespace = self.text.lines[self.cursorY - 1].leading_whitespace_width(self.data, self.text.tab_width)
					if orig_col > whitespace:
						orig_col = whitespace
					self.cursorCol = orig_col
			else:
				# Position at start of file
				self.cursorX = 0
				self.cursorCol = 0

			if not (event.modifiers() & Qt.ShiftModifier):
				self.deselect()
		elif event.key() == Qt.Key_Down:
			if self.cursorY < (self.rows - 1):
				# Not at end of file
				orig_col = self.cursorCol
				self.cursorY += 1
				self.cursorX = self.text.lines[self.cursorY].col_to_offset(self.cursorCol)
				self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
				if (self.cursorX == 0) and (self.text.lines[self.cursorY].length == 0) and (self.cursorCol < orig_col):
					whitespace = 0
					if (self.cursorY > 0):
						whitespace = self.text.lines[self.cursorY - 1].leading_whitespace_width(self.data, self.text.tab_width)
					if orig_col > whitespace:
						orig_col = whitespace
					self.cursorCol = orig_col
			else:
				# Position at end of file
				self.cursorX = self.text.lines[self.cursorY].length
				self.cursorCol = self.text.lines[self.cursorY].width

			if not (event.modifiers() & Qt.ShiftModifier):
				self.deselect()
		elif event.key() == Qt.Key_PageUp:
			if self.cursorY >= self.visibleRows:
				# Not at start of file, move up a page
				self.cursorY -= self.visibleRows
				self.cursorX = self.text.lines[self.cursorY].col_to_offset(self.cursorCol)
				self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
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
				self.cursorCol = 0

			if not (event.modifiers() & Qt.ShiftModifier):
				self.deselect()
		elif event.key() == Qt.Key_PageDown:
			if self.cursorY < (self.rows - self.visibleRows - 1):
				# Not at end of file, move down a page
				self.cursorY += self.visibleRows
				self.cursorX = self.text.lines[self.cursorY].col_to_offset(self.cursorCol)
				self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
				yofs = self.verticalScrollBar().value()
				yofs += self.visibleRows
				if yofs > (self.rows - self.visibleRows):
					# Ensure view start is within bounds
					yofs = self.rows - self.visibleRows
				self.verticalScrollBar().setValue(yofs)
			elif self.cursorY == (self.rows - self.visibleRows - 1):
				# Cursor will be on last line
				self.cursorY += self.visibleRows
				self.cursorX = self.text.lines[self.cursorY].col_to_offset(self.cursorCol)
				self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
			else:
				# Position at end of file
				self.cursorY = self.rows - 1
				self.cursorX = self.text.lines[self.cursorY].length
				self.cursorCol = self.text.lines[self.cursorY].width

			if not (event.modifiers() & Qt.ShiftModifier):
				self.deselect()
		elif event.key() == Qt.Key_Home:
			if event.modifiers() & self.ctrl:
				# Ctrl+Home positions cursor to start of file
				self.cursorY = 0

			# Position cursor at first non-whitespace character, or at beginning of line if already there
			first_non_whitespace = self.text.lines[self.cursorY].leading_whitespace_width(self.data, self.text.tab_width)
			if (self.cursorCol != 0) and (self.cursorCol <= first_non_whitespace):
				self.cursorX = 0
				self.cursorCol = 0
			else:
				self.cursorCol = first_non_whitespace
				self.cursorX = self.text.lines[self.cursorY].col_to_offset(self.cursorCol)

			if not (event.modifiers() & Qt.ShiftModifier):
				self.deselect()
		elif event.key() == Qt.Key_End:
			if event.modifiers() & self.ctrl:
				# Ctrl+End positions cursor to end of file
				self.cursorY = self.rows - 1
			self.cursorX = self.text.lines[self.cursorY].length
			self.cursorCol = self.text.lines[self.cursorY].width

			if not (event.modifiers() & Qt.ShiftModifier):
				self.deselect()
		elif event.key() == Qt.Key_Backspace:
			self.view.begin_undo()
			if self.is_selection_active():
				# Selection active, delete selection
				selStart, selEnd = self.get_selection_range_relative()
				self.data.remove(selStart + self.data.start(), selEnd - selStart)
				self.cursorY = self.text.offset_to_line(selStart)
				self.cursorX = selStart - self.text.lines[self.cursorY].offset
				self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
			elif self.cursorCol != self.text.lines[self.cursorY].offset_to_col(self.cursorX):
				# Virtual whitespace active, unindent instead
				rightmost_col = self.text.lines[self.cursorY].offset_to_col(self.cursorX)

				leading_tab_width = -1 
				if self.cursorX != 0:
					leading_tab_width = 0
				elif self.cursorY > 0:
					leading_tab_width = self.text.lines[self.cursorY - 1].leading_tab_width(self.data, self.text.tab_width)
					if leading_tab_width == self.text.lines[self.cursorY - 1].width:
						leading_tab_width = -1

				if (leading_tab_width > (self.cursorCol - rightmost_col)) or (leading_tab_width == -1):
					tabs = int((self.cursorCol - rightmost_col) / self.text.tab_width)
				else:
					tabs = int(leading_tab_width / self.text.tab_width)

				if self.cursorCol > (tabs * self.text.tab_width):
					self.cursorCol -= 1
				else:
					self.cursorCol -= self.text.tab_width
			else:
				# No selection, save offset and move cursor to the left
				ofs = self.data.start() + self.text.lines[self.cursorY].offset + self.cursorX
				oldCursorX = self.cursorX
				if self.cursorX > 0:
					self.cursorX -= 1
					self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
				elif self.cursorY > 0:
					self.cursorY -= 1
					self.cursorX = self.text.lines[self.cursorY].length
					self.cursorCol = self.text.lines[self.cursorY].width
				if ofs > 0:
					self.data.remove(ofs - 1, 1)
			self.deselect()
			self.view.commit_undo()
		elif event.key() == Qt.Key_Delete:
			self.view.begin_undo()
			if self.is_selection_active():
				# Selection active, delete selection
				selStart, selEnd = self.get_selection_range_relative()
				self.data.remove(selStart + self.data.start(), selEnd - selStart)
				self.cursorY = self.text.offset_to_line(selStart)
				self.cursorX = selStart - self.text.lines[self.cursorY].offset
				self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
			else:
				# No selection, delete current byte
				ofs = self.data.start() + self.text.lines[self.cursorY].offset + self.cursorX
				self.data.remove(ofs, 1)
			self.deselect()
			self.view.commit_undo()
		elif event.key() == Qt.Key_Tab:
			if self.is_selection_active():
				self.indent_selection()
			else:
				self.input_text('\t')
		elif event.key() == Qt.Key_Backtab:
			if self.is_selection_active():
				self.unindent_selection()
			else:
				self.input_text('\t')
#		elif (event.key() == Qt.Key_G) and ((event.modifiers() & self.ctrl) or (event.modifiers() & self.command)):
#			self.go_to_line(event.modifiers() & Qt.ShiftModifier)
#		elif (event.key() == Qt.Key_N) and ((event.modifiers() & self.ctrl) or (event.modifiers() & self.command)):
#			self.find_next()
#		elif (event.key() == Qt.Key_Slash) and ((event.modifiers() & self.ctrl) or (event.modifiers() & self.command)):
#			dlg = FindDialog(FindDialog.SEARCH_REGEX, self)
#			if dlg.exec_() == QDialog.Accepted:
#				self.perform_find(dlg)
		elif (event.key() == Qt.Key_Enter) or (event.key() == Qt.Key_Return):
			self.input_newline()
		elif (event.key() == Qt.Key_Z) and (event.modifiers() & Qt.ControlModifier) and (event.modifiers() & Qt.ShiftModifier):
			self.view.redo()
		elif (event.key() == Qt.Key_Z) and (event.modifiers() & Qt.ControlModifier):
			self.view.undo()
		elif (event.key() == Qt.Key_X) and (event.modifiers() & Qt.ControlModifier):
			self.cut()
		elif (event.key() == Qt.Key_C) and (event.modifiers() & Qt.ControlModifier):
			self.copy()
		elif (event.key() == Qt.Key_V) and (event.modifiers() & Qt.ControlModifier):
			self.paste()
		elif (event.key() == Qt.Key_A) and (event.modifiers() & Qt.ControlModifier):
			self.selectAll()
		elif (len(event.text()) == 1) and ((event.text() >= ' ') and (event.text() <= '~')) or (event.text() == '\t'):
			self.input_text(bytes(event.text()))

		self.repositionCaret()
		if self.selectionVisible or event.modifiers() & Qt.ShiftModifier:
			self.viewport().update()

	def keyReleaseEvent(self, event):
		# Pass unhandled key to parent
		super(TextEditor, self).keyReleaseEvent(event)

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

			action = popup.exec_(QCursor.pos())
			if action in action_table:
				action_table[action]()
			return

		if event.button() != Qt.LeftButton:
			return

		# Compute which location was clicked
		x = int((event.x() + (self.charWidth / 2) - 2) / self.charWidth)
		y = int((event.y() - 2) / self.charHeight)
		self.lastMouseX = x
		self.lastMouseY = y
		if y < 0:
			y = 0
		if x < 7:
			x = 0
		else:
			x -= 7

		xofs = self.horizontalScrollBar().value()
		yofs = self.verticalScrollBar().value()
		x += xofs
		y += yofs

		if (y < len(self.text.lines)) and (x > self.text.lines[y].width):
			if event.modifiers() & Qt.ShiftModifier:
				x = 0
				y += 1
			else:
				x = self.text.lines[y].width

		# Update position
		if y >= self.rows:
			# Position after end of file
			self.cursorY = self.rows - 1
			self.cursorX = self.text.lines[self.cursorY].length
			self.cursorCol = self.text.lines[self.cursorY].width
		else:
			self.cursorY = y
			self.cursorX = self.text.lines[self.cursorY].col_to_offset(x)
			self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)

		if not (event.modifiers() & Qt.ShiftModifier):
			self.deselect()

		self.repositionCaret()
		if event.modifiers() & Qt.ShiftModifier:
			self.viewport().update()

		self.left_button_down = True

	def mouseMoveEvent(self, event):
		if not self.left_button_down:
			return

		x = int((event.x() + (self.charWidth / 2) - 2) / self.charWidth)
		y = int((event.y() - 2) / self.charHeight)
		if (x == self.lastMouseX) and (y == self.lastMouseY):
			# Mouse has not moved to another character
			return
		self.lastMouseX = x
		self.lastMouseY = y

		# Compute new position of mouse
		if y < 0:
			y = 0
		if x < 7:
			x = 0
		else:
			x -= 7

		xofs = self.horizontalScrollBar().value()
		yofs = self.verticalScrollBar().value()
		x += xofs
		y += yofs

		if (y < len(self.text.lines)) and (x > self.text.lines[y].width):
			x = 0
			y += 1

		# Update position
		if y >= self.rows:
			# Position after end of file
			self.cursorY = self.rows - 1
			self.cursorX = self.text.lines[self.cursorY].length
			self.cursorCol = self.text.lines[self.cursorY].width
		else:
			self.cursorY = y
			self.cursorX = self.text.lines[self.cursorY].col_to_offset(x)
			self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)

		self.repositionCaret()
		self.viewport().update()

	def mouseReleaseEvent(self, event):
		if event.button() != Qt.LeftButton:
			return
		self.left_button_down = False

	def event(self, event):
		# Intercept tab events
		if (event.type() == QEvent.KeyPress) and (event.key() == Qt.Key_Tab):
			self.keyPressEvent(event)
			return True
		elif (event.type() == QEvent.KeyPress) and (event.key() == Qt.Key_Backtab):
			self.keyPressEvent(event)
			return True
		return super(TextEditor, self).event(event)

	def closeRequest(self):
		self.text.remove_callback(self)
		self.text.close()
		return True

	def navigate(self, addr):
		ofs = addr - self.data.start()
		if ofs < 0:
			return False
		if ofs > len(self.data):
			return False
		self.cursorY = self.text.offset_to_line(ofs)
		self.cursorX = ofs - self.text.lines[self.cursorY].offset
		self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
		self.deselect()
		self.repositionCaret()
		return True

	def get_history_entry(self):
		return TextEditorHistoryEntry(self)

	def navigate_to_history_entry(self, entry):
		ofs = entry.addr - self.data.start()
		if ofs < 0:
			ofs = 0
		if ofs > len(self.data):
			ofs = len(self.data)
		self.cursorY = self.text.offset_to_line(ofs)
		self.cursorX = ofs - self.text.lines[self.cursorY].offset
		self.cursorCol = self.text.lines[self.cursorY].offset_to_col(self.cursorX)
		self.deselect()
		self.repositionCaret()

	def notify_save(self):
		# Repaint as the existing modification colors are no longer valid
		self.viewport().update()

	def notify_insert_lines(self, text, line, count):
		areaSize = self.viewport().size()
		self.adjustSize(areaSize.width(), areaSize.height())

	def notify_remove_lines(self, text, line, count):
		areaSize = self.viewport().size()
		self.adjustSize(areaSize.width(), areaSize.height())

	def notify_update_lines(self, text, line, count):
		self.viewport().update()

	def notify_max_width_changed(self, text, width):
		areaSize = self.viewport().size()
		self.adjustSize(areaSize.width(), areaSize.height())

	def fontChanged(self):
		self.initFont()
		areaSize = self.viewport().size()
		self.adjustSize(areaSize.width(), areaSize.height())
		self.repositionCaret()
		self.viewport().update()

	def getPriority(data, filename):
		ext = os.path.splitext(filename)[1].lower()
		if data.read(0, 2) == '#!':
			# Shell script
			return 25
		elif os.path.basename(filename) == 'Makefile':
			return 25
		elif ext in textExtensions:
			return 25
		return 0
	getPriority = staticmethod(getPriority)

	def getViewName():
		return "Text editor"
	getViewName = staticmethod(getViewName)

	def getShortViewName():
		return "Text"
	getShortViewName = staticmethod(getShortViewName)

ViewTypes += [TextEditor]

