# PowerPC disassembler for Python

# Copyright (c) 2011-2012 Rusty Wagner
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

Registers = ["r%d" % i for i in xrange(0, 32)]
RegisterOrZero = [0] + ["r%d" % i for i in xrange(1, 32)]
FloatRegisters = ["f%d" % i for i in xrange(0, 32)]

def all_conds(operation):
	prefixes = ['', 'dnz', 'dz']
	conds = ['lt', 'gt', 'eq', 'so', 'ge', 'le', 'ne', 'ns']
	suffixes = ['', '+', '-']
	result = [operation.replace('$', i) for i in ['dnz', 'dz']]
	for prefix in prefixes:
		for cond in conds:
			for suffix in suffixes:
				result.append(operation.replace('$', prefix + cond) + suffix)
	return result

ConditionalBranches = all_conds("b$") + all_conds("b$a")
CallInstructions = ["bl", "bla", "bctrl"] + all_conds("b$l") + all_conds("b$la") + all_conds("b$ctrl")
BranchInstructions = ConditionalBranches + ["b", "ba", "blr", "bctr"] + all_conds("b$lr") + all_conds("b$ctr")

def sign_extend_16(val):
	if val & 0x8000:
		return val - 0x10000
	else:
		return val

def sign_extend_24(val):
	if val & 0x800000:
		return val - 0x1000000
	else:
		return val

def cond_bit(instr, opcode, addr):
	if opcode & 1:
		instr.operation += "."

def link_bit(instr, opcode, addr):
	if opcode & 1:
		instr.operation += "l"

def overflow_bit(instr, opcode, addr):
	if opcode & 0x400:
		instr.operation += "o"

def double_bit(instr, opcode, addr):
	if opcode & 0x200000:
		instr.operation = instr.operation.replace('$', 'd')
	else:
		instr.operation = instr.operation.replace('$', 'w')

def cond_overflow_bits(instr, opcode, addr):
	overflow_bit(instr, opcode, addr)
	cond_bit(instr, opcode, addr)

def cond_branch(instr):
	# Handle extended mnemonics for branches
	cond = ""
	label = None
	suffix = ""

	if (instr.operands[0] & 6) == 0:
		# Decrement CTR, branch if CTR not zero
		cond = 'dnz'
		if instr.operands[0] & 0x8:
			if instr.operands[0] & 1:
				suffix = '+'
			else:
				suffix = '-'
	elif (instr.operands[0] & 6) == 2:
		# Decrement CTR, branch if CTR is zero
		cond = 'dz'
		if instr.operands[0] & 0x8:
			if instr.operands[0] & 1:
				suffix = '+'
			else:
				suffix = '-'

	if (instr.operands[0] & 0x10) == 0:
		# Condition bits used
		if instr.operands[1] & 8:
			if (instr.operands[1] & 3) == 0:
				cond += 'lt'
			elif (instr.operands[1] & 3) == 1:
				cond += 'gt'
			elif (instr.operands[1] & 3) == 2:
				cond += 'eq'
			elif (instr.operands[1] & 3) == 3:
				cond += 'so'
		else:
			if (instr.operands[1] & 3) == 0:
				cond += 'ge'
			elif (instr.operands[1] & 3) == 1:
				cond += 'le'
			elif (instr.operands[1] & 3) == 2:
				cond += 'ne'
			elif (instr.operands[1] & 3) == 3:
				cond += 'ns'
		if instr.operands[1] & 0x1c:
			label = "cr%d" % (instr.operands[1] >> 2)

	instr.operation = instr.operation.replace('$', cond) + suffix
	if label is None:
		instr.operands = instr.operands[2:]
	else:
		instr.operands = [label] + instr.operands[2:]

def link_bit_and_cond_branch(instr, opcode, addr):
	link_bit(instr, opcode, addr)
	cond_branch(instr)

def bc(instr, opcode, addr):
	if opcode & 2:
		if opcode & 1:
			instr.operation = "b$la"
		else:
			instr.operation = "b$a"
		target = sign_extend_16(opcode & 0xfffc)
	else:
		if opcode & 1:
			instr.operation = "b$l"
		else:
			instr.operation = "b$"
		target = sign_extend_16(opcode & 0xfffc) + addr
	instr.operands = [OperandDecode[i](opcode, addr) for i in ['BO', 'BI']]
	instr.operands.append(target)
	cond_branch(instr)

def b(instr, opcode, addr):
	if opcode & 2:
		if opcode & 1:
			instr.operation = "bla"
		else:
			instr.operation = "ba"
		target = sign_extend_24(opcode & 0xfffffc)
	else:
		if opcode & 1:
			instr.operation = "bl"
		else:
			instr.operation = "b"
		target = sign_extend_24(opcode & 0xfffffc) + addr
	instr.operands = [target]

def std(instr, opcode, addr):
	if opcode & 1:
		instr.operation = "stdu"
	else:
		instr.operation = "std"
	instr.operands = [OperandDecode[i](opcode, addr) for i in ['rS', 'rA']]
	instr.operands.append(sign_extend_16(opcode & 0xfffc))

