#!/usr/bin/env python
import os
import sys
import subprocess
import tempfile
import traceback

import logging
logger = logging.getLogger('framework')
#logger.setLevel(logging.ERROR)

class assemblyException(Exception):
	def __init__(self,message):
		super(assemblyException,self).__init__("Shellcode failed to assemble!\n" + message)

class disassemblyException(Exception):
	def __init__(self,message):
		super(disassemblyException,self).__init__("Shellcode failed to disassemble!\n" + message)

def disassemble(buff):
	infile = tempfile.NamedTemporaryFile(delete=False)
	try:
		infile.write(buff)
		infile.close()
		
		asm = "No output\n"
		asm = subprocess.check_output(["ndisasm", "-u", infile.name])
		
		os.unlink(infile.name)
	except:
		#traceback.print_exc()
		os.unlink(infile.name)
		raise disassemblyException(asm)
	
	return asm

def assemble(buff, includes='.', *args, **kwargs):
	header = kwargs.get("header", "BITS 32\n")
	infile = buff
	if type(buff) is not file:
		infile = tempfile.NamedTemporaryFile()
		infile.write(header)
		infile.write(buff)
		infile.flush()
	outfile = tempfile.NamedTemporaryFile()
	errors = "write file failed"

	define_args = []
	try:
		del kwargs["header"]
	except:
		pass

	for item in args:
		define_args.append("-d"+str(item))

	for k, v in kwargs.iteritems():
		k = str(k).upper()
		define_args.append("-D %s=%s" % (k, str(v)))
	
	nasm_args = ["nasm"]
	nasm_args.extend(define_args)
	nasm_args.append('-I '+ includes)
	nasm_args.extend(["-fbin", "-o", outfile.name, infile.name])

	try:
		logger.debug("executing: " + ' '.join(nasm_args))
		popen = subprocess.Popen(nasm_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		output, errors = popen.communicate()
		asm = outfile.read()
		if popen.returncode == 0:
			errors = None
		else:
			asm = None
	except OSError as e:
		asm = None
		errors = e.args[1]
	except:
		asm = None
	
	return (asm, errors)

def main():
	usage = "{0} [-d] [-b]\n\t-d - disassemble\n\t-b - bare (no opcodes or addresses)"
	
	dis = False
	bare = False
	if "-d" in sys.argv:
		dis = True
	if "-b" in sys.argv:
		bare = True
		
	asm = sys.stdin.read()
	out = ""
	if dis:
		out = ""
		try:
			out = disassemble(asm)
		except disassemblyException as de:
			logger.error(de.message)
			exit(1)

		if bare:
			tmp = ""
			for a in out.split("\n"):
				if a != "":
					tmp += a.split(None,2)[-1]+"\n"
			out = tmp
	else:
		try:
			out = assemble(asm)
		except assemblyException as ae:
			logger.error(ae.message)
			exit(1)
	sys.stdout.write(out)

if __name__ == "__main__":
	logger.addHandler(logging.StreamHandler())
	main()
