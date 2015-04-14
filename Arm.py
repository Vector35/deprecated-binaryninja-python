# Copyright (c) 2013 Rusty Wagner
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

Registers = ["r%d" % i for i in xrange(0, 13)] + ["sp", "lr", "pc"]

ConditionalSuffix = [".eq", ".ne", ".cs", ".cc", ".mi", ".pl", ".vs", ".vc", ".hi", ".ls", ".ge", ".lt", ".gt", ".le", "", ""]

class Instruction:
	def __init__(self):
		self.operation = None
		self.operands = []
		self.length = 4

class MemoryOperand:
	def __init__(self, components, writeback):
		self.components = components
		self.writeback = writeback

def reg_shift_immed(reg, typecode, shift, neg = False):
	prefix = ""
	if neg:
		prefix = "-"
	if (typecode == 0) and (shift == 0):
		return prefix + Registers[reg]
	if typecode == 0:
		return [prefix + Registers[reg], "lsl", shift]
	if typecode == 1:
		return [prefix + Registers[reg], "lsr", shift]
	if typecode == 2:
		return [prefix + Registers[reg], "asr", shift]
	if (typecode == 3) and (shift == 0):
		return [prefix + Registers[reg], "rrx"]
	return [prefix + Registers[reg], "ror", shift]

def reg_shift_reg(basereg, typecode, shiftreg, neg = False):
	prefix = ""
	if neg:
		prefix = "-"
	if typecode == 0:
		return [prefix + Registers[basereg], "lsl", Registers[shiftreg]]
	if typecode == 1:
		return [prefix + Registers[basereg], "lsr", Registers[shiftreg]]
	if typecode == 2:
		return [prefix + Registers[basereg], "asr", Registers[shiftreg]]
	return [prefix + Registers[basereg], "ror", Registers[shiftreg]]

def arm_unconditional_instr(instr, opcode):
	op1 = (opcode >> 20) & 0xff

	if (op1 & 0b11100000) == 0b10100000:
		instr.operation = "blx"
		imm24 = opcode & 0xffffff
		if imm24 & (1 << 23):
			instr.operands = [(addr + 8 + ((imm24 | (~0xffffff)) << 2) + ((opcode >> 23) & 2) + 1) & 0xffffffff]
		else:
			instr.operands = [(addr + 8 + (imm24 << 2) + ((opcode >> 23) & 2) + 1) & 0xffffffff]

