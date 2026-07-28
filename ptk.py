#!/usr/bin/env python

#__name__ = "ptools" # that caused problems, hehe... lets learn from this
__description__ = "ptools library"
__IANAP__ = "I am not a programmer"
__WTFIWT__A__ = "What the fuck is with the __'s anyway?"
__version__ = "0.0.3"

import sys, os, string, shlex, types
import portage_util
from output import bold, red, green, darkgreen, turquoise, nocolor, blue, yellow
from portage import isvalidatom, config, db, settings, pkgsplit, catpkgsplit, get_operator, pkgcmp, catsplit

# constants
root="/"
user_config_path		= "/etc/portage"
user_profile_dir		= settings.user_profile_dir
keywords				= user_config_path+"/package.keywords"
use						= user_config_path+"/package.use"
mask					= user_config_path+"/package.mask"
unmask					= user_config_path+"/package.unmask"
modules_file_path		= user_config_path+"/modules"
custom_profile_path		= user_config_path+"/profile"
user_virtuals_file		= user_config_path+"/virtuals"
ebuild_sh_env_file		= user_config_path+"/bashrc"
custom_mirrors_file		= user_config_path+"/mirrors"
#porttree: packages available to install?
porttree = db[root]["porttree"]
portdb = porttree.dbapi
#vartree: packages already installed?
vartree = db[root]["vartree"]
vardb = vartree.dbapi
#virtuals: psudo things?
virtuals = db[root]["virtuals"]

called = str(os.path.split(sys.argv[0])[1])
lsagv = len(sys.argv)
x = 1

class package:#{{{
	"""
	An object to represent a package avaliable in portage
	"""
	def __init__(self, cp='', cpv=''):#{{{
		self.settings = config(clone=settings)
		arch = self.settings['ARCH']
		testing = "~"+arch
		keymask = "-"+arch
		allmask = "-*"
		self.pkeywordsdict = self.settings.pkeywordsdict
		self.pusedict = self.settings.pusedict
		self.uses = portage_util.unique_array(self.settings["USE"].split())
		if cpv:
			self.set_cpv(cpv, tree="port")
		if cp:
			self.set_cp(cp)
#}}}
	def set_cp(self, cp):#{{{
		"""
		Semantics:	Sets the category and package names.
		Arguements:	CP or P(interactive if P is ambigious)
		"""
		self.in_tree = all_packages(cp)
		if not self.in_tree:
			raise Exception
		self.in_system = all_installed_packages(cp)
		self.cp = get_cp_from_str(self.in_tree[0])
		self.packagename = get_p_from_str(self.cp)
		self.category = catsplit(self.in_tree[0])[0]
		self.settings.setcpv(self.cp)
		self.set_use_key()
#}}}
	def set_cpv(self, cpv, tree):#{{{
		"""
		Semantics:	Sets the category, package names and version
		Arguements:	CPV
		"""
		self.set_cp(get_cp_from_str(cpv))
		self.version = get_v_from_str(cpv)
		self.cpv = self.cp+"-"+self.version
		self.settings.setcpv(self.cpv)
		self.pusekey = self.settings.pusekey

		if tree == "port":
			self.iuses = portage_util.unique_array(portdb.aux_get(cpv,['IUSE'])[0].split())
			self.rdepend = str(portdb.aux_get(cpv,['RDEPEND'])[0]).split()
			self.depend = str(portdb.aux_get(cpv,['DEPEND'])[0]).split()
			self.pkeywords = portdb.aux_get(cpv,['KEYWORDS'])[0].split()
			self.path = portdb.findname(cpv)
			self.slot = porttree.getslot(cpv)
			self.set_use_key()
		if tree == "var":
			self.iuses = portage_util.unique_array(vardb.aux_get(cpv,['IUSE'])[0].split())
			self.used = portage_util.unique_array(vardb.aux_get(cpv,['USE'])[0].split())
			self.rdepend = str(vardb.aux_get(cpv,['RDEPEND'])[0]).split()
			self.depend = str(vardb.aux_get(cpv,['DEPEND'])[0]).split()
			self.pkeywords = vardb.aux_get(cpv,['KEYWORDS'])[0].split()
			self.path = vardb.findname(cpv)
			self.slot = vartree.getslot(cpv)
			self.set_use_key()
