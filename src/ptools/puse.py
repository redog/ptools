"""``puse`` - show or set per-package USE flags."""

import argparse
import sys
from collections.abc import Sequence
from typing import Any

from ptools.cli_common import (
    GLOBAL_OPTIONS,
    USE_FLAG_RE,
    ArgumentParser,
    Output,
    add_global_options,
    dispatch,
    render_field,
    render_mutation,
    resolve_config_root,
    validate_tokens,
)
from ptools.config_store import ConfigStore
from ptools.errors import UsageError
from ptools.portage_adapter import PortageBackend
from ptools.services import MutationService, ReadOnlyService

PROG = "puse"

EPILOG = """\
examples:
  puse app-editors/neovim              show the effective USE state
  puse app-editors/neovim lua -python  enable lua, disable python
  puse --exact =app-editors/neovim-0.10.4 lua
  puse --unset app-editors/neovim lua  drop the managed lua entry
"""


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        prog=PROG,
        usage="puse [OPTIONS] PACKAGE [FLAG ...]",
        description=(
            "Show or set per-package USE flags in "
            "<config-root>/package.use/ptools. With no FLAG, show the current state."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_global_options(parser)
    parser.add_argument("package", metavar="PACKAGE", help="cat/pkg, =cat/pkg-ver, or a bare name")
    parser.add_argument(
        "flags", metavar="FLAG", nargs="*", help="USE flag to enable, or -flag to disable"
    )
    return parser


def run(args: argparse.Namespace, backend: PortageBackend) -> dict[str, Any]:
    config_root = resolve_config_root(backend)
    store = ConfigStore(dry_run=args.dry_run, merge_duplicates=args.merge_duplicates)

    if args.unset:
        if not args.flags:
            raise UsageError("--unset requires at least one USE flag")
        flags = validate_tokens(args.flags, USE_FLAG_RE, "USE flag")
        service = MutationService(backend, store, config_root)
        return service.apply_use("unset", args.package, flags, args.exact)

    if args.flags:
        flags = validate_tokens(args.flags, USE_FLAG_RE, "USE flag")
        service = MutationService(backend, store, config_root)
        return service.apply_use("set", args.package, flags, args.exact)

    return ReadOnlyService(backend, store, config_root).use_show(args.package, args.exact)


def render(out: Output, payload: dict[str, Any]) -> str:
    if payload["operation"] != "use.show":
        return render_mutation(out, payload)
    lines = [f"{out.paint(payload['atom'], 'bold')}  ({payload['cpv'] or 'no version'})"]
    lines.append(render_field(out, "iuse", payload["iuse"]))
    lines.append(render_field(out, "effective use", payload["effective"]))
    lines.append(
        render_field(
            out,
            "installed use",
            payload["installed_use"],
            empty="(not installed)" if not payload["installed"] else "-",
        )
    )
    lines.append(render_field(out, "managed", payload["managed"], empty="(none)"))
    lines.append(render_field(out, "target", payload["target"]))
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None, backend: PortageBackend | None = None) -> int:
    return dispatch(
        prog=PROG,
        parser=build_parser(),
        options=GLOBAL_OPTIONS,
        argv=argv,
        backend=backend,
        run=run,
        render=render,
    )


if __name__ == "__main__":
    sys.exit(main())