def group(group_map, ext_opcode, instr, opcode, addr):
	op = group_map[ext_opcode]
	if op is None:
		return instr
	if type(op) == list:
		instr.operation = op[0]
		instr.operands = [OperandDecode[i](opcode, addr) for i in op[1]]
		if op[2]:
			op[2](instr, opcode, addr)
	else:
		op(instr, opcode, addr)

# Extended mnemonic handlers
def crset(instr, opcode, addr):
	if (instr.operands[0] == instr.operands[1]) and (instr.operands[1] == instr.operands[2]):
		# creqv bx, bx, bx => crset bx
		instr.operation = "crset"
		instr.operands = [instr.operands[0]]

def crclr(instr, opcode, addr):
	if (instr.operands[0] == instr.operands[1]) and (instr.operands[1] == instr.operands[2]):
		# crxor bx, bx, bx => crclr bx
		instr.operation = "crclr"
		instr.operands = [instr.operands[0]]

def crmove(instr, opcode, addr):
	if instr.operands[1] == instr.operands[2]:
		# cror bx, by, by => crmove bx, by
		instr.operation = "crmove"
		instr.operands = [instr.operands[0], instr.operands[1]]

def trap(instr, opcode, addr):
	if instr.operands[0] == 31:
		# Unconditional trap
		instr.operation = "trap"
		instr.operands = []
		return

	encodings = {
		1: "lgt",
		2: "llt",
		4: "eq",
		5: "lge",
		6: "lle",
		8: "gt",
		12: "ge",
		16: "lt",
		20: "le",
		24: "ne"
	}

	if instr.operands[0] in encodings:
		# Trap has a simplified mnemonic
		instr.operation = instr.operation[0:2] + encodings[instr.operands[0]] + instr.operation[2:]
		instr.operands = instr.operands[1:]

def get_spr_name(spr):
	spr_map = {1: "xer", 8: "lr", 9: "ctr"}
	if spr in spr_map:
		return spr_map[spr]
	return None

def mfspr(instr, opcode, addr):
	spr = get_spr_name(instr.operands[1])
	if spr:
		instr.operation = "mf" + spr
		instr.operands = [instr.operands[0]]

def mtspr(instr, opcode, addr):
	spr = get_spr_name(instr.operands[0])
	if spr:
		instr.operation = "mt" + spr
		instr.operands = [instr.operands[1]]

def nop(instr, opcode, addr):
	if (instr.operands[0] == "r0") and (instr.operands[1] == "r0") and (instr.operands[2] == 0):
		instr.operation = "nop"
		instr.operands = []

def li(instr, opcode, addr):
	if instr.operands[1] == 0:
		instr.operation = "li"
		instr.operands = [instr.operands[0], instr.operands[1]]

def lis(instr, opcode, addr):
	if instr.operands[1] == 0:
		instr.operation = "lis"
		instr.operands = [instr.operands[0], instr.operands[1]]

def mr(instr, opcode, addr):
	if instr.operands[1] == instr.operands[2]:
		instr.operation = "mr"
		instr.operands = [instr.operands[0], instr.operands[1]]
	cond_bit(instr, opcode, addr)

def nor(instr, opcode, addr):
	if instr.operands[1] == instr.operands[2]:
		instr.operation = "not"
		instr.operands = [instr.operands[0], instr.operands[1]]
	cond_bit(instr, opcode, addr)

def mtcr(instr, opcode, addr):
	if instr.operands[0] == 0xff:
		instr.operation = "mtcr"
		instr.operands = [instr.operands[1]]

def rlwinm(instr, opcode, addr):
	if instr.operands[4] == 31:
		if instr.operands[3] == 0:
			instr.operation = "rotlwi"
			instr.operands = [instr.operands[0], instr.operands[1], instr.operands[2]]
		elif instr.operands[2] == (32 - instr.operands[3]):
			instr.operation = "srwi"
			instr.operands = [instr.operands[0], instr.operands[1], instr.operands[3]]
		elif instr.operands[2] == 0:
			instr.operation = "clrlwi"
			instr.operands = [instr.operands[0], instr.operands[1], instr.operands[3]]
		elif instr.operands[2] >= (32 - instr.operands[3]):
			instr.operation = "extrwi"
			instr.operands = [instr.operands[0], instr.operands[1], 32 - instr.operands[3], (32 - instr.operands[3]) - instr.operands[2]]
	elif (instr.operands[3] == 0) and (instr.operands[4] == (31 - instr.operands[2])):
		instr.operation = "slwi"
		instr.operands = [instr.operands[0], instr.operands[1], instr.operands[2]]
	elif (instr.operands[2] == 0) and (instr.operands[3] == 0):
		instr.operation = "clrrwi"
		instr.operands = [instr.operands[0], instr.operands[1], 31 - instr.operands[4]]
	elif instr.operands[3] == 0:
		instr.operation = "extlwi"
		instr.operands = [instr.operands[0], instr.operands[1], instr.operands[4] + 1, instr.operands[2]]
	cond_bit(instr, opcode, addr)

