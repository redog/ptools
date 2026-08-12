# ptools — Continue-From-Here Build Prompt

> This is a **promptware loop**. ptools already exists as a partially built
> Python 3 package; your job is to **finish and correct it**, not build from
> zero. This file plus `docs/*.md` are the single source of truth for intent.
> Everything is on `main`; changes are reverted through git history if a loop
> iteration goes wrong.

---

# 1. Operating Protocol (how you iterate)

```yaml
Agent Host: liminal (user "imp"), Ubuntu, NO system portage module available
Integration/Validation Host: gumbo (Gentoo), reached via the GitHub self-hosted
  runner that fires on push; OR a local stage3 chroot you may create on liminal
Source of Truth: this file + docs/environment.md + docs/legacy-behavior.md
Version Control: commit and push directly to main per logical unit of work
  (CI on gumbo validates each push); revert via git history if an iteration is bad
Release: never publish; never upload to PyPI
```

```text
Loop per unit of work:
  1. Read current state (this file, docs/, the code you are about to touch).
  2. Make the smallest correct change toward the next milestone.
  3. Run LOCAL gates on liminal (mock backend — no portage needed):
       ruff check .   &&   ruff format --check .
       mypy src/ptools
       pytest -m 'not integration'          # 85% coverage gate applies
  4. Commit + push to main.
  5. The gumbo runner runs the full suite (incl. integration) against real
     portage. Read its result; if red, fix forward or revert.
  6. Update the relevant docs/*.md completion-check file as milestones close.

STOP and ask the user when:
  - a decision is marked OPEN below, or a new one arises;
  - a change would write to a REAL /etc/portage outside a sandbox/chroot;
  - scope would expand beyond finishing ptools as specified here.

NEVER:
  - break or corrupt live portage configuration;
  - escalate privilege from inside the tool (see Privilege Policy);
  - use shell=True or interpolate user input into a shell;
  - commit secrets; publish a release; create an ebuild before behavior is complete.
```

---

# 2. Current State (factual, verified against the tree)

```yaml
Done:
  Packaging: hatchling, src/ layout, pyproject.toml, requires-python >=3.11
  Command surface (Milestone A): puse + pkw are first-class argparse CLIs
    (src/ptools/puse.py, src/ptools/pkw.py) sharing src/ptools/cli_common.py.
    The umbrella cli.py and the compat/ subprocess shims are DELETED;
    [project.scripts] exposes only puse and pkw.
  Exit-code mapping (Milestone B): full 0/2/3/4/5/6/7/8 table on
    PtoolsError.exit_code; results on stdout, errors (incl. JSON errors) on stderr
  Config store (Milestone C): preservation, inline comments, duplicate-fail with
    opt-in --merge-duplicates, symlink refusal, flat-layout detection, atomic
    replace preserving mode/ownership, never world-writable, NO sudo
  Core services: ReadOnlyService + MutationService (src/ptools/services.py)
  Portage adapter: PortageBackend Protocol + MockPortageBackend
                   (src/ptools/portage_adapter.py; get_portage_backend factory);
                   real integration split out to src/ptools/portage_real.py
  Domain + errors: src/ptools/domain.py, src/ptools/errors.py
  Test suite: tests/unit/* green on the mock backend (85% gate; ~97% actual);
    tests/integration/test_real_portage.py written, skips without portage
  Discovery script: scripts/discover_environment.py (run by CI on gumbo)
  CI: .github/workflows/ci.yml runs pytest + environment discovery on the
      gumbo gentoo-dev runner
  Real-system validation (Milestones D+E): performed in an amd64 stage3 chroot
    on liminal, because gumbo has no registered self-hosted runner (its job has
    been queued since 2026-08-11). docs/environment.md now holds real values;
    docs/gentoo-validation.md records the evidence, including portage actually
    consuming a generated package.use entry.
  Chroot harness: scripts/chroot_validate.sh + scripts/chroot_inner.sh
                  + scripts/verify_consumption.py

Environment override:
  PTOOLS_CONFIG_ROOT replaces <PORTAGE_CONFIGROOT>/etc/portage — this is how
  sandbox/chroot testing writes without touching a live configuration.

  Documentation (Milestone F): README carries every section SPEC §23 requires
    (purpose, background, supported Gentoo/Python, installation, read-only /
    dry-run / write examples, target policy, exit codes, JSON, limitations, and
    a migration table each for puse and pkw). tests/unit/test_docs.py
    machine-checks it: every ```bash example is executed against the mock
    backend, the exit-code table is compared to the error taxonomy, the
    documented targets to what the tools report, and [project.scripts] to
    puse+pkw only. Stale SPEC sections are marked SUPERSEDED.

