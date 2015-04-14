# X86 disassembler for Python

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

FLAG_LOCK = 1
FLAG_REP = 2
FLAG_REPNE = 4
FLAG_REPE = 8
FLAG_OPSIZE = 16
FLAG_ADDRSIZE = 32
FLAG_64BIT_ADDRESS = 64
FLAG_INSUFFICIENT_LENGTH = 0x80000000

FLAG_ANY_REP = (FLAG_REP | FLAG_REPE | FLAG_REPNE)

DEC_FLAG_LOCK = 0x0020
DEC_FLAG_REP = 0x0040
DEC_FLAG_REP_COND = 0x0080
DEC_FLAG_BYTE = 0x0100
DEC_FLAG_FLIP_OPERANDS = 0x0200
DEC_FLAG_IMM_SX = 0x0400
DEC_FLAG_INC_OPERATION_FOR_64 = 0x0800
DEC_FLAG_OPERATION_OP_SIZE = 0x1000
DEC_FLAG_FORCE_16BIT = 0x2000
DEC_FLAG_INVALID_IN_64BIT = 0x4000
DEC_FLAG_DEFAULT_TO_64BIT = 0x8000
DEC_FLAG_REG_RM_SIZE_MASK = 0x03
DEC_FLAG_REG_RM_2X_SIZE = 0x01
DEC_FLAG_REG_RM_FAR_SIZE = 0x02
DEC_FLAG_REG_RM_NO_SIZE = 0x03

ControlRegs = ["cr0", "cr1", "cr2", "cr3", "cr4", "cr5", "cr6", "cr7", "cr8", "cr9", "cr10", "cr11", "cr12", "cr13", "cr14", "cr15"]
DebugRegs = ["dr0", "dr1", "dr2", "dr3", "dr4", "dr5", "dr6", "dr7", "dr8", "dr9", "dr10", "dr11", "dr12", "dr13", "dr14", "dr15"]
TestRegs = ["tr0", "tr1", "tr2", "tr3", "tr4", "tr5", "tr6", "tr7", "tr8", "tr9", "tr10", "tr11", "tr12", "tr13", "tr14", "tr15"]

MainOpcodeMap = [
	["add", "rm_reg_8_lock"], ["add", "rm_reg_v_lock"], ["add", "reg_rm_8"], ["add", "reg_rm_v"], # 0x00
	["add", "eax_imm_8"], ["add", "eax_imm_v"], ["push", "push_pop_seg"], ["pop", "push_pop_seg"], # 0x04
	["or", "rm_reg_8_lock"], ["or", "rm_reg_v_lock"], ["or", "reg_rm_8"], ["or", "reg_rm_v"], # 0x08
	["or", "eax_imm_8"], ["or", "eax_imm_v"], ["push", "push_pop_seg"], [None, "two_byte"], # 0x0c
	["adc", "rm_reg_8_lock"], ["adc", "rm_reg_v_lock"], ["adc", "reg_rm_8"], ["adc", "reg_rm_v"], # 0x10
	["adc", "eax_imm_8"], ["adc", "eax_imm_v"], ["push", "push_pop_seg"], ["pop", "push_pop_seg"], # 0x14
	["sbb", "rm_reg_8_lock"], ["sbb", "rm_reg_v_lock"], ["sbb", "reg_rm_8"], ["sbb", "reg_rm_v"], # 0x18
	["sbb", "eax_imm_8"], ["sbb", "eax_imm_v"], ["push", "push_pop_seg"], ["pop", "push_pop_seg"], # 0x1c
	["and", "rm_reg_8_lock"], ["and", "rm_reg_v_lock"], ["and", "reg_rm_8"], ["and", "reg_rm_v"], # 0x20
	["and", "eax_imm_8"], ["and", "eax_imm_v"], [None, None], ["daa", "no_operands"], # 0x24
	["sub", "rm_reg_8_lock"], ["sub", "rm_reg_v_lock"], ["sub", "reg_rm_8"], ["sub", "reg_rm_v"], # 0x28
	["sub", "eax_imm_8"], ["sub", "eax_imm_v"], [None, None], ["das", "no_operands"], # 0x2c
	["xor", "rm_reg_8_lock"], ["xor", "rm_reg_v_lock"], ["xor", "reg_rm_8"], ["xor", "reg_rm_v"], # 0x30
	["xor", "eax_imm_8"], ["xor", "eax_imm_v"], [None, None], ["aaa", "no_operands"], # 0x34
	["cmp", "rm_reg_8"], ["cmp", "rm_reg_v"], ["cmp", "reg_rm_8"], ["cmp", "reg_rm_v"], # 0x38
	["cmp", "eax_imm_8"], ["cmp", "eax_imm_v"], [None, None], ["aas", "no_operands"], # 0x3c
	["inc", "op_reg_v"], ["inc", "op_reg_v"], ["inc", "op_reg_v"], ["inc", "op_reg_v"], # 0x40
	["inc", "op_reg_v"], ["inc", "op_reg_v"], ["inc", "op_reg_v"], ["inc", "op_reg_v"], # 0x44
	["dec", "op_reg_v"], ["dec", "op_reg_v"], ["dec", "op_reg_v"], ["dec", "op_reg_v"], # 0x48
	["dec", "op_reg_v"], ["dec", "op_reg_v"], ["dec", "op_reg_v"], ["dec", "op_reg_v"], # 0x4c
	["push", "op_reg_v_def64"], ["push", "op_reg_v_def64"], ["push", "op_reg_v_def64"], ["push", "op_reg_v_def64"], # 0x50
	["push", "op_reg_v_def64"], ["push", "op_reg_v_def64"], ["push", "op_reg_v_def64"], ["push", "op_reg_v_def64"], # 0x54
	["pop", "op_reg_v_def64"], ["pop", "op_reg_v_def64"], ["pop", "op_reg_v_def64"], ["pop", "op_reg_v_def64"], # 0x58
	["pop", "op_reg_v_def64"], ["pop", "op_reg_v_def64"], ["pop", "op_reg_v_def64"], ["pop", "op_reg_v_def64"], # 0x5c
	[["pusha", "pushad"], "op_size_no64"], [["popa", "popad"], "op_size_no64"], ["bound", "reg_rm2x_v"], ["arpl", "arpl"], # 0x60
	[None, None], [None, None], [None, None], [None, None], # 0x64
	["push", "imm_v_def64"], ["imul", "reg_rm_imm_v"], ["push", "immsx_v_def64"], ["imul", "reg_rm_immsx_v"], # 0x68
	["insb", "edi_dx_8_rep"], [["insw", "insd"], "edi_dx_op_size_rep"], ["outsb", "dx_esi_8_rep"], [["outsw", "outsd"], "dx_esi_op_size_rep"], # 0x6c
	["jo", "relimm_8_def64"], ["jno", "relimm_8_def64"], ["jb", "relimm_8_def64"], ["jae", "relimm_8_def64"], # 0x70
	["je", "relimm_8_def64"], ["jne", "relimm_8_def64"], ["jbe", "relimm_8_def64"], ["ja", "relimm_8_def64"], # 0x74
	["js", "relimm_8_def64"], ["jns", "relimm_8_def64"], ["jpe", "relimm_8_def64"], ["jpo", "relimm_8_def64"], # 0x78
	["jl", "relimm_8_def64"], ["jge", "relimm_8_def64"], ["jle", "relimm_8_def64"], ["jg", "relimm_8_def64"], # 0x7c
	[0, "group_rm_imm_8_lock"], [0, "group_rm_imm_v_lock"], [0, "group_rm_imm_8_no64_lock"], [0, "group_rm_immsx_v_lock"], # 0x80
	["test", "rm_reg_8"], ["test", "rm_reg_v"], ["xchg", "rm_reg_8_lock"], ["xchg", "rm_reg_v_lock"], # 0x84
	["mov", "rm_reg_8"], ["mov", "rm_reg_v"], ["mov", "reg_rm_8"], ["mov", "reg_rm_v"], # 0x88
	["mov", "rm_sreg_v"], ["lea", "reg_rm_0"], ["mov", "sreg_rm_v"], ["pop", "rm_v_def64"], # 0x8c
	["nop", "nop"], ["xchg", "eax_op_reg_v"], ["xchg", "eax_op_reg_v"], ["xchg", "eax_op_reg_v"], # 0x90
	["xchg", "eax_op_reg_v"], ["xchg", "eax_op_reg_v"], ["xchg", "eax_op_reg_v"], ["xchg", "eax_op_reg_v"], # 0x94
	[["cbw", "cwde", "cdqe"], "op_size"], [["cwd", "cdq", "cqo"], "op_size"], ["callf", "far_imm_no64"], ["fwait", "no_operands"], # 0x98
	[["pushf", "pushfd", "pushfq"], "op_size_def64"], [["popf", "popfd", "popfq"], "op_size_def64"], ["sahf", "no_operands"], ["lahf", "no_operands"], # 0x9c
	["mov", "eax_addr_8"], ["mov", "eax_addr_v"], ["mov", "addr_eax_8"], ["mov", "addr_eax_v"], # 0xa0
	["movsb", "edi_esi_8_rep"], [["movsw", "movsd", "movsq"], "edi_esi_op_size_rep"], ["cmpsb", "esi_edi_8_repc"], [["cmpsw", "cmpsd", "cmpsq"], "esi_edi_op_size_repc"], # 0xa4
	["test", "eax_imm_8"], ["test", "eax_imm_v"], ["stosb", "edi_eax_8_rep"], [["stosw", "stosd", "stosq"], "edi_eax_op_size_rep"], # 0xa8
	["lodsb", "eax_esi_8_rep"], [["lodsw", "lodsd", "lodsq"], "eax_esi_op_size_rep"], ["scasb", "eax_edi_8_repc"], [["scasw", "scasd", "scasq"], "eax_edi_op_size_repc"], # 0xac
	["mov", "op_reg_imm_8"], ["mov", "op_reg_imm_8"], ["mov", "op_reg_imm_8"], ["mov", "op_reg_imm_8"], # 0xb0
	["mov", "op_reg_imm_8"], ["mov", "op_reg_imm_8"], ["mov", "op_reg_imm_8"], ["mov", "op_reg_imm_8"], # 0xb4
	["mov", "op_reg_imm_v"], ["mov", "op_reg_imm_v"], ["mov", "op_reg_imm_v"], ["mov", "op_reg_imm_v"], # 0xb8
	["mov", "op_reg_imm_v"], ["mov", "op_reg_imm_v"], ["mov", "op_reg_imm_v"], ["mov", "op_reg_imm_v"], # 0xbc
	[1, "group_rm_imm_8"], [1, "group_rm_imm8_v"], ["retn", "imm_16"], ["retn", "no_operands"], # 0xc0
	["les", "reg_rm_f"], ["lds", "reg_rm_f"], [2, "group_rm_imm_8"], [2, "group_rm_imm_v"], # 0xc4
	["enter", "imm16_imm8"], ["leave", "no_operands"], ["retf", "imm_16"], ["retf", "no_operands"], # 0xc8
	["int3", "no_operands"], ["int", "imm_8"], ["into", "no_operands"], ["iret", "no_operands"], # 0xcc
	[1, "group_rm_one_8"], [1, "group_rm_one_v"], [1, "group_rm_cl_8"], [1, "group_rm_cl_v"], # 0xd0
	["aam", "imm_8"], ["aad", "imm_8"], ["salc", "no_operands"], ["xlat", "al_ebx_al"], # 0xd4
	[0, "fpu"], [1, "fpu"], [2, "fpu"], [3, "fpu"], # 0xd8
	[4, "fpu"], [5, "fpu"], [6, "fpu"], [7, "fpu"], # 0xdc
	["loopne", "relimm_8_def64"], ["loope", "relimm_8_def64"], ["loop", "relimm_8_def64"], [["jcxz", "jecxz", "jrcxz"], "relimm_8_addr_size_def64"], # 0xe0
	["in", "eax_imm8_8"], ["in", "eax_imm8_v"], ["out", "imm8_eax_8"], ["out", "imm8_eax_v"], # 0xe4
	["calln", "relimm_v_def64"], ["jmpn", "relimm_v_def64"], ["jmpf", "far_imm_no64"], ["jmpn", "relimm_8_def64"], # 0xe8
	["in", "eax_dx_8"], ["in", "eax_dx_v"], ["out", "dx_eax_8"], ["out", "dx_eax_v"], # 0xec
	[None, None], ["int1", "no_operands"], [None, None], [None, None], # 0xf0
	["hlt", "no_operands"], ["cmc", "no_operands"], [3, "group_f6"], [3, "group_f7"], # 0xf4
	["clc", "no_operands"], ["stc", "no_operands"], ["cli", "no_operands"], ["sti", "no_operands"], # 0xf8
	["cld", "no_operands"], ["std", "no_operands"], [4, "group_rm_8_lock"], [5, "group_ff"], # 0xfc
]