def rlwnm(instr, opcode, addr):
	if (instr.operands[3] == 0) and (instr.operands[4] == 31):
		instr.operation = "rotlw"
		instr.operands = [instr.operands[0], instr.operands[1], instr.operands[2]]
	cond_bit(instr, opcode, addr)

# Opcode tables
OperandDecode = {
	'SI': lambda opcode, addr: sign_extend_16(opcode & 0xffff),
	'UI': lambda opcode, addr: opcode & 0xffff,
	'DS': lambda opcode, addr: opcode & 0xfffc,
	'SH': lambda opcode, addr: (opcode >> 11) & 31,
	'sh': lambda opcode, addr: ((opcode >> 11) & 31) | ((opcode & 2) << 4),
	'NB': lambda opcode, addr: (opcode >> 11) & 31,
	'MB': lambda opcode, addr: (opcode >> 6) & 31,
	'mb': lambda opcode, addr: ((opcode >> 6) & 31) | (opcode & 0x20),
	'ME': lambda opcode, addr: (opcode >> 1) & 31,
	'me': lambda opcode, addr: ((opcode >> 6) & 31) | (opcode & 0x20),
	'rA': lambda opcode, addr: Registers[(opcode >> 16) & 31],
	'rA|0': lambda opcode, addr: RegisterOrZero[(opcode >> 16) & 31],
	'rB': lambda opcode, addr: Registers[(opcode >> 11) & 31],
	'rS': lambda opcode, addr: Registers[(opcode >> 21) & 31],
	'rT': lambda opcode, addr: Registers[(opcode >> 21) & 31],
	'frA': lambda opcode, addr: FloatRegisters[(opcode >> 16) & 31],
	'frB': lambda opcode, addr: FloatRegisters[(opcode >> 11) & 31],
	'frC': lambda opcode, addr: FloatRegisters[(opcode >> 6) & 31],
	'frS': lambda opcode, addr: FloatRegisters[(opcode >> 21) & 31],
	'frT': lambda opcode, addr: FloatRegisters[(opcode >> 21) & 31],
	'SR': lambda opcode, addr: (opcode >> 16) & 15,
	'L': lambda opcode, addr: (opcode >> 21) & 1,
	'L2': lambda opcode, addr: (opcode >> 16) & 1,
	'BF': lambda opcode, addr: (opcode >> 21) & 31,
	'BF2': lambda opcode, addr: "cr%d" % ((opcode >> 23) & 7),
	'BFA2': lambda opcode, addr: "cr%d" % ((opcode >> 18) & 7),
	'BI': lambda opcode, addr: (opcode >> 16) & 31,
	'BO': lambda opcode, addr: (opcode >> 21) & 31,
	'BH': lambda opcode, addr: (opcode >> 11) & 3,
	'BT': lambda opcode, addr: (opcode >> 21) & 31,
	'BA': lambda opcode, addr: (opcode >> 16) & 31,
	'BB': lambda opcode, addr: (opcode >> 11) & 31,
	'TO': lambda opcode, addr: (opcode >> 21) & 31,
	'LEV': lambda opcode, addr: (opcode >> 5) & 0x7f,
	'spr': lambda opcode, addr: ((opcode >> 16) & 0x1f) | ((opcode >> 6) & 0x3e0),
	'FXM': lambda opcode, addr: (opcode >> 12) & 0xff,
	'FLM': lambda opcode, addr: (opcode >> 17) & 0xff,
	'U': lambda opcode, addr: (opcode >> 12) & 0xf
}

Group19Map = {
	0: ["mcrf", ['BF2', 'BFA2'], None],
	16: ["b$lr", ['BO', 'BI'], link_bit_and_cond_branch],
	18: ["rfid", [], None],
	33: ["crnor", ['BT', 'BA', 'BB'], None],
	129: ["crandc", ['BT', 'BA', 'BB'], None],
	150: ["isync", [], None],
	193: ["crxor", ['BT', 'BA', 'BB'], crclr],
	225: ["crnand", ['BT', 'BA', 'BB'], None],
	257: ["crand", ['BT', 'BA', 'BB'], None],
	274: ["hrfid", [], None],
	289: ["creqv", ['BT', 'BA', 'BB'], crset],
	417: ["crorc", ['BT', 'BA', 'BB'], None],
	449: ["cror", ['BT', 'BA', 'BB'], crmove],
	528: ["b$ctr", ['BO', 'BI'], link_bit_and_cond_branch]
}

Group30Map = {
	0: ["rldicl", ['rA', 'rS', 'sh', 'mb'], cond_bit],
	1: ["rldicl", ['rA', 'rS', 'sh', 'mb'], cond_bit],
	2: ["rldicr", ['rA', 'rS', 'sh', 'me'], cond_bit],
	3: ["rldicr", ['rA', 'rS', 'sh', 'me'], cond_bit],
	4: ["rldic", ['rA', 'rS', 'sh', 'mb'], cond_bit],
	5: ["rldic", ['rA', 'rS', 'sh', 'mb'], cond_bit],
	6: ["rldimi", ['rA', 'rS', 'sh', 'mb'], cond_bit],
	7: ["rldimi", ['rA', 'rS', 'sh', 'mb'], cond_bit],
	8: ["rldcl", ['rA', 'rS', 'rB', 'mb'], cond_bit],
	9: ["rldcr", ['rA', 'rS', 'rB', 'me'], cond_bit]
}