def arm_data_processing_instr(instr, opcode, addr):
	op = (opcode >> 25) & 1
	op1 = (opcode >> 20) & 0x1f
	op2 = (opcode >> 4) & 0xf
	rn = (opcode >> 16) & 0xf
	rd = (opcode >> 12) & 0xf
	imm5 = (opcode >> 7) & 0x1f
	typecode = (opcode >> 5) & 3
	rm = opcode & 0xf
	if op == 0:
		if op2 == 0b1001:
			if (op1 & 0b11110) == 0b00000:
				instr.operation = "mul"
				if op1 & 1:
					instr.operation += "s"
				instr.operands = [Registers[rn], Registers[rm], Registers[imm5 >> 1]]
			elif (op1 & 0b11110) == 0b00010:
				instr.operation = "mla"
				if op1 & 1:
					instr.operation += "s"
				instr.operands = [Registers[rn], Registers[rm], Registers[imm5 >> 1], Registers[rd]]
			elif op1 == 0b00100:
				instr.operation = "umaal"
				instr.operands = [Registers[rd], Registers[rn], Registers[rm], Registers[imm5 >> 1]]
			elif op1 == 0b00110:
				instr.operation = "mls"
				instr.operands = [Registers[rn], Registers[rm], Registers[imm5 >> 1], Registers[rd]]
			if (op1 & 0b11110) == 0b01000:
				instr.operation = "umull"
				if op1 & 1:
					instr.operation += "s"
				instr.operands = [Registers[rd], Registers[rn], Registers[rm], Registers[imm5 >> 1]]
			elif (op1 & 0b11110) == 0b01010:
				instr.operation = "umlal"
				if op1 & 1:
					instr.operation += "s"
				instr.operands = [Registers[rd], Registers[rn], Registers[rm], Registers[imm5 >> 1]]
			if (op1 & 0b11110) == 0b01100:
				instr.operation = "smull"
				if op1 & 1:
					instr.operation += "s"
				instr.operands = [Registers[rd], Registers[rn], Registers[rm], Registers[imm5 >> 1]]
			elif (op1 & 0b11110) == 0b01110:
				instr.operation = "smlal"
				if op1 & 1:
					instr.operation += "s"
				instr.operands = [Registers[rd], Registers[rn], Registers[rm], Registers[imm5 >> 1]]
			elif op1 == 0b10000:
				instr.operation = "swp"
				instr.operands = [Registers[rd], Registers[rm], MemoryOperand([Registers[rn]], False)]
			elif op1 == 0b10100:
				instr.operation = "swpb"
				instr.operands = [Registers[rd], Registers[rm], MemoryOperand([Registers[rn]], False)]
			elif op1 == 0b11000:
				instr.operation = "strex"
				instr.operands = [Registers[rd], Registers[rm], MemoryOperand([Registers[rn]], False)]
			elif op1 == 0b11001:
				instr.operation = "ldrex"
				instr.operands = [Registers[rd], MemoryOperand([Registers[rn]], False)]
			elif op1 == 0b11010:
				instr.operation = "strexd"
				instr.operands = [Registers[rd], Registers[rm], Registers[(rm + 1) & 0xf], MemoryOperand([Registers[rn]], False)]
			elif op1 == 0b11011:
				instr.operation = "ldrexd"
				instr.operands = [Registers[rd], Registers[(rd + 1) & 0xf], MemoryOperand([Registers[rn]], False)]
			elif op1 == 0b11100:
				instr.operation = "strexb"
				instr.operands = [Registers[rd], Registers[rm], MemoryOperand([Registers[rn]], False)]
			elif op1 == 0b11101:
				instr.operation = "ldrexb"
				instr.operands = [Registers[rd], MemoryOperand([Registers[rn]], False)]
			elif op1 == 0b11110:
				instr.operation = "strexh"
				instr.operands = [Registers[rd], Registers[rm], MemoryOperand([Registers[rn]], False)]
			elif op1 == 0b11111:
				instr.operation = "ldrexh"
				instr.operands = [Registers[rd], MemoryOperand([Registers[rn]], False)]
		elif (op2 & 0b1001) == 0b1001:
			if (op1 & 0b10010) == 0b00010:
				if op2 == 0b1011:
					if op1 & 1:
						instr.operation = "ldrht"
					else:
						instr.operation = "strht"
					instr.operands = [Registers[rd], MemoryOperand([Registers[rn]], False)]
					if op1 & 4:
						if op1 & 8:
							instr.operands.append(((opcode >> 4) & 0xf0) | (opcode & 0xf))
						else:
							instr.operands.append(-(((opcode >> 4) & 0xf0) | (opcode & 0xf)))
					else:
						if op1 & 8:
							instr.operands.append(Registers[rm])
						else:
							instr.operands.append("-" + Registers[rm])
				elif op2 == 0b1101:
					instr.operation = "ldrsbt"
					instr.operands = [Registers[rd], MemoryOperand([Registers[rn]], False)]
					if op1 & 4:
						if op1 & 8:
							instr.operands.append(((opcode >> 4) & 0xf0) | (opcode & 0xf))
						else:
							instr.operands.append(-(((opcode >> 4) & 0xf0) | (opcode & 0xf)))
					else:
						if op1 & 8:
							instr.operands.append(Registers[rm])
						else:
							instr.operands.append("-" + Registers[rm])
				elif op2 == 0b1101:
					instr.operation = "ldrsht"
					instr.operands = [Registers[rd], MemoryOperand([Registers[rn]], False)]
					if op1 & 4:
						if op1 & 8:
							instr.operands.append(((opcode >> 4) & 0xf0) | (opcode & 0xf))
						else:
							instr.operands.append(-(((opcode >> 4) & 0xf0) | (opcode & 0xf)))
					else:
						if op1 & 8:
							instr.operands.append(Registers[rm])
						else:
							instr.operands.append("-" + Registers[rm])
			elif op2 == 0b1011:
				if (op1 & 0b00101) == 0b00000:
					instr.operation = "strh"
					if op1 & 2:
						if op1 & 0x10:
							if op1 & 8:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn], Registers[rm]], True)]
							else:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn], "-" + Registers[rm]], True)]
						else:
							if op1 & 8:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn]], False), Registers[rm]]
							else:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn]], False), "-" + Registers[rm]]
					else:
						if op1 & 8:
							instr.operands = [Registers[rd], MemoryOperand([Registers[rn], Registers[rm]], False)]
						else:
							instr.operands = [Registers[rd], MemoryOperand([Registers[rn], "-" + Registers[rm]], False)]
				elif (op1 & 0b00101) == 0b00001:
					instr.operation = "ldrh"
					if op1 & 2:
						if op1 & 0x10:
							if op1 & 8:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn], Registers[rm]], True)]
							else:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn], "-" + Registers[rm]], True)]
						else:
							if op1 & 8:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn]], False), Registers[rm]]
							else:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn]], False), "-" + Registers[rm]]
					else:
						if op1 & 8:
							instr.operands = [Registers[rd], MemoryOperand([Registers[rn], Registers[rm]], False)]
						else:
							instr.operands = [Registers[rd], MemoryOperand([Registers[rn], "-" + Registers[rm]], False)]
				elif (op1 & 0b00101) == 0b00100:
					instr.operation = "strh"
					imm8 = ((opcode >> 4) & 0xf0) | (opcode & 0xf)
					if op1 & 2:
						if op1 & 0x10:
							if op1 & 8:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn], imm8], True)]
							else:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn], -imm8], True)]
						else:
							if op1 & 8:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn]], False), imm8]
							else:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn]], False), -imm8]
					else:
						if op1 & 8:
							instr.operands = [Registers[rd], MemoryOperand([Registers[rn], imm8], False)]
						else:
							instr.operands = [Registers[rd], MemoryOperand([Registers[rn], -imm8], False)]
				elif (op1 & 0b00101) == 0b00101:
					instr.operation = "ldrh"
					imm8 = ((opcode >> 4) & 0xf0) | (opcode & 0xf)
					if op1 & 2:
						if op1 & 0x10:
							if op1 & 8:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn], imm8], True)]
							else:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn], -imm8], True)]
						else:
							if op1 & 8:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn]], False), imm8]
							else:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn]], False), -imm8]
					else:
						if op1 & 8:
							instr.operands = [Registers[rd], MemoryOperand([Registers[rn], imm8], False)]
						else:
							instr.operands = [Registers[rd], MemoryOperand([Registers[rn], -imm8], False)]
			elif (op2 == 0b1101) or (op2 == 0b1111):
				if (op1 & 0b00101) == 0b00000:
					if op == 0b1101:
						instr.operation = "ldrd"
					else:
						instr.operation = "strd"
					instr.operands = [Registers[rd], Registers[(rd + 1) & 0xf]]
					if op1 & 2:
						if op1 & 0x10:
							if op1 & 8:
								instr.operands += [MemoryOperand([Registers[rn], Registers[rm]], True)]
							else:
								instr.operands += [MemoryOperand([Registers[rn], "-" + Registers[rm]], True)]
						else:
							if op1 & 8:
								instr.operands += [MemoryOperand([Registers[rn]], False), Registers[rm]]
							else:
								instr.operands += [MemoryOperand([Registers[rn]], False), "-" + Registers[rm]]
					else:
						if op1 & 8:
							instr.operands += [MemoryOperand([Registers[rn], Registers[rm]], False)]
						else:
							instr.operands += [MemoryOperand([Registers[rn], "-" + Registers[rm]], False)]
				elif (op1 & 0b00101) == 0b00001:
					if op2 == 0b1101:
						instr.operation = "ldrsb"
					else:
						instr.operation = "ldrsh"
					if op1 & 2:
						if op1 & 0x10:
							if op1 & 8:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn], Registers[rm]], True)]
							else:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn], "-" + Registers[rm]], True)]
						else:
							if op1 & 8:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn]], False), Registers[rm]]
							else:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn]], False), "-" + Registers[rm]]
					else:
						if op1 & 8:
							instr.operands = [Registers[rd], MemoryOperand([Registers[rn], Registers[rm]], False)]
						else:
							instr.operands = [Registers[rd], MemoryOperand([Registers[rn], "-" + Registers[rm]], False)]
				elif (op1 & 0b00101) == 0b00100:
					if op2 == 0b1101:
						instr.operation = "ldrd"
					else:
						instr.operation = "strd"
					instr.operands = [Registers[rd], Registers[(rd + 1) & 0xf]]
					if op1 & 2:
						if op1 & 0x10:
							if op1 & 8:
								instr.operands += [MemoryOperand([Registers[rn], imm8], True)]
							else:
								instr.operands += [MemoryOperand([Registers[rn], -imm8], True)]
						else:
							if op1 & 8:
								instr.operands += [MemoryOperand([Registers[rn]], False), imm8]
							else:
								instr.operands += [MemoryOperand([Registers[rn]], False), -imm8]
					else:
						if op1 & 8:
							instr.operands += [MemoryOperand([Registers[rn], imm8], False)]
						else:
							instr.operands += [MemoryOperand([Registers[rn], -imm8], False)]
				elif (op1 & 0b00101) == 0b00101:
					if op2 == 0b1101:
						instr.operation = "ldrsb"
					else:
						instr.operation = "ldrsh"
					imm8 = ((opcode >> 4) & 0xf0) | (opcode & 0xf)
					if op1 & 2:
						if op1 & 0x10:
							if op1 & 8:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn], imm8], True)]
							else:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn], -imm8], True)]
						else:
							if op1 & 8:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn]], False), imm8]
							else:
								instr.operands = [Registers[rd], MemoryOperand([Registers[rn]], False), -imm8]
					else:
						if op1 & 8:
							instr.operands = [Registers[rd], MemoryOperand([Registers[rn], imm8], False)]
						else:
							instr.operands = [Registers[rd], MemoryOperand([Registers[rn], -imm8], False)]
		elif (op1 & 0b11001) == 0b10000:
			if op2 == 0b0000:
				if (op1 & 2) == 0:
					instr.operation = "mrs"
					instr.operands = [Registers[rd], "apsr"]
				else:
					instr.operation = "msr"
					instr.operands = ["apsr_" + ["", "g", "nzcvq", "nzcvqg"][(rn >> 2) & 3], Registers[rm]]
			elif op2 == 0b0001:
				if op1 == 0b10010:
					instr.operation = "bx"
					instr.operands = [Registers[rm]]
				elif op1 == 0b10110:
					instr.operation = "clz"
					instr.operands = [Registers[rd], Registers[rm]]
			elif op2 == 0b0010:
				if op1 == 0b10010:
					instr.operation = "bxj"
					instr.operands = [Registers[rm]]
			elif op2 == 0b0011:
				if op1 == 0b10010:
					instr.operation = "blx"
					instr.operands = [Registers[rm]]
			elif op2 == 0b0101:
				instr.operation = ["qadd", "qsub", "qdadd", "qdsub"][(op1 >> 1) & 3]
				instr.operands = [Registers[rd], Registers[rm], Registers[rn]]
			elif op2 == 0b0111:
				if op1 == 0b10010:
					instr.operation = "bkpt"
					instr.operands = [((opcode >> 4) & 0xfff0) | (opcode & 0xf)]
				elif op1 == 0b10110:
					instr.operation = "smc"
					instr.operands = [opcode & 0xf]
			elif op1 == 0b10000:
				instr.operation = "smla" + ["b", "t"][(op2 >> 1) & 1] + ["b", "t"][(op2 >> 2) & 1]
				instr.operands = [Registers[rn], Registers[rm], Registers[imm5 >> 1], Registers[rd]]
			elif op1 == 0b10010:
				if op2 & 2:
					instr.operation = "smulw" + ["b", "t"][(op2 >> 2) & 1]
					instr.operands = [Registers[rn], Registers[rm], Registers[imm5 >> 1]]
				else:
					instr.operation = "smlaw" + ["b", "t"][(op2 >> 2) & 1]
					instr.operands = [Registers[rn], Registers[rm], Registers[imm5 >> 1], Registers[rd]]
			elif op1 == 0b10100:
				instr.operation = "smlal" + ["b", "t"][(op2 >> 1) & 1] + ["b", "t"][(op2 >> 2) & 1]
				instr.operands = [Registers[rd], Registers[rn], Registers[rm], Registers[imm5 >> 1]]
			elif op1 == 0b10110:
				instr.operation = "smul" + ["b", "t"][(op2 >> 1) & 1] + ["b", "t"][(op2 >> 2) & 1]
				instr.operands = [Registers[rn], Registers[rm], Registers[imm5 >> 1]]
		elif (op2 & 1) == 0:
			if (op1 & 0b11110) == 0b11010:
				if imm5 == 0:
					if typecode == 3:
						instr.operation = "rrx"
					else:
						instr.operation = "mov"
					if op1 & 1:
						instr.operation += "s"
					instr.operands = [Registers[rd], Registers[rm]]
				else:
					instr.operation = ["lsl", "lsr", "asr", "ror"][typecode]
					if op1 & 1:
						instr.operation += "s"
					instr.operands = [Registers[rd], Registers[rm], imm5]
			elif (op1 & 0b11000) == 0b10000:
				instr.operation = ["tst", "teq", "cmp", "cmpn"][(op1 >> 1) & 3]
				instr.operands = [Registers[rn], reg_shift_immed(rm, typecode, imm5)]
			elif (op1 & 0b11110) == 0b11110:
				instr.operation = "mvn"
				if op1 & 1:
					instr.operation += "s"
				instr.operands = [Registers[rd], reg_shift_immed(rm, typecode, imm5)]
			else:
				instr.operation = ["and", "eor", "sub", "rsb", "add", "adc", "sbc", "rsc", None, None,
					None, None, "orr", None, "bic", None][op1 >> 1]
				if op1 & 1:
					instr.operation += "s"
				instr.operands = [Registers[rd], Registers[rn], reg_shift_immed(rm, typecode, imm5)]
		elif (op2 & 0b1001) == 0b0001:
			if (op1 & 0b11110) == 0b11010:
				instr.operation = ["lsl", "lsr", "asr", "ror"][typecode]
				if op1 & 1:
					instr.operation += "s"
				instr.operands = [Registers[rd], Registers[rm], Registers[imm5 >> 1]]
			elif (op1 & 0b11000) == 0b10000:
				instr.operation = ["tst", "teq", "cmp", "cmpn"][(op1 >> 1) & 3]
				instr.operands = [Registers[rn], reg_shift_reg(rm, typecode, imm5 >> 1)]
			elif (op1 & 0b11110) == 0b11110:
				instr.operation = "mvn"
				if op1 & 1:
					instr.operation += "s"
				instr.operands = [Registers[rd], reg_shift_reg(rm, typecode, imm5 >> 1)]
			else:
				instr.operation = ["and", "eor", "sub", "rsb", "add", "adc", "sbc", "rsc", None, None,
					None, None, "orr", None, "bic", None][op1 >> 1]
				if op1 & 1:
					instr.operation += "s"
				instr.operands = [Registers[rd], Registers[rn], reg_shift_reg(rm, typecode, imm5 >> 1)]
	elif op1 == 0b10000:
		instr.operation = "movw"
		instr.operands = [Registers[rd], ((opcode >> 4) & 0xf000) | (opcode & 0xfff)]
	elif op1 == 0b10100:
		instr.operation = "movt"
		instr.operands = [Registers[rd], ((opcode >> 4) & 0xf000) | (opcode & 0xfff)]
	elif op1 == 0b10010:
		if rn == 0:
			if (opcode & 0xff) == 0:
				instr.operation = "nop"
			elif (opcode & 0xff) == 1:
				instr.operation = "yield"
			elif (opcode & 0xff) == 2:
				instr.operation = "wfe"
			elif (opcode & 0xff) == 3:
				instr.operation = "wfi"
			elif (opcode & 0xff) == 4:
				instr.operation = "sev"
			elif (opcode & 0xf0) == 0xf0:
				instr.operation = "dbg"
				instr.operands = [opcode & 0xf]
		else:
			instr.operation = "msr"
			instr.operands = ["apsr_" + ["", "g", "nzcvq", "nzcvqg"][(rn >> 2) & 3], opcode & 0xfff]
	elif op1 == 0b10110:
		instr.operation = "msr"
		instr.operands = ["apsr_" + ["", "g", "nzcvq", "nzcvqg"][(rn >> 2) & 3], opcode & 0xfff]
	elif (op1 & 0b11001) != 0b10000:
		if (op1 & 0b11000) == 0b10000:
			instr.operation = ["tst", "teq", "cmp", "cmpn"][(op1 >> 1) & 3]
			instr.operands = [Registers[rn], opcode & 0xfff]
		elif (op1 & 0b11110) == 0b11010:
			instr.operation = "mov"
			if op1 & 1:
				instr.operation += "s"
			instr.operands = [Registers[rd], opcode & 0xfff]
		elif (op1 & 0b11110) == 0b11110:
			instr.operation = "mov"
			if op1 & 1:
				instr.operation += "s"
			instr.operands = [Registers[rd], (~(opcode & 0xfff)) & 0xffffffff]
		else:
			instr.operation = ["and", "eor", "sub", "rsb", "add", "adc", "sbc", "rsc", None, None,
				None, None, "orr", None, "bic", None][op1 >> 1]
			if op1 & 1:
				instr.operation += "s"
			instr.operands = [Registers[rd], Registers[rn], opcode & 0xfff]

