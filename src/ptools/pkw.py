"""``pkw`` - show or set per-package accept_keywords."""

import argparse
import sys
from collections.abc import Sequence
from typing import Any

from ptools.cli_common import (
    GLOBAL_OPTIONS,
    KEYWORD_RE,
    ArgumentParser,
    Output,
    add_global_options,
    color_keyword,
    dispatch,
    render_field,
    render_init,
    render_managed_state,
    render_mutation,
    resolve_config_root,
    validate_tokens,
)
from ptools.config_store import ConfigStore
from ptools.errors import PortageIntegrationError, UsageError
from ptools.portage_adapter import PortageBackend
from ptools.services import (
    InitService,
    MutationService,
    ReadOnlyService,
    validate_target_filename,
)

PROG = "pkw"

OPTIONS = GLOBAL_OPTIONS | {"--testing"}

EPILOG = """\
examples:
  pkw app-editors/neovim               show the keyword state
  pkw --testing app-editors/neovim     accept ~ARCH for the package
  pkw app-editors/neovim '**'          accept any keyword, including none
  pkw --unset app-editors/neovim '~amd64'
  pkw --file 99-local app-editors/neovim '~amd64'
  pkw --init                           write <config-root>/ptools.conf
"""


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        prog=PROG,
        usage="pkw [OPTIONS] PACKAGE [KEYWORD ...]",
        description=(
            "Show or set per-package keywords under "
            "<config-root>/package.accept_keywords/. Shows read every file there; "
            "writes go to the file already holding the atom, or to the configured "
            "default for new atoms. With no KEYWORD, show the current state."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_global_options(parser)
    parser.add_argument(
        "--testing", action="store_true", help="shorthand for the ~ARCH keyword of this system"
    )
    parser.add_argument(
        "package",
        metavar="PACKAGE",
        nargs="?",
        default=None,
        help="cat/pkg, =cat/pkg-ver, or a bare name",
    )
    parser.add_argument(
        "keywords", metavar="KEYWORD", nargs="*", help="~arch, arch, -*, ** or an explicit value"
    )
    return parser


def run(args: argparse.Namespace, backend: PortageBackend) -> dict[str, Any]:
    config_root = resolve_config_root(backend)
    store = ConfigStore(dry_run=args.dry_run, merge_duplicates=args.merge_duplicates)

    if args.init:
        if args.package or args.keywords or args.unset or args.exact or args.file or args.testing:
            raise UsageError("--init takes no PACKAGE, tokens, or other mode options")
        return InitService(backend, store, config_root).run()
    if args.package is None:
        raise UsageError("the following arguments are required: PACKAGE")

    chosen_file = validate_target_filename(args.file) if args.file else None
    if chosen_file and not (args.keywords or args.unset or args.testing):
        raise UsageError("--file only applies to mutations: pass KEYWORD tokens or --unset")

    if args.unset:
        if args.testing:
            raise UsageError("--testing cannot be combined with --unset")
        if not args.keywords:
            raise UsageError("--unset requires at least one keyword")
        keywords = validate_tokens(args.keywords, KEYWORD_RE, "keyword")
        service = MutationService(backend, store, config_root)
        return service.apply_keyword("unset", args.package, keywords, args.exact, chosen_file)

    keywords = validate_tokens(args.keywords, KEYWORD_RE, "keyword")
    if args.testing:
        arch = backend.get_setting("ARCH", "")
        if not arch:
            raise PortageIntegrationError("cannot determine ARCH from the portage configuration")
        keywords += (f"~{arch}",)

    if keywords:
        service = MutationService(backend, store, config_root)
        return service.apply_keyword("set", args.package, keywords, args.exact, chosen_file)

    return ReadOnlyService(backend, store, config_root).keyword_show(args.package, args.exact)


def render(out: Output, payload: dict[str, Any]) -> str:
    if payload["operation"] == "init":
        return render_init(out, payload)
    if payload["operation"] != "keyword.show":
        return render_mutation(out, payload)
    lines = [f"{out.paint(payload['atom'], 'bold')}  ({payload['cpv'] or 'no version'})"]
    lines.append(render_field(out, "arch", out.paint(payload["arch"], "bold") if payload["arch"] else "", empty="(unknown)"))
    kw_colored = " ".join(color_keyword(out, kw) for kw in payload["keywords"])
    lines.append(render_field(out, "ebuild keywords", kw_colored or "-"))
    lines.extend(render_managed_state(out, payload))
    if payload["legacy_package_keywords"]:
        lines.append(
            out.paint("  note: legacy package.keywords exists and is left untouched", "yellow")
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None, backend: PortageBackend | None = None) -> int:
    return dispatch(
        prog=PROG,
        parser=build_parser(),
        options=OPTIONS,
        argv=argv,
        backend=backend,
        run=run,
        render=render,
    )


if __name__ == "__main__":
    sys.exit(main())
