#!/usr/bin/env python
import sys, os, string
sys.path = ["/usr/lib/ptools"]+["/usr/lib/portage/pym"]+sys.path
from ptk import *

#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=

######   #    #  #     #
#     #  #   #   #  #  #
#     #  #  #    #  #  #
######   ###     #  #  #
#        #  #    #  #  #
#        #   #   #  #  #
#        #    #   ## ##
__me__ = "pkw"
__version__ = "0.0.3"
__whatido__ = "alter package keywords"
__support__ = "bugzilla@opelousas.org"
__disclaimer__ = "I suck & you can't sue me. But feel free to try, so you can suck to"
__faq__ = "Don't ask why. Just show me a better way."
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
testing = "~"+settings['ARCH']
unall = "-*"
pkw = keywords
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
# Begin Options
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
#{{{
options=[
"--any",
"--exact",
"--fix-kw",
"--help",
"--remove",
"--change",
"--version",
"--unall",
]

shortopts={
"a":"--any",
"e":"--exact",
"f":"--fix-kw",
"r":"--remove",
"c":"--change",
"h":"--help",
"u":"--unall",
"v":"--version",
}
tcl=sys.argv[1:]
cmdline=[]
myopts=[]
myargs=[]
#}}}
def help():#{{{
	print
	print
	print bold("Usage:")
	print "   "+turquoise(__me__)+" [ "+green("option")+" ] [ "+green("package")+" ] "
	print
	print bold("Options:")
	print turquoise("--any\n-a ")+bold("Add/Remove keywords for any version of the package\n")
	print turquoise("--change\n-c ")+bold("Change keywords for a package\n")
	print turquoise("--exact\n-e ")+bold("Add/Remove keywords for a single version of the package\n")
	print turquoise("--fix-kw\n-f ")+bold("Interactively cleanup package.keywords file(Incomplete)\n")
	print turquoise("--remove\n-r ")+bold("Removes a package from package.keywords\n")
	print turquoise("--help\n-h ")+bold("Show this and quit\n")
	print turquoise("--unall\n-u ")+bold("use -* keyword(Does not work with --fix-kw)\n")
	print turquoise("--version\n-v ")+bold("Print package version information and quit\n")
#	print turquoise("--\n- ")+bold("\n")
	sys.exit(1)
#}}}
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
#{{{
# short options
for x in tcl:
	if x[0:1]=="-"and x[1:2]!="-":
		for y in x[1:]:
			if shortopts.has_key(y):
				if shortopts[y] in cmdline:
					print
					print shortopts[y]," used more than once"
				else:
					cmdline.append(shortopts[y])
			else:
				print "!!! Error: -"+y+" is not a valid option."
				sys.exit(1)
	else:
		cmdline.append(x)

# long options
for x in cmdline:
	if not x:
		continue
	if len(x)>=2 and x[:2]=="--":
		x = x[2:]
		if "--"+x not in options:
			print "!!! Error:",x,"is an invalid option."
			sys.exit(1)
	if "--"+x in options:
		myopts.append("--"+x)
	else:
		myargs.append(x)
#}}}
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
# End Options 
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
# grab_kw() kicks ass
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
def grab_kw(mycpv):#{{{
	"""
	Semantics:	Get the keywords from a cpv(current only works for porttree)
	Arguements:	CPV 
	Returns:	A list of the keywords from a package's ebuild
			False if no ebuild found
	"""
	# Does the ebuild exist?
	if ( path_to_cpv(mycpv) == None ):
#		print red("!!! Cannot find an ebuild for "+ mycpv)
		return False
	else:
		return str(portdb.aux_get(mycpv,['KEYWORDS'])[0]).split()
#}}}
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
# fix_invalid_kw() if I ever finish this, it could kickass....
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
#   WILL cleanup entries no longer needed due to newer & stable packages in portage
#	This feature need has been preceded by more natural functionality in portage via etc-update
#	Use that, this way has bugs
#	That and it seems something here acts weird when trying to update to newer builds 
#	run it several times and it seems to complete... hehe
def fix_invalid_kw(mykwo):#{{{
	"""
	Compares package.keywords file to the portage tree removeing atoms that no longer affect the tree.
	"""
	try:
		fdro = open(mykwo.pkw)
	except IOError:
		ioerror(mykwo.pkw, "r")
		return 0
	# if a version is given check that its correct
#	mypld = mykwo.pld.copy()
	akeys = pld.keys()
	for k in akeys:
		acpvr = pkgsplit(k)
		mycpv = dep_getcpv(k)
		if ( acpvr == None ) & ( ' '.join(k) != "-~"+mykwo.arch ):
			print yellow("Always ") + "use testing version of "+k+" ~"+mykwo.arch
		elif ( ' '.join(k) == "-~"+mykwo.arch ):
			print green("Never ") + "use testing version of "+k+" -~"+mykwo.arch
		elif ( acpvr != None ) & ( grab_kw(mycpv) == 0 ):
			print turquoise(k+" is no longer a valid package, please choose another.")
			try:
				# grab the operator too?
				thecpv = choose_pkg(getCPFromCPV(k))
				print red("Removed "+k+" from "+pkw)
				rpld = del_kw(pld, k, depatom=True)
#				print thecpv
				addme = "="+thecpv
				write_pkw(add_kw(rpld, addme, depatom=True))
				print green("Added "+addme+" ~"+mykwo.arch+" to "+str(pkw))
			except:
				print "You loose"
				sys.exit(1)
		elif not isvalidatom(k):
			print "remove " + k
#}}}
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
# Begin Execution: AKA: say_your_prayers()
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
if __name__ == '__main__':#{{{
	if ( len(myopts) < 1):
		help()
	if ( "--help" in myopts ):
		help()
#}}}
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
# yep I plan on keeping up with this one
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
	if ( "--version" in myopts ):#{{{
		version(__version__, __whatido__, __support__)
		sys.exit(1)
#}}}
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
# 
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
	if ( "--change" in myopts):#{{{
		if ( "--any" in myopts ):
			pkg = myargs[0]
			p = package(cp=get_cp_from_str(pkg))
			if ("--unall" in myopts ):
				kw = unall
			else:
				kw = testing
			p.add_kw(kw)
			print green("Adding ") + p.cp + " " + yellow(kw) +" to " + str(keywords)
			p.write_pkw()
			sys.exit(1)
		elif ("--exact" in myopts ):
			pkg = myargs[0]
			p = package(cpv=choose_pkg(pkg))
			if ("--unall" in myopts ):
				kw = unall
			else:
				kw = testing
			p.add_kw(kw)
			print green("Adding ") + p.cpv + " " + yellow(kw) +" to " + str(keywords)
			p.write_pkw()
			sys.exit(1)
		else:
			help()
#}}}
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
# fix em because im lazy, very very lazy *aparently the portage guys thought of this
# also. TODO: fix fix_invalid_kw() to work with package()
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
	if ("--fix-kw" in myopts):#{{{
		print red(">>> ")+bold("This will erase all comments in " + pkw)
		fix_invalid_kw(__kwo__)
		sys.exit(1)
#}}}
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
# remove em because this is easier than finishing fix em 
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
	if ("--remove" in myopts):#{{{
		pkg = myargs[0]
		if ("--any" in myopts):
			p = package(cp=get_cp_from_str(pkg))
		elif ("--exact" in myopts):
			p = package(cpv=choose_pkg(pkg))
		else:
			help()
		p.del_kw()
		print green("Removing ") + pkg + green(" from ") + keywords
		p.write_pkw()
		sys.exit(1)
	help()
#}}}
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
# End of Execution Options....Did we win?
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
