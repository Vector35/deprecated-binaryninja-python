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
import time
import struct
import X86
import PPC
import Arm
from ElfFile import *
from PEFile import *
from MachOFile import *


ExeFormats = [ElfFile, PEFile, MachOFile]


class InstructionText:
	def __init__(self):
		self.lines = []
		self.tokens = []

class X86Instruction:
	def __init__(self, opcode, addr, disasm, addr_size):
		self.opcode = opcode
		self.addr = addr
		self.disasm = disasm
		self.addr_size = addr_size
		self.plt = None
		self.text = InstructionText()

		if ((disasm.operation == "jmpn") or self.isCall() or self.isConditionalBranch()) and (disasm.operands[0].operand == "imm"):
			self.target = disasm.operands[0].immediate
		else:
			self.target = None

	def isConditionalBranch(self):
		return self.disasm.operation in ["jo", "jno", "jb", "jae", "je", "jne", "jbe", "ja", "js", "jns",
			"jpe", "jpo", "jl", "jge", "jle", "jg", "jcxz", "jecxz", "jrcxz", "loop"]

	def isLocalJump(self):
		if self.disasm.operation == "jmpn":
			return True
		if self.isConditionalBranch():
			return True
		return False

	def isCall(self):
		if self.disasm.operation == "calln":
			return True
		if self.disasm.operation == "callf":
			return True
		return False

	def isBlockEnding(self):
		if self.disasm.operation in ["jmpn", "jmpf", "retn", "retf"]:
			return True
		if self.isConditionalBranch():
			return True
		if self.disasm.operation == "hlt":
			return True
		return False

	def isValid(self):
		return self.disasm.operation != None

	def length(self):
		return self.disasm.length

	def format_text(self, block, options):
		old_lines = []
		old_tokens = []
		self.text.lines = []
		self.text.tokens = []

		line = []
		tokens = []
		x = 0
		instr = self.disasm

		if "address" in options:
			string = "%.8x   " % self.addr
			line += [[string, QColor(0, 0, 128)]]
			x += len(string)

		if instr.operation == None:
			line += [["??", Qt.black]]
			self.text.lines += [line]
			self.text.tokens += [tokens]
			return (old_lines != self.text.lines) or (old_tokens != self.text.tokens)

		result = ""
		operation = ""
		if instr.flags & X86.FLAG_LOCK:
			operation += "lock "
		if instr.flags & X86.FLAG_ANY_REP:
			operation += "rep"
			if instr.flags & X86.FLAG_REPNE:
				operation += "ne"
			elif instr.flags & X86.FLAG_REPE:
				operation += "e"
			operation += " "
		operation += instr.operation
		if len(operation) < 7:
			operation += " " * (7 - len(operation))
		result += operation + " "

		for j in range(0, len(instr.operands)):
			if j != 0:
				result += ", "
			if instr.operands[j].operand == "imm":
				value = instr.operands[j].immediate & ((1 << (instr.operands[j].size * 8)) - 1)
				numfmt = "0x%%.%dx" % (instr.operands[j].size * 2)
				string = numfmt % value
				if (instr.operands[j].size == self.addr_size) and (block.analysis.functions.has_key(value)):
					# Pointer to existing function
					func = block.analysis.functions[value]
					string = func.name
					if func.plt:
						color = QColor(192, 0, 192)
					else:
						color = QColor(0, 0, 192)
					if len(result) > 0:
						line += [[result, Qt.black]]
						x += len(result)
						result = ""
					line += [[string, color]]
					tokens += [[x, len(string), "ptr", value, string]]
					x += len(string)
				elif (instr.operands[j].size == self.addr_size) and (value >= block.exe.start()) and (value < block.exe.end()) and (not self.isLocalJump()):
					# Pointer within module
					if len(result) > 0:
						line += [[result, Qt.black]]
						x += len(result)
						result = ""
					if value in block.exe.symbols_by_addr:
						string = block.exe.symbols_by_addr[value]
					line += [[string, QColor(0, 0, 192)]]
					tokens += [[x, len(string), "ptr", value, string]]
					x += len(string)
				else:
					result += string
			elif instr.operands[j].operand == "mem":
				plus = False
				result += X86.get_size_string(instr.operands[j].size)
				if (instr.segment != None) or (instr.operands[j].segment == "es"):
					result += instr.operands[j].segment + ":"
				result += '['
				if instr.operands[j].components[0] != None:
					tokens += [[x + len(result), len(instr.operands[j].components[0]), "reg", instr.operands[j].components[0]]]
					result += instr.operands[j].components[0]
					plus = True
				if instr.operands[j].components[1] != None:
					if plus:
						tokens += [[x + len(result) + 1, len(instr.operands[j].components[1]), "reg", instr.operands[j].components[1]]]
					else:
						tokens += [[x + len(result), len(instr.operands[j].components[1]), "reg", instr.operands[j].components[1]]]
					result += X86.get_operand_string(instr.operands[j].components[1],
						instr.operands[j].scale, plus)
					plus = True
				if (instr.operands[j].immediate != 0) or ((instr.operands[j].components[0] == None) and (instr.operands[j].components[1] == None)):
					if plus and (instr.operands[j].immediate >= -0x80) and (instr.operands[j].immediate < 0):
						result += '-'
						result += "0x%.2x" % (-instr.operands[j].immediate)
					elif plus and (instr.operands[j].immediate > 0) and (instr.operands[j].immediate <= 0x7f):
						result += '+'
						result += "0x%.2x" % instr.operands[j].immediate
					elif plus and (instr.operands[j].immediate >= -0x8000) and (instr.operands[j].immediate < 0):
						result += '-'
						result += "0x%.8x" % (-instr.operands[j].immediate)
					elif instr.flags & X86.FLAG_64BIT_ADDRESS:
						if plus:
							result += '+'
						value = instr.operands[j].immediate
						string = "0x%.16x" % instr.operands[j].immediate
						if hasattr(block.exe, "plt") and block.exe.plt.has_key(value):
							# Pointer to PLT entry
							self.plt = block.exe.plt[value]
							if len(result) > 0:
								line += [[result, Qt.black]]
								x += len(result)
								result = ""
							string = self.plt + "@PLT"
							line += [[string, QColor(0, 0, 192)]]
							tokens += [[x, len(string), "ptr", value, string]]
							x += len(string)
						elif (value >= block.exe.start()) and (value < block.exe.end()):
							# Pointer within module
							if len(result) > 0:
								line += [[result, Qt.black]]
								x += len(result)
								result = ""
							if value in block.exe.symbols_by_addr:
								string = block.exe.symbols_by_addr[value]
							line += [[string, QColor(0, 0, 192)]]
							tokens += [[x, len(string), "ptr", value, string]]
							x += len(string)
						else:
							result += string
					else:
						if plus:
							result += '+'
						value = instr.operands[j].immediate & 0xffffffff
						string = "0x%.8x" % value
						if (self.addr_size == 4) and hasattr(block.exe, "plt") and block.exe.plt.has_key(value):
							# Pointer to PLT entry
							self.plt = block.exe.plt[value]
							if len(result) > 0:
								line += [[result, Qt.black]]
								x += len(result)
								result = ""
							string = block.exe.decorate_plt_name(self.plt)
							line += [[string, QColor(0, 0, 192)]]
							tokens += [[x, len(string), "ptr", value, string]]
							x += len(string)
						elif (self.addr_size == 4) and (value >= block.exe.start()) and (value < block.exe.end()):
							# Pointer within module
							if len(result) > 0:
								line += [[result, Qt.black]]
								x += len(result)
								result = ""
							if value in block.exe.symbols_by_addr:
								string = block.exe.symbols_by_addr[value]
							line += [[string, QColor(0, 0, 192)]]
							tokens += [[x, len(string), "ptr", value, string]]
							x += len(string)
						else:
							result += string
				result += ']'
			else:
				tokens += [[x + len(result), len(instr.operands[j].operand), "reg", instr.operands[j].operand]]
				result += instr.operands[j].operand

		if len(result) > 0:
			line += [[result, Qt.black]]
		self.text.lines += [line]
		self.text.tokens += [tokens]

		return (old_lines != self.text.lines) or (old_tokens != self.text.tokens)

	def get_prefix_count(self):
		for count in range(0, len(self.opcode)):
			if self.opcode[count] in ["\x26", "\x2e", "\x36", "\x3e", "\x64", "\x65", "\x66", "\x67", "\xf0", "\xf2", "\xf3"]:
				continue
			if (self.addr_size == 8) and (self.opcode[count] >= '\x40') and (self.opcode[count] <= "\x4f"):
				continue
			return count
		return len(self.opcode)

	def patch_to_nop(self, exe):
		exe.write(self.addr, "\x90" * len(self.opcode))

	def is_patch_branch_allowed(self):
		return self.isConditionalBranch()

	def patch_to_always_branch(self, exe):
		prefix_count = self.get_prefix_count()
		if self.opcode[prefix_count] == "\x0f":
			# Two byte branch
			exe.write(self.addr, ("\x90" * (prefix_count + 1)) + "\xb9" + self.opcode[prefix_count+2:])
		else:
			# One byte branch
			exe.write(self.addr, ("\x90" * prefix_count) + "\xeb" + self.opcode[prefix_count+1:])

	def patch_to_invert_branch(self, exe):
		prefix_count = self.get_prefix_count()
		if self.opcode[prefix_count] == "\x0f":
			# Two byte branch
			exe.write(self.addr, self.opcode[0:prefix_count+1] + chr(ord(self.opcode[prefix_count+1]) ^ 1) +
				self.opcode[prefix_count+2:])
		else:
			# One byte branch
			exe.write(self.addr, self.opcode[0:prefix_count] + chr(ord(self.opcode[prefix_count]) ^ 1) +
				self.opcode[prefix_count+1:])

	def is_patch_to_zero_return_allowed(self):
		return self.isCall()

	def patch_to_zero_return(self, exe):
		exe.write(self.addr, "\x31\xc0" + ("\x90" * (len(self.opcode) - 2)))

	def is_patch_to_fixed_return_value_allowed(self):
		return self.isCall() and (len(self.opcode) >= 5)

	def patch_to_fixed_return_value(self, exe, value):
		if len(self.opcode) < 5:
			return
		exe.write(self.addr, "\xb8" + struct.pack("<I", value & 0xffffffff) + ("\x90" * (len(self.opcode) - 5)))