#}}}
	def set_use_key(self):#{{{
		"""
		Set the key to =cat-egory/package-name-version
		or cate-gory/package-name if not an exact version
		"""
		# I got tired of seeing it suggested so I use this to do it.
		if hasattr(self, "cpv"):
			self.settings.pusekey = "="+self.cpv
			self.pusekey = "="+self.cpv
		elif hasattr(self, "cp"):
			self.settings.pusekey = self.cp
			self.pusekey = self.cp
#}}}
	def write_dict(self, mydict, file):#{{{
		"""
		write a dict to file 
		{key => {depkey => value}}
		"""
		try:
			fp=open(file, "w")
		except IOError:
			ioerror(file, "w")
			return 0
		for key in mydict.keys():
			for x in mydict[key]:
				fp.write(x+" ")
				for y in mydict[key][x]:
					fp.write(y+" ")
				fp.write("\n")
		fp.close()
		return 1
#}}}
	def write_pkw(self):#{{{
		self.write_dict(self.pkeywordsdict, keywords)
#		print green("Updated ") + keywords
#}}}
	def write_pku(self):#{{{
		self.write_dict(self.pusedict, use)
#		print green("Updated ") + use
#}}}
	def add_kw(self, kw):#{{{
		"""
		Semantics:	Add kw to a pkeywords dict
		Arguements:	keyword
		"""
		if not self.pkeywordsdict.has_key(self.cp):
			self.pkeywordsdict.update({self.cp:{}})
			if not self.pkeywordsdict[self.cp].has_key(self.pusekey):
				self.pkeywordsdict[self.cp][self.pusekey] = [kw]
			else:
				self.pkeywordsdict[self.cp].update({self.pusekey:[kw]})
		elif not self.pkeywordsdict[self.cp].has_key(self.pusekey):
				self.pkeywordsdict[self.cp][self.pusekey] = [kw]
		else:
			self.pkeywordsdict[self.cp].update({self.pusekey:[kw]})
#}}}
	def add_use(self, use):#{{{
		"""
		Semantics: Add use flags to a pusedict
		Arguements: a use flag
		"""
		if not self.pusedict.has_key(self.cp):
				self.pusedict.update({self.cp:{}})
				if not self.pusedict[self.cp].has_key(self.pusekey):
					self.pusedict[self.cp][self.pusekey] = [use]
				else:
					self.pusedict[self.cp][self.pusekey].append(use)
		elif not self.pusedict[self.cp].has_key(self.pusekey):
				self.pusedict[self.cp][self.pusekey] = [use]
		else:
			self.pusedict[self.cp][self.pusekey].append(use)
#}}}
	def del_use(self, myuse):#{{{
		"""
		Semantics: Remove a use flags from a pusedict
		Arguements: a use flag
		"""
		try:
			if self.pusedict.has_key(self.cp):
				self.pusedict[self.cp][self.pusekey].remove(myuse)
			if not self.pusedict[self.cp].has_key(self.pusekey):
				del self.pusedict[self.cp][self.pusekey]
			if not self.pusedict.has_key(self.cp):
				del self.pusedict[self.cp]
		except ValueError:
			print myuse
			print red(myuse + " cannot be removed because it is not set" )
		except KeyError, e:
			print red("No matching package listed in ") + use
			sys.exit(1)
#}}}
	def del_kw(self):#{{{
		"""
		Semantics: Remove a package keyword entry from pkeywordsdict
		Arguements: a use flag
		"""
		try:
			if self.pkeywordsdict.has_key(self.cp):
				del self.pkeywordsdict[self.cp][self.pusekey]
			if not self.pkeywordsdict.has_key(self.cp):
				del self.pkeywordsdict[self.cp]
		except ValueError:
			print mykw
			print red(mykw + " cannot be removed because it is not set" )
		except KeyError, e:
			print red("No matching package listed in ") + keywords
			sys.exit(1)
