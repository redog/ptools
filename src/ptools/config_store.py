"""Read/modify/write the ptools-managed portage config files.

Rules this module enforces (build_PROMPT.md §5):

* comments, blank lines, and every line for another atom survive byte-for-byte;
* duplicate atoms are an error unless the caller opts into merging;
* the target is replaced atomically, preserving mode and ownership;
* an interrupted write never leaves a partial or truncated target;
* no privilege escalation - an unwritable target is a permission error.
"""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ptools.domain import ConfigMutation, MutationResult
from ptools.errors import InvalidConfigError, PermissionDeniedError, WriteError


@dataclass(frozen=True)
class ParsedLine:
    """One physical line, split into the parts we may need to re-render."""

    raw: str
    indent: str
    atom: str | None
    values: tuple[str, ...]
    comment: str


def parse_line(raw: str) -> ParsedLine:
    body, sep, comment = raw.partition("#")
    indent = body[: len(body) - len(body.lstrip())]
    tokens = body.split()
    return ParsedLine(
        raw=raw,
        indent=indent,
        atom=tokens[0] if tokens else None,
        values=tuple(tokens[1:]),
        comment=f"{sep}{comment}".rstrip("\r\n") if sep else "",
    )


def render_line(line: ParsedLine, values: tuple[str, ...]) -> str:
    rendered = f"{line.indent}{line.atom} {' '.join(values)}".rstrip()
    if line.comment:
        rendered = f"{rendered} {line.comment}"
    return f"{rendered}\n"


def parse_file(content: str) -> list[ParsedLine]:
    return [parse_line(raw) for raw in content.splitlines(keepends=True)]


def apply_set(values: tuple[str, ...], tokens: tuple[str, ...]) -> tuple[str, ...]:
    """Add each token, dropping the token it contradicts (``lua`` vs ``-lua``)."""
    result = list(values)
    for token in tokens:
        base = token.removeprefix("-")
        counterpart = base if token.startswith("-") else f"-{base}"
        if counterpart in result:
            result.remove(counterpart)
        if token not in result:
            result.append(token)
    return tuple(result)


def apply_unset(values: tuple[str, ...], tokens: tuple[str, ...]) -> tuple[str, ...]:
    """Drop both the plain and the negated form of each token."""
    drop = set()
    for token in tokens:
        base = token.removeprefix("-")
        drop.update({base, f"-{base}"})
    return tuple(value for value in values if value not in drop)


