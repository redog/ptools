# Gentoo validation (Milestone E)

Validation was performed against **real portage**, not the mock backend.

```yaml
DATE: 2026-08-11
METHOD: amd64 stage3 chroot created on liminal (the gumbo self-hosted runner had
        no registered runner at the time, so the chroot alternative was used)
STAGE3: stage3-amd64-openrc-20260811T083102Z.tar.xz
REPOSITORY: portage-latest.tar.xz snapshot -> /var/db/repos/gentoo (19442 packages)
PROFILE: default/linux/amd64/23.0 (10 profiles in the stack)
PYTHON: 3.14.6
PORTAGE: 3.0.81.2
HARNESS: scripts/chroot_validate.sh + scripts/chroot_inner.sh
RESULT: all checks passed
RERUN: 2026-08-12, same chroot, 12 steps, all passed. Re-run again at HEAD
       627766e ("map a broken portage configuration to exit 7"): 13 integration
       tests passed, all 12 steps passed. This is the run that covers the two
       portage fixes 705a691 (vdb metadata fallback) and 627766e (exit 7) --
       both landed after the earlier rerun, so until now neither had executed
       against real portage on any host.
```

The harness is re-runnable: it reuses an extracted chroot and clears the managed
targets first, so every step produces evidence from a known state rather than
leftovers from the previous run.

No host configuration was touched: every write landed inside the chroot or in a
`PTOOLS_CONFIG_ROOT` sandbox under `/tmp`.

## 1. Integration suite

`pytest -m integration` — **13 passed, 0 skipped**. Covers a category-qualified
atom, an exact atom, an invalid atom, an ambiguous unqualified name, a unique
unqualified name, USE/keyword reads, the vdb metadata fallback, a sandboxed write
with preservation, CLI round trips, and dry-run.

## 2. Read-only operation, non-root

```text
$ puse sys-apps/portage                       # as `nobody`
sys-apps/portage  (sys-apps/portage-3.0.81.2)
  iuse:                   apidoc build doc gentoo-dev +ipc +native-extensions +rsync-verify selinux test xattr ...
  effective use:          abi_x86_64 amd64 elibc_glibc ipc kernel_linux native-extensions python_targets_python3_14 rsync-verify xattr
  installed use:          abi_x86_64 amd64 elibc_glibc ipc kernel_linux native-extensions python_targets_python3_13 python_targets_python3_14 rsync-verify xattr
  managed:                (none)
  target:                 /etc/portage/package.use/ptools

$ pkw sys-apps/portage                        # as `nobody`
  arch:                   amd64
  ebuild keywords:        ~alpha amd64 arm arm64 ~hppa ~loong ~m68k ~mips ppc ppc64 ~riscv ~s390 ~sparc x86
```

Reading requires no privilege, and the values match what portage itself reports.

## 3. Non-root dry-run

```text
$ puse --dry-run sys-apps/portage doc         # as `nobody`, exit 0
[dry-run] sys-apps/portage: +doc -> /etc/portage/package.use/ptools
OK: /etc/portage/package.use still absent after the dry-run
```

A dry-run neither writes nor requires write access — it does not even create the
target directory.

## 4. Non-root write is refused (exit 5)

```text
$ puse sys-apps/portage doc                   # as `nobody`
puse: error: cannot write to /etc/portage/package.use: Permission denied; re-run as root
exit=5
```

No privilege escalation is attempted: ptools never invokes sudo.

## 5. Write preserves the rest of the file

Target seeded with hand-written content, then `puse sys-apps/portage apidoc` as
root:

```text
# hand written, must survive

app-shells/bash net
sys-apps/portage apidoc
```

The comment, the blank line, and the unrelated `app-shells/bash` entry are
untouched.

## 6. Portage consumes the generated entry

The candidate flag is an IUSE flag portage does **not** currently enable, so its
appearance can only come from the new entry:

```text
before: sys-apps/portage-3.0.81.2 effective USE contains apidoc: False
$ puse sys-apps/portage apidoc
after:  sys-apps/portage-3.0.81.2 effective USE contains apidoc: True
```

Read back through `portage.config().setcpv()` — portage's own USE evaluation,
not ptools re-reading its own file. See `scripts/verify_consumption.py`.

## 7. Idempotency and unset

```text
$ puse --json sys-apps/portage apidoc
{"operation": "use.set", ..., "added": [], "removed": [], "changed": false, "dry_run": false}

$ puse --unset sys-apps/portage apidoc
sys-apps/portage: -apidoc -> /etc/portage/package.use/ptools
```

After the unset the file is back to its seeded content — the now-empty managed
entry is removed rather than left as a bare atom.

## 8. Keywords

```text
$ pkw --testing sys-apps/portage
sys-apps/portage: +~amd64 -> /etc/portage/package.accept_keywords/ptools
```

`~amd64` came from the host's real ARCH, not a default.

