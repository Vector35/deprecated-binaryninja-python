# Copyright (c) 2013-2015 Rusty Wagner
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


class PEFile(BinaryAccessor):
	class SectionInfo:
		def __init__(self):
			self.virtual_size = None
			self.virtual_address = None
			self.size_of_raw_data = None
			self.pointer_to_raw_data = None
			self.characteristics = None

	def __init__(self, data):
		self.data = data
		self.valid = False
		self.callbacks = []
		self.symbols_by_name = {}
		self.symbols_by_addr = {}
		if not self.is_pe():
			return

		try:
			self.tree = Structure(self.data)
			self.mz = self.tree.struct("MZ header", "mz")
			self.mz.uint16("magic")
			self.mz.uint16("lastsize")
			self.mz.uint16("nblocks")
			self.mz.uint16("nreloc")
			self.mz.uint16("hdrsize")
			self.mz.uint16("minalloc")
			self.mz.uint16("maxalloc")
			self.mz.uint16("ss")
			self.mz.uint16("sp")
			self.mz.uint16("checksum")
			self.mz.uint16("ip")
			self.mz.uint16("cs")
			self.mz.uint16("relocpos")
			self.mz.uint16("noverlay")
			self.mz.bytes(8, "reserved1")
			self.mz.uint16("oem_id")
			self.mz.uint16("oem_info")
			self.mz.bytes(20, "reserved2")
			self.mz.uint32("pe_offset")

			self.header = self.tree.struct("PE header", "header")
			self.header.seek(self.mz.pe_offset)
			self.header.uint32("magic")
			self.header.uint16("machine")
			self.header.uint16("section_count")
			self.header.uint32("timestamp")
			self.header.uint32("coff_symbol_table")
			self.header.uint32("coff_symbol_count")
			self.header.uint16("optional_header_size")
			self.header.uint16("characteristics")

			self.header.struct("Optional header", "opt")
			self.header.opt.uint16("magic")
			self.header.opt.uint8("major_linker_version")
			self.header.opt.uint8("minor_linker_version")
			self.header.opt.uint32("size_of_code")
			self.header.opt.uint32("size_of_init_data")
			self.header.opt.uint32("size_of_uninit_data")
			self.header.opt.uint32("address_of_entry")
			self.header.opt.uint32("base_of_code")

			if self.header.opt.magic == 0x10b: # 32-bit
				self.bits = 32
				self.header.opt.uint32("base_of_data")
				self.header.opt.uint32("image_base")
				self.header.opt.uint32("section_align")
				self.header.opt.uint32("file_align")
				self.header.opt.uint16("major_os_version")
				self.header.opt.uint16("minor_os_version")
				self.header.opt.uint16("major_image_version")
				self.header.opt.uint16("minor_image_version")
				self.header.opt.uint16("major_subsystem_version")
				self.header.opt.uint16("minor_subsystem_version")
				self.header.opt.uint32("win32_version")
				self.header.opt.uint32("size_of_image")
				self.header.opt.uint32("size_of_headers")
				self.header.opt.uint32("checksum")
				self.header.opt.uint16("subsystem")
				self.header.opt.uint16("dll_characteristics")
				self.header.opt.uint32("size_of_stack_reserve")
				self.header.opt.uint32("size_of_stack_commit")
				self.header.opt.uint32("size_of_heap_reserve")
				self.header.opt.uint32("size_of_heap_commit")
				self.header.opt.uint32("loader_flags")
				self.header.opt.uint32("data_dir_count")
			elif self.header.opt.magic == 0x20b: # 64-bit
				self.bits = 64
				self.header.opt.uint64("image_base")
				self.header.opt.uint32("section_align")
				self.header.opt.uint32("file_align")
				self.header.opt.uint16("major_os_version")
				self.header.opt.uint16("minor_os_version")
				self.header.opt.uint16("major_image_version")
				self.header.opt.uint16("minor_image_version")
				self.header.opt.uint16("major_subsystem_version")
				self.header.opt.uint16("minor_subsystem_version")
				self.header.opt.uint32("win32_version")
				self.header.opt.uint32("size_of_image")
				self.header.opt.uint32("size_of_headers")
				self.header.opt.uint32("checksum")
				self.header.opt.uint16("subsystem")
				self.header.opt.uint16("dll_characteristics")
				self.header.opt.uint64("size_of_stack_reserve")
				self.header.opt.uint64("size_of_stack_commit")
				self.header.opt.uint64("size_of_heap_reserve")
				self.header.opt.uint64("size_of_heap_commit")
				self.header.opt.uint32("loader_flags")
				self.header.opt.uint32("data_dir_count")
			else:
				self.valid = False
				return

			self.image_base = self.header.opt.image_base

			self.data_dirs = self.header.array(self.header.opt.data_dir_count, "data_dirs")
			for i in xrange(0, self.header.opt.data_dir_count):
				self.data_dirs[i].uint32("virtual_address")
				self.data_dirs[i].uint32("size")

			self.sections = []
			header_section_obj = PEFile.SectionInfo()
			header_section_obj.virtual_size = self.header.opt.size_of_headers
			header_section_obj.virtual_address = 0
			header_section_obj.size_of_raw_data = self.header.opt.size_of_headers
			header_section_obj.pointer_to_raw_data = 0
			header_section_obj.characteristics = 0
			self.sections.append(header_section_obj)

			self.tree.array(self.header.section_count, "sections")
			for i in xrange(0, self.header.section_count):
				section = self.tree.sections[i]
				section.seek(self.mz.pe_offset + self.header.optional_header_size + 24 + (i * 40))
				section.bytes(8, "name")
				section.uint32("virtual_size")
				section.uint32("virtual_address")
				section.uint32("size_of_raw_data")
				section.uint32("pointer_to_raw_data")
				section.uint32("pointer_to_relocs")
				section.uint32("pointer_to_line_numbers")
				section.uint16("reloc_count")
				section.uint16("line_number_count")
				section.uint32("characteristics")

				section_obj = PEFile.SectionInfo()
				section_obj.virtual_size = section.virtual_size
				section_obj.virtual_address = section.virtual_address & ~(self.header.opt.section_align - 1)
				section_obj.size_of_raw_data = section.size_of_raw_data
				section_obj.pointer_to_raw_data = section.pointer_to_raw_data & ~(self.header.opt.file_align - 1)
				section_obj.characteristics = section.characteristics
				self.sections.append(section_obj)

			self.symbols_by_name["_start"] = self.entry()
			self.symbols_by_addr[self.entry()] = "_start"

			if self.header.opt.data_dir_count >= 2:
				self.imports = self.tree.array(0, "imports")
				for i in xrange(0, self.data_dirs[1].size / 20):
					if self.read(self.image_base + self.data_dirs[1].virtual_address + (i * 20), 4) == "\0\0\0\0":
						break
					if self.read(self.image_base + self.data_dirs[1].virtual_address + (i * 20) + 16, 4) == "\0\0\0\0":
						break
					self.imports.append()
					dll = self.imports[i]
					dll.seek(self.virtual_address_to_file_offset(self.image_base + self.data_dirs[1].virtual_address) + (i * 20))
					dll.uint32("lookup")
					dll.uint32("timestamp")
					dll.uint32("forward_chain")
					dll.uint32("name")
					dll.uint32("iat")

				for dll in self.imports:
					name = self.read_string(self.image_base + dll.name).split('.')
					if len(name) > 1:
						name = '.'.join(name[0:-1])
					else:
						name = name[0]

					entry_ofs = self.image_base + dll.lookup
					iat_ofs = self.image_base + dll.iat
					while True:
						if self.bits == 32:
							entry = self.read_uint32(entry_ofs)
							is_ordinal = (entry & 0x80000000) != 0
							entry &= 0x7fffffff
						else:
							entry = self.read_uint64(entry_ofs)
							is_ordinal = (entry & 0x8000000000000000) != 0
							entry &= 0x7fffffffffffffff

						if (not is_ordinal) and (entry == 0):
							break

						if is_ordinal:
							func = name + "!Ordinal%d" % (entry & 0xffff)
						else:
							func = name + "!" + self.read_string(self.image_base + entry + 2)

						self.symbols_by_name[func] = iat_ofs
						self.symbols_by_addr[iat_ofs] = func

						entry_ofs += self.bits / 8
						iat_ofs += self.bits / 8

			if (self.header.opt.data_dir_count >= 1) and (self.data_dirs[0].size >= 40):
				self.exports = self.tree.struct("Export directory", "exports")
				self.exports.seek(self.virtual_address_to_file_offset(self.image_base + self.data_dirs[0].virtual_address))
				self.exports.uint32("characteristics")
				self.exports.uint32("timestamp")
				self.exports.uint16("major_version")
				self.exports.uint16("minor_version")
				self.exports.uint32("dll_name")
				self.exports.uint32("base")
				self.exports.uint32("function_count")
				self.exports.uint32("name_count")
				self.exports.uint32("address_of_functions")
				self.exports.uint32("address_of_names")
				self.exports.uint32("address_of_name_ordinals")

				self.exports.array(self.exports.function_count, "functions")
				for i in xrange(0, self.exports.function_count):
					self.exports.functions[i].seek(self.virtual_address_to_file_offset(self.image_base + self.exports.address_of_functions) + (i * 4))
					self.exports.functions[i].uint32("address")

				self.exports.array(self.exports.name_count, "names")
				for i in xrange(0, self.exports.name_count):
					self.exports.names[i].seek(self.virtual_address_to_file_offset(self.image_base + self.exports.address_of_names) + (i * 4))
					self.exports.names[i].uint32("address_of_name")

				self.exports.array(self.exports.name_count, "name_ordinals")
				for i in xrange(0, self.exports.name_count):
					self.exports.name_ordinals[i].seek(self.virtual_address_to_file_offset(self.image_base + self.exports.address_of_name_ordinals) + (i * 2))
					self.exports.name_ordinals[i].uint16("ordinal")

				for i in xrange(0, self.exports.name_count):
					function_index = self.exports.name_ordinals[i].ordinal - self.exports.base
					address = self.image_base + self.exports.functions[function_index].address
					name = self.read_string(self.image_base + self.exports.names[i].address_of_name)

					self.symbols_by_addr[address] = name
					self.symbols_by_name[name] = address

			self.tree.complete()
			self.valid = True
		except:
			self.valid = False

		if self.valid:
			self.data.add_callback(self)

	def read_string(self, addr):
		result = ""
		while True:
			ch = self.read(addr, 1)
			addr += 1
			if (len(ch) == 0) or (ch == '\0'):
				break
			result += ch
		return result

	def virtual_address_to_file_offset(self, addr):
		for i in self.sections:
			if ((addr >= (self.image_base + i.virtual_address)) and (addr < (self.image_base + i.virtual_address + i.virtual_size))) and (i.virtual_size != 0):
				cur = i
		if cur == None:
			return None
		ofs = addr - (self.image_base + cur.virtual_address)
		return cur.pointer_to_raw_data + ofs

	def read(self, ofs, len):
		result = ""
		while len > 0:
			cur = None
			for i in self.sections:
				if ((ofs >= (self.image_base + i.virtual_address)) and (ofs < (self.image_base + i.virtual_address + i.virtual_size))) and (i.virtual_size != 0):
					cur = i
			if cur == None:
				break

			prog_ofs = ofs - (self.image_base + cur.virtual_address)
			mem_len = cur.virtual_size - prog_ofs
			file_len = cur.size_of_raw_data - prog_ofs
			if mem_len > len:
				mem_len = len
			if file_len > len:
				file_len = len

			if file_len <= 0:
				result += "\x00" * mem_len
				len -= mem_len
				ofs += mem_len
				continue

			result += self.data.read(cur.pointer_to_raw_data + prog_ofs, file_len)
			len -= file_len
			ofs += file_len

		return result

	def next_valid_addr(self, ofs):
		result = -1
		for i in self.sections:
			if ((self.image_base + i.virtual_address) >= ofs) and (i.virtual_size != 0) and ((result == -1) or ((self.image_base + i.virtual_address) < result)):
				result = self.image_base + i.virtual_address
		return result

	def get_modification(self, ofs, len):
		result = []
		while len > 0:
			cur = None
			for i in self.sections:
				if ((ofs >= (self.image_base + i.virtual_address)) and (ofs < (self.image_base + i.virtual_address + i.virtual_size))) and (i.virtual_size != 0):
					cur = i
			if cur == None:
				break

			prog_ofs = ofs - (self.image_base + cur.virtual_address)
			mem_len = cur.virtual_size - prog_ofs
			file_len = cur.size_of_raw_data - prog_ofs
			if mem_len > len:
				mem_len = len
			if file_len > len:
				file_len = len

			if file_len <= 0:
				result += [DATA_ORIGINAL] * mem_len
				len -= mem_len
				ofs += mem_len
				continue

			result += self.data.get_modification(cur.pointer_to_raw_data + prog_ofs, file_len)
			len -= file_len
			ofs += file_len

		return result

	def write(self, ofs, data):
		result = 0
		while len(data) > 0:
			cur = None
			for i in self.sections:
				if ((ofs >= (self.image_base + i.virtual_address)) and (ofs < (self.image_base + i.virtual_address + i.virtual_size))) and (i.virtual_size != 0):
					cur = i
			if cur == None:
				break

			prog_ofs = ofs - (self.image_base + cur.virtual_address)
			mem_len = cur.virtual_size - prog_ofs
			file_len = cur.size_of_raw_data - prog_ofs
			if mem_len > len:
				mem_len = len
			if file_len > len:
				file_len = len

			if file_len <= 0:
				break

			result += self.data.write(cur.pointer_to_raw_data + prog_ofs, data[0:file_len])
			data = data[file_len:]
			ofs += file_len

		return result

	def insert(self, ofs, data):
		return 0

	def remove(self, ofs, size):
		return 0

	def notify_data_write(self, data, ofs, contents):
		# Find sections that hold data backed by updated regions of the file
		for i in self.sections:
			if ((ofs + len(contents)) > i.pointer_to_raw_data) and (ofs < (i.pointer_to_raw_data + i.size_of_raw_data)) and (i.virtual_size != 0):
				# This section has been updated, compute which region has been changed
				from_start = ofs - i.pointer_to_raw_data
				data_ofs = 0
				length = len(contents)
				if from_start < 0:
					length += from_start
					data_ofs -= from_start
					from_start = 0
				if (from_start + length) > i.size_of_raw_data:
					length = i.size_of_raw_data - from_start

				# Notify callbacks
				if length > 0:
					for cb in self.callbacks:
						if hasattr(cb, "notify_data_write"):
							cb.notify_data_write(self, self.image_base + i.virtual_address + from_start,
								contents[data_ofs:(data_ofs + length)])

	def save(self, filename):
		self.data.save(filename)

	def start(self):
		return self.image_base

	def entry(self):
		return self.image_base + self.header.opt.address_of_entry

	def __len__(self):
		max = None
		for i in self.sections:
			if ((max == None) or ((self.image_base + i.virtual_address + i.virtual_size) > max)) and (i.virtual_size != 0):
				max = self.image_base + i.virtual_address + i.virtual_size
		return max - self.start()

	def is_pe(self):
		if self.data.read(0, 2) != "MZ":
			return False
		ofs = self.data.read(0x3c, 4)
		if len(ofs) != 4:
			return False
		ofs = struct.unpack("<I", ofs)[0]
		if self.data.read(ofs, 4) != "PE\0\0":
			return False
		magic = self.data.read(ofs + 24, 2)
		if len(magic) != 2:
			return False
		magic = struct.unpack("<H", magic)[0]
		return (magic == 0x10b) or (magic == 0x20b)

	def architecture(self):
		if self.header.machine == 0x14c:
			return "x86"
		if self.header.machine == 0x8664:
			return "x86_64"
		if self.header.machine == 0x166:
			return "mips"
		if self.header.machine == 0x266:
			return "mips16"
		if self.header.machine == 0x366:
			return "mips"
		if self.header.machine == 0x466:
			return "mips16"
		if self.header.machine == 0x1f0:
			return "ppc"
		if self.header.machine == 0x1f1:
			return "ppc"
		if self.header.machine == 0x1c0:
			return "arm"
		if self.header.machine == 0x1c2:
			return "thumb"
		if self.header.machine == 0x1c4:
			return "thumb"
		if self.header.machine == 0xaa64:
			return "arm64"
		if self.header.machine == 0x200:
			return "ia64"
		return None

	def decorate_plt_name(self, name):
		return name + "@IAT"

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


class PEViewer(HexEditor):
	def __init__(self, data, filename, view, parent):
		view.exe = PEFile(data)
		super(PEViewer, self).__init__(view.exe, filename, view, parent)
		view.register_navigate("exe", self, self.navigate)

	def getPriority(data, ext):
		if data.read(0, 2) != "MZ":
			return -1
		ofs = data.read(0x3c, 4)
		if len(ofs) != 4:
			return -1
		ofs = struct.unpack("<I", ofs)[0]
		if data.read(ofs, 4) != "PE\0\0":
			return -1
		magic = data.read(ofs + 24, 2)
		if len(magic) != 2:
			return -1
		magic = struct.unpack("<H", magic)[0]
		if (magic == 0x10b) or (magic == 0x20b):
			return 25
		return -1
	getPriority = staticmethod(getPriority)

	def getViewName():
		return "PE viewer"
	getViewName = staticmethod(getViewName)

	def getShortViewName():
		return "PE"
	getShortViewName = staticmethod(getShortViewName)

	def handlesNavigationType(name):
		return name == "exe"
	handlesNavigationType = staticmethod(handlesNavigationType)

ViewTypes += [PEViewer]

