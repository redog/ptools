import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ptools.domain import ConfigMutation, FileChange
from ptools.errors import InvalidConfigError


@dataclass
class ConfigStore:
    dry_run: bool = False

    def apply_mutation(self, file_path: Path, mutation: ConfigMutation) -> FileChange | None:
        """
        Parses the config file, modifies or adds the entry for the specific atom,
        and writes it back atomically.
        """
        content = ""
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

        lines = content.splitlines(keepends=True)
        new_lines = []
        found = False

        for line in lines:
            stripped = line.strip()
            # Preserve empty lines and comments
            if not stripped or stripped.startswith("#"):
                new_lines.append(line)
                continue

            parts = stripped.split()
            if not parts:
                new_lines.append(line)
                continue

            entry_atom = parts[0]
            if entry_atom == mutation.atom:
                if found:
                    raise InvalidConfigError(
                        f"Duplicate atom {mutation.atom} found in {file_path}. Please merge duplicates."
                    )
                found = True

                # Apply mutation
                current_values = set(parts[1:])
                for value in mutation.values:
                    if mutation.operation == "set":
                        if value.startswith("-") and value[1:] in current_values:
                            current_values.remove(value[1:])
                        elif not value.startswith("-") and f"-{value}" in current_values:
                            current_values.remove(f"-{value}")
                        current_values.add(value)
                    elif mutation.operation == "unset":
                        # Remove both 'flag' and '-flag'
                        clean_value = value.removeprefix("-")
                        current_values.discard(clean_value)
                        current_values.discard(f"-{clean_value}")

                if current_values:
                    sorted_values = sorted(current_values)
                    new_line = f"{entry_atom} {' '.join(sorted_values)}\n"
                    new_lines.append(new_line)
                # If no values left, the line is removed completely
            else:
                new_lines.append(line)

        if not found and mutation.operation == "set":
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] = new_lines[-1] + "\n"
            sorted_values = sorted(set(mutation.values))
            new_lines.append(f"{mutation.atom} {' '.join(sorted_values)}\n")

        new_content = "".join(new_lines)

        if content == new_content:
            return None

        change = FileChange(path=file_path, before=content, after=new_content)

        if not self.dry_run:
            self._write_atomic(file_path, new_content)

        return change

    def _write_atomic(self, file_path: Path, content: str) -> None:
        if os.geteuid() != 0 and str(file_path).startswith("/etc/"):
            import subprocess

            fd, temp_path = tempfile.mkstemp(prefix=".ptools-tmp-")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())

                subprocess.run(["sudo", "mkdir", "-p", str(file_path.parent)], check=True)
                subprocess.run(["sudo", "mv", temp_path, str(file_path)], check=True)
                subprocess.run(["sudo", "chmod", "644", str(file_path)], check=True)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            return

        file_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=file_path.parent, prefix=".ptools-tmp-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

            if file_path.exists():
                stat = file_path.stat()
                os.chmod(temp_path, stat.st_mode)
                os.chown(temp_path, stat.st_uid, stat.st_gid)
            else:
                os.chmod(temp_path, 0o644)

            os.replace(temp_path, file_path)
        except Exception:
            os.remove(temp_path)
            raise
