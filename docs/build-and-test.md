# Building, testing & packaging ptools on Gentoo

A straight guide for anyone on a Gentoo box who wants to build, test, and
install ptools by hand — no CI, no containers. ptools is a standard Python 3
package (hatchling, `src/` layout) with a pytest suite, exposing two commands:
`puse` and `pkw`. (`ptools` is the distribution name — it is not a command.)

---

## 0. Layout at a glance

```
pyproject.toml          # hatchling build backend, deps, tool config
src/ptools/             # the package
  puse.py pkw.py        # the two console entry points (first-class CLIs)
  cli_common.py         # shared argv handling, output, exit-code mapping
  domain.py services.py config_store.py errors.py
  portage_adapter.py    # backend Protocol + MockPortageBackend + factory
  portage_real.py       # the real portage integration (imports `portage`)
scripts/                # discover_environment.py (Milestone D)
tests/unit/             # pytest suite (uses the mock backend — no Gentoo needed)
tests/integration/      # real-portage tests, marked `integration`
```

Entry points (from `pyproject.toml`):

| Command  | Target             |
|----------|--------------------|
| `puse`   | `ptools.puse:main` |
| `pkw`    | `ptools.pkw:main`  |

Both CLIs call the service layer directly; neither shells out to the other, and
neither escalates privilege. Writing to a real `/etc/portage` means running them
under `sudo`/as root yourself; otherwise they exit 5.

Requires **Python ≥ 3.11**. Runtime deps: none declared — the real portage
backend imports `portage`, which is already present on any Gentoo box.

---

## 1. Get a dev environment

The dev tools (pytest, coverage, mypy, ruff, build) aren't declared as a `[dev]`
extra, so install them yourself. Two ways:

**A. venv + pip (isolated, no root):**

```bash
git clone https://github.com/redog/ptools && cd ptools
python -m venv .venv && source .venv/bin/activate
pip install -e .                       # editable install of ptools
pip install pytest pytest-cov mypy ruff build
```

Note: inside a venv, `import portage` won't resolve unless you create it with
`--system-site-packages`. The **unit tests don't need portage** (they use the
mock backend), so a plain venv is fine for build+test. Only the *real* CLI
against live portage needs system python — see §5.

**B. System python via portage (no venv):**

```bash
sudo emerge -n dev-python/pytest dev-python/pytest-cov dev-python/mypy \
                dev-python/build dev-vcs/git
# ruff: sudo emerge -n dev-python/ruff  (or pipx install ruff)
```

This keeps `import portage` working, so both the tests and the real CLIs run.

---

## 2. Build

Standard PEP 517 build — produces an sdist and a wheel in `dist/`:

```bash
python -m build
ls dist/            # ptools-0.1.0.tar.gz  ptools-0.1.0-py3-none-any.whl
```

Or just install it (editable for dev, regular to smoke-test the entry points):

```bash
pip install -e .        # editable
# or
pip install dist/ptools-0.1.0-py3-none-any.whl
```

---

## 3. Test

The pytest config in `pyproject.toml` bakes in coverage with an **85% gate**
(`--cov=ptools --cov-fail-under=85`) and an `integration` marker for tests that
need a real environment.

```bash
pytest                          # full suite + coverage gate (uses mock backend)
pytest -m "not integration"     # skip environment-specific tests
pytest -q tests/unit/test_services.py::TestName   # target one test
pytest --no-cov                 # quick run without the coverage gate
```

`portage_real.py` is excluded from coverage (`[tool.coverage.run] omit`),
because it's the layer that talks to real portage and is exercised by the
integration tests on a Gentoo host, not by unit tests.

Type-check and lint (both configured in `pyproject.toml`; mypy is `strict`):

```bash
mypy src/ptools
ruff check .
```

---

## 4. Run the tools (after install)

```bash
puse app-editors/vim              # read-only: effective USE state
puse app-editors/vim python -gtk  # needs root: writes package.use/ptools
pkw --testing app-editors/vim     # needs root: writes package.accept_keywords/ptools
puse --help ; pkw --help
```

---

## 5. Real portage vs the mock

