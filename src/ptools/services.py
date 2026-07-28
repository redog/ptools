from typing import Any

from ptools.domain import ResolvedPackage
from ptools.portage_adapter import PortageBackend


class ReadOnlyService:
    def __init__(self, backend: PortageBackend):
        self.backend = backend

    def resolve(self, atom: str) -> ResolvedPackage:
        return self.backend.resolve(atom)

    def versions(self, atom: str) -> dict[str, Any]:
        pkg = self.resolve(atom)
        return {
            "atom": pkg.atom,
            "cp": pkg.cp,
            "installed": list(pkg.installed_versions),
            "repository": list(pkg.repository_versions),
        }

    def use_show(self, atom: str) -> dict[str, Any]:
        pkg = self.resolve(atom)
        iuse = self.backend.iuse(pkg.atom)
        effective = self.backend.effective_use(pkg.atom)
        installed = self.backend.installed_use(pkg.atom)

        return {
            "atom": pkg.atom,
            "cp": pkg.cp,
            "iuse": list(iuse),
            "effective": list(effective),
            "installed": list(installed),
        }

    def keyword_show(self, atom: str) -> dict[str, Any]:
        # Simple for now, just resolves and shows the versions, as keyword state
        # is mostly about what's in accept_keywords and the arch.
        pkg = self.resolve(atom)
        return {
            "atom": pkg.atom,
            "cp": pkg.cp,
            "note": "Keyword state analysis deferred to config inspection.",
        }


from pathlib import Path

from ptools.config_store import ConfigStore
from ptools.domain import ConfigMutation


class MutationService:
    def __init__(self, backend: PortageBackend, store: ConfigStore, config_root: Path):
        self.backend = backend
        self.store = store
        self.config_root = config_root

    def resolve_atom(self, atom: str, exact: bool = False) -> str:
        pkg = self.backend.resolve(atom)
        from ptools.errors import PackageNotFoundError

        if exact:
            if not pkg.cpv:
                raise PackageNotFoundError(f"Cannot resolve exact version for {atom}")
            return f"={pkg.cpv}"
        return pkg.cp

    def apply_use(
        self, operation: str, atom: str, flags: tuple[str, ...], exact: bool = False
    ) -> dict[str, Any]:
        resolved = self.resolve_atom(atom, exact)
        target = self.config_root / "package.use/ptools"
        mutation = ConfigMutation(operation=operation, atom=resolved, values=flags)  # type: ignore

        change = self.store.apply_mutation(target, mutation)

        return {
            "operation": f"use.{operation}",
            "atom": resolved,
            "target": str(target),
            "added": list(flags) if operation == "set" else [],
            "removed": list(flags) if operation == "unset" else [],
            "changed": change is not None,
            "dry_run": self.store.dry_run,
            "diff_before": change.before if change else None,
            "diff_after": change.after if change else None,
        }

    def apply_keyword(
        self, operation: str, atom: str, keywords: tuple[str, ...], exact: bool = False
    ) -> dict[str, Any]:
        resolved = self.resolve_atom(atom, exact)
        target = self.config_root / "package.accept_keywords/ptools"
        mutation = ConfigMutation(operation=operation, atom=resolved, values=keywords)  # type: ignore

        change = self.store.apply_mutation(target, mutation)

        return {
            "operation": f"keyword.{operation}",
            "atom": resolved,
            "target": str(target),
            "added": list(keywords) if operation == "set" else [],
            "removed": list(keywords) if operation == "unset" else [],
            "changed": change is not None,
            "dry_run": self.store.dry_run,
            "diff_before": change.before if change else None,
            "diff_after": change.after if change else None,
        }