#}}}
	def usediff(self):#{{{
		"""
		Semantics: Contrast use, iuse, usemask
		Returns: List of use flags enabled, disabled, and masked
		"""
		nuse=[]
		for y in self.iuses:
			if y in self.settings.usemask:
				nuse.append(blue("-("+y+")"))
			elif y in self.uses:
				nuse.append(red("+"+y))
			else:
				nuse.append(blue("-"+y))
		return nuse
#}}}
#}}}
class installed_package(package):#{{{
	'''
	An object to represent a package installed by portage
	Seems to work...so far
	'''
	def __init__(self, cp='', cpv=''):#{{{
		"""
		use cp or cpv but not both
		cp is more interactive set cpv for exact matches
		"""
		package.__init__(self)
		if cpv:
			self.cpv = cpv
			self.set_cpv(self.cpv, tree="var")
		elif cp:
			self.cp = cp
			self.set_cp(latest_installed_cpv(get_cp_from_str(self.cp)))
		#}}}
#}}}
def version(ver, desc, support):#{{{
	"""
	Semantics:	Prints tool description, version, and contact information.
	Arguments:	Tool version, description, and maintainers email address.
	Returns:	None
	"""
	print darkgreen(">>> Portage tool to ")+darkgreen(desc)
	print darkgreen(">>> ")+blue("Thank You for useing ")+blue(called)+" "+ver
	print darkgreen(">>> ")+blue("Email questions, complaints, or bugs to:")
	print darkgreen(">>> ")+turquoise(support)
#}}}
def ioerror(file, mode):#{{{
	"""
	Semantics:	Prints File permission error
	Arguments:	Filename, Permission mode
	Returns:	None
	"""
	this = {
	'r': lambda x: "read",
	'w': lambda x: "write",
	'r+': lambda x: "read and write",
	'a': lambda x: "read and write"
	}[mode](x)
	print red("!!! Error: ")+bold(file+" must exist and have "+this+" permission to run the command")
#}}}
def fix_value(error, tree, is_masked):#{{{
	"""
	Semantics:	empowers a user to fix an xmatch error
	Arguements:	An xmatch ValueError
	Returns:	list of avaliable cpv's in portage tree
	"""
	if 'port' in tree and not is_masked:
		return portdb.xmatch("match-all", error[0][int(choose(error[0]))])
	elif 'port' in tree and is_masked:
		return portdb.xmatch("match-visible", error[0][int(choose(error[0]))])
	if 'var' in tree:
		return vardb.match(error[0][int(choose(error[0]))])
#}}}
def ask(prompt, retries=4):#{{{
	"""
	Semantics:	Prompts for yes or no, complains and quits if neither given after retry limit.
	Arguements:	Question prompt, Number of retries, Complaint
	Returns:	True or False
	"""
	complaint='Yes or no, please!'
	while True:
		ok = raw_input(prompt)
		if ok in ('y', 'Y', 'ye',  'yes', 'Yes', 'YES' ): return True
		if ok in ('n', 'N', 'no', 'nop', 'nope', 'No', 'NO'): return False
		retries = retries - 1
		if retries < 0: raise IOError, red('luser error')
		print complaint
#}}}
def choose(list):#{{{
	"""
	Semantics:	Prompts user to select from a list
	Arguements:	A list
	Returns:	Returns the string selected
	"""
	x = 0
	lrange = range(len(list))
	for each in list:
		print turquoise("["+str(x)+"] ") + each
		x = x + 1
	while True:
		choice = raw_input("Please select:")
		if int(choice) in lrange:
			answer = choice
			break
		else:
			print red("That was not a valid choice!")
	return answer
#}}}
def cpvcmp(cpvlist):#{{{
	"""
	Semantics:	Find the largest cpv in a list of cpvs(No valid/invalid discriminate)
	Arguements:	list of CPV values
	Returns:	CPV string
	"""
	largest=""
	for cpv in cpvlist:
		if not largest and cpv:
			largest = cpv
		if pkgcmp(catpkgsplit(cpv)[1:], catpkgsplit(largest)[1:]) > 0:
			largest = cpv
	return largest
