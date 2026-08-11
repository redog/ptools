# Building, testing & packaging ptools on Gentoo

A straight guide for anyone on a Gentoo box who wants to check, run, and
install ptools by hand. No CI, no containers, no special host — just Gentoo,
portage, and git. The end goal is an **ebuild** that installs `puse`, `pkw`,
and the `ptk` library.

---

## 0. Read this first

- ptools is **Python 2** source, mid-port to **Python 3** (see `SPEC.md`). It
  uses `print` statements, `has_key`, `raw_input`, `except X, e:` and imports
  the old **`portage_util`** / **`output`** module names, which modern portage
  now exposes as **`portage.util`** / **`portage.output`**.
- So on a current Gentoo (`python` is python3) the code **won't compile or
  import unchanged** — `py_compile` throws `SyntaxError`. That's expected; the
  failures are the porting to-do list, not a broken setup.
- **The tools write to your real `/etc/portage`.** `ptk.py` hardcodes
  `user_config_path = "/etc/portage"` and ignores `PORTAGE_CONFIGROOT`, so the
  write commands (`--change`, `--remove`) edit `package.use` /
  `package.keywords` on the machine you run them on. Read commands (`--show`,
  `--help`) are safe. See §3 for how to test writes without regret.

---

## 1. Prerequisites

You already have what matters on any Gentoo install: portage (provides the
`portage` python module) and a system python. Add git, and optionally linters:

```bash
sudo emerge -n dev-vcs/git
# optional, nice to have for the port work:
sudo emerge -n dev-python/pyflakes   # or: pipx install ruff
```

Grab the source:

```bash
git clone https://github.com/redog/ptools
cd ptools
```

---

## 2. Static checks ("does it build?")

There's no compile step — it's Python — so the first gate is "does it parse?"

```bash
# syntax check under the system python (python3): expect py2 SyntaxErrors today
python -m py_compile ptk.py puse.py pkw.py

# clearer, one file at a time
for f in ptk.py puse.py pkw.py; do
  echo "== $f =="
  python -c "import ast; ast.parse(open('$f').read())" || true
done

# richer linters, if installed
ruff check .
pyflakes *.py
```

Once `py_compile` is clean, the imports are the next layer (only meaningful
after the syntax is py3-clean):

```bash
python -c "import ptk"   # surfaces portage_util/output -> portage.util/portage.output
```

---

## 3. Running & testing the tools

`ptk.py` is the shared library; `puse` and `pkw` are the front-ends. Test the
**read-only** paths first — they don't touch `/etc/portage`:

```bash
python puse.py --help
python puse.py --show app-editors/vim     # prints effective USE state
python pkw.py  --help
python ptk.py                             # runs test_world(): a world-consistency report
```

### Testing the write paths without wrecking /etc/portage

The mutating commands edit real files. Pick one of these before running them:

**a) Back up and restore (simplest):**

```bash
sudo cp -a /etc/portage/package.use /etc/portage/package.use.bak 2>/dev/null || true

python puse.py --change --any app-editors/vim -minimal   # add a flag
cat /etc/portage/package.use                             # inspect
python puse.py --remove --any app-editors/vim minimal    # undo

# restore if anything looks off:
sudo mv /etc/portage/package.use.bak /etc/portage/package.use
```

**b) Version /etc under git** (many Gentoo admins already do this) — run the
tool, `git diff /etc/portage`, and `git checkout` to revert.

**c) Full isolation without a container** — run inside a stage3 chroot you
control, so a bad write only hits the chroot's `/etc/portage`. More setup, but
total safety if you're testing destructive paths repeatedly.

---

## 4. Packaging into an ebuild

Target install layout:

| File     | Destination        | Role           |
|----------|--------------------|----------------|
| `ptk.py` | `/usr/lib/ptools/` | shared library |
| `puse.py`| `/usr/bin/puse`    | USE-flag CLI   |
| `pkw.py` | `/usr/bin/pkw`     | keyword CLI    |

The front-ends already prepend `/usr/lib/ptools` to `sys.path`, so this matches
the source. (Post-port, the cleaner path is to ship `ptk` as a real importable
module in site-packages and drop the `sys.path` hack.)

### 4a. Make a local overlay (one time)

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

### 4b. A live (`-9999`) ebuild for iteration

Pulls straight from git — no release tarball or Manifest needed. Save as
`/var/db/repos/localrepo/app-portage/ptools/ptools-9999.ebuild`:

```bash
# Copyright 1999-2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

PYTHON_COMPAT=( python3_{11..13} )
inherit python-single-r1 git-r3

DESCRIPTION="Tools for managing per-package portage USE flags and keywords"
HOMEPAGE="https://github.com/redog/ptools"
EGIT_REPO_URI="https://github.com/redog/ptools.git"

LICENSE="GPL-2"
SLOT="0"
KEYWORDS=""   # live ebuild: no keywords, must be unmasked to install

REQUIRED_USE="${PYTHON_REQUIRED_USE}"

# The scripts import portage's python API, so our interpreter must match the
# one portage itself is built for.
RDEPEND="
	${PYTHON_DEPS}
	sys-apps/portage[${PYTHON_SINGLE_USEDEP}]
"

src_install() {
	insinto /usr/lib/ptools
	doins ptk.py

	newbin puse.py puse
	newbin pkw.py pkw
	python_fix_shebang "${ED}"/usr/bin/puse "${ED}"/usr/bin/pkw
}
```

### 4c. Build, install, verify

```bash
cd /var/db/repos/localrepo/app-portage/ptools

# step through phases for fast feedback on src_install (no system change yet):
sudo ebuild ptools-9999.ebuild clean unpack compile install
# inspect the staged tree under the printed ${ED}/ (usr/bin, usr/lib/ptools)

# unmask the live ebuild, then merge it for real:
echo '=app-portage/ptools-9999 **' | sudo tee /etc/portage/package.accept_keywords/ptools
sudo emerge -av app-portage/ptools

# verify:
puse --help
equery files app-portage/ptools     # or: qlist ptools
sudo emerge -C app-portage/ptools   # clean uninstall when done
```

### 4d. Tagged-release ebuild (once you cut a version)

When you tag e.g. `v0.0.3`, drop `git-r3` for a distfile:

```bash
SRC_URI="https://github.com/redog/ptools/archive/refs/tags/v${PV}.tar.gz -> ${P}.tar.gz"
KEYWORDS="~amd64"
S="${WORKDIR}/${PN}-${PV}"   # github tarballs unpack to <repo>-<version>/
```

then `sudo ebuild ptools-0.0.3.ebuild manifest` to generate the Manifest and
`emerge` as above.

---

## 5. One-liners

```bash
# quick "does the whole tree parse under py3?" gate
python -m py_compile ptk.py puse.py pkw.py && echo OK

# list the py2-isms to fix
grep -nE '\bprint [^(]|\.has_key\(|raw_input\(|except [A-Za-z].*, [a-z]+:|raise [A-Za-z]+,' *.py

# the portage import names that need renaming
grep -nE 'portage_util|from output import' *.py
```

## 6. Suggested order of attack

1. Make `py_compile` pass (py2 → py3 syntax).
2. Fix imports: `portage_util` → `portage.util`, `output` → `portage.output`;
   audit the `from portage import ...` names against the current API.
3. Get `puse --show <pkg>` working read-only.
4. Validate the write paths (back up `/etc/portage` first, per §3).
5. Install via the `-9999` ebuild; iterate with `ebuild … install`.
6. Tag a release and add the versioned ebuild.
