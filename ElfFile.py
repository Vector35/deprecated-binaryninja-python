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

from BinaryData import *
from Structure import *
from HexEditor import *
from View import *


class ElfFile(BinaryAccessor):
	def __init__(self, data):
		self.data = data
		self.valid = False
		self.callbacks = []
		self.symbols_by_name = {}
		self.symbols_by_addr = {}
		if not self.is_elf():
			return

		try:
			self.tree = Structure(self.data)
			self.header = self.tree.struct("ELF header", "header")
			self.header.struct("ELF identification", "ident")

			self.header.ident.uint32("magic")
			self.header.ident.uint8("file_class")
			self.header.ident.uint8("encoding")
			self.header.ident.uint8("version")
			self.header.ident.uint8("abi")
			self.header.ident.uint8("abi_version")
			self.header.ident.bytes(7, "pad")

			self.header.uint16("type")
			self.header.uint16("arch")
			self.header.uint32("version")

			self.symbol_table_section = None
			self.dynamic_symbol_table_section = None

			if self.header.ident.file_class == 1: # 32-bit
				self.header.uint32("entry")
				self.header.uint32("program_header_offset")
				self.header.uint32("section_header_offset")
				self.header.uint32("flags")
				self.header.uint16("header_size")
				self.header.uint16("program_header_size")
				self.header.uint16("program_header_count")
				self.header.uint16("section_header_size")
				self.header.uint16("section_header_count")
				self.header.uint16("string_table")

				try:
					self.sections = self.tree.array(self.header.section_header_count, "sections")
					for i in range(0, self.header.section_header_count):
						section = self.sections[i]
						section.seek(self.header.section_header_offset + (i * 40))
						section.uint32("name")
						section.uint32("type")
						section.uint32("flags")
						section.uint32("addr")
						section.uint32("offset")
						section.uint32("size")
						section.uint32("link")
						section.uint32("info")
						section.uint32("align")
						section.uint32("entry_size")

						if section.type == 2:
							self.symbol_table_section = section
						elif section.type == 11:
							self.dynamic_symbol_table_section = section
				except:
					# Section headers are not required to load an ELF, skip errors
					self.sections = self.tree.array(0, "sections")
					pass

				self.program_headers = self.tree.array(self.header.program_header_count, "programHeaders")
				for i in range(0, self.header.program_header_count):
					header = self.program_headers[i]
					header.seek(self.header.program_header_offset + (i * 32))
					header.uint32("type")
					header.uint32("offset")
					header.uint32("virtual_addr")
					header.uint32("physical_addr")
					header.uint32("file_size")
					header.uint32("memory_size")
					header.uint32("flags")
					header.uint32("align")

				# Parse symbol tables
				self.symbols_by_name["_start"] = self.entry()
				self.symbols_by_addr[self.entry()] = "_start"

				try:
					if self.symbol_table_section:
						self.symbol_table = self.tree.array(self.symbol_table_section.size / 16, "Symbols", "symbols")
						self.parse_symbol_table_32(self.symbol_table, self.symbol_table_section, self.sections[self.symbol_table_section.link])

					if self.dynamic_symbol_table_section:
						self.dynamic_symbol_table = self.tree.array(self.dynamic_symbol_table_section.size / 16, "Symbols", "symbols")
						self.parse_symbol_table_32(self.dynamic_symbol_table, self.dynamic_symbol_table_section, self.sections[self.dynamic_symbol_table_section.link])
				except:
					# Skip errors in symbol table
					pass

				# Parse relocation tables
				self.plt = {}
				for section in self.sections:
					if section.type == 9:
						self.parse_reloc_32(section)
					elif section.type == 4:
						self.parse_reloca_32(section)
			elif self.header.ident.file_class == 2: # 64-bit
				self.header.uint64("entry")
				self.header.uint64("program_header_offset")
				self.header.uint64("section_header_offset")
				self.header.uint32("flags")
				self.header.uint16("header_size")
				self.header.uint16("program_header_size")
				self.header.uint16("program_header_count")
				self.header.uint16("section_header_size")
				self.header.uint16("section_header_count")
				self.header.uint16("string_table")

				try:
					self.sections = self.tree.array(self.header.section_header_count, "sections")
					for i in range(0, self.header.section_header_count):
						section = self.sections[i]
						section.seek(self.header.section_header_offset + (i * 64))
						section.uint32("name")
						section.uint32("type")
						section.uint64("flags")
						section.uint64("addr")
						section.uint64("offset")
						section.uint64("size")
						section.uint32("link")
						section.uint32("info")
						section.uint64("align")
						section.uint64("entry_size")

						if section.type == 2:
							self.symbol_table_section = section
						elif section.type == 11:
							self.dynamic_symbol_table_section = section
				except:
					# Section headers are not required to load an ELF, skip errors
					self.sections = self.tree.array(0, "sections")
					pass

				self.program_headers = self.tree.array(self.header.program_header_count, "program_headers")
				for i in range(0, self.header.program_header_count):
					header = self.program_headers[i]
					header.seek(self.header.program_header_offset + (i * 56))
					header.uint32("type")
					header.uint32("flags")
					header.uint64("offset")
					header.uint64("virtual_addr")
					header.uint64("physical_addr")
					header.uint64("file_size")
					header.uint64("memory_size")
					header.uint64("align")

				# Parse symbol tables
				self.symbols_by_name["_start"] = self.entry()
				self.symbols_by_addr[self.entry()] = "_start"

				try:
					if self.symbol_table_section:
						self.symbol_table = self.tree.array(self.symbol_table_section.size / 24, "Symbols", "symbols")
						self.parse_symbol_table_64(self.symbol_table, self.symbol_table_section, self.sections[self.symbol_table_section.link])

					if self.dynamic_symbol_table_section:
						self.dynamic_symbol_table = self.tree.array(self.dynamic_symbol_table_section.size / 24, "Symbols", "symbols")
						self.parse_symbol_table_64(self.dynamic_symbol_table, self.dynamic_symbol_table_section, self.sections[self.dynamic_symbol_table_section.link])
				except:
					# Skip errors in symbol table
					pass

				# Parse relocation tables
				self.plt = {}
				for section in self.sections:
					if section.type == 9:
						self.parse_reloc_64(section)
					elif section.type == 4:
						self.parse_reloca_64(section)

			self.tree.complete()
			self.valid = True
		except:
			self.valid = False

		if self.valid:
			self.data.add_callback(self)

	def read_string_table(self, strings, offset):
		end = strings.find("\x00", offset)
		return strings[offset:end]

	def parse_symbol_table_32(self, table, section, string_table):
		strings = self.data.read(string_table.offset, string_table.size)
		for i in range(0, section.size / 16):
			table[i].seek(section.offset + (i * 16))
			table[i].uint32("name_offset")
			table[i].uint32("value")
			table[i].uint32("size")
			table[i].uint8("info")
			table[i].uint8("other")
			table[i].uint16("section")
			table[i].name = self.read_string_table(strings, table[i].name_offset)

			if len(table[i].name) > 0:
				self.symbols_by_name[table[i].name] = table[i].value
				self.symbols_by_addr[table[i].value] = table[i].name

	def parse_symbol_table_64(self, table, section, string_table):
		strings = self.data.read(string_table.offset, string_table.size)
		for i in range(0, section.size / 24):
			table[i].seek(section.offset + (i * 24))
			table[i].uint32("name_offset")
			table[i].uint8("info")
			table[i].uint8("other")
			table[i].uint16("section")
			table[i].uint64("value")
			table[i].uint64("size")
			table[i].name = self.read_string_table(strings, table[i].name_offset)

			if len(table[i].name) > 0:
				self.symbols_by_name[table[i].name] = table[i].value
				self.symbols_by_addr[table[i].value] = table[i].name

	def parse_reloc_32(self, section):
		for i in range(0, section.size / 8):
			ofs = self.data.read_uint32(section.offset + (i * 8))
			info = self.data.read_uint32(section.offset + (i * 8) + 4)
			sym = info >> 8
			reloc_type = info & 0xff
			if reloc_type == 7: # R_386_JUMP_SLOT
				self.plt[ofs] = self.dynamic_symbol_table[sym].name
				self.symbols_by_name[self.decorate_plt_name(self.dynamic_symbol_table[sym].name)] = ofs
				self.symbols_by_addr[ofs] = self.decorate_plt_name(self.dynamic_symbol_table[sym].name)

	def parse_reloca_32(self, section):
		for i in range(0, section.size / 12):
			ofs = self.data.read_uint32(section.offset + (i * 12))
			info = self.data.read_uint32(section.offset + (i * 12) + 4)
			sym = info >> 8
			reloc_type = info & 0xff
			if reloc_type == 7: # R_386_JUMP_SLOT
				self.plt[ofs] = self.dynamic_symbol_table[sym].name
				self.symbols_by_name[self.decorate_plt_name(self.dynamic_symbol_table[sym].name)] = ofs
				self.symbols_by_addr[ofs] = self.decorate_plt_name(self.dynamic_symbol_table[sym].name)

	def parse_reloc_64(self, section):
		for i in range(0, section.size / 16):
			ofs = self.data.read_uint64(section.offset + (i * 16))
			info = self.data.read_uint64(section.offset + (i * 16) + 8)
			sym = info >> 32
			reloc_type = info & 0xff
			if reloc_type == 7: # R_X86_64_JUMP_SLOT
				self.plt[ofs] = self.dynamic_symbol_table[sym].name
				self.symbols_by_name[self.decorate_plt_name(self.dynamic_symbol_table[sym].name)] = ofs
				self.symbols_by_addr[ofs] = self.decorate_plt_name(self.dynamic_symbol_table[sym].name)

	def parse_reloca_64(self, section):
		for i in range(0, section.size / 24):
			ofs = self.data.read_uint64(section.offset + (i * 24))
			info = self.data.read_uint64(section.offset + (i * 24) + 8)
			sym = info >> 32
			reloc_type = info & 0xff
			if reloc_type == 7: # R_X86_64_JUMP_SLOT
				self.plt[ofs] = self.dynamic_symbol_table[sym].name
				self.symbols_by_name[self.decorate_plt_name(self.dynamic_symbol_table[sym].name)] = ofs
				self.symbols_by_addr[ofs] = self.decorate_plt_name(self.dynamic_symbol_table[sym].name)

	def read(self, ofs, len):
		result = ""
		while len > 0:
			cur = None
			for i in self.program_headers:
				if ((ofs >= i.virtual_addr) and (ofs < (i.virtual_addr + i.memory_size))) and (i.memory_size != 0):
					cur = i
			if cur == None:
				break

			prog_ofs = ofs - cur.virtual_addr
			mem_len = cur.memory_size - prog_ofs
			file_len = cur.file_size - prog_ofs
			if mem_len > len:
				mem_len = len
			if file_len > len:
				file_len = len

			if file_len <= 0:
				result += "\x00" * mem_len
				len -= mem_len
				ofs += mem_len
				continue

			result += self.data.read(cur.offset + prog_ofs, file_len)
			len -= file_len
			ofs += file_len

		return result

	def next_valid_addr(self, ofs):
		result = -1
		for i in self.program_headers:
			if (i.virtual_addr >= ofs) and (i.memory_size != 0) and ((result == -1) or (i.virtual_addr < result)):
				result = i.virtual_addr
		return result

	def get_modification(self, ofs, len):
		result = []
		while len > 0:
			cur = None
			for i in self.program_headers:
				if ((ofs >= i.virtual_addr) and (ofs < (i.virtual_addr + i.memory_size))) and (i.memory_size != 0):
					cur = i
			if cur == None:
				break

			prog_ofs = ofs - cur.virtual_addr
			mem_len = cur.memory_size - prog_ofs
			file_len = cur.file_size - prog_ofs
			if mem_len > len:
				mem_len = len
			if file_len > len:
				file_len = len

			if file_len <= 0:
				result += [DATA_ORIGINAL] * mem_len
				len -= mem_len
				ofs += mem_len
				continue

			result += self.data.get_modification(cur.offset + prog_ofs, file_len)
			len -= file_len
			ofs += file_len

		return result

	def write(self, ofs, data):
		result = 0
		while len(data) > 0:
			cur = None
			for i in self.program_headers:
				if ((ofs >= i.virtual_addr) and (ofs < (i.virtual_addr + i.memory_size))) and (i.memory_size != 0):
					cur = i
			if cur == None:
				break

			prog_ofs = ofs - cur.virtual_addr
			mem_len = cur.memory_size - prog_ofs
			file_len = cur.file_size - prog_ofs
			if mem_len > len:
				mem_len = len
			if file_len > len:
				file_len = len

			if file_len <= 0:
				break

			result += self.data.write(cur.offset + prog_ofs, data[0:file_len])
			data = data[file_len:]
			ofs += file_len

		return result

	def insert(self, ofs, data):
		return 0

	def remove(self, ofs, size):
		return 0

	def notify_data_write(self, data, ofs, contents):
		# Find sections that hold data backed by updated regions of the file
		for i in self.program_headers:
			if ((ofs + len(contents)) > i.offset) and (ofs < (i.offset + i.file_size)) and (i.memory_size != 0):
				# This section has been updated, compute which region has been changed
				from_start = ofs - i.offset
				data_ofs = 0
				length = len(contents)
				if from_start < 0:
					length += from_start
					data_ofs -= from_start
					from_start = 0
				if (from_start + length) > i.file_size:
					length = i.file_size - from_start

				# Notify callbacks
				if length > 0:
					for cb in self.callbacks:
						if hasattr(cb, "notify_data_write"):
							cb.notify_data_write(self, i.virtual_addr + from_start,
								contents[data_ofs:(data_ofs + length)])

	def save(self, filename):
		self.data.save(filename)

	def start(self):
		result = None
		for i in self.program_headers:
			if ((result == None) or (i.virtual_addr < result)) and (i.memory_size != 0):
				result = i.virtual_addr
		return result

	def entry(self):
		return self.header.entry

	def __len__(self):
		max = None
		for i in self.program_headers:
			if ((max == None) or ((i.virtual_addr + i.memory_size) > max)) and (i.memory_size != 0):
				max = i.virtual_addr + i.memory_size
		return max - self.start()

	def is_elf(self):
		return self.data.read(0, 4) == "\x7fELF"

	def architecture(self):
		if self.header.arch == 2:
			return "sparc"
		if self.header.arch == 3:
			return "x86"
		if self.header.arch == 4:
			return "m68000"
		if self.header.arch == 8:
			return "mips"
		if self.header.arch == 15:
			return "pa_risc"
		if self.header.arch == 18:
			return "sparc_32plus"
		if self.header.arch == 20:
			return "ppc"
		if self.header.arch == 40:
			return "arm"
		if self.header.arch == 41:
			return "alpha"
		if self.header.arch == 43:
			return "sparc_v9"
		if self.header.arch == 62:
			return "x86_64"
		return None

	def decorate_plt_name(self, name):
		return name + "@PLT"

	def create_symbol(self, addr, name):
		self.symbols_by_name[name] = addr
		self.symbols_by_addr[addr] = name

	def delete_symbol(self, addr, name):
		if name in self.symbols_by_name:
			del(self.symbols_by_name[name])
		if addr in self.symbols_by_addr:
			del(self.symbols_by_addr[addr])

	def add_callback(self, cb):
		self.callbacks.append(cb)

	def remove_callback(self, cb):
		self.callbacks.remove(cb)

	def is_modified(self):
		return self.data.is_modified()

	def find(self, regex, addr):
		while (addr < self.end()) and (addr != -1):
			data = self.read(addr, 0xfffffffff)
			match = regex.search(data)
			if match != None:
				return match.start() + addr

			addr += len(data)
			addr = self.next_valid_addr(addr)

		return -1

	def has_undo_actions(self):
		return self.data.has_undo_actions()

	def commit_undo(self, before_loc, after_loc):
		self.data.commit_undo(before_loc, after_loc)

	def undo(self):
		self.data.undo()

	def redo(self):
		self.data.redo()


class ElfViewer(HexEditor):
	def __init__(self, data, filename, view, parent):
		view.exe = ElfFile(data)
		super(ElfViewer, self).__init__(view.exe, filename, view, parent)
		view.register_navigate("exe", self, self.navigate)

	def getPriority(data, ext):
		if data.read(0, 4) == "\x7fELF":
			return 25
		return -1
	getPriority = staticmethod(getPriority)

	def getViewName():
		return "ELF viewer"
	getViewName = staticmethod(getViewName)

	def getShortViewName():
		return "ELF"
	getShortViewName = staticmethod(getShortViewName)

	def handlesNavigationType(name):
		return name == "exe"
	handlesNavigationType = staticmethod(handlesNavigationType)

ViewTypes += [ElfViewer]