def arm_load_store_instr(instr, opcode):
	op1 = (opcode >> 20) & 0x1f
	a = (opcode >> 25) & 1
	rn = (opcode >> 16) & 0xf
	rt = (opcode >> 12) & 0xf
	imm5 = (opcode >> 7) & 0xf
	typecode = (opcode >> 5) & 3
	rm = opcode & 0xf
	imm12 = opcode & 0xfff

	if a == 0:
		if (op1 & 0b10111) == 0b00010:
			instr.operation = "strt"
			if op1 & 8:
				instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), imm12]
			else:
				instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), -imm12]
		elif (op1 & 0b10111) == 0b00011:
			instr.operation = "ldrt"
			if op1 & 8:
				instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), imm12]
			else:
				instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), -imm12]
		elif (op1 & 0b10111) == 0b00110:
			instr.operation = "strbt"
			if op1 & 8:
				instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), imm12]
			else:
				instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), -imm12]
		elif (op1 & 0b10111) == 0b00111:
			instr.operation = "ldrbt"
			if op1 & 8:
				instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), imm12]
			else:
				instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), -imm12]
		elif (op1 & 0b00101) == 0b00000:
			instr.operation = "str"
			if op1 & 2:
				if op1 & 0x10:
					if op1 & 8:
						instr.operands = [Registers[rt], MemoryOperand([Registers[rn], imm12], True)]
					else:
						instr.operands = [Registers[rt], MemoryOperand([Registers[rn], -imm12], True)]
				else:
					if op1 & 8:
						instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), imm12]
					else:
						instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), -imm12]
			else:
				if op1 & 8:
					instr.operands = [Registers[rt], MemoryOperand([Registers[rn], imm12], False)]
				else:
					instr.operands = [Registers[rt], MemoryOperand([Registers[rn], -imm12], False)]
		elif (op1 & 0b00101) == 0b00001:
			instr.operation = "ldr"
			if op1 & 2:
				if op1 & 0x10:
					if op1 & 8:
						instr.operands = [Registers[rt], MemoryOperand([Registers[rn], imm12], True)]
					else:
						instr.operands = [Registers[rt], MemoryOperand([Registers[rn], -imm12], True)]
				else:
					if op1 & 8:
						instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), imm12]
					else:
						instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), -imm12]
			else:
				if op1 & 8:
					instr.operands = [Registers[rt], MemoryOperand([Registers[rn], imm12], False)]
				else:
					instr.operands = [Registers[rt], MemoryOperand([Registers[rn], -imm12], False)]
		elif (op1 & 0b00101) == 0b00100:
			instr.operation = "strb"
			if op1 & 2:
				if op1 & 0x10:
					if op1 & 8:
						instr.operands = [Registers[rt], MemoryOperand([Registers[rn], imm12], True)]
					else:
						instr.operands = [Registers[rt], MemoryOperand([Registers[rn], -imm12], True)]
				else:
					if op1 & 8:
						instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), imm12]
					else:
						instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), -imm12]
			else:
				if op1 & 8:
					instr.operands = [Registers[rt], MemoryOperand([Registers[rn], imm12], False)]
				else:
					instr.operands = [Registers[rt], MemoryOperand([Registers[rn], -imm12], False)]
		elif (op1 & 0b00101) == 0b00101:
			instr.operation = "ldrb"
			if op1 & 2:
				if op1 & 0x10:
					if op1 & 8:
						instr.operands = [Registers[rt], MemoryOperand([Registers[rn], imm12], True)]
					else:
						instr.operands = [Registers[rt], MemoryOperand([Registers[rn], -imm12], True)]
				else:
					if op1 & 8:
						instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), imm12]
					else:
						instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), -imm12]
			else:
				if op1 & 8:
					instr.operands = [Registers[rt], MemoryOperand([Registers[rn], imm12], False)]
				else:
					instr.operands = [Registers[rt], MemoryOperand([Registers[rn], -imm12], False)]
	else:
		if (op1 & 0b10111) == 0b00010:
			instr.operation = "strt"
			instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), reg_shift_immed(rm, typecode,
				imm5, (op1 & 8) == 0)]
		elif (op1 & 0b10111) == 0b00011:
			instr.operation = "ldrt"
			instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), reg_shift_immed(rm, typecode,
				imm5, (op1 & 8) == 0)]
		elif (op1 & 0b10111) == 0b00110:
			instr.operation = "strbt"
			instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), reg_shift_immed(rm, typecode,
				imm5, (op1 & 8) == 0)]
		elif (op1 & 0b10111) == 0b00111:
			instr.operation = "ldrbt"
			instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), reg_shift_immed(rm, typecode,
				imm5, (op1 & 8) == 0)]
		elif (op1 & 0b00101) == 0b00000:
			instr.operation = "str"
			if op1 & 2:
				if op1 & 0x10:
					instr.operands = [Registers[rt], MemoryOperand([Registers[rn], reg_shift_immed(rm, typecode,
						imm5, (op1 & 8) == 0)], True)]
				else:
					instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), reg_shift_immed(rm, typecode,
						imm5, (op1 & 8) == 0)]
			else:
				instr.operands = [Registers[rt], MemoryOperand([Registers[rn], reg_shift_immed(rm, typecode,
					imm5, (op1 & 8) == 0)], False)]
		elif (op1 & 0b00101) == 0b00001:
			instr.operation = "ldr"
			if op1 & 2:
				if op1 & 0x10:
					instr.operands = [Registers[rt], MemoryOperand([Registers[rn], reg_shift_immed(rm, typecode,
						imm5, (op1 & 8) == 0)], True)]
				else:
					instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), reg_shift_immed(rm, typecode,
						imm5, (op1 & 8) == 0)]
			else:
				instr.operands = [Registers[rt], MemoryOperand([Registers[rn], reg_shift_immed(rm, typecode,
					imm5, (op1 & 8) == 0)], False)]
		elif (op1 & 0b00101) == 0b00100:
			instr.operation = "strb"
			if op1 & 2:
				if op1 & 0x10:
					instr.operands = [Registers[rt], MemoryOperand([Registers[rn], reg_shift_immed(rm, typecode,
						imm5, (op1 & 8) == 0)], True)]
				else:
					instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), reg_shift_immed(rm, typecode,
						imm5, (op1 & 8) == 0)]
			else:
				instr.operands = [Registers[rt], MemoryOperand([Registers[rn], reg_shift_immed(rm, typecode,
					imm5, (op1 & 8) == 0)], False)]
		elif (op1 & 0b00101) == 0b00101:
			instr.operation = "ldrb"
			if op1 & 2:
				if op1 & 0x10:
					instr.operands = [Registers[rt], MemoryOperand([Registers[rn], reg_shift_immed(rm, typecode,
						imm5, (op1 & 8) == 0)], True)]
				else:
					instr.operands = [Registers[rt], MemoryOperand([Registers[rn]], False), reg_shift_immed(rm, typecode,
						imm5, (op1 & 8) == 0)]
			else:
				instr.operands = [Registers[rt], MemoryOperand([Registers[rn], reg_shift_immed(rm, typecode,
					imm5, (op1 & 8) == 0)], False)]