Group31Map = {
	0: ["cmp$", ['BF2', 'rA', 'rB'], double_bit],
	4: ["tw", ['TO', 'rA', 'rB'], trap],
	8: ["subfc", ['rT', 'rA', 'rB'], cond_overflow_bits],
	9: ["mulhdu", ['rT', 'rA', 'rB'], cond_bit],
	10: ["addc", ['rT', 'rA', 'rB'], cond_overflow_bits],
	11: ["mulhwu", ['rT', 'rA', 'rB'], cond_bit],
	19: ["mfcr", ['rT'], None],
	20: ["lwarx", ['rT', 'rA|0', 'rB'], None],
	21: ["ldx", ['rT', 'rA|0', 'rB'], None],
	23: ["lwzx", ['rT', 'rA|0', 'rB'], None],
	24: ["slw", ['rA', 'rS', 'rB'], cond_bit],
	26: ["cntlzw", ['rA', 'rS'], cond_bit],
	27: ["sld", ['rA', 'rS', 'rB'], cond_bit],
	28: ["and", ['rA', 'rS', 'rB'], cond_bit],
	32: ["cmp$l", ['BF2', 'rA', 'rB'], double_bit],
	40: ["subf", ['rT', 'rA', 'rB'], cond_overflow_bits],
	53: ["ldux", ['rT', 'rA', 'rB'], None],
	54: ["dcbst", ['rA|0', 'rB'], None],
	55: ["lwzux", ['rT', 'rA', 'rB'], None],
	58: ["cntlzd", ['rA', 'rS'], cond_bit],
	60: ["andc", ['rA', 'rS', 'rB'], cond_bit],
	68: ["td", ['TO', 'rA', 'rB'], trap],
	73: ["mulhd", ['rT', 'rA', 'rB'], cond_bit],
	75: ["mulhw", ['rT', 'rA', 'rB'], cond_bit],
	83: ["mfmsr", ['rT'], None],
	84: ["ldarx", ['rT', 'rA|0', 'rB'], None],
	86: ["dcbf", ['rA|0', 'rB'], None],
	87: ["lbzx", ['rT', 'rA|0', 'rB'], None],
	104: ["neg", ['rT', 'rA'], cond_overflow_bits],
	119: ["lbzux", ['rT', 'rA', 'rB'], None],
	122: ["popcntb", ['rA', 'rS'], cond_bit],
	124: ["nor", ['rA', 'rS', 'rB'], nor],
	136: ["subfe", ['rT', 'rA', 'rB'], cond_overflow_bits],
	138: ["adde", ['rT', 'rA', 'rB'], cond_overflow_bits],
	144: ["mtcrf", ['FXM', 'rS'], mtcr],
	146: ["mtmsr", ['rS', 'L2'], None],
	149: ["stdx", ['rS', 'rA|0', 'rB'], None],
	150: ["stwcx.", ['rS', 'rA|0', 'rB'], None],
	151: ["stwx", ['rS', 'rA|0', 'rB'], None],
	178: ["mtmsrd", ['rS', 'L2'], None],
	181: ["stdux", ['rS', 'rA', 'rB'], None],
	183: ["stwux", ['rS', 'rA', 'rB'], None],
	200: ["subfze", ['rT', 'rA'], cond_overflow_bits],
	202: ["addze", ['rT', 'rA'], cond_overflow_bits],
	210: ["mtsr", ['SR', 'rS'], None],
	214: ["stdcx.", ['rS', 'rA|0', 'rB'], None],
	215: ["stbx", ['rS', 'rA|0', 'rB'], None],
	232: ["subfme", ['rT', 'rA'], cond_overflow_bits],
	233: ["mulld", ['rT', 'rA', 'rB'], cond_overflow_bits],
	234: ["addme", ['rT', 'rA'], cond_overflow_bits],
	235: ["mullw", ['rT', 'rA', 'rB'], cond_overflow_bits],
	242: ["mtsrin", ['rS', 'rB'], None],
	246: ["dcbtst", ['rA|0', 'rB'], None],
	247: ["stbux", ['rS', 'rA', 'rB'], None],
	266: ["add", ['rT', 'rA', 'rB'], cond_overflow_bits],
	274: ["tlbiel", ['rB', 'L'], None],
	278: ["dcbt", ['rA|0', 'rB'], None],
	279: ["lhzx", ['rT', 'rA|0', 'rB'], None],
	284: ["eqv", ['rA', 'rS', 'rB'], cond_bit],
	306: ["tlbie", ['rB', 'L'], None],
	310: ["eciwx", ['rT', 'rA|0', 'rB'], None],
	311: ["lhzux", ['rT', 'rA', 'rB'], None],
	316: ["xor", ['rA', 'rS', 'rB'], cond_bit],
	339: ["mfspr", ['rT', 'spr'], mfspr],
	341: ["lwax", ['rT', 'rA|0', 'rB'], None],
	343: ["lhax", ['rT', 'rA|0', 'rB'], None],
	370: ["tlbia", [], None],
	371: ["mftb", ['rT', 'spr'], None],
	373: ["lwaux", ['rT', 'rA', 'rB'], None],
	375: ["lhaux", ['rT', 'rA', 'rB'], None],
	402: ["slbmte", ['rS', 'rB'], None],
	407: ["sthx", ['rS', 'rA|0', 'rB'], None],
	412: ["orc", ['rA', 'rS', 'rB'], cond_bit],
	413: ["sradi", ['rA', 'rS', 'sh'], cond_bit],
	434: ["slbie", ['rB'], None],
	438: ["ecowx", ['rS', 'rA|0', 'rB'], None],
	439: ["sthux", ['rS', 'rA', 'rB'], None],
	444: ["or", ['rA', 'rS', 'rB'], mr],
	457: ["divdu", ['rT', 'rA', 'rB'], cond_overflow_bits],
	459: ["divwu", ['rT', 'rA', 'rB'], cond_overflow_bits],
	467: ["mtspr", ['spr', 'rS'], mtspr],
	476: ["nand", ['rA', 'rS', 'rB'], cond_bit],
	489: ["divd", ['rT', 'rA', 'rB'], cond_overflow_bits],
	491: ["divw", ['rT', 'rA', 'rB'], cond_overflow_bits],
	498: ["slbia", [], None],
	512: ["mcrxr", ['BF2'], None],
	533: ["lswx", ['rT', 'rA|0', 'rB'], None],
	534: ["lwbrx", ['rT', 'rA|0', 'rB'], None],
	535: ["lfsx", ['frT', 'rA|0', 'rB'], None],
	536: ["srw", ['rA', 'rS', 'rB'], cond_bit],
	539: ["srd", ['rA', 'rS', 'rB'], cond_bit],
	566: ["tlbsync", [], None],
	567: ["lfsux", ['frT', 'rA', 'rB'], None],
	595: ["mfsr", ['rT', 'SR'], None],
	597: ["lswi", ['rT', 'rA|0', 'NB'], None],
	598: ["sync", [], None],
	599: ["lfdx", ['frT', 'rA|0', 'rB'], None],
	631: ["lfdux", ['frT', 'rA', 'rB'], None],
	659: ["mfsrin", ['rT', 'rB'], None],
	661: ["stswx", ['rS', 'rA|0', 'rB'], None],
	662: ["stwbrx", ['rS', 'rA|0', 'rB'], None],
	663: ["stfsx", ['frS', 'rA|0', 'rB'], None],
	695: ["stfsux", ['frS', 'rA', 'rB'], None],
	725: ["stswi", ['rS', 'rA|0', 'NB'], None],
	727: ["stfdx", ['frS', 'rA|0', 'rB'], None],
	759: ["stfdux", ['frS', 'rA', 'rB'], None],
	790: ["lhbrx", ['rT', 'rA|0', 'rB'], None],
	792: ["sraw", ['rA', 'rS', 'rB'], cond_bit],
	794: ["srad", ['rA', 'rS', 'rB'], cond_bit],
	824: ["srawi", ['rA', 'rS', 'SH'], cond_bit],
	851: ["slbmfev", ['rT', 'rB'], None],
	854: ["eieio", [], None],
	915: ["slbmfee", ['rT', 'rB'], None],
	918: ["sthbrx", ['rS', 'rA|0', 'rB'], None],
	922: ["extsh", ['rA', 'rS'], cond_bit],
	954: ["extsb", ['rA', 'rS'], cond_bit],
	982: ["icbi", ['rA|0', 'rB'], None],
	983: ["stfiwx", ['frS', 'rA|0', 'rB'], None],
	986: ["extsw", ['rA', 'rS'], cond_bit],
	1014: ["dcbz", ['rA|0', 'rB'], None]
}

