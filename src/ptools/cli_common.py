"""Shared runtime for the first-class ``puse`` and ``pkw`` commands.

Both commands are flat and terse: ``cmd [OPTIONS] PACKAGE [TOKEN ...]``. They
call the service layer directly - there is no umbrella command and nothing here
ever spawns a subprocess.
"""

import argparse
import json
import os
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, NoReturn

from ptools.errors import AmbiguousPackageError, PtoolsError, UsageError
from ptools.portage_adapter import PortageBackend, get_portage_backend

#: Options understood by both commands. Anything else starting with ``--`` is a
#: usage error, which keeps ``-lua`` and ``-*`` usable as plain operands.
GLOBAL_OPTIONS = frozenset(
    {
        "--exact",
        "--dry-run",
        "--json",
        "--quiet",
        "--no-color",
        "--unset",
        "--merge-duplicates",
        "--file",
        "--init",
        "--version",
        "--help",
    }
)

#: Options that consume the following argument as their value.
VALUE_OPTIONS = frozenset({"--file"})

USE_FLAG_RE = re.compile(r"^-?[A-Za-z0-9][A-Za-z0-9+_@-]*$")
KEYWORD_RE = re.compile(r"^(\*\*|-?\*|[-~]?[A-Za-z0-9][A-Za-z0-9+_.-]*)$")

_COLORS = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33"}


class ArgumentParser(argparse.ArgumentParser):
    """argparse, but parse failures become exit-code-2 UsageErrors."""

    def error(self, message: str) -> NoReturn:
        raise UsageError(message)


def add_global_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--exact", action="store_true", help="target =cat/pkg-ver, not cat/pkg")
    parser.add_argument("--unset", action="store_true", help="remove the listed managed tokens")
    parser.add_argument(
        "--merge-duplicates",
        action="store_true",
        help="combine duplicate entries for the atom instead of failing",
    )
    parser.add_argument(
        "--file",
        metavar="NAME",
        default=None,
        help="write to this file inside the target directory instead of the resolved one",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="discover the config layout and write <config-root>/ptools.conf",
    )
    parser.add_argument("--version", action="store_true", help="print the ptools version and exit")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    parser.add_argument("--json", action="store_true", help="emit a single JSON object on stdout")
    parser.add_argument("--quiet", action="store_true", help="suppress human-readable output")
    parser.add_argument("--no-color", action="store_true", help="never emit ANSI colour")


def partition_argv(argv: Sequence[str], options: frozenset[str]) -> tuple[list[str], list[str]]:
    """Split argv into options and operands.

    Operands are taken literally, so ``-lua`` and ``-*`` reach the parser as
    values rather than as unknown short options. A bare ``--`` ends the options.
    """
    found: list[str] = []
    operands: list[str] = []
    end_of_options = False
    expects_value: str | None = None
    for arg in argv:
        if end_of_options:
            operands.append(arg)
        elif expects_value is not None:
            found.append(arg)
            expects_value = None
        elif arg == "--":
            end_of_options = True
        elif arg in ("-h", "--help"):
            found.append("--help")
        elif arg.startswith("--"):
            name = arg.split("=", 1)[0]
            if name not in options:
                raise UsageError(f"unrecognized option: {arg}")
            found.append(arg)
            if name in VALUE_OPTIONS and "=" not in arg:
                expects_value = name
        else:
            operands.append(arg)
    if expects_value is not None:
        raise UsageError(f"option {expects_value} requires a value")
    return found, operands


def validate_tokens(tokens: Sequence[str], pattern: re.Pattern[str], label: str) -> tuple[str, ...]:
    for token in tokens:
        if not pattern.match(token):
            raise UsageError(f"invalid {label}: {token!r}")
    return tuple(tokens)


def resolve_config_root(backend: PortageBackend) -> Path:
    """Portage's configuration root, never assumed to be ``/``.

    ``PTOOLS_CONFIG_ROOT`` overrides it outright, which is how sandbox and
    chroot testing writes somewhere other than a live /etc/portage.
    """
    override = os.environ.get("PTOOLS_CONFIG_ROOT")
    if override:
        return Path(override)
    return Path(backend.get_setting("PORTAGE_CONFIGROOT", "/") or "/") / "etc" / "portage"


@dataclass
class Output:
    prog: str
    json_mode: bool = False
    quiet: bool = False
    color: bool = False

    def paint(self, text: str, style: str) -> str:
        if not self.color:
            return text
        return f"\033[{_COLORS[style]}m{text}\033[0m"

    def result(
        self, payload: dict[str, Any], render: Callable[["Output", dict[str, Any]], str]
    ) -> None:
        if self.json_mode:
            print(json.dumps(payload), file=sys.stdout)
        elif not self.quiet:
            print(render(self, payload), file=sys.stdout)

    def failure(self, exc: PtoolsError, usage: str | None = None) -> int:
        if self.json_mode:
            print(
                json.dumps(
                    {"error": exc.kind, "message": str(exc), "exit_code": exc.exit_code},
                ),
                file=sys.stderr,
            )
        else:
            if usage:
                print(usage.rstrip(), file=sys.stderr)
            print(f"{self.prog}: {self.paint('error', 'red')}: {exc}", file=sys.stderr)
        return exc.exit_code