def arm_media_instr(instr, opcode):
	pass

def arm_branch_instr(instr, opcode, addr):
	op = (opcode >> 20) & 0x3f
	rn = (opcode >> 16) & 0xf
	imm24 = opcode & 0xffffff

	if op & 0x20:
		if op & 0x10:
			instr.operation = "bl"
			if imm24 & (1 << 23):
				instr.operands = [(addr + 8 + ((imm24 | (~0xffffff)) << 2)) & 0xffffffff]
			else:
				instr.operands = [(addr + 8 + (imm24 << 2)) & 0xffffffff]
		else:
			instr.operation = "b"
			if imm24 & (1 << 23):
				instr.operands = [(addr + 8 + ((imm24 | (~0xffffff)) << 2)) & 0xffffffff]
			else:
				instr.operands = [(addr + 8 + (imm24 << 2)) & 0xffffffff]
	elif op & 1:
		instr.operation = "ldm"
		if op & 8:
			instr.operation += "i"
		else:
			instr.operation += "d"
		if op & 0x10:
			instr.operation += "b"
		else:
			instr.operation += "a"
		if op & 2:
			instr.operands = [Registers[rn] + "!"]
		else:
			instr.operands = [Registers[rn]]
		for i in xrange(0, 16):
			if opcode & (1 << i):
				instr.operands.append(Registers[i])
	else:
		instr.operation = "stm"
		if op & 8:
			instr.operation += "i"
		else:
			instr.operation += "d"
		if op & 0x10:
			instr.operation += "b"
		else:
			instr.operation += "a"
		if op & 2:
			instr.operands = [Registers[rn] + "!"]
		else:
			instr.operands = [Registers[rn]]
		for i in xrange(0, 16):
			if opcode & (1 << i):
				instr.operands.append(Registers[i])

