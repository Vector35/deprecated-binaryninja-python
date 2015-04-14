# Copyright (c) 2012-2015 Rusty Wagner
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

import os
import sys
import struct
import threading
import time
if os.name != "nt":
	# Windows doesn't do PTYs
	import pty
	import subprocess
	import select
	import fcntl
	import termios
	import signal
from TerminalEmulator import *
from Threads import *


class TerminalUpdateThread(threading.Thread):
	def __init__(self, proc, data_pipe, exit_pipe):
		super(TerminalUpdateThread, self).__init__()
		self.proc = proc
		self.data_pipe = data_pipe
		self.exit_pipe = exit_pipe
		self.running = True
		self.alive = True

	def run(self):
		while self.running:
			self.proc.check_for_output(self, self.data_pipe, self.exit_pipe)
		os.close(self.data_pipe)
		os.close(self.exit_pipe)
		self.alive = False

	def stop(self):
		self.running = False


class TerminalProcess:
	def __init__(self, cmd, raw_debug = None):
		if os.name == "nt":
			raise RuntimeError, "Windows does not support pseudo-terminal devices"

		if cmd:
			# Spawn the new process in a new PTY
			self.exit_pipe, child_pipe = os.pipe()
			self.exit_callback = None

			pid, fd = pty.fork()
			if pid == 0:
				try:
					os.environ["TERM"] = "xterm-256color"
					if "PYTHONPATH" in os.environ:
						del(os.environ["PYTHONPATH"])
					if "LD_LIBRARY_PATH" in os.environ:
						del(os.environ["LD_LIBRARY_PATH"])
					if sys.platform == "darwin":
						if "DYLD_LIBRARY_PATH" in os.environ:
							del(os.environ["DYLD_LIBRARY_PATH"])

					retval = subprocess.call(cmd, close_fds=True)
					os.write(2, "\033[01;34mProcess has completed.\033[00m\n")
					os.write(child_pipe, "t")
					os._exit(retval)
				except:
					pass
				os.write(2, "\033[01;31mCommand '" + cmd[0] + "' failed to execute.\033[00m\n")
				os.write(child_pipe, "f")
				os._exit(1)

			os.close(child_pipe)

			self.pid = pid
			self.data_pipe = fd
		else:
			self.exit_pipe = -1
			self.pid = -1
			self.data_pipe = -1

		self.rows = 25
		self.cols = 80
		self.term = TerminalEmulator(self.rows, self.cols)
		self.raw_debug = raw_debug
		self.completed = False

		self.term.response_callback = self.send_input

		if cmd:
			# Initialize terminal settings
			fcntl.ioctl(self.data_pipe, termios.TIOCSWINSZ, struct.pack("hhhh", self.rows, self.cols, 0, 0))
			attribute = termios.tcgetattr(self.data_pipe)
			termios.tcsetattr(self.data_pipe, termios.TCSAFLUSH, attribute)
		else:
			self.process_input("\033[01;33mEnter desired command arguments, then run again.\033[00m\r\n")
			self.completed = True

	def process_input(self, data):
		self.term.process(data)
		if self.raw_debug is not None:
			self.raw_debug.insert(len(self.raw_debug), data)

	def exit_notify(self, thread, ok):
		if thread == self.thread:
			# Process that is exiting was the active process, notify owner
			self.completed = True
			if self.exit_callback:
				run_on_gui_thread(lambda: self.exit_callback(ok))
		thread.stop()

	def check_for_output(self, thread, data_pipe, exit_pipe):
		# Combine writes in 20ms intervals to avoid too many calls to run_on_gui_thread
		ready_data = ""
		timeout = 0.02
		end_time = time.time() + timeout

		while len(ready_data) < 8192:
			input_ready, output_ready, error = select.select([data_pipe, exit_pipe], [], [], timeout)
			if data_pipe in input_ready:
				try:
					data = os.read(data_pipe, 4096)
				except:
					data = ""
				if len(data) > 0:
					ready_data += data
					timeout = end_time - time.time()
					if timeout > 0:
						continue
			if exit_pipe in input_ready:
				result = os.read(exit_pipe, 1)
				if result == "t":
					ok = True
				else:
					ok = False
				run_on_gui_thread(lambda: self.exit_notify(thread, ok))
			break

		if len(ready_data) > 0:
			run_on_gui_thread(lambda: self.process_input(ready_data))
			return True
		return False

	def send_input(self, data):
		try:
			os.write(self.data_pipe, data)
		except:
			pass

	def resize(self, rows, cols):
		if (self.rows == rows) and (self.cols == cols):
			return

		self.rows = rows
		self.cols = cols
		self.term.resize(self.rows, self.cols)

		if not self.completed:
			fcntl.ioctl(self.data_pipe, termios.TIOCSWINSZ, struct.pack("hhhh", self.rows, self.cols, 0, 0))

	def start_monitoring(self):
		if not self.completed:
			self.thread = TerminalUpdateThread(self, self.data_pipe, self.exit_pipe)
			self.thread.start()

	def kill(self):
		if not self.completed:
			os.kill(self.pid, signal.SIGHUP)
			thread = self.thread
			thread.stop()
			while thread.alive:
				QCoreApplication.processEvents()

	def restart(self, cmd):
		if not self.completed:
			self.process_input("\n\033[01;31mProcess killed.\033[00m\r\n")
			os.kill(self.pid, signal.SIGHUP)
			thread = self.thread
			thread.stop()
			while thread.alive:
				QCoreApplication.processEvents()

		self.exit_pipe, child_pipe = os.pipe()
		pid, fd = pty.fork()
		if pid == 0:
			try:
				os.environ["TERM"] = "xterm-256color"
				retval = subprocess.call(cmd, close_fds=True)
				os.write(2, "\033[01;34mProcess has completed.\033[00m\n")
				os.write(child_pipe, "t")
				os._exit(retval)
			except:
				pass
			os.write(2, "\033[01;31mCommand '" + cmd[0] + "' failed to execute.\033[00m\n")
			os.write(child_pipe, "f")
			os._exit(1)

		os.close(child_pipe)
		self.process_input("\033[01;34mStarted process with PID %d.\033[00m\r\n" % pid)

		self.pid = pid
		self.data_pipe = fd
		self.completed = False

		# Initialize terminal settings
		fcntl.ioctl(self.data_pipe, termios.TIOCSWINSZ, struct.pack("hhhh", self.rows, self.cols, 0, 0))
		attribute = termios.tcgetattr(self.data_pipe)
		termios.tcsetattr(self.data_pipe, termios.TCSAFLUSH, attribute)

		self.thread = TerminalUpdateThread(self, self.data_pipe, self.exit_pipe)
		self.thread.start()

	def reinit(self):
		self.rows = 25
		self.cols = 80
		self.term = TerminalEmulator(self.rows, self.cols)
		self.term.response_callback = self.send_input
		self.process_input("\033[01;33mEnter desired command arguments, then run again.\033[00m\r\n")

