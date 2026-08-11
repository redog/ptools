from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Operation = Literal["set", "unset"]


@dataclass(frozen=True)
class ResolvedPackage:
    atom: str
    cp: str
    cpv: str | None
    installed_versions: tuple[str, ...]
    repository_versions: tuple[str, ...]


@dataclass(frozen=True)
class ConfigMutation:
    operation: Operation
    atom: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class MutationResult:
    """Outcome of applying one mutation to one managed file."""

    path: Path
    before: str
    after: str
    added: tuple[str, ...]
    removed: tuple[str, ...]

    @property
    def changed(self) -> bool:
        return self.before != self.after
