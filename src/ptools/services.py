"""Service layer: everything the CLIs do, minus argument parsing and output."""

import configparser
import re
from pathlib import Path
from typing import Any

from ptools.config_store import ConfigStore, stack_values
from ptools.domain import ConfigMutation, Operation
from ptools.errors import (
    AmbiguousTargetError,
    InvalidConfigError,
    PackageNotFoundError,
    PtoolsError,
    UsageError,
)
from ptools.portage_adapter import PortageBackend

#: A plain filename inside package.use/ or package.accept_keywords/: no path
#: separators, no leading dot (portage skips dotfiles).
TARGET_FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+@:-]*$")


def validate_target_filename(name: str, exc: type[PtoolsError] = UsageError) -> str:
    """A plain filename usable inside the managed directory, or raise ``exc``."""
    if not TARGET_FILE_RE.match(name):
        raise exc(f"invalid target filename: {name!r} (plain filename, no path, no leading dot)")
    return name


#: Marker filename for "managed by this tool set", inside the directory layout.
#: The default write target for new atoms unless ptools.conf says otherwise.
MANAGED_NAME = "ptools"

#: Optional configuration for ptools itself, beside the portage config it
#: describes ([use] / [keywords] sections, ``default-file`` key each).
CONFIG_NAME = "ptools.conf"


def use_dir(config_root: Path) -> Path:
    return config_root / "package.use"


def keyword_dir(config_root: Path) -> Path:
    return config_root / "package.accept_keywords"


def use_target(config_root: Path) -> Path:
    return use_dir(config_root) / MANAGED_NAME