class PPCInstruction:
	def __init__(self, opcode, addr, disasm):
		self.opcode = opcode
		self.addr = addr
		self.disasm = disasm
		self.plt = None
		self.text = InstructionText()

		self.target = None
		if self.disasm.operation and self.disasm.operation.startswith('b') and (len(self.disasm.operands) > 0):
			if type(disasm.operands[-1]) != str:
				self.target = disasm.operands[-1]

	def isConditionalBranch(self):
		return self.disasm.operation in PPC.ConditionalBranches

	def isLocalJump(self):
		if self.disasm.operation in ["b", "ba"]:
			return True
		if self.isConditionalBranch():
			return True
		return False

	def isCall(self):
		return self.disasm.operation in PPC.CallInstructions

	def isBlockEnding(self):
		if self.disasm.operation in (PPC.BranchInstructions + ["trap"]):
			return True
		if self.isLocalJump():
			return True
		return False

	def isValid(self):
		return self.disasm.operation != None

	def length(self):
		return 4

	def format_text(self, block, options):
		old_lines = []
		old_tokens = []
		self.text.lines = []
		self.text.tokens = []

		line = []
		tokens = []
		x = 0
		instr = self.disasm

		if "address" in options:
			string = "%.8x   " % self.addr
			line += [[string, QColor(0, 0, 128)]]
			x += len(string)

		if instr.operation == None:
			line += [["??", Qt.black]]
			self.text.lines += [line]
			self.text.tokens += [tokens]
			return (old_lines != self.text.lines) or (old_tokens != self.text.tokens)

		result = ""
		operation = instr.operation
		if len(operation) < 7:
			operation += " " * (7 - len(operation))
		result += operation + " "

		for j in range(0, len(instr.operands)):
			if j != 0:
				result += ", "
			if type(instr.operands[j]) != str:
				value = instr.operands[j]
				if instr.operands[j] < 0:
					string = "-0x%x" % -instr.operands[j]
				else:
					string = "0x%x" % instr.operands[j]
				if block.analysis.functions.has_key(value):
					# Pointer to existing function
					func = block.analysis.functions[value]
					string = func.name
					if func.plt:
						color = QColor(192, 0, 192)
					else:
						color = QColor(0, 0, 192)
					if len(result) > 0:
						line += [[result, Qt.black]]
						x += len(result)
						result = ""
					line += [[string, color]]
					tokens += [[x, len(string), "ptr", value, string]]
					x += len(string)
				elif (value >= block.exe.start()) and (value < block.exe.end()) and (not self.isLocalJump()):
					# Pointer within module
					if len(result) > 0:
						line += [[result, Qt.black]]
						x += len(result)
						result = ""
					if value in block.exe.symbols_by_addr:
						string = block.exe.symbols_by_addr[value]
					line += [[string, QColor(0, 0, 192)]]
					tokens += [[x, len(string), "ptr", value, string]]
					x += len(string)
				else:
					result += string
			else:
				tokens += [[x + len(result), len(instr.operands[j]), "reg", instr.operands[j]]]
				result += instr.operands[j]

		if len(result) > 0:
			line += [[result, Qt.black]]
		self.text.lines += [line]
		self.text.tokens += [tokens]

		return (old_lines != self.text.lines) or (old_tokens != self.text.tokens)

	def patch_to_nop(self, exe):
		exe.write(self.addr, "\x60\x00\x00\x00")

	def is_patch_branch_allowed(self):
		return self.isConditionalBranch()

	def patch_to_always_branch(self, exe):
		pass

	def patch_to_invert_branch(self, exe):
		pass

	def is_patch_to_zero_return_allowed(self):
		return self.isCall()

	def patch_to_zero_return(self, exe):
		pass

	def is_patch_to_fixed_return_value_allowed(self):
		return self.isCall()

	def patch_to_fixed_return_value(self, exe, value):
		pass


