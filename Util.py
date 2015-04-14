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
from PySide.QtCore import *
from PySide.QtGui import *
from Crypto.Hash import MD2
from Crypto.Hash import MD4
from Crypto.Hash import MD5
from Crypto.Hash import SHA
from Crypto.Hash import SHA256
from Crypto.Hash import HMAC
import Transform


def hex_dump_encode(data):
	result = ""
	for i in range(0, len(data), 16):
		result += "%.8x:" % i
		hex = ""
		ascii = ""
		for j in range(0, 16):
			if (i + j) >= len(data):
				hex += "   "
			else:
				hex += " %.2x" % ord(data[i + j])
				if (data[i + j] < ' ') or (data[i + j] > '~'):
					ascii += "."
				else:
					ascii += data[i + j]
		result += hex + "  " + ascii + "\n"
	return result

def hex_dump_decode(data):
	result = ""
	lines = data.split("\n")
	for line in lines:
		# Hex dump lines follow the following format:
		# * An address, followed by any number of spaces
		# * The hex dump itself, 16 bytes per line
		# * Optionally two or more spaces, followed by the ASCII dump
		line.strip(" \t")
		if line.find(' ') == -1:
			continue
		hex = line[line.find(' '):].strip(" \t")
		if hex.find("  ") != -1:
			hex = hex[0:hex.find("  ")]
		hex = hex.replace(" ", "")
		hex = hex[0:32]
		result += hex.decode("hex")
	return result

def encode_utf16_string(data, char_escape):
	if len(data) % 2:
		raise ValueError, "Odd number of bytes"
	result = ""
	for i in range(0, len(data), 2):
		value = struct.unpack("<H", data[i:i+2])[0]
		if (value >= ' ') and (value <= '~'):
			result += chr(value)
		else:
			result += char_escape + ("%.4x" % value)
	return result

def encode_url(data):
	result = ""
	for i in range(0, len(data)):
		if data[i] in ['-', '_', '.', '~']:
			result += data[i]
		elif (data[i] >= '0') and (data[i] <= '9'):
			result += data[i]
		elif (data[i] >= 'a') and (data[i] <= 'z'):
			result += data[i]
		elif (data[i] >= 'A') and (data[i] <= 'Z'):
			result += data[i]
		else:
			result += "%%%.2x" % ord(data[i])
	return result

def decode_url(data):
	result = ""
	i = 0
	while i < len(data):
		if data[i] == '%':
			if data[i + 1] == 'u':
				result += unichr(int(data[i+2:i+6], 16)).encode("utf8")
				i += 6
			else:
				result += chr(int(data[i+1:i+3], 16))
				i += 3
		else:
			result += data[i]
			i += 1
	return result

def encode_c_array(data, element_size, element_struct, type_name, postfix):
	if len(data) % element_size:
		raise ValueError, "Data length is not a multiple of the element size"

	fmt = "0x%%.%dx%s" % (element_size * 2, postfix)
	result = "{\n"
	for i in range(0, len(data), 16):
		line = ""
		for j in range(0, 16, element_size):
			if (i + j) >= len(data):
				break
			if j > 0:
				line += ", "
			value = struct.unpack(element_struct, data[i+j:i+j+element_size])[0]
			line += fmt % value
		if (i + 16) < len(data):
			line += ","
		result += "\t" + line + "\n"
	return type_name + (" data[%d] = \n" % (len(data) / element_size)) + result + "};\n"

def decode_int_list(data, signed, unsigned):
	result = ""
	list = data.split(",")
	for i in list:
		i = i.strip(" \t\r\n")
		value = int(i, 0)
		if value < 0:
			result += struct.pack(signed, value)
		else:
			result += struct.pack(unsigned, value)
	return result

class CancelException(Exception):
	pass

def request_key(obj):
	dlg = Transform.KeyDialog(obj)
	if dlg.exec_() == QDialog.Rejected:
		raise CancelException
	return dlg.key[:]