## 9. A real flat `package.use` is refused, not clobbered

The flat layout is a legitimate portage configuration, so the refusal had to be
seen against a real one rather than only a unit-test fixture. `/etc/portage/
package.use` was replaced with a hand-written **file** carrying an entry portage
does not otherwise enable, and portage was asked to evaluate it first:

```text
sys-apps/portage-3.0.81.2 effective USE contains apidoc: True   # from the flat file
second candidate flag: build

$ puse sys-apps/portage build
puse: error: /etc/portage/package.use is a regular file; ptools requires the
directory layout (convert it with: mv /etc/portage/package.use
/etc/portage/package.use.tmp && mkdir /etc/portage/package.use && mv
/etc/portage/package.use.tmp /etc/portage/package.use/00-local)
exit=6

OK: flat file byte-identical after the refusal
```

Checked by sha256 either side: ptools does not replace the file with a
directory, does not append to it, and does not truncate it. Reads still work
under the flat layout — the show form reported `apidoc` in effective USE (portage
picking up the flat entry) while correctly reporting `managed: (none)`, since
none of it came from a ptools-managed target.

## Bug found by this validation

`portage.dep.Atom("cat/pkg").cpv` returns the **cp**, not a cpv, for an
unversioned atom. The backend trusted it, so every package-wide lookup produced
a bogus "cpv" that then failed `setcpv()` and `aux_get()` — meaning USE and
keyword reads were broken for exactly the default (package-wide) case. Unit
tests could not see this: the mock had the sane behavior. Fixed by always taking
the cpv from the version-sorted match result, and covered by an integration
assertion that a resolved cpv carries a version.

## Not covered here

- A long-lived, real (non-chroot) Gentoo installation with years of accumulated
  `/etc/portage` content. (The flat-layout gap that used to be listed here is
  closed — see §9, checked against real portage.)
- A second architecture; only amd64 was exercised.
- The gumbo runner leg, which is still queued (the repo has zero registered
  runners, so the queued jobs cannot start; bring-up is a human step on the
  gumbo host itself — see "Why the gumbo leg cannot start" below). The workflow
  now fails that leg loudly if the integration suite skips: it asserts `portage`
  imports inside the venv, and re-runs `pytest -m integration --junitxml`
  rejecting any run with zero tests or any skip. Without those guards a runner
  missing the portage module would have reported green while validating nothing.

## Why the gumbo leg cannot start

Read against the dev-env tree on 2026-08-12. Both config files really are
correct: `containers.list` has `gentoo-dev:Containerfile.gentoo:devenv-gentoo`
uncommented, and `projects.list` has `redog/ptools : gentoo-dev`. The blocker is
*not* only that a human has to run bring-up — the previously documented bring-up
command would not have produced a matching runner:

- `run-runners.sh` is the only script that reads `projects.list` and registers a
  runner with `--labels self-hosted,gumbo,<os>` (`run-runners.sh:145`), which is
  what this repo's `runs-on: [self-hosted, gumbo, gentoo-dev]` needs.
- `start-env.sh` **never calls `run-runners.sh`** (no reference to it in that
  file). dev-env's README lists it as "Called by `start-env.sh`", but the README
  also carries an "Integrating `run-runners.sh` into `start-env.sh`" section
  describing that swap as still to be done. The README's own claim is stale.
- `start-env.sh` only starts a runner at all with `--include-runner`
  (`start-env.sh:100-102`), and that one is the generic `devenv-runner` image
  whose entrypoint hardcodes `--labels "gumbo,podman"`
  (`runner-entrypoint.sh:48`). Those labels never match `gentoo-dev`, and that
  image has no `portage` either.

So `./start-env.sh --rebuild --persist` alone leaves ptools' jobs queued forever.
The missing step is `run-runners.sh`. Full sequence for a human on gumbo:

```bash
./update-configs.sh                     # sync git-tracked config to ~/.config/dev-env
./start-env.sh --build-gentoo           # once; populates gentoo-pkgs/ binpkgs
./start-env.sh --rebuild --persist      # builds the devenv-gentoo image
./run-runners.sh --dry-run              # preview; then, if it looks right:
./run-runners.sh --only redog/ptools    # starts gentoo-dev + registers the runner
```

`run-runners.sh` needs `GITHUB_TOKEN` in `~/.config/dev-env/.env` and skips any
OS whose image is not built yet, so step 3 must precede it. Changing
`start-env.sh` to call it is a dev-env decision, in a file dev-env's README
flags as security-sensitive; it is out of scope for ptools and is not done here.

One refinement on that decision, from `run-runners.sh`'s own header: it "takes
NO input from the network" — all intent comes from the git-tracked, regex-
validated `containers.list`/`projects.list`. So `start-env.sh` calling it with
no network-derived arguments would *not* widen the `authorized_keys`
`command=` gate; the pinned command stays
`start-env.sh --rebuild --persist` and `$SSH_ORIGINAL_COMMAND` is still only
honoured when it is exactly `update`.