class ArmInstruction:
	def __init__(self, opcode, addr, disasm):
		self.opcode = opcode
		self.addr = addr
		self.disasm = disasm
		self.plt = None
		self.text = InstructionText()

		self.target = None
		if self.disasm.operation and ((self.disasm.operation == "b") or (self.disasm.operation == "bx") or (self.disasm.operation == "bl") or (self.disasm.operation == "blx")) and (type(self.disasm.operands[0]) != str):
			self.target = disasm.operands[0]
		elif self.disasm.operation and ((self.disasm.operation[0:2] == "b.") or (self.disasm.operation[0:3] == "bx.") or (self.disasm.operation[0:3] == "bl.") or (self.disasm.operation[0:4] == "blx.")) and (type(self.disasm.operands[0]) != str):
			self.target = disasm.operands[0]

	def isConditionalBranch(self):
		if self.disasm.operation and ((self.disasm.operation[0:2] == "b.") or (self.disasm.operation[0:3] == "bx.")) and (self.target is not None):
			return True
		return False

	def isLocalJump(self):
		if self.disasm.operation and ((self.disasm.operation == "b") or (self.disasm.operation == "bx")) and (self.target is not None):
			return True
		return self.isConditionalBranch()

	def isCall(self):
		return self.disasm.operation and ((self.disasm.operation == "bl") or (self.disasm.operation == "blx") or (self.disasm.operation[0:3] == "bl.") or (self.disasm.operation[0:4] == "blx."))

	def isBlockEnding(self):
		if self.isLocalJump():
			return True
		if self.disasm.operation and ((self.disasm.operation == "b") or (self.disasm.operation == "bx")):
			return True
		if self.disasm.operation and (self.disasm.operation[0:3] == "ldm") and ("pc" in self.disasm.operands[1:]):
			return True
		if self.disasm.operation and (self.disasm.operation == "ldr") and (self.disasm.operands[0] == "pc"):
			return True
		if self.disasm.operation and (self.disasm.operation == "pop") and ("pc" in self.disasm.operands):
			return True
		return False

	def isValid(self):
		return self.disasm.operation != None

	def length(self):
		return self.disasm.length

	def format_text(self, block, options):
		old_lines = []
		old_tokens = []
		self.text.lines = []
		self.text.tokens = []

		line = []
		tokens = []
		x = 0
		instr = self.disasm

		if "address" in options:
			string = "%.8x   " % self.addr
			line += [[string, QColor(0, 0, 128)]]
			x += len(string)

		if instr.operation == None:
			line += [["??", Qt.black]]
			self.text.lines += [line]
			self.text.tokens += [tokens]
			return (old_lines != self.text.lines) or (old_tokens != self.text.tokens)

		result = ""
		operation = instr.operation.replace(".", "")
		if len(operation) < 7:
			operation += " " * (7 - len(operation))
		result += operation + " "

		for j in range(0, len(instr.operands)):
			if j != 0:
				result += ", "
			if type(instr.operands[j]) == list:
				if instr.operands[j][0][0] == "-":
					tokens += [[x + len(result) + 1, len(instr.operands[j][0]) - 1, "reg", instr.operands[j][0][1:]]]
				elif instr.operands[j][0][-1] == "!":
					tokens += [[x + len(result), len(instr.operands[j][0]) - 1, "reg", instr.operands[j][0][:-1]]]
				else:
					tokens += [[x + len(result), len(instr.operands[j][0]), "reg", instr.operands[j][0]]]
				result += instr.operands[j][0] + " "
				if len(instr.operands[j]) == 2:
					result +=  instr.operands[j][1]
				elif type(instr.operands[j][2]) == str:
					result += instr.operands[j][1] + " "
					if instr.operands[j][2][0] == "-":
						tokens += [[x + len(result) + 1, len(instr.operands[j][2]) - 1, "reg", instr.operands[j][2][1:]]]
					elif instr.operands[j][0][-1] == "!":
						tokens += [[x + len(result), len(instr.operands[j][2]) - 1, "reg", instr.operands[j][2][:-1]]]
					else:
						tokens += [[x + len(result), len(instr.operands[j][2]), "reg", instr.operands[j][2]]]
					result += instr.operands[j][2]
				else:
					result += " %s %d" % (instr.operands[j][1], instr.operands[j][2])
			elif instr.operands[j].__class__ == Arm.MemoryOperand:
				result += "["
				for k in range(0, len(instr.operands[j].components)):
					if k != 0:
						result += ", "
					if type(instr.operands[j].components[k]) == str:
						if instr.operands[j].components[k][0] == "-":
							tokens += [[x + len(result) + 1, len(instr.operands[j].components[k]) - 1, "reg", instr.operands[j].components[k][1:]]]
						elif instr.operands[j].components[k][-1] == "!":
							tokens += [[x + len(result), len(instr.operands[j].components[k]) - 1, "reg", instr.operands[j].components[k][:-1]]]
						else:
							tokens += [[x + len(result), len(instr.operands[j].components[k]), "reg", instr.operands[j].components[k]]]
						result += instr.operands[j].components[k]
					elif type(instr.operands[j].components[k]) == list:
						if instr.operands[j].components[k][0][0] == "-":
							tokens += [[x + len(result) + 1, len(instr.operands[j].components[k][0]) - 1, "reg", instr.operands[j].components[k][0][1:]]]
						elif instr.operands[j].components[k][0][-1] == "!":
							tokens += [[x + len(result), len(instr.operands[j].components[k][0]) - 1, "reg", instr.operands[j].components[k][0][:-1]]]
						else:
							tokens += [[x + len(result), len(instr.operands[j].components[k][0]), "reg", instr.operands[j].components[k][0]]]
						result += instr.operands[j].components[k][0] + " "
						if len(instr.operands[j].components[k]) == 2:
							result += instr.operands[j].components[k][1]
						elif type(instr.operands[j].components[k][2]) == str:
							result += instr.operands[j].components[k][1] + " "
							if instr.operands[j].components[k][2][0] == "-":
								tokens += [[x + len(result) + 1, len(instr.operands[j].components[k][2]) - 1, "reg", instr.operands[j].components[k][2][1:]]]
							elif instr.operands[j][2][-1] == "!":
								tokens += [[x + len(result), len(instr.operands[j].components[k][2]) - 1, "reg", instr.operands[j].components[k][2][:-1]]]
							else:
								tokens += [[x + len(result), len(instr.operands[j].components[k][2]), "reg", instr.operands[j].components[k][2]]]
							result += instr.operands[j].components[k][2]
						else:
							result += "%s %d" % (instr.operands[j].components[k][1], instr.operands[j].components[k][2])
					else:
						value = instr.operands[j].components[k]
						if instr.operands[j].components[k] < 0:
							string = "-0x%x" % -instr.operands[j].components[k]
						else:
							string = "0x%x" % instr.operands[j].components[k]
						if block.analysis.functions.has_key(value):
							# Pointer to existing function
							func = block.analysis.functions[value]
							string = func.name
							if func.plt:
								color = QColor(192, 0, 192)
							else:
								color = QColor(0, 0, 192)
							if len(result) > 0:
								line += [[result, Qt.black]]
								x += len(result)
								result = ""
							line += [[string, color]]
							tokens += [[x, len(string), "ptr", value, string]]
							x += len(string)
						elif (value >= block.exe.start()) and (value < block.exe.end()) and (not self.isLocalJump()):
							# Pointer within module
							if len(result) > 0:
								line += [[result, Qt.black]]
								x += len(result)
								result = ""
							if value in block.exe.symbols_by_addr:
								string = block.exe.symbols_by_addr[value]
							line += [[string, QColor(0, 0, 192)]]
							tokens += [[x, len(string), "ptr", value, string]]
							x += len(string)
						else:
							result += string
				result += "]"
				if instr.operands[j].writeback:
					result += "!"
			elif type(instr.operands[j]) != str:
				value = instr.operands[j]
				if instr.operands[j] < 0:
					string = "-0x%x" % -instr.operands[j]
				else:
					string = "0x%x" % instr.operands[j]
				if block.analysis.functions.has_key(value):
					# Pointer to existing function
					func = block.analysis.functions[value]
					string = func.name
					if func.plt:
						color = QColor(192, 0, 192)
					else:
						color = QColor(0, 0, 192)
					if len(result) > 0:
						line += [[result, Qt.black]]
						x += len(result)
						result = ""
					line += [[string, color]]
					tokens += [[x, len(string), "ptr", value, string]]
					x += len(string)
				elif (value >= block.exe.start()) and (value < block.exe.end()) and (not self.isLocalJump()):
					# Pointer within module
					if len(result) > 0:
						line += [[result, Qt.black]]
						x += len(result)
						result = ""
					if value in block.exe.symbols_by_addr:
						string = block.exe.symbols_by_addr[value]
					line += [[string, QColor(0, 0, 192)]]
					tokens += [[x, len(string), "ptr", value, string]]
					x += len(string)
				else:
					result += string
			else:
				if instr.operands[j][0] == "-":
					tokens += [[x + len(result) + 1, len(instr.operands[j]) - 1, "reg", instr.operands[j][1:]]]
				elif instr.operands[j][-1] == "!":
					tokens += [[x + len(result), len(instr.operands[j]) - 1, "reg", instr.operands[j][:-1]]]
				else:
					tokens += [[x + len(result), len(instr.operands[j]), "reg", instr.operands[j]]]
				result += instr.operands[j]

		if (instr.operation == "ldr") and (instr.operands[1].__class__ == Arm.MemoryOperand) and (len(instr.operands[1].components) == 1) and (type(instr.operands[1].components[0]) != str) and (type(instr.operands[1].components[0]) != list):
			addr = instr.operands[1].components[0]
			if (addr >= block.exe.start()) and ((addr + 4) <= block.exe.end()):
				result += " ; ="
				value = block.exe.read_uint32(addr)
				string = "0x%x" % value
				if block.analysis.functions.has_key(value):
					# Pointer to existing function
					func = block.analysis.functions[value]
					string = func.name
					if func.plt:
						color = QColor(192, 0, 192)
					else:
						color = QColor(0, 0, 192)
					if len(result) > 0:
						line += [[result, Qt.black]]
						x += len(result)
						result = ""
					line += [[string, color]]
					tokens += [[x, len(string), "ptr", value, string]]
					x += len(string)
				elif (value >= block.exe.start()) and (value < block.exe.end()) and (not self.isLocalJump()):
					# Pointer within module
					if len(result) > 0:
						line += [[result, Qt.black]]
						x += len(result)
						result = ""
					if value in block.exe.symbols_by_addr:
						string = block.exe.symbols_by_addr[value]
					line += [[string, QColor(0, 0, 192)]]
					tokens += [[x, len(string), "ptr", value, string]]
					x += len(string)
				else:
					result += string

		if len(result) > 0:
			line += [[result, Qt.black]]
		self.text.lines += [line]
		self.text.tokens += [tokens]

		return (old_lines != self.text.lines) or (old_tokens != self.text.tokens)

	def patch_to_nop(self, exe):
		if self.addr & 1:
			if self.disasm.length == 4:
				exe.write(self.addr & (~1), "\x00\x46\x00\x46")
			else:
				exe.write(self.addr & (~1), "\x00\x46")
		else:
			exe.write(self.addr, "\x00\x00\xa0\xe1")

	def is_patch_branch_allowed(self):
		return self.isConditionalBranch()

	def patch_to_always_branch(self, exe):
		if self.addr & 1:
			opcode = exe.read_uint16(self.addr & (~1))
			imm8 = opcode & 0xff
			if imm8 & 0x80:
				imm11 = imm8 | 0x700
			else:
				imm11 = imm8
			opcode = 0xe000 | imm11
			exe.write_uint16(self.addr & (~1), opcode)
		else:
			exe.write_uint32(self.addr, (exe.read_uint32(self.addr) & 0x0fffffff) | 0xe0000000)

	def patch_to_invert_branch(self, exe):
		if self.addr & 1:
			exe.write_uint16(self.addr & (~1), self.read_uint16(self.addr & (~1)) ^ (1 << 8))
		else:
			exe.write_uint32(self.addr, exe.read_uint32(self.addr) ^ (1 << 28))

	def is_patch_to_zero_return_allowed(self):
		return self.isCall()

	def patch_to_zero_return(self, exe):
		if self.addr & 1:
			if self.disasm.length == 4:
				exe.write(self.addr & (~1), "\x00\x20\x00\x46")
			else:
				exe.write(self.addr & (~1), "\x00\x20")
		else:
			cc = exe.read_uint32(self.addr) & 0xf0000000
			if cc == 0xf0000000:
				cc = 0xe0000000
			exe.write_uint32(self.addr, cc | 0x03a00000)

	def is_patch_to_fixed_return_value_allowed(self):
		return self.isCall()

	def patch_to_fixed_return_value(self, exe, value):
		if self.addr & 1:
			exe.write_uint16(self.addr & (~1), 0x2000 | (value & 0xff))
			if self.disasm.length == 4:
				exe.write((self.addr + 2) & (~1), "\x00\x46")
		else:
			cc = exe.read_uint32(self.addr) & 0xf0000000
			if cc == 0xf0000000:
				cc = 0xe0000000
			exe.write_uint32(self.addr, cc | 0x03000000 | ((value << 4) & 0xf0000) | (value & 0xfff))


