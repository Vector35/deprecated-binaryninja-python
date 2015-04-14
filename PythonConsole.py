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
from Fonts import *
import code
import sys
import threading
import Threads

class PythonConsoleOutput():
	def __init__(self, orig, error):
		self.stdout = orig
		self.error = error

	def write(self, data):
		console = None
		if "value" in dir(_python_console):
			console = _python_console.value

		if console is None:
			self.stdout.write(data)
		else:
			if self.error:
				Threads.run_on_gui_thread(lambda: console.write_stderr(data))
			else:
				Threads.run_on_gui_thread(lambda: console.write_stdout(data))

class PythonConsoleInput():
	def __init__(self, orig):
		self.stdin = orig

	def read(self, size):
		console = None
		if "value" in dir(_python_console):
			console = _python_console.value

		if console is None:
			return self.stdin.read(size)
		else:
			return console.read_stdin(size)

	def readline(self):
		console = None
		if "value" in dir(_python_console):
			console = _python_console.value

		if console is None:
			return self.stdin.readline()
		else:
			return console.readline_stdin()

class PythonConsoleThread(threading.Thread):
	def __init__(self, console):
		threading.Thread.__init__(self)
		self.console = console
		self.globals = {"__name__":"__console__", "__doc__":None}
		self.code = None
		self.event = threading.Event()
		self.done = threading.Event()
		self.exit = False
		self.interpreter = code.InteractiveInterpreter(self.globals)

		# There is no way to interrupt a thread that isn't the main thread, so
		# to avoid not being able to close the app, create the thread as
		# as daemon thread.
		self.daemon = True

		# Set up environment with useful variables and functions
		self.globals["data"] = Threads.GuiObjectProxy(self.console.view.data)
		self.globals["exe"] = Threads.GuiObjectProxy(self.console.view.exe)
		self.globals["view"] = Threads.GuiObjectProxy(self.console.view)

		self.globals["current_view"] = Threads.GuiObjectProxy(lambda: self.console.view.view)
		self.globals["change_view"] = Threads.GuiObjectProxy(lambda type: self.console.view.setViewType(type))
		self.globals["navigate"] = Threads.GuiObjectProxy(lambda type, pos: self.console.view.navigate(type, pos))
		self.globals["create_file"] = Threads.GuiObjectProxy(lambda data: Threads.create_file(data))

		self.globals["cursor"] = Threads.GuiObjectProxy(lambda: self.console.view.view.get_cursor_pos())
		self.globals["set_cursor"] = Threads.GuiObjectProxy(lambda pos: self.console.view.view.set_cursor_pos(pos))
		self.globals["selection_range"] = Threads.GuiObjectProxy(lambda: self.console.view.view.get_selection_range())
		self.globals["set_selection_range"] = Threads.GuiObjectProxy(lambda start, end: self.console.view.view.set_selection_range(start, end))
		self.globals["selection"] = Threads.GuiObjectProxy(lambda: self.get_selection())
		self.globals["replace_selection"] = Threads.GuiObjectProxy(lambda value: self.replace_selection(value))
		self.globals["write_at_cursor"] = Threads.GuiObjectProxy(lambda value: self.write_at_cursor(value))

		self.globals["undo"] = Threads.GuiObjectProxy(lambda: self.console.view.undo())
		self.globals["redo"] = Threads.GuiObjectProxy(lambda: self.console.view.redo())
		self.globals["commit"] = Threads.GuiObjectProxy(lambda: self.console.view.commit_undo())

		self.globals["copy"] = Threads.GuiObjectProxy(lambda value: self.copy(value))
		self.globals["paste"] = Threads.GuiObjectProxy(lambda: self.console.view.view.paste())
		self.globals["clipboard"] = Threads.GuiObjectProxy(lambda: self.get_clipboard())

	# Helper APIs
	def get_selection(self):
		data = self.console.view.view.data
		range = self.console.view.view.get_selection_range()
		return data.read(range[0], range[1] - range[0])

	def replace_selection(self, value):
		data = self.console.view.view.data
		range = self.console.view.view.get_selection_range()
		if (range[1] - range[0]) == len(value):
			result = data.write(range[0], value)
		else:
			data.remove(range[0], range[1] - range[0])
			result = data.insert(range[0], value)
		self.console.view.view.set_cursor_pos(range[0] + result)
		return result

	def write_at_cursor(self, value):
		data = self.console.view.view.data
		pos = self.console.view.view.get_cursor_pos()
		result = data.write(pos, value)
		self.console.view.view.set_cursor_pos(pos + result)
		return result

	def copy(self, data):
		if type(data) != str:
			data = str(data)
		clipboard = QApplication.clipboard()
		clipboard.clear()
		mime = QMimeData()
		mime.setText(data.encode("string_escape").replace("\"", "\\\""))
		mime.setData("application/octet-stream", QByteArray(data))
		clipboard.setMimeData(mime)

	def get_clipboard(self):
		clipboard = QApplication.clipboard()
		mime = clipboard.mimeData()
		if mime.hasFormat("application/octet-stream"):
			return mime.data("application/octet-stream").data()
		elif mime.hasText():
			return mime.text().encode("utf8")
		else:
			return None

	# Thread run loop
	def run(self):
		_python_console.value = self.console
		while not self.exit:
			self.event.wait()
			self.event.clear()
			if self.exit:
				break
			if self.code:
				self.interpreter.runsource(self.code)
				self.code = None
				self.done.set()