Still open:
  Gumbo runner    : the CONFIG is already correct on both sides - dev-env
                    containers.list enables gentoo-dev and projects.list has
                    `redog/ptools : gentoo-dev`. What is missing is bring-up ON
                    the gumbo host, which by design has no inbound path from
                    liminal (see dev-env README "Security boundary" - do NOT try
                    to widen the SSH gate). Confirmed by API, not just inferred
                    from the queue: `gh api repos/redog/ptools/actions/runners`
                    returns total_count 0, so no runner has ever registered -
                    bring-up still pending, NOT a registered runner gone offline
                    (5 runs queued as of 2026-08-12).

                    CORRECTION (2026-08-12, read against the dev-env tree): the
                    bring-up command previously recorded here was insufficient.
                    `start-env.sh --rebuild --persist` does NOT register a
                    gentoo-dev runner - only `run-runners.sh` applies the labels
                    `self-hosted,gumbo,<os>` that this repo's ci.yml matches
                    (run-runners.sh:145), and start-env.sh never calls it. Its
                    own optional `--include-runner` container is the generic
                    devenv-runner image with hardcoded labels "gumbo,podman"
                    (runner-entrypoint.sh:48) and no portage. Correct sequence,
                    and the run-runners.sh step is the one that was missing:
                      ./update-configs.sh
                      ./start-env.sh --build-gentoo     # once, populates gentoo-pkgs/
                      ./start-env.sh --rebuild --persist   # builds devenv-gentoo
                      ./run-runners.sh --only redog/ptools # registers the runner
                    Details and evidence: docs/gentoo-validation.md
                    "Why the gumbo leg cannot start". Teaching start-env.sh to
                    call run-runners.sh is a dev-env change in a security-
                    sensitive file - OPEN, ask the user; do not do it silently.
                    (Refinement: dev-env's README diagram documents the forced
                    command as chaining "-> rebuild + run-runners.sh", which
                    start-env.sh does not do - so that gap is code-vs-its-own-
                    design, not a boundary held on purpose. Still OPEN: other
                    repo, security-sensitive file, out of ptools' scope.)

                    SECOND, EARLIER BREAK (2026-08-12): nothing on gumbo is
                    listening at all. redog/dev-env had 3 registered runners,
                    ALL offline (labels gumbo,podman), so dev-env's own
                    update-gumbo.yml (runs-on: gumbo) has been queued since
                    2026-08-11 too. So a start-env.sh fix could not even be
                    delivered to the host remotely. Both breaks require someone
                    at the gumbo console, runner bring-up first. Nothing about
                    the gumbo leg is actionable from liminal.
                    UPDATE (later on 2026-08-12): dev-env's runner count is now
                    total_count 0 - the three offline registrations have been
                    reaped. Same conclusion, fewer moving parts: no runner
                    record exists for gumbo in either repo.

                    WHEN GUMBO RETURNS, re-trigger explicitly; do not wait on
                    the 5 queued runs. GitHub expires jobs that wait ~24h for a
                    self-hosted runner (the backlog dates from 2026-08-11T21:42Z),
                    and ci.yml's push trigger is path-filtered to **/*.py,
                    pyproject.toml, and ci.yml - so docs commits, which is all
                    this repo has produced since 22a165f, will not re-queue it:
                      gh workflow run ci.yml -R redog/ptools --ref main
                    ci.yml already declares workflow_dispatch. See
                    docs/gentoo-validation.md "Do not count on the queued runs
                    to drain".
  Milestone F     : everything except the gumbo leg is DONE and green -
                    ruff check, ruff format --check, mypy strict, pytest
                    (156 passed, 97.15% vs the 85% gate), python -m build
                    (sdist + wheel), python -m twine check (both PASSED), and
                    the documentation/migration work above. The single
                    outstanding criterion is the integration suite passing on
                    gumbo as a second, independent Gentoo host. (It already
                    passes on real portage in the stage3 chroot: 13 passed,
                    see docs/gentoo-validation.md §1.)
```

Legacy originals `ptk.py`/`puse.py`/`pkw.py` are **deleted from the tree**; they
live in git history and their behavior is captured in `docs/legacy-behavior.md`.
Do not recreate them.

---

# 3. Resolved Decisions (previously the "unknowns"; now confirmed)

```yaml
Command Surface: two first-class commands, `puse` and `pkw`. `ptools` is the
  PACKAGE/dist name and a description of the set — NOT a command anyone types.
  Drop the `ptools` console entry point. puse/pkw call the services directly;
  they are NOT compatibility wrappers and do NOT subprocess another command.
Package Inspection: folded into puse/pkw as the default "show" form — no separate
  `package` command.
Interface Style: flat and terse, unix-like (`puse [opts] PACKAGE [tokens...]`).
Managed USE Target: /etc/portage/package.use/ptools           (directory layout)
Managed Keyword Target: /etc/portage/package.accept_keywords/ptools (directory layout)
  (the file is named `ptools` as a marker for "managed by this tool set".)
Backups: none by default (no .bak). Safety comes from preservation + atomic writes.
Privilege Policy: the tool performs NO privilege escalation. The user runs it as
  root / via sudo when writing. If the target is not writable, exit 5 (Permission)
  with a clear message. Read-only operations never require privilege.
PORTAGE_CONFIGROOT: discover at runtime; never assume `/`.
Minimum Python: 3.11 (from pyproject; supersedes the old "unresolved" placeholder).
Target ARCH / Portage version: read from the real system (Milestone D); never assume amd64.
Backup Policy / Layout / Wrappers: confirmed above — no longer open.

OPEN: (none currently — ask before introducing a new decision)
```

---

# 4. Command Surface (target contract)

Global options (both commands): `[--exact] [--dry-run] [--json] [--quiet] [--no-color]`
- `--exact` targets `=cat/pkg-ver`; default targets `cat/pkg` (package-wide).
- `--dry-run` computes and prints the plan but writes nothing (target bytes unchanged).
- `--json` emits a single JSON object on stdout (no ANSI, ever).

```bash
# puse — per-package USE flags (+ inspection)
puse [GLOBAL] PACKAGE                       # show effective USE state (default when no tokens)
puse [GLOBAL] PACKAGE TOKEN [TOKEN ...]     # set: TOKEN = flag (enable) | -flag (disable)
puse [GLOBAL] --unset PACKAGE FLAG [FLAG ...]   # remove managed flag AND -flag entries

# pkw — per-package keywords (+ inspection)
pkw  [GLOBAL] PACKAGE                        # show keyword state
pkw  [GLOBAL] PACKAGE KEYWORD [KEYWORD ...]  # set: KEYWORD = ~arch | -* | explicit value
pkw  [GLOBAL] --testing PACKAGE              # expands to ~${ARCH}
pkw  [GLOBAL] --unset PACKAGE KEYWORD [KEYWORD ...]
```

```yaml
Package Inputs:
  Category Qualified: app-editors/neovim
  Exact:              =app-editors/neovim-0.10.4
  Version Matched:    ~app-editors/neovim-0.10.4
  Unqualified:        neovim   # may be ambiguous -> exit 4
Configuration Format: whitespace-delimited atom + tokens; comments, blank lines,
  and unrelated entries are PRESERVED byte-for-byte.
Duplicate Atom: fail by default; opt-in merge via --merge-duplicates only.
Idempotency: repeated identical operations report changed:false and write nothing.
```

```json
{ "operation": "use.set", "atom": "app-editors/neovim",
  "target": "/etc/portage/package.use/ptools",
  "added": ["lua"], "removed": [], "changed": true, "dry_run": false }
```

```yaml
Exit Codes:
  0 Success | 2 Usage | 3 Not Found | 4 Ambiguous | 5 Permission
  6 Invalid Configuration | 7 Portage Error | 8 Write Error
Stream Contract:
  results -> stdout ; errors -> stderr ; JSON contains no ANSI ; no success msgs on stderr
Atomic Write:
  read target -> parse managed entries -> render candidate -> write temp file in the
  target dir -> flush -> preserve existing mode/ownership -> os.replace() atomically.
  An interrupted write must never leave a partial or truncated target.
```

---

# 5. Hard Constraints — Do-Not List

```text
✗ Do not make `ptools` an installed command; do not reintroduce an umbrella CLI.
✗ Do not implement puse/pkw as subprocess shims or "compat wrappers" — they are
  first-class CLIs that call the service layer directly.
✗ Do not modify a real /etc/portage during development without explicit approval;
  use a sandbox dir or a stage3 chroot.
✗ Do not escalate privilege from within the tool; refuse with exit 5 instead.
✗ Do not write outside the resolved Portage configuration root.
✗ Do not rewrite whole files under package.use/ or package.accept_keywords/.
✗ Do not erase comments, blank lines, unknown-but-valid lines, or unrelated entries.
✗ Do not normalize/merge duplicate atoms without --merge-duplicates.
✗ Do not silently migrate legacy package.keywords to package.accept_keywords.
✗ Do not follow arbitrary symlinks during privileged writes.
✗ Do not change ownership/permissions except to preserve an existing target.
✗ Do not create world-writable files.
✗ Do not log/print/commit credentials or secrets.
✗ Do not use shell=True or interpolate user input into a shell.
✗ Do not execute emerge, dispatch-conf, or etc-update; do not install/remove packages.
✗ Do not publish a release or upload to PyPI.
✗ Do not create an ebuild before package + runtime behavior are complete.
✗ Do not implement custom atom parsing, version comparison, repo visibility,
  USE-mask/force, or package matching — use the supported Portage API.
✗ Do not use private Portage APIs when a supported API or stable command exists.
✗ Do not implement the legacy --fix-kw cleanup in this pass (deferred).
✗ Do not invent behavior for the lost fourth legacy tool or expand scope.
✗ Do not add Click, Typer, Rich, or Pydantic without a demonstrated unmet need.
✗ Do not claim Gentoo compatibility from unit tests alone.
✗ Do not mark a milestone complete while its checks fail or are unrecorded.
```

Reuse order for Portage integration (highest first): **portage Python API**
(`portage`, `portage.dbapi`, `Atom`, settings) → `portageq` → `equery`/`eix`.
Never scrape `emerge` output.

---

# 6. Remaining Milestones (dependency-ordered)

```yaml
A. DONE - Refactor CLI to first-class puse/pkw:
   What: Delete the `ptools` umbrella (cli.py) and the subprocess shims in
     compat/. Implement `puse` and `pkw` as standalone argparse CLIs that call
     ReadOnlyService/MutationService/ConfigStore directly, per §4. Fold
     inspection into the bare-PACKAGE show form. Update pyproject [project.scripts]
     to expose ONLY puse and pkw. Update/rewrite tests accordingly.
   Done when: `puse --help` and `pkw --help` exit 0; no `ptools` script is
     installed; no subprocess call to another ptools command exists; the show,
     set, unset, --testing, --exact, --dry-run, and --json paths have passing
     unit tests using the mock backend; ruff+mypy+pytest green at >=85%.

B. DONE - Complete exit-code mapping:
   What: Map every failure to §4's table (2 usage, 5 permission, 6 invalid config,
     7 portage, 8 write) across both commands, results on stdout / errors on stderr.
   Done when: tests assert each code for a representative failure; JSON error
     objects accompany non-zero exits; no success text is emitted on stderr.