def keyword_target(config_root: Path) -> Path:
    return keyword_dir(config_root) / MANAGED_NAME


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

    def keyword_implicit(self) -> tuple[str, ...]:
        """What a bare atom means in package.accept_keywords: accept ``~ARCH``."""
        arch = self.backend.get_setting("ARCH", "")
        return (f"~{arch}",) if arch else ()

    def default_file(self, section: str) -> str:
        """The write target for atoms with no existing entry, per ptools.conf."""
        path = self.config_root / CONFIG_NAME
        if not path.exists():
            return MANAGED_NAME
        parser = configparser.ConfigParser()
        try:
            parser.read_string(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError as exc:
            raise InvalidConfigError(f"{path} is not valid UTF-8: {exc}") from exc
        except OSError as exc:
            raise InvalidConfigError(f"cannot read {path}: {exc.strerror}") from exc
        except configparser.Error as exc:
            raise InvalidConfigError(f"cannot parse {path}: {exc}") from exc
        name = parser.get(section, "default-file", fallback=MANAGED_NAME).strip()
        return validate_target_filename(name, InvalidConfigError)

    def resolve_target(
        self,
        directory: Path,
        managed_atom: str,
        implicit: tuple[str, ...],
        chosen_file: str | None,
        section: str,
    ) -> tuple[Path, list[str]]:
        """Follow the atom: the file to mutate, plus other files carrying it.

        --file wins outright; else the single file already holding the atom;
        several holders without --file is ambiguous; a new atom goes to the
        configured default file.
        """
        entries = self.store.scan_entries(directory, managed_atom, implicit)
        names = [name for name, _ in entries]
        if chosen_file is not None:
            return directory / chosen_file, [name for name in names if name != chosen_file]
        if len(names) == 1:
            return directory / names[0], []
        if len(names) > 1:
            raise AmbiguousTargetError(
                f"{managed_atom} has entries in more than one file under {directory}: "
                f"{', '.join(names)}; pass --file NAME to choose one"
            )
        return directory / self.default_file(section), []


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

    def _managed_state(
        self, directory: Path, managed_atom: str, implicit: tuple[str, ...], section: str
    ) -> dict[str, Any]:
        """The atom's entries across every file, plus the resolved write target.

        ``target`` is None when a plain mutation would be ambiguous (entries in
        several files and no --file to pick one).
        """
        entries = self.store.scan_entries(directory, managed_atom, implicit)
        target: str | None
        if len(entries) == 1:
            target = str(directory / entries[0][0])
        elif not entries:
            target = str(directory / self.default_file(section))
        else:
            target = None
        return {
            "managed": list(stack_values(entries)),
            "entries": [{"file": name, "values": list(values)} for name, values in entries],
            "target": target,
        }

    def use_show(self, atom: str, exact: bool = False) -> dict[str, Any]:
        package = self.backend.resolve(atom)
        managed_atom = self.target_atom(atom, exact)
        return {
            "operation": "use.show",
            "atom": managed_atom,
            "cp": package.cp,
            "cpv": package.cpv,
            "installed": list(package.installed_versions),
            "iuse": list(self.backend.iuse(atom)),
            "effective": list(self.backend.effective_use(atom)),
            "installed_use": list(self.backend.installed_use(atom)),
            **self._managed_state(use_dir(self.config_root), managed_atom, (), "use"),
        }

    def keyword_show(self, atom: str, exact: bool = False) -> dict[str, Any]:
        package = self.backend.resolve(atom)
        managed_atom = self.target_atom(atom, exact)
        legacy = self.config_root / "package.keywords"
        return {
            "operation": "keyword.show",
            "atom": managed_atom,
            "cp": package.cp,
            "cpv": package.cpv,
            "arch": self.backend.get_setting("ARCH", ""),
            "installed": list(package.installed_versions),
            "keywords": list(self.backend.keywords(atom)),
            **self._managed_state(
                keyword_dir(self.config_root), managed_atom, self.keyword_implicit(), "keywords"
            ),
            "legacy_package_keywords": legacy.exists(),
        }


class MutationService(_Service):
    def apply_use(
        self,
        operation: Operation,
        atom: str,
        flags: tuple[str, ...],
        exact: bool = False,
        chosen_file: str | None = None,
    ) -> dict[str, Any]:
        return self._apply(
            "use", use_dir(self.config_root), operation, atom, flags, exact, (), chosen_file
        )

    def apply_keyword(
        self,
        operation: Operation,
        atom: str,
        keywords: tuple[str, ...],
        exact: bool = False,
        chosen_file: str | None = None,
    ) -> dict[str, Any]:
        return self._apply(
            "keyword",
            keyword_dir(self.config_root),
            operation,
            atom,
            keywords,
            exact,
            self.keyword_implicit(),
            chosen_file,
        )

    def _apply(
        self,
        domain: str,
        directory: Path,
        operation: Operation,
        atom: str,
        values: tuple[str, ...],
        exact: bool,
        implicit: tuple[str, ...],
        chosen_file: str | None,
    ) -> dict[str, Any]:
        managed_atom = self.target_atom(atom, exact)
        section = "use" if domain == "use" else "keywords"
        target, also_in = self.resolve_target(
            directory, managed_atom, implicit, chosen_file, section
        )
        result = self.store.apply_mutation(
            target,
            ConfigMutation(operation=operation, atom=managed_atom, values=values),
            implicit=implicit,
        )
        return {
            "operation": f"{domain}.{operation}",
            "atom": managed_atom,
            "target": str(target),
            "added": list(result.added),
            "removed": list(result.removed),
            "changed": result.changed,
            "dry_run": self.store.dry_run,
            "also_in": also_in,
        }


class InitService(_Service):
    """``--init``: discover the layout and write <config-root>/ptools.conf."""

    def _suggest(self, directory: Path) -> str:
        names = [name for name, _ in _scannable_files(directory)]
        if "default" in names:
            return "default"
        if len(names) == 1:
            return names[0]
        return MANAGED_NAME

    def run(self) -> dict[str, Any]:
        path = self.config_root / CONFIG_NAME
        if path.exists():
            raise InvalidConfigError(
                f"{path} already exists; edit it directly (or remove it and re-run --init)"
            )
        use_default = self._suggest(use_dir(self.config_root))
        keyword_default = self._suggest(keyword_dir(self.config_root))
        content = (
            "# Written by --init; edit freely. default-file names the file inside\n"
            "# package.use/ or package.accept_keywords/ that receives NEW entries;\n"
            "# existing entries are edited in whichever file already holds them.\n"
            f"[use]\ndefault-file = {use_default}\n\n"
            f"[keywords]\ndefault-file = {keyword_default}\n"
        )
        if not self.store.dry_run:
            self.store.write_atomic(path, content)
        return {
            "operation": "init",
            "target": str(path),
            "use_default": use_default,
            "keywords_default": keyword_default,
            "changed": True,
            "dry_run": self.store.dry_run,
        }


def _scannable_files(directory: Path) -> list[tuple[str, Path]]:
    if not directory.is_dir():
        return []
    return [
        (path.name, path)
        for path in sorted(directory.iterdir())
        if not path.name.startswith(".") and path.is_file()
    ]
