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

from PySide.QtCore import *
from PySide.QtGui import *
from Crypto.Cipher import AES
from Crypto.Cipher import Blowfish
from Crypto.Cipher import CAST
from Crypto.Cipher import DES
from Crypto.Cipher import DES3
from Crypto.Cipher import ARC2
from Crypto.Cipher import ARC4
import HexEditor
import View
import BinaryData


class KeyDialog(QDialog):
	def __init__(self, parent, iv = False):
		super(KeyDialog, self).__init__(parent)
		self.key = BinaryData.BinaryData("")
		if iv:
			self.iv = BinaryData.BinaryData("")

		self.setWindowTitle("Input Key")
		layout = QVBoxLayout()

		layout.addWidget(QLabel("Key:"))
		self.edit = View.ViewFrame(HexEditor.HexEditor, self.key, "", [HexEditor.HexEditor])
		if iv:
			self.edit.setMinimumSize(600, 32)
		else:
			self.edit.setMinimumSize(600, 64)
		layout.addWidget(self.edit, 1)

		if iv:
			layout.addWidget(QLabel("Initialization vector:"))
			self.iv_edit = View.ViewFrame(HexEditor.HexEditor, self.iv, "", [HexEditor.HexEditor])
			self.iv_edit.setMinimumSize(600, 32)
			layout.addWidget(self.iv_edit, 1)

		self.closeButton = QPushButton("Close")
		self.closeButton.clicked.connect(self.close)
		self.closeButton.setAutoDefault(False)

		self.assembleButton = QPushButton("OK")
		self.assembleButton.clicked.connect(self.accept)
		self.assembleButton.setAutoDefault(True)

		buttonLayout = QHBoxLayout()
		buttonLayout.setContentsMargins(0, 0, 0, 0)
		buttonLayout.addStretch(1)
		buttonLayout.addWidget(self.assembleButton)
		buttonLayout.addWidget(self.closeButton)
		layout.addLayout(buttonLayout)
		self.setLayout(layout)


def xor_transform(data, key):
	if len(key) == 0:
		return data

	result = ""
	for i in xrange(0, len(data)):
		result += chr(ord(data[i]) ^ ord(key[i % len(key)]))
	return result

def aes_encrypt_transform(data, key, mode, iv):
	aes = AES.new(key, mode, iv)
	return aes.encrypt(data)

def aes_decrypt_transform(data, key, mode, iv):
	aes = AES.new(key, mode, iv)
	return aes.decrypt(data)

def blowfish_encrypt_transform(data, key, mode, iv):
	blowfish = Blowfish.new(key, mode, iv)
	return blowfish.encrypt(data)

def blowfish_decrypt_transform(data, key, mode, iv):
	blowfish = Blowfish.new(key, mode, iv)
	return blowfish.decrypt(data)

def cast_encrypt_transform(data, key, mode, iv):
	cast = CAST.new(key, mode, iv)
	return cast.encrypt(data)

def cast_decrypt_transform(data, key, mode, iv):
	cast = CAST.new(key, mode, iv)
	return cast.decrypt(data)

def des_encrypt_transform(data, key, mode, iv):
	des = DES.new(key, mode, iv)
	return des.encrypt(data)

def des_decrypt_transform(data, key, mode, iv):
	des = DES.new(key, mode, iv)
	return des.decrypt(data)

def des3_encrypt_transform(data, key, mode, iv):
	des = DES3.new(key, mode, iv)
	return des.encrypt(data)

def des3_decrypt_transform(data, key, mode, iv):
	des = DES3.new(key, mode, iv)
	return des.decrypt(data)

def rc2_encrypt_transform(data, key, mode, iv):
	arc2 = ARC2.new(key, mode, iv)
	return arc2.encrypt(data)

def rc2_decrypt_transform(data, key, mode, iv):
	arc2 = ARC2.new(key, mode, iv)
	return arc2.decrypt(data)

def rc4_transform(data, key):
	arc4 = ARC4.new(key)
	return arc4.encrypt(data)