C. DONE (unit + sandbox; chroot evidence lands with E) - Harden the managed config store:
   What: Preserve comments/blank/unknown/unrelated lines; reject invalid selected
     entries; duplicate atoms fail (opt-in --merge-duplicates); deterministic
     render; atomic replace preserving mode/ownership.
   Done when: unit + sandbox tests prove preservation, duplicate-fail, and that an
     interrupted candidate write never yields a partial target.

D. DONE (via stage3 chroot; re-confirm on gumbo when it is back) - REAL environment discovery:
   What: On gumbo (via the runner) or a local stage3 chroot, capture real
     PYTHON_VERSION, PORTAGE_VERSION, PORTAGE_MODULE, ROOT, EPREFIX,
     PORTAGE_CONFIGROOT, ARCH, PACKAGE_USE_LAYOUT, PACKAGE_KEYWORD_LAYOUT, and
     EXISTING_TOOL_DECISIONS. Validate the real portage backend (Atom import +
     a supported db match) via the `integration`-marked tests.
   Done when: docs/environment.md holds real (non-mocked) values and the
     integration tests pass on gumbo for a category-qualified atom, an exact atom,
     an invalid atom, and an ambiguous unqualified name.

E. DONE (stage3 chroot; see docs/gentoo-validation.md) - Validate on current Gentoo:
   What: Read-only, non-root dry-run, sandbox/chroot write (file preserved), and
     evidence that portage actually consumes the generated entries.
   Done when: docs/gentoo-validation.md records profile, portage+python versions,
     layouts, and exact results incl. portage consuming a generated sandbox entry.

