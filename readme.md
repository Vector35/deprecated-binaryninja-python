# Binary Ninja
This is the Binary Ninja prototype, written in Python. See [binary.ninja](http://binary.ninja) for news and updates about Binary Ninja.

This source code is released under the [GPLv2 license](https://www.gnu.org/licenses/gpl-2.0.html). The individual disassembler libraries (which include `X86.py`, `PPC.py`, and `ARM.py`) are released under the [MIT license](http://opensource.org/licenses/MIT).

Binary Ninja and the Binary Ninja logo are trademarks of Vector 35 LLC.

## Running Binary Ninja
Binary Ninja is cross-platform and can run on Linux, Mac OS X, Windows, and FreeBSD. In order to run Binary Ninja, you will need to install a few prerequisites:

* [Python 2.7](https://www.python.org/downloads/)
* [PySide](https://pypi.python.org/pypi/PySide#installing-prerequisites) for Qt Python bindings
* The [pycrypto](https://www.dlitz.net/software/pycrypto/) library

You can start Binary Ninja by running `binja.py` in the Python interpreter.