Group58Map = {
	0: ["ld", ['rT', 'rA|0', 'DS'], None],
	1: ["ldu", ['rT', 'rA', 'DS'], None],
	2: ["lwa", ['rT', 'rA|0', 'DS'], None]
}

Group59Map = {
	18: ["fdivs", ['frT', 'frA', 'frB'], cond_bit],
	20: ["fsubs", ['frT', 'frA', 'frB'], cond_bit],
	21: ["fadds", ['frT', 'frA', 'frB'], cond_bit],
	22: ["fsqrts", ['frT', 'frB'], cond_bit],
	24: ["fres", ['frT', 'frB'], cond_bit],
	25: ["fmuls", ['frT', 'frA', 'frC'], cond_bit],
	26: ["frsqrtes", ['frT', 'frB'], cond_bit],
	28: ["fmsubs", ['frT', 'frA', 'frC', 'frB'], cond_bit],
	29: ["fmadds", ['frT', 'frA', 'frC', 'frB'], cond_bit],
	30: ["fnmsubs", ['frT', 'frA', 'frC', 'frB'], cond_bit],
	31: ["fnmadds", ['frT', 'frA', 'frC', 'frB'], cond_bit]
}

Group63Map = {
	0: ["fcmpu", ['BF2', 'frA', 'frB'], None],
	12: ["frsp", ['frT', 'frB'], cond_bit],
	14: ["fctiw", ['frT', 'frB'], cond_bit],
	15: ["fctiwz", ['frT', 'frB'], cond_bit],
	32: ["fcmpo", ['BF2', 'frA', 'frB'], None],
	38: ["mtfsb1", ['BF'], cond_bit],
	40: ["fneg", ['frT', 'frB'], cond_bit],
	64: ["mcrfs", ['BF2', 'BFA2'], None],
	70: ["mtfsb0", ['BF'], cond_bit],
	72: ["fmr", ['frT', 'frB'], cond_bit],
	134: ["mtfsfi", ['BF2', 'U'], cond_bit],
	136: ["fnabs", ['frT', 'frB'], cond_bit],
	264: ["fabs", ['frT', 'frB'], cond_bit],
	583: ["mffs", ['frT'], cond_bit],
	711: ["mtfsf", ['FLM', 'frB'], cond_bit],
	814: ["fctid", ['frT', 'frB'], cond_bit],
	815: ["fctidz", ['frT', 'frB'], cond_bit],
	846: ["fcfid", ['frT', 'frB'], cond_bit]
}