class BasicBlock:
	def __init__(self, analysis, exe, entry):
		self.analysis = analysis
		self.exe = exe
		self.entry = entry
		self.exits = []
		self.prev = []
		self.true_path = None
		self.false_path = None
		self.instrs = []
		self.header_text = InstructionText()

	def populate(self, known_instrs):
		addr = self.entry
		while True:
			known_instrs[addr] = self

			if self.exe.architecture() == "x86":
				opcode = self.exe.read(addr, 15)
				result = X86.disassemble32(opcode, addr)
				opcode = opcode[0:result.length]
				instr = X86Instruction(opcode, addr, result, 4)
				arch = X86
			elif self.exe.architecture() == "x86_64":
				opcode = self.exe.read(addr, 15)
				result = X86.disassemble64(opcode, addr)
				opcode = opcode[0:result.length]
				instr = X86Instruction(opcode, addr, result, 8)
				arch = X86
			elif self.exe.architecture() == "ppc":
				opcode = self.exe.read(addr, 4)
				if len(opcode) == 4:
					result = PPC.disassemble(struct.unpack(">I", opcode)[0], addr)
					instr = PPCInstruction(opcode, addr, result)
				else:
					instr = PPCInstruction("", addr, PPC.Instruction())
				arch = PPC
			elif self.exe.architecture() == "arm":
				opcode = self.exe.read(addr & (~1), 4)
				if len(opcode) == 4:
					result = Arm.disassemble(struct.unpack("<I", opcode)[0], addr)
					instr = ArmInstruction(opcode, addr, result)
				else:
					instr = ArmInstruction("", addr, Arm.Instruction())
				arch = Arm
			else:
				break

			self.instrs += [instr]
			instr.format_text(self, self.analysis.options)
			if not instr.isValid():
				break

			if instr.isBlockEnding():
				if instr.isConditionalBranch():
					self.true_path = instr.target
					self.false_path = addr + instr.length()
					self.exits += [self.true_path, self.false_path]
				elif instr.target != None:
					self.exits += [instr.target]
				break

			addr += instr.length()
			if addr in known_instrs:
				self.exits += [addr]
				break

	def update(self):
		changed = False
		for instr in self.instrs:
			if instr.format_text(self, self.analysis.options):
				changed = True
		return changed

