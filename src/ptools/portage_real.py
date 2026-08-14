"""Real Gentoo integration.

Everything package-shaped (atom parsing, version comparison, matching, USE
resolution) is delegated to the supported portage Python API; ptools never
reimplements it and never scrapes emerge output.

This module imports ``portage`` at import time, so it is only reachable through
:func:`ptools.portage_adapter.get_portage_backend`.
"""

from typing import Any

import portage  # type: ignore[import-not-found]
from portage.dep import Atom  # type: ignore[import-not-found]
from portage.exception import (  # type: ignore[import-not-found]
    InvalidAtom,
    PortageException,
)

from ptools.domain import ResolvedPackage
from ptools.errors import AmbiguousPackageError, PackageNotFoundError, PortageIntegrationError


class RealPortageBackend:
    def __init__(self) -> None:
        self.portdb: Any = portage.portdb
        self.vardb: Any = portage.db[portage.root]["vartree"].dbapi
        self.settings: Any = portage.settings

    def _resolve_unqualified(self, name: str) -> str:
        matches = sorted({cp for cp in self.portdb.cp_all() if cp.split("/")[-1] == name})
        if not matches:
            matches = sorted({cp for cp in self.vardb.cp_all() if cp.split("/")[-1] == name})
        if not matches:
            raise PackageNotFoundError(f"package not found: {name}")
        if len(matches) > 1:
            raise AmbiguousPackageError(
                f"ambiguous package name: {name} (matches {', '.join(matches)})",
                matches=tuple(matches),
            )
        return str(matches[0])

    def resolve(self, request: str) -> ResolvedPackage:
        if not request.strip():
            raise PackageNotFoundError("empty package request")

        try:
            if "/" in request:
                atom = Atom(request, allow_wildcard=False)
            else:
                atom = Atom(self._resolve_unqualified(request))
        except InvalidAtom as exc:
            raise PackageNotFoundError(f"invalid package atom: {request} ({exc})") from exc

        try:
            repo_matches = list(self.portdb.match(atom))
            installed_matches = list(self.vardb.match(atom))
        except Exception as exc:  # portage raises a wide range of its own errors
            raise PortageIntegrationError(f"portage lookup failed for {request}: {exc}") from exc

        if not repo_matches and not installed_matches:
            raise PackageNotFoundError(f"package not found: {request}")

        # Always take the cpv from the match: portage sorts matches by version,
        # and Atom.cpv is the *cp* for an unversioned atom, not a real cpv.
        best = repo_matches[-1] if repo_matches else installed_matches[-1]
        return ResolvedPackage(
            atom=str(atom),
            cp=str(atom.cp),
            cpv=str(best),
            installed_versions=tuple(installed_matches),
            repository_versions=tuple(repo_matches),
        )

    def atom_cp(self, atom: str) -> str | None:
        """The cp a config-file atom refers to, or None if unparsable.

        Parsing goes through portage's Atom, never by hand. Wildcard and
        repo-qualified atoms parse; a wildcard cp simply never equals a real
        one, so those entries are not attributed to any package.
        """
        try:
            return str(Atom(atom, allow_wildcard=True, allow_repo=True).cp)
        except InvalidAtom:
            return None

    def _aux(self, db: Any, cpv: str, key: str) -> tuple[str, ...]:
        try:
            return tuple(db.aux_get(cpv, [key])[0].split())
        except KeyError:
            return ()
        except PortageException as exc:
            raise PortageIntegrationError(f"cannot read {key} for {cpv}: {exc}") from exc

    def _db_for(self, resolved: ResolvedPackage) -> Any:
        """The db that actually carries ``resolved.cpv``.

        A package that is installed but no longer in the tree resolves its cpv out
        of the vdb; asking portdb to look that cpv up raises instead of returning
        metadata. Every metadata read must go through here.
        """
        return self.portdb if resolved.repository_versions else self.vardb

    def effective_use(self, atom: str) -> tuple[str, ...]:
        resolved = self.resolve(atom)
        if not resolved.cpv:
            return ()
        settings = portage.config(clone=self.settings)
        try:
            settings.setcpv(resolved.cpv, mydb=self._db_for(resolved))
        except Exception as exc:
            raise PortageIntegrationError(f"cannot evaluate USE for {atom}: {exc}") from exc
        return tuple(sorted(settings.get("PORTAGE_USE", settings.get("USE", "")).split()))

    def installed_use(self, atom: str) -> tuple[str, ...]:
        resolved = self.resolve(atom)
        if not resolved.installed_versions:
            return ()
        return self._aux(self.vardb, resolved.installed_versions[-1], "USE")

    def iuse(self, atom: str) -> tuple[str, ...]:
        resolved = self.resolve(atom)
        if not resolved.cpv:
            return ()
        return self._aux(self._db_for(resolved), resolved.cpv, "IUSE")

    def keywords(self, atom: str) -> tuple[str, ...]:
        resolved = self.resolve(atom)
        if not resolved.cpv:
            return ()
        return self._aux(self._db_for(resolved), resolved.cpv, "KEYWORDS")

    def get_setting(self, key: str, default: str = "") -> str:
        value = self.settings.get(key, default)
        return str(value) if value is not None else default
