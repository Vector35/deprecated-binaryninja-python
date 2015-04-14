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
import thread
import threading

gui_thread = None
main_window = None

class RunCodeEvent(QEvent):
	def __init__(self, code):
		super(RunCodeEvent, self).__init__(QEvent.User)
		self.code = code
		self.event = threading.Event()
		self.result = None
		self.exception = None

# Proxy to ensure that GUI calls run on the GUI thread
# Code derived from: http://code.activestate.com/recipes/496741-object-proxying/ 
class GuiObjectProxy(object):
	__slots__ = ["_obj", "__weakref__"]
	def __init__(self, obj):
		object.__setattr__(self, "_obj", obj)
	
	#
	# proxying (special cases)
	#
	def __getattribute__(self, name):
		result = run_on_gui_thread(lambda: getattr(object.__getattribute__(self, "_obj"), name))
		if result is None:
			return result
		if type(result) in [int, float, str, bool]:
			return result
		return GuiObjectProxy(result)
	def __delattr__(self, name):
		run_on_gui_thread(lambda: delattr(object.__getattribute__(self, "_obj"), name))
	def __setattr__(self, name, value):
		run_on_gui_thread(lambda: setattr(object.__getattribute__(self, "_obj"), name, value))
	
	def __nonzero__(self):
		return run_on_gui_thread(lambda: bool(object.__getattribute__(self, "_obj")))
	def __str__(self):
		return run_on_gui_thread(lambda: str(object.__getattribute__(self, "_obj")))
	def __repr__(self):
		return run_on_gui_thread(lambda: repr(object.__getattribute__(self, "_obj")))
	
	#
	# factories
	#
	_special_names = [
		'__abs__', '__add__', '__and__', '__call__', '__cmp__', '__coerce__', 
		'__contains__', '__delitem__', '__delslice__', '__div__', '__divmod__', 
		'__eq__', '__float__', '__floordiv__', '__ge__', '__getitem__', 
		'__getslice__', '__gt__', '__hash__', '__hex__', '__iadd__', '__iand__',
		'__idiv__', '__idivmod__', '__ifloordiv__', '__ilshift__', '__imod__', 
		'__imul__', '__int__', '__invert__', '__ior__', '__ipow__', '__irshift__', 
		'__isub__', '__iter__', '__itruediv__', '__ixor__', '__le__', '__len__', 
		'__long__', '__lshift__', '__lt__', '__mod__', '__mul__', '__ne__', 
		'__neg__', '__oct__', '__or__', '__pos__', '__pow__', '__radd__', 
		'__rand__', '__rdiv__', '__rdivmod__', '__reduce__', '__reduce_ex__', 
		'__repr__', '__reversed__', '__rfloorfiv__', '__rlshift__', '__rmod__', 
		'__rmul__', '__ror__', '__rpow__', '__rrshift__', '__rshift__', '__rsub__', 
		'__rtruediv__', '__rxor__', '__setitem__', '__setslice__', '__sub__', 
		'__truediv__', '__xor__', 'next',
	]
	
	@classmethod
	def _create_class_proxy(cls, theclass):
		"""creates a proxy for the given class"""
		
		def make_method(name):
			def method(self, *args, **kw):
				return run_on_gui_thread(lambda: getattr(object.__getattribute__(self, "_obj"), name)(*args, **kw))
			return method
		
		namespace = {}
		for name in cls._special_names:
			if hasattr(theclass, name):
				namespace[name] = make_method(name)
		return type("%s(%s)" % (cls.__name__, theclass.__name__), (cls,), namespace)
	
	def __new__(cls, obj, *args, **kwargs):
		"""
		creates an proxy instance referencing `obj`. (obj, *args, **kwargs) are
		passed to this class' __init__, so deriving classes can define an 
		__init__ method of their own.
		note: _class_proxy_cache is unique per deriving class (each deriving
		class must hold its own cache)
		"""
		try:
			cache = cls.__dict__["_class_proxy_cache"]
		except KeyError:
			cls._class_proxy_cache = cache = {}
		try:
			theclass = cache[obj.__class__]
		except KeyError:
			cache[obj.__class__] = theclass = cls._create_class_proxy(obj.__class__)
		ins = object.__new__(theclass)
		theclass.__init__(ins, obj, *args, **kwargs)
		return ins

def is_gui_thread():
	global gui_thread
	return thread.get_ident() == gui_thread

def run_on_gui_thread(code):
	global main_window
	if is_gui_thread():
		return code()
	event = RunCodeEvent(code)
	QCoreApplication.postEvent(main_window, event)
	event.event.wait()
	if event.exception is not None:
		raise event.exception[0], event.exception[1], event.exception[2]
	return event.result

def create_file(data):
	global main_window
	main_window.create_tab_from_data(data)

