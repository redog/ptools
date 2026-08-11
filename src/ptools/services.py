"""Service layer: everything the CLIs do, minus argument parsing and output."""

from pathlib import Path
from typing import Any

from ptools.config_store import ConfigStore
from ptools.domain import ConfigMutation, Operation
from ptools.errors import PackageNotFoundError
from ptools.portage_adapter import PortageBackend

#: Marker filename for "managed by this tool set", inside the directory layout.
MANAGED_NAME = "ptools"


def use_target(config_root: Path) -> Path:
    return config_root / "package.use" / MANAGED_NAME


def keyword_target(config_root: Path) -> Path:
    return config_root / "package.accept_keywords" / MANAGED_NAME


class _Service:
    def __init__(self, backend: PortageBackend, store: ConfigStore, config_root: Path):
        self.backend = backend
        self.store = store
        self.config_root = config_root

    def target_atom(self, atom: str, exact: bool = False) -> str:
        """The atom to write to config: ``=cat/pkg-ver`` with --exact, else ``cat/pkg``."""
        package = self.backend.resolve(atom)
        if not exact:
            return package.cp
        if not package.cpv:
            raise PackageNotFoundError(f"no version available to pin for {atom}")
        return f"={package.cpv}"


class ReadOnlyService(_Service):
    def resolve(self, atom: str) -> dict[str, Any]:
        package = self.backend.resolve(atom)
        return {
            "atom": package.atom,
            "cp": package.cp,
            "cpv": package.cpv,
            "installed": list(package.installed_versions),
            "repository": list(package.repository_versions),
        }

    def use_show(self, atom: str, exact: bool = False) -> dict[str, Any]:
        package = self.backend.resolve(atom)
        managed_atom = self.target_atom(atom, exact)
        target = use_target(self.config_root)
        return {
            "operation": "use.show",
            "atom": managed_atom,
            "cp": package.cp,
            "cpv": package.cpv,
            "installed": list(package.installed_versions),
            "iuse": list(self.backend.iuse(atom)),
            "effective": list(self.backend.effective_use(atom)),
            "installed_use": list(self.backend.installed_use(atom)),
            "managed": list(self.store.read_values(target, managed_atom)),
            "target": str(target),
        }

    def keyword_show(self, atom: str, exact: bool = False) -> dict[str, Any]:
        package = self.backend.resolve(atom)
        managed_atom = self.target_atom(atom, exact)
        target = keyword_target(self.config_root)
        legacy = self.config_root / "package.keywords"
        return {
            "operation": "keyword.show",
            "atom": managed_atom,
            "cp": package.cp,
            "cpv": package.cpv,
            "arch": self.backend.get_setting("ARCH", ""),
            "installed": list(package.installed_versions),
            "keywords": list(self.backend.keywords(atom)),
            "managed": list(self.store.read_values(target, managed_atom)),
            "target": str(target),
            "legacy_package_keywords": legacy.exists(),
        }


class MutationService(_Service):
    def apply_use(
        self, operation: Operation, atom: str, flags: tuple[str, ...], exact: bool = False
    ) -> dict[str, Any]:
        return self._apply("use", use_target(self.config_root), operation, atom, flags, exact)

    def apply_keyword(
        self, operation: Operation, atom: str, keywords: tuple[str, ...], exact: bool = False
    ) -> dict[str, Any]:
        return self._apply(
            "keyword", keyword_target(self.config_root), operation, atom, keywords, exact
        )

    def _apply(
        self,
        domain: str,
        target: Path,
        operation: Operation,
        atom: str,
        values: tuple[str, ...],
        exact: bool,
    ) -> dict[str, Any]:
        managed_atom = self.target_atom(atom, exact)
        result = self.store.apply_mutation(
            target, ConfigMutation(operation=operation, atom=managed_atom, values=values)
        )
        return {
            "operation": f"{domain}.{operation}",
            "atom": managed_atom,
            "target": str(target),
            "added": list(result.added),
            "removed": list(result.removed),
            "changed": result.changed,
            "dry_run": self.store.dry_run,
        }
