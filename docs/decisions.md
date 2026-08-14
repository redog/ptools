# Design decisions

The distilled *why* behind ptools' behavior. Each entry was resolved during
the 2026 modernization (milestones A–J) and is settled — reopen one only with
the project owner. The full deliberation history lived in `SPEC.md` and
`build_PROMPT.md`, deleted after the 1.0.0 release; both remain in git
history and inside the `v1.0.0` tag tarball.

## Command surface

- **Two commands, `puse` and `pkw`; `ptools` is only the distribution name.**
  Flat, terse, unix-like (`puse [OPTIONS] PACKAGE [TOKEN ...]`), inspection as
  the bare-`PACKAGE` form. The umbrella `ptools <noun> <verb>` CLI was
  considered and rejected: the original tools' shape was already right.
- **Ambiguous names offer a menu on a terminal** (reinstated 2026-08-13 from
  the Python 2 originals, reversing an earlier "no interactive mode" call).
  Gated on stdin *and* stderr being TTYs with neither `--json` nor `--quiet`,
  so every scripted invocation stays deterministic: exit 4, candidates on
  stderr. There is deliberately no `--interactive` flag — TTY detection is
  the switch.
- **`--version` works without portage**, because version questions come from
  exactly the machines where the backend is broken.

## Portage integration

- **Everything package-shaped goes through the portage Python API** — atom
  parsing, version comparison, matching, effective USE, ARCH. Never
  reimplemented, never scraped from `emerge` output. Portage owns Gentoo
  semantics; approximations rot.
- **Nothing is assumed**: not `/` as root, not `/etc/portage` as config root
  (`PORTAGE_CONFIGROOT`, overridden outright by `PTOOLS_CONFIG_ROOT` for
  sandboxing), not amd64 (`--testing` expands from the live ARCH).

## Privilege

- **No escalation, ever.** An unwritable target exits 5; running under sudo is
  the user's explicit decision, not the tool's. (The 2004 originals shelled
  out to sudo; that did not survive.)

## The config store

- **Preservation is the prime directive.** Comments, blank lines, unknown
  lines, unrelated entries survive byte-for-byte; whole files are never
  rewritten; a semantic no-op changes nothing at all. When in doubt, ptools
  refuses — refusing is the side that cannot mangle a configuration.
- **Atomic replace** (temp file + `os.replace`), preserving mode and
  ownership, never world-writable, symlinked targets refused. No `.bak`
  backups — keep `/etc` under git if you want history.
- **Duplicates fail (exit 6)** unless `--merge-duplicates` opts in.
- **The flat layout is refused, not converted** (exit 6 with the `mv`/`mkdir`
  recipe). Converting someone's config uninvited is how tools destroy trust.
  Legacy `package.keywords` is likewise never written or migrated.
- **A bare atom in `package.accept_keywords` means `~ARCH`** — verified
  against real portage, not wiki lore (`docs/gentoo-validation.md` §10).
  ptools reads it as an implicit value and merges into it; a valueless
  `package.use` entry stays an error, because there it really is meaningless.

## Multi-file management (Milestone H)

- **Shows read every file in the directory and every atom form of the
  package** (exact, versioned, slotted — labeled as written), because portage
  does; anything less lies to the user.
- **Writes follow the atom**: the single file already holding it is edited in
  place; several holders is exit 4 until `--file` picks one; new atoms go to
  the `default-file` from `ptools.conf`, falling back to the `ptools` marker
  file. Chosen over "always write the ptools file" to avoid silently creating
  cross-file duplicate entries.
- **`ptools.conf` lives in `<config-root>`, not `~/.config`**: it describes
  the system's portage configuration, must read the same under sudo, and is
  carried automatically by the sandbox override. `--init` discovers a layout
  but refuses to overwrite an existing config.

## Output contract

- Results on stdout, errors on stderr, never a success message on stderr.
- Exit codes: 0 success, 2 usage, 3 not found, 4 ambiguous, 5 permission,
  6 invalid configuration, 7 portage error, 8 write error — machine-checked
  against the README table by `tests/unit/test_docs.py`.
- `--json` emits one object, no ANSI, ever.

## Non-goals (settled, not deferred)

- **`--fix-kw` is dropped permanently** (2026-08-14): whole-directory cleanup
  is a job for modern tooling, not for these two commands.
- Wildcard entries (`cat/*`, `*/*`) and nested subdirectories are honoured by
  portage but not attributed by shows.
- No `emerge`/`dispatch-conf`/`etc-update` execution, no package installs.
- The lost fourth legacy tool stays lost — no behavior was invented for it.
- **No PyPI.** The release channel is a git tag plus the in-tree overlay
  (`overlay/`: live `-9999` and the tagged, Manifest-verified version).

## Provenance

Rebuilt 2026 from the 2004–2005 Python 2 originals (`ptk.py`, `puse.py`,
`pkw.py` — deleted, recorded in `docs/legacy-behavior.md`) by a promptware
loop: agent-written changes, machine-checked docs, unit tests on a mock
backend, and integration runs against real portage in a stage3 chroot and on
the gumbo self-hosted CI runner.