for i in xrange(0, 32):
	Group63Map[18 + (i << 5)] = ["fdiv", ['frT', 'frA', 'frB'], cond_bit]
	Group63Map[20 + (i << 5)] = ["fsub", ['frT', 'frA', 'frB'], cond_bit]
	Group63Map[21 + (i << 5)] = ["fadd", ['frT', 'frA', 'frB'], cond_bit]
	Group63Map[22 + (i << 5)] = ["fsqrt", ['frT', 'frB'], cond_bit]
	Group63Map[23 + (i << 5)] = ["fsel", ['frT', 'frA', 'frC', 'frB'], cond_bit]
	Group63Map[24 + (i << 5)] = ["fre", ['frT', 'frB'], cond_bit]
	Group63Map[25 + (i << 5)] = ["fmul", ['frT', 'frA', 'frC'], cond_bit]
	Group63Map[26 + (i << 5)] = ["fsqrte", ['frT', 'frB'], cond_bit]
	Group63Map[28 + (i << 5)] = ["fmsub", ['frT', 'frA', 'frC', 'frB'], cond_bit]
	Group63Map[29 + (i << 5)] = ["fmadd", ['frT', 'frA', 'frC', 'frB'], cond_bit]
	Group63Map[30 + (i << 5)] = ["fnmsub", ['frT', 'frA', 'frC', 'frB'], cond_bit]
	Group63Map[31 + (i << 5)] = ["fnmadd", ['frT', 'frA', 'frC', 'frB'], cond_bit]

