from typing import Any, Protocol

from ptools.domain import ResolvedPackage
from ptools.errors import AmbiguousPackageError, PackageNotFoundError, PortageIntegrationError


class PortageBackend(Protocol):
    def resolve(self, request: str) -> ResolvedPackage: ...

    def effective_use(self, atom: str) -> tuple[str, ...]: ...

    def installed_use(self, atom: str) -> tuple[str, ...]: ...

    def iuse(self, atom: str) -> tuple[str, ...]: ...

    def get_setting(self, key: str, default: str = "") -> str: ...


class MockPortageBackend:
    """A mock backend for testing without a real Gentoo installation."""

    def __init__(self, packages: dict[str, dict[str, Any]]):
        self.packages = packages

    def _parse_atom(self, request: str) -> tuple[str, str, str | None, bool]:
        # Very simple mock atom parser
        exact = request.startswith("=")
        clean_request = request[1:] if exact or request.startswith("~") else request

        parts = clean_request.split("/")
        if len(parts) == 2:
            cp_parts = parts[1].split("-")
            # Assuming category/package-version
            if any(char.isdigit() for char in parts[1]):
                cp = f"{parts[0]}/{cp_parts[0]}"
                cpv = clean_request
            else:
                cp = clean_request
                cpv = None
        else:
            cp = parts[0]
            cpv = None

        return clean_request, cp, cpv, exact

    def resolve(self, request: str) -> ResolvedPackage:
        _clean_request, cp, cpv, exact = self._parse_atom(request)

        matches = []
        for pkg_cp in self.packages:
            if pkg_cp == cp or ("/" not in request and pkg_cp.endswith("/" + cp)):
                matches.append(pkg_cp)

        if not matches:
            raise PackageNotFoundError(f"Package not found: {request}")

        if len(matches) > 1:
            raise AmbiguousPackageError(
                f"Ambiguous package: {request}. Matches: {', '.join(matches)}"
            )

        matched_cp = matches[0]
        pkg_data = self.packages[matched_cp]

        f"={matched_cp}-{cpv.split('-')[1]}" if cpv and exact else matched_cp
        if not exact and cpv:
            f"~{matched_cp}-{cpv.split('-')[1]}"

        return ResolvedPackage(
            atom=request,  # Preserve original
            cp=matched_cp,
            cpv=cpv if cpv else f"{matched_cp}-{pkg_data['repo_versions'][-1]}",
            installed_versions=tuple(
                f"{matched_cp}-{v}" for v in pkg_data.get("installed_versions", [])
            ),
            repository_versions=tuple(
                f"{matched_cp}-{v}" for v in pkg_data.get("repo_versions", [])
            ),
        )

    def effective_use(self, atom: str) -> tuple[str, ...]:
        res = self.resolve(atom)
        return tuple(self.packages[res.cp].get("effective_use", []))

    def installed_use(self, atom: str) -> tuple[str, ...]:
        res = self.resolve(atom)
        return tuple(self.packages[res.cp].get("installed_use", []))

    def iuse(self, atom: str) -> tuple[str, ...]:
        res = self.resolve(atom)
        return tuple(self.packages[res.cp].get("iuse", []))

    def get_setting(self, key: str, default: str = "") -> str:
        if key == "PORTAGE_CONFIGROOT":
            return "/"
        if key == "ARCH":
            return "amd64"
        return default


try:
    import portage  # type: ignore
    from portage.dep import Atom  # type: ignore

    PORTAGE_AVAILABLE = True
except ImportError:
    PORTAGE_AVAILABLE = False


class RealPortageBackend:
    """Real Gentoo portage integration"""

    def __init__(self) -> None:
        if not PORTAGE_AVAILABLE:
            raise PortageIntegrationError("Portage Python API not available")
        self.portdb = portage.portdb
        self.vardb = portage.vardb
        self.settings = portage.settings

    def _get_matches(self, request: str) -> list[str]:
        if "/" not in request:
            # Handle unqualified
            matches = []
            for cp in self.portdb.cp_all():
                if cp.split("/")[1] == request:
                    matches.append(cp)
            return matches
        return [request]

    def resolve(self, request: str) -> ResolvedPackage:
        try:
            if not request:
                raise PackageNotFoundError("Empty package request")

            try:
                atom_obj = Atom(request)
                cp = atom_obj.cp
                cpv = atom_obj.cpv
                clean_request = str(atom_obj)
            except portage.exception.InvalidAtom:
                matches = self._get_matches(request)
                if not matches:
                    raise PackageNotFoundError(f"Package not found: {request}")
                if len(matches) > 1:
                    raise AmbiguousPackageError(
                        f"Ambiguous package: {request}. Matches: {', '.join(matches)}"
                    )
                cp = matches[0]
                cpv = None
                clean_request = cp

            repo_matches = self.portdb.match(clean_request)
            installed_matches = self.vardb.match(clean_request)

            if not repo_matches and not installed_matches:
                raise PackageNotFoundError(f"Package not found: {request}")

            return ResolvedPackage(
                atom=clean_request,
                cp=cp,
                cpv=cpv if cpv else repo_matches[-1] if repo_matches else installed_matches[-1],
                installed_versions=tuple(installed_matches),
                repository_versions=tuple(repo_matches),
            )
        except (PackageNotFoundError, AmbiguousPackageError):
            raise
        except Exception as e:
            raise PortageIntegrationError(f"Portage error: {e!s}")

    def effective_use(self, atom: str) -> tuple[str, ...]:
        res = self.resolve(atom)
        if not res.cpv:
            return ()
        self.settings.setcpv(res.cpv)
        return tuple(self.settings["PORTAGE_USE"].split())

    def installed_use(self, atom: str) -> tuple[str, ...]:
        res = self.resolve(atom)
        if not res.cpv:
            return ()
        try:
            return tuple(self.vardb.aux_get(res.cpv, ["USE"])[0].split())
        except KeyError:
            return ()

    def iuse(self, atom: str) -> tuple[str, ...]:
        res = self.resolve(atom)
        if not res.cpv:
            return ()
        try:
            return tuple(self.portdb.aux_get(res.cpv, ["IUSE"])[0].split())
        except KeyError:
            return ()

    def get_setting(self, key: str, default: str = "") -> str:
        return str(self.settings.get(key, default))


def get_portage_backend() -> PortageBackend:
    if PORTAGE_AVAILABLE:
        return RealPortageBackend()
    # Provide an empty mock if portage isn't available and this is called in a real run
    return MockPortageBackend({})
