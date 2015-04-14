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

import threading
from Analysis import *
from Fonts import *
from View import *
from FindDialog import *
from ArchitectureDialog import *


class DisassemblerBlock:
	def __init__(self, block):
		self.block = block
		self.edges = []
		self.incoming = []
		self.new_exits = []

class DisassemblerEdge:
	def __init__(self, color, dest):
		self.color = color
		self.dest = dest
		self.points = []
		self.start_index = 0

	def addPoint(self, row, col, index = 0):
		self.points += [[row, col, 0]]
		if len(self.points) > 1:
			self.points[len(self.points) - 2][2] = index

class DisassemblerHistoryEntry:
	def __init__(self, view):
		self.function = view.function
		self.scroll_x = view.horizontalScrollBar().value()
		self.scroll_y = view.verticalScrollBar().value()
		self.cur_instr = view.cur_instr
		self.highlight_token = view.highlight_token

class DisassemblerView(QAbstractScrollArea):
	statusUpdated = Signal(QWidget, name="statusUpdated")

	def __init__(self, data, filename, view, parent):
		super(DisassemblerView, self).__init__(parent)

		self.status = ""
		self.view = view

		self.data = data
		for type in ExeFormats:
			exe = type(data)
			if exe.valid:
				self.data = exe
				self.view.exe = exe
				break

		# Create analysis and start it in another thread
		self.analysis = Analysis(self.data)
		self.analysis_thread = threading.Thread(None, self.analysis_thread_proc)
		self.analysis_thread.daemon = True
		self.analysis_thread.start()

		# Start disassembly view at the entry point of the binary
		if hasattr(self.data, "entry"):
			self.function = self.data.entry()
		else:
			self.function = None
		self.update_id = None
		self.ready = False
		self.desired_pos = None
		self.highlight_token = None
		self.cur_instr = None
		self.scroll_mode = False
		self.blocks = {}
		self.show_il = False
		self.simulation = None

		# Create timer to automatically refresh view when it needs to be updated
		self.updateTimer = QTimer()
		self.updateTimer.setInterval(100)
		self.updateTimer.setSingleShot(False)
		self.updateTimer.timeout.connect(self.updateTimerEvent)
		self.updateTimer.start()

		self.initFont()

		# Initialize scroll bars
		self.width = 0
		self.height = 0
		self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
		self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
		self.horizontalScrollBar().setSingleStep(self.charWidth)
		self.verticalScrollBar().setSingleStep(self.charHeight)
		areaSize = self.viewport().size()
		self.adjustSize(areaSize.width(), areaSize.height())

		# Setup navigation
		self.view.register_navigate("disassembler", self, self.navigate)
		self.view.register_navigate("make_proc", self, self.make_proc)

		self.search_regex = None
		self.last_search_type = FindDialog.SEARCH_HEX

	def initFont(self):
		# Get font and compute character sizes
		self.font = getMonospaceFont()
		self.baseline = int(QFontMetricsF(self.font).ascent())
		self.charWidth = QFontMetricsF(self.font).width('X')
		self.charHeight = int(QFontMetricsF(self.font).height()) + getExtraFontSpacing()
		self.charOffset = getFontVerticalOffset()

	def adjustSize(self, width, height):
		# Recompute size information
		self.renderWidth = self.width
		self.renderHeight = self.height
		self.renderXOfs = 0
		self.renderYOfs = 0
		if self.renderWidth < width:
			self.renderXOfs = int((width - self.renderWidth) / 2)
			self.renderWidth = width
		if self.renderHeight < height:
			self.renderYOfs = int((height - self.renderHeight) / 2)
			self.renderHeight = height

		# Update scroll bar information
		self.horizontalScrollBar().setPageStep(width)
		self.horizontalScrollBar().setRange(0, self.renderWidth - width)
		self.verticalScrollBar().setPageStep(height)
		self.verticalScrollBar().setRange(0, self.renderHeight - height)

	def resizeEvent(self, event):
		# Window was resized, adjust scroll bar
		self.adjustSize(event.size().width(), event.size().height())

	def get_cursor_pos(self):
		if self.cur_instr is None:
			return self.function
		return self.cur_instr

	def set_cursor_pos(self, addr):
		if not self.view.navigate("disassembler", addr):
			self.view_in_hex_editor(addr)

	def get_selection_range(self):
		return (self.get_cursor_pos(), self.get_cursor_pos())

	def set_selection_range(self, begin, end):
		self.set_cursor_pos(begin)

	def write(self, data):
		pos = self.get_cursor_pos()
		if pos is None:
			return False
		return self.data.write(pos, data) == len(data)

	def copy_address(self):
		clipboard = QApplication.clipboard()
		clipboard.clear()
		mime = QMimeData()
		mime.setText("0x%x" % self.get_cursor_pos())
		clipboard.setMimeData(mime)

	def analysis_thread_proc(self):
		self.analysis.analyze()

	def closeRequest(self):
		# Stop analysis when closing tab
		self.analysis.stop()
		return True

	def paintEvent(self, event):
		# Initialize painter
		p = QPainter(self.viewport())
		p.setFont(self.font)

		xofs = self.horizontalScrollBar().value()
		yofs = self.verticalScrollBar().value()

		if not self.ready:
			# Analysis for the current function is not yet complete, paint loading screen
			gradient = QLinearGradient(QPointF(0, 0), QPointF(self.viewport().size().width(), self.viewport().size().height()))
			gradient.setColorAt(0, QColor(232, 232, 232))
			gradient.setColorAt(1, QColor(192, 192, 192))
			p.setPen(QColor(0, 0, 0, 0))
			p.setBrush(QBrush(gradient))
			p.drawRect(0, 0, self.viewport().size().width(), self.viewport().size().height())

			if self.function is None:
				text = "No function selected"
			else:
				text = "Loading..."
			p.setPen(Qt.black)
			p.drawText((self.viewport().size().width() / 2) - ((len(text) * self.charWidth) / 2),
				(self.viewport().size().height() / 2) + self.charOffset + self.baseline - (self.charHeight / 2), text)
			return

		# Render background
		gradient = QLinearGradient(QPointF(-xofs, -yofs), QPointF(self.renderWidth - xofs, self.renderHeight - yofs))
		gradient.setColorAt(0, QColor(232, 232, 232))
		gradient.setColorAt(1, QColor(192, 192, 192))
		p.setPen(QColor(0, 0, 0, 0))
		p.setBrush(QBrush(gradient))
		p.drawRect(0, 0, self.viewport().size().width(), self.viewport().size().height())

		p.translate(self.renderXOfs - xofs, self.renderYOfs - yofs)

		# Render each node
		for block in self.blocks.values():
			# Render shadow
			p.setPen(QColor(0, 0, 0, 0))
			p.setBrush(QColor(0, 0, 0, 128))
			p.drawRect(block.x + self.charWidth + 4, block.y + self.charWidth + 4,
				block.width - (4 + 2 * self.charWidth), block.height - (4 + 2 * self.charWidth))

			# Render node background
			gradient = QLinearGradient(QPointF(0, block.y + self.charWidth),
				QPointF(0, block.y + block.height - self.charWidth))
			gradient.setColorAt(0, QColor(255, 255, 252))
			gradient.setColorAt(1, QColor(255, 255, 232))
			p.setPen(Qt.black)
			p.setBrush(QBrush(gradient))
			p.drawRect(block.x + self.charWidth, block.y + self.charWidth,
				block.width - (4 + 2 * self.charWidth), block.height - (4 + 2 * self.charWidth))

			if self.cur_instr != None:
				y = block.y + (2 * self.charWidth) + (len(block.block.header_text.lines) * self.charHeight)
				for instr in block.block.instrs:
					if instr.addr == self.cur_instr:
						p.setPen(QColor(0, 0, 0, 0))
						p.setBrush(QColor(255, 255, 128, 128))
						p.drawRect(block.x + self.charWidth + 3, y, block.width - (10 + 2 * self.charWidth),
							len(instr.text.lines) * self.charHeight)
					y += len(instr.text.lines) * self.charHeight

			if self.highlight_token:
				# Render highlighted tokens
				x = block.x + (2 * self.charWidth)
				y = block.y + (2 * self.charWidth)
				for line in block.block.header_text.tokens:
					for token in line:
						if token[2:] == self.highlight_token:
							p.setPen(QColor(0, 0, 0, 0))
							p.setBrush(QColor(192, 0, 0, 64))
							p.drawRect(x + token[0] * self.charWidth, y,
								token[1] * self.charWidth, self.charHeight)
					y += self.charHeight
				for instr in block.block.instrs:
					for line in instr.text.tokens:
						for token in line:
							if token[2:] == self.highlight_token:
								p.setPen(QColor(0, 0, 0, 0))
								p.setBrush(QColor(192, 0, 0, 64))
								p.drawRect(x + token[0] * self.charWidth, y,
									token[1] * self.charWidth, self.charHeight)
						y += self.charHeight

			# Render node text
			x = block.x + (2 * self.charWidth)
			y = block.y + (2 * self.charWidth)
			for line in block.block.header_text.lines:
				partx = x
				for part in line:
					p.setPen(part[1])
					p.drawText(partx, y + self.charOffset + self.baseline, part[0])
					partx += len(part[0]) * self.charWidth
				y += self.charHeight
			for instr in block.block.instrs:
				for line in instr.text.lines:
					partx = x
					for part in line:
						p.setPen(part[1])
						p.drawText(partx, y + self.charOffset + self.baseline, part[0])
						partx += len(part[0]) * self.charWidth
					y += self.charHeight

			# Render edges
			for edge in block.edges:
				p.setPen(edge.color)
				p.setBrush(edge.color)
				p.drawPolyline(edge.polyline)
				p.drawConvexPolygon(edge.arrow)

	def isMouseEventInBlock(self, event):
		# Convert coordinates to system used in blocks
		xofs = self.horizontalScrollBar().value()
		yofs = self.verticalScrollBar().value()
		x = event.x() + xofs - self.renderXOfs
		y = event.y() + yofs - self.renderYOfs

		# Check each block for hits
		for block in self.blocks.values():
			# Compute coordinate relative to text area in block
			blockx = x - (block.x + (2 * self.charWidth))
			blocky = y - (block.y + (2 * self.charWidth))
			# Check to see if click is within bounds of block
			if (blockx < 0) or (blockx > (block.width - 4 * self.charWidth)):
				continue
			if (blocky < 0) or (blocky > (block.height - 4 * self.charWidth)):
				continue
			return True

		return False

	def getInstrForMouseEvent(self, event):
		# Convert coordinates to system used in blocks
		xofs = self.horizontalScrollBar().value()
		yofs = self.verticalScrollBar().value()
		x = event.x() + xofs - self.renderXOfs
		y = event.y() + yofs - self.renderYOfs

		# Check each block for hits
		for block in self.blocks.values():
			# Compute coordinate relative to text area in block
			blockx = x - (block.x + (2 * self.charWidth))
			blocky = y - (block.y + (2 * self.charWidth))
			# Check to see if click is within bounds of block
			if (blockx < 0) or (blockx > (block.width - 4 * self.charWidth)):
				continue
			if (blocky < 0) or (blocky > (block.height - 4 * self.charWidth)):
				continue
			# Compute row within text
			row = int(blocky / self.charHeight)
			# Determine instruction for this row
			cur_row = len(block.block.header_text.lines)
			if row < cur_row:
				return block.block.entry
			for instr in block.block.instrs:
				if row < cur_row + len(instr.text.lines):
					return instr.addr
				cur_row += len(instr.text.lines)

		return None

	def getTokenForMouseEvent(self, event):
		# Convert coordinates to system used in blocks
		xofs = self.horizontalScrollBar().value()
		yofs = self.verticalScrollBar().value()
		x = event.x() + xofs - self.renderXOfs
		y = event.y() + yofs - self.renderYOfs

		# Check each block for hits
		for block in self.blocks.values():
			# Compute coordinate relative to text area in block
			blockx = x - (block.x + (2 * self.charWidth))
			blocky = y - (block.y + (2 * self.charWidth))
			# Check to see if click is within bounds of block
			if (blockx < 0) or (blockx > (block.width - 4 * self.charWidth)):
				continue
			if (blocky < 0) or (blocky > (block.height - 4 * self.charWidth)):
				continue
			# Compute row and column within text
			col = int(blockx / self.charWidth)
			row = int(blocky / self.charHeight)
			# Check tokens to see if one was clicked
			cur_row = 0
			for line in block.block.header_text.tokens:
				if cur_row == row:
					for token in line:
						if (col >= token[0]) and (col < (token[0] + token[1])):
							# Clicked on a token
							return token
				cur_row += 1
			for instr in block.block.instrs:
				for line in instr.text.tokens:
					if cur_row == row:
						for token in line:
							if (col >= token[0]) and (col < (token[0] + token[1])):
								# Clicked on a token
								return token
					cur_row += 1

		return None

	def find_instr(self, addr):
		for block in self.blocks.values():
			for instr in block.block.instrs:
				if instr.addr == addr:
					return instr
		return None

	def nop_out(self, addr):
		instr = self.find_instr(addr)
		if instr != None:
			self.view.begin_undo()
			instr.patch_to_nop(self.data)
			self.view.commit_undo()

	def always_branch(self, addr):
		instr = self.find_instr(addr)
		if instr != None:
			self.view.begin_undo()
			instr.patch_to_always_branch(self.data)
			self.view.commit_undo()

	def invert_branch(self, addr):
		instr = self.find_instr(addr)
		if instr != None:
			self.view.begin_undo()
			instr.patch_to_invert_branch(self.data)
			self.view.commit_undo()

	def skip_and_return_zero(self, addr):
		instr = self.find_instr(addr)
		if instr != None:
			self.view.begin_undo()
			instr.patch_to_zero_return(self.data)
			self.view.commit_undo()

	def skip_and_return_value(self, addr):
		instr = self.find_instr(addr)
		if instr != None:
			value, ok = QInputDialog.getText(self, "Skip and Return Value", "Return value:", QLineEdit.Normal)
			if ok:
				try:
					value = int(value, 0)
				except:
					QMessageBox.critical(self, "Error", "Expected numerical address")
					return
	
			self.view.begin_undo()
			instr.patch_to_fixed_return_value(self.data, value)
			self.view.commit_undo()

	def view_in_hex_editor(self, addr):
		if not self.view.navigate("exe", addr):
			self.view.navigate("hex", addr)

	def show_address(self):
		if "address" in self.analysis.options:
			addr = False
		else:
			addr = True
		self.analysis.set_address_view(addr)

	def context_menu(self, addr):
		popup = QMenu()
		view_in_hex = popup.addAction("View in &hex editor")
		view_in_hex.triggered.connect(lambda : self.view_in_hex_editor(addr))
		view_in_hex.setShortcut(QKeySequence(Qt.Key_H))
		popup.addAction("Copy address", self.copy_address)
		enter_name_action = popup.addAction("Re&name symbol", self.enter_name)
		enter_name_action.setShortcut(QKeySequence(Qt.Key_N))
		undefine_name_action = popup.addAction("&Undefine symbol", self.undefine_name)
		undefine_name_action.setShortcut(QKeySequence(Qt.Key_U))
		show_address_action = popup.addAction("Show &address", self.show_address)
		show_address_action.setCheckable(True)
		show_address_action.setChecked("address" in self.analysis.options)
		popup.addSeparator()

		patch = popup.addMenu("&Patch")
		patch.addAction("Convert to NOP").triggered.connect(lambda : self.nop_out(addr))
		instr = self.find_instr(addr)
		if instr:
			if instr.is_patch_branch_allowed():
				patch.addAction("Never branch").triggered.connect(lambda : self.nop_out(addr))
				patch.addAction("Always branch").triggered.connect(lambda : self.always_branch(addr))
				patch.addAction("Invert branch").triggered.connect(lambda : self.invert_branch(addr))
			if instr.is_patch_to_zero_return_allowed():
				patch.addAction("Skip and return zero").triggered.connect(lambda : self.skip_and_return_zero(addr))
			if instr.is_patch_to_fixed_return_value_allowed():
				patch.addAction("Skip and return value...").triggered.connect(lambda : self.skip_and_return_value(addr))

		popup.exec_(QCursor.pos())

	def mousePressEvent(self, event):
		if (event.button() != Qt.LeftButton) and (event.button() != Qt.RightButton):
			return

		if not self.isMouseEventInBlock(event):
			# Click outside any block, enter scrolling mode
			self.scroll_base_x = event.x()
			self.scroll_base_y = event.y()
			self.scroll_mode = True
			self.viewport().grabMouse()
			return

		# Check for click on a token and highlight it
		token = self.getTokenForMouseEvent(event)
		if token:
			self.highlight_token = token[2:]
		else:
			self.highlight_token = None

		# Update current instruction
		instr = self.getInstrForMouseEvent(event)
		if instr != None:
			self.cur_instr = instr
		else:
			self.cur_instr = None

		self.viewport().update()

		if (instr != None) and (event.button() == Qt.RightButton):
			self.context_menu(instr)

	def mouseMoveEvent(self, event):
		if self.scroll_mode:
			x_delta = self.scroll_base_x - event.x()
			y_delta = self.scroll_base_y - event.y()
			self.scroll_base_x = event.x()
			self.scroll_base_y = event.y()
			self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + x_delta)
			self.verticalScrollBar().setValue(self.verticalScrollBar().value() + y_delta)

	def mouseReleaseEvent(self, event):
		if event.button() != Qt.LeftButton:
			return

		if self.scroll_mode:
			self.scroll_mode = False
			self.viewport().releaseMouse()

	def mouseDoubleClickEvent(self, event):
		token = self.getTokenForMouseEvent(event)
		if token and (token[2] == "ptr"):
			self.analysis.lock.acquire()
			if not self.analysis.functions.has_key(token[3]):
				# Not a function or not analyzed, go to address in hex editor
				addr = token[3]
				self.analysis.lock.release()
				self.view_in_hex_editor(addr)
			else:
				self.view.add_history_entry()
				self.function = token[3]
				self.ready = False
				self.desired_pos = None
				self.cur_instr = None
				self.highlight_token = None
				self.viewport().update()
				self.analysis.lock.release()

	def go_to_address(self):
		addr_str, ok = QInputDialog.getText(self, "Go To Address", "Address:", QLineEdit.Normal)
		if ok:
			try:
				addr = int(addr_str, 16)
				if (addr < self.data.start()) or (addr > self.data.end()):
					if hasattr(self.data, "symbols_by_name") and (addr_str in self.data.symbols_by_name):
						addr = self.data.symbols_by_name[addr_str]
					else:
						QMessageBox.critical(self, "Error", "Address out of range")
						return
			except:
				if hasattr(self.data, "symbols_by_name") and (addr_str in self.data.symbols_by_name):
					addr = self.data.symbols_by_name[addr_str]
				elif (addr_str[0] == '@') and hasattr(self.data, "symbols_by_name") and (addr_str[1:] in self.data.symbols_by_name):
					addr = self.data.symbols_by_name[addr_str[1:]]
				else:
					QMessageBox.critical(self, "Error", "Invalid address or symbol")
					return

			# Try navigating within disassembly, if it isn't within a function then
			# navigate to the hex editor
			if not self.view.navigate("disassembler", addr):
				self.view_in_hex_editor(addr)

	def enter_name(self):
		# A symbol must be selected
		if (self.highlight_token == None) or (self.highlight_token[0] != "ptr"):
			QMessageBox.critical(self, "Error", "No symbol selected.")
			return

		addr = self.highlight_token[1]
		name = self.highlight_token[2]

		# Ask for new name
		new_name, ok = QInputDialog.getText(self, "Rename Symbol", "Symbol name:", QLineEdit.Normal, name)
		if ok:
			self.analysis.create_symbol(addr, new_name)

	def undefine_name(self):
		# A symbol must be selected
		if (self.highlight_token == None) or (self.highlight_token[0] != "ptr"):
			QMessageBox.critical(self, "Error", "No symbol selected.")
			return

		addr = self.highlight_token[1]
		name = self.highlight_token[2]

		# Ask for new name
		self.analysis.undefine_symbol(addr, name)

	def navigate_for_find(self, addr):
		func, instr = self.analysis.find_instr(addr, True)
		if func != None:
			self.navigate(addr)
		else:
			self.make_proc(addr)
			self.cur_instr = addr
			self.desired_pos = None

	def perform_find(self, dlg):
		self.search_regex = dlg.search_regex()
		if self.cur_instr != None:
			self.search_start = self.cur_instr
		else:
			if self.function is None:
				return
			self.search_start = self.function

		found_loc = self.data.find(self.search_regex, self.search_start)
		if found_loc != -1:
			self.view.add_history_entry()
			self.navigate_for_find(found_loc)
			self.search_pos = found_loc + 1
			return

		found_loc = self.data.find(self.search_regex, self.data.start())
		if (found_loc != -1) and (found_loc < self.search_start):
			self.view.add_history_entry()
			self.navigate_for_find(found_loc)
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
				self.navigate_for_find(found_loc)
				self.search_pos = found_loc + 1
				return
			self.search_pos = 0
		else:
			if (found_loc != -1) and (found_loc < self.search_start):
				self.view.add_history_entry()
				self.navigate_for_find(found_loc)
				self.search_pos = found_loc + 1
				return

			QMessageBox.information(self, "End of Search", "No additional matches found.")
			self.search_pos = self.search_start
			return

		found_loc = self.data.find(self.search_regex, self.search_pos)
		if found_loc < self.search_start:
			self.view.add_history_entry()
			self.navigate_for_find(found_loc)
			self.search_pos = found_loc + 1
			return

		QMessageBox.information(self, "End of Search", "No additional matches found.")
		self.search_pos = self.search_start

	def keyPressEvent(self, event):
		if event.key() == Qt.Key_H:
			if self.cur_instr != None:
				self.view_in_hex_editor(self.cur_instr)
			else:
				if self.function is not None:
					self.view_in_hex_editor(self.function)
		elif event.key() == Qt.Key_G:
			self.go_to_address()
		elif event.key() == Qt.Key_N:
			self.enter_name()
		elif event.key() == Qt.Key_U:
			self.undefine_name()
		elif event.key() == Qt.Key_Slash:
			dlg = FindDialog(FindDialog.SEARCH_REGEX, self)
			if dlg.exec_() == QDialog.Accepted:
				self.perform_find(dlg)
		else:
			super(DisassemblerView, self).keyPressEvent(event)

	def prepareGraphNode(self, block):
		# Compute size of node in pixels
		width = 0
		height = 0
		for line in block.block.header_text.lines:
			chars = 0
			for part in line:
				chars += len(part[0])
			if chars > width:
				width = chars
			height += 1
		for instr in block.block.instrs:
			for line in instr.text.lines:
				chars = 0
				for part in line:
					chars += len(part[0])
				if chars > width:
					width = chars
				height += 1
		block.width = (width + 4) * self.charWidth + 4
		block.height = (height * self.charHeight) + (4 * self.charWidth) + 4

	def adjustGraphLayout(self, block, col, row):
		block.col += col
		block.row += row
		for edge in block.new_exits:
			self.adjustGraphLayout(self.blocks[edge], col, row)

	def computeGraphLayout(self, block):
		# Compute child node layouts and arrange them horizontally
		col = 0
		row_count = 1
		for edge in block.new_exits:
			self.computeGraphLayout(self.blocks[edge])
			self.adjustGraphLayout(self.blocks[edge], col, 1)
			col += self.blocks[edge].col_count
			if (self.blocks[edge].row_count + 1) > row_count:
				row_count = self.blocks[edge].row_count + 1

		block.row = 0
		if col >= 2:
			# Place this node centered over the child nodes
			block.col = (col - 2) / 2
			block.col_count = col
		else:
			# No child nodes, set single node's width (nodes are 2 columns wide to allow
			# centering over a branch)
			block.col = 0
			block.col_count = 2
		block.row_count = row_count

	def isEdgeMarked(self, edges, row, col, index):
		if index >= len(edges[row][col]):
			return False
		return edges[row][col][index]

	def markEdge(self, edges, row, col, index):
		while len(edges[row][col]) <= index:
			edges[row][col] += [False]
		edges[row][col][index] = True

	def findHorizEdgeIndex(self, edges, row, min_col, max_col):
		# Find a valid index
		i = 0
		while True:
			valid = True
			for col in range(min_col, max_col + 1):
				if self.isEdgeMarked(edges, row, col, i):
					valid = False
					break
			if valid:
				break
			i += 1

		# Mark chosen index as used
		for col in range(min_col, max_col + 1):
			self.markEdge(edges, row, col, i)
		return i

	def findVertEdgeIndex(self, edges, col, min_row, max_row):
		# Find a valid index
		i = 0
		while True:
			valid = True
			for row in range(min_row, max_row + 1):
				if self.isEdgeMarked(edges, row, col, i):
					valid = False
					break
			if valid:
				break
			i += 1

		# Mark chosen index as used
		for row in range(min_row, max_row + 1):
			self.markEdge(edges, row, col, i)
		return i

	def routeEdge(self, horiz_edges, vert_edges, edge_valid, start, end, color):
		edge = DisassemblerEdge(color, end)

		# Find edge index for initial outgoing line
		i = 0
		while True:
			if not self.isEdgeMarked(vert_edges, start.row + 1, start.col + 1, i):
				break
			i += 1
		self.markEdge(vert_edges, start.row + 1, start.col + 1, i)
		edge.addPoint(start.row + 1, start.col + 1)
		edge.start_index = i
		horiz = False

		# Find valid column for moving vertically to the target node
		if end.row < (start.row + 1):
			min_row = end.row
			max_row = start.row + 1
		else:
			min_row = start.row + 1
			max_row = end.row
		col = start.col + 1
		if min_row != max_row:
			ofs = 0
			while True:
				col = start.col + 1 - ofs
				if col >= 0:
					valid = True
					for row in range(min_row, max_row + 1):
						if not edge_valid[row][col]:
							valid = False
							break
					if valid:
						break

				col = start.col + 1 + ofs
				if col < len(edge_valid[min_row]):
					valid = True
					for row in range(min_row, max_row + 1):
						if not edge_valid[row][col]:
							valid = False
							break
					if valid:
						break

				ofs += 1

		if col != (start.col + 1):
			# Not in same column, need to generate a line for moving to the correct column
			if col < (start.col + 1):
				min_col = col
				max_col = start.col + 1
			else:
				min_col = start.col + 1
				max_col = col
			index = self.findHorizEdgeIndex(horiz_edges, start.row + 1, min_col, max_col)
			edge.addPoint(start.row + 1, col, index)
			horiz = True

		if end.row != (start.row + 1):
			# Not in same row, need to generate a line for moving to the correct row
			index = self.findVertEdgeIndex(vert_edges, col, min_row, max_row)
			edge.addPoint(end.row, col, index)
			horiz = False

		if col != (end.col + 1):
			# Not in ending column, need to generate a line for moving to the correct column
			if col < (end.col + 1):
				min_col = col
				max_col = end.col + 1
			else:
				min_col = end.col + 1
				max_col = col
			index = self.findHorizEdgeIndex(horiz_edges, end.row, min_col, max_col)
			edge.addPoint(end.row, end.col + 1, index)
			horiz = True

		# If last line was horizontal, choose the ending edge index for the incoming edge
		if horiz:
			index = self.findVertEdgeIndex(vert_edges, end.col + 1, end.row, end.row)
			edge.points[len(edge.points) - 1][2] = index

		return edge

	def renderFunction(self, func):
		# Create render nodes
		self.blocks = {}
		for block in func.blocks.values():
			self.blocks[block.entry] = DisassemblerBlock(block)
			self.prepareGraphNode(self.blocks[block.entry])

		# Populate incoming lists
		for block in self.blocks.values():
			for edge in block.block.exits:
				self.blocks[edge].incoming += [block.block.entry]

		# Construct acyclic graph where each node is used as an edge exactly once
		block = func.blocks[func.entry]
		visited = [func.entry]
		queue = [self.blocks[func.entry]]
		changed = True

		while changed:
			changed = False

			# First pick nodes that have single entry points
			while len(queue) > 0:
				block = queue.pop()

				for edge in block.block.exits:
					if edge in visited:
						continue

					# If node has no more unseen incoming edges, add it to the graph layout now
					if len(self.blocks[edge].incoming) == 1:
						self.blocks[edge].incoming.remove(block.block.entry)
						block.new_exits += [edge]
						queue += [self.blocks[edge]]
						visited += [edge]
						changed = True

			# No more nodes satisfy constraints, pick a node to continue constructing the graph
			best = None
			for block in self.blocks.values():
				if not block.block.entry in visited:
					continue
				for edge in block.block.exits:
					if edge in visited:
						continue
					if (best == None) or (len(self.blocks[edge].incoming) < best_edges) or ((len(self.blocks[edge].incoming) == best_edges) and (edge < best)):
						best = edge
						best_edges = len(self.blocks[edge].incoming)
						best_parent = block

			if best != None:
				self.blocks[best].incoming.remove(best_parent.block.entry)
				best_parent.new_exits += [best]
				visited += [best]
				changed = True

		# Compute graph layout from bottom up
		self.computeGraphLayout(self.blocks[func.entry])

		# Prepare edge routing
		horiz_edges = [None] * (self.blocks[func.entry].row_count + 1)
		vert_edges = [None] * (self.blocks[func.entry].row_count + 1)
		edge_valid = [None] * (self.blocks[func.entry].row_count + 1)
		for row in range(0, self.blocks[func.entry].row_count + 1):
			horiz_edges[row] = [None] * (self.blocks[func.entry].col_count + 1)
			vert_edges[row] = [None] * (self.blocks[func.entry].col_count + 1)
			edge_valid[row] = [True] * (self.blocks[func.entry].col_count + 1)
			for col in range(0, self.blocks[func.entry].col_count + 1):
				horiz_edges[row][col] = []
				vert_edges[row][col] = []
		for block in self.blocks.values():
			edge_valid[block.row][block.col + 1] = False

		# Perform edge routing
		for block in self.blocks.values():
			start = block
			for edge in block.block.exits:
				end = self.blocks[edge]
				color = Qt.black
				if edge == block.block.true_path:
					color = QColor(0, 144, 0)
				elif edge == block.block.false_path:
					color = QColor(144, 0, 0)
				start.edges += [self.routeEdge(horiz_edges, vert_edges, edge_valid, start, end, color)]

		# Compute edge counts for each row and column
		col_edge_count = [0] * (self.blocks[func.entry].col_count + 1)
		row_edge_count = [0] * (self.blocks[func.entry].row_count + 1)
		for row in range(0, self.blocks[func.entry].row_count + 1):
			for col in range(0, self.blocks[func.entry].col_count + 1):
				if len(horiz_edges[row][col]) > row_edge_count[row]:
					row_edge_count[row] = len(horiz_edges[row][col])
				if len(vert_edges[row][col]) > col_edge_count[col]:
					col_edge_count[col] = len(vert_edges[row][col])

		# Compute row and column sizes
		col_width = [0] * (self.blocks[func.entry].col_count + 1)
		row_height = [0] * (self.blocks[func.entry].row_count + 1)
		for block in self.blocks.values():
			if (int(block.width / 2)) > col_width[block.col]:
				col_width[block.col] = int(block.width / 2)
			if (int(block.width / 2)) > col_width[block.col + 1]:
				col_width[block.col + 1] = int(block.width / 2)
			if int(block.height) > row_height[block.row]:
				row_height[block.row] = int(block.height)

		# Compute row and column positions
		col_x = [0] * self.blocks[func.entry].col_count
		row_y = [0] * self.blocks[func.entry].row_count
		self.col_edge_x = [0] * (self.blocks[func.entry].col_count + 1)
		self.row_edge_y = [0] * (self.blocks[func.entry].row_count + 1)
		x = 16
		for i in range(0, self.blocks[func.entry].col_count):
			self.col_edge_x[i] = x
			x += 8 * col_edge_count[i]
			col_x[i] = x
			x += col_width[i]
		y = 16
		for i in range(0, self.blocks[func.entry].row_count):
			self.row_edge_y[i] = y
			y += 8 * row_edge_count[i]
			row_y[i] = y
			y += row_height[i]
		self.col_edge_x[self.blocks[func.entry].col_count] = x
		self.row_edge_y[self.blocks[func.entry].row_count] = y
		self.width = x + 16 + (8 * col_edge_count[self.blocks[func.entry].col_count])
		self.height = y + 16 + (8 * row_edge_count[self.blocks[func.entry].row_count])

		# Compute node positions
		for block in self.blocks.values():
			block.x = int((col_x[block.col] + col_width[block.col] + 4 * col_edge_count[block.col + 1]) - (block.width / 2))
			if (block.x + block.width) > (col_x[block.col] + col_width[block.col] + col_width[block.col + 1] + 8 * col_edge_count[block.col + 1]):
				block.x = int((col_x[block.col] + col_width[block.col] + col_width[block.col + 1] + 8 * col_edge_count[block.col + 1]) - block.width)
			block.y = row_y[block.row]

		# Precompute coordinates for edges
		for block in self.blocks.values():
			for edge in block.edges:
				start = edge.points[0]
				start_row = start[0]
				start_col = start[1]
				last_index = edge.start_index
				last_pt = QPoint(self.col_edge_x[start_col] + (8 * last_index) + 4,
					block.y + block.height + 4 - (2 * self.charWidth))
				pts = [last_pt]

				for i in range(0, len(edge.points)):
					end = edge.points[i]
					end_row = end[0]
					end_col = end[1]
					last_index = end[2]
					if start_col == end_col:
						new_pt = QPoint(last_pt.x(), self.row_edge_y[end_row] + (8 * last_index) + 4)
					else:
						new_pt = QPoint(self.col_edge_x[end_col] + (8 * last_index) + 4, last_pt.y())
					pts += [new_pt]
					last_pt = new_pt
					start_col = end_col

				new_pt = QPoint(last_pt.x(), edge.dest.y + self.charWidth - 1)
				pts += [new_pt]
				edge.polyline = pts

				pts = [QPoint(new_pt.x() - 3, new_pt.y() - 6), QPoint(new_pt.x() + 3, new_pt.y() - 6), new_pt]
				edge.arrow = pts

		# Adjust scroll bars for new size
		areaSize = self.viewport().size()
		self.adjustSize(areaSize.width(), areaSize.height())

		if self.desired_pos:
			# There was a position saved, navigate to it
			self.horizontalScrollBar().setValue(self.desired_pos[0])
			self.verticalScrollBar().setValue(self.desired_pos[1])
		elif self.cur_instr != None:
			self.show_cur_instr()
		else:
			# Ensure start node is visible
			start_x = self.blocks[func.entry].x + self.renderXOfs + int(self.blocks[func.entry].width / 2)
			self.horizontalScrollBar().setValue(start_x - int(areaSize.width() / 2))
			self.verticalScrollBar().setValue(0)

		self.update_id = func.update_id
		self.ready = True
		self.viewport().update(0, 0, areaSize.width(), areaSize.height())

	def updateTimerEvent(self):
		status = self.analysis.status
		if status != self.status:
			self.status = status
			self.statusUpdated.emit(self)

		if self.function is None:
			return

		if self.ready:
			# Check for updated code
			self.analysis.lock.acquire()
			if self.update_id != self.analysis.functions[self.function].update_id:
				self.renderFunction(self.analysis.functions[self.function])
			self.analysis.lock.release()
			return

		# View not up to date, check to see if active function is ready
		self.analysis.lock.acquire()
		if self.analysis.functions.has_key(self.function):
			if self.analysis.functions[self.function].ready:
				# Active function now ready, generate graph
				self.renderFunction(self.analysis.functions[self.function])
		self.analysis.lock.release()

	def show_cur_instr(self):
		for block in self.blocks.values():
			row = len(block.block.header_text.lines)
			for instr in block.block.instrs:
				if self.cur_instr == instr.addr:
					x = block.x + int(block.width / 2)
					y = block.y + (2 * self.charWidth) + int((row + 0.5) * self.charHeight)
					self.horizontalScrollBar().setValue(x + self.renderXOfs -
						int(self.horizontalScrollBar().pageStep() / 2))
					self.verticalScrollBar().setValue(y + self.renderYOfs -
						int(self.verticalScrollBar().pageStep() / 2))
					return
				row += len(instr.text.lines)

	def navigate(self, addr):
		# Check to see if address is within current function
		for block in self.blocks.values():
			row = len(block.block.header_text.lines)
			for instr in block.block.instrs:
				if (addr >= instr.addr) and (addr < (instr.addr + len(instr.opcode))):
					self.cur_instr = instr.addr
					self.show_cur_instr()
					self.viewport().update()
					return True
				row += len(instr.text.lines)

		# Check other functions for this address
		func, instr = self.analysis.find_instr(addr)
		if func != None:
			self.function = func
			self.cur_instr = instr
			self.highlight_token = None
			self.ready = False
			self.desired_pos = None
			self.viewport().update()
			return True

		return False

	def make_proc(self, addr):
		# Create a procedure at the requested address if one does not already exist
		if self.data.architecture() is None:
			# Architecture not defined yet, ask the user and set it now
			arch_dlg = ArchitectureDialog(self)
			if arch_dlg.exec_() == QDialog.Rejected:
				return False
			self.data.default_arch = arch_dlg.result

		self.analysis.lock.acquire()
		if addr not in self.analysis.functions:
			self.analysis.queue.append(addr)
		self.analysis.lock.release()

		self.function = addr
		self.cur_instr = None
		self.highlight_token = None
		self.ready = False
		self.desired_pos = None
		self.viewport().update()
		return True

	def navigate_to_history_entry(self, entry):
		self.function = entry.function
		self.ready = False
		self.desired_pos = [entry.scroll_x, entry.scroll_y]
		self.cur_instr = entry.cur_instr
		self.highlight_token = entry.highlight_token
		self.viewport().update()

	def get_history_entry(self):
		return DisassemblerHistoryEntry(self)

	def fontChanged(self):
		self.initFont()

		if self.ready:
			# Rerender function to update layout
			self.analysis.lock.acquire()
			self.renderFunction(self.analysis.functions[self.function])
			self.analysis.lock.release()

	def getPriority(data, ext):
		if Analysis.isPreferredForFile(data):
			return 80
		return 0
	getPriority = staticmethod(getPriority)

	def getViewName():
		return "Disassembler"
	getViewName = staticmethod(getViewName)

	def getShortViewName():
		return "Disassembler"
	getShortViewName = staticmethod(getShortViewName)

	def handlesNavigationType(name):
		return (name == "disassembler") or (name == "make_proc")
	handlesNavigationType = staticmethod(handlesNavigationType)

ViewTypes += [DisassemblerView]