MainOpcodeMap = [
	None, # 0
	None, # 1
	["tdi", ['TO', 'rA', 'SI'], trap], # 2
	["twi", ['TO', 'rA', 'SI'], trap], # 3
	None, # 4
	None, # 5
	None, # 6
	["mulli", ['rT', 'rA', 'SI'], None], # 7
	["subfic", ['rT', 'rA', 'SI'], None], # 8
	None, # 9
	["cmpl$i", ['BF2', 'rA', 'UI'], double_bit], # 10
	["cmp$i", ['BF2', 'rA', 'SI'], double_bit], # 11
	["addic", ['rT', 'rA', 'SI'], None], # 12
	["addic.", ['rT', 'rA', 'SI'], None], # 13
	["addi", ['rT', 'rA|0', 'SI'], li], # 14
	["addis", ['rT', 'rA|0', 'SI'], lis], # 15
	bc, # 16
	["sc", ['LEV'], None], # 17
	b, # 18
	lambda instr, opcode, addr: group(Group19Map, (opcode >> 1) & 1023, instr, opcode, addr), # 19
	["rlwimi", ['rS', 'rA', 'SH', 'MB', 'ME'], cond_bit], # 20
	["rlwinm", ['rS', 'rA', 'SH', 'MB', 'ME'], rlwinm], # 21
	None, # 22
	["rlwnm", ['rS', 'rA', 'rB', 'MB', 'ME'], rlwnm], # 23
	["ori", ['rS', 'rA', 'UI'], nop], # 24
	["oris", ['rS', 'rA', 'UI'], None], # 25
	["xori", ['rS', 'rA', 'UI'], None], # 26
	["xoris", ['rS', 'rA', 'UI'], None], # 27
	["andi", ['rS', 'rA', 'UI'], None], # 28
	["andis", ['rS', 'rA', 'UI'], None], # 29
	lambda instr, opcode, addr: group(Group30Map, (opcode >> 1) & 15, instr, opcode, addr), # 30
	lambda instr, opcode, addr: group(Group31Map, (opcode >> 1) & 1023, instr, opcode, addr), # 31
	["lwz", ['rT', 'rA|0', 'SI'], None], # 32
	["lwzu", ['rT', 'rA', 'SI'], None], # 33
	["lbz", ['rT', 'rA|0', 'SI'], None], # 34
	["lbzu", ['rT', 'rA', 'SI'], None], # 35
	["stw", ['rS', 'rA|0', 'SI'], None], # 36
	["stwu", ['rS', 'rA', 'SI'], None], # 37
	["stb", ['rS', 'rA|0', 'SI'], None], # 38
	["stbu", ['rS', 'rA', 'SI'], None], # 39
	["lhz", ['rT', 'rA|0', 'SI'], None], # 40
	["lhzu", ['rT', 'rA', 'SI'], None], # 41
	["lha", ['rT', 'rA|0', 'SI'], None], # 42
	["lhau", ['rT', 'rA', 'SI'], None], # 43
	["sth", ['rS', 'rA|0', 'SI'], None], # 44
	["sthu", ['rS', 'rA', 'SI'], None], # 45
	["lmw", ['rT', 'rA|0', 'SI'], None], # 46
	["stmw", ['rS', 'rA|0', 'SI'], None], # 47
	["lfs", ['frT', 'rA|0', 'SI'], None], # 48
	["lfsu", ['frT', 'rA', 'SI'], None], # 49
	["lfd", ['frT', 'rA|0', 'SI'], None], # 50
	["lfdu", ['frT', 'rA', 'SI'], None], # 51
	["stfs", ['frS', 'rA|0', 'SI'], None], # 52
	["stfsu", ['frS', 'rA', 'SI'], None], # 53
	["stfd", ['frS', 'rA|0', 'SI'], None], # 54
	["stfdu", ['frS', 'rA', 'SI'], None], # 55
	None, # 56
	None, # 57
	lambda instr, opcode, addr: group(Group58Map, opcode & 3, instr, opcode, addr), # 58
	lambda instr, opcode, addr: group(Group59Map, (opcode >> 1) & 31, instr, opcode, addr), # 59
	None, # 60
	None, # 61
	std, # 62
	lambda instr, opcode, addr: group(Group63Map, (opcode >> 1) & 1023, instr, opcode, addr) # 63
]

def ppc_load_reg(instr, i):
	return il_load_reg(instr.operands[i], 8)

def ppc_load_reg_word(instr, i):
	return il_load_reg(instr.operands[i], 4)

def ppc_load_imm(instr, i):
	return il_load_imm(instr.operands[i], 8)

def ppc_load_imm_shifted(instr, i):
	return il_load_imm(instr.operands[i] << 16, 8)

def ppc_load(instr, size):
	return il_read(instr.operands[1], None, 0, instr.operands[2], 8, size)

def ppc_load_indexed(instr, size):
	return il_read(instr.operands[1], instr.operands[2], 0, 0, 8, size)

def ppc_store_reg(instr, i, val):
	return il_store_reg(instr.operands[i], val)

def ppc_store(instr, size):
	return il_write(instr.operands[1], None, 0, instr.operands[2], 8, il_load_reg(instr.operands[0], size))

def ppc_store_indexed(instr, size):
	return il_write(instr.operands[1], instr.operands[2], 0, 0, 8, il_load_reg(instr.operands[0], size))

def ppc_update(instr):
	return ppc_store_reg(instr, 1, il_add(ppc_load_reg(instr, 1), ppc_load_imm(instr, 2)))

def ppc_update_indexed(instr):
	return ppc_store_reg(instr, 1, il_add(ppc_load_reg(instr, 1), ppc_load_reg(instr, 2)))

