# Binary Ninja (OBSOLETE PYTHON PROTOTYPE)
This is the Binary Ninja prototype, written in Python. See [binary.ninja](https://binary.ninja) for information about the current version.

This source code is released under the [GPLv2 license](https://www.gnu.org/licenses/gpl-2.0.html). The individual disassembler libraries (which include `X86.py`, `PPC.py`, and `ARM.py`) are released under the [MIT license](http://opensource.org/licenses/MIT).

Binary Ninja and the Binary Ninja logo are trademarks of Vector 35 LLC.

## Running Binary Ninja
Binary Ninja is cross-platform and can run on Linux, Mac OS X, Windows, and FreeBSD. In order to run Binary Ninja, you will need to install a few prerequisites:

* [Python 2.7](https://www.python.org/downloads/)
* [PySide](https://pypi.python.org/pypi/PySide#installing-prerequisites) for Qt Python bindings
* The [pycrypto](https://www.dlitz.net/software/pycrypto/) library

You can start Binary Ninja by running `binja.py` in the Python interpreter.

### Windows Step-by-step Instructions

* Install the latest [Python 2.7](https://www.python.org/downloads/).
* In a command-prompt, run:
```
    cd \Python27\Scripts
    pip install PySide
    easy_install http://www.voidspace.org.uk/downloads/pycrypto26/pycrypto-2.6.win32-py2.7.exe
```
* Install [SourceTree](http://www.sourcetreeapp.com/download/) or [GitHub for Windows](https://windows.github.com/)
* Clone `https://github.com/Vector35/binaryninja-python` to a local folder using whichever tool you installed.
* Run `binja.py` from the directory you cloned the source code into