@dataclass
class ConfigStore:
    dry_run: bool = False
    merge_duplicates: bool = False

    # -- reading ---------------------------------------------------------

    def read(self, file_path: Path) -> str:
        try:
            return file_path.read_text(encoding="utf-8") if file_path.exists() else ""
        except PermissionError as exc:
            raise PermissionDeniedError(f"cannot read {file_path}: {exc.strerror}") from exc
        except UnicodeDecodeError as exc:
            raise InvalidConfigError(f"{file_path} is not valid UTF-8: {exc}") from exc
        except OSError as exc:
            raise InvalidConfigError(f"cannot read {file_path}: {exc.strerror}") from exc

    def read_values(
        self, file_path: Path, atom: str, implicit: tuple[str, ...] = ()
    ) -> tuple[str, ...]:
        """Values currently managed for ``atom``; empty if it has no entry.

        ``implicit`` is what a bare (valueless) entry means in this file: in
        package.accept_keywords a lone atom accepts ``~ARCH`` (verified against
        real portage, docs/gentoo-validation.md §10), while in package.use a
        bare entry means nothing and ``implicit`` stays empty.
        """
        lines = parse_file(self.read(file_path))
        values: list[str] = []
        for index in self._select(lines, atom, file_path):
            values.extend(lines[index].values or implicit)
        return tuple(dict.fromkeys(values))

    def _select(self, lines: list[ParsedLine], atom: str, file_path: Path) -> list[int]:
        indexes = [i for i, line in enumerate(lines) if line.atom == atom]
        if len(indexes) > 1 and not self.merge_duplicates:
            raise InvalidConfigError(
                f"duplicate entries for {atom} in {file_path} "
                f"(lines {', '.join(str(i + 1) for i in indexes)}); "
                f"re-run with --merge-duplicates to combine them"
            )
        return indexes

    # -- mutating --------------------------------------------------------

    def apply_mutation(
        self, file_path: Path, mutation: ConfigMutation, implicit: tuple[str, ...] = ()
    ) -> MutationResult:
        before = self.read(file_path)
        lines = parse_file(before)
        selected = self._select(lines, mutation.atom, file_path)

        old_values: tuple[str, ...] = ()
        for index in selected:
            if not lines[index].values and not implicit:
                raise InvalidConfigError(
                    f"entry for {mutation.atom} in {file_path} line {index + 1} has no values"
                )
            old_values += lines[index].values or implicit
        old_values = tuple(dict.fromkeys(old_values))

        if mutation.operation == "set":
            new_values = apply_set(old_values, mutation.values)
        else:
            new_values = apply_unset(old_values, mutation.values)

        rendered = [line.raw for line in lines]
        if selected and not (len(selected) == 1 and new_values == old_values):
            keep = selected[0]
            if new_values:
                rendered[keep] = render_line(lines[keep], new_values)
            else:
                rendered[keep] = ""
            for index in selected[1:]:
                rendered[index] = ""
        elif not selected and new_values:
            if rendered and not rendered[-1].endswith("\n"):
                rendered[-1] += "\n"
            rendered.append(f"{mutation.atom} {' '.join(new_values)}\n")

        after = "".join(rendered)
        result = MutationResult(
            path=file_path,
            before=before,
            after=after,
            added=tuple(v for v in new_values if v not in old_values),
            removed=tuple(v for v in old_values if v not in new_values),
        )

        if result.changed and not self.dry_run:
            self.write_atomic(file_path, after)
        return result

    # -- writing ---------------------------------------------------------

    def write_atomic(self, file_path: Path, content: str) -> None:
        if file_path.is_symlink():
            raise WriteError(f"refusing to write through a symlink: {file_path}")

        parent = file_path.parent
        if parent.exists() and not parent.is_dir():
            raise InvalidConfigError(
                f"{parent} is a regular file; ptools requires the directory layout "
                f"(convert it with: mv {parent} {parent}.tmp && mkdir {parent} && "
                f"mv {parent}.tmp {parent}/00-local)"
            )

        try:
            parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(dir=parent, prefix=".ptools-")
        except PermissionError as exc:
            raise PermissionDeniedError(
                f"cannot write to {parent}: {exc.strerror}; re-run as root"
            ) from exc
        except OSError as exc:
            raise WriteError(f"cannot prepare {parent}: {exc.strerror}") from exc

        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            self._preserve_metadata(file_path, temp_path)
            os.replace(temp_path, file_path)
        except PermissionError as exc:
            temp_path.unlink(missing_ok=True)
            raise PermissionDeniedError(
                f"cannot replace {file_path}: {exc.strerror}; re-run as root"
            ) from exc
        except OSError as exc:
            temp_path.unlink(missing_ok=True)
            raise WriteError(f"cannot write {file_path}: {exc.strerror}") from exc
        except BaseException:
            # Interrupted part-way: the candidate is discarded, the target is
            # untouched because os.replace() never ran.
            temp_path.unlink(missing_ok=True)
            raise

    def _preserve_metadata(self, file_path: Path, temp_path: Path) -> None:
        if file_path.exists():
            stat = file_path.stat()
            os.chmod(temp_path, stat.st_mode & 0o7777 & ~0o002)
            if os.geteuid() == 0:
                os.chown(temp_path, stat.st_uid, stat.st_gid)
        else:
            os.chmod(temp_path, 0o644)