def arm_supervisor_instr(instr, opcode):
	op1 = (opcode >> 20) & 0x3f

	if (op1 & 0b110000) == 0b110000:
		instr.operation = "svc"
		instr.operands = [opcode & 0xffffff]

def thumb_16_arith(instr, opcode):
	op = (opcode >> 9) & 0x1f
	imm5 = (opcode >> 6) & 0x1f
	rm = (opcode >> 3) & 7
	rd = opcode & 7

	if (op & 0b11100) == 0:
		if imm5 == 0:
			instr.operation = "movs"
			instr.operands = [Registers[rd], Registers[rm]]
		else:
			instr.operation = "lsl"
			instr.operands = [Registers[rd], Registers[rm], imm5]
	elif (op & 0b11100) == 0b00100:
		instr.operation = "lsr"
		instr.operands = [Registers[rd], Registers[rm], imm5]
	elif (op & 0b11100) == 0b01000:
		instr.operation = "asr"
		instr.operands = [Registers[rd], Registers[rm], imm5]
	elif op == 0b01100:
		instr.operation = "add"
		instr.operands = [Registers[rd], Registers[rm], Registers[imm5 & 7]]
	elif op == 0b01101:
		instr.operation = "sub"
		instr.operands = [Registers[rd], Registers[rm], Registers[imm5 & 7]]
	elif op == 0b01110:
		instr.operation = "add"
		instr.operands = [Registers[rd], Registers[rm], imm5 & 7]
	elif op == 0b01111:
		instr.operation = "sub"
		instr.operands = [Registers[rd], Registers[rm], imm5 & 7]
	elif (op & 0b11100) == 0b10000:
		instr.operation = "mov"
		instr.operands = [Registers[(opcode >> 8) & 7], opcode & 0xff]
	elif (op & 0b11100) == 0b10100:
		instr.operation = "cmp"
		instr.operands = [Registers[(opcode >> 8) & 7], opcode & 0xff]
	elif (op & 0b11100) == 0b11000:
		instr.operation = "add"
		instr.operands = [Registers[(opcode >> 8) & 7], opcode & 0xff]
	elif (op & 0b11100) == 0b11100:
		instr.operation = "sub"
		instr.operands = [Registers[(opcode >> 8) & 7], opcode & 0xff]

