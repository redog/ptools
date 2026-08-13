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
    render_init,
    render_managed_state,
    render_mutation,
    resolve_config_root,
    validate_tokens,
)
from ptools.config_store import ConfigStore
from ptools.errors import UsageError
from ptools.portage_adapter import PortageBackend
from ptools.services import (
    InitService,
    MutationService,
    ReadOnlyService,
    validate_target_filename,
)

PROG = "puse"

EPILOG = """\
examples:
  puse app-editors/neovim              show the effective USE state
  puse app-editors/neovim lua -python  enable lua, disable python
  puse --exact =app-editors/neovim-0.10.4 lua
  puse --unset app-editors/neovim lua  drop the managed lua entry
  puse --file 50-editors app-editors/neovim lua
  puse --init                          write <config-root>/ptools.conf
"""


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        prog=PROG,
        usage="puse [OPTIONS] PACKAGE [FLAG ...]",
        description=(
            "Show or set per-package USE flags under <config-root>/package.use/. "
            "Shows read every file there; writes go to the file already holding "
            "the atom, or to the configured default for new atoms. With no FLAG, "
            "show the current state."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_global_options(parser)
    parser.add_argument(
        "package",
        metavar="PACKAGE",
        nargs="?",
        default=None,
        help="cat/pkg, =cat/pkg-ver, or a bare name",
    )
    parser.add_argument(
        "flags", metavar="FLAG", nargs="*", help="USE flag to enable, or -flag to disable"
    )
    return parser


def run(args: argparse.Namespace, backend: PortageBackend) -> dict[str, Any]:
    config_root = resolve_config_root(backend)
    store = ConfigStore(dry_run=args.dry_run, merge_duplicates=args.merge_duplicates)

    if args.init:
        if args.package or args.flags or args.unset or args.exact or args.file:
            raise UsageError("--init takes no PACKAGE, tokens, or other mode options")
        return InitService(backend, store, config_root).run()
    if args.package is None:
        raise UsageError("the following arguments are required: PACKAGE")

    chosen_file = validate_target_filename(args.file) if args.file else None
    if chosen_file and not (args.flags or args.unset):
        raise UsageError("--file only applies to mutations: pass FLAG tokens or --unset")

    if args.unset:
        if not args.flags:
            raise UsageError("--unset requires at least one USE flag")
        flags = validate_tokens(args.flags, USE_FLAG_RE, "USE flag")
        service = MutationService(backend, store, config_root)
        return service.apply_use("unset", args.package, flags, args.exact, chosen_file)

    if args.flags:
        flags = validate_tokens(args.flags, USE_FLAG_RE, "USE flag")
        service = MutationService(backend, store, config_root)
        return service.apply_use("set", args.package, flags, args.exact, chosen_file)

    return ReadOnlyService(backend, store, config_root).use_show(args.package, args.exact)


def render(out: Output, payload: dict[str, Any]) -> str:
    if payload["operation"] == "init":
        return render_init(out, payload)
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
    lines.extend(render_managed_state(out, payload))
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