class PythonConsoleLineEdit(QLineEdit):
	prevHistory = Signal(())
	nextHistory = Signal(())

	def __init__(self, *args):
		super(PythonConsoleLineEdit, self).__init__(*args)

	def event(self, event):
		if (event.type() == QEvent.KeyPress) and (event.key() == Qt.Key_Tab):
			self.insert("\t")
			return True
		if (event.type() == QEvent.KeyPress) and (event.key() == Qt.Key_Up):
			self.prevHistory.emit()
			return True
		if (event.type() == QEvent.KeyPress) and (event.key() == Qt.Key_Down):
			self.nextHistory.emit()
			return True
		return QLineEdit.event(self, event)

class PythonConsole(QWidget):
	def __init__(self, view):
		super(PythonConsole, self).__init__(view)
		self.view = view

		font = getMonospaceFont()

		layout = QVBoxLayout()
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(0)

		self.output = QTextEdit()
		self.output.setFont(font)
		self.output.setReadOnly(True)
		layout.addWidget(self.output, 1)

		input_layout = QHBoxLayout()
		input_layout.setContentsMargins(4, 4, 4, 4)
		input_layout.setSpacing(4)

		self.prompt = QLabel(">>>")
		self.prompt.setFont(font)
		input_layout.addWidget(self.prompt)
		self.input = PythonConsoleLineEdit()
		self.input.setFont(font)
		self.input.returnPressed.connect(self.process_input)
		self.input.prevHistory.connect(self.prev_history)
		self.input.nextHistory.connect(self.next_history)
		input_layout.addWidget(self.input)

		layout.addLayout(input_layout, 0)

		self.setLayout(layout)
		self.setFocusPolicy(Qt.NoFocus)
		self.setMinimumSize(100, 100)

		size_policy = self.sizePolicy()
		size_policy.setVerticalStretch(1)
		self.setSizePolicy(size_policy)

		self.thread = PythonConsoleThread(self)
		self.thread.start()

		self.completion_timer = QTimer()
		self.completion_timer.setInterval(100)
		self.completion_timer.setSingleShot(False)
		self.completion_timer.timeout.connect(self.completion_timer_event)
		self.completion_timer.start()

		self.source = None
		self.running = False

		self.input_requested = False
		self.input_result = ""
		self.input_event = threading.Event()

		self.input_history = []
		self.input_history_pos = None

	def stop(self):
		self.thread.exit = True
		self.thread.event.set()
		# Can't join here, as it might be stuck in user code

	def process_input(self):
		self.input_history += [str(self.input.text())]
		self.input_history_pos = None

		input = str(self.input.text()) + "\n"
		self.input.setText("")

		self.output.textCursor().movePosition(QTextCursor.End)
		fmt = QTextCharFormat()
		fmt.setForeground(QBrush(Qt.black))
		if len(self.prompt.text()) > 0:
			self.output.textCursor().insertText(self.prompt.text() + " " + input, fmt)
		else:
			self.output.textCursor().insertText(input, fmt)
		self.output.ensureCursorVisible()

		if self.input_requested:
			# Request for data from stdin
			self.input_requested = False
			self.input.setEnabled(False)
			self.input_result = input
			self.input_event.set()
			return

		if self.source is not None:
			self.source = self.source + input
			if input != "\n":
				# Don't end multiline input until a blank line
				return
			input = self.source

		try:
			result = code.compile_command(input)
		except:
			result = False

		if result is None:
			if self.source is None:
				self.source = input
			else:
				self.source += input
			self.prompt.setText("...")
			return

		self.source = None
		self.prompt.setText(">>>")

		self.thread.code = input
		self.thread.event.set()
		self.running = True

		self.thread.done.wait(0.05)
		if self.thread.done.is_set():
			self.thread.done.clear()
			self.running = False
		else:
			self.input.setEnabled(False)

	def prev_history(self):
		if len(self.input_history) == 0:
			return
		if self.input_history_pos is None:
			self.input_history_pos = len(self.input_history)
		if self.input_history_pos == 0:
			return
		self.input_history_pos -= 1
		self.input.setText(self.input_history[self.input_history_pos])

	def next_history(self):
		if self.input_history_pos is None:
			return
		if (self.input_history_pos + 1) >= len(self.input_history):
			self.input_history_pos = None
			self.input.setText("")
			return
		self.input_history_pos += 1
		self.input.setText(self.input_history[self.input_history_pos])

	def completion_timer_event(self):
		if self.thread.done.is_set():
			self.thread.done.clear()
			self.running = False
			self.input.setEnabled(True)
			self.input.setFocus(Qt.OtherFocusReason)
			self.prompt.setText(">>>")

	def request_input(self):
		self.input_requested = True
		self.input.setEnabled(True)
		self.input.setFocus(Qt.OtherFocusReason)
		self.prompt.setText("")

	def write_stdout(self, data):
		self.output.textCursor().movePosition(QTextCursor.End)
		fmt = QTextCharFormat()
		fmt.setForeground(QBrush(Qt.blue))
		self.output.textCursor().insertText(data, fmt)
		self.output.ensureCursorVisible()

	def write_stderr(self, data):
		self.output.textCursor().movePosition(QTextCursor.End)
		fmt = QTextCharFormat()
		fmt.setForeground(QBrush(Qt.red))
		self.output.textCursor().insertText(data, fmt)
		self.output.ensureCursorVisible()

	def read_stdin(self, size):
		if Threads.is_gui_thread():
			raise RuntimeError, "Cannot call read_stdin from GUI thread"

		if len(self.input_result) == 0:
			Threads.run_on_gui_thread(self.request_input)
			self.input_event.wait()
			self.input_event.clear()

		if len(self.input_result) > size:
			result = self.input_result[0:size]
			self.input_result = self.input_result[size:]
			return result

		result = self.input_result
		self.input_result = ""
		return 

	def readline_stdin(self):
		if Threads.is_gui_thread():
			raise RuntimeError, "Cannot call readline_stdin from GUI thread"

		if len(self.input_result) == 0:
			Threads.run_on_gui_thread(self.request_input)
			self.input_event.wait()
			self.input_event.clear()

		result = self.input_result
		self.input_result = ""
		return result


sys.stderr = PythonConsoleOutput(sys.stderr, True)
sys.stdout = PythonConsoleOutput(sys.stdout, False)
sys.stdin = PythonConsoleInput(sys.stdin)
_python_console = threading.local()