F. BLOCKED on the gumbo runner only - everything else DONE (see §2):
   Release candidate (no publish):
   What: machine-checked docs + migration notes; all gates green; build artifacts.
   Done when: ruff check + format check pass; mypy passes; pytest >=85%; all
     integration tests pass on gumbo; wheel + sdist build; twine check passes.
   (Ebuild work — see docs/build-and-test.md — is a SEPARATE step after F.)
```

---

# 7. Quality Gates (run locally on liminal with the mock backend)

```bash
ruff check .
ruff format --check .
mypy src/ptools
pytest -m 'not integration'        # 85% coverage gate (pyproject)
python -m build                    # sdist + wheel, when packaging
python -m twine check dist/*       # artifact validation, Milestone F
# integration tests run on the gumbo runner after push:
pytest -m integration
```

---

# 8. Grounding

```yaml
Repository: https://github.com/redog/ptools   (branch: main)
Package Root: src/ptools
Test Root: tests
Build Metadata: pyproject.toml (hatchling)
Modernization Spec: SPEC.md
Legacy Behavior Notes: docs/legacy-behavior.md
Environment Discovery (currently MOCKED — fix in Milestone D): docs/environment.md
Official Portage Source: https://github.com/gentoo/portage
package.use docs: https://wiki.gentoo.org/wiki//etc/portage/package.use
package.accept_keywords docs: https://wiki.gentoo.org/wiki//etc/portage/package.accept_keywords
Runtime Dependencies: portage + Python standard library (no third-party runtime deps)
```