TwoByteOpcodeMap = [
	[6, "group_0f00"], [7, "group_0f01"], ["lar", "reg_rm_v"], ["lsl", "reg_rm_v"], # 0x00
	[None, None], ["syscall", "no_operands"], ["clts", "no_operands"], ["sysret", "no_operands"], # 0x04
	["invd", "no_operands"], ["wbinvd", "no_operands"], [None, None], ["ud2", "no_operands"], # 0x08
	[None, None], [8, "group_rm_0"], ["femms", "no_operands"], [0, "_3dnow"], # 0x0c
	[0, "sse_table"], [0, "sse_table_flip"], [1, "sse_table"], [2, "sse_table_flip"], # 0x10
	[3, "sse_table"], [4, "sse_table"], [5, "sse_table"], [6, "sse_table_flip"], # 0x14
	[9, "group_rm_0"], [10, "group_rm_0"], [10, "group_rm_0"], [10, "group_rm_0"], # 0x18
	[10, "group_rm_0"], [10, "group_rm_0"], [10, "group_rm_0"], [10, "group_rm_0"], # 0x1c
	[ControlRegs, "reg_cr"], [DebugRegs, "reg_cr"], [ControlRegs, "cr_reg"], [DebugRegs, "cr_reg"], # 0x20
	[TestRegs, "reg_cr"], [None, None], [TestRegs, "cr_reg"], [None, None], # 0x24
	[7, "sse_table"], [7, "sse_table_flip"], [8, "sse_table"], [9, "sse_table_flip"], # 0x28
	[10, "sse_table"], [11, "sse_table"], [12, "sse_table"], [13, "sse_table"], # 0x2c
	["wrmsr", "no_operands"], ["rdtsc", "no_operands"], ["rdmsr", "no_operands"], ["rdpmc", "no_operands"], # 0x30
	["sysenter", "no_operands"], ["sysexit", "no_operands"], [None, None], ["getsec", "no_operands"], # 0x34
	[None, None], [None, None], [None, None], [None, None], # 0x38
	[None, None], [None, None], [None, None], [None, None], # 0x3c
	["cmovo", "reg_rm_v"], ["cmovno", "reg_rm_v"], ["cmovb", "reg_rm_v"], ["cmovae", "reg_rm_v"], # 0x40
	["cmove", "reg_rm_v"], ["cmovne", "reg_rm_v"], ["cmovbe", "reg_rm_v"], ["cmova", "reg_rm_v"], # 0x44
	["cmovs", "reg_rm_v"], ["cmovns", "reg_rm_v"], ["cmovpe", "reg_rm_v"], ["cmovpo", "reg_rm_v"], # 0x48
	["cmovl", "reg_rm_v"], ["cmovge", "reg_rm_v"], ["cmovle", "reg_rm_v"], ["cmovg", "reg_rm_v"], # 0x4c
	[14, "sse_table"], [["sqrtps", "sqrtpd", "sqrtsd", "sqrtss"], "sse"], [["rsqrtps", "rsqrtss"], "sse_single"], [["rcpps", "rcpss"], "sse_single"], # 0x50
	[["andps", "andpd"], "sse_packed"], [["andnps", "andnpd"], "sse_packed"], [["orps", "orpd"], "sse_packed"], [["xorps", "xorpd"], "sse_packed"], # 0x54
	[["addps", "addpd", "addsd", "addss"], "sse"], [["mulps", "mulpd", "mulsd", "mulss"], "sse"], [15, "sse_table"], [16, "sse_table"], # 0x58
	[["subps", "subpd", "subsd", "subss"], "sse"], [["minps", "minpd", "minsd", "minss"], "sse"], [["divps", "divpd", "divsd", "divss"], "sse"], [["maxps", "maxpd", "maxsd", "maxss"], "sse"], # 0x5c
	[17, "sse_table"], [18, "sse_table"], [19, "sse_table"], ["packsswb", "mmx"], # 0x60
	["pcmpgtb", "mmx"], ["pcmpgtw", "mmx"], ["pcmpgtd", "mmx"], ["packuswb", "mmx"], # 0x64
	["punpckhbw", "mmx"], ["punpckhwd", "mmx"], ["punpckhdq", "mmx"], ["packssdw", "mmx"], # 0x68
	["punpcklqdq", "mmx_sseonly"], ["punpckhqdq", "mmx_sseonly"], [20, "sse_table_incop64"], [21, "sse_table"], # 0x6c
	[22, "sse_table_imm_8"], [0, "mmx_group"], [1, "mmx_group"], [2, "mmx_group"], # 0x70
	["pcmpeqb", "mmx"], ["pcmpeqw", "mmx"], ["pcmpeqd", "mmx"], ["emms", "no_operands"], # 0x74
	["vmread", "rm_reg_def64"], ["vmwrite", "rm_reg_def64"], [None, None], [None, None], # 0x78
	[23, "sse_table"], [24, "sse_table"], [25, "sse_table_incop64_flip"], [21, "sse_table_flip"], # 0x7c
	["jo", "relimm_v_def64"], ["jno", "relimm_v_def64"], ["jb", "relimm_v_def64"], ["jae", "relimm_v_def64"], # 0x80
	["je", "relimm_v_def64"], ["jne", "relimm_v_def64"], ["jbe", "relimm_v_def64"], ["ja", "relimm_v_def64"], # 0x84
	["js", "relimm_v_def64"], ["jns", "relimm_v_def64"], ["jpe", "relimm_v_def64"], ["jpo", "relimm_v_def64"], # 0x88
	["jl", "relimm_v_def64"], ["jge", "relimm_v_def64"], ["jle", "relimm_v_def64"], ["jg", "relimm_v_def64"], # 0x8c
	["seto", "rm_8"], ["setno", "rm_8"], ["setb", "rm_8"], ["setae", "rm_8"], # 0x90
	["sete", "rm_8"], ["setne", "rm_8"], ["setbe", "rm_8"], ["seta", "rm_8"], # 0x94
	["sets", "rm_8"], ["setns", "rm_8"], ["setpe", "rm_8"], ["setpo", "rm_8"], # 0x98
	["setl", "rm_8"], ["setge", "rm_8"], ["setle", "rm_8"], ["setg", "rm_8"], # 0x9c
	["push", "push_pop_seg"], ["pop", "push_pop_seg"], ["cpuid", "no_operands"], ["bt", "rm_reg_v"], # 0xa0
	["shld", "rm_reg_imm8_v"], ["shld", "rm_reg_cl_v"], [None, None], [None, None], # 0xa4
	["push", "push_pop_seg"], ["pop", "push_pop_seg"], ["rsm", "no_operands"], ["bts", "rm_reg_v_lock"], # 0xa8
	["shrd", "rm_reg_imm8_v"], ["shrd", "rm_reg_cl_v"], [24, "group_0fae"], ["imul", "reg_rm_v"], # 0xac
	["cmpxchg", "rm_reg_8_lock"], ["cmpxchg", "rm_reg_v_lock"], ["lss", "reg_rm_f"], ["btr", "rm_reg_v_lock"], # 0xb0
	["lfs", "reg_rm_f"], ["lgs", "reg_rm_f"], ["movzx", "movsxzx_8"], ["movzx", "movsxzx_16"], # 0xb4
	["popcnt", "_0fb8"], [None, None], [11, "group_rm_imm8_v"], ["btc", "rm_reg_v_lock"], # 0xb8
	["bsf", "reg_rm_v"], ["bsr", "reg_rm_v"], ["movsx", "movsxzx_8"], ["movsx", "movsxzx_16"], # 0xbc
	["xadd", "rm_reg_8_lock"], ["xadd", "rm_reg_v_lock"], [26, "sse_table_imm_8"], ["movnti", "movnti"], # 0xc0
	[27, "pinsrw"], [28, "sse_table_imm_8"], [29, "sse_table_imm_8"], ["cmpxch8b", "cmpxch8b"], # 0xc4
	["bswap", "op_reg_v"], ["bswap", "op_reg_v"], ["bswap", "op_reg_v"], ["bswap", "op_reg_v"], # 0xc8
	["bswap", "op_reg_v"], ["bswap", "op_reg_v"], ["bswap", "op_reg_v"], ["bswap", "op_reg_v"], # 0xcc
	[30, "sse_table"], ["psrlw", "mmx"], ["psrld", "mmx"], ["psrlq", "mmx"], # 0xd0
	["paddq", "mmx"], ["pmullw", "mmx"], [31, "sse_table"], [32, "sse_table"], # 0xd4
	["psubusb", "mmx"], ["psubusw", "mmx"], ["pminub", "mmx"], ["pand", "mmx"], # 0xd8
	["paddusb", "mmx"], ["paddusw", "mmx"], ["pmaxub", "mmx"], ["pandn", "mmx"], # 0xdc
	["pavgb", "mmx"], ["psraw", "mmx"], ["psrad", "mmx"], ["pavgw", "mmx"], # 0xe0
	["pmulhuw", "mmx"], ["pmulhw", "mmx"], [33, "sse_table"], [34, "sse_table_flip"], # 0xe4
	["psubsb", "mmx"], ["psubsw", "mmx"], ["pminsw", "mmx"], ["por", "mmx"], # 0xe8
	["paddsb", "mmx"], ["paddsw", "mmx"], ["pmaxsw", "mmx"], ["pxor", "mmx"], # 0xec
	[35, "sse_table"], ["psllw", "mmx"], ["pslld", "mmx"], ["psllq", "mmx"], # 0xf0
	["pmuludq", "mmx"], ["pmaddwd", "mmx"], ["psadbw", "mmx"], [36, "sse_table"], # 0xf4
	["psubb", "mmx"], ["psubw", "mmx"], ["psubd", "mmx"], ["psubq", "mmx"], # 0xf8
	["paddb", "mmx"], ["paddw", "mmx"], ["paddd", "mmx"], ["ud", "no_operands"] # 0xfc
]

ThreeByte0F38Map = [
	[0x00, "pshufb", "mmx"], [0x01, "phaddw", "mmx"], [0x02, "phaddd", "mmx"], [0x03, "phaddsw", "mmx"],
	[0x04, "pmaddubsw", "mmx"], [0x05, "phsubw", "mmx"], [0x06, "phsubd", "mmx"], [0x07, "phsubsw", "mmx"],
	[0x08, "psignb", "mmx"], [0x09, "psignw", "mmx"], [0x0a, "psignd", "mmx"], [0x0b, "pmulhrsw", "mmx"],
	[0x10, "pblendvb", "mmx_sseonly"], [0x14, "blendvps", "mmx_sseonly"], [0x15, "blendvpd", "mmx_sseonly"],
	[0x17, "ptest", "mmx_sseonly"], [0x1c, "pabsb", "mmx"], [0x1d, "pabsw", "mmx"], [0x1e, "pabsd", "mmx"],
	[0x20, 37, "sse_table"], [0x21, 38, "sse_table"], [0x22, 39, "sse_table"], [0x23, 40, "sse_table"],
	[0x24, 41, "sse_table"], [0x25, 42, "sse_table"], [0x28, "pmuldq", "mmx_sseonly"], [0x29, "pcmpeqq", "mmx_sseonly"],
	[0x2a, 43, "sse_table"], [0x2b, "packusdw", "mmx_sseonly"], [0x30, 44, "sse_table"], [0x31, 45, "sse_table"],
	[0x32, 46, "sse_table"], [0x33, 47, "sse_table"], [0x34, 48, "sse_table"], [0x35, 49, "sse_table"],
	[0x37, "pcmpgtq", "mmx_sseonly"], [0x38, "pminsb", "mmx_sseonly"], [0x39, "pminsd", "mmx_sseonly"],
	[0x3a, "pminuw", "mmx_sseonly"], [0x3b, "pminud", "mmx_sseonly"], [0x3c, "pmaxsb", "mmx_sseonly"],
	[0x3d, "pmaxsd", "mmx_sseonly"], [0x3e, "pmaxuw", "mmx_sseonly"], [0x3f, "pmaxud", "mmx_sseonly"],
	[0x40, "pmulld", "mmx_sseonly"], [0x41, "phminposuw", "mmx_sseonly"], [0xf0, "crc32", "crc32_8"], [0xf1, "crc32", "crc32_v"]
]

ThreeByte0F3AMap = [
	[0x08, "roundps", "mmx_sseonly"], [0x09, "roundpd", "mmx_sseonly"], [0x0a, 50, "sse_table"], [0x0b, 51, "sse_table"],
	[0x0c, "blendps", "mmx_sseonly"], [0x0d, "blendpd", "mmx_sseonly"], [0x0e, "pblendw", "mmx_sseonly"], [0x0f, "palignr", "mmx"],
	[0x14, 52, "sse_table_mem8_flip"], [0x15, 53, "sse_table"], [0x16, 54, "sse_table_incop64_flip"],
	[0x17, 55, "sse_table_flip"], [0x20, 56, "sse_table_mem8"], [0x21, 57, "sse_table"], [0x22, 58, "sse_table_incop64"],
	[0x40, "dpps", "mmx_sseonly"], [0x41, "dppd", "mmx_sseonly"], [0x42, "mpsadbw", "mmx_sseonly"],
	[0x60, "pcmpestrm", "mmx_sseonly"], [0x61, "pcmpestri", "mmx_sseonly"], [0x62, "pcmpistrm", "mmx_sseonly"],
	[0x63, "pcmpistri", "mmx_sseonly"]
]

FPUMemOpcodeMap = [
	[ # 0xd8
		["fadd", "mem_32"], ["fmul", "mem_32"], ["fcom", "mem_32"], ["fcomp", "mem_32"], # 0
		["fsub", "mem_32"], ["fsubr", "mem_32"], ["fdiv", "mem_32"], ["fdivr", "mem_32"] # 4
	],
	[ # 0xd9
		["fld", "mem_32"], [None, None], ["fst", "mem_32"], ["fstp", "mem_32"], # 0
		["fldenv", "mem_floatenv"], ["fldcw", "mem_16"], ["fstenv", "mem_floatenv"], ["fstcw", "mem_16"] # 4
	],
	[ # 0xda
		["fiadd", "mem_32"], ["fimul", "mem_32"], ["ficom", "mem_32"], ["ficomp", "mem_32"], # 0
		["fisub", "mem_32"], ["fisubr", "mem_32"], ["fidiv", "mem_32"], ["fidivr", "mem_32"] # 4
	],
	[ # 0xdb
		["fild", "mem_32"], ["fisttp", "mem_32"], ["fist", "mem_32"], ["fistp", "mem_32"], # 0
		[None, None], ["fld", "mem_80"], [None, None], ["fstp", "mem_80"] # 4
	],
	[ # 0xdc
		["fadd", "mem_64"], ["fmul", "mem_64"], ["fcom", "mem_64"], ["fcomp", "mem_64"], # 0
		["fsub", "mem_64"], ["fsubr", "mem_64"], ["fdiv", "mem_64"], ["fdivr", "mem_64"] # 4
	],
	[ # 0xdd
		["fld", "mem_64"], ["fisttp", "mem_64"], ["fst", "mem_64"], ["fstp", "mem_64"], # 0
		["frstor", "mem_floatsave"], [None, None], ["fsave", "mem_floatsave"], ["fstsw", "mem_16"] # 4
	],
	[ # 0xde
		["fiadd", "mem_16"], ["fimul", "mem_16"], ["ficom", "mem_16"], ["ficomp", "mem_16"], # 0
		["fisub", "mem_16"], ["fisubr", "mem_16"], ["fidiv", "mem_16"], ["fidivr", "mem_16"] # 4
	],
	[ # 0xdf
		["fild", "mem_16"], ["fisttp", "mem_16"], ["fist", "mem_16"], ["fistp", "mem_16"], # 0
		["fbld", "mem_80"], ["fild", "mem_64"], ["fbstp", "mem_80"], ["fistp", "mem_64"] # 4
	]
]