def populate_copy_as_menu(menu, obj, action_table):
	string_menu = menu.addMenu("Escaped string")
	action_table[string_menu.addAction("ASCII")] = lambda : obj.copy_as(lambda data : data.encode("string_escape").replace("\"", "\\\""), False)
	action_table[string_menu.addAction("UTF-8 URL")] = lambda : obj.copy_as(encode_url, False)
	action_table[string_menu.addAction("UTF-8 IDNA")] = lambda : obj.copy_as(lambda data : data.decode("utf8").encode("idna"), False)
	action_table[string_menu.addAction("UTF-16 (\\u)")] = lambda : obj.copy_as(lambda data : encode_utf16_string(data, "\\u"), False)
	action_table[string_menu.addAction("UTF-16 (%u)")] = lambda : obj.copy_as(lambda data : encode_utf16_string(data, "%u"), False)
	action_table[string_menu.addAction("UTF-16 URL")] = lambda : obj.copy_as(lambda data : encode_url(data.decode("utf16").encode("utf8")), False)
	action_table[string_menu.addAction("UTF-16 IDNA")] = lambda : obj.copy_as(lambda data : data.decode("utf16").encode("idna"), False)
	unicode_menu = menu.addMenu("Unicode")
	action_table[unicode_menu.addAction("UTF-16")] = lambda : obj.copy_as(lambda data : data.decode("utf16"), False)
	action_table[unicode_menu.addAction("UTF-32")] = lambda : obj.copy_as(lambda data : data.decode("utf32"), False)
	menu.addSeparator()
	action_table[menu.addAction("Hex dump")] = lambda : obj.copy_as(hex_dump_encode, False)
	action_table[menu.addAction("Raw hex")] = lambda : obj.copy_as(lambda data : data.encode("hex"), False)
	action_table[menu.addAction("Base64")] = lambda : obj.copy_as(lambda data : data.encode("base64"), False)
	action_table[menu.addAction("UUEncode")] = lambda : obj.copy_as(lambda data : data.encode("uu_codec"), False)
	compress_menu = menu.addMenu("Compressed")
	action_table[compress_menu.addAction("zlib")] = lambda : obj.copy_as(lambda data : data.encode("zlib"), True)
	action_table[compress_menu.addAction("bz2")] = lambda : obj.copy_as(lambda data : data.encode("bz2"), True)
	menu.addSeparator()
	array_menu = menu.addMenu("C array")
	action_table[array_menu.addAction("8-bit elements")] = lambda : obj.copy_as(lambda data : encode_c_array(data, 1, "B", "unsigned char", ""), False)
	action_table[array_menu.addAction("16-bit elements")] = lambda : obj.copy_as(lambda data : encode_c_array(data, 2, "<H", "unsigned short", ""), False)
	action_table[array_menu.addAction("32-bit elements")] = lambda : obj.copy_as(lambda data : encode_c_array(data, 4, "<I", "unsigned int", ""), False)
	action_table[array_menu.addAction("64-bit elements")] = lambda : obj.copy_as(lambda data : encode_c_array(data, 8, "<Q", "unsigned long long", "LL"), False)
	menu.addSeparator()
	hash_menu = menu.addMenu("Hash")
	action_table[hash_menu.addAction("MD2")] = lambda : obj.copy_as(lambda data : MD2.new(data).digest(), True)
	action_table[hash_menu.addAction("MD4")] = lambda : obj.copy_as(lambda data : MD4.new(data).digest(), True)
	action_table[hash_menu.addAction("MD5")] = lambda : obj.copy_as(lambda data : MD5.new(data).digest(), True)
	action_table[hash_menu.addAction("SHA-1")] = lambda : obj.copy_as(lambda data : SHA.new(data).digest(), True)
	action_table[hash_menu.addAction("SHA-256")] = lambda : obj.copy_as(lambda data : SHA256.new(data).digest(), True)
	hmac_menu = hash_menu.addMenu("HMAC")
	action_table[hmac_menu.addAction("MD2")] = lambda : obj.copy_as(lambda data : HMAC.new(request_key(obj), data, MD2).digest(), True)
	action_table[hmac_menu.addAction("MD4")] = lambda : obj.copy_as(lambda data : HMAC.new(request_key(obj), data, MD4).digest(), True)
	action_table[hmac_menu.addAction("MD5")] = lambda : obj.copy_as(lambda data : HMAC.new(request_key(obj), data, MD5).digest(), True)
	action_table[hmac_menu.addAction("SHA-1")] = lambda : obj.copy_as(lambda data : HMAC.new(request_key(obj), data, SHA).digest(), True)
	action_table[hmac_menu.addAction("SHA-256")] = lambda : obj.copy_as(lambda data : HMAC.new(request_key(obj), data, SHA256).digest(), True)

