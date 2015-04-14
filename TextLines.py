# Copyright (c) 2011-2012 Rusty Wagner
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

HIGHLIGHT_NONE = 0
HIGHLIGHT_KEYWORD = 1
HIGHLIGHT_IDENTIFIER = 2
HIGHLIGHT_STRING = 3
HIGHLIGHT_VALUE = 4
HIGHLIGHT_ESCAPE = 5
HIGHLIGHT_COMMENT = 6
HIGHLIGHT_DIRECTIVE = 7


highlightTypes = {}


class HighlightState:
	def __init__(self, style):
		self.style = style

	def __eq__(self, other):
		if other is None:
			return False
		return self.style == other.style


class HighlightToken:
	def __init__(self, start, length, state):
		self.start = start
		self.length = length
		self.state = state


class Highlight:
	def __init__(self):
		pass

	def simple_tokenize(self, text):
		tokens = []
		cur_token = ""
		string_char = None
		backslash = False
		offset = 0
		for i in xrange(0, len(text)):
			ch = text[i]
			if string_char:
				if backslash:
					cur_token += ch
					backslash = False
				elif ch == '\\':
					cur_token += ch
					backslash = True
				elif ch == string_char:
					cur_token += ch
					tokens.append((offset, cur_token))
					cur_token = ""
					offset = i + 1
					string_char = None
				else:
					cur_token += ch
			elif (ch == '\'') or (ch == '"'):
				if len(cur_token) > 0:
					tokens.append((offset, cur_token))
					cur_token = ""
				offset = i
				cur_token = ch
				string_char = ch
			elif (ch == ' ') or (ch == '\t'):
				if len(cur_token) > 0:
					tokens.append((offset, cur_token))
					cur_token = ""
				offset = i + 1
			elif ((ch >= '0') and (ch <= '9')) or ((ch >= 'A') and (ch <= 'Z')) or ((ch >= 'a') and (ch <= 'z')) or (ch == '_'):
				cur_token += ch
			else:
				if len(cur_token) > 0:
					tokens.append((offset, cur_token))
					cur_token = ""
				tokens.append((offset, ch))
				offset = i + 1
		if len(cur_token) > 0:
			tokens.append((offset, cur_token))
		return tokens

	def append_escaped_string_tokens(self, line, offset, text):
		cur_token = ""
		token_start = offset
		i = 0
		while i < len(text):
			if text[i] == '\\':
				if len(cur_token) > 0:
					line.tokens.append(HighlightToken(token_start, len(cur_token),
						HighlightState(HIGHLIGHT_STRING)))
					cur_token = ""
				if text[i:i+2] == "\\x":
					line.tokens.append(HighlightToken(offset + i, len(text[i:i+4]),
						HighlightState(HIGHLIGHT_ESCAPE)))
					i += len(text[i:i+4])
				elif text[i:i+2] == "\\u":
					line.tokens.append(HighlightToken(offset + i, len(text[i:i+6]),
						HighlightState(HIGHLIGHT_ESCAPE)))
					i += len(text[i:i+6])
				else:
					line.tokens.append(HighlightToken(offset + i, len(text[i:i+2]),
						HighlightState(HIGHLIGHT_ESCAPE)))
					i += len(text[i:i+2])
				token_start = offset + i
			else:
				cur_token += text[i]
				i += 1
		if len(cur_token) > 0:
			line.tokens.append(HighlightToken(token_start, len(cur_token), HighlightState(HIGHLIGHT_STRING)))


