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


class PythonHighlight(Highlight):
	def __init__(self, data):
		self.keywords = ["class", "def", "if", "elif", "else", "for", "in", "while", "return", "and", "or", "not", "is",
			"print", "try", "except", "finally", "raise", "as", "assert", "break", "continue", "exec", "pass",
			"lambda", "with", "yield"]
		self.identifiers = ["self", "super", "len", "del", "type", "repr", "str", "int", "bytes", "long", "hex",
			"range", "xrange"]
		self.values = ["None", "True", "False"]
		self.directives = ["import", "from", "global"]
		self.definitions = ["class", "def", "import", "from"]

	def update_line(self, line, text):
		if text.find('#') != -1:
			token = HighlightToken(text.find('#'), len(text) - text.find('#'), HighlightState(HIGHLIGHT_COMMENT))
			line.tokens.append(token)
			text = text[0:text.find('#')]

		tokens = self.simple_tokenize(text)
		for i in xrange(0, len(tokens)):
			token = tokens[i]
			if token[1] in self.keywords:
				line.tokens.append(HighlightToken(token[0], len(token[1]), HighlightState(HIGHLIGHT_KEYWORD)))
			elif token[1] in self.identifiers:
				line.tokens.append(HighlightToken(token[0], len(token[1]), HighlightState(HIGHLIGHT_IDENTIFIER)))
			elif token[1] in self.values:
				line.tokens.append(HighlightToken(token[0], len(token[1]), HighlightState(HIGHLIGHT_VALUE)))
			elif token[1] in self.directives:
				line.tokens.append(HighlightToken(token[0], len(token[1]), HighlightState(HIGHLIGHT_DIRECTIVE)))
			elif (i > 0) and (tokens[i - 1][1] in self.definitions):
				line.tokens.append(HighlightToken(token[0], len(token[1]), HighlightState(HIGHLIGHT_IDENTIFIER)))
			elif (token[1][0] == '"') or (token[1][0] == '\''):
				self.append_escaped_string_tokens(line, token[0], token[1])
			elif (token[1][0] >= '0') and (token[1][0] <= '9'):
				line.tokens.append(HighlightToken(token[0], len(token[1]), HighlightState(HIGHLIGHT_VALUE)))

		return None


highlightTypes["Python source"] = PythonHighlight

