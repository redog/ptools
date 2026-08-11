# Environment Discovery

Real values, captured by `scripts/discover_environment.py` running against real
portage — not the mock backend. See `docs/gentoo-validation.md` for how the host
was produced and what else was verified on it.

```yaml
DISCOVERED_ON: 2026-08-11
HOST: amd64 stage3 chroot (stage3-amd64-openrc-20260811T083102Z) on liminal
PYTHON_VERSION: 3.14.6
PORTAGE_VERSION: 3.0.81.2
PORTAGE_MODULE: /usr/lib/python3.14/site-packages/portage
ROOT: /
EPREFIX: (unset)
PORTAGE_CONFIGROOT: /
ARCH: amd64
ACCEPT_KEYWORDS: amd64
PROFILE: /var/db/repos/gentoo/profiles/default/linux/amd64/23.0
PROFILE_STACK: 10
EBUILD_REPOSITORIES: gentoo
PACKAGES_IN_TREE: 19442
MANAGED_USE_TARGET: /etc/portage/package.use/ptools
MANAGED_KEYWORD_TARGET: /etc/portage/package.accept_keywords/ptools
```

## PACKAGE_USE_LAYOUT / PACKAGE_KEYWORD_LAYOUT

```yaml
PACKAGE_USE_LAYOUT: absent on a fresh stage3; created as a directory by ptools
PACKAGE_KEYWORD_LAYOUT: absent on a fresh stage3; created as a directory by ptools
LEGACY_PACKAGE_KEYWORDS: absent
```

A fresh stage3 ships **neither** `package.use` nor `package.accept_keywords`, so
there is no layout to detect: ptools creates `package.use/` and
`package.accept_keywords/` as directories and writes the `ptools` file inside
them. On an installed system either path may already exist as a **regular
file** (the old flat layout); ptools does not convert it — it refuses with exit
6 and prints the `mv`/`mkdir` sequence to migrate by hand.

## EXISTING_TOOL_DECISIONS

```yaml
ATOM_PARSING: portage.dep.Atom (never hand-rolled)
PACKAGE_MATCHING: portdb.match / vardb.match (returns version-sorted cpvs)
USE_EVALUATION: portage.config(clone=settings).setcpv(cpv, mydb=portdb)["PORTAGE_USE"]
METADATA: portdb.aux_get(cpv, ["IUSE"|"KEYWORDS"|"USE"])
INSTALLED_DB: portage.db[portage.root]["vartree"].dbapi
CAVEAT: Atom("cat/pkg").cpv returns the *cp*, not a cpv, for an unversioned
        atom. Take the cpv from the match result instead. This was a real bug,
        caught only on a real system, and is now covered by an integration test.
```

## Reproducing

```bash
scripts/discover_environment.py            # on any Gentoo host
sudo scripts/chroot_validate.sh /var/tmp/ptools-chroot   # in a stage3 chroot
```

The CI job on the gumbo runner also runs the discovery script and uploads the
output as the `environment-gentoo-dev` artifact, so this file can be refreshed
from a second, independent host once that runner is registered again.
