#!/usr/bin/env python3
"""Prove that portage actually consumes a ptools-generated package.use entry.

Two modes, meant to be used either side of a `puse` write (Milestone E):

    verify_consumption.py pick  cat/pkg          -> prints a candidate USE flag
    verify_consumption.py check cat/pkg FLAG     -> exit 0 iff FLAG is now in
                                                    the package's effective USE

The "candidate" is an IUSE flag of the package that portage does *not* currently
enable, so seeing it appear afterwards can only be the effect of the new entry.
Everything is read through the supported portage API.
"""

import sys


def effective_use(cpv: str) -> set[str]:
    import portage

    settings = portage.config(clone=portage.settings)
    settings.setcpv(cpv, mydb=portage.portdb)
    return set(settings["PORTAGE_USE"].split())


def best_cpv(atom: str) -> str:
    import portage

    matches = portage.portdb.match(atom)
    if not matches:
        raise SystemExit(f"no ebuild matches {atom}")
    return str(matches[-1])


def iuse(cpv: str) -> list[str]:
    import portage

    raw = portage.portdb.aux_get(cpv, ["IUSE"])[0].split()
    return [flag.lstrip("+-") for flag in raw]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit(__doc__)
    mode, atom = argv[0], argv[1]
    cpv = best_cpv(atom)

    if mode == "pick":
        enabled = effective_use(cpv)
        for flag in iuse(cpv):
            if flag not in enabled and not flag.startswith(("abi_", "elibc_", "kernel_")):
                print(flag)
                return 0
        raise SystemExit(f"every IUSE flag of {cpv} is already enabled")

    if mode == "check":
        flag = argv[2]
        enabled = effective_use(cpv)
        print(f"{cpv} effective USE contains {flag}: {flag in enabled}")
        return 0 if flag in enabled else 1

    raise SystemExit(f"unknown mode: {mode}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