def render_mutation(out: Output, payload: dict[str, Any]) -> str:
    prefix = out.paint("[dry-run] ", "yellow") if payload["dry_run"] else ""
    atom = out.paint(payload["atom"], "bold")
    if not payload["changed"]:
        line = f"{prefix}{atom}: no change"
    else:
        parts = [out.paint(f"+{value}", "green") for value in payload["added"]]
        parts += [out.paint(f"-{value}", "red") for value in payload["removed"]]
        line = f"{prefix}{atom}: {' '.join(parts)} -> {payload['target']}"
    if payload.get("also_in"):
        note = f"note: entries for this atom also exist in: {', '.join(payload['also_in'])}"
        line = f"{line}\n{out.paint(f'  {note}', 'yellow')}"
    return line


def render_field(out: Output, label: str, values: Sequence[str] | str, empty: str = "-") -> str:
    text = " ".join(values) if not isinstance(values, str) else values
    return f"  {out.paint(f'{label}:', 'dim'):<24}{text or empty}"


def render_managed_state(out: Output, payload: dict[str, Any]) -> list[str]:
    """The ``managed``/``target`` lines of a show, one line per entry.

    An entry whose atom differs from the one a mutation would target (an exact
    or slotted form of the same package) shows that atom after the filename.
    """
    lines = []
    if payload["entries"]:
        for entry in payload["entries"]:
            label = f"managed [{entry['file']}]"
            if entry["atom"] != payload["atom"]:
                label = f"{label} {entry['atom']}"
            lines.append(render_field(out, label, entry["values"]))
    else:
        lines.append(render_field(out, "managed", [], empty="(none)"))
    lines.append(
        render_field(out, "target", payload["target"] or "(ambiguous - pass --file to choose)")
    )
    return lines


def render_init(out: Output, payload: dict[str, Any]) -> str:
    prefix = out.paint("[dry-run] ", "yellow") if payload["dry_run"] else ""
    return "\n".join(
        [
            f"{prefix}{out.paint(payload['target'], 'bold')}",
            render_field(out, "use default-file", payload["use_default"]),
            render_field(out, "keywords default-file", payload["keywords_default"]),
        ]
    )


def ptools_version() -> str:
    """The installed distribution version; 'unknown' from an uninstalled tree."""
    try:
        return metadata.version("ptools")
    except metadata.PackageNotFoundError:
        return "unknown"


def can_prompt(args: argparse.Namespace) -> bool:
    """Whether an interactive menu is allowed: a human on both ends, and no
    machine-readable or quiet output that a prompt would corrupt. Scripted
    invocations therefore stay deterministic and still exit 4."""
    return bool(sys.stdin.isatty() and sys.stderr.isatty() and not args.json and not args.quiet)


def select_match(matches: tuple[str, ...]) -> str | None:
    """Offer the candidate packages as a numbered menu on stderr.

    Returns the chosen cp, or None on anything other than a valid number
    (blank line, q, EOF, out of range) — the caller then fails as usual.
    """
    print("ambiguous package name - candidates:", file=sys.stderr)
    for index, match in enumerate(matches, start=1):
        print(f"  {index}) {match}", file=sys.stderr)
    print(f"select 1-{len(matches)} (anything else aborts): ", end="", file=sys.stderr, flush=True)
    line = sys.stdin.readline()
    try:
        choice = int(line.strip())
    except ValueError:
        return None
    if 1 <= choice <= len(matches):
        return matches[choice - 1]
    return None


def dispatch(
    *,
    prog: str,
    parser: argparse.ArgumentParser,
    options: frozenset[str],
    argv: Sequence[str] | None,
    backend: PortageBackend | None,
    run: Callable[[argparse.Namespace, PortageBackend], dict[str, Any]],
    render: Callable[[Output, dict[str, Any]], str],
) -> int:
    """Parse, execute, print, and map any failure onto its exit code."""
    raw = list(sys.argv[1:] if argv is None else argv)
    # --json / --no-color must be honoured even if parsing itself fails.
    out = Output(
        prog=prog,
        json_mode="--json" in raw,
        color=color_enabled("--no-color" in raw),
    )
    try:
        found, operands = partition_argv(raw, options)
        args = parser.parse_args([*found, "--", *operands])
        out = Output(
            prog=prog,
            json_mode=args.json,
            quiet=args.quiet,
            color=color_enabled(args.no_color),
        )
        if args.version:
            # Must work without portage: version questions come from exactly
            # the machines where the backend may be broken or absent.
            print(f"{prog} (ptools) {ptools_version()}", file=sys.stdout)
            return 0
        if backend is None:
            backend = get_portage_backend()
        try:
            payload = run(args, backend)
        except AmbiguousPackageError as exc:
            # The legacy tools offered ambiguous names as a menu; do the same
            # when a human is attached, otherwise fail exactly as before.
            if not (exc.matches and can_prompt(args)):
                raise
            choice = select_match(exc.matches)
            if choice is None:
                raise
            args.package = choice
            payload = run(args, backend)
    except PtoolsError as exc:
        return out.failure(exc, parser.format_usage() if isinstance(exc, UsageError) else None)
    out.result(payload, render)
    return 0


def color_enabled(no_color: bool) -> bool:
    if no_color or os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()