Re-read on 2026-08-12, this leans further toward "unfinished" than the earlier
note allowed. dev-env's README architecture diagram documents the forced command
as chaining into exactly that call:

```
│ authorized_keys command= forces   │
│  start-env.sh --rebuild --persist │
│   → update-configs.sh sync        │
│   → rebuild + run-runners.sh      │
```

So the README describes behavior `start-env.sh` does not implement — the gap is
between the code and dev-env's own stated design, not a boundary someone chose
to hold. The `run-runners.sh` header's "so start-env.sh does not have to" reads,
in that light, as *why the network-input handling lives elsewhere*, not as a bar
on calling it. This still stays OPEN: it is a change to another repo, in a file
that repo flags as security-sensitive, and it is out of scope for ptools.

## The host is not listening at all (checked 2026-08-12)

Fixing `start-env.sh` would not, by itself, start the ptools leg — the trigger
chain is already dead one link earlier:

- `gh api repos/redog/dev-env/actions/runners` first returned `total_count` 3
  with **all three `"status": "offline"`** (ids 137, 138, 140; labels
  `self-hosted, Linux, X64, gumbo, podman` — the generic `devenv-runner`).
- Re-checked later the same day, that endpoint returns **`total_count` 0**: the
  three offline registrations are gone, so even the stale registrations have now
  been reaped. The conclusion does not change, it only gets simpler — there is
  no runner record for gumbo anywhere.
- dev-env's `update-gumbo.yml` is `runs-on: gumbo`, so it needs one of those to
  be online. Its runs have been **queued since 2026-08-11** (6 of them, oldest
  ~4h30m at time of checking). Re-checked `2026-08-12T00:40Z`: still zero
  runners registered on either repo, so neither backlog has moved.

Both repos are now in the same state, though they arrived there differently:

| repo | runners registered | history | consequence |
|------|--------------------|---------|-------------|
| `redog/ptools` | 0 | never registered | needs `run-runners.sh` on gumbo |
| `redog/dev-env` | 0 | 3 registered, went offline, then reaped | nothing on gumbo is listening |

Net: no process on gumbo is polling GitHub, so nothing can be triggered
remotely — not the ptools leg, and not the dev-env self-update that would carry
a `start-env.sh` fix to the host. Both breaks need someone at the gumbo console,
and the runner-container bring-up has to come first. Until then the gumbo leg of
Milestone F cannot be attempted from liminal by any means that respects the
security boundary.
The gentoo image runs `emerge-webrsync` at build time
(`Containerfile.gentoo`), so the integration suite will have a real ebuild
repository and the skip-guard should pass once a runner registers.

## Do not count on the queued runs to drain

The queued ptools runs — **8** as measured at `2026-08-12T01:20Z` — are not a
reliable way to collect the evidence once gumbo comes back. Two reasons:

- GitHub terminates a job that has waited too long for a self-hosted runner to
  pick it up (~24h). The backlog is only ~3h30m old at that measurement, and the
  eight runs fall out of the queue across one window: the oldest (`428aa4b`,
  waiting since `2026-08-11T21:42Z`) around `2026-08-12T21:42Z`, the newest
  (`627766e`, since `2026-08-12T00:59Z`) around `2026-08-13T00:59Z`. So if a
  runner registers *before* that window the queued runs would in fact drain by
  themselves, and after it nothing is left to drain at all.
- `ci.yml`'s push trigger is path-filtered to `**/*.py`, `pyproject.toml`, and
  `.github/workflows/ci.yml`. Docs-only commits do **not** arm a new run, so
  pushing another note like this one will not re-queue the leg. (Two commits
  since `22a165f` did arm one, because they were not docs-only despite their
  subjects: `705a691` changed `portage_real.py`, and `bafbc64` touched
  `ci.yml` alongside its doc edit.)

One refinement, because it changes what a drained backlog would be worth: the
newest queued run is no longer merely "closest to the tip", it covers **exactly
the code at `HEAD`**. `627766e` is the last commit that touched code; the two
commits after it (`3126461`, `d747e71`) are docs-only — which is also why they
armed no run of their own. So if a runner registers inside the window above,
run `627766e` alone is sufficient evidence for the current tree, and the other
seven are superseded. That is a reason not to *panic* about the backlog
expiring, not a reason to wait on it: an explicit
`gh workflow run ci.yml -R redog/ptools --ref main` is still the way to collect
the evidence, and it is the only way once the window closes.

So after runner bring-up, trigger the leg explicitly rather than waiting:

```
gh workflow run ci.yml -R redog/ptools --ref main
```

`ci.yml` already declares `workflow_dispatch`, so no workflow change is needed
for this. That run is what closes Milestone F: its "Assert the integration suite
actually ran" step is the check that turns a green job into real evidence.