FPURegOpcodeMap = [
	[ # 0xd8
		["fadd", "st0_fpureg"], ["fmul", "st0_fpureg"], ["fcom", "st0_fpureg"], ["fcomp", "st0_fpureg"], # 0
		["fsub", "st0_fpureg"], ["fsubr", "st0_fpureg"], ["fdiv", "st0_fpureg"], ["fdivr", "st0_fpureg"] # 4
	],
	[ # 0xd9
		["fld", "fpureg"], ["fxch", "st0_fpureg"], [12, "reggroup_no_operands"], [None, None], # 0
		[13, "reggroup_no_operands"], [14, "reggroup_no_operands"], [15, "reggroup_no_operands"], [16, "reggroup_no_operands"] # 4
	],
	[ # 0xda
		["fcmovb", "st0_fpureg"], ["fcmove", "st0_fpureg"], ["fcmovbe", "st0_fpureg"], ["fcmovu", "st0_fpureg"], # 0
		[None, None], [17, "reggroup_no_operands"], [None, None], [None, None] # 4
	],
	[ # 0xdb
		["fcmovnb", "st0_fpureg"], ["fcmovne", "st0_fpureg"], ["fcmovnbe", "st0_fpureg"], ["fcmovnu", "st0_fpureg"], # 0
		[18, "reggroup_no_operands"], ["fucomi", "st0_fpureg"], ["fcomi", "st0_fpureg"], [21, "reggroup_no_operands"] # 4
	],
	[ # 0xdc
		["fadd", "fpureg_st0"], ["fmul", "fpureg_st0"], [None, None], [None, None], # 0
		["fsubr", "fpureg_st0"], ["fsub", "fpureg_st0"], ["fdivr", "fpureg_st0"], ["fdiv", "fpureg_st0"] # 4
	],
	[ # 0xdd
		["ffree", "fpureg"], [None, None], ["fst", "fpureg"], ["fstp", "fpureg"], # 0
		["fucom", "st0_fpureg"], ["fucomp", "st0_fpureg"], [None, None], [22, "reggroup_no_operands"] # 4
	],
	[ # 0xde
		["faddp", "fpureg_st0"], ["fmulp", "fpureg_st0"], [None, None], [19, "reggroup_no_operands"], # 0
		["fsubrp", "fpureg_st0"], ["fsubp", "fpureg_st0"], ["fdivrp", "fpureg_st0"], ["fdivp", "fpureg_st0"] # 4
	],
	[ # 0xdf
		["ffreep", "fpureg"], [None, None], [None, None], [None, None], # 0
		[20, "reggroup_ax"], ["fucomip", "st0_fpureg"], ["fcomip", "st0_fpureg"], [23, "reggroup_no_operands"] # 4
	]
]

GroupOperations = [
	["add", "or", "adc", "sbb", "and", "sub", "xor", "cmp"], # Group 0
	["rol", "ror", "rcl", "rcr", "shl", "shr", "shl", "sar"], # Group 1
	["mov", None, None, None, None, None, None, None], # Group 2
	["test", "test", "not", "neg", "mul", "imul", "div", "idiv"], # Group 3
	["inc", "dec", None, None, None, None, None, None], # Group 4
	["inc", "dec", "calln", "callf", "jmpn", "jmpf", "push", None], # Group 5
	["sldt", "str", "lldt", "ltr", "verr", "verw", None, None], # Group 6
	["sgdt", "sidt", "lgdt", "lidt", "smsw", None, "lmsw", "invlpg"], # Group 7
	["prefetch", "prefetchw", "prefetch", "prefetch", "prefetch", "prefetch", "prefetch", "prefetch"], # Group 8
	["prefetchnta", "prefetcht0", "prefetcht1", "prefetcht2", "mmxnop", "mmxnop", "mmxnop", "mmxnop"], # Group 9
	["mmxnop", "mmxnop", "mmxnop", "mmxnop", "mmxnop", "mmxnop", "mmxnop", "mmxnop"], # Group 10
	[None, None, None, None, "bt", "bts", "btr", "btc"], # Group 11
	["fnop", None, None, None, None, None, None, None], # Group 12
	["fchs", "fabs", None, None, "ftst", "fxam", None, None], # Group 13
	["fld1", "fldl2t", "fldl2e", "fldpi", "fldlg2", "fldln2", "fldz", None], # Group 14
	["f2xm1", "fyl2x", "fptan", "fpatan", "fxtract", "fprem1", "fdecstp", "fincstp"], # Group 15
	["fprem", "fyl2xp1", "fsqrt", "fsincos", "frndint", "fscale", "fsin", "fcos"], # Group 16
	[None, "fucompp", None, None, None, None, None, None], # Group 17
	["feni", "fdisi", "fclex", "finit", "fsetpm", "frstpm", None, None], # Group 18
	[None, "fcompp", None, None, None, None, None, None], # Group 19
	["fstsw", "fstdw", "fstsg", None, None, None, None, None], # Group 20
	[None, None, None, None, "frint2", None, None, None], # Group 21
	[None, None, None, None, "frichop", None, None, None], # Group 22
	[None, None, None, None, "frinear", None, None, None], # Group 23
	["fxsave", "fxrstor", "ldmxcsr", "stmxcsr", "xsave", "xrstor", None, "clflush"], # Group 24
	[None, None, None, None, None, "lfence", "mfence", "sfence"] # Group 25
]

Group0F01RegOperations = [
	[None, "vmcall", "vmlaunch", "vmresume", "vmxoff", None, None, None],
	["monitor", "mwait", None, None, None, None, None, None],
	["xgetbv", "xsetbv", None, None, None, None, None, None],
	[None, None, None, None, None, None, None, None],
	[None, None, None, None, None, None, None, None],
	[None, None, None, None, None, None, None, None],
	[None, None, None, None, None, None, None, None],
	["swapgs", "rdtscp", None, None, None, None, None, None]
]

MMXGroupOperations = [
	[ # Group 0
		[None, None], [None, None], ["psrlw", "psrlw"], [None, None],
		["psraw", "psraw"], [None, None], ["psllw", "psllw"], [None, None]
	],
	[ # Group 1
		[None, None], [None, None], ["psrld", "psrld"], [None, None],
		["psrad", "psrad"], [None, None], ["pslld", "pslld"], [None, None]
	],
	[ # Group 2
		[None, None], [None, None], ["psrlq", "psrlq"], [None, "psrldq"],
		[None, None], [None, None], ["psllq", "psllq"], [None, "pslldq"]
	]
]