class TextLine:
	def __init__(self, offset, length, width, offset_map, newline_length):
		self.offset = offset
		self.length = length
		self.width = width
		self.offset_map = offset_map
		self.newline_length = newline_length
		self.highlight_state = HighlightState(HIGHLIGHT_NONE)
		self.tokens = []

	def offset_to_col(self, offset):
		if len(self.offset_map) == 0:
			return offset
		for i in xrange(0, len(self.offset_map)):
			if self.offset_map[i][0] > offset:
				if i == 0:
					return offset
				return self.offset_map[i - 1][1] + (offset - self.offset_map[i - 1][0])
		return self.offset_map[len(self.offset_map) - 1][1] + (offset - self.offset_map[len(self.offset_map) - 1][0])

	def col_to_offset(self, col):
		if len(self.offset_map) == 0:
			if col > self.length:
				return self.length
			return col
		for i in xrange(0, len(self.offset_map)):
			if self.offset_map[i][1] > col:
				if i == 0:
					if col > self.length:
						return self.length
					if col >= self.offset_map[i][0]:
						return self.offset_map[i][0] - 1
					return col
				offset = self.offset_map[i - 1][0] + (col - self.offset_map[i - 1][1])
				if offset >= self.offset_map[i][0]:
					return self.offset_map[i][0] - 1
				return offset
		offset = self.offset_map[len(self.offset_map) - 1][0] + (col - self.offset_map[len(self.offset_map) - 1][1])
		if offset > self.length:
			return self.length
		return offset

	def read(self, data):
		return data.read(data.start() + self.offset, self.length)

	def recompute(self, data, tab_width):
		contents = self.read(data)
		width = 0
		self.offset_map = []
		for i in xrange(0, len(contents)):
			if contents[i] == '\t':
				width += tab_width - (width % tab_width)
				self.offset_map.append((i + 1, width))
			else:
				width += 1
		self.width = width

	def leading_tab_width(self, data, tab_width):
		contents = self.read(data)
		width = 0
		for i in xrange(0, len(contents)):
			if contents[i] == '\t':
				width += tab_width
			else:
				break
		return width

	def leading_whitespace_width(self, data, tab_width):
		contents = self.read(data)
		width = 0
		for i in xrange(0, len(contents)):
			if contents[i] == '\t':
				width += tab_width - (width % tab_width)
			elif contents[i] == ' ':
				width += 1
			else:
				break
		return width