class Function:
	def __init__(self, analysis, exe, entry, name = None):
		self.analysis = analysis
		self.exe = exe
		self.entry = entry
		if name:
			self.name = name
		else:
			self.name = "sub_%.8x" % entry
		self.blocks = {}
		self.plt = False
		self.ready = False
		self.update_id = None

	def findBasicBlocks(self):
		# Reset block information in case we are reanalyzing an updated function
		self.blocks = {}
		self.plt = False
		self.ready = False
		self.update_id = self.analysis.get_next_update_id()

		# Create initial basic block and add it to the queue
		block = BasicBlock(self.analysis, self.exe, self.entry)
		block.header_text.lines += [[[self.name + ":", QColor(192, 0, 0)]]]
		block.header_text.tokens += [[[0, len(self.name), "ptr", self.entry, self.name]]]
		queue = [block]
		known_instrs = {}

		# Process until all blocks are found
		while len(queue) > 0:
			block = queue.pop()

			# Find instructions for this block
			block.populate(known_instrs)
			self.blocks[block.entry] = block

			# Follow block exits
			for edge in block.exits:
				already_found = edge in self.blocks
				for i in queue:
					if i.entry == edge:
						already_found = True
				if not already_found:
					if edge in known_instrs:
						# Address is within another basic block, split the block so that
						# the new edge can point to a basic block as well
						block = known_instrs[edge]
						for i in range(0, len(block.instrs)):
							if block.instrs[i].addr == edge:
								break

						new_block = BasicBlock(self.analysis, self.exe, edge)
						new_block.exits = block.exits
						new_block.true_path = block.true_path
						new_block.false_path = block.false_path
						new_block.instrs = block.instrs[i:]
						for instr in new_block.instrs:
							known_instrs[instr.addr] = new_block
						self.blocks[edge] = new_block

						block.exits = [edge]
						block.true_path = None
						block.false_path = None
						block.instrs = block.instrs[0:i]
					else:
						# New basic block
						block = BasicBlock(self.analysis, self.exe, edge)
						self.blocks[edge] = block
						known_instrs[edge] = block
						queue += [block]

		# Set previous block list for each block
		for block in self.blocks.values():
			block.prev = []
		for block in self.blocks.values():
			for exit in block.exits:
				self.blocks[exit].prev.append(block)

		if (len(self.blocks) == 1) and (len(block.instrs) == 1) and (block.instrs[0].plt != None):
			# Function is a trampoline to a PLT entry
			self.rename(block.instrs[0].plt)
			self.plt = True
			self.exe.create_symbol(self.entry, self.name)

	def findCalls(self):
		calls = []
		for block in self.blocks.values():
			for instr in block.instrs:
				if instr.isCall() and (instr.target != None):
					if (instr.target >= self.exe.start()) and (instr.target < self.exe.end()):
						calls += [instr.target]
		return calls

	def update(self):
		changed = False
		for block in self.blocks.values():
			if block.update():
				changed = True
		if changed:
			self.update_id = self.analysis.get_next_update_id()

	def rename(self, name):
		self.name = name
		self.blocks[self.entry].header_text.lines[0] = [[name + ":", QColor(192, 0, 0)]]
		self.blocks[self.entry].header_text.tokens[0] = [[0, len(self.name), "ptr", self.entry, self.name]]