SSETable = [
	[ # Entry 0
		[["movups", "sse_128", "sse_128"], ["movupd", "sse_128", "sse_128"], ["movsd", "sse_128", "sse_128"], ["movss", "sse_128", "sse_128"]],
		[["movups", "sse_128", "sse_128"], ["movupd", "sse_128", "sse_128"], ["movsd", "sse_128", "sse_64"], ["movss", "sse_128", "sse_32"]]
	],
	[ # Entry 1
		[["movhlps", "sse_128", "sse_128"], [None, 0, 0], ["movddup", "sse_128", "sse_128"], ["movsldup", "sse_128", "sse_128"]],
		[["movlps", "sse_128", "sse_64"], ["movlpd", "sse_128", "sse_64"], ["movddup", "sse_128", "sse_64"], ["movsldup", "sse_128", "sse_128"]]
	],
	[ # Entry 2
		[[None, 0, 0], [None, 0, 0], [None, 0, 0], [None, 0, 0]],
		[["movlps", "sse_128", "sse_64"], ["movlpd", "sse_128", "sse_64"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 3
		[["unpcklps", "sse_128", "sse_128"], ["unpcklpd", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[["unpcklps", "sse_128", "sse_128"], ["unpcklpd", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 4
		[["unpckhps", "sse_128", "sse_128"], ["unpckhpd", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[["unpckhps", "sse_128", "sse_128"], ["unpckhpd", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 5
		[["movlhps", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0], ["movshdup", "sse_128", "sse_128"]],
		[["movhps", "sse_128", "sse_64"], ["movhpd", "sse_128", "sse_64"], [None, 0, 0], ["movshdup", "sse_128", "sse_128"]]
	],
	[ # Entry 6
		[[None, 0, 0], [None, 0, 0], [None, 0, 0], [None, 0, 0]],
		[["movhps", "sse_128", "sse_64"], ["movhpd", "sse_128", "sse_64"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 7
		[["movaps", "sse_128", "sse_128"], ["movapd", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[["movaps", "sse_128", "sse_128"], ["movapd", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 8
		[["cvtpi2ps", "sse_128", "mmx_64"], ["cvtpi2pd", "sse_128", "mmx_64"], ["cvtsi2sd", "sse_128", "gpr_32_or_64"], ["cvtsi2ss", "sse_128", "gpr_32_or_64"]],
		[["cvtpi2ps", "sse_128", "mmx_64"], ["cvtpi2pd", "sse_128", "mmx_64"], ["cvtsi2sd", "sse_128", "gpr_32_or_64"], ["cvtsi2ss", "sse_128", "gpr_32_or_64"]]
	],
	[ # Entry 9
		[[None, 0, 0], [None, 0, 0], [None, 0, 0], [None, 0, 0]],
		[["movntps", "sse_128", "sse_128"], ["movntpd", "sse_128", "sse_128"], ["movntsd", "sse_128", "sse_64"], ["movntss", "see_128", "sse_32"]]
	],
	[ # Entry 10
		[["cvttps2pi", "mmx_64", "sse_128"], ["cvttpd2pi", "mmx_64", "sse_128"], ["cvttsd2si", "gpr_32_or_64", "sse_128"], ["cvttss2si", "gpr_32_or_64", "sse_128"]],
		[["cvttps2pi", "mmx_64", "sse_64"], ["cvttpd2pi", "mmx_64", "sse_128"], ["cvttsd2si", "gpr_32_or_64", "sse_64"], ["cvttss2si", "gpr_32_or_64", "sse_32"]]
	],
	[ # Entry 11
		[["cvtps2pi", "mmx_64", "sse_128"], ["cvtpd2pi", "mmx_64", "sse_128"], ["cvtsd2si", "gpr_32_or_64", "sse_128"], ["cvtss2si", "gpr_32_or_64", "sse_128"]],
		[["cvtps2pi", "mmx_64", "sse_64"], ["cvtpd2pi", "mmx_64", "sse_128"], ["cvtsd2si", "gpr_32_or_64", "sse_64"], ["cvtss2si", "gpr_32_or_64", "sse_32"]]
	],
	[ # Entry 12
		[["ucomiss", "sse_128", "sse_128"], ["ucomisd", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[["ucomiss", "sse_128", "sse_32"], ["ucomisd", "sse_128", "sse_64"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 13
		[["comiss", "sse_128", "sse_128"], ["comisd", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[["comiss", "sse_128", "sse_32"], ["comisd", "sse_128", "sse_64"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 14
		[["movmskps", "gpr_32_or_64", "sse_128"], ["movmskpd", "gpr_32_or_64", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], [None, 0, 0], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 15
		[["cvtps2pd", "sse_128", "sse_128"], ["cvtpd2ps", "sse_128", "sse_128"], ["cvtsd2ss", "sse_128", "sse_128"], ["cvtss2sd", "sse_128", "sse_128"]],
		[["cvtps2pd", "sse_128", "sse_64"], ["cvtpd2ps", "sse_128", "sse_128"], ["cvtsd2ss", "sse_128", "sse_64"], ["cvtss2sd", "sse_128", "sse_32"]]
	],
	[ # Entry 16
		[["cvtdq2ps", "sse_128", "sse_128"], ["cvtps2dq", "sse_128", "sse_128"], [None, 0, 0], ["cvttps2dq", "sse_128", "sse_128"]],
		[["cvtdq2ps", "sse_128", "sse_128"], ["cvtps2dq", "sse_128", "sse_128"], [None, 0, 0], ["cvttps2dq", "sse_128", "sse_128"]]
	],
	[ # Entry 17
		[["punpcklbw", "mmx_64", "mmx_64"], ["punpcklbw", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[["punpcklbw", "mmx_64", "mmx_32"], ["punpcklbw", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 18
		[["punpcklwd", "mmx_64", "mmx_64"], ["punpcklwd", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[["punpcklwd", "mmx_64", "mmx_32"], ["punpcklwd", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 19
		[["punpckldq", "mmx_64", "mmx_64"], ["punpckldq", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[["punpckldq", "mmx_64", "mmx_32"], ["punpckldq", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 20
		[[["movd", "movq"], "mmx_64", "gpr_32_or_64"], [["movd", "movq"], "sse_128", "gpr_32_or_64"], [None, 0, 0], [None, 0, 0]],
		[[["movd", "movq"], "mmx_64", "gpr_32_or_64"], [["movd", "movq"], "sse_128", "gpr_32_or_64"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 21
		[["movq", "mmx_64", "mmx_64"], ["movdqa", "sse_128", "sse_128"], [None, 0, 0], ["movdqu", "sse_128", "sse_128"]],
		[["movq", "mmx_64", "mmx_64"], ["movdqa", "sse_128", "sse_128"], [None, 0, 0], ["movdqu", "sse_128", "sse_128"]]
	],
	[ # Entry 22
		[["pshufw", "mmx_64", "mmx_64"], ["pshufd", "sse_128", "sse_128"], ["pshuflw", "sse_128", "sse_128"], ["pshufhw", "sse_128", "sse_128"]],
		[["pshufw", "mmx_64", "mmx_64"], ["pshufd", "sse_128", "sse_128"], ["pshuflw", "sse_128", "sse_128"], ["pshufhw", "sse_128", "sse_128"]]
	],
	[ # Entry 23
		[[None, 0, 0], ["haddpd", "sse_128", "sse_128"], ["haddps", "sse_128", "sse_128"], [None, 0, 0]],
		[[None, 0, 0], ["haddpd", "sse_128", "sse_128"], ["haddps", "sse_128", "sse_128"], [None, 0, 0]]
	],
	[ # Entry 24
		[[None, 0, 0], ["hsubpd", "sse_128", "sse_128"], ["hsubps", "sse_128", "sse_128"], [None, 0, 0]],
		[[None, 0, 0], ["hsubpd", "sse_128", "sse_128"], ["hsubps", "sse_128", "sse_128"], [None, 0, 0]]
	],
	[ # Entry 25
		[[["movd", "movq"], "mmx_64", "gpr_32_or_64"], [["movd", "movq"], "sse_128", "gpr_32_or_64"], [None, 0, 0], ["movq", "sse_128_flip", "sse_128_flip"]],
		[[["movd", "movq"], "mmx_64", "gpr_32_or_64"], [["movd", "movq"], "sse_128", "gpr_32_or_64"], [None, 0, 0], ["movq", "sse_128_flip", "sse_128_flip"]]
	],
	[ # Entry 26
		[["cmpps", "sse_128", "sse_128"], ["cmppd", "sse_128", "sse_128"], ["cmpsd", "sse_128", "sse_128"], ["cmpss", "sse_128", "sse_128"]],
		[["cmpps", "sse_128", "sse_128"], ["cmppd", "sse_128", "sse_128"], ["cmpsd", "sse_128", "sse_64"], ["cmpss", "sse_128", "sse_32"]]
	],
	[ # Entry 27
		[["pinsrw", "mmx_64", "gpr_32_or_64"], ["pinsrw", "sse_128", "gpr_32_or_64"], [None, 0, 0], [None, 0, 0]],
		[["pinsrw", "mmx_64", "gpr_32_or_64"], ["pinsrw", "sse_128", "gpr_32_or_64"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 28
		[["pextrw", "gpr_32_or_64", "mmx_64"], ["pextrw", "gpr_32_or_64", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[["pextrw", "gpr_32_or_64", "mmx_64"], ["pextrw", "gpr_32_or_64", "sse_128"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 29
		[["shufps", "sse_128", "sse_128"], ["shufpd", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[["shufps", "sse_128", "sse_128"], ["shufpd", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 30
		[[None, 0, 0], ["addsubpd", "sse_128", "sse_128"], ["addsubps", "sse_128", "sse_128"], [None, 0, 0]],
		[[None, 0, 0], ["addsubpd", "sse_128", "sse_128"], ["addsubps", "sse_128", "sse_128"], [None, 0, 0]]
	],
	[ # Entry 31
		[[None, 0, 0], ["movq", "sse_128_flip", "sse_128_flip"], ["movdq2q", "mmx_64", "sse_128"], ["movq2dq", "sse_128", "mmx_64"]],
		[[None, 0, 0], ["movq", "sse_128_flip", "sse_128_flip"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 32
		[["pmovmskb", "gpr_32_or_64", "mmx_64"], ["pmovmskb", "gpr_32_or_64", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], [None, 0, 0], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 33
		[[None, 0, 0], ["cvttpd2dq", "sse_128", "sse_128"], ["cvtpd2dq", "sse_128", "sse_128"], ["cvtdq2pd", "sse_128", "sse_128"]],
		[[None, 0, 0], ["cvttpd2dq", "sse_128", "sse_128"], ["cvtpd2dq", "sse_128", "sse_128"], ["cvtdq2pd", "sse_128", "sse_128"]]
	],
	[ # Entry 34
		[[None, 0, 0], [None, 0, 0], [None, 0, 0], [None, 0, 0]],
		[["movntq", "mmx_64", "mmx_64"], ["movntdq", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 35
		[[None, 0, 0], [None, 0, 0], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], [None, 0, 0], ["lddqu", "sse_128", "sse_128"], [None, 0, 0]]
	],
	[ # Entry 36
		[["maskmovq", "mmx_64", "mmx_64"], ["maskmovdqu", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], [None, 0, 0], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 37
		[[None, 0, 0], ["pmovsxbw", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["pmovsxbw", "sse_128", "sse_64"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 38
		[[None, 0, 0], ["pmovsxbd", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["pmovsxbd", "sse_128", "sse_32"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 39
		[[None, 0, 0], ["pmovsxbq", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["pmovsxbq", "sse_128", "sse_16"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 40
		[[None, 0, 0], ["pmovsxwd", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["pmovsxwd", "sse_128", "sse_64"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 41
		[[None, 0, 0], ["pmovsxwq", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["pmovsxwq", "sse_128", "sse_32"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 42
		[[None, 0, 0], ["pmovsxdq", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["pmovsxdq", "sse_128", "sse_64"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 43
		[[None, 0, 0], [None, 0, 0], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["movntdqa", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 44
		[[None, 0, 0], ["pmovzxbw", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["pmovzxbw", "sse_128", "sse_64"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 45
		[[None, 0, 0], ["pmovzxbd", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["pmovzxbd", "sse_128", "sse_32"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 46
		[[None, 0, 0], ["pmovzxbq", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["pmovzxbq", "sse_128", "sse_16"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 47
		[[None, 0, 0], ["pmovzxwd", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["pmovzxwd", "sse_128", "sse_64"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 48
		[[None, 0, 0], ["pmovzxwq", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["pmovzxwq", "sse_128", "sse_32"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 49
		[[None, 0, 0], ["pmovzxdq", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["pmovzxdq", "sse_128", "sse_64"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 50
		[[None, 0, 0], ["roundss", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["roundss", "sse_128", "sse_32"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 51
		[[None, 0, 0], ["roundsd", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["roundsd", "sse_128", "sse_64"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 52
		[[None, 0, 0], ["pextrb", "sse_128", "gpr_32_or_64"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["pextrb", "sse_128", "gpr_32_or_64"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 53
		[[None, 0, 0], ["pextrw", "gpr_32_or_64", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["pextrw", "sse_16", "sse_128"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 54
		[[None, 0, 0], [["pextrd", "pextrq"], "sse_128", "gpr_32_or_64"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], [["pextrd", "pextrq"], "sse_128", "gpr_32_or_64"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 55
		[[None, 0, 0], ["extractps", "sse_128", "gpr_32_or_64"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["extractps", "sse_128", "sse_32"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 56
		[[None, 0, 0], ["pinsrb", "sse_128", "gpr_32_or_64"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["pinsrb", "sse_128", "gpr_32_or_64"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 57
		[[None, 0, 0], ["insertps", "sse_128", "sse_128"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], ["insertps", "sse_128", "sse_32"], [None, 0, 0], [None, 0, 0]]
	],
	[ # Entry 58
		[[None, 0, 0], [["pinsrd", "pinsrq"], "sse_128", "gpr_32_or_64"], [None, 0, 0], [None, 0, 0]],
		[[None, 0, 0], [["pinsrd", "pinsrq"], "sse_128", "gpr_32_or_64"], [None, 0, 0], [None, 0, 0]]
	]
]

Sparse3DNowOpcodes = [
	[0x0c, "pi2fw"], [0x0d, "pi2fd"],
	[0x1c, "pf2iw"], [0x1d, "pf2id"],
	[0x86, "pfrcpv"], [0x87, "pfrsqrtv"], [0x8a, "pfnacc"], [0x8e, "pfpnacc"],
	[0x90, "pfcmpge"], [0x94, "pfmin"], [0x96, "pfrcp"], [0x97, "pfrsqrt"], [0x9a, "pfsub"], [0x9e, "pfadd"],
	[0xa0, "pfcmpgt"], [0xa4, "pfmax"], [0xa6, "pfrcpit1"], [0xa7, "pfrsqit1"], [0xaa, "pfsubr"], [0xae, "pfacc"],
	[0xb0, "pfcmpeq"], [0xb4, "pfmul"], [0xb6, "pfrcpit2"], [0xb7, "pmulhrw"], [0xbb, "pswapd"], [0xbf, "pavgusb"]
]

Reg8List = ["al", "cl", "dl", "bl", "ah", "ch", "dh", "bh"]
Reg8List64 = ["al", "cl", "dl", "bl", "spl", "bpl", "sil", "dil", "r8b", "r9b", "r10b", "r11b", "r12b", "r13b", "r14b", "r15b"]
Reg16List = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di", "r8w", "r9w", "r10w", "r11w", "r12w", "r13w", "r14w", "r15w"]
Reg32List = ["eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi", "r8d", "r9d", "r10d", "r11d", "r12d", "r13d", "r14d", "r15d"]
Reg64List = ["rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi", "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"]
MMXRegList = ["mm0", "mm1", "mm2", "mm3", "mm4", "mm5", "mm6", "mm7", "mm0", "mm1", "mm2", "mm3", "mm4", "mm5", "mm6", "mm7"]
XMMRegList = ["xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5", "xmm6", "xmm7", "xmm8", "xmm9", "xmm10", "xmm11", "xmm12", "xmm13", "xmm14", "xmm15"]
FPURegList = ["st0", "st1", "st2", "st3", "st4", "st5", "st6", "st7", "st0", "st1", "st2", "st3", "st4", "st5", "st6", "st7"]

RM16Components = [["bx", "si", "ds"], ["bx", "di", "ds"], ["bp", "si", "ss"], ["bp", "di", "ss"], ["si", None, "ds"],
	["di", None, "ds"], ["bp", None, "ss"], ["bx", None, "ds"], [None, None, "ds"]]

class InstructionOperand:
	def __init__(self):
		self.operand = None
		self.components = [None, None]
		self.scale = 1
		self.size = 0
		self.immediate = 0
		self.segment = None
		self.rip_relative = False

class Instruction:
	def __init__(self):
		self.operation = None
		self.operands = [InstructionOperand(), InstructionOperand(), InstructionOperand()]
		self.flags = 0
		self.segment = None
		self.length = 0

	def finalize(self):
		while (len(self.operands) > 0) and (self.operands[-1].operand == None):
			self.operands.pop()

class DecodeState:
	def __init__(self):
		self.result = Instruction()
		self.opcode_offset = 0
		self.flags = 0
		self.invalid = False
		self.insufficient_length = False
		self.op_prefix = False
		self.rep = False
		self.using64 = False
		self.rex = False
		self.rex_rm1 = False
		self.rex_rm2 = False
		self.rex_reg = False

def get_byte_reg_list(state):
	if state.rex:
		return Reg8List64
	else:
		return Reg8List

def get_reg_list_for_final_op_size(state):
	if state.final_op_size == 1:
		return get_byte_reg_list(state)
	if state.final_op_size == 2:
		return Reg16List
	if state.final_op_size == 4:
		return Reg32List
	if state.final_op_size == 8:
		return Reg64List

def get_reg_list_for_addr_size(state):
	if state.addr_size == 2:
		return Reg16List
	if state.addr_size == 4:
		return Reg32List
	if state.addr_size == 8:
		return Reg64List

def get_final_op_size(state):
	if state.flags & DEC_FLAG_BYTE:
		return 1
	else:
		return state.op_size

def read8(state):
	if len(state.opcode) < 1:
		# Read past end of buffer, returning 0xcc from now on will guarantee exit
		state.invalid = True
		state.insufficient_length = True
		state.opcode = ""
		return 0xcc

	val = ord(state.opcode[0])
	state.opcode = state.opcode[1:]
	state.prev_opcode = val
	state.opcode_offset += 1
	return val

def peek8(state):
	if len(state.opcode) < 1:
		# Read past end of buffer, returning 0xcc from now on will guarantee exit
		state.invalid = True
		state.insufficient_length = True
		state.opcode = ""
		return 0xcc

	val = ord(state.opcode[0])
	return val

def read16(state):
	val = read8(state)
	val |= read8(state) << 8
	return val

def read32(state):
	val = read16(state)
	val |= read16(state) << 16
	return val

def read64(state):
	val = read32(state)
	val |= read32(state) << 32
	return val

def read8_signed(state):
	val = read8(state)
	if val & 0x80:
		val = -(0x100 - val)
	return val

def read16_signed(state):
	val = read16(state)
	if val & 0x8000:
		val = -(0x10000 - val)
	return val

def read32_signed(state):
	val = read32(state)
	if val & 0x80000000:
		val = -(0x100000000 - val)
	return val

def read_final_op_size(state):
	if state.flags & DEC_FLAG_IMM_SX:
		return read8_signed(state)
	if state.final_op_size == 1:
		return read8(state)
	if state.final_op_size == 2:
		return read16(state)
	if state.final_op_size == 4:
		return read32(state)
	if state.final_op_size == 8:
		return read32_signed(state)

def read_addr_size(state):
	if state.addr_size == 2:
		return read16(state)
	if state.addr_size == 4:
		return read32(state)
	if state.addr_size == 8:
		return read64(state)

def read_signed_final_op_size(state):
	if state.final_op_size == 1:
		return read8_signed(state)
	if state.final_op_size == 2:
		return read16_signed(state)
	if state.final_op_size == 4:
		return read32_signed(state)
	if state.final_op_size == 8:
		return read32_signed(state)

def update_operation_for_addr_size(state):
	if state.addr_size == 4:
		state.result.operation = state.result.operation[1]
	elif state.addr_size == 8:
		state.result.operation = state.result.operation[2]
	else:
		state.result.operation = state.result.operation[0]

def process_encoding(state, encoding):
	state.result.operation = encoding[0]
	encoder = encoding[1]

	state.flags = Encoding[encoder][1]
	if state.using64 and (state.flags & DEC_FLAG_INVALID_IN_64BIT):
		state.invalid = True
		return
	if state.using64 and (state.flags & DEC_FLAG_DEFAULT_TO_64BIT):
		if state.op_prefix:
			state.op_size = 2
		else:
			state.op_size = 8
	state.final_op_size = get_final_op_size(state)

	if state.flags & DEC_FLAG_FLIP_OPERANDS:
		state.operand0 = state.result.operands[1]
		state.operand1 = state.result.operands[0]
	else:
		state.operand0 = state.result.operands[0]
		state.operand1 = state.result.operands[1]

	if state.flags & DEC_FLAG_FORCE_16BIT:
		state.final_op_size = 2

	if state.flags & DEC_FLAG_OPERATION_OP_SIZE:
		if state.final_op_size == 4:
			state.result.operation = state.result.operation[1]
		elif state.final_op_size == 8:
			if len(state.result.operation) < 3:
				state.final_op_size = 4
				state.result.operation = state.result.operation[1]
			else:
				state.result.operation = state.result.operation[2]
		else:
			state.result.operation = state.result.operation[0]

	if state.flags & DEC_FLAG_REP:
		if state.rep != None:
			state.result.flags |= FLAG_REP
	elif state.flags & DEC_FLAG_REP_COND:
		if state.rep == "repne":
			state.result.flags |= FLAG_REPNE
		elif state.rep == "repe":
			state.result.flags |= FLAG_REPE

	Encoding[encoder][0](state)

	if state.result.operation == None:
		state.invalid = True

	if state.result.flags & FLAG_LOCK:
		# Ensure instruction allows lock and it has proper semantics
		if (state.flags & DEC_FLAG_LOCK) == 0:
			state.invalid = True
		elif state.result.operation == "cmp":
			state.invalid = True
		elif (state.result.operands[0].operand != "mem") and (state.result.operands[1].operand != "mem"):
			state.invalid = True

def process_opcode(state, map, opcode):
	process_encoding(state, map[opcode])

def process_sparse_opcode(state, map, opcode):
	state.result.operation = None
	min = 0
	max = len(map) - 1
	while min <= max:
		i = (min + max) / 2
		if opcode > map[i][0]:
			min = i + 1
		elif opcode < map[i][0]:
			max = i - 1
		else:
			process_encoding(state, [map[i][1], map[i][2]])
			break

def get_final_segment(state, seg):
	if state.result.segment == None:
		return seg
	else:
		return state.result.segment

def set_mem_operand(state, oper, rmdef, immed):
	oper.operand = "mem"
	oper.components = [rmdef[0], rmdef[1]]
	oper.immediate = immed
	oper.segment = get_final_segment(state, rmdef[2])

def decode_rm(state, rm_oper, reg_list, rm_size):
	rm_byte = read8(state)
	mod = rm_byte >> 6
	rm = rm_byte & 7
	reg_field = (rm_byte >> 3) & 7

	rm_oper.size = rm_size
	if state.addr_size == 2:
		if mod == 0:
			if rm == 6:
				rm = 8
				set_mem_operand(state, rm_oper, RM16Components[rm], read16(state))
			else:
				set_mem_operand(state, rm_oper, RM16Components[rm], 0)
		elif mod == 1:
			set_mem_operand(state, rm_oper, RM16Components[rm], read8_signed(state))
		elif mod == 2:
			set_mem_operand(state, rm_oper, RM16Components[rm], read16_signed(state))
		elif mod == 3:
			rm_oper.operand = reg_list[rm]
		if rm_oper.components[0] == None:
			rm_oper.immediate &= 0xffff
	else:
		addr_reg_list = get_reg_list_for_addr_size(state)
		if state.rex_rm1:
			rm_reg1_offset = 8
		else:
			rm_reg1_offset = 0
		if state.rex_rm2:
			rm_reg2_offset = 8
		else:
			rm_reg2_offset = 0
		seg = None
		rm_oper.operand = "mem"
		if (mod != 3) and (rm == 4):
			# SIB byte present
			sib_byte = read8(state)
			base = sib_byte & 7
			index = (sib_byte >> 3) & 7
			rm_oper.scale = 1 << (sib_byte >> 6)
			if (mod != 0) or (base != 5):
				rm_oper.components[0] = addr_reg_list[base + rm_reg1_offset]
			if (index + rm_reg2_offset) != 4:
				rm_oper.components[1] = addr_reg_list[index + rm_reg2_offset]
			if mod == 0:
				if base == 5:
					rm_oper.immediate = read32_signed(state)
			elif mod == 1:
				rm_oper.immediate = read8_signed(state)
			elif mod == 2:
				rm_oper.immediate = read32_signed(state)
			if ((base + rm_reg1_offset) == 4) or ((base + rm_reg1_offset) == 5):
				seg = "ss"
			else:
				seg = "ds"
		else:
			if mod == 0:
				if rm == 5:
					rm_oper.immediate = read32_signed(state)
					if state.addr_size == 8:
						rm_oper.rip_relative = True
						state.result.flags |= FLAG_64BIT_ADDRESS
				else:
					rm_oper.components[0] = addr_reg_list[rm + rm_reg1_offset]
				seg = "ds"
			elif mod == 1:
				rm_oper.components[0] = addr_reg_list[rm + rm_reg1_offset]
				rm_oper.immediate = read8_signed(state)
				if rm == 5:
					seg = "ss"
				else:
					seg = "ds"
			elif mod == 2:
				rm_oper.components[0] = addr_reg_list[rm + rm_reg1_offset]
				rm_oper.immediate = read32_signed(state)
				if rm == 5:
					seg = "ss"
				else:
					seg = "ds"
			elif mod == 3:
				rm_oper.operand = reg_list[rm + rm_reg1_offset]
		if seg != None:
			rm_oper.segment = get_final_segment(state, seg)

	return reg_field

def decode_rm_reg(state, rm_oper, rm_reg_list, rm_size, reg_oper, reg_list, reg_size):
	reg = decode_rm(state, rm_oper, rm_reg_list, rm_size)
	if reg_oper != None:
		if state.rex_reg:
			reg_offset = 8
		else:
			reg_offset = 0
		reg_oper.size = reg_size
		reg_oper.operand = reg_list[reg + reg_offset]

def set_operand_to_es_edi(state, oper, size):
	addr_reg_list = get_reg_list_for_addr_size(state)
	oper.operand = "mem"
	oper.components[0] = addr_reg_list[7]
	oper.size = size
	oper.segment = "es"

def set_operand_to_ds_esi(state, oper, size):
	addr_reg_list = get_reg_list_for_addr_size(state)
	oper.operand = "mem"
	oper.components[0] = addr_reg_list[6]
	oper.size = size
	oper.segment = get_final_segment(state, "ds")

def set_operand_to_imm_addr(state, oper):
	oper.operand = "mem"
	oper.immediate = read_addr_size(state)
	oper.segment = get_final_segment(state, "ds")
	oper.size = state.final_op_size

def set_operand_to_eax_final_op_size(state, oper):
	reg_list = get_reg_list_for_final_op_size(state)
	oper.operand = reg_list[0]
	oper.size = state.final_op_size

def set_operand_to_op_reg(state, oper):
	reg_list = get_reg_list_for_final_op_size(state)
	if state.rex_rm1:
		reg_offset = 8
	else:
		reg_offset = 0
	oper.operand = reg_list[(state.prev_opcode & 7) + reg_offset]
	oper.size = state.final_op_size

def set_operand_to_imm(state, oper):
	oper.operand = "imm"
	oper.size = state.final_op_size
	oper.immediate = read_final_op_size(state)

def set_operand_to_imm8(state, oper):
	oper.operand = "imm"
	oper.size = 1
	oper.immediate = read8(state)

def set_operand_to_imm16(state, oper):
	oper.operand = "imm"
	oper.size = 2
	oper.immediate = read16(state)

def decode_sse_prefix(state):
	if state.op_prefix:
		state.op_prefix = False
		return 1
	elif state.rep == "repne":
		state.rep = None
		return 2
	elif state.rep == "repe":
		state.rep = None
		return 3
	else:
		return 0

def get_size_for_sse_type(type):
	if type == 2:
		return 8
	elif type == 3:
		return 4
	else:
		return 16

def get_operand_for_sse_entry_type(state, type, operand_index):
	if type == "sse_128_flip":
		operand_index = 1 - operand_index
	if operand_index == 0:
		return state.operand0
	else:
		return state.operand1

def get_reg_list_for_sse_entry_type(state, type):
	if type == "mmx_32":
		return MMXRegList
	if type == "mmx_64":
		return MMXRegList
	if type == "gpr_32_or_64":
		if state.final_op_size == 8:
			return Reg64List
		else:
			return Reg32List
	return XMMRegList

def get_size_for_sse_entry_type(state, type):
	if type == "sse_16":
		return 2
	if type == "sse_32":
		return 4
	if type == "mmx_32":
		return 4
	if type == "sse_64":
		return 8
	if type == "mmx_64":
		return 8
	if type == "gpr_32_or_64":
		if state.final_op_size == 8:
			return 8
		else:
			return 4
	return 16

def update_operation_for_sse_entry_type(state, type):
	if (type == "gpr_32_or_64") and (state.final_op_size == 8):
		state.result.operation = state.result.operation[1]
	elif type == "gpr_32_or_64":
		state.result.operation = state.result.operation[0]

def invalid_decode(state):
	state.invalid = True

def decode_two_byte(state):
	opcode = read8(state)
	if opcode == 0x38:
		process_sparse_opcode(state, ThreeByte0F38Map, read8(state))
	elif opcode == 0x3a:
		process_sparse_opcode(state, ThreeByte0F3AMap, read8(state))
		set_operand_to_imm8(state, state.result.operands[2])
	else:
		process_opcode(state, TwoByteOpcodeMap, opcode)

def decode_fpu(state):
	mod_rm = peek8(state)
	reg = (mod_rm >> 3) & 7
	op = state.result.operation

	if (mod_rm & 0xc0) == 0xc0:
		map = FPURegOpcodeMap[op]
	else:
		map = FPUMemOpcodeMap[op]
	process_encoding(state, map[reg])

def decode_no_operands(state):
	pass

def decode_reg_rm(state):
	size = state.final_op_size
	reg_list = get_reg_list_for_final_op_size(state)
	if (state.flags & DEC_FLAG_REG_RM_SIZE_MASK) == DEC_FLAG_REG_RM_2X_SIZE:
		size *= 2
	elif (state.flags & DEC_FLAG_REG_RM_SIZE_MASK) == DEC_FLAG_REG_RM_FAR_SIZE:
		size += 2
	elif (state.flags & DEC_FLAG_REG_RM_SIZE_MASK) == DEC_FLAG_REG_RM_NO_SIZE:
		size = 0

	decode_rm_reg(state, state.operand1, reg_list, size, state.operand0, reg_list, state.final_op_size)

	if (size != state.final_op_size) and (state.operand1.operand != "mem"):
		state.invalid = True

def decode_reg_rm_imm(state):
	reg_list = get_reg_list_for_final_op_size(state)
	decode_rm_reg(state, state.operand1, reg_list, state.final_op_size,
		state.operand0, reg_list, state.final_op_size)
	set_operand_to_imm(state, state.result.operands[2])

def decode_rm_reg_imm8(state):
	reg_list = get_reg_list_for_final_op_size(state)
	decode_rm_reg(state, state.operand0, reg_list, state.final_op_size,
		state.operand1, reg_list, state.final_op_size)
	set_operand_to_imm8(state, state.result.operands[2])

def decode_rm_reg_cl(state):
	reg_list = get_reg_list_for_final_op_size(state)
	decode_rm_reg(state, state.operand0, reg_list, state.final_op_size,
		state.operand1, reg_list, state.final_op_size)
	state.result.operands[2].operand = "cl"
	state.result.operands[2].size = 1

def decode_eax_imm(state):
	set_operand_to_eax_final_op_size(state, state.operand0)
	set_operand_to_imm(state, state.operand1)

def decode_push_pop_seg(state):
	offset = 0
	if state.prev_opcode >= 0xa0: # FS/GS
		offset = -16
	state.operand0.operand = ["es", "cs", "ss", "ds", "fs", "gs"][(state.prev_opcode >> 3) + offset]
	state.operand0.size = state.final_op_size

def decode_op_reg(state):
	set_operand_to_op_reg(state, state.operand0)

def decode_eax_op_reg(state):
	set_operand_to_eax_final_op_size(state, state.operand0)
	set_operand_to_op_reg(state, state.operand1)

def decode_op_reg_imm(state):
	set_operand_to_op_reg(state, state.operand0)
	state.operand1.operand = "imm"
	state.operand1.size = state.final_op_size
	if state.final_op_size == 8:
		state.operand1.immediate = read64(state)
	else:
		state.operand1.immediate = read_final_op_size(state)

def decode_nop(state):
	if state.rex_rm1:
		state.result.operation = "xchg"
		set_operand_to_eax_final_op_size(state, state.operand0)
		set_operand_to_op_reg(state, state.operand1)

def decode_imm(state):
	set_operand_to_imm(state, state.operand0)

def decode_imm16_imm8(state):
	set_operand_to_imm16(state, state.operand0)
	set_operand_to_imm8(state, state.operand1)

def decode_edi_dx(state):
	set_operand_to_es_edi(state, state.operand0, state.final_op_size)
	state.operand1.operand = "dx"
	state.operand1.size = 2

def decode_dx_esi(state):
	state.operand0.operand = "dx"
	state.operand0.size = 2
	set_operand_to_ds_esi(state, state.operand1, state.final_op_size)

def decode_rel_imm(state):
	state.operand0.operand = "imm"
	state.operand0.size = state.op_size
	state.operand0.immediate = read_signed_final_op_size(state)
	state.operand0.immediate += state.addr + state.opcode_offset

def decode_rel_imm_addr_size(state):
	decode_rel_imm(state)
	update_operation_for_addr_size(state)

def decode_group_rm(state):
	reg_list = get_reg_list_for_final_op_size(state)
	reg_field = decode_rm(state, state.operand0, reg_list, state.final_op_size)
	state.result.operation = GroupOperations[state.result.operation][reg_field]

def decode_group_rm_imm(state):
	reg_list = get_reg_list_for_final_op_size(state)
	reg_field = decode_rm(state, state.operand0, reg_list, state.final_op_size)
	state.result.operation = GroupOperations[state.result.operation][reg_field]
	set_operand_to_imm(state, state.operand1)

def decode_group_rm_imm8v(state):
	reg_list = get_reg_list_for_final_op_size(state)
	reg_field = decode_rm(state, state.operand0, reg_list, state.final_op_size)
	state.result.operation = GroupOperations[state.result.operation][reg_field]
	set_operand_to_imm8(state, state.operand1)

def decode_group_rm_one(state):
	reg_list = get_reg_list_for_final_op_size(state)
	reg_field = decode_rm(state, state.operand0, reg_list, state.final_op_size)
	state.result.operation = GroupOperations[state.result.operation][reg_field]
	state.operand1.operand = "imm"
	state.operand1.size = 1
	state.operand1.immediate = 1

def decode_group_rm_cl(state):
	reg_list = get_reg_list_for_final_op_size(state)
	reg_field = decode_rm(state, state.operand0, reg_list, state.final_op_size)
	state.result.operation = GroupOperations[state.result.operation][reg_field]
	state.operand1.operand = "cl"
	state.operand1.size = 1

def decode_group_f6_f7(state):
	reg_list = get_reg_list_for_final_op_size(state)
	reg_field = decode_rm(state, state.operand0, reg_list, state.final_op_size)
	state.result.operation = GroupOperations[state.result.operation][reg_field]
	if state.result.operation == "test":
		set_operand_to_imm(state, state.operand1)
	# Check for valid locking semantics
	if (state.result.flags & FLAG_LOCK) and (state.result.operation != "not") and (state.result.operation != "neg"):
		state.invalid = True

def decode_group_ff(state):
	if state.using64:
		# Default to 64-bit for jumps and calls and pushes
		rm = peek8(state)
		reg_field = (rm >> 3) & 7
		if (reg_field == 2) or (reg_field == 4):
			if state.op_prefix:
				state.final_op_size = 4
				state.op_size = 4
			else:
				state.final_op_size = 8
				state.op_size = 8
		elif reg_field == 6:
			if state.op_prefix:
				state.final_op_size = 2
				state.op_size = 2
			else:
				state.final_op_size = 8
				state.op_size = 8
	reg_list = get_reg_list_for_final_op_size(state)
	reg_field = decode_rm(state, state.operand0, reg_list, state.final_op_size)
	state.result.operation = GroupOperations[state.result.operation][reg_field]
	# Check for valid far jump/call semantics
	if (state.result.operation == "callf") or (state.result.operation == "jmpf"):
		if state.operand0.operand != "mem":
			state.invalid = True
		state.operand0.size += 2
	# Check for valid locking semantics
	if (state.result.flags & FLAG_LOCK) and (state.result.operation != "inc") and (state.result.operation != "dec"):
		state.invalid = True

def decode_group_0f00(state):
	rm = peek8(state)
	mod_field = (rm >> 6) & 3
	reg_field = (rm >> 3) & 7
	if ((mod_field != 3) and (reg_field < 2)) or ((reg_field >= 2) and (reg_field <= 5)):
		state.final_op_size = 2
	reg_list = get_reg_list_for_final_op_size(state)
	reg_field = decode_rm(state, state.operand0, reg_list, state.final_op_size)
	state.result.operation = GroupOperations[state.result.operation][reg_field]

def decode_group_0f01(state):
	rm = peek8(state)
	mod_field = (rm >> 6) & 3
	reg_field = (rm >> 3) & 7
	rm_field = rm & 7

	if (mod_field == 3) and (reg_field != 4) and (reg_field != 6):
		state.result.operation = Group0F01RegOperations[reg_field][rm_field]
		read8(state)
	else:
		if reg_field < 4:
			if state.using64:
				state.final_op_size = 10
			else:
				state.final_op_size = 6
		elif ((mod_field != 3) and (reg_field == 4)) or (reg_field == 6):
			state.final_op_size = 2
		elif reg_field == 7:
			state.final_op_size = 1
		reg_list = get_reg_list_for_final_op_size(state)
		reg_field = decode_rm(state, state.operand0, reg_list, state.final_op_size)
		state.result.operation = GroupOperations[state.result.operation][reg_field]

def decode_group_0fae(state):
	rm = peek8(state)
	mod_field = (rm >> 6) & 3
	reg_field = (rm >> 3) & 7

	if mod_field == 3:
		state.result.operation = GroupOperations[state.result.operation + 1][reg_field]
		read8(state)
	else:
		if (reg_field & 2) == 0:
			state.final_op_size = 512
		elif (reg_field & 6) == 2:
			state.final_op_size = 4
		else:
			state.final_op_size = 1
		reg_list = get_reg_list_for_final_op_size(state)
		reg_field = decode_rm(state, state.operand0, reg_list, state.final_op_size)
		state.result.operation = GroupOperations[state.result.operation][reg_field]

def decode_0fb8(state):
	if state.rep != "repe":
		if state.using64:
			if state.op_prefix:
				state.op_size = 4
			else:
				state.op_size = 8
		state.final_op_size = get_final_op_size(state)
		state.operand0.operand = "imm"
		state.operand0.size = state.final_op_size
		state.operand0.immediate = read_signed_final_op_size(state)
		state.operand0.immediate += state.addr + state.opcode_offset
	else:
		size = state.final_op_size
		reg_list = get_reg_list_for_final_op_size(state)
		if (state.flags & DEC_FLAG_RM_SIZE_MASK) == DEC_FLAG_REG_RM_2X_SIZE:
			size *= 2
		elif (state.flags & DEC_FLAG_RM_SIZE_MASK) == DEC_FLAG_REG_RM_FAR_SIZE:
			size += 2
		elif (state.flags & DEC_FLAG_RM_SIZE_MASK) == DEC_FLAG_REG_RM_NO_SIZE:
			size = 0

		decode_rm_reg(state, state.operand1, reg_list, size, state.operand0, reg_list, state.final_op_size)

		if (size != state.final_op_size) and (state.operand1.operand != "mem"):
			state.invalid = True

def decode_rm_sreg_v(state):
	reg_list = get_reg_list_for_final_op_size(state)
	reg_field = decode_rm(state, state.operand0, reg_list, state.final_op_size)
	if reg_field >= 6:
		state.invalid = True
	state.operand1.operand = ["es", "cs", "ss", "ds", "fs", "gs", None, None][reg_field]
	state.operand1.size = 2
	if state.result.operands[0].operand == "cs":
		state.invalid = True

def decode_rm8(state):
	reg_list = get_byte_reg_list(state)
	decode_rm(state, state.operand0, reg_list, 1)

def decode_rm_v(state):
	reg_list = get_reg_list_for_final_op_size(state)
	decode_rm(state, state.operand0, reg_list, state.final_op_size)

def decode_far_imm(state):
	set_operand_to_imm(state, state.operand1)
	set_operand_to_imm16(state, state.operand0)

def decode_eax_addr(state):
	set_operand_to_eax_final_op_size(state, state.operand0)
	set_operand_to_imm_addr(state, state.operand1)
	if state.addr_size == 8:
		state.result.flags |= FLAG_64BIT_ADDRESS

def decode_edi_esi(state):
	set_operand_to_es_edi(state, state.operand0, state.final_op_size)
	set_operand_to_ds_esi(state, state.operand1, state.final_op_size)

def decode_edi_eax(state):
	set_operand_to_es_edi(state, state.operand0, state.final_op_size)
	set_operand_to_eax_final_op_size(state, state.operand1)

def decode_eax_esi(state):
	set_operand_to_eax_final_op_size(state, state.operand0)
	set_operand_to_ds_esi(state, state.operand1, state.final_op_size)

def decode_al_ebx_al(state):
	reg_list = get_reg_list_for_addr_size(state)
	state.operand0.operand = "al"
	state.operand0.size = 1
	state.operand1.operand = "mem"
	state.operand1.components = [reg_list[3], "al"]
	state.operand1.size = 1
	state.operand1.segment = get_final_segment(state, "ds")

def decode_eax_imm8(state):
	set_operand_to_eax_final_op_size(state, state.operand0)
	set_operand_to_imm8(state, state.operand1)

def decode_eax_dx(state):
	set_operand_to_eax_final_op_size(state, state.operand0)
	state.operand1.operand = "dx"
	state.operand1.size = 2

def decode_3dnow(state):
	decode_rm_reg(state, state.operand1, MMXRegList, 8, state.operand0, MMXRegList, 8)
	op = read8(state)
	state.result.operation = None
	min = 0
	max = len(Sparse3DNowOpcodes) - 1
	while min <= max:
		i = (min + max) / 2
		if op > Sparse3DNowOpcodes[i][0]:
			min = i + 1
		elif op < Sparse3DNowOpcodes[i][0]:
			max = i - 1
		else:
			state.result.operation = Sparse3DNowOpcodes[i][1]
			break

def decode_sse_table(state):
	type = decode_sse_prefix(state)
	rm = peek8(state)
	mod_field = (rm >> 6) & 3

	entry = SSETable[state.result.operation]
	if mod_field == 3:
		op_entry = entry[0][type]
	else:
		op_entry = entry[1][type]

	state.result.operation = op_entry[0]
	decode_rm_reg(state, get_operand_for_sse_entry_type(state, op_entry[2], 1),
		get_reg_list_for_sse_entry_type(state, op_entry[2]), get_size_for_sse_entry_type(state, op_entry[2]),
		get_operand_for_sse_entry_type(state, op_entry[1], 0),
		get_reg_list_for_sse_entry_type(state, op_entry[1]), get_size_for_sse_entry_type(state, op_entry[1]))

	if state.flags & DEC_FLAG_INC_OPERATION_FOR_64:
		update_operation_for_sse_entry_type(state, op_entry[1])
		update_operation_for_sse_entry_type(state, op_entry[2])

def decode_sse_table_imm8(state):
	type = decode_sse_prefix(state)
	rm = peek8(state)
	mod_field = (rm >> 6) & 3

	entry = SSETable[state.result.operation]
	if mod_field == 3:
		op_entry = entry[0][type]
	else:
		op_entry = entry[1][type]

	state.result.operation = op_entry[0]
	decode_rm_reg(state, get_operand_for_sse_entry_type(state, op_entry[2], 1),
		get_reg_list_for_sse_entry_type(state, op_entry[2]), get_size_for_sse_entry_type(state, op_entry[2]),
		get_operand_for_sse_entry_type(state, op_entry[1], 0),
		get_reg_list_for_sse_entry_type(state, op_entry[1]), get_size_for_sse_entry_type(state, op_entry[1]))

	if state.flags & DEC_FLAG_INC_OPERATION_FOR_64:
		update_operation_for_sse_entry_type(state, op_entry[1])
		update_operation_for_sse_entry_type(state, op_entry[2])

	set_operand_to_imm8(state, state.result.operands[2])

def decode_sse_table_mem8(state):
	type = decode_sse_prefix(state)
	rm = peek8(state)
	mod_field = (rm >> 6) & 3

	entry = SSETable[state.result.operation]
	if mod_field == 3:
		op_entry = entry[0][type]
	else:
		op_entry = entry[1][type]

	state.result.operation = op_entry[0]
	decode_rm_reg(state, get_operand_for_sse_entry_type(state, op_entry[2], 1),
		get_reg_list_for_sse_entry_type(state, op_entry[2]), get_size_for_sse_entry_type(state, op_entry[2]),
		get_operand_for_sse_entry_type(state, op_entry[1], 0),
		get_reg_list_for_sse_entry_type(state, op_entry[1]), get_size_for_sse_entry_type(state, op_entry[1]))

	if state.flags & DEC_FLAG_INC_OPERATION_FOR_64:
		update_operation_for_sse_entry_type(state, op_entry[1])
		update_operation_for_sse_entry_type(state, op_entry[2])

	if state.operand0.operand == "mem":
		state.operand0.size = 1
	if state.operand1.operand == "mem":
		state.operand1.size = 1

def decode_sse(state):
	type = decode_sse_prefix(state)
	rm = peek8(state)
	mod_field = (rm >> 6) & 3

	state.result.operation = state.result.operation[type]
	if mod_field == 3:
		size = 16
	else:
		size = get_size_for_sse_type(type)
	decode_rm_reg(state, state.operand1, XMMRegList, size, state.operand0, XMMRegList, 16)

def decode_sse_single(state):
	type = decode_sse_prefix(state)
	rm = peek8(state)
	mod_field = (rm >> 6) & 3

	if (type == 1) or (type == 2):
		state.invalid = True
	else:
		state.result.operation = state.result.operation[type & 1]
		if mod_field == 3:
			size = 16
		else:
			size = get_size_for_sse_type(type)
		decode_rm_reg(state, state.operand1, XMMRegList, 16, state.operand0, XMMRegList, 16)

def decode_sse_packed(state):
	type = decode_sse_prefix(state)

	if (type == 2) or (type == 3):
		state.invalid = True
	else:
		state.result.operation = state.result.operation[type & 1]
		decode_rm_reg(state, state.operand1, XMMRegList, 16, state.operand0, XMMRegList, 16)

def decode_mmx(state):
	if state.op_prefix:
		decode_rm_reg(state, state.operand1, XMMRegList, 16, state.operand0, XMMRegList, 16)
	else:
		decode_rm_reg(state, state.operand1, MMXRegList, 8, state.operand0, MMXRegList, 8)

def decode_mmx_sse_only(state):
	if state.op_prefix:
		decode_rm_reg(state, state.operand1, XMMRegList, 16, state.operand0, XMMRegList, 16)
	else:
		state.invalid = True

def decode_mmx_group(state):
	if state.op_prefix:
		reg_field = decode_rm(state, state.operand0, XMMRegList, 16)
		state.result.operation = MMXGroupOperations[state.result.operation][reg_field][1]
	else:
		reg_field = decode_rm(state, state.operand0, MMXRegList, 8)
		state.result.operation = MMXGroupOperations[state.result.operation][reg_field][0]
	set_operand_to_imm8(state, state.operand1)

def decode_pinsrw(state):
	type = decode_sse_prefix(state)
	rm = peek8(state)
	mod_field = (rm >> 6) & 3

	entry = SSETable[state.result.operation]
	if mod_field == 3:
		op_entry = entry[0][type]
	else:
		op_entry = entry[1][type]

	state.result.operation = op_entry[0]
	decode_rm_reg(state, get_operand_for_sse_entry_type(state, op_entry[2], 1),
		get_reg_list_for_sse_entry_type(state, op_entry[2]), get_size_for_sse_entry_type(state, op_entry[2]),
		get_operand_for_sse_entry_type(state, op_entry[1], 0),
		get_reg_list_for_sse_entry_type(state, op_entry[1]), get_size_for_sse_entry_type(state, op_entry[1]))

	if state.flags & DEC_FLAG_INC_OPERATION_FOR_64:
		update_operation_for_sse_entry_type(state, op_entry[1])
		update_operation_for_sse_entry_type(state, op_entry[2])

	set_operand_to_imm8(state, state.result.operands[2])

	if state.operand1.operand == "mem":
		state.operand1.size = 2

def decode_reg_cr(state):
	if state.final_op_size == 2:
		state.final_op_size = 4
	reg_list = get_reg_list_for_final_op_size(state)
	reg = read8(state)
	if state.result.flags & FLAG_LOCK:
		state.result.flags &= ~FLAG_LOCK
		state.rex_reg = True
	if state.rex_rm1:
		state.operand0.operand = reg_list[(reg & 7) + 8]
	else:
		state.operand0.operand = reg_list[(reg & 7)]
	state.operand0.size = state.final_op_size
	if state.rex_reg:
		state.operand1.operand = state.result.operation[((reg >> 3) & 7) + 8]
	else:
		state.operand1.operand = state.result.operation[((reg >> 3) & 7)]
	state.operand1.size = state.final_op_size
	state.result.operation = "mov"

def decode_mov_sx_zx_8(state):
	decode_rm_reg(state, state.operand1, get_byte_reg_list(state), 1, state.operand0,
		get_reg_list_for_final_op_size(state), state.final_op_size)

def decode_mov_sx_zx_16(state):
	decode_rm_reg(state, state.operand1, Reg16List, 2, state.operand0,
		get_reg_list_for_final_op_size(state), state.final_op_size)

def decode_mem16(state):
	decode_rm(state, state.operand0, Reg32List, 2)
	if state.operand0.operand != "mem":
		state.invalid = True

def decode_mem32(state):
	decode_rm(state, state.operand0, Reg32List, 4)
	if state.operand0.operand != "mem":
		state.invalid = True

def decode_mem64(state):
	decode_rm(state, state.operand0, Reg32List, 8)
	if state.operand0.operand != "mem":
		state.invalid = True

def decode_mem80(state):
	decode_rm(state, state.operand0, Reg32List, 10)
	if state.operand0.operand != "mem":
		state.invalid = True

def decode_mem_float_env(state):
	if state.final_op_size == 2:
		decode_rm(state, state.operand0, Reg32List, 14)
	else:
		decode_rm(state, state.operand0, Reg32List, 28)
	if state.operand0.operand != "mem":
		state.invalid = True

def decode_mem_float_save(state):
	if state.final_op_size == 2:
		decode_rm(state, state.operand0, Reg32List, 94)
	else:
		decode_rm(state, state.operand0, Reg32List, 108)
	if state.operand0.operand != "mem":
		state.invalid = True

def decode_fpu_reg(state):
	decode_rm(state, state.operand0, FPURegList, 10)

def decode_fpu_reg_st0(state):
	decode_rm(state, state.operand0, FPURegList, 10)
	state.operand1.operand = "st0"
	state.operand1.size = 10

def decode_reg_group_no_operands(state):
	rm_byte = read8(state)
	state.result.operation = GroupOperations[state.result.operation][rm_byte & 7]

def decode_reg_group_ax(state):
	rm_byte = read8(state)
	state.result.operation = GroupOperations[state.result.operation][rm_byte & 7]
	state.operand0.operand = "ax"
	state.operand0.size = 2

def decode_cmpxch8b(state):
	rm = peek8(state)
	reg_field = (rm >> 3) & 7

	if reg_field == 1:
		if state.final_op_size == 2:
			state.final_op_size = 4
		elif state.final_op_size == 8:
			state.result.operation = "cmpxch16b"
		decode_rm(state, state.operand0, get_reg_list_for_final_op_size(state), state.final_op_size * 2)
	elif reg_field == 6:
		if state.op_prefix:
			state.result.operation = "vmclear"
		elif state.rep == "repe":
			state.result.operation = "vmxon"
		else:
			state.result.operation = "vmptrld"
		decode_rm(state, state.operand0, Reg64List, 8)
	elif reg_field == 7:
		state.result.operation = "vmptrst"
		decode_rm(state, state.operand0, Reg64List, 8)
	else:
		state.invalid = True

	if state.operand0.operand != "mem":
		state.invalid = True

def decode_mov_nti(state):
	if state.final_op_size == 2:
		state.final_op_size = 4
	decode_rm_reg(state, state.operand0, get_reg_list_for_final_op_size(state), state.final_op_size,
		state.operand1, get_reg_list_for_final_op_size(state), state.final_op_size)
	if state.operand0.operand != "mem":
		state.invalid = True

def decode_crc32(state):
	src_reg_list = get_reg_list_for_final_op_size(state)
	if state.final_op_size == 8:
		dest_reg_list = Reg64List
		dest_size = 8
	else:
		dest_reg_list = Reg32List
		dest_size = 4
	decode_rm_reg(state, state.operand1, src_reg_list, state.final_op_size,
		state.operand0, dest_reg_list, dest_size)

def decode_arpl(state):
	if state.using64:
		state.result.operation = "movsxd"
		reg_list = get_reg_list_for_final_op_size(state)
		decode_rm_reg(state, state.operand1, Reg32List, 4, state.operand0, reg_list, state.final_op_size)
	else:
		state.final_op_size = 2
		reg_list = get_reg_list_for_final_op_size(state)
		decode_rm_reg(state, state.operand0, reg_list, 2, state.operand1, reg_list, state.final_op_size)

Encoding = {
	None : [invalid_decode, 0],
	"two_byte" : [decode_two_byte, 0], "fpu" : [decode_fpu, 0],
	"no_operands" : [decode_no_operands, 0], "op_size" : [decode_no_operands, DEC_FLAG_OPERATION_OP_SIZE],
	"op_size_def64" : [decode_no_operands, DEC_FLAG_DEFAULT_TO_64BIT | DEC_FLAG_OPERATION_OP_SIZE],
	"op_size_no64" : [decode_no_operands, DEC_FLAG_INVALID_IN_64BIT | DEC_FLAG_OPERATION_OP_SIZE],
	"reg_rm_8" : [decode_reg_rm, DEC_FLAG_BYTE], "rm_reg_8" : [decode_reg_rm, DEC_FLAG_BYTE | DEC_FLAG_FLIP_OPERANDS],
	"rm_reg_8_lock" : [decode_reg_rm, DEC_FLAG_BYTE | DEC_FLAG_FLIP_OPERANDS | DEC_FLAG_LOCK],
	"rm_reg_16" : [decode_reg_rm, DEC_FLAG_FLIP_OPERANDS | DEC_FLAG_FORCE_16BIT],
	"reg_rm_v" : [decode_reg_rm, 0], "rm_reg_v" : [decode_reg_rm, DEC_FLAG_FLIP_OPERANDS],
	"rm_reg_v_lock" : [decode_reg_rm, DEC_FLAG_FLIP_OPERANDS | DEC_FLAG_LOCK],
	"reg_rm2x_v" : [decode_reg_rm, DEC_FLAG_REG_RM_2X_SIZE], "reg_rm_imm_v" : [decode_reg_rm_imm, 0],
	"reg_rm_immsx_v" : [decode_reg_rm_imm, DEC_FLAG_IMM_SX], "reg_rm_0" : [decode_reg_rm, DEC_FLAG_REG_RM_NO_SIZE],
	"reg_rm_f" : [decode_reg_rm, DEC_FLAG_REG_RM_FAR_SIZE],
	"rm_reg_def64" : [decode_reg_rm, DEC_FLAG_FLIP_OPERANDS | DEC_FLAG_DEFAULT_TO_64BIT],
	"rm_reg_imm8_v" : [decode_rm_reg_imm8, 0], "rm_reg_cl_v" : [decode_rm_reg_cl, 0],
	"eax_imm_8" : [decode_eax_imm, DEC_FLAG_BYTE], "eax_imm_v" : [decode_eax_imm, 0],
	"push_pop_seg" : [decode_push_pop_seg, 0],
	"op_reg_v" : [decode_op_reg, 0], "op_reg_v_def64" : [decode_op_reg, DEC_FLAG_DEFAULT_TO_64BIT],
	"eax_op_reg_v" : [decode_eax_op_reg, 0], "op_reg_imm_8" : [decode_op_reg_imm, DEC_FLAG_BYTE],
	"op_reg_imm_v" : [decode_op_reg_imm, 0], "nop" : [decode_nop, 0],
	"imm_v_def64" : [decode_imm, DEC_FLAG_DEFAULT_TO_64BIT],
	"immsx_v_def64" : [decode_imm, DEC_FLAG_IMM_SX | DEC_FLAG_DEFAULT_TO_64BIT],
	"imm_8" : [decode_imm, DEC_FLAG_BYTE], "imm_16" : [decode_imm, DEC_FLAG_FORCE_16BIT],
	"imm16_imm8" : [decode_imm16_imm8, 0],
	"edi_dx_8_rep" : [decode_edi_dx, DEC_FLAG_BYTE | DEC_FLAG_REP],
	"edi_dx_op_size_rep" : [decode_edi_dx, DEC_FLAG_OPERATION_OP_SIZE | DEC_FLAG_REP],
	"dx_esi_8_rep" : [decode_dx_esi, DEC_FLAG_BYTE | DEC_FLAG_REP],
	"dx_esi_op_size_rep" : [decode_dx_esi, DEC_FLAG_OPERATION_OP_SIZE | DEC_FLAG_REP],
	"relimm_8_def64" : [decode_rel_imm, DEC_FLAG_BYTE | DEC_FLAG_DEFAULT_TO_64BIT],
	"relimm_v_def64" : [decode_rel_imm, DEC_FLAG_DEFAULT_TO_64BIT],
	"relimm_8_addr_size_def64" : [decode_rel_imm_addr_size, DEC_FLAG_BYTE | DEC_FLAG_DEFAULT_TO_64BIT],
	"group_rm_8" : [decode_group_rm, DEC_FLAG_BYTE], "group_rm_v" : [decode_group_rm, 0],
	"group_rm_8_lock" : [decode_group_rm, DEC_FLAG_BYTE | DEC_FLAG_LOCK],
	"group_rm_0" : [decode_group_rm, DEC_FLAG_REG_RM_NO_SIZE],
	"group_rm_imm_8" : [decode_group_rm_imm, DEC_FLAG_BYTE],
	"group_rm_imm_8_lock" : [decode_group_rm_imm, DEC_FLAG_BYTE | DEC_FLAG_LOCK],
	"group_rm_imm_8_no64_lock" : [decode_group_rm_imm, DEC_FLAG_BYTE | DEC_FLAG_INVALID_IN_64BIT | DEC_FLAG_LOCK],
	"group_rm_imm8_v" : [decode_group_rm_imm8v, 0],
	"group_rm_imm_v" : [decode_group_rm_imm, 0], "group_rm_imm_v_lock" : [decode_group_rm_imm, DEC_FLAG_LOCK],
	"group_rm_immsx_v_lock" : [decode_group_rm_imm, DEC_FLAG_IMM_SX | DEC_FLAG_LOCK],
	"group_rm_one_8" : [decode_group_rm_one, DEC_FLAG_BYTE], "group_rm_one_v" : [decode_group_rm_one, 0],
	"group_rm_cl_8" : [decode_group_rm_cl, DEC_FLAG_BYTE], "group_rm_cl_v" : [decode_group_rm_cl, 0],
	"group_f6" : [decode_group_f6_f7, DEC_FLAG_BYTE | DEC_FLAG_LOCK], "group_f7" : [decode_group_f6_f7, DEC_FLAG_LOCK],
	"group_ff" : [decode_group_ff, DEC_FLAG_LOCK],
	"group_0f00" : [decode_group_0f00, 0], "group_0f01" : [decode_group_0f01, 0], "group_0fae" : [decode_group_0fae, 0],
	"_0fb8" : [decode_0fb8, 0],
	"rm_sreg_v" : [decode_rm_sreg_v, 0], "sreg_rm_v" : [decode_rm_sreg_v, DEC_FLAG_FLIP_OPERANDS],
	"rm_8" : [decode_rm8, 0], "rm_v_def64" : [decode_rm_v, DEC_FLAG_DEFAULT_TO_64BIT],
	"far_imm_no64" : [decode_far_imm, DEC_FLAG_INVALID_IN_64BIT],
	"eax_addr_8" : [decode_eax_addr, DEC_FLAG_BYTE], "eax_addr_v" : [decode_eax_addr, 0],
	"addr_eax_8" : [decode_eax_addr, DEC_FLAG_BYTE | DEC_FLAG_FLIP_OPERANDS],
	"addr_eax_v" : [decode_eax_addr, DEC_FLAG_FLIP_OPERANDS],
	"edi_esi_8_rep" : [decode_edi_esi, DEC_FLAG_BYTE | DEC_FLAG_REP],
	"edi_esi_op_size_rep" : [decode_edi_esi, DEC_FLAG_OPERATION_OP_SIZE | DEC_FLAG_REP],
	"esi_edi_8_repc" : [decode_edi_esi, DEC_FLAG_BYTE | DEC_FLAG_FLIP_OPERANDS | DEC_FLAG_REP_COND],
	"esi_edi_op_size_repc" : [decode_edi_esi, DEC_FLAG_FLIP_OPERANDS | DEC_FLAG_OPERATION_OP_SIZE | DEC_FLAG_REP_COND],
	"edi_eax_8_rep" : [decode_edi_eax, DEC_FLAG_BYTE | DEC_FLAG_REP],
	"edi_eax_op_size_rep" : [decode_edi_eax, DEC_FLAG_OPERATION_OP_SIZE | DEC_FLAG_REP],
	"eax_esi_8_rep" : [decode_eax_esi, DEC_FLAG_BYTE | DEC_FLAG_REP],
	"eax_esi_op_size_rep" : [decode_eax_esi, DEC_FLAG_OPERATION_OP_SIZE | DEC_FLAG_REP],
	"eax_edi_8_repc" : [decode_edi_eax, DEC_FLAG_BYTE | DEC_FLAG_FLIP_OPERANDS | DEC_FLAG_REP_COND],
	"eax_edi_op_size_repc" : [decode_edi_eax, DEC_FLAG_FLIP_OPERANDS | DEC_FLAG_OPERATION_OP_SIZE | DEC_FLAG_REP_COND],
	"al_ebx_al" : [decode_al_ebx_al, 0],
	"eax_imm8_8" : [decode_eax_imm8, DEC_FLAG_BYTE], "eax_imm8_v" : [decode_eax_imm8, 0],
	"imm8_eax_8" : [decode_eax_imm8, DEC_FLAG_BYTE | DEC_FLAG_FLIP_OPERANDS],
	"imm8_eax_v" : [decode_eax_imm8, DEC_FLAG_FLIP_OPERANDS],
	"eax_dx_8" : [decode_eax_dx, DEC_FLAG_BYTE], "eax_dx_v" : [decode_eax_dx, 0],
	"dx_eax_8" : [decode_eax_dx, DEC_FLAG_BYTE | DEC_FLAG_FLIP_OPERANDS],
	"dx_eax_v" : [decode_eax_dx, DEC_FLAG_FLIP_OPERANDS], "_3dnow" : [decode_3dnow, 0],
	"sse_table" : [decode_sse_table, 0], "sse_table_flip" : [decode_sse_table, DEC_FLAG_FLIP_OPERANDS],
	"sse_table_imm_8" : [decode_sse_table_imm8, 0], "sse_table_imm_8_flip" : [decode_sse_table_imm8, DEC_FLAG_FLIP_OPERANDS],
	"sse_table_incop64" : [decode_sse_table, DEC_FLAG_INC_OPERATION_FOR_64],
	"sse_table_incop64_flip" : [decode_sse_table, DEC_FLAG_INC_OPERATION_FOR_64 | DEC_FLAG_FLIP_OPERANDS],
	"sse_table_mem8" : [decode_sse_table_mem8, 0], "sse_table_mem8_flip" : [decode_sse_table_mem8, DEC_FLAG_FLIP_OPERANDS],
	"sse" : [decode_sse, 0], "sse_single" : [decode_sse_single, 0], "sse_packed" : [decode_sse_packed, 0],
	"mmx" : [decode_mmx, 0], "mmx_sseonly" : [decode_mmx_sse_only, 0],
	"mmx_group" : [decode_mmx_group, 0], "pinsrw" : [decode_pinsrw, 0],
	"reg_cr" : [decode_reg_cr, DEC_FLAG_DEFAULT_TO_64BIT | DEC_FLAG_LOCK],
	"cr_reg" : [decode_reg_cr, DEC_FLAG_FLIP_OPERANDS | DEC_FLAG_DEFAULT_TO_64BIT | DEC_FLAG_LOCK],
	"movsxzx_8" : [decode_mov_sx_zx_8, 0], "movsxzx_16" : [decode_mov_sx_zx_16, 0],
	"mem_16" : [decode_mem16, 0], "mem_32" : [decode_mem32, 0], "mem_64" : [decode_mem64, 0], "mem_80" : [decode_mem80, 0],
	"mem_floatenv" : [decode_mem_float_env, 0], "mem_floatsave" : [decode_mem_float_save, 0],
	"fpureg" : [decode_fpu_reg, 0], "st0_fpureg" : [decode_fpu_reg_st0, DEC_FLAG_FLIP_OPERANDS],
	"fpureg_st0" : [decode_fpu_reg_st0, 0],
	"reggroup_no_operands" : [decode_reg_group_no_operands, 0], "reggroup_ax" : [decode_reg_group_ax, 0],
	"cmpxch8b" : [decode_cmpxch8b, DEC_FLAG_LOCK], "movnti" : [decode_mov_nti, 0],
	"crc32_8" : [decode_crc32, DEC_FLAG_BYTE], "crc32_v" : [decode_crc32, 0],
	"arpl" : [decode_arpl, 0]
}

def x86_reg_size(reg):
	if reg in Reg8List:
		return 1
	if reg in Reg8List64:
		return 1
	if reg in Reg16List:
		return 2
	if reg in Reg32List:
		return 4
	if reg in Reg64List:
		return 8
	if reg in MMXRegList:
		return 8
	if reg in XMMRegList:
		return 16
	return 10

def process_prefixes(state):
	rex = 0
	addr_prefix = False

	while not state.invalid:
		prefix = read8(state)
		if (prefix >= 0x26) and (prefix <= 0x3e) and ((prefix & 7) == 6):
			# Segment prefix
			state.result.segment = ["es", "cs", "ss", "ds"][(prefix >> 3) - 4]
		elif prefix == 0x64:
			state.result.segment = "fs"
		elif prefix == 0x65:
			state.result.segment = "gs"
		elif prefix == 0x66:
			state.op_prefix = True
			state.result.flags |= FLAG_OPSIZE
		elif prefix == 0x67:
			addr_prefix = True
			state.result.flags |= FLAG_ADDRSIZE
		elif prefix == 0xf0:
			state.result.flags |= FLAG_LOCK
		elif prefix == 0xf2:
			state.rep = "repne"
		elif prefix == 0xf3:
			state.rep = "repe"
		elif state.using64 and (prefix >= 0x40) and (prefix <= 0x4f):
			# REX prefix
			rex = prefix
			continue
		else:
			# Not a prefix, continue instruction processing
			state.opcode = chr(prefix) + state.opcode
			state.opcode_offset -= 1
			break

		# Force ignore REX unless it is the last prefix
		rex = 0

	if state.op_prefix:
		if state.op_size == 2:
			state.op_size = 4
		else:
			state.op_size = 2
	if addr_prefix:
		if state.addr_size == 4:
			state.addr_size = 2
		else:
			state.addr_size = 4

	if rex != 0:
		# REX prefix found before opcode
		state.rex = True
		state.rex_rm1 = (rex & 1) != 0
		state.rex_rm2 = (rex & 2) != 0
		state.rex_reg = (rex & 4) != 0
		if (rex & 8) != 0:
			state.op_size = 8

def finish_disassemble(state):
	state.result.length = state.opcode_offset
	for i in state.result.operands:
		if i.rip_relative:
			i.immediate += state.addr + state.result.length
	if state.insufficient_length and (state.orig_len < 15):
		state.result.flags |= FLAG_INSUFFICIENT_LENGTH
	if state.invalid:
		state.result.operation = None
	state.result.finalize()

def disassemble16(opcode, addr):
	state = DecodeState()
	state.opcode = opcode
	state.addr = addr
	state.addr_size = 2
	state.op_size = 2
	state.using64 = False

	if len(state.opcode) > 15:
		state.opcode = state.opcode[0:15]
	state.orig_len = len(state.opcode)

	process_prefixes(state)
	process_opcode(state, MainOpcodeMap, read8(state))
	finish_disassemble(state)

	state.result.addr_size = state.addr_size
	return state.result

def disassemble32(opcode, addr):
	state = DecodeState()
	state.opcode = opcode
	state.addr = addr
	state.addr_size = 4
	state.op_size = 4
	state.using64 = False

	if len(state.opcode) > 15:
		state.opcode = state.opcode[0:15]
	state.orig_len = len(state.opcode)

	process_prefixes(state)
	process_opcode(state, MainOpcodeMap, read8(state))
	finish_disassemble(state)

	state.result.addr_size = state.addr_size
	return state.result

def disassemble64(opcode, addr):
	state = DecodeState()
	state.opcode = opcode
	state.addr = addr
	state.addr_size = 8
	state.op_size = 4
	state.using64 = True

	if len(state.opcode) > 15:
		state.opcode = state.opcode[0:15]
	state.orig_len = len(state.opcode)

	process_prefixes(state)
	process_opcode(state, MainOpcodeMap, read8(state))
	finish_disassemble(state)

	state.result.addr_size = state.addr_size
	return state.result

def get_size_string(size):
	if size == 1:
		return "byte "
	if size == 2:
		return "word "
	if size == 4:
		return "dword "
	if size == 6:
		return "fword "
	if size == 8:
		return "qword "
	if size == 10:
		return "tword "
	if size == 16:
		return "oword "
	return ""

def get_operand_string(type, scale, plus):
	if plus:
		result = "+"
	else:
		result = ""
	result += type
	if scale != 1:
		result += "*%d" % scale
	return result

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
					for j in range(0, instr.length):
						result += "%.2x" % ord(opcode[j])
					for j in range(instr.length, width):
						result += "  "
					break
				elif fmt[i] == 'i':
					operation = ""
					if instr.flags & FLAG_LOCK:
						operation += "lock "
					if instr.flags & FLAG_ANY_REP:
						operation += "rep"
						if instr.flags & FLAG_REPNE:
							operation += "ne"
						elif instr.flags & FLAG_REPE:
							operation += "e"
						operation += " "
					operation += instr.operation
					for j in range(len(operation), width):
						operation += " "
					result += operation
					break
				elif fmt[i] == 'o':
					for j in range(0, len(instr.operands)):
						if j != 0:
							result += ", "
						if instr.operands[j].operand == "imm":
							numfmt = "0x%%.%dx" % (instr.operands[j].size * 2)
							result += numfmt % (instr.operands[j].immediate &
								((1 << (instr.operands[j].size * 8)) - 1))
						elif instr.operands[j].operand == "mem":
							plus = False
							result += get_size_string(instr.operands[j].size)
							if (instr.segment != None) or (instr.operands[j].segment == "es"):
								result += instr.operands[j].segment + ":"
							result += '['
							if instr.operands[j].components[0] != None:
								result += instr.operands[j].components[0]
								plus = True
							if instr.operands[j].components[1] != None:
								result += get_operand_string(instr.operands[j].components[1],
									instr.operands[j].scale, plus)
								plus = True
							if (instr.operands[j].immediate != 0) or ((instr.operands[j].components[0] == None) and (instr.operands[j].components[1] == None)):
								if plus and (instr.operands[j].immediate >= -0x80) and (instr.operands[j].immediate < 0):
									result += '-'
									result += "0x%.2x" % (-instr.operands[j].immediate)
								elif plus and (instr.operands[j].immediate > 0) and (instr.operands[j].immediate <= 0x7f):
									result += '+'
									result += "0x%.2x" % instr.operands[j].immediate
								elif (instr.flags & FLAG_64BIT_ADDRESS) != 0:
									if plus:
										result += '+'
									result += "0x%.16x" % instr.operands[j].immediate
								else:
									if plus:
										result += '+'
									result += "0x%.8x" % (instr.operands[j].immediate & 0xffffffff)
							result += ']'
						else:
							result += instr.operands[j].operand
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

def disassemble16_to_string(fmt, opcode, addr):
	instr = disassemble16(opcode, addr)
	return format_instruction_string(fmt, opcode, addr, instr)

def disassemble32_to_string(fmt, opcode, addr):
	instr = disassemble32(opcode, addr)
	return format_instruction_string(fmt, opcode, addr, instr)

def disassemble64_to_string(fmt, opcode, addr):
	instr = disassemble64(opcode, addr)
	return format_instruction_string(fmt, opcode, addr, instr)