class TextLines:
	def __init__(self, data, tab_width, highlight = None):
		self.data = data
		self.tab_width = tab_width
		self.highlight = highlight
		self.callbacks = []

		self.data.add_callback(self)

		newline_count = {"\r": 0, "\n": 0, "\r\n": 0, "\n\r": 0}

		offset = 0
		width = 0
		line_start = offset
		offset_map = []
		self.lines = []

		# Break the file into lines
		while offset < len(self.data):
			ch = self.data.read(offset + self.data.start(), 1)
			if len(ch) == 0:
				break
			offset += 1

			if ch == '\r':
				if self.data.read(offset, 1) == '\n':
					offset += 1
					newline_count['\r\n'] += 1
					self.lines.append(TextLine(line_start, (offset - 2) - line_start, width, offset_map, 2))
					line_start = offset
					width = 0
					offset_map = []
				else:
					newline_count['\r'] += 1
					self.lines.append(TextLine(line_start, (offset - 1) - line_start, width, offset_map, 1))
					line_start = offset
					width = 0
					offset_map = []
			elif ch == '\n':
				if self.data.read(offset, 1) == '\r':
					offset += 1
					newline_count['\n\r'] += 1
					self.lines.append(TextLine(line_start, (offset - 2) - line_start, width, offset_map, 2))
					line_start = offset
					width = 0
					offset_map = []
				else:
					newline_count['\n'] += 1
					self.lines.append(TextLine(line_start, (offset - 1) - line_start, width, offset_map, 1))
					line_start = offset
					width = 0
					offset_map = []
			elif ch == '\t':
				width += self.tab_width - (width % self.tab_width)
				offset_map.append((offset - line_start, width))
			else:
				width += 1

		if (line_start != offset) or (len(self.lines) == 0):
			self.lines.append(TextLine(line_start, offset - line_start, width, offset_map, 0))

		# If there is a trailing newline, add the final blank line to ensure consistent editing
		if (len(self.lines) > 0) and (self.lines[len(self.lines) - 1].newline_length > 0):
			self.lines.append(TextLine(offset, 0, 0, [], 0))

		# Determine what type of newline should be used for this file
		self.default_newline = '\n'
		default_newline_count = newline_count['\n']
		for newline in newline_count.keys():
			if newline_count[newline] > default_newline_count:
				self.default_newline = newline
				default_newline_count = newline_count[newline]

		# Compute maximum line width
		self.max_line_width = 0
		self.update_max_width()

		if self.highlight:
			# Run text through the syntax highlighter
			if hasattr(self.highlight, "default_state"):
				state = self.highlight.default_state
			else:
				state = HighlightState(HIGHLIGHT_NONE)
			for line in self.lines:
				line.highlight_state = state
				line.tokens = []
				text = self.data.read(self.data.start() + line.offset, line.length)
				state = self.highlight.update_line(line, text)

	def close(self):
		self.data.remove_callback(self)

	def set_highlight(self, highlight):
		self.highlight = highlight

		# Reapply highlighting to entire file
		if self.highlight:
			# Run text through the syntax highlighter
			if hasattr(self.highlight, "default_state"):
				state = self.highlight.default_state
			else:
				state = HighlightState(HIGHLIGHT_NONE)
			for line in self.lines:
				line.highlight_state = state
				line.tokens = []
				text = self.data.read(self.data.start() + line.offset, line.length)
				state = self.highlight.update_line(line, text)
		else:
			for line in self.lines:
				line.highlight_state = None
				line.tokens = []

		# Notify callbacks that everything has updated
		for cb in self.callbacks:
			if hasattr(cb, "notify_update_lines"):
				cb.notify_update_lines(self, 0, len(self.lines))

	def offset_to_line(self, offset):
		# Binary search for the correct line for speed
		min_line = 0
		max_line = len(self.lines)
		while min_line < max_line:
			i = int((min_line + max_line) / 2)
			if i < min_line:
				i = min_line
			if i >= max_line:
				i = max_line - 1

			if (offset >= self.lines[i].offset) and (offset < (self.lines[i].offset + self.lines[i].length +
				self.lines[i].newline_length)):
				return i

			if offset < self.lines[i].offset:
				max_line = i
			else:
				min_line = i + 1

		# If line not found, was past the end of the buffer
		return len(self.lines) - 1

	def rebase_lines(self, first, diff):
		for i in xrange(first, len(self.lines)):
			self.lines[i].offset += diff

	def rebase_lines_absolute(self, first, offset):
		self.rebase_lines(first, offset - self.lines[first].offset)

	def update_highlight(self, line, count):
		if self.highlight:
			# Run updated lines through the highlighter, and continue updating until the state is consistent
			# with what was already there
			final_count = 0
			state = self.lines[line].highlight_state
			while line < len(self.lines):
				self.lines[line].highlight_state = state
				self.lines[line].tokens = []
				text = self.data.read(self.data.start() + self.lines[line].offset, self.lines[line].length)
				state = self.highlight.update_line(self.lines[line], text)

				line += 1
				final_count += 1

				# If we have processed the required lines, break out when highlighting is up to date
				if (line < len(self.lines)) and (state == self.lines[line].highlight_state) and (final_count >= count):
					# Starting state hasn't changed for this line, so the rest of the data won't change either
					break
		else:
			# No highlighting, only update the range specified
			final_count = count
		return final_count

	def update_max_width(self):
		max_line_width = 0
		for line in self.lines:
			if line.width > max_line_width:
				max_line_width = line.width

		changed = self.max_line_width != max_line_width
		self.max_line_width = max_line_width

		if changed:
			for cb in self.callbacks:
				if hasattr(cb, "notify_max_width_changed"):
					cb.notify_max_width_changed(self, max_line_width)

	def add_callback(self, cb):
		self.callbacks.append(cb)

	def remove_callback(self, cb):
		self.callbacks.remove(cb)

	def handle_delete(self, offset, size):
		# Figure out how lines are affected by the delete, process lines until deleted range is exhausted
		line = self.offset_to_line(offset)
		while size > 0:
			x = offset - self.lines[line].offset
			if size > (self.lines[line].length - x):
				line_remaining = (self.lines[line].length + self.lines[line].newline_length - x)
				if size >= line_remaining:
					# Removing the entire remaining part of the line, combine with next line
					to_remove = line_remaining
					if line + 1 < len(self.lines):
						self.lines[line].length = x + self.lines[line + 1].length
						self.lines[line].newline_length = self.lines[line + 1].newline_length
						del(self.lines[line + 1])
					else:
						self.lines[line].length = x
						self.lines[line].newline_length = 0
				else:
					# Removing part of the newline
					self.newline_length = line_remaining - size
					to_remove = size
				self.rebase_lines(line + 1, -to_remove)
				size -= to_remove
			else:
				# Removing part of the line
				self.lines[line].length -= size
				self.rebase_lines(line + 1, -size)
				size = 0
		return line

	def handle_insert(self, offset, contents):
		# Figure out how lines are affected by the insertion
		line = self.offset_to_line(offset)
		first_line = line
		i = 0
		while i < len(contents):
			if (contents[i:i+2] == '\r\n') or (contents[i:i+2] == '\n\r'):
				# Inserting two character newline, split current line into two
				x = (offset + i) - self.lines[line].offset
				remaining = self.lines[line].length - x
				next_line = TextLine(offset + i + 2, remaining, 0, [], self.lines[line].newline_length)
				self.lines[line].length = x
				self.lines[line].newline_length = 2
				line += 1
				self.lines.insert(line, next_line)
				i += 2
			elif (contents[i] == '\r') or (contents[i] == '\n'):
				# Inserting one character newline, split current line into two
				x = (offset + i) - self.lines[line].offset
				remaining = self.lines[line].length - x
				next_line = TextLine(offset + i + 1, remaining, 0, [], self.lines[line].newline_length)
				self.lines[line].length = x
				self.lines[line].newline_length = 1
				line += 1
				self.lines.insert(line, next_line)
				i += 1
			else:
				# Normal character, make current line longer
				self.lines[line].length += 1
				i += 1

		# Rebase remaining lines to account for insertion
		if (line + 1) < len(self.lines):
			self.rebase_lines_absolute(line + 1, self.lines[line].offset + self.lines[line].length +
				self.lines[line].newline_length)

		return first_line, line

	def notify_data_write(self, data, offset, contents):
		# Handle a write by simulating a delete then an insert
		old_line_count = len(self.lines)
		self.handle_delete(offset, len(contents))
		first_line, line = self.handle_insert(offset, contents)

		# Update width and offsets for affected lines
		lines_affected = (len(self.lines) - old_line_count) + 1
		for i in xrange(first_line, first_line + lines_affected):
			self.lines[i].recompute(self.data, self.tab_width)

		# Notify callbacks about any inserted or removed lines 
		if len(self.lines) > old_line_count:
			for cb in self.callbacks:
				if hasattr(cb, "notify_insert_lines"):
					cb.notify_insert_lines(self, first_line, len(self.lines) - old_line_count)
		elif len(self.lines) < old_line_count:
			for cb in self.callbacks:
				if hasattr(cb, "notify_remove_lines"):
					cb.notify_remove_lines(self, line, old_line_count - len(self.lines))

		# Update syntax highlighting and notify callbacks about updates
		count = self.update_highlight(first_line, lines_affected)

		for cb in self.callbacks:
			if hasattr(cb, "notify_update_lines"):
				cb.notify_update_lines(self, first_line, count)

		self.update_max_width()

	def notify_data_insert(self, data, offset, contents):
		old_line_count = len(self.lines)
		first_line, line = self.handle_insert(offset, contents)

		# Update width and offsets for affected lines
		lines_affected = (len(self.lines) - old_line_count) + 1
		for i in xrange(first_line, first_line + lines_affected):
			self.lines[i].recompute(self.data, self.tab_width)

		# Notify callbacks about any inserted lines 
		if len(self.lines) != old_line_count:
			for cb in self.callbacks:
				if hasattr(cb, "notify_insert_lines"):
					cb.notify_insert_lines(self, first_line, len(self.lines) - old_line_count)

		# Update syntax highlighting and notify callbacks about updates
		count = self.update_highlight(first_line, lines_affected)

		for cb in self.callbacks:
			if hasattr(cb, "notify_update_lines"):
				cb.notify_update_lines(self, first_line, count)

		self.update_max_width()

	def notify_data_remove(self, data, offset, size):
		old_line_count = len(self.lines)
		line = self.handle_delete(offset, size)

		# Only one line's width (the current one) can be affected, which may have involved combining lines above
		self.lines[line].recompute(self.data, self.tab_width)

		# Notify callbacks about any removed lines 
		if len(self.lines) != old_line_count:
			for cb in self.callbacks:
				if hasattr(cb, "notify_remove_lines"):
					cb.notify_remove_lines(self, line, old_line_count - len(self.lines))

		# Update syntax highlighting and notify callbacks about updates
		count = self.update_highlight(line, 1)

		for cb in self.callbacks:
			if hasattr(cb, "notify_update_lines"):
				cb.notify_update_lines(self, line, count)

		self.update_max_width()

