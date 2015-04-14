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

import array
import unicodedata


class TerminalEmulator:
	RENDITION_BOLD = 0x001
	RENDITION_DIM = 0x002
	RENDITION_UNDERLINE = 0x008
	RENDITION_INVERSE = 0x040
	RENDITION_HIDDEN = 0x080
	RENDITION_FOREGROUND_256 = 0x100
	RENDITION_BACKGROUND_256 = 0x200
	RENDITION_WRITTEN_CHAR = 0x800  # Only set when character was written normally, used to detect line wrap on copy/paste

	def __init__(self, rows, cols):
		self.rows = rows
		self.cols = cols

		# Initialize screen arrays
		self.screen = []
		self.rendition = []
		self.other_screen = []
		self.other_rendition = []
		self.alt_screen = False
		self.dirty = set()

		self.default_screen_line = array.array('u')
		self.default_rendition_line = array.array('I')
		for i in xrange(0, cols):
			self.default_screen_line.append(u' ')
			self.default_rendition_line.append(0)
		for i in xrange(0, rows):
			self.screen.append(array.array('u', self.default_screen_line))
			self.rendition.append(array.array('I', self.default_rendition_line))
			self.other_screen.append(array.array('u', self.default_screen_line))
			self.other_rendition.append(array.array('I', self.default_rendition_line))

		self.history_screen = []
		self.history_rendition = []

		self.active_rendition = 0

		self.cursor_row = 0
		self.cursor_col = 0
		self.cursor_visible = True
		self.tab_width = 8

		self.scroll_top = 0
		self.scroll_bottom = self.rows - 1

		self.saved_cursor_row = 0
		self.saved_cursor_col = 0

		self.saved_normal_cursor_row = 0
		self.saved_normal_cursor_col = 0
		self.saved_alt_cursor_row = 0
		self.saved_alt_cursor_col = 0

		self.escape_mode = False
		self.window_title_mode = False
		self.ignored_window_title = False
		self.line_draw = False
		self.utf8_buffer = ""
		self.utf8_len = 0
		self.unprocessed_input = u""
		self.application_cursor_keys = False
		self.insert_mode = False

		self.update_callback = None
		self.title_callback = None
		self.response_callback = None

		self.special_chars = {
			u'\x07': self.bell,
			u'\x08': self.backspace,
			u'\x09': self.horizontal_tab,
			u'\x0a': self.line_feed,
			u'\x0b': self.line_feed,
			u'\x0c': self.line_feed,
			u'\x0d': self.carriage_return
		}

		self.escape_sequences = {
			u'@': self.insert_chars,
			u'A': self.cursor_up,
			u'B': self.cursor_down,
			u'C': self.cursor_right,
			u'D': self.cursor_left,
			u'E': self.cursor_next_line,
			u'F': self.cursor_prev_line,
			u'G': self.set_cursor_col,
			u'`': self.set_cursor_col,
			u'd': self.set_cursor_row,
			u'H': self.move_cursor,
			u'f': self.move_cursor,
			u'I': self.cursor_right_tab,
			u'J': self.erase_screen,
			u'?J': self.erase_screen,
			u'K': self.erase_line,
			u'?K': self.erase_line,
			u'r': self.scroll_region,
			u'L': self.insert_lines,
			u'P': self.delete_chars,
			u'M': self.delete_lines,
			u'S': self.scroll_up_lines,
			u'T': self.scroll_down_lines,
			u'X': self.erase_chars,
			u'Z': self.cursor_left_tab,
			u'm': self.graphic_rendition,
			u'h': self.set_option,
			u'l': self.clear_option,
			u'?h': self.set_private_option,
			u'?l': self.clear_private_option,
			u'c': self.device_attr,
			u'>c': self.device_secondary_attr,
			u'n': self.device_status,
			u'?n': self.device_status,
			u'!p': self.soft_reset
		}

		self.charset_escapes = [u' ', u'#', u'%', u'(', u')', u'*', u'+']
		self.line_draw_map = {
			u'j': unicode('\xe2\x94\x98', 'utf8'),
			u'k': unicode('\xe2\x94\x90', 'utf8'),
			u'l': unicode('\xe2\x94\x8c', 'utf8'),
			u'm': unicode('\xe2\x94\x94', 'utf8'),
			u'n': unicode('\xe2\x94\xbc', 'utf8'),
			u'q': unicode('\xe2\x94\x80', 'utf8'),
			u't': unicode('\xe2\x94\x9c', 'utf8'),
			u'u': unicode('\xe2\x94\xa4', 'utf8'),
			u'v': unicode('\xe2\x94\xb4', 'utf8'),
			u'w': unicode('\xe2\x94\xac', 'utf8'),
			u'x': unicode('\xe2\x94\x82', 'utf8')
		}

	def invalidate(self):
		for i in xrange(0, self.rows):
			self.dirty.add(i)

	def resize(self, rows, cols):
		if rows > self.rows:
			# Adding rows
			for i in xrange(self.rows, rows):
				self.screen.append(array.array('u', self.default_screen_line))
				self.rendition.append(array.array('I', self.default_rendition_line))
				self.other_screen.append(array.array('u', self.default_screen_line))
				self.other_rendition.append(array.array('I', self.default_rendition_line))
		elif rows < self.rows:
			if self.alt_screen:
				# Alternate screen buffer is active
				normal_cursor_row = self.saved_normal_cursor_row
				if normal_cursor_row < rows:
					# Cursor is at top, remove lines from bottom
					self.other_screen = self.other_screen[:rows]
					self.other_rendition = self.other_rendition[:rows]
				else:
					# Cursor is at bottom, remove lines from top, and place them in the
					# history buffer
					for i in xrange(0, (normal_cursor_row + 1) - rows):
						screen_line = self.other_screen.pop(0)
						rendition_line = self.other_rendition.pop(0)
						self.history_screen.append(screen_line)
						self.history_rendition.append(rendition_line)
					self.other_screen = self.other_screen[:rows]
					self.other_rendition = self.other_rendition[:rows]
				self.screen = self.screen[:rows]
				self.rendition = self.rendition[:rows]
			else:
				# Normal screen buffer is active
				normal_cursor_row = self.cursor_row
				if normal_cursor_row < rows:
					# Cursor is at top, remove lines from bottom
					self.screen = self.screen[:rows]
					self.rendition = self.rendition[:rows]
				else:
					# Cursor is at bottom, remove lines from top, and place them in the
					# history buffer
					for i in xrange(0, (normal_cursor_row + 1) - rows):
						screen_line = self.screen.pop(0)
						rendition_line = self.rendition.pop(0)
						self.history_screen.append(screen_line)
						self.history_rendition.append(rendition_line)
					self.screen = self.screen[:rows]
					self.rendition = self.rendition[:rows]
				self.other_screen = self.other_screen[:rows]
				self.other_rendition = self.other_rendition[:rows]

		if cols > self.cols:
			# Adding columns
			for i in xrange(0, rows):
				for j in xrange(self.cols, cols):
					self.screen[i].append(u' ')
					self.rendition[i].append(0)
					self.other_screen[i].append(u' ')
					self.other_rendition[i].append(0)
			for j in xrange(self.cols, cols):
				self.default_screen_line.append(u' ')
				self.default_rendition_line.append(0)
		elif cols < self.cols:
			# Removing columns
			for i in xrange(0, rows):
				self.screen[i] = self.screen[i][0:cols]
				self.rendition[i] = self.rendition[i][0:cols]
				self.other_screen[i] = self.other_screen[i][0:cols]
				self.other_rendition[i] = self.other_rendition[i][0:cols]
			self.default_screen_line = self.default_screen_line[0:cols]
			self.default_rendition_line = self.default_rendition_line[0:cols]

		self.rows = rows
		self.cols = cols

		self.scroll_top = 0
		self.scroll_bottom = self.rows - 1

		# Ensure cursors are within bounds
		if self.cursor_col > cols:
			self.cursor_col = cols
		if self.cursor_row >= rows:
			self.cursor_row = rows - 1
		if self.saved_cursor_col > cols:
			self.saved_cursor_col = cols
		if self.saved_cursor_row >= rows:
			self.saved_cursor_row = rows - 1
		if self.saved_normal_cursor_col > cols:
			self.saved_normal_cursor_col = cols
		if self.saved_normal_cursor_row >= rows:
			self.saved_normal_cursor_row = rows - 1
		if self.saved_alt_cursor_col > cols:
			self.saved_alt_cursor_col = cols
		if self.saved_alt_cursor_row >= rows:
			self.saved_alt_cursor_row = rows - 1

		self.invalidate()
		if self.update_callback:
			self.update_callback()

	def response(self, data):
		if self.response_callback:
			self.response_callback(data)

	def bell(self):
		# I'm not going to annoy people here
		pass

	def backspace(self):
		if self.cursor_col > 0:
			self.cursor_col -= 1

	def horizontal_tab(self):
		self.cursor_col += self.tab_width - (self.cursor_col % self.tab_width)
		if self.cursor_col > self.cols:
			self.cursor_col = self.cols

	def scroll_up(self):
		top_screen = self.screen.pop(self.scroll_top)
		top_rendition = self.rendition.pop(self.scroll_top)

		# Only update history if windowing isn't being used and the normal screen buffer is active
		if (self.scroll_top == 0) and (self.scroll_bottom == (self.rows - 1)) and (not self.alt_screen):
			self.history_screen.append(top_screen)
			self.history_rendition.append(top_rendition)
			top_screen = array.array('u', self.default_screen_line)
			top_rendition = array.array('I', self.default_rendition_line)
		else:
			top_screen[0:self.cols] = self.default_screen_line
			top_rendition[0:self.cols] = self.default_rendition_line
		if self.active_rendition != 0:
			for i in xrange(0, self.cols):
				top_rendition[i] = self.active_rendition
		self.screen.insert(self.scroll_bottom, top_screen)
		self.rendition.insert(self.scroll_bottom, top_rendition)

		self.invalidate()

	def line_feed(self):
		if self.cursor_row >= self.scroll_bottom:
			self.scroll_up()
		else:
			self.cursor_row += 1

	def reverse_line_feed(self):
		if self.cursor_row <= self.scroll_top:
			self.insert_lines([1])
		else:
			self.cursor_row -= 1

	def newline(self):
		self.line_feed()
		self.cursor_col = 0

	def carriage_return(self):
		self.cursor_col = 0

	def escape(self):
		self.escape_mode = True

	def write_char(self, ch):
		if self.cursor_col >= self.cols:
			self.newline()
		if self.line_draw and (ch in self.line_draw_map):
			ch = self.line_draw_map[ch]

		if self.insert_mode:
			self.insert_chars([1])

		# Write character at cursor location
		self.screen[self.cursor_row][self.cursor_col] = ch
		self.rendition[self.cursor_row][self.cursor_col] = self.active_rendition | TerminalEmulator.RENDITION_WRITTEN_CHAR
		self.dirty.add(self.cursor_row)

		self.cursor_col += 1

	def erase_rect(self, top_row, left_col, bot_row, right_col):
		for row in xrange(top_row, bot_row):
			if row < 0:
				continue
			if row >= self.rows:
				break

			for col in xrange(left_col, right_col):
				if col < 0:
					continue
				if col >= self.cols:
					break
				self.screen[row][col] = u' '
				self.rendition[row][col] = self.active_rendition

			self.dirty.add(row)

	def cursor_up(self, params):
		count = params[0]
		if count == 0:
			count = 1
		self.cursor_row -= count
		if self.cursor_row < 0:
			self.cursor_row = 0

	def cursor_down(self, params):
		count = params[0]
		if count == 0:
			count = 1
		self.cursor_row += count
		if self.cursor_row >= self.rows:
			self.cursor_row = self.rows - 1

	def cursor_right(self, params):
		count = params[0]
		if count == 0:
			count = 1
		self.cursor_col += count
		if self.cursor_col >= self.cols:
			self.cursor_col = self.cols

	def cursor_left(self, params):
		count = params[0]
		if count == 0:
			count = 1
		self.cursor_col -= count
		if self.cursor_col < 0:
			self.cursor_col = 0

	def cursor_next_line(self, params):
		count = params[0]
		if count == 0:
			count = 1
		self.cursor_col = 0
		self.cursor_row += count
		if self.cursor_row >= self.rows:
			self.cursor_row = self.rows - 1

	def cursor_prev_line(self, params):
		count = params[0]
		if count == 0:
			count = 1
		self.cursor_col = 0
		self.cursor_row -= count
		if self.cursor_row < 0:
			self.cursor_row = 0

	def set_cursor_col(self, params):
		self.cursor_col = params[0] - 1
		if self.cursor_col < 0:
			self.cursor_col = 0
		if self.cursor_col > self.cols:
			self.cursor_col = self.cols

	def set_cursor_row(self, params):
		self.cursor_row = params[0] - 1
		if self.cursor_row < 0:
			self.cursor_row = 0
		if self.cursor_row >= self.rows:
			self.cursor_row = self.rows - 1

	def move_cursor(self, params):
		self.cursor_row = params[0] - 1
		if len(params) < 2:
			self.cursor_col = 0
		else:
			self.cursor_col = params[1] - 1
		if self.cursor_col < 0:
			self.cursor_col = 0
		if self.cursor_col > self.cols:
			self.cursor_col = self.cols
		if self.cursor_row < 0:
			self.cursor_row = 0
		if self.cursor_row >= self.rows:
			self.cursor_row = self.rows - 1

	def cursor_left_tab(self, params):
		count = params[0]
		if count == 0:
			count = 1
		if count > self.cols:
			count = self.cols
		for i in xrange(0, count):
			if (self.cursor_col % self.tab_width) == 0:
				self.cursor_col -= self.tab_width
			else:
				self.cursor_col -= self.cursor_col % self.tab_width
			if self.cursor_col < 0:
				self.cursor_col = 0

	def cursor_right_tab(self, params):
		count = params[0]
		if count == 0:
			count = 1
		if count > self.cols:
			count = self.cols
		for i in xrange(0, count):
			self.cursor_col += self.tab_width - (self.cursor_col % self.tab_width)
			if self.cursor_col > self.cols:
				self.cursor_col = self.cols

	def erase_screen(self, params):
		if (len(params) == 0) or (params[0] == 0):
			self.erase_rect(self.cursor_row, self.cursor_col, self.cursor_row + 1, self.cols)
			self.erase_rect(self.cursor_row + 1, 0, self.rows, self.cols)
		elif params[0] == 1:
			self.erase_rect(0, 0, self.cursor_row, self.cols)
			self.erase_rect(self.cursor_row, 0, self.cursor_row + 1, self.cursor_col + 1)
		elif params[0] == 2:
			self.erase_rect(0, 0, self.rows, self.cols)
			self.cursor_row = 0
			self.cursor_col = 0

	def erase_line(self, params):
		if (len(params) == 0) or (params[0] == 0):
			self.erase_rect(self.cursor_row, self.cursor_col, self.cursor_row + 1, self.cols)
		elif params[0] == 1:
			self.erase_rect(self.cursor_row, 0, self.cursor_row + 1, self.cursor_col + 1)
		elif params[0] == 2:
			self.erase_rect(self.cursor_row, 0, self.cursor_row + 1, self.cols)

	def scroll_region(self, params):
		if len(params) < 2:
			return
		self.scroll_top = params[0] - 1
		self.scroll_bottom = params[1] - 1
		if self.scroll_top < 0:
			self.scroll_top = 0
		if self.scroll_top >= self.rows:
			self.scroll_top = self.rows - 1
		if self.scroll_bottom < 0:
			self.scroll_bottom = 0
		if self.scroll_bottom >= self.rows:
			self.scroll_bottom = self.rows - 1

	def insert_lines(self, params):
		count = params[0]
		if count == 0:
			count = 1

		if count == 0:
			return
		if (self.cursor_row < self.scroll_top) or (self.cursor_row > self.scroll_bottom):
			return

		if count > ((self.scroll_bottom + 1) - self.cursor_row):
			count = (self.scroll_bottom + 1) - self.cursor_row

		erased_screen = []
		erased_rendition = []
		for i in xrange(0, count):
			erased_screen.append(self.screen.pop((self.scroll_bottom + 1) - count))
			erased_rendition.append(self.rendition.pop((self.scroll_bottom + 1) - count))
			for j in xrange(0, self.cols):
				erased_screen[i][j] = u' '
				erased_rendition[i][j] = self.active_rendition

		for i in xrange(0, count):
			self.screen.insert(self.cursor_row, erased_screen[i])
			self.rendition.insert(self.cursor_row, erased_rendition[i])

		self.invalidate()

	def delete_lines(self, params):
		count = params[0]
		if count == 0:
			count = 1

		if (self.cursor_row < self.scroll_top) or (self.cursor_row > self.scroll_bottom):
			return

		if count == 0:
			return
		if count > ((self.scroll_bottom + 1) - self.cursor_row):
			count = (self.scroll_bottom + 1) - self.cursor_row

		erased_screen = []
		erased_rendition = []
		for i in xrange(0, count):
			erased_screen.append(self.screen.pop(self.cursor_row))
			erased_rendition.append(self.rendition.pop(self.cursor_row))
			for j in xrange(0, self.cols):
				erased_screen[i][j] = u' '
				erased_rendition[i][j] = self.active_rendition

		for i in xrange(0, count):
			self.screen.insert((self.scroll_bottom + 1) - count, erased_screen[i])
			self.rendition.insert((self.scroll_bottom + 1) - count, erased_rendition[i])

		self.invalidate()

	def scroll_up_lines(self, params):
		count = params[0]
		if count == 0:
			count = 1

		if count == 0:
			return
		if count > ((self.scroll_bottom + 1) - self.scroll_top):
			count = (self.scroll_bottom + 1) - self.scroll_top

		erased_screen = []
		erased_rendition = []
		for i in xrange(0, count):
			erased_screen.append(self.screen.pop(self.scroll_top))
			erased_rendition.append(self.rendition.pop(self.scroll_top))
			for j in xrange(0, self.cols):
				erased_screen[i][j] = u' '
				erased_rendition[i][j] = self.active_rendition

		for i in xrange(0, count):
			self.screen.insert((self.scroll_bottom + 1) - count, erased_screen[i])
			self.rendition.insert((self.scroll_bottom + 1) - count, erased_rendition[i])

		self.invalidate()

	def scroll_down_lines(self, params):
		count = params[0]
		if count == 0:
			count = 1

		if count == 0:
			return
		if count > ((self.scroll_bottom + 1) - self.scroll_top):
			count = (self.scroll_bottom + 1) - self.scroll_top

		erased_screen = []
		erased_rendition = []
		for i in xrange(0, count):
			erased_screen.append(self.screen.pop((self.scroll_bottom + 1) - count))
			erased_rendition.append(self.rendition.pop((self.scroll_bottom + 1) - count))
			for j in xrange(0, self.cols):
				erased_screen[i][j] = u' '
				erased_rendition[i][j] = self.active_rendition

		for i in xrange(0, count):
			self.screen.insert(self.scroll_top, erased_screen[i])
			self.rendition.insert(self.scroll_top, erased_rendition[i])

		self.invalidate()

	def insert_chars(self, params):
		count = params[0]
		if count == 0:
			count = 1
		if count > (self.cols - self.cursor_col):
			count = self.cols - self.cursor_col
		for i in xrange(self.cols - 1, self.cursor_col + count - 1, -1):
			self.screen[self.cursor_row][i] = self.screen[self.cursor_row][i - count]
			self.rendition[self.cursor_row][i] = self.rendition[self.cursor_row][i - count]
		self.erase_rect(self.cursor_row, self.cursor_col, self.cursor_row + 1, self.cursor_col + count)
		self.dirty.add(self.cursor_row)

	def delete_chars(self, params):
		count = params[0]
		if count == 0:
			count = 1
		if count > (self.cols - self.cursor_col):
			count = self.cols - self.cursor_col
		for i in xrange(self.cursor_col, self.cols - count):
			self.screen[self.cursor_row][i] = self.screen[self.cursor_row][i + count]
			self.rendition[self.cursor_row][i] = self.rendition[self.cursor_row][i + count]
		self.erase_rect(self.cursor_row, self.cols - count, self.cursor_row + 1, self.cols)
		self.dirty.add(self.cursor_row)

	def erase_chars(self, params):
		count = params[0]
		if count == 0:
			count = 1
		self.erase_rect(self.cursor_row, self.cursor_col, self.cursor_row + 1, self.cursor_col + count)

	def graphic_rendition(self, params):
		i = 0
		while i < len(params):
			val = params[i]
			if val == 0:
				# Default rendition
				self.active_rendition = 0
			elif (val >= 1) and (val <= 9):
				# Set style
				self.active_rendition &= ~0xff
				self.active_rendition |= 1 << (val - 1)
			elif (val >= 21) and (val <= 29):
				# Clear style
				self.active_rendition &= ~(1 << (val - 21))
			elif (val >= 30) and (val <= 37):
				# Normal foreground color
				self.active_rendition &= ~(0x00ff0000 | TerminalEmulator.RENDITION_FOREGROUND_256)
				self.active_rendition |= (val - 29) << 16
			elif val == 38:
				if ((i + 2) < len(params)) and (params[i + 1] == 5):
					# 256-color foreground
					self.active_rendition &= ~0x00ff0000
					self.active_rendition |= TerminalEmulator.RENDITION_FOREGROUND_256
					self.active_rendition |= (params[i + 2] & 0xff) << 16
					i += 2
			elif val == 39:
				# Default foreground color
				self.active_rendition &= ~(0x00ff0000 | TerminalEmulator.RENDITION_FOREGROUND_256)
			elif (val >= 40) and (val <= 47):
				# Normal background color
				self.active_rendition &= ~(0xff000000 | TerminalEmulator.RENDITION_BACKGROUND_256)
				self.active_rendition |= (val - 39) << 24
			elif val == 48:
				if ((i + 2) < len(params)) and (params[i + 1] == 5):
					# 256-color background
					self.active_rendition &= ~0xff000000
					self.active_rendition |= TerminalEmulator.RENDITION_BACKGROUND_256
					self.active_rendition |= (params[i + 2] & 0xff) << 24
					i += 2
			elif val == 49:
				# Default background color
				self.active_rendition &= ~(0xff000000 | TerminalEmulator.RENDITION_BACKGROUND_256)
			elif (val >= 90) and (val <= 97):
				# High intensity foreground color
				self.active_rendition &= ~(0x00ff0000 | TerminalEmulator.RENDITION_FOREGROUND_256)
				self.active_rendition |= (val - 81) << 16
			elif (val >= 100) and (val <= 107):
				# High intensity background color
				self.active_rendition &= ~(0xff000000 | TerminalEmulator.RENDITION_BACKGROUND_256)
				self.active_rendition |= (val - 91) << 16
			else:
				print "Unsupported graphic rendition %d" % val

			i += 1

	def set_option(self, params):
		for option in params:
			if option == 4: # Insert mode
				self.insert_mode = True

	def clear_option(self, params):
		for option in params:
			if option == 4: # Insert mode
				self.insert_mode = False

	def set_private_option(self, params):
		for option in params:
			if option == 1: # Cursor key setting
				self.application_cursor_keys = True
			if option == 25: # Cursor visibility
				self.cursor_visible = True
			if ((option == 47) or (option == 1049)) and (not self.alt_screen): # Alternate screen buffer
				self.screen, self.other_screen = self.other_screen, self.screen
				self.rendition, self.other_rendition = self.other_rendition, self.rendition
				self.saved_normal_cursor_row = self.cursor_row
				self.saved_normal_cursor_col = self.cursor_col
				self.cursor_row = self.saved_alt_cursor_row
				self.cursor_col = self.saved_alt_cursor_col
				self.alt_screen = True
				self.invalidate()

	def clear_private_option(self, params):
		for option in params:
			if option == 1: # Cursor key setting
				self.application_cursor_keys = False
			if option == 25: # Cursor visibility
				self.cursor_visible = False
			if ((option == 47) or (option == 1049)) and (self.alt_screen): # Alternate screen buffer
				self.screen, self.other_screen = self.other_screen, self.screen
				self.rendition, self.other_rendition = self.other_rendition, self.rendition
				self.saved_alt_cursor_row = self.cursor_row
				self.saved_alt_cursor_col = self.cursor_col
				self.cursor_row = self.saved_normal_cursor_row
				self.cursor_col = self.saved_normal_cursor_col
				self.alt_screen = False
				self.invalidate()

	def device_attr(self, params):
		self.response("\033[?1;2c")

	def device_secondary_attr(self, params):
		self.response("\033[>0;1;0c")

	def device_status(self, params):
		if params[0] == 5:
			self.response("\033[0n") # OK
		elif params[0] == 6:
			self.response("\033[%d;%dR" % (self.cursor_row + 1, self.cursor_col + 1))

	def soft_reset(self, params):
		self.active_rendition = 0
		self.cursor_visible = True
		self.tab_width = 8
		self.scroll_top = 0
		self.scroll_bottom = self.rows - 1
		self.line_draw = False

	def parse_params(self, params):
		if len(params) == 0:
			result = []
		else:
			try:
				result = [int(i) for i in params.split(u';')]
			except ValueError:
				print "Invalid parameters '%s'" % params
				return []
		return result

	def process_escape(self, sequence):
		if (sequence == u'=') or (sequence == u'>'):
			# Numpad handling, just ignore it
			return
		if sequence == u'c':
			# Terminal reset
			self.active_rendition = 0
			self.erase_rect(0, 0, self.rows, self.cols)
			self.cursor_row = 0
			self.cursor_col = 0
			self.saved_cursor_row = 0
			self.saved_cursor_col = 0
			self.invalidate()
			return
		if sequence == u'7':
			# Save cursor
			self.saved_cursor_row = self.cursor_row
			self.saved_cursor_col = self.cursor_col
			return
		if sequence == u'8':
			# Restore cursor
			self.cursor_row = self.saved_cursor_row
			self.cursor_col = self.saved_cursor_col
			return
		if sequence == u'D':
			self.line_feed()
			return
		if sequence == u'E':
			self.newline()
			return
		if sequence == u'M':
			self.reverse_line_feed()
			return
		if sequence[0] != u'[':
			print "Unhandled escape sequence '%s'" % sequence
			return

		params = sequence[1:-1]
		mode = sequence[-1]

		if (len(params) > 0) and (params[0] == u'?'):
			mode = u'?' + mode
			params = params[1:]
		if (len(params) > 0) and (params[0] == u'>'):
			mode = u'>' + mode
			params = params[1:]
		if (len(params) > 0) and (params[0] == u'!'):
			mode = u'!' + mode
			params = params[1:]

		params = self.parse_params(params)
		if len(params) == 0:
			params = [0]

		if mode in self.escape_sequences:
			self.escape_sequences[mode](params)
		else:
			print "Unhandled escape sequence '%s'" % sequence

	def start_window_title(self, sequence):
		params = self.parse_params(sequence[1:-1])
		if (len(params) == 0) or (params[0] == 0) or (params[0] == 2):
			# Setting window name
			self.ignored_window_title = False
		else:
			# Setting icon name, just ignore
			self.ignored_window_title = True

	def process(self, data):
		for raw_ch in data:
			if self.utf8_len == 0:
				if ord(raw_ch) < 128:
					ch = unicode(raw_ch)
				elif ord(raw_ch) < 0xc0:
					# Unexpected continuation character
					ch = unichr(ord(raw_ch))
				elif ord(raw_ch) < 0xe0:
					self.utf8_buffer = raw_ch
					self.utf8_len = 1
				elif ord(raw_ch) < 0xf0:
					self.utf8_buffer = raw_ch
					self.utf8_len = 2
				elif ord(raw_ch) < 0xf8:
					self.utf8_buffer = raw_ch
					self.utf8_len = 3
				elif ord(raw_ch) < 0xfc:
					self.utf8_buffer = raw_ch
					self.utf8_len = 4
				elif ord(raw_ch) < 0xfe:
					self.utf8_buffer = raw_ch
					self.utf8_len = 5
				else:
					# Invalid first byte
					ch = unichr(ord(raw_ch))
			else:
				if (ord(raw_ch) & 0xc0) != 0x80:
					# Invalid continuation character
					ch = unichr(ord(raw_ch))
					self.utf8_len = 0
				else:
					self.utf8_buffer += raw_ch
					self.utf8_len -= 1
					if self.utf8_len == 0:
						ch = unicode(self.utf8_buffer, 'utf8', 'replace')

			if self.utf8_len > 0:
				continue

			# Check for combining characters
			try:
				if (unicodedata.combining(ch) != 0) and (self.cursor_col > 0):
					# Combining character, so combine it with the previously written character
					last_ch = self.screen[self.cursor_row][self.cursor_col - 1]
					combined = unicodedata.normalize("NFC", last_ch + ch)
					if len(combined) == 1:
						# Successful combine, write out new character
						self.screen[self.cursor_row][self.cursor_col - 1] = combined
						self.dirty.add(self.cursor_row)
						continue
			except TypeError:
				# Invalid character
				ch = u' '

			if self.window_title_mode:
				if ch == u'\007': # Bell character ends window title
					if self.title_callback and not self.ignored_window_title:
						self.title_callback(self.unprocessed_input)
					self.unprocessed_input = u""
					self.window_title_mode = False
				else:
					self.unprocessed_input += ch
			elif ch in self.special_chars:
				self.special_chars[ch]()
			elif self.escape_mode:
				self.unprocessed_input += ch
				if len(self.unprocessed_input) == 1:
					if (ch != u'[') and (ch != u']') and (ch not in self.charset_escapes):
						# Special type of escape sequence, no parameters
						self.process_escape(self.unprocessed_input)
						self.unprocessed_input = u""
						self.escape_mode = False
				elif (len(self.unprocessed_input) == 2) and (self.unprocessed_input[0] in self.charset_escapes):
					if self.unprocessed_input == "(0":
						# Select line drawing character set
						self.line_draw = True
					else:
						# Other character set escape, just use UTF8
						self.line_draw = False
					self.unprocessed_input = u""
					self.escape_mode = False
				elif (ch >= u'@') and (ch <= u'~'):
					# Ending character found, process sequence
					self.process_escape(self.unprocessed_input)
					self.unprocessed_input = u""
					self.escape_mode = False
				else:
					# Parameter character, add to pending string
					if self.unprocessed_input.startswith(u']') and (ch == u';'):
						# Setting window title, wait for bell character to finish
						self.start_window_title(self.unprocessed_input)
						self.unprocessed_input = u""
						self.escape_mode = False
						self.window_title_mode = True
			elif ch == u'\033':
				self.escape()
			else:
				self.write_char(ch)

		if self.update_callback:
			self.update_callback()

	def get_dirty_lines(self):
		result = self.dirty
		self.dirty = set()
		return result

