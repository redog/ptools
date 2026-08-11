# ptools — manual build & test cheat sheet

How to check, run, and package ptools by hand, without waiting on the gumbo CI
runner. Ultimate target: an **ebuild** that installs `puse`, `pkw`, and the
`ptk` library onto a real Gentoo system.

---

## 0. Reality check (read this first)

- ptools is **Python 2** source, mid-port to **Python 3** (see `SPEC.md`).
  The scripts use `print` statements, `has_key`, `raw_input`, `except X, e:`
  and import **`portage_util`** / **`output`** — the old top-level portage
  module names. Modern portage exposes these as **`portage.util`** and
  **`portage.output`**.
- Consequence: on a current Gentoo (`python` == python3), the code **won't
  compile or import as-is**. `py_compile` will throw `SyntaxError`. That's
  expected and is itself the to-do list for the port — not a broken setup.
- These tools **write to `/etc/portage`** (hardcoded in `ptk.py`:
  `user_config_path = "/etc/portage"`). They do **not** honor
  `PORTAGE_CONFIGROOT` for writes. So **never smoke-test the write paths on a
  box whose `/etc/portage` you care about.** Use the disposable `gentoo-dev`
  container (below) — same environment CI uses, and nothing to lose.

---

## 1. Where to run it

The code imports `portage`, so it only works on a machine with portage's
Python modules — i.e. Gentoo. Two options:

**A. The disposable `gentoo-dev` container (recommended).** Same image the CI
runner uses; clobbering its `/etc/portage` is harmless.

```bash
# on gumbo, with the devenv up (start-env.sh)
podman exec -it -u eric gentoo-dev bash --login
# then, inside:
git clone https://github.com/redog/ptools && cd ptools
```

Or one-shot without the full tmux env:

```bash
podman run --rm -it -v "$PWD:/src:z" -w /src localhost/devenv-gentoo bash
```

**B. A real Gentoo box** — fine for read-only checks and ebuild work; just
respect the `/etc/portage` write warning above.

---

## 2. Static checks (run these now — they map the port work)

No build step; it's Python. "Does it parse?" is the first gate.

```bash
# syntax check under the system python (python3): expect py2 SyntaxErrors today
python -m py_compile ptk.py puse.py pkw.py

# same thing, more readable failure, one file at a time
for f in ptk.py puse.py pkw.py; do echo "== $f =="; python -c "import ast,sys; ast.parse(open('$f').read())" || true; done

# if you have them, richer linters (pipx install ruff / pyflakes)
ruff check .
pyflakes *.py
```

What you'll see today: `print ...` statements, `except IOError, e:` etc. —
each is a concrete py3 fix. Green `py_compile` == the port's syntax layer is
done. (Note: the CI workflow in `.github/workflows/ci.yml` runs exactly this
`py_compile` step, so it stays red until the port lands — by design.)

Import-level check (only meaningful **after** syntax is py3-clean):

```bash
# will surface the portage_util/output -> portage.util/portage.output renames
python -c "import ptk"
```

---

## 3. Smoke-testing the CLIs (post-port, in the container)

`ptk.py` is the shared library; `puse` and `pkw` are the front-ends. Once the
code runs, exercise the **read-only** paths first — `--show` and `--help` don't
touch `/etc/portage`:

```bash
python puse.py --help
python puse.py --show app-editors/vim      # read-only: prints USE state
python pkw.py  --help
```

Write paths (**mutate `/etc/portage/package.use` — container only**):

```bash
python puse.py --change --any app-editors/vim -minimal   # add a flag
python puse.py --remove --any app-editors/vim minimal    # remove it
cat /etc/portage/package.use                             # inspect the result
```

`ptk.py` run directly executes `test_world()` (a world-consistency report):

```bash
python ptk.py
```

Tip: snapshot config before a write test so you can diff/restore:

```bash
cp -a /etc/portage/package.use{,.bak} 2>/dev/null || true
```

---

## 4. Packaging → the ebuild

End goal: `emerge app-portage/ptools` installs:

| File     | Destination           | Role            |
|----------|-----------------------|-----------------|
| `ptk.py` | `/usr/lib/ptools/`    | shared library  |
| `puse.py`| `/usr/bin/puse`       | USE-flag CLI    |
| `pkw.py` | `/usr/bin/pkw`        | keyword CLI     |

(The front-ends already prepend `/usr/lib/ptools` to `sys.path`, so this layout
matches the source. Post-port, the cleaner move is to install `ptk` as a real
importable module into site-packages and drop the `sys.path` hack — noted for
later.)

### 4a. Local overlay (one-time setup, inside the container)

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

### 4b. A live (`-9999`) ebuild for dev iteration

No release tarball or Manifest needed — pulls straight from git, always HEAD.
Save as `/var/db/repos/localrepo/app-portage/ptools/ptools-9999.ebuild`:

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

# The scripts import the portage python API, so our interpreter must match the
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

### 4c. Build / test the ebuild

```bash
cd /var/db/repos/localrepo/app-portage/ptools

# step through phases without a full merge (fast feedback on src_install):
sudo ebuild ptools-9999.ebuild clean unpack compile install

# inspect the staged install tree before it lands:
#   look under the printed ${ED}/ path for usr/bin/{puse,pkw}, usr/lib/ptools/

# full install to the system (needs the -9999 unmasked):
echo '=app-portage/ptools-9999 **' | sudo tee /etc/portage/package.accept_keywords/ptools
sudo emerge -av app-portage/ptools

# then verify it's really installed and runnable:
puse --help
qlist ptools     # or: equery files app-portage/ptools
sudo emerge -C app-portage/ptools   # clean uninstall when done
```

### 4d. Tagged-release ebuild (once a version is cut)

When you tag e.g. `v0.0.3` on GitHub, the release form drops `git-r3` and uses a
distfile instead:

```bash
SRC_URI="https://github.com/redog/ptools/archive/refs/tags/v${PV}.tar.gz -> ${P}.tar.gz"
KEYWORDS="~amd64"
# S="${WORKDIR}/${PN}-${PV}"   # github tarballs unpack to <repo>-<version>/
```

then `sudo ebuild ptools-0.0.3.ebuild manifest` to generate the Manifest, and
`emerge` as above.

---

## 5. One-liners

```bash
# quick "does the whole tree parse under py3?" gate (mirrors CI)
python -m py_compile ptk.py puse.py pkw.py && echo OK

# find every py2-ism to fix (rough but useful)
grep -nE '\bprint [^(]|\.has_key\(|raw_input\(|except [A-Za-z].*, [a-z]+:|raise [A-Za-z]+,' *.py

# confirm the portage import names that need renaming
grep -nE 'portage_util|from output import' *.py
```

---

## 6. Suggested order of attack

1. Make `py_compile` pass (py2 → py3 syntax). CI goes green here.
2. Fix imports: `portage_util` → `portage.util`, `output` → `portage.output`;
   audit the `portage import ...` names against the current API.
3. Get `python puse.py --show <pkg>` working read-only in the container.
4. Validate the write paths against a throwaway `/etc/portage`.
5. Land the `-9999` ebuild; iterate with `ebuild ... install`.
6. Tag a release and add the versioned ebuild.