def thumb_16_load_store(instr, opcode):
	opa = (opcode >> 12) & 0xf
	opb = (opcode >> 9) & 7
	rm = (opcode >> 6) & 7
	rn = (opcode >> 3) & 7
	rt = opcode & 7

	if opa == 0b0101:
		instr.operation = ["str", "strh", "strb", "ldsrb", "ldr", "ldrh", "ldrb", "ldrsh"][opb]
		instr.operands = [Registers[rt], MemoryOperand([Registers[rn], Registers[rm]], False)]
	elif opa == 0b0110:
		instr.operation = ["str", "ldr"][opb >> 2]
		instr.operands = [Registers[rt], MemoryOperand([Registers[rn], (opcode >> 6) & 0x1f], False)]
	elif opa == 0b0111:
		instr.operation = ["strb", "ldrb"][opb >> 2]
		instr.operands = [Registers[rt], MemoryOperand([Registers[rn], (opcode >> 6) & 0x1f], False)]
	elif opa == 0b1000:
		instr.operation = ["strh", "ldrh"][opb >> 2]
		instr.operands = [Registers[rt], MemoryOperand([Registers[rn], (opcode >> 6) & 0x1f], False)]
	elif opa == 0b1001:
		instr.operation = ["str", "ldr"][opb >> 2]
		instr.operands = [Registers[(opcode >> 8) & 7], MemoryOperand(["sp", opcode & 0xff], False)]

def thumb_16_if_then(instr, opcode):
	firstcond = (opcode >> 4) & 0xf
	mask = opcode & 0xf

	if mask == 0:
		if firstcond < 5:
			instr.operation = ["nop", "yield", "wfe", "wfi", "sev"]
	elif mask & 1:
		instr.operation = ["ite", "itt"][((mask >> 3) & 1) ^ (firstcond & 1)]
		instr.operation += ["e", "t"][((mask >> 2) & 1) ^ (firstcond & 1)]
		instr.operation += ["e", "t"][((mask >> 1) & 1) ^ (firstcond & 1)]
	elif mask & 2:
		instr.operation = ["ite", "itt"][((mask >> 3) & 1) ^ (firstcond & 1)]
		instr.operation += ["e", "t"][((mask >> 2) & 1) ^ (firstcond & 1)]
	elif mask & 4:
		instr.operation = ["ite", "itt"][((mask >> 3) & 1) ^ (firstcond & 1)]
	else:
		instr.operation = "it"

	instr.operands = ["eq", "ne", "cs", "cc", "mi", "pl", "vs", "vc", "hi", "ls", "ge", "lt", "gt", "le", "al", 15]

def thumb_16_misc(instr, opcode, addr):
	op = (opcode >> 5) & 0x7f
	rm = (opcode >> 3) & 7
	rd = opcode & 7

	if op == 0b0110010:
		instr.operation = "setend"
		instr.opearnds = [(opcode >> 8) & 1]
	elif op == 0b0110011:
		instr.operation = "cps"
		if op & 4:
			instr.operation += "a"
		if op & 2:
			instr.operation += "i"
		if op & 1:
			instr.operation += "f"
		instr.operands = [(opcode >> 4) & 1]
	elif (op & 0b1111100) == 0b0000000:
		instr.operation = "add"
		instr.operands = ["sp", "sp", opcode & 0x7f]
	elif (op & 0b1111100) == 0b0000100:
		instr.operation = "sub"
		instr.operands = ["sp", "sp", opcode & 0x7f]
	elif (op & 0b1101000) == 0b0001000:
		instr.operation = "cbz"
		ofs = ((opcode >> 3) & 0x40) | ((opcode >> 2) & 0x3e)
		instr.operands = [Registers[opcode & 7], (((addr + 4) & (~3)) + ofs + 1) & 0xffffffff]
	elif (op & 0b1111110) == 0b0010000:
		instr.operation = "sxth"
		instr.operands = [Registers[rd], Registers[rm]]
	elif (op & 0b1111110) == 0b0010010:
		instr.operation = "sxtb"
		instr.operands = [Registers[rd], Registers[rm]]
	elif (op & 0b1111110) == 0b0010100:
		instr.operation = "uxth"
		instr.operands = [Registers[rd], Registers[rm]]
	elif (op & 0b1111110) == 0b0010110:
		instr.operation = "uxtb"
		instr.operands = [Registers[rd], Registers[rm]]
	elif (op & 0b1110000) == 0b0100000:
		instr.operation = "push"
		instr.operands = []
		for i in xrange(0, 8):
			if opcode & (1 << i):
				instr.operands.append(Registers[i])
		if opcode & (1 << 8):
			instr.operands.append("lr")
	elif (op & 0b1101000) == 0b1001000:
		instr.operation = "cbnz"
		ofs = ((opcode >> 3) & 0x40) | ((opcode >> 2) & 0x3e)
		instr.operands = [Registers[opcode & 7], (((addr + 4) & (~3)) + ofs + 1) & 0xffffffff]
	elif (op & 0b1111110) == 0b1010000:
		instr.operation = "rev"
		instr.operands = [Registers[rd], Registers[rm]]
	elif (op & 0b1111110) == 0b1010010:
		instr.operation = "rev16"
		instr.operands = [Registers[rd], Registers[rm]]
	elif (op & 0b1111110) == 0b1010110:
		instr.operation = "revsh"
		instr.operands = [Registers[rd], Registers[rm]]
	elif (op & 0b1110000) == 0b1100000:
		instr.operation = "pop"
		instr.operands = []
		for i in xrange(0, 8):
			if opcode & (1 << i):
				instr.operands.append(Registers[i])
		if opcode & (1 << 8):
			instr.operands.append("pc")
	elif (op & 0b1111000) == 0b1110000:
		instr.operation = "bkpt"
		instr.operands = [opcode & 0xff]
	elif (op & 0b1111000) == 0b1111000:
		thumb_16_if_then(instr, opcode)

