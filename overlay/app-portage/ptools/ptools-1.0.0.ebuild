# Copyright 2004-2026 redog
# Distributed under the terms of the GNU General Public License v3

EAPI=8

DISTUTILS_USE_PEP517=hatchling
# 3.14 is what the validation host runs (docs/environment.md); 3.11 is the
# floor from pyproject's requires-python.
PYTHON_COMPAT=( python3_{11..14} )
inherit distutils-r1

DESCRIPTION="Gentoo Portage configuration tools (USE flags and keywords)"
HOMEPAGE="https://github.com/redog/ptools"
SRC_URI="https://github.com/redog/ptools/archive/refs/tags/v${PV}.tar.gz -> ${P}.tar.gz"
S="${WORKDIR}/${PN}-${PV}"

LICENSE="GPL-3"
SLOT="0"
KEYWORDS="~amd64"

# Runtime: the real backend imports the portage python API, so match portage's
# interpreter.
RDEPEND="sys-apps/portage[${PYTHON_USEDEP}]"

distutils_enable_tests pytest

python_test() {
	# pyproject bakes a coverage gate into pytest addopts; clear addopts so
	# the ebuild needs no pytest-cov and a coverage threshold cannot fail
	# the package build. The integration tests run too — on a Gentoo build
	# host they exercise the real portage backend read-only and write only
	# under PTOOLS_CONFIG_ROOT sandboxes.
	epytest -o addopts=
}