#}}}
def path_to_cpv(mycpv, tree='port'):#{{{
	"""
	Semantics:	Find a cpv's ebuild in a tree
	Arguements:	CPV, db tree 
	Returns:	Location of an ebuild
	"""
	if 'port' in tree:
		return portdb.findname(mycpv)
	if 'var' in tree:
		return vardb.findname(mycpv)
#}}}
def all_packages(mykey, name='none'):#{{{
	"""
	Semantics:	Search for cpv's in portage tree prompt user if key not a unique cp
	Arguements:	A CPV, CP, PV, P or dep_atom
	Returns:	list of avaliable cpv's in portage tree
	"""
		# try to use xmatch to give us all masked and unmasked packages for a key
	try:
		return portdb.xmatch("match-all", mykey)
	except ValueError, e:
		# fixes ValueError on sudo, =sudo; will call choose() for user input
		return fix_value(e, 'port', None)
	except KeyError, e:
		# fixes KeyError on qingy-0.6.0, app-portage/ptools-0.0.1 ; needs >= = <= key so lets take their suggestion
		myop = get_operator(mykey)
		try:
			fixkey = myop+mykey
		except:
			if myop == None:
				myop = "="
				fixkey = myop+mykey
			else:
				raise FunkyError, "all_packages(): Something really funky just happened. Please report this."
		return portdb.xmatch("match-all", fixkey)
	except:
		# if not fixed some luser asked for garbage
		return []
#}}}
def all_installed_packages(mykey, name='none'):#{{{
	"""
	Semantics:	Search for cpv's in vardb
	Arguements:	A CPV, CP, PV, P or dep_atom
	Returns:	list of installed cpv's in a portage db 
	"""
	try:
		return vardb.match(mykey)
	except ValueError, e:
		return fix_value(e, 'var', None)
	except:
		myop = get_operator(mykey)
		try:
			return vardb.match(myop+mykey)
		except:
			if myop == None:
				return vardb.match("="+mykey)
			else:
				raise FunkyError, "all_installed_packages(): Something really funky just happened. Please report this."

#}}}
def latest_cpv(mykey, tree='port', is_masked='masked'):#{{{
	"""
	Semantics:	Find the latest version of a package
	Arguements:	CP, P, db tree, is_masked=None if unmasking
	Returns:	cpv
	"""
	if 'port' in tree:
		if is_masked == None:
			# not sure how well this works with package.mask package.unmask 
			return cpvcmp(all_packages(mykey))
		else:
			try:
				return cpvcmp(portdb.xmatch("match-visible", mykey))
			except ValueError, e:
				return cpvcmp(fix_value(e, tree, is_masked))
			except KeyError:
				myop = get_operator(mykey)
				try:
					fixkey = myop+mykey
				except:
					if myop == None:
						myop = "="
						fixkey = myop+mykey
					else:
						raise FunkyError, "all_packages(): Something really funky just happened. Please report this."
				return cpvcmp(portdb.xmatch("match-visible", fixkey))
			except:
				# if not fixed some luser asked for garbage
				return ""
	if 'var' in tree:
		try:
			return cpvcmp(all_installed_packages(mykey))
		except:
			# if not fixed some luser asked for garbage
			return ""
#}}}
def latest_installed_cpv(mykey):#{{{
	"""
	Semantics:	Find the latest version of an installed package
	Arguements:	CP, P, db tree
	Returns:	cpv
	"""
	return latest_cpv(mykey, 'var')#}}}
def get_cp_from_str(mykey):#{{{
	"""
	Semantics:	Search for a CP in tree by string
	Arguements:	A CPV, CP, PV, P, or dep_atom
	Returns:	CP
	"""
	x = []
	x = all_packages(mykey)
	if ( len(x) != 0 ):
		return pkgsplit(x[0])[0]
	else:
		x = all_installed_packages(mykey)
	if ( len(x) != 0 ):
		return pkgsplit(x[0])[0]
	else:
		sys.stderr.write(red("An ebuild for "+mykey+" cannot be found on this system\n"))
		sys.exit(1)
