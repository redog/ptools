# ptools by redog

Two small commands for editing per-package Portage configuration: **`puse`** for
USE flags and **`pkw`** for keywords. `ptools` is the distribution name — it is
not a command anyone types.

## Purpose

Reading and changing per-package USE flags or keywords means hand-editing files
under `/etc/portage`. ptools does that edit for you: it asks portage what a
package actually is, writes one managed file per concern, and leaves every other
line in the target byte-for-byte alone. It never escalates privilege, never runs
`emerge`, and never parses atoms itself — atom parsing, version comparison, and
package matching all go through the portage Python API.

## Historical background

Promptware rebuild of 2004 portage tools, written originally while I was
learning python ~ 2004-2005. This project rebuilds some of those tools with
modern changes in mind and better integration with gentoo's established tools.
The Python 2 originals (`ptk.py`, `puse.py`, `pkw.py`) are deleted from the tree
and live in git history; `docs/legacy-behavior.md` records what they did.

Coding is mostly handled by agents with me managing the vibes as the kids call
it.

## Supported Gentoo versions

Validated against a current Gentoo system — see `docs/gentoo-validation.md` for
the full record.

| | Validated on |
|---|---|
| Profile | `default/linux/amd64/23.0` |
| Portage | 3.0.81.2 |
| Repository | `gentoo` (~19.4k packages) |
| ARCH | amd64 (never assumed — read from portage) |

Nothing is arch-specific: `pkw --testing` expands to `~${ARCH}` from the live
configuration, and the configuration root comes from `PORTAGE_CONFIGROOT`
rather than being assumed to be `/`.

## Supported Python versions

Python **3.11 or newer** (`requires-python = ">=3.11"`). Runtime dependencies:
none declared — the backend imports `portage`, which is already present on any
Gentoo box. Because it imports the system `portage`, ptools must run under the
same interpreter portage itself uses; a bare venv without
`--system-site-packages` cannot see it and both commands exit 7.

## Installation

```bash
# from a checkout, into the system interpreter
pip install .

# or build artifacts first
python -m build && pip install dist/ptools-0.1.0-py3-none-any.whl
```

A live ebuild ships in this repo as a ready-to-use overlay (`overlay/`, package
`app-portage/ptools`); registering and using it is walked through in
`docs/build-and-test.md` §6.

## Read-only examples

Showing state needs no privilege and writes nothing.

```bash
puse app-editors/neovim                  # IUSE, effective USE, installed USE, managed entries
pkw app-editors/neovim                   # ARCH, ebuild KEYWORDS, managed entries
puse --exact =app-editors/neovim-0.10.4  # a specific version rather than the package
```

```text
$ puse app-editors/neovim
app-editors/neovim  (app-editors/neovim-0.11.0)
  iuse:                   lua python tree-sitter
  effective use:          lua tree-sitter
  installed use:          lua
  managed:                (none)
  target:                 /etc/portage/package.use/ptools
```

## Dry-run examples

`--dry-run` resolves the package, computes the plan, prints it, and leaves the
target's bytes untouched — it does not even create the target directory. It
needs no write access, so it is the safe way to preview as an ordinary user.

```bash
puse --dry-run app-editors/neovim lua -python
pkw --dry-run --testing app-editors/neovim
```

```text
$ puse --dry-run app-editors/neovim lua
[dry-run] app-editors/neovim: +lua -> /etc/portage/package.use/ptools
```

## Write examples

```text
ptools modifies Portage configuration under /etc/portage. Use --dry-run before applying changes.
```

Writing needs root — ptools performs **no** privilege escalation of its own, so
run it under `sudo` yourself. An unwritable target exits 5 rather than trying to
elevate.

```bash
puse app-editors/neovim lua -python      # enable lua, disable python
pkw --testing app-editors/neovim         # accept ~amd64 for this package
pkw app-editors/neovim '**'              # accept any keyword, including none
puse --unset app-editors/neovim lua      # drop the managed lua entry
pkw --unset app-editors/neovim '~amd64'
```

Repeating an operation is idempotent: it reports `no change` and writes nothing.

To exercise writes without touching a live configuration, point
`PTOOLS_CONFIG_ROOT` at a scratch directory — this replaces
`<PORTAGE_CONFIGROOT>/etc/portage` outright:

```bash
PTOOLS_CONFIG_ROOT=/tmp/sandbox-portage puse app-editors/neovim lua
```

## Configuration target policy

| Concern | Target |
|---|---|
| USE flags | `<config-root>/package.use/ptools` |
| Keywords | `<config-root>/package.accept_keywords/ptools` |

The file is named `ptools` as a marker for "managed by this tool set". The
config root is discovered from portage (`PORTAGE_CONFIGROOT`), or overridden
by `PTOOLS_CONFIG_ROOT`.

