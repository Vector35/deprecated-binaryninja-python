# Copyright (c) 2012-2015 Rusty Wagner
# All rights reserved.

# Redistribution and use in source and binary forms are permitted
# provided that the above copyright notice and this paragraph are
# duplicated in all such forms and that any documentation,
# advertising materials, and other materials related to such
# distribution and use acknowledge that the software was developed
# by the Rusty Wagner. The name of the
# Rusty Wagner may not be used to endorse or promote products derived
# from this software without specific prior written permission.
# THIS SOFTWARE IS PROVIDED ``AS IS'' AND WITHOUT ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, WITHOUT LIMITATION, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.

from BinaryData import *
from Structure import *
from HexEditor import *
from View import *


class MachOFile(BinaryAccessor):
	def __init__(self, data):
		self.data = data
		self.valid = False
		self.callbacks = []
		self.symbols_by_name = {}
		self.symbols_by_addr = {}
		self.plt = {}
		if not self.is_macho():
			return

		try:
			self.tree = Structure(self.data)
			self.header = self.tree.struct("Mach-O header", "header")

			self.header.uint32_le("magic")
			if (self.header.magic == 0xfeedface) or (self.header.magic == 0xfeedfacf):
				self.header.uint32_le("cputype")
				self.header.uint32_le("cpusubtype")
				self.header.uint32_le("filetype")
				self.header.uint32_le("cmds")
				self.header.uint32_le("cmdsize")
				self.header.uint32_le("flags")
				if self.header.magic == 0xfeedfacf:
					self.header.uint32_le("reserved")
					self.bits = 64
				else:
					self.bits = 32
				self.big_endian = False
			elif (self.header.magic == 0xcefaedfe) or (self.header.magic == 0xcffaedfe):
				self.header.uint32_be("cputype")
				self.header.uint32_be("cpusubtype")
				self.header.uint32_be("filetype")
				self.header.uint32_be("cmds")
				self.header.uint32_be("cmdsize")
				self.header.uint32_be("flags")
				if self.header.magic == 0xcffaedfe:
					self.header.uint32_be("reserved")
					self.bits = 64
				else:
					self.bits = 32
				self.big_endian = True

			self.symbol_table = None
			self.dynamic_symbol_table = None

			# Parse loader commands
			self.commands = self.tree.array(self.header.cmds, "commands")
			self.segments = []
			self.sections = []
			offset = self.header.getSize()
			for i in xrange(0, self.header.cmds):
				cmd = self.commands[i]
				cmd.seek(offset)
				if self.big_endian:
					cmd.uint32_be("cmd")
					cmd.uint32_be("size")
				else:
					cmd.uint32_le("cmd")
					cmd.uint32_le("size")

				if cmd.cmd == 1: # SEGMENT
					cmd.bytes(16, "name")
					if self.big_endian:
						cmd.uint32_be("vmaddr")
						cmd.uint32_be("vmsize")
						cmd.uint32_be("fileoff")
						cmd.uint32_be("filesize")
						cmd.uint32_be("maxprot")
						cmd.uint32_be("initprot")
						cmd.uint32_be("nsects")
						cmd.uint32_be("flags")
					else:
						cmd.uint32_le("vmaddr")
						cmd.uint32_le("vmsize")
						cmd.uint32_le("fileoff")
						cmd.uint32_le("filesize")
						cmd.uint32_le("maxprot")
						cmd.uint32_le("initprot")
						cmd.uint32_le("nsects")
						cmd.uint32_le("flags")

					if cmd.initprot != 0: # Ignore __PAGE_ZERO or anything like it
						self.segments.append(cmd)

					cmd.array(cmd.nsects, "sections")
					for i in xrange(0, cmd.nsects):
						section = cmd.sections[i]
						section.bytes(16, "name")
						section.bytes(16, "segment")
						if self.big_endian:
							section.uint32_be("addr")
							section.uint32_be("size")
							section.uint32_be("offset")
							section.uint32_be("align")
							section.uint32_be("reloff")
							section.uint32_be("nreloc")
							section.uint32_be("flags")
							section.uint32_be("reserved1")
							section.uint32_be("reserved2")
						else:
							section.uint32_le("addr")
							section.uint32_le("size")
							section.uint32_le("offset")
							section.uint32_le("align")
							section.uint32_le("reloff")
							section.uint32_le("nreloc")
							section.uint32_le("flags")
							section.uint32_le("reserved1")
							section.uint32_le("reserved2")
						self.sections.append(section)

					for i in xrange(0, cmd.nsects):
						section = cmd.sections[i]
						section.array(section.nreloc, "relocs")
						for j in xrange(0, section.nreloc):
							reloc = section.relocs[j]
							reloc.seek(section.reloff + (j * 8))
							if self.big_endian:
								reloc.uint32_be("addr")
								reloc.uint32_be("value")
							else:
								reloc.uint32_le("addr")
								reloc.uint32_le("value")
				elif cmd.cmd == 25: # SEGMENT_64
					cmd.bytes(16, "name")
					if self.big_endian:
						cmd.uint64_be("vmaddr")
						cmd.uint64_be("vmsize")
						cmd.uint64_be("fileoff")
						cmd.uint64_be("filesize")
						cmd.uint32_be("maxprot")
						cmd.uint32_be("initprot")
						cmd.uint32_be("nsects")
						cmd.uint32_be("flags")
					else:
						cmd.uint64_le("vmaddr")
						cmd.uint64_le("vmsize")
						cmd.uint64_le("fileoff")
						cmd.uint64_le("filesize")
						cmd.uint32_le("maxprot")
						cmd.uint32_le("initprot")
						cmd.uint32_le("nsects")
						cmd.uint32_le("flags")

					if cmd.initprot != 0: # Ignore __PAGE_ZERO or anything like it
						self.segments.append(cmd)

					cmd.array(cmd.nsects, "sections")
					for i in xrange(0, cmd.nsects):
						section = cmd.sections[i]
						section.bytes(16, "name")
						section.bytes(16, "segment")
						if self.big_endian:
							section.uint64_be("addr")
							section.uint64_be("size")
							section.uint32_be("offset")
							section.uint32_be("align")
							section.uint32_be("reloff")
							section.uint32_be("nreloc")
							section.uint32_be("flags")
							section.uint32_be("reserved1")
							section.uint32_be("reserved2")
							section.uint32_be("reserved3")
						else:
							section.uint64_le("addr")
							section.uint64_le("size")
							section.uint32_le("offset")
							section.uint32_le("align")
							section.uint32_le("reloff")
							section.uint32_le("nreloc")
							section.uint32_le("flags")
							section.uint32_le("reserved1")
							section.uint32_le("reserved2")
							section.uint32_le("reserved3")
						self.sections.append(section)

					for i in xrange(0, cmd.nsects):
						section = cmd.sections[i]
						section.array(section.nreloc, "relocs")
						for j in xrange(0, section.nreloc):
							reloc = section.relocs[j]
							reloc.seek(section.reloff + (j * 8))
							if self.big_endian:
								reloc.uint32_be("addr")
								reloc.uint32_be("value")
							else:
								reloc.uint32_le("addr")
								reloc.uint32_le("value")
				elif cmd.cmd == 5: # UNIX_THREAD
					if self.header.cputype == 7: # x86
						cmd.uint32_le("flavor")
						cmd.uint32_le("count")
						for reg in ["eax", "ebx", "ecx", "edx", "edi", "esi", "ebp", "esp", "ss", "eflags",
							"eip", "cs", "ds", "es", "fs", "gs"]:
							cmd.uint32_le(reg)
						self.entry_addr = cmd.eip
					elif self.header.cputype == 0x01000007: # x86_64
						cmd.uint32_le("flavor")
						cmd.uint32_le("count")
						for reg in ["rax", "rbx", "rcx", "rdx", "rdi", "rsi", "rbp", "rsp", "r8", "r9",
								"r10", "r11", "r12", "r13", "r14", "r15", "rip", "rflags", "cs", "fs", "gs"]:
							cmd.uint64_le(reg)
						self.entry_addr = cmd.rip
					elif self.header.cputype == 18: # PPC32
						cmd.uint32_be("flavor")
						cmd.uint32_be("count")
						for reg in ["srr0", "srr1"] + ["r%d" % i for i in xrange(0, 32)] + ["cr", "xer",
							"lr", "ctr", "mq", "vrsave"]:
							cmd.uint32_be(reg)
						self.entry_addr = cmd.srr0
					elif self.header.cputype == 0x01000012: # PPC64
						cmd.uint32_be("flavor")
						cmd.uint32_be("count")
						for reg in ["srr0", "srr1"] + ["r%d" % i for i in xrange(0, 32)] + ["cr", "xer",
							"lr", "ctr", "mq", "vrsave"]:
							cmd.uint64_be(reg)
						self.entry_addr = cmd.srr0
					elif self.header.cputype == 12: # ARM
						cmd.uint32_le("flavor")
						cmd.uint32_le("count")
						for reg in ["r%d" % i for i in xrange(0, 13)] + ["sp", "lr", "pc", "cpsr"]:
							cmd.uint32_le(reg)
						self.entry_addr = cmd.pc
				elif cmd.cmd == 2: # SYMTAB
					if self.big_endian:
						cmd.uint32_be("symoff")
						cmd.uint32_be("nsyms")
						cmd.uint32_be("stroff")
						cmd.uint32_be("strsize")
					else:
						cmd.uint32_le("symoff")
						cmd.uint32_le("nsyms")
						cmd.uint32_le("stroff")
						cmd.uint32_le("strsize")

					self.symbol_table = self.tree.array(cmd.nsyms, "symtab")
					strings = self.data.read(cmd.stroff, cmd.strsize)

					sym_offset = cmd.symoff
					for j in xrange(0, cmd.nsyms):
						entry = self.symbol_table[j]
						entry.seek(sym_offset)

						if self.big_endian:
							entry.uint32_be("strx")
							entry.uint8("type")
							entry.uint8("sect")
							entry.uint16_be("desc")
							if self.bits == 32:
								entry.uint32_be("value")
							else:
								entry.uint64_be("value")
						else:
							entry.uint32_le("strx")
							entry.uint8("type")
							entry.uint8("sect")
							entry.uint16_le("desc")
							if self.bits == 32:
								entry.uint32_le("value")
							else:
								entry.uint64_le("value")

						str_end = strings.find("\x00", entry.strx)
						entry.name = strings[entry.strx:str_end]

						if self.bits == 32:
							sym_offset += 12
						else:
							sym_offset += 16
				elif cmd.cmd == 11: # DYSYMTAB
					if self.big_endian:
						cmd.uint32_be("ilocalsym")
						cmd.uint32_be("nlocalsym")
						cmd.uint32_be("iextdefsym")
						cmd.uint32_be("nextdefsym")
						cmd.uint32_be("iundefsym")
						cmd.uint32_be("nundefsym")
						cmd.uint32_be("tocoff")
						cmd.uint32_be("ntoc")
						cmd.uint32_be("modtaboff")
						cmd.uint32_be("nmodtab")
						cmd.uint32_be("extrefsymoff")
						cmd.uint32_be("nextrefsyms")
						cmd.uint32_be("indirectsymoff")
						cmd.uint32_be("nindirectsyms")
						cmd.uint32_be("extreloff")
						cmd.uint32_be("nextrel")
						cmd.uint32_be("locreloff")
						cmd.uint32_be("nlocrel")
					else:
						cmd.uint32_le("ilocalsym")
						cmd.uint32_le("nlocalsym")
						cmd.uint32_le("iextdefsym")
						cmd.uint32_le("nextdefsym")
						cmd.uint32_le("iundefsym")
						cmd.uint32_le("nundefsym")
						cmd.uint32_le("tocoff")
						cmd.uint32_le("ntoc")
						cmd.uint32_le("modtaboff")
						cmd.uint32_le("nmodtab")
						cmd.uint32_le("extrefsymoff")
						cmd.uint32_le("nextrefsyms")
						cmd.uint32_le("indirectsymoff")
						cmd.uint32_le("nindirectsyms")
						cmd.uint32_le("extreloff")
						cmd.uint32_le("nextrel")
						cmd.uint32_le("locreloff")
						cmd.uint32_le("nlocrel")
				elif (cmd.cmd & 0x7fffffff) == 0x22: # DYLD_INFO
					self.dynamic_symbol_table = cmd
					if self.big_endian:
						cmd.uint32_be("rebaseoff")
						cmd.uint32_be("rebasesize")
						cmd.uint32_be("bindoff")
						cmd.uint32_be("bindsize")
						cmd.uint32_be("weakbindoff")
						cmd.uint32_be("weakbindsize")
						cmd.uint32_be("lazybindoff")
						cmd.uint32_be("lazybindsize")
						cmd.uint32_be("exportoff")
						cmd.uint32_be("exportsize")
					else:
						cmd.uint32_le("rebaseoff")
						cmd.uint32_le("rebasesize")
						cmd.uint32_le("bindoff")
						cmd.uint32_le("bindsize")
						cmd.uint32_le("weakbindoff")
						cmd.uint32_le("weakbindsize")
						cmd.uint32_le("lazybindoff")
						cmd.uint32_le("lazybindsize")
						cmd.uint32_le("exportoff")
						cmd.uint32_le("exportsize")

				offset += cmd.size

			# Add symbols from symbol table
			if self.symbol_table:
				for i in xrange(0, len(self.symbol_table)):
					symbol = self.symbol_table[i]

					# Only use symbols that are within a section
					if ((symbol.type & 0xe) == 0xe) and (symbol.sect <= len(self.sections)):
						self.create_symbol(symbol.value, symbol.name)

			# If there is a DYLD_INFO section, parse it and add PLT entries
			if self.dynamic_symbol_table:
				self.parse_dynamic_tables([[self.dynamic_symbol_table.bindoff, self.dynamic_symbol_table.bindsize],
					[self.dynamic_symbol_table.lazybindoff, self.dynamic_symbol_table.lazybindsize]])

			self.tree.complete()
			self.valid = True
		except:
			self.valid = False
			raise

		if self.valid:
			self.data.add_callback(self)

	def read_leb128(self, data, ofs):
		value = 0
		shift = 0
		while ofs < len(data):
			cur = ord(data[ofs])
			ofs += 1
			value |= (cur & 0x7f) << shift
			shift += 7
			if (cur & 0x80) == 0:
				break
		return value, ofs

	def parse_dynamic_tables(self, tables):
		# Interpret DYLD_INFO instructions (not documented by Apple)
		# http://networkpx.blogspot.com/2009/09/about-lcdyldinfoonly-command.html
		ordinal = 0
		segment = 0
		offset = 0
		sym_type = 0
		name = ""

		for table in tables:
			offset = table[0]
			size = table[1]
			opcodes = self.data.read(offset, size)
			i = 0
			while i < len(opcodes):
				opcode = ord(opcodes[i])
				i += 1
				if (opcode >> 4) == 0:
					continue
				elif (opcode >> 4) == 1:
					ordinal = opcode & 0xf
				elif (opcode >> 4) == 2:
					ordinal, i = self.read_leb128(opcodes, i)
				elif (opcode >> 4) == 3:
					ordinal = -(opcode & 0xf)
				elif (opcode >> 4) == 4:
					name = ""
					while i < len(opcodes):
						ch = opcodes[i]
						i += 1
						if ch == '\x00':
							break
						name += ch
				elif (opcode >> 4) == 5:
					sym_type = opcode & 0xf
				elif (opcode >> 4) == 6:
					addend, i = self.read_leb128(opcodes, i)
				elif (opcode >> 4) == 7:
					segment = opcode & 0xf
					offset, i = self.read_leb128(opcodes, i)
				elif (opcode >> 4) == 8:
					rel, i = self.read_leb128(opcodes, i)
					offset += rel
				elif (opcode >> 4) >= 9:
					if (sym_type == 1) and (segment <= len(self.segments)):
						# Add pointer type entries to the PLT
						addr = self.segments[segment - 1].vmaddr + offset
						self.plt[addr] = name
						self.create_symbol(addr, self.decorate_plt_name(name))
					if self.bits == 32:
						offset += 4
					else:
						offset += 8
					if (opcode >> 4) == 10:
						rel, i = self.read_leb128(opcodes, i)
						offset += rel
					elif (opcode >> 4) == 11:
						offset += (opcode & 0xf) * 4
					elif (opcode >> 4) == 12:
						count, i = self.read_leb128(opcodes, i)
						skip, i = self.read_leb128(opcodes, i)

	def read(self, ofs, len):
		result = ""
		while len > 0:
			cur = None
			for i in self.segments:
				if ((ofs >= i.vmaddr) and (ofs < (i.vmaddr + i.vmsize))) and (i.vmsize != 0):
					cur = i
			if cur == None:
				break

			prog_ofs = ofs - cur.vmaddr
			mem_len = cur.vmsize - prog_ofs
			file_len = cur.filesize - prog_ofs
			if mem_len > len:
				mem_len = len
			if file_len > len:
				file_len = len

			if file_len <= 0:
				result += "\x00" * mem_len
				len -= mem_len
				ofs += mem_len
				continue

			result += self.data.read(cur.fileoff + prog_ofs, file_len)
			len -= file_len
			ofs += file_len

		return result

	def next_valid_addr(self, ofs):
		result = -1
		for i in self.segments:
			if (i.vmaddr >= ofs) and (i.vmsize != 0) and ((result == -1) or (i.vmaddr < result)):
				result = i.vmaddr
		return result

	def get_modification(self, ofs, len):
		result = []
		while len > 0:
			cur = None
			for i in self.segments:
				if ((ofs >= i.vmaddr) and (ofs < (i.vmaddr + i.vmsize))) and (i.vmsize != 0):
					cur = i
			if cur == None:
				break

			prog_ofs = ofs - cur.vmaddr
			mem_len = cur.vmsize - prog_ofs
			file_len = cur.filesize - prog_ofs
			if mem_len > len:
				mem_len = len
			if file_len > len:
				file_len = len

			if file_len <= 0:
				result += [DATA_ORIGINAL] * mem_len
				len -= mem_len
				ofs += mem_len
				continue

			result += self.data.get_modification(cur.fileoff + prog_ofs, file_len)
			len -= file_len
			ofs += file_len

		return result

	def write(self, ofs, data):
		result = 0
		while len(data) > 0:
			cur = None
			for i in self.segments:
				if ((ofs >= i.vmaddr) and (ofs < (i.vmaddr + i.vmsize))) and (i.vmsize != 0):
					cur = i
			if cur == None:
				break

			prog_ofs = ofs - cur.vmaddr
			mem_len = cur.vmsize - prog_ofs
			file_len = cur.filesize - prog_ofs
			if mem_len > len:
				mem_len = len
			if file_len > len:
				file_len = len

			if file_len <= 0:
				break

			result += self.data.write(cur.fileoff + prog_ofs, data[0:file_len])
			data = data[file_len:]
			ofs += file_len

		return result

	def insert(self, ofs, data):
		return 0

	def remove(self, ofs, size):
		return 0

	def notify_data_write(self, data, ofs, contents):
		# Find sections that hold data backed by updated regions of the file
		for i in self.segments:
			if ((ofs + len(contents)) > i.fileoff) and (ofs < (i.fileoff + i.filesize)) and (i.vmsize != 0):
				# This section has been updated, compute which region has been changed
				from_start = ofs - i.fileoff
				data_ofs = 0
				length = len(contents)
				if from_start < 0:
					length += from_start
					data_ofs -= from_start
					from_start = 0
				if (from_start + length) > i.filesize:
					length = i.filesize - from_start

				# Notify callbacks
				if length > 0:
					for cb in self.callbacks:
						if hasattr(cb, "notify_data_write"):
							cb.notify_data_write(self, i.vmaddr + from_start,
								contents[data_ofs:(data_ofs + length)])

	def save(self, filename):
		self.data.save(filename)

	def start(self):
		result = None
		for i in self.segments:
			if ((result == None) or (i.vmaddr < result)) and (i.vmsize != 0):
				result = i.vmaddr
		return result

	def entry(self):
		if not hasattr(self, "entry_addr"):
			return self.start()
		return self.entry_addr

	def __len__(self):
		max = None
		for i in self.segments:
			if ((max == None) or ((i.vmaddr + i.vmsize) > max)) and (i.vmsize != 0):
				max = i.vmaddr + i.vmsize
		return max - self.start()

	def is_macho(self):
		if self.data.read(0, 4) == "\xfe\xed\xfa\xce":
			return True
		if self.data.read(0, 4) == "\xfe\xed\xfa\xcf":
			return True
		if self.data.read(0, 4) == "\xce\xfa\xed\xfe":
			return True
		if self.data.read(0, 4) == "\xcf\xfa\xed\xfe":
			return True
		return False

	def architecture(self):
		if self.header.cputype == 7:
			return "x86"
		if self.header.cputype == 0x01000007:
			return "x86_64"
		if self.header.cputype == 12:
			return "arm"
		if self.header.cputype == 18:
			return "ppc"
		if self.header.cputype == 0x01000012:
			return "ppc"
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


class MachOViewer(HexEditor):
	def __init__(self, data, filename, view, parent):
		view.exe = MachOFile(data)
		super(MachOViewer, self).__init__(view.exe, filename, view, parent)
		view.register_navigate("exe", self, self.navigate)

	def getPriority(data, ext):
		if data.read(0, 4) == "\xfe\xed\xfa\xce":
			return 25
		if data.read(0, 4) == "\xfe\xed\xfa\xcf":
			return 25
		if data.read(0, 4) == "\xce\xfa\xed\xfe":
			return 25
		if data.read(0, 4) == "\xcf\xfa\xed\xfe":
			return 25
		return -1
	getPriority = staticmethod(getPriority)

	def getViewName():
		return "Mach-O viewer"
	getViewName = staticmethod(getViewName)

	def getShortViewName():
		return "Mach-O"
	getShortViewName = staticmethod(getShortViewName)

	def handlesNavigationType(name):
		return name == "exe"
	handlesNavigationType = staticmethod(handlesNavigationType)

ViewTypes += [MachOViewer]

