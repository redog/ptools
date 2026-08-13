"""Portage backend protocol, the test double, and the backend factory.

The real implementation lives in :mod:`ptools.portage_real` and is imported
lazily so that this module (and everything above it) stays importable on hosts
without a system ``portage``.
"""

import re
from typing import Any, Protocol

from ptools.domain import ResolvedPackage
from ptools.errors import AmbiguousPackageError, PackageNotFoundError, PortageIntegrationError


class PortageBackend(Protocol):
    def resolve(self, request: str) -> ResolvedPackage: ...

    def atom_cp(self, atom: str) -> str | None: ...

    def effective_use(self, atom: str) -> tuple[str, ...]: ...

    def installed_use(self, atom: str) -> tuple[str, ...]: ...

    def iuse(self, atom: str) -> tuple[str, ...]: ...

    def keywords(self, atom: str) -> tuple[str, ...]: ...

    def get_setting(self, key: str, default: str = "") -> str: ...


# Mock-only: the real backend never parses atoms by hand, it asks portage.
_MOCK_VERSION_RE = re.compile(r"-(\d[^-]*(?:-r\d+)?)$")


class MockPortageBackend:
    """A hand-rolled backend for testing without a real Gentoo installation.

    Package data is a mapping of ``cat/pkg`` to the keys ``repo_versions``,
    ``installed_versions``, ``iuse``, ``effective_use``, ``installed_use`` and
    ``keywords``.
    """

    def __init__(self, packages: dict[str, dict[str, Any]], settings: dict[str, str] | None = None):
        self.packages = packages
        self.settings = {"PORTAGE_CONFIGROOT": "/", "ARCH": "amd64", **(settings or {})}

    def _split_request(self, request: str) -> tuple[str, str | None]:
        """Return ``(cp_or_name, version)`` for a mock request string."""
        stripped = request.lstrip("=~<>!")
        match = _MOCK_VERSION_RE.search(stripped)
        if match:
            return stripped[: match.start()], match.group(1)
        return stripped, None

    def resolve(self, request: str) -> ResolvedPackage:
        if not request:
            raise PackageNotFoundError("empty package request")

        name, version = self._split_request(request)

        if "/" in name:
            matches = [cp for cp in self.packages if cp == name]
        else:
            matches = [cp for cp in self.packages if cp.split("/")[-1] == name]

        if not matches:
            raise PackageNotFoundError(f"package not found: {request}")
        if len(matches) > 1:
            raise AmbiguousPackageError(
                f"ambiguous package name: {request} (matches {', '.join(sorted(matches))})",
                matches=tuple(sorted(matches)),
            )

        cp = matches[0]
        data = self.packages[cp]
        repo_versions = tuple(data.get("repo_versions", ()))
        installed_versions = tuple(data.get("installed_versions", ()))

        if version is not None and version not in repo_versions + installed_versions:
            raise PackageNotFoundError(f"package not found: {request}")

        if version is not None:
            cpv: str | None = f"{cp}-{version}"
        elif repo_versions:
            cpv = f"{cp}-{repo_versions[-1]}"
        elif installed_versions:
            cpv = f"{cp}-{installed_versions[-1]}"
        else:
            cpv = None

        return ResolvedPackage(
            atom=request,
            cp=cp,
            cpv=cpv,
            installed_versions=tuple(f"{cp}-{v}" for v in installed_versions),
            repository_versions=tuple(f"{cp}-{v}" for v in repo_versions),
        )

    def atom_cp(self, atom: str) -> str | None:
        """The cp a config-file atom refers to, or None if unparsable."""
        base = atom.split(":", 1)[0].split("::", 1)[0]
        name, _version = self._split_request(base)
        return name if "/" in name else None

    def _field(self, atom: str, key: str) -> tuple[str, ...]:
        resolved = self.resolve(atom)
        return tuple(self.packages[resolved.cp].get(key, ()))

    def effective_use(self, atom: str) -> tuple[str, ...]:
        return self._field(atom, "effective_use")

    def installed_use(self, atom: str) -> tuple[str, ...]:
        return self._field(atom, "installed_use")

    def iuse(self, atom: str) -> tuple[str, ...]:
        return self._field(atom, "iuse")

    def keywords(self, atom: str) -> tuple[str, ...]:
        return self._field(atom, "keywords")

    def get_setting(self, key: str, default: str = "") -> str:
        return self.settings.get(key, default)


def get_portage_backend() -> PortageBackend:
    """Return the real portage backend, or fail with exit code 7.

    Importing ``portage`` reads the whole configuration, so a broken make.conf
    or profile raises out of the import itself - as a portage exception, not an
    ImportError. Constructing the backend can fail the same way (``portage.db``
    has no entry for an unexpected ROOT). Both are portage integration failures
    and must land on exit 7 rather than escaping as a traceback.
    """
    try:
        from ptools.portage_real import RealPortageBackend
    except ImportError as exc:
        raise PortageIntegrationError(f"portage Python API not available: {exc}") from exc
    except Exception as exc:
        raise PortageIntegrationError(f"portage configuration failed to load: {exc}") from exc

    try:
        return RealPortageBackend()
    except Exception as exc:
        raise PortageIntegrationError(f"cannot initialise the portage backend: {exc}") from exc
