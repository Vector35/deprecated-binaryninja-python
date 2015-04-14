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

from TextLines import *


class CHighlight(Highlight):
	def __init__(self, data):
		self.keywords = ["const", "bool", "char", "int", "short", "long", "float", "double", "signed", "unsigned",
			"int8_t", "int16_t", "int32_t", "int64_t", "uint8_t", "uint16_t", "uint32_t", "uint64_t", "size_t",
			"ssize_t", "ptrdiff_t", "struct", "union", "enum", "return", "if", "else", "for", "while", "do",
			"break", "continue", "goto", "switch", "case", "default", "void", "sizeof", "typedef", "static",
			"extern", "__cdecl", "__stdcall", "__fastcall", "__subarch", "__noreturn"]
		self.identifiers = ["stdin", "stdout", "stderr", "min", "max", "abs", "__undefined", "__rdtsc",
			"__rdtsc_low", "__rdtsc_high", "__next_arg", "__prev_arg", "__byteswap", "__syscall", "va_list",
			"va_start", "va_arg", "va_end"]
		self.values = ["NULL", "true", "false"]

	def update_line(self, line, text):
		long_comment = False
		if line.highlight_state.style == HIGHLIGHT_COMMENT:
			long_comment = True

		if text.find("//") != -1:
			token = HighlightToken(text.find("//"), len(text) - text.find("//"), HighlightState(HIGHLIGHT_COMMENT))
			line.tokens.append(token)
			text = text[0:text.find("//")]

		if text.find('#') != -1:
			token = HighlightToken(text.find('#'), len(text) - text.find('#'), HighlightState(HIGHLIGHT_DIRECTIVE))
			line.tokens.append(token)
			text = text[0:text.find('#')]

		tokens = self.simple_tokenize(text)
		for i in xrange(0, len(tokens)):
			token = tokens[i]
			if (token[1] == "/") and (i > 0) and (tokens[i - 1][1] == '*') and (token[0] == (tokens[i - 1][0] + 1)):
				line.tokens.append(HighlightToken(token[0], len(token[1]), HighlightState(HIGHLIGHT_COMMENT)))
				long_comment = False
			elif (token[1] == "/") and ((i + 1) < len(tokens)) and (tokens[i + 1][1] == '*') and (token[0] == (tokens[i + 1][0] - 1)):
				line.tokens.append(HighlightToken(token[0], len(token[1]), HighlightState(HIGHLIGHT_COMMENT)))
				long_comment = True
			elif long_comment:
				line.tokens.append(HighlightToken(token[0], len(token[1]), HighlightState(HIGHLIGHT_COMMENT)))
			elif token[1] in self.keywords:
				line.tokens.append(HighlightToken(token[0], len(token[1]), HighlightState(HIGHLIGHT_KEYWORD)))
			elif token[1] in self.identifiers:
				line.tokens.append(HighlightToken(token[0], len(token[1]), HighlightState(HIGHLIGHT_IDENTIFIER)))
			elif token[1] in self.values:
				line.tokens.append(HighlightToken(token[0], len(token[1]), HighlightState(HIGHLIGHT_VALUE)))
			elif (token[1][0] == '"') or (token[1][0] == '\''):
				self.append_escaped_string_tokens(line, token[0], token[1])
			elif (token[1][0] >= '0') and (token[1][0] <= '9'):
				line.tokens.append(HighlightToken(token[0], len(token[1]), HighlightState(HIGHLIGHT_VALUE)))

		if long_comment:
			return HighlightState(HIGHLIGHT_COMMENT)
		return HighlightState(HIGHLIGHT_NONE)


highlightTypes["C source"] = CHighlight