- **Preservation.** Comments, blank lines, unrelated atoms, and lines ptools
  does not understand survive byte-for-byte. Whole files are never rewritten.
- **Atomic replace.** A candidate is written to a temp file in the target
  directory, then `os.replace()`d into place, preserving the existing mode and
  ownership. An interrupted write never leaves a partial or truncated target.
- **No backups.** No `.bak` files. Safety comes from preservation plus the
  atomic replace. Keep `/etc` under git if you want history.
- **Duplicates fail.** Two entries for the same atom are an error (exit 6)
  unless you pass `--merge-duplicates`.
- **Bare keyword atoms.** In `package.accept_keywords` a line that is just an
  atom means "accept `~ARCH`" — portage semantics. `pkw` reports it as a
  managed `~ARCH` entry, merges new keywords into it (writing the implicit
  value out explicitly), treats re-adding `~ARCH` as `no change`, and removes
  the entry when `~ARCH` is unset. In `package.use` a valueless entry carries
  no meaning and is refused (exit 6).
- **Directory layout only.** If `package.use` or `package.accept_keywords`
  already exists as a regular file (the old flat layout), ptools refuses with
  exit 6 and prints the `mv`/`mkdir` sequence to migrate by hand — it does not
  convert it for you.
- **Legacy `package.keywords`** is never written or migrated; `pkw` only notes
  that it exists.
- Symlinked targets are refused, and files are never created world-writable.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 2 | Usage |
| 3 | Not Found |
| 4 | Ambiguous |
| 5 | Permission |
| 6 | Invalid Configuration |
| 7 | Portage Error |
| 8 | Write Error |

Results go to stdout, errors to stderr. Success messages are never written to
stderr.

## JSON output

`--json` emits a single JSON object on stdout and never contains ANSI colour.

```bash
puse --json app-editors/neovim lua
```

```json
{ "operation": "use.set", "atom": "app-editors/neovim",
  "target": "/etc/portage/package.use/ptools",
  "added": ["lua"], "removed": [], "changed": true, "dry_run": false }
```

A non-zero exit is accompanied by a JSON error object on **stderr**:

```json
{ "error": "ambiguous", "message": "ambiguous package name: vim (matches app-editors/vim, app-misc/vim)", "exit_code": 4 }
```

## Known limitations

- `--fix-kw` (the legacy invalid-keyword cleanup) is not implemented; it is
  deferred.
- A fourth legacy tool existed and is lost. No behavior was invented for it.
- The flat-file layout is detected and refused, not converted.
- No privilege escalation, so writing is a `sudo` away rather than automatic.
- USE-mask/force and repository visibility are portage's business; ptools
  reports what portage computes rather than reimplementing it.

## Migration from puse

The old mode switches are gone. The shape is now `puse [OPTIONS] PACKAGE [FLAG ...]`.

| Legacy | Now |
|---|---|
| `puse --show PKG` | `puse PKG` |
| `puse --change --any PKG lua` | `puse PKG lua` |
| `puse --change --any --not PKG lua` | `puse PKG -lua` |
| `puse --change --exact =PKG-VER lua` | `puse --exact =PKG-VER lua` |
| `puse --remove PKG lua` | `puse --unset PKG lua` |

`--exact` keeps its old meaning. `--any` was the default and is simply dropped.

## Migration from pkw

`pkw [OPTIONS] PACKAGE [KEYWORD ...]`.

| Legacy | Now |
|---|---|
| `pkw --show PKG` | `pkw PKG` |
| `pkw --change --any PKG` | `pkw --testing PKG` |
| `pkw --change PKG '~amd64'` | `pkw PKG '~amd64'` |
| `pkw --remove PKG '~amd64'` | `pkw --unset PKG '~amd64'` |
| `pkw --fix-kw` | not implemented (deferred) |

Two behavioral changes worth knowing: the originals shelled out to `sudo` and
ptools does not, and ptools writes to `package.accept_keywords/` — it will not
touch a legacy `package.keywords`.

## For agents / contributors

**Active build instructions live in [`build_PROMPT.md`](build_PROMPT.md)** — a
continue-from-here promptware loop with the current state, resolved decisions,
command surface, and remaining milestones. Read it first. Supporting docs:
[`SPEC.md`](SPEC.md), [`docs/legacy-behavior.md`](docs/legacy-behavior.md),
[`docs/environment.md`](docs/environment.md),
[`docs/gentoo-validation.md`](docs/gentoo-validation.md), and
[`docs/build-and-test.md`](docs/build-and-test.md).

The examples and the exit-code table above are machine-checked against the code
by `tests/unit/test_docs.py`.
