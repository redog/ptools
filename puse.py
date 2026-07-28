#!/usr/bin/env python
import sys
sys.path = ["/usr/lib/ptools"]+["/usr/lib/portage/pym"]+sys.path
from ptk import *

#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=

######	  #	   #   ######   ######
#	  #   #	   #  #         #
#	  #   #	   #  #         #
######	  #	   #   ######   ###
#		  #	   #         #  #
#		  #	   #         #  #
#		   ####    ######   ######
__me__ = "puse"
__version__ = "0.0.1"
__whatido__ = "alter package use flags"
__support__ = "bugzilla@opelousas.org"
__disclaimer__ = "I suck & you can't sue me. But feel free to try, so you can suck to"
__faq__ = "Don't ask why. Just show me a better way."
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
# Begin Options
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
options=[#{{{
"--help",
"--any",
"--change",
"--exact",
"--not",
"--remove",
"--show",
"--version",
"--verbose"
]

shortopts={
"a":"--any",
"c":"--change",
"e":"--exact",
"n":"--not",
"r":"--remove",
"s":"--show",
"h":"--help",
"V":"--version",
"v":"--verbose"
}

tcl=sys.argv[1:]
cmdline=[]
myopts=[]
myargs=[]

#}}}
# short options#{{{
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
def help():#{{{
	print
	print
	print bold("Usage:")
	print "   "+turquoise(__me__)+" [ "+green("option")+" ] [ "+green("package")+" ] [ "+ yellow("use flags")+" ]"
	print
	print bold("Options:")
	print turquoise("--any\n-a ")+bold("Flags apply to any version of the package\n")
	print turquoise("--change\n-c ")+bold("Change use flags for a package\n")
	print turquoise("--exact\n-e ")+bold("Flags apply to a single version of the package\n")
	print turquoise("--show\n-s ")+bold("Show the use flags for a package\n")
	print turquoise("--help\n-h ")+bold("Show this and quit\n")
	sys.exit(1)
#}}}
def show(mykey):#{{{
	#TODO: make it show all avaliable & all installed pkg's with a verbose option or somehow without 
	# requiring the arg to be the cpv
	# currently doesn't show installed packages that are not the latest version
	try:
		mykey = pkgsplit(all_packages(mykey)[0])[0]
	except IndexError, e:
		print
		print red('There is no package named ') + mykey

	installed = latest_installed_cpv(mykey)
	if installed:
		installedp = installed_package(cpv=installed)

	avaliable = latest_cpv(mykey, is_masked="masked")
	if avaliable:
		avaliablep = package(cpv=avaliable)

	newest_in_tree = latest_cpv(mykey, is_masked=None)
	if newest_in_tree:
		newestp = package(cpv=newest_in_tree)

	# if the package itself is the latest and is installed.
	if installed and avaliable and installed == newest_in_tree:
		print "["+yellow("Installed")+"] "+green(installed)+": ",
		for each in installedp.usediff():
			print each,
	# there is an installed version and an avaliable version
	elif avaliable and installed and not avaliable == installed:
		print "["+yellow("Installed")+"] "+green(installed)+": ",
		for each in installedp.usediff():
			print each,
		print ""
		print "["+green("Unmasked")+"] "+green(avaliable)+": ",
		for each in avaliablep.usediff():
			print each,
		print ""
	# if the package itself is ready to be installed
	elif avaliable and newest_in_tree and not installed:
		print "["+green("Unmasked")+"] "+green(avaliable)+": ",
		for each in avaliablep.usediff():
			print each,
	# if there is no unmasked or keyworded package but there is an ebuild tell me anyway
	elif not avaliable and newest_in_tree:
		print "["+red("Masked")+"] "+green(newest_in_tree)+": ",
		for each in newestp.usediff():
			print each,
	else:
		sys.exit(1)
#}}}
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
# Begin Execution: AKA: say_your_prayers()
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
#TODO: add output statements to indicate success'
if __name__ == '__main__':
	if ( len(myopts) < 1 or len(myargs) < 1):
		help()

	if ( "--help" in myopts ):
		help()

	if ("--remove" in myopts ):
		pkg = myargs[0]
		useflags = myargs[1:]
		if ("--exact" in myopts):
			p = package(cpv=choose_pkg(pkg))
		elif ("--any" in myopts):
			p = package(cp=get_cp_from_str(pkg))
		else:
			help()
		if ("--not" in myopts ):
			for flag in useflags:
				p.del_use("-"+flag)
			p.write_pku()
		for flag in useflags:
			p.del_use(flag)
		p.write_pku()
		sys.exit(1)

	if ("--show" in myopts ):
		for arg in myargs:
			show(arg)
		sys.exit(1)

	if ("--change" in myopts):
		pkg = myargs[0]
		useflags = myargs[1:]
		if ("--any" in myopts ):
			p = package(cp=get_cp_from_str(pkg))
			if ("--not" in myopts ):
				for flag in useflags:
					p.add_use("-"+flag)
				p.write_pku()
			for flag in useflags:
				p.add_use(flag)
			p.write_pku()
			sys.exit(1)
		elif ("--exact" in myopts ):
			p = package(cpv=choose_pkg(pkg))
			if ("--not" in myopts ):
				for flag in useflags:
					p.add_use("-"+flag)
				p.write_pku()
			for flag in useflags:
				p.add_use(flag)
			p.write_pku()
			sys.exit(1)
		else:
			help()

	if ( "--version" in myopts ):
		version(__version__, __whatido__, __support__)
		sys.exit(1)
	help()
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
# End of Execution Options....Did we win?
#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=
