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
```

No host configuration was touched: every write landed inside the chroot or in a
`PTOOLS_CONFIG_ROOT` sandbox under `/tmp`.

## 1. Integration suite

`pytest -m integration` — **12 passed**. Covers a category-qualified atom, an
exact atom, an invalid atom, an ambiguous unqualified name, a unique unqualified
name, USE/keyword reads, a sandboxed write with preservation, CLI round trips,
and dry-run.

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

## Bug found by this validation

`portage.dep.Atom("cat/pkg").cpv` returns the **cp**, not a cpv, for an
unversioned atom. The backend trusted it, so every package-wide lookup produced
a bogus "cpv" that then failed `setcpv()` and `aux_get()` — meaning USE and
keyword reads were broken for exactly the default (package-wide) case. Unit
tests could not see this: the mock had the sane behavior. Fixed by always taking
the cpv from the version-sorted match result, and covered by an integration
assertion that a resolved cpv carries a version.

## Not covered here

- A long-lived, real (non-chroot) Gentoo installation with pre-existing
  `package.use` content and a flat-layout file. The flat-layout refusal is unit
  tested but has not been seen against a real flat `/etc/portage/package.use`.
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
honoured when it is exactly `update`. The countervailing point is that the same
header says the split exists "so start-env.sh does not have to ... Keep it that
way", i.e. the separation looks deliberate rather than unfinished, which is why
this stays an OPEN question for the user rather than an obvious fix.
The gentoo image runs `emerge-webrsync` at build time
(`Containerfile.gentoo`), so the integration suite will have a real ebuild
repository and the skip-guard should pass once a runner registers.