def populate_transform_menu(menu, obj, action_table):
	aes_menu = menu.addMenu("AES")
	aes_ecb_menu = aes_menu.addMenu("ECB mode")
	aes_cbc_menu = aes_menu.addMenu("CBC mode")
	action_table[aes_ecb_menu.addAction("Encrypt")] = lambda: obj.transform_with_key(lambda data, key: aes_encrypt_transform(data, key, AES.MODE_ECB, ""))
	action_table[aes_ecb_menu.addAction("Decrypt")] = lambda: obj.transform_with_key(lambda data, key: aes_decrypt_transform(data, key, AES.MODE_ECB, ""))
	action_table[aes_cbc_menu.addAction("Encrypt")] = lambda: obj.transform_with_key_and_iv(lambda data, key, iv: aes_encrypt_transform(data, key, AES.MODE_CBC, iv))
	action_table[aes_cbc_menu.addAction("Decrypt")] = lambda: obj.transform_with_key_and_iv(lambda data, key, iv: aes_decrypt_transform(data, key, AES.MODE_CBC, iv))

	blowfish_menu = menu.addMenu("Blowfish")
	blowfish_ecb_menu = blowfish_menu.addMenu("ECB mode")
	blowfish_cbc_menu = blowfish_menu.addMenu("CBC mode")
	action_table[blowfish_ecb_menu.addAction("Encrypt")] = lambda: obj.transform_with_key(lambda data, key: blowfish_encrypt_transform(data, key, Blowfish.MODE_ECB, ""))
	action_table[blowfish_ecb_menu.addAction("Decrypt")] = lambda: obj.transform_with_key(lambda data, key: blowfish_decrypt_transform(data, key, Blowfish.MODE_ECB, ""))
	action_table[blowfish_cbc_menu.addAction("Encrypt")] = lambda: obj.transform_with_key_and_iv(lambda data, key, iv: blowfish_encrypt_transform(data, key, Blowfish.MODE_CBC, iv))
	action_table[blowfish_cbc_menu.addAction("Decrypt")] = lambda: obj.transform_with_key_and_iv(lambda data, key, iv: blowfish_decrypt_transform(data, key, Blowfish.MODE_CBC, iv))

	cast_menu = menu.addMenu("CAST")
	cast_ecb_menu = cast_menu.addMenu("ECB mode")
	cast_cbc_menu = cast_menu.addMenu("CBC mode")
	action_table[cast_ecb_menu.addAction("Encrypt")] = lambda: obj.transform_with_key(lambda data, key: cast_encrypt_transform(data, key, CAST.MODE_ECB, ""))
	action_table[cast_ecb_menu.addAction("Decrypt")] = lambda: obj.transform_with_key(lambda data, key: cast_decrypt_transform(data, key, CAST.MODE_ECB, ""))
	action_table[cast_cbc_menu.addAction("Encrypt")] = lambda: obj.transform_with_key_and_iv(lambda data, key, iv: cast_encrypt_transform(data, key, CAST.MODE_CBC, iv))
	action_table[cast_cbc_menu.addAction("Decrypt")] = lambda: obj.transform_with_key_and_iv(lambda data, key, iv: cast_decrypt_transform(data, key, CAST.MODE_CBC, iv))

	des_menu = menu.addMenu("DES")
	des_ecb_menu = des_menu.addMenu("ECB mode")
	des_cbc_menu = des_menu.addMenu("CBC mode")
	action_table[des_ecb_menu.addAction("Encrypt")] = lambda: obj.transform_with_key(lambda data, key: des_encrypt_transform(data, key, DES.MODE_ECB, ""))
	action_table[des_ecb_menu.addAction("Decrypt")] = lambda: obj.transform_with_key(lambda data, key: des_decrypt_transform(data, key, DES.MODE_ECB, ""))
	action_table[des_cbc_menu.addAction("Encrypt")] = lambda: obj.transform_with_key_and_iv(lambda data, key, iv: des_encrypt_transform(data, key, DES.MODE_CBC, iv))
	action_table[des_cbc_menu.addAction("Decrypt")] = lambda: obj.transform_with_key_and_iv(lambda data, key, iv: des_decrypt_transform(data, key, DES.MODE_CBC, iv))

	des3_menu = menu.addMenu("Triple DES")
	des3_ecb_menu = des3_menu.addMenu("ECB mode")
	des3_cbc_menu = des3_menu.addMenu("CBC mode")
	action_table[des3_ecb_menu.addAction("Encrypt")] = lambda: obj.transform_with_key(lambda data, key: des3_encrypt_transform(data, key, DES3.MODE_ECB, ""))
	action_table[des3_ecb_menu.addAction("Decrypt")] = lambda: obj.transform_with_key(lambda data, key: des3_decrypt_transform(data, key, DES3.MODE_ECB, ""))
	action_table[des3_cbc_menu.addAction("Encrypt")] = lambda: obj.transform_with_key_and_iv(lambda data, key, iv: des3_encrypt_transform(data, key, DES3.MODE_CBC, iv))
	action_table[des3_cbc_menu.addAction("Decrypt")] = lambda: obj.transform_with_key_and_iv(lambda data, key, iv: des3_decrypt_transform(data, key, DES3.MODE_CBC, iv))

	rc2_menu = menu.addMenu("RC2")
	rc2_ecb_menu = rc2_menu.addMenu("ECB mode")
	rc2_cbc_menu = rc2_menu.addMenu("CBC mode")
	action_table[rc2_ecb_menu.addAction("Encrypt")] = lambda: obj.transform_with_key(lambda data, key: rc2_encrypt_transform(data, key, ARC2.MODE_ECB, ""))
	action_table[rc2_ecb_menu.addAction("Decrypt")] = lambda: obj.transform_with_key(lambda data, key: rc2_decrypt_transform(data, key, ARC2.MODE_ECB, ""))
	action_table[rc2_cbc_menu.addAction("Encrypt")] = lambda: obj.transform_with_key_and_iv(lambda data, key, iv: rc2_encrypt_transform(data, key, ARC2.MODE_CBC, iv))
	action_table[rc2_cbc_menu.addAction("Decrypt")] = lambda: obj.transform_with_key_and_iv(lambda data, key, iv: rc2_decrypt_transform(data, key, ARC2.MODE_CBC, iv))

	action_table[menu.addAction("RC4")] = lambda: obj.transform_with_key(lambda data, key: rc4_transform(data, key))
	action_table[menu.addAction("XOR")] = lambda: obj.transform_with_key(lambda data, key: xor_transform(data, key))