- **Unit tests** run anywhere — they inject `MockPortageBackend`, so no Gentoo
  required (handy for editing on a non-Gentoo machine).
- **The real CLIs** use `portage_real.py`, which imports `portage`. That needs
  system python (Gentoo), not a bare venv. Without it both commands exit 7.
- **Write safety:** write paths edit your real `/etc/portage` config through
  `config_store.py`; show paths and `--dry-run` never write. Point
  `PTOOLS_CONFIG_ROOT` at a scratch directory to exercise writes without
  touching the live configuration:

  ```bash
  PTOOLS_CONFIG_ROOT=/tmp/sandbox-portage puse app-editors/vim python
  ```

  ptools takes no backups, so on a box you care about either use that override,
  or keep `/etc` under git and `git checkout` to revert.

---

## 6. Package as an ebuild

Because it's a PEP 517 / hatchling project, the ebuild is a clean
`distutils-r1` one — `distutils_enable_tests` wires the suite straight into
`src_test`.

### 6a. Local overlay (one time)

```bash
sudo mkdir -p /var/db/repos/localrepo/{metadata,profiles}
echo localrepo | sudo tee /var/db/repos/localrepo/profiles/repo_name
printf 'masters = gentoo\n' | sudo tee /var/db/repos/localrepo/metadata/layout.conf
sudo mkdir -p /etc/portage/repos.conf
sudo tee /etc/portage/repos.conf/localrepo.conf >/dev/null <<'EOF'
[localrepo]
location = /var/db/repos/localrepo
EOF
```

### 6b. A live (`-9999`) ebuild for iteration

Save as `/var/db/repos/localrepo/app-portage/ptools/ptools-9999.ebuild`:

```bash
# Copyright 1999-2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DISTUTILS_USE_PEP517=hatchling
PYTHON_COMPAT=( python3_{11..13} )
inherit distutils-r1 git-r3

DESCRIPTION="Gentoo Portage configuration tools (USE flags and keywords)"
HOMEPAGE="https://github.com/redog/ptools"
EGIT_REPO_URI="https://github.com/redog/ptools.git"

LICENSE="GPL-2"
SLOT="0"
KEYWORDS=""   # live ebuild: unmask to install (see below)

# Runtime: the real backend imports the portage python API, so match portage's
# interpreter.
RDEPEND="sys-apps/portage[${PYTHON_USEDEP}]"

distutils_enable_tests pytest

python_test() {
	# upstream bakes a --cov-fail-under gate into pyproject; drop it for the
	# ebuild so a coverage threshold can't fail the package build.
	epytest --no-cov
}
```

If `dev-python/pytest-cov` isn't pulled in and `epytest` complains about the
`--cov` addopts, either add `test? ( dev-python/pytest-cov )` to `BDEPEND` or
keep the `--no-cov` override above.

### 6c. Build, test, install, verify

```bash
cd /var/db/repos/localrepo/app-portage/ptools

# run through phases (compiles + runs the test suite in src_test):
sudo ebuild ptools-9999.ebuild clean test install

# merge for real (live ebuild needs unmasking):
# NB: not the file named `ptools` — that one belongs to the tool itself.
echo '=app-portage/ptools-9999 **' | sudo tee /etc/portage/package.accept_keywords/99-local
sudo emerge -av app-portage/ptools

puse --help && pkw --help
equery files app-portage/ptools
sudo emerge -C app-portage/ptools     # clean uninstall
```

### 6d. Tagged-release ebuild

When you tag e.g. `v0.1.0`, swap `git-r3` for a distfile:

```bash
SRC_URI="https://github.com/redog/ptools/archive/refs/tags/v${PV}.tar.gz -> ${P}.tar.gz"
KEYWORDS="~amd64"
S="${WORKDIR}/${PN}-${PV}"
```

then `sudo ebuild ptools-0.1.0.ebuild manifest` and `emerge` as above.

---

## 7. Quick reference

```bash
python -m build                 # sdist + wheel
pytest                          # tests + 85% coverage gate
pytest --no-cov -m "not integration"   # fast, env-agnostic
mypy src/ptools && ruff check . # types + lint
pip install -e .                # editable dev install
```
