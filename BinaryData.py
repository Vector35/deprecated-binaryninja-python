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

import struct
import io
import thread
import Threads

DATA_ORIGINAL = 0
DATA_CHANGED = 1
DATA_INSERTED = 2


class BinaryAccessor:
	def read_uint8(self, ofs):
		return struct.unpack('B', self.read(ofs, 1))[0]

	def read_uint16(self, ofs):
		return struct.unpack('<H', self.read(ofs, 2))[0]

	def read_uint32(self, ofs):
		return struct.unpack('<I', self.read(ofs, 4))[0]

	def read_uint64(self, ofs):
		return struct.unpack('<Q', self.read(ofs, 8))[0]

	def read_uint16_le(self, ofs):
		return struct.unpack('<H', self.read(ofs, 2))[0]

	def read_uint32_le(self, ofs):
		return struct.unpack('<I', self.read(ofs, 4))[0]

	def read_uint64_le(self, ofs):
		return struct.unpack('<Q', self.read(ofs, 8))[0]

	def read_uint16_be(self, ofs):
		return struct.unpack('>H', self.read(ofs, 2))[0]

	def read_uint32_be(self, ofs):
		return struct.unpack('>I', self.read(ofs, 4))[0]

	def read_uint64_be(self, ofs):
		return struct.unpack('>Q', self.read(ofs, 8))[0]

	def read_int8(self, ofs):
		return struct.unpack('b', self.read(ofs, 1))[0]

	def read_int16(self, ofs):
		return struct.unpack('<h', self.read(ofs, 2))[0]

	def read_int32(self, ofs):
		return struct.unpack('<i', self.read(ofs, 4))[0]

	def read_int64(self, ofs):
		return struct.unpack('<q', self.read(ofs, 8))[0]

	def read_int16_le(self, ofs):
		return struct.unpack('<h', self.read(ofs, 2))[0]

	def read_int32_le(self, ofs):
		return struct.unpack('<i', self.read(ofs, 4))[0]

	def read_int64_le(self, ofs):
		return struct.unpack('<q', self.read(ofs, 8))[0]

	def read_int16_be(self, ofs):
		return struct.unpack('>h', self.read(ofs, 2))[0]

	def read_int32_be(self, ofs):
		return struct.unpack('>i', self.read(ofs, 4))[0]

	def read_int64_be(self, ofs):
		return struct.unpack('>q', self.read(ofs, 8))[0]

	def write_uint8(self, ofs, val):
		return self.write(ofs, struct.pack('B', val)) == 1

	def write_uint16(self, ofs, val):
		return self.write(ofs, struct.pack('<H', val)) == 2

	def write_uint32(self, ofs, val):
		return self.write(ofs, struct.pack('<I', val)) == 4

	def write_uint64(self, ofs, val):
		return self.write(ofs, struct.pack('<Q', val)) == 8

	def write_uint16_le(self, ofs, val):
		return self.write(ofs, struct.pack('<H', val)) == 2

	def write_uint32_le(self, ofs, val):
		return self.write(ofs, struct.pack('<I', val)) == 4

	def write_uint64_le(self, ofs, val):
		return self.write(ofs, struct.pack('<Q', val)) == 8

	def write_uint16_be(self, ofs, val):
		return self.write(ofs, struct.pack('>H', val)) == 2

	def write_uint32_be(self, ofs, val):
		return self.write(ofs, struct.pack('>I', val)) == 4

	def write_uint64_be(self, ofs, val):
		return self.write(ofs, struct.pack('>Q', val)) == 8

	def write_int8(self, ofs, val):
		return self.write(ofs, struct.pack('b', val)) == 1

	def write_int16(self, ofs, val):
		return self.write(ofs, struct.pack('<h', val)) == 2

	def write_int32(self, ofs, val):
		return self.write(ofs, struct.pack('<i', val)) == 4

	def write_int64(self, ofs, val):
		return self.write(ofs, struct.pack('<q', val)) == 8

	def write_int16_le(self, ofs, val):
		return self.write(ofs, struct.pack('<h', val)) == 2

	def write_int32_le(self, ofs, val):
		return self.write(ofs, struct.pack('<i', val)) == 4

	def write_int64_le(self, ofs, val):
		return self.write(ofs, struct.pack('<q', val)) == 8

	def write_int16_be(self, ofs, val):
		return self.write(ofs, struct.pack('>h', val)) == 2

	def write_int32_be(self, ofs, val):
		return self.write(ofs, struct.pack('>i', val)) == 4

	def write_int64_be(self, ofs, val):
		return self.write(ofs, struct.pack('>q', val)) == 8

	def end(self):
		return self.start() + len(self)

	def __str__(self):
		return self.read(0, len(self))

	def __getitem__(self, offset):
		if type(offset) == slice:
			start = offset.start
			end = offset.stop
			if start is None:
				start = self.start()
			if end is None:
				end = self.start() + len(self)
			if end < 0:
				end = self.start() + len(self) + end

			if (offset.step is None) or (offset.step == 1):
				return self.read(start, end - start)
			else:
				result = ""
				for i in xrange(start, end, offset.step):
					part = self.read(i, 1)
					if len(part) == 0:
						return result
					result += part
				return result

		result = self.read(offset, 1)
		if len(result) == 0:
			raise IndexError
		return result

	def __setitem__(self, offset, value):
		if type(offset) == slice:
			start = offset.start
			end = offset.stop
			if start is None:
				start = self.start()
			if end is None:
				end = self.start() + len(self)
			if end < 0:
				end = self.start() + len(self) + end

			if (offset.step is None) or (offset.step == 1):
				if end < start:
					return
				if len(value) != (end - start):
					self.remove(start, end - start)
					self.insert(start, value)
				else:
					self.write(start, value)
			else:
				rel_offset = 0
				j = 0
				for i in xrange(start, end, offset.step):
					if j < len(value):
						self.write(i + rel_offset, value[j])
					else:
						self.remove(i + rel_offset)
						rel_offset -= 1
		else:
			if self.write(offset, value) == 0:
				raise IndexError

	def __delitem__(self, offset):
		if type(offset) == slice:
			start = offset.start
			end = offset.stop
			if start is None:
				start = self.start()
			if end is None:
				end = self.start() + len(self)
			if end < 0:
				end = self.start() + len(self) + end

			if (offset.step is None) or (offset.step == 1):
				if end < start:
					return
				self.remove(start, end - start)
			else:
				rel_offset = 0
				for i in xrange(start, end, offset.step):
					self.remove(i + rel_offset)
					rel_offset -= 1
		else:
			if self.remove(offset, 1) == 0:
				raise IndexError