def populate_paste_from_menu(menu, obj, action_table):
	string_menu = menu.addMenu("Escaped string")
	action_table[string_menu.addAction("ASCII")] = lambda : obj.paste_from(lambda data : data.decode("string_escape"))
	action_table[string_menu.addAction("UTF-8 URL")] = lambda : obj.paste_from(decode_url)
	action_table[string_menu.addAction("UTF-8 IDNA")] = lambda : obj.paste_from(lambda data : data.decode("idna").encode("utf8"))
	action_table[string_menu.addAction("UTF-16 (\\u)")] = lambda : obj.paste_from(lambda data : data.decode("unicode_escape").encode("utf-16le"))
	action_table[string_menu.addAction("UTF-16 (%u)")] = lambda : obj.paste_from(lambda data : decode_url(data).decode("utf8").encode("utf-16le"))
	action_table[string_menu.addAction("UTF-16 URL")] = lambda : obj.paste_from(lambda data : decode_url(data).decode("utf8").encode("utf-16le"))
	action_table[string_menu.addAction("UTF-16 IDNA")] = lambda : obj.paste_from(lambda data : data.decode("idna").encode("utf-16le"))
	unicode_menu = menu.addMenu("Unicode")
	action_table[unicode_menu.addAction("UTF-16")] = lambda : obj.paste_from(lambda data : data.decode("utf8").encode("utf-16le"))
	action_table[unicode_menu.addAction("UTF-32")] = lambda : obj.paste_from(lambda data : data.decode("utf8").encode("utf-32le"))
	menu.addSeparator()
	action_table[menu.addAction("Hex dump")] = lambda : obj.paste_from(hex_dump_decode)
	action_table[menu.addAction("Raw hex")] = lambda : obj.paste_from(lambda data : data.translate(None, " ,\t\r\n").decode("hex"))
	action_table[menu.addAction("Base64")] = lambda : obj.paste_from(lambda data : data.decode("base64"))
	action_table[menu.addAction("UUEncode")] = lambda : obj.paste_from(lambda data : data.decode("uu_codec"))
	action_table[menu.addAction("Python expression")] = lambda : obj.paste_from(lambda data : eval(data))
	compress_menu = menu.addMenu("Compressed")
	action_table[compress_menu.addAction("zlib")] = lambda : obj.paste_from(lambda data : data.decode("zlib"))
	action_table[compress_menu.addAction("bz2")] = lambda : obj.paste_from(lambda data : data.decode("bz2"))
	menu.addSeparator()
	list_menu = menu.addMenu("Integer list")
	action_table[list_menu.addAction("8-bit elements")] = lambda : obj.paste_from(lambda data : decode_int_list(data, "b", "B"))
	action_table[list_menu.addAction("16-bit elements")] = lambda : obj.paste_from(lambda data : decode_int_list(data, "<h", "<H"))
	action_table[list_menu.addAction("32-bit elements")] = lambda : obj.paste_from(lambda data : decode_int_list(data, "<i", "<I"))
	action_table[list_menu.addAction("64-bit elements")] = lambda : obj.paste_from(lambda data : decode_int_list(data, "<q", "<Q"))