class Analysis:
	def __init__(self, exe):
		self.exe = exe
		self.start = None
		self.functions = {}
		self.run = True
		self.lock = threading.Lock()
		self.queue = []
		self.status = ""
		self.update_id = 0
		self.update_request = False
		self.options = set()
		self.exe.add_callback(self)

	def get_next_update_id(self):
		self.update_id += 1
		return self.update_id

	def analyze(self):
		self.lock.acquire()
		if hasattr(self.exe, "entry"):
			self.status = "Disassembling function at 0x%.8x..." % self.exe.entry()
			self.start = Function(self, self.exe, self.exe.entry(), '_start')
			self.functions[self.exe.entry()] = self.start
			self.start.findBasicBlocks()
			self.queue += self.start.findCalls()
			self.start.ready = True
		self.lock.release()

		while self.run:
			while (len(self.queue) > 0) and self.run:
				self.lock.acquire()

				entry = self.queue.pop()
				self.status = "Disassembling function at 0x%.8x..." % entry

				if entry not in self.functions:
					if entry in self.exe.symbols_by_addr:
						func = Function(self, self.exe, entry, self.exe.symbols_by_addr[entry])
					else:
						func = Function(self, self.exe, entry)
					self.functions[entry] = func
				else:
					func = self.functions[entry]

				func.findBasicBlocks()
				calls = func.findCalls()

				for call in calls:
					already_found = self.functions.has_key(call)
					for i in self.queue:
						if i == call:
							already_found = True
					if not already_found:
						self.queue += [call]

				func.ready = True
				self.lock.release()

				# Give GUI thread a chance to do stuff
				time.sleep(0.001)

			# Update disassembly so that function names are correct
			self.update_request = False
			for func in self.functions.values():
				if not self.run:
					break
				self.lock.acquire()
				self.status = "Updating function at 0x%.8x..." % func.entry
				func.update()
				self.lock.release()
				time.sleep(0.001)

			# Wait for any additional function requests to come in
			self.status = ""
			while (len(self.queue) == 0) and (not self.update_request) and self.run:
				time.sleep(0.1)

	def stop(self):
		run = False

	def find_instr(self, addr, exact_match = False):
		self.lock.acquire()

		for func in self.functions.values():
			for block in func.blocks.values():
				for instr in block.instrs:
					if (exact_match and (addr == instr.addr)) or ((not exact_match) and (addr >= instr.addr) and (addr < (instr.addr + len(instr.opcode)))):
						result = [func.entry, instr.addr]
						self.lock.release()
						return result

		self.lock.release()
		return [None, None]

	def notify_data_write(self, data, ofs, contents):
		self.lock.acquire()

		# Update any functions containing the updated bytes
		start = ofs
		end = ofs + len(contents)

		for func in self.functions.values():
			added = False
			for block in func.blocks.values():
				for instr in block.instrs:
					if (end > instr.addr) and (start < (instr.addr + len(instr.opcode))):
						if func.entry not in self.queue:
							self.queue += [func.entry]
							added = True
							break
				if added:
					break

		self.lock.release()

	def create_symbol(self, addr, name):
		self.lock.acquire()
		self.exe.create_symbol(addr, name)
		if addr in self.functions:
			self.functions[addr].rename(name)
		self.update_request = True
		self.lock.release()

	def undefine_symbol(self, addr, name):
		self.lock.acquire()
		self.exe.delete_symbol(addr, name)
		if addr in self.functions:
			self.functions[addr].rename("sub_%.8x" % addr)
		self.update_request = True
		self.lock.release()

	def set_address_view(self, addr):
		self.lock.acquire()
		if addr:
			self.options.add("address")
		else:
			self.options.remove("address") 
		self.update_request = True
		self.lock.release()

	def isPreferredForFile(data):
		for type in ExeFormats:
			exe = type(data)
			if exe.valid:
				return True
		return False
	isPreferredForFile = staticmethod(isPreferredForFile)