class WriteUndoEntry:
	def __init__(self, data, offset, old_contents, new_contents, old_mod):
		self.data = data
		self.offset = offset
		self.old_contents = old_contents
		self.new_contents = new_contents
		self.old_mod = old_mod

class InsertUndoEntry:
	def __init__(self, data, offset, contents):
		self.data = data
		self.offset = offset
		self.contents = contents

class RemoveUndoEntry:
	def __init__(self, data, offset, old_contents, old_mod):
		self.data = data
		self.offset = offset
		self.old_contents = old_contents
		self.old_mod = old_mod


class BinaryData(BinaryAccessor):
	def __init__(self, data = ""):
		self.data = data
		self.modification = [DATA_ORIGINAL] * len(data)
		self.modified = False
		self.callbacks = []
		self.undo_buffer = []
		self.redo_buffer = []
		self.temp_undo_buffer = []
		self.unmodified_undo_index = 0
		self.symbols_by_name = {}
		self.symbols_by_addr = {}
		self.default_arch = None

	def read(self, ofs, size):
		return self.data[ofs:(ofs + size)]

	def write(self, ofs, data):
		if len(data) == 0:
			return 0
		if ofs == len(self.data):
			return self.insert(len(self.data), data)
		if ofs >= len(self.data):
			return 0
		append = ""
		if (ofs + len(data)) > len(self.data):
			append = data[len(self.data)-ofs:]
			data = data[0:len(self.data)-ofs]

		undo_entry = WriteUndoEntry(self, ofs, self.data[ofs:ofs+len(data)], data, self.modification[ofs:ofs+len(data)])
		self.insert_undo_entry(undo_entry, self.undo_write, self.redo_write)

		self.data = self.data[0:ofs] + data + self.data[ofs+len(data):]
		for i in xrange(ofs, ofs + len(data)):
			if self.modification[i] == DATA_ORIGINAL:
				self.modification[i] = DATA_CHANGED
		for cb in self.callbacks:
			if hasattr(cb, "notify_data_write"):
				cb.notify_data_write(self, ofs, data)
		self.modified = True
		if len(append) > 0:
			return len(data) + self.insert(len(self.data), append)
		return len(data)

	def insert(self, ofs, data):
		if len(data) == 0:
			return 0
		if ofs > len(self.data):
			return 0

		undo_entry = InsertUndoEntry(self, ofs, data)
		self.insert_undo_entry(undo_entry, self.undo_insert, self.redo_insert)

		self.data = self.data[0:ofs] + data + self.data[ofs:]
		self.modification[ofs:ofs] = [DATA_INSERTED] * len(data)
		for cb in self.callbacks:
			if hasattr(cb, "notify_data_insert"):
				cb.notify_data_insert(self, ofs, data)
		self.modified = True
		return len(data)

	def remove(self, ofs, size):
		if size == 0:
			return 0
		if ofs >= len(self.data):
			return 0
		if (ofs + size) > len(self.data):
			size = len(self.data) - ofs

		undo_entry = RemoveUndoEntry(self, ofs, self.data[ofs:ofs+size], self.modification[ofs:ofs+size])
		self.insert_undo_entry(undo_entry, self.undo_remove, self.redo_remove)

		self.data = self.data[0:ofs] + self.data[ofs+size:]
		del self.modification[ofs:ofs+size]
		for cb in self.callbacks:
			if hasattr(cb, "notify_data_remove"):
				cb.notify_data_remove(self, ofs, size)
		self.modified = True
		return size

	def get_modification(self, ofs, size):
		return self.modification[ofs:ofs+size]

	def add_callback(self, cb):
		self.callbacks.append(cb)

	def remove_callback(self, cb):
		self.callbacks.remove(cb)

	def save(self, filename):
		f = io.open(filename, 'wb')
		f.write(self.data)
		f.close()
		self.modification = [DATA_ORIGINAL] * len(self.data)
		self.modified = False
		self.unmodified_undo_index = len(self.undo_buffer)

	def start(self):
		return 0

	def __len__(self):
		return len(self.data)

	def is_modified(self):
		return self.modified

	def find(self, regex, addr):
		match = regex.search(self.data, addr)
		if match == None:
			return -1
		return match.start()

	def commit_undo(self, before_loc, after_loc):
		if len(self.temp_undo_buffer) == 0:
			return
		if len(self.undo_buffer) < self.unmodified_undo_index:
			self.unmodified_undo_index = -1
		entries = self.temp_undo_buffer
		self.temp_undo_buffer = []
		self.undo_buffer.append([before_loc, after_loc, entries])
		self.redo_buffer = []

	def insert_undo_entry(self, data, undo_func, redo_func):
		self.temp_undo_buffer.append([data, undo_func, redo_func])

	def undo_write(self, entry):
		self.data = self.data[0:entry.offset] + entry.old_contents + self.data[entry.offset + len(entry.old_contents):]
		self.modification = self.modification[0:entry.offset] + entry.old_mod + self.modification[entry.offset + len(entry.old_mod):]
		for cb in self.callbacks:
			if hasattr(cb, "notify_data_write"):
				cb.notify_data_write(self, entry.offset, entry.old_contents)

	def redo_write(self, entry):
		self.data = self.data[0:entry.offset] + entry.new_contents + self.data[entry.offset + len(entry.new_contents):]
		for i in xrange(entry.offset, entry.offset + len(entry.new_contents)):
			if self.modification[i] == DATA_ORIGINAL:
				self.modification[i] = DATA_CHANGED
		for cb in self.callbacks:
			if hasattr(cb, "notify_data_write"):
				cb.notify_data_write(self, entry.offset, entry.new_contents)
		self.modified = True

	def undo_insert(self, entry):
		self.data = self.data[0:entry.offset] + self.data[entry.offset + len(entry.contents):]
		self.modification = self.modification[0:entry.offset] + self.modification[entry.offset + len(entry.contents):]
		for cb in self.callbacks:
			if hasattr(cb, "notify_data_remove"):
				cb.notify_data_remove(self, entry.offset, len(entry.contents))

	def redo_insert(self, entry):
		self.data = self.data[0:entry.offset] + entry.contents + self.data[entry.offset:]
		self.modification[entry.offset:entry.offset] = [DATA_INSERTED] * len(entry.contents)
		for cb in self.callbacks:
			if hasattr(cb, "notify_data_insert"):
				cb.notify_data_insert(self, entry.offset, entry.contents)
		self.modified = True

	def undo_remove(self, entry):
		self.data = self.data[0:entry.offset] + entry.old_contents + self.data[entry.offset:]
		self.modification = self.modification[0:entry.offset] + entry.old_mod + self.modification[entry.offset:]
		for cb in self.callbacks:
			if hasattr(cb, "notify_data_insert"):
				cb.notify_data_insert(self, entry.offset, entry.old_contents)

	def redo_remove(self, entry):
		self.data = self.data[0:entry.offset] + self.data[entry.offset + len(entry.old_contents):]
		self.modification = self.modification[0:entry.offset] + self.modification[entry.offset + len(entry.old_contents):]
		for cb in self.callbacks:
			if hasattr(cb, "notify_data_remove"):
				cb.notify_data_remove(self, entry.offset, len(entry.old_contents))
		self.modified = True

	def undo(self):
		if len(self.undo_buffer) == 0:
			return None

		undo_desc = self.undo_buffer.pop()
		self.redo_buffer.append(undo_desc)

		for entry in undo_desc[2][::-1]:
			entry[1](entry[0])

		self.modified = (len(self.undo_buffer) != self.unmodified_undo_index)
		return undo_desc[0]

	def redo(self):
		if len(self.redo_buffer) == 0:
			return None

		redo_desc = self.redo_buffer.pop()
		self.undo_buffer.append(redo_desc)

		for entry in redo_desc[2]:
			entry[2](entry[0])

		self.modified = (len(self.undo_buffer) != self.unmodified_undo_index)
		return redo_desc[1]

	def architecture(self):
		return self.default_arch


class BinaryFile(BinaryData):
	def __init__(self, filename):
		f = io.open(filename, 'rb')
		data = f.read()
		f.close()
		BinaryData.__init__(self, data)

