from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class PackageRequest:
    raw: str
    exact: bool


@dataclass(frozen=True)
class ResolvedPackage:
    atom: str
    cp: str
    cpv: str | None
    installed_versions: tuple[str, ...]
    repository_versions: tuple[str, ...]


@dataclass(frozen=True)
class ConfigMutation:
    operation: Literal["set", "unset"]
    atom: str
    values: tuple[str, ...]


from pathlib import Path


@dataclass(frozen=True)
class FileChange:
    path: Path
    before: str
    after: str