ILInstructions = {
	"addi": lambda instr: [ppc_store_reg(instr, 0, il_add(ppc_load_reg(instr, 1), ppc_load_imm(instr, 2)))],
	"addis": lambda instr: [ppc_store_reg(instr, 0, il_add(ppc_load_reg(instr, 1), ppc_load_imm_shifted(instr, 2)))],
	"add": lambda instr: [ppc_store_reg(instr, 0, il_add(ppc_load_reg(instr, 1), ppc_load_reg(instr, 2)))],
	"b": lambda instr: [il_jump(ppc_load_imm(instr, 0))],
	"bctr": lambda instr: [il_jump(il_load_reg("ctr", 8))],
	"bctrl": lambda instr: [il_call(il_load_reg("ctr", 8))],
	"bl": lambda instr: [il_call(ppc_load_imm(instr, 0))],
	"blr": lambda instr: [il_ret(0)],
	"clrrwi": lambda instr: [ppc_store_reg(instr, 0, il_and(ppc_load_reg_word(instr, 1), il_load_imm(-1 << instr.operands[2], 4)))],
	"lbz": lambda instr: [ppc_store_reg(instr, 0, il_extend_u(ppc_load(instr, 1), 8))],
	"lbzx": lambda instr: [ppc_store_reg(instr, 0, il_extend_u(ppc_load_indexed(instr, 1), 8))],
	"lbzu": lambda instr: [ppc_store_reg(instr, 0, il_extend_u(ppc_load(instr, 1), 8)), ppc_update(instr)],
	"lbzux": lambda instr: [ppc_store_reg(instr, 0, il_extend_u(ppc_load_indexed(instr, 1), 8)), ppc_update_indexed(instr)],
	"lhz": lambda instr: [ppc_store_reg(instr, 0, il_extend_u(ppc_load(instr, 2), 8))],
	"lhzx": lambda instr: [ppc_store_reg(instr, 0, il_extend_u(ppc_load_indexed(instr, 2), 8))],
	"lhzu": lambda instr: [ppc_store_reg(instr, 0, il_extend_u(ppc_load(instr, 2), 8)), ppc_update(instr)],
	"lhzux": lambda instr: [ppc_store_reg(instr, 0, il_extend_u(ppc_load_indexed(instr, 2), 8)), ppc_update_indexed(instr)],
	"lwz": lambda instr: [ppc_store_reg(instr, 0, il_extend_u(ppc_load(instr, 4), 8))],
	"lwzx": lambda instr: [ppc_store_reg(instr, 0, il_extend_u(ppc_load_indexed(instr, 4), 8))],
	"lwzu": lambda instr: [ppc_store_reg(instr, 0, il_extend_u(ppc_load(instr, 4), 8)), ppc_update(instr)],
	"lwzux": lambda instr: [ppc_store_reg(instr, 0, il_extend_u(ppc_load_indexed(instr, 4), 8)), ppc_update_indexed(instr)],
	"ld": lambda instr: [ppc_store_reg(instr, 0, ppc_load(instr, 8))],
	"ldx": lambda instr: [ppc_store_reg(instr, 0, ppc_load_indexed(instr, 8))],
	"ldu": lambda instr: [ppc_store_reg(instr, 0, ppc_load(instr, 8)), ppc_update(instr)],
	"ldux": lambda instr: [ppc_store_reg(instr, 0, ppc_load_indexed(instr, 8)), ppc_update_indexed(instr)],
	"li": lambda instr: [ppc_store_reg(instr, 0, ppc_load_imm(instr, 1))],
	"lis": lambda instr: [ppc_store_reg(instr, 0, ppc_load_imm_shifted(instr, 1))],
	"mfctr": lambda instr: [ppc_store_reg(instr, 0, il_load_reg("ctr", 8))],
	"mflr": lambda instr: [ppc_store_reg(instr, 0, il_load_reg("lr", 8))],
	"mr": lambda instr: [ppc_store_reg(instr, 0, ppc_load_reg(instr, 1))],
	"mtctr": lambda instr: [il_store_reg("ctr", ppc_load_reg(instr, 0))],
	"mtlr": lambda instr: [il_store_reg("lr", ppc_load_reg(instr, 0))],
	"slwi": lambda instr: [ppc_store_reg(instr, 0, il_shl(ppc_load_reg_word(instr, 1), il_load_imm(instr.operands[2], 4)))],
	"stb": lambda instr: [ppc_store(instr, 1)],
	"stbx": lambda instr: [ppc_store_indexed(instr, 1)],
	"stbu": lambda instr: [ppc_store(instr, 1), ppc_update(instr)],
	"stbux": lambda instr: [ppc_store_indexed(instr, 1), ppc_update_indexed(instr)],
	"sth": lambda instr: [ppc_store(instr, 2)],
	"sthx": lambda instr: [ppc_store_indexed(instr, 2)],
	"sthu": lambda instr: [ppc_store(instr, 2), ppc_update(instr)],
	"sthux": lambda instr: [ppc_store_indexed(instr, 2), ppc_update_indexed(instr)],
	"stw": lambda instr: [ppc_store(instr, 4)],
	"stwx": lambda instr: [ppc_store_indexed(instr, 4)],
	"stwu": lambda instr: [ppc_store(instr, 4), ppc_update(instr)],
	"stwux": lambda instr: [ppc_store_indexed(instr, 4), ppc_update_indexed(instr)],
	"std": lambda instr: [ppc_store(instr, 8)],
	"stdx": lambda instr: [ppc_store_indexed(instr, 8)],
	"stdu": lambda instr: [ppc_store(instr, 8), ppc_update(instr)],
	"stdux": lambda instr: [ppc_store_indexed(instr, 8), ppc_update_indexed(instr)],
}

class Instruction:
	def __init__(self):
		self.operation = None
		self.operands = []

def disassemble(opcode, addr):
	instr = Instruction()
	op = MainOpcodeMap[(opcode >> 26) & 63]
	if op is None:
		return instr
	if type(op) == list:
		instr.operation = op[0]
		instr.operands = [OperandDecode[i](opcode, addr) for i in op[1]]
		if op[2]:
			op[2](instr, opcode, addr)
	else:
		op(instr, opcode, addr)
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
					operation = instr.operation
					for j in range(len(operation), width):
						operation += " "
					result += operation
					break
				elif fmt[i] == 'o':
					for j in range(0, len(instr.operands)):
						if j != 0:
							result += ", "
						if type(instr.operands[j]) != str:
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

