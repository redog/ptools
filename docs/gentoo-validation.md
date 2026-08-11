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
  gumbo host itself). The workflow now fails that leg loudly if the integration
  suite skips: it asserts `portage` imports inside the venv, and re-runs
  `pytest -m integration --junitxml` rejecting any run with zero tests or any
  skip. Without those guards a runner missing the portage module would have
  reported green while validating nothing.