def thumb_16(instr, opcode, addr):
	instr.length = 2

	op = (opcode >> 10) & 0x3f
	op2 = (opcode >> 6) & 0xf
	rm = (opcode >> 3) & 7
	rd = opcode & 7

	if (op & 0b110000) == 0:
		thumb_16_arith(instr, opcode)
	elif op == 0b010000:
		if op2 == 0b1001:
			instr.operation = "rsb"
			instr.operands = [Registers[rd], Registers[rm], 0]
		elif op2 == 0b1101:
			instr.operation = "mul"
			instr.operands = [Registers[rd], Registers[rm], Registers[rd]]
		else:
			instr.operation = ["and", "eor", "lsl", "lsr", "asr", "adc", "sbc", "ror", "tst", None,
				"cmp", "cmn", "orr", None, "bic", "mvn"]
			instr.operands = [Registers[rd], Registers[rm]]
	elif op == 0b010001:
		if (op2 & 0b1100) == 0:
			instr.operation = "add"
			instr.operands = [Registers[rd + ((opcode >> 4) & 8)], Registers[(opcode >> 3) & 0xf]]
		elif (op2 & 0b1100) == 0b0100:
			instr.operation = "cmp"
			instr.operands = [Registers[rd + ((opcode >> 4) & 8)], Registers[(opcode >> 3) & 0xf]]
		elif (op2 & 0b1100) == 0b1000:
			instr.operation = "mov"
			instr.operands = [Registers[rd + ((opcode >> 4) & 8)], Registers[(opcode >> 3) & 0xf]]
		elif (op2 & 0b1110) == 0b1100:
			instr.operation = "bx"
			instr.operands = [Registers[(opcode >> 3) & 0xf]]
		elif (op2 & 0b1110) == 0b1110:
			instr.operation = "blx"
			instr.operands = [Registers[(opcode >> 3) & 0xf]]
	elif (op & 0b111110) == 0b010010:
		instr.operation = "ldr"
		instr.operands = [Registers[(opcode >> 8) & 7], MemoryOperand([((addr + 4) & 0xfffffffc) + ((opcode & 0xff) << 2)], False)]
	elif ((op & 0b111100) == 0b010100) or ((op & 0b111000) == 0b011000) or ((op & 0b111000) == 0b100000):
		thumb_16_load_store(instr, opcode)
	elif (op & 0b111110) == 0b101000:
		instr.operation = "adr"
		instr.operands = [Registers[(opcode >> 8) & 7], ((addr + 4) & 0xfffffffc) + (opcode & 0xff)]
	elif (op & 0b111110) == 0b101010:
		instr.operation = "add"
		instr.operands = [Registers[(opcode >> 8) & 7], "sp", opcode & 0xff]
	elif (op & 0b111100) == 0b101100:
		thumb_16_misc(instr, opcode, addr)
	elif (op & 0b111110) == 0b110000:
		instr.operation = "stmia"
		instr.operands = [Registers[(opcode >> 8) & 7] + "!"]
		for i in xrange(0, 8):
			if opcode & (1 << i):
				instr.operands.append(Registers[i])
	elif (op & 0b111110) == 0b110010:
		instr.operation = "ldmia"
		if opcode & (1 << ((opcode >> 8) & 7)):
			instr.operands = [Registers[(opcode >> 8) & 7]]
		else:
			instr.operands = [Registers[(opcode >> 8) & 7] + "!"]
		for i in xrange(0, 8):
			if opcode & (1 << i):
				instr.operands.append(Registers[i])
	elif (op & 0b111100) == 0b110100:
		if ((opcode >> 8) & 0b1110) != 0b1110:
			instr.operation = "b" + ConditionalSuffix[(opcode >> 8) & 0xf]
			if opcode & 0x80:
				instr.operands = [(((addr + 4) & (~3)) + (((opcode & 0xff) | (~0xff)) << 1) + 1) & 0xffffffff]
			else:
				instr.operands = [(((addr + 4) & (~3)) + ((opcode & 0xff) << 1) + 1) & 0xffffffff]
		elif ((opcode >> 8) & 0b1111) == 0b1111:
			instr.operation = "svc"
			instr.operands = [opcode & 0xff]
	elif (op & 0b111110) == 0b111000:
		instr.operation = "b"
		if opcode & 0x400:
			instr.operands = [(((addr + 4) & (~3)) + (((opcode & 0x7ff) | (~0x7ff)) << 1) + 1) & 0xffffffff]
		else:
			instr.operands = [(((addr + 4) & (~3)) + ((opcode & 0x7ff) << 1) + 1) & 0xffffffff]