#}}}
def get_p_from_str(mykey):#{{{
	"""
	Semantics:	Search for a P in tree by string
	Arguements:	A CPV, CP, PV, P, or dep_atom
	Returns:	P
	"""
	x = []
	x = all_packages(mykey, 'get_p_from_str')
	if ( len(x) != 0 ):
		return catpkgsplit(x[0])[1]
	else:
		x = all_installed_packages(mykey)
	if ( len(x) != 0 ):
		return catpkgsplit(x[0])[1]
	else:
		sys.stderr.write(red("An ebuild for "+mykey+" cannot be found on this system\n"))
#}}}
def get_v_from_str(mykey):#{{{
	"""
	Semantics:	
	Arguements:	A CPV, CP, PV, P or dep_atom
	Returns:	V(will return the version for the newest unmasked version if no version given)
	"""
	x = []
	x = all_packages(mykey)
	if ( len(x) != 0):
		ver = pkgsplit(x[0])[1]
		rev = pkgsplit(x[0])[2]
		if not rev == "r0":
			return str(ver+"-"+rev)
		else:
			return str(ver)
	else:
		x = all_installed_packages(mykey)
	if ( len(x) !=0 ):
		ver = pkgsplit(x[0])[1]
		rev = pkgsplit(x[0])[2]
		if not rev == "r0":
			return str(ver+"-"+rev)
		else:
			return str(ver)
	else:
		sys.stderr.write(red("An ebuild for "+mykey+" cannot be found on this system\n"))
#}}}
def choose_pkg(mypkg):#{{{
	"""
	Semantics:	Prompts user to select from a list of avaliable packages in a portage db
	Arguements:	A CPV, CP, PV, P, or dep_atom 
	Returns:	Returns the selected cpv or False if there is no package
	"""
	retrys = 4
	x = 0
	fp = all_packages(mypkg, 'choose_pkg')
	fp_range = [str(i) for i in range(len(fp))]
	if len(fp) > 1:
		for cpv in fp:
			if x < len(fp):
				print turquoise("["+str(x)+"] ") + cpv
			x = x + 1
		while True:
			choice = raw_input("Please select a package to add by entering its corresponding number:")
			if choice in fp_range:
				answer = choice
				break
			else:
				print red("That was not a valid package!")
			retrys = retrys - 1
			if retrys < 0: raise IOError, red('luser error')
		return fp[int(answer)] #....must...get...sleep|MORE COFFEE
	else:
		if len(fp) == 1:
			return fp[0]
		else:
			return False
#}}}

def test_world():
	# still broken... need to account for slots... and um fix some of the logic.... should be useing package() and installed_package()
	from portage import grabfile, WORLD_FILE
	worldlist = grabfile(WORLD_FILE)
	for x in worldlist:
		installed = all_installed_packages(x)
		avaliable = latest_cpv(x, is_masked="masked")
		newest_in_tree = latest_cpv(x, is_masked=None)
		if installed and avaliable and cpvcmp(installed) == avaliable:
			print green(avaliable) + " is the highest "+yellow("unmasked") +" version avaliable in the tree and is currently installed"
		elif installed and newest_in_tree and newest_in_tree == cpvcmp(installed):
			print green(newest_in_tree) + " is the highest version avaliable in the tree and is currently installed"
		elif avaliable and newest_in_tree and newest_in_tree == avaliable:
			print yellow(avaliable) + " is avaliable for you to upgrade and it is the higest version in the tree"
		elif installed:
			for each in installed:
				if len(all_packages(each)) == 0 and latest_cpv(get_cp_from_str(each)):
					if cpvcmp([each , latest_cpv(get_cp_from_str(each))]) != each:
						print  red("No ebuild exist in portage for the installed package: ") + yellow(each) + " consider upgrading to the latest unmasked version " + green(latest_cpv(get_cp_from_str(each)))
					else:
						print red("No ebuild exist in portage for the installed package: ") + yellow(each) + " consider downgrading to " + green(latest_cpv(get_cp_from_str(each)))
				else:
					print bold(red("There are no newer, older, masked, unmasked, or exact matches for ")) + each


if __name__ == "__main__":
	test_world()