def thumb_32_branch(instr, opcode, addr):
	op = (opcode >> 4) & 0x7f
	op1 = (opcode >> 28) & 7
	op2 = (opcode >> 24) & 0xf

	if (op1 & 0b101) == 0b100:
		instr.operation = "blx"
		s = (opcode >> 10) & 1
		j1 = (opcode >> 29) & 1
		j2 = (opcode >> 27) & 1
		i1 = j1 ^ s ^ 1
		i2 = j2 ^ s ^ 1
		ofs = (s << 24) | (i1 << 23) | (i2 << 22) | ((opcode & 0x3ff) << 12) | (((opcode >> 17) & 0x3ff) << 2)
		if s:
			ofs |= ~0x1ffffff
		instr.operands = [(((addr + 4) & (~3)) + ofs) & 0xffffffff]
	elif (op1 & 0b101) == 0b101:
		instr.operation = "bl"
		s = (opcode >> 10) & 1
		j1 = (opcode >> 29) & 1
		j2 = (opcode >> 27) & 1
		i1 = j1 ^ s ^ 1
		i2 = j2 ^ s ^ 1
		ofs = (s << 24) | (i1 << 23) | (i2 << 22) | ((opcode & 0x3ff) << 12) | (((opcode >> 16) & 0x7ff) << 1)
		if s:
			ofs |= ~0x1ffffff
		instr.operands = [(((addr + 4) & (~3)) + ofs + 1) & 0xffffffff]

def thumb_32(instr, opcode, addr):
	op1 = (opcode >> 11) & 3
	op2 = (opcode >> 4) & 0x7f
	op = (opcode >> 31) & 1

	if (op1 == 0b10) and (op == 1):
		thumb_32_branch(instr, opcode, addr)

def disassemble(opcode, addr):
	global Registers, ConditionalSuffix

	instr = Instruction()

	if addr & 1: # Thumb mode
		op = (opcode >> 11) & 0x1f
		if (op == 0b11101) or (op == 0b11110) or (op == 0b11111):
			thumb_32(instr, opcode, addr)
		else:
			thumb_16(instr, opcode & 0xffff, addr)
	else: # Arm mode
		cc = (opcode >> 28) & 15
		op1 = (opcode >> 25) & 7
		op = (opcode >> 4) & 1

		if cc == 0b1111:
			arm_unconditional_instr(instr, opcode)
		elif (op1 & 0b110) == 0b000:
			arm_data_processing_instr(instr, opcode, addr)
		elif ((op1 & 0b110) == 0b010) or ((op1 == 0b011) and (op == 0)):
			arm_load_store_instr(instr, opcode)
		elif (op1 == 0b011) and (op == 1):
			arm_media_instr(instr, opcode)
		elif (op1 & 0b110) == 0b100:
			arm_branch_instr(instr, opcode, addr)
		elif (op1 & 0b110) == 0b110:
			arm_supervisor_instr(instr, opcode)

		# Convert [pc, imm] to final destination
		for i in xrange(0, len(instr.operands)):
			if instr.operands[i].__class__ == MemoryOperand:
				if (len(instr.operands[i].components) == 2) and (instr.operands[i].components[0] == "pc") and (type(instr.operands[i].components[1]) != str) and (type(instr.operands[i].components[1]) != list):
					instr.operands[i].components = [(addr + 8 + instr.operands[i].components[1]) & 0xffffffff]

		if instr.operation is not None:
			instr.operation += ConditionalSuffix[cc]

	return instr

def format_instruction_string(fmt, opcode, addr, instr):
	result = ""
	i = 0
	while i < len(fmt):
		if fmt[i] == '%':
			width = 0
			i += 1
			while i < len(fmt):
				if fmt[i] == 'a':
					if width == 0:
						width = 8
					result += ("%%.%dx" % width) % addr
					break
				elif fmt[i] == 'b':
					result += "%.8x" % opcode
					break
				elif fmt[i] == 'i':
					operation = instr.operation.replace(".", "")
					for j in range(len(operation), width):
						operation += " "
					result += operation
					break
				elif fmt[i] == 'o':
					for j in range(0, len(instr.operands)):
						if j != 0:
							result += ", "
						if type(instr.operands[j]) == list:
							if len(instr.operands[j]) == 2:
								result += instr.operands[j][0] + " " + instr.operands[j][1]
							elif type(instr.operands[j][2]) == str:
								result += instr.operands[j][0] + (" %s %s" % (instr.operands[j][1], instr.operands[j][2]))
							else:
								result += instr.operands[j][0] + (" %s %d" % (instr.operands[j][1], instr.operands[j][2]))
						elif type(instr.operands[j]) == MemoryOperand:
							result += "["
							for k in range(0, len(instr.operands[j].components)):
								if k != 0:
									result += ", "
								if type(instr.operands[j].components[k]) == str:
									result += instr.operands[j].components[k]
								elif type(instr.operands[j].components[k]) == list:
									if len(instr.operands[j].components[k]) == 2:
										result += instr.operands[j].components[k][0] + " " + instr.operands[j].components[k][1]
									elif type(instr.operands[j].components[k][2]) == str:
										result += instr.operands[j].components[k][0] + (" %s %s" % (instr.operands[j].components[k][1],
											instr.operands[j].components[k][2]))
									else:
										result += instr.operands[j].components[k][0] + (" %s %d" % (instr.operands[j].components[k][1],
											instr.operands[j].components[k][2]))
								elif instr.operands[j].components[k] < 0:
									result += "-0x%x" % -instr.operands[j].components[k]
								else:
									result += "0x%x" % instr.operands[j].components[k]
							result += "]"
							if instr.operands[j].writeback:
								result += "!"
						elif type(instr.operands[j]) != str:
							if instr.operands[j] < 0:
								result += "-0x%x" % -instr.operands[j]
							else:
								result += "0x%x" % instr.operands[j]
						else:
							result += instr.operands[j]
					break
				elif (fmt[i] >= '0') and (fmt[i] <= '9'):
					width = (width * 10) + (ord(fmt[i]) - 0x30)
				else:
					result += fmt[i]
					break
				i += 1
		else:
			result += fmt[i]
		i += 1
	return result

def disassemble_to_string(fmt, opcode, addr):
	instr = disassemble(opcode, addr)
	return format_instruction_string(fmt, opcode, addr, instr)

