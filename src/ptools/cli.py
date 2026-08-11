import argparse
import json
import sys
from typing import NoReturn

from ptools.errors import AmbiguousPackageError, PackageNotFoundError, PtoolsError
from ptools.portage_adapter import get_portage_backend
from ptools.services import ReadOnlyService


def fatal(message: str, code: int = 1) -> NoReturn:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(code)


def main() -> int:
    parser = argparse.ArgumentParser(description="ptools: Gentoo Portage configuration tools")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Package commands
    pkg_parser = subparsers.add_parser("package", help="Package operations")
    pkg_sub = pkg_parser.add_subparsers(dest="subcommand", required=True)

    resolve_cmd = pkg_sub.add_parser("resolve", help="Resolve package atom")
    resolve_cmd.add_argument("atom", help="Package atom to resolve")

    versions_cmd = pkg_sub.add_parser("versions", help="List versions")
    versions_cmd.add_argument("atom", help="Package atom to resolve")

    # USE commands
    use_parser = subparsers.add_parser("use", help="USE flag operations")
    use_sub = use_parser.add_subparsers(dest="subcommand", required=True)

    use_show_cmd = use_sub.add_parser("show", help="Show USE state")
    use_show_cmd.add_argument("atom", help="Package atom")

    use_set_cmd = use_sub.add_parser("set", help="Set USE flags")
    use_set_cmd.add_argument("atom", help="Package atom")
    use_set_cmd.add_argument("flags", nargs="+", help="USE flags")
    use_set_cmd.add_argument("--exact", action="store_true", help="Apply to exact version")
    use_set_cmd.add_argument("--dry-run", action="store_true", help="Do not write")

    use_unset_cmd = use_sub.add_parser("unset", help="Unset USE flags")
    use_unset_cmd.add_argument("atom", help="Package atom")
    use_unset_cmd.add_argument("flags", nargs="+", help="USE flags")
    use_unset_cmd.add_argument("--exact", action="store_true", help="Apply to exact version")
    use_unset_cmd.add_argument("--dry-run", action="store_true", help="Do not write")

    # Keyword commands
    kw_parser = subparsers.add_parser("keyword", help="Keyword operations")
    kw_sub = kw_parser.add_subparsers(dest="subcommand", required=True)

    kw_show_cmd = kw_sub.add_parser("show", help="Show Keyword state")
    kw_show_cmd.add_argument("atom", help="Package atom")

    kw_set_cmd = kw_sub.add_parser("set", help="Set Keywords")
    kw_set_cmd.add_argument("atom", help="Package atom")
    kw_set_cmd.add_argument("keywords", nargs="*", help="Keywords")
    kw_set_cmd.add_argument("--testing", action="store_true", help="Add testing keyword for ARCH")
    kw_set_cmd.add_argument("--exact", action="store_true", help="Apply to exact version")
    kw_set_cmd.add_argument("--dry-run", action="store_true", help="Do not write")

    kw_unset_cmd = kw_sub.add_parser("unset", help="Unset Keywords")
    kw_unset_cmd.add_argument("atom", help="Package atom")
    kw_unset_cmd.add_argument("keywords", nargs="+", help="Keywords")
    kw_unset_cmd.add_argument("--exact", action="store_true", help="Apply to exact version")
    kw_unset_cmd.add_argument("--dry-run", action="store_true", help="Do not write")

    args = parser.parse_args()

    backend = get_portage_backend()
    service = ReadOnlyService(backend)

    from pathlib import Path

    from ptools.config_store import ConfigStore
    from ptools.services import MutationService

    try:
        if args.command == "package":
            if args.subcommand == "resolve":
                res = service.resolve(args.atom)
                result = {"atom": res.atom, "cp": res.cp, "cpv": res.cpv}
            elif args.subcommand == "versions":
                result = service.versions(args.atom)

        elif args.command == "use":
            if args.subcommand == "show":
                result = service.use_show(args.atom)
            else:
                store = ConfigStore(dry_run=args.dry_run)
                mut_svc = MutationService(
                    backend,
                    store,
                    Path(backend.get_setting("PORTAGE_CONFIGROOT", "/")) / "etc/portage",
                )
                result = mut_svc.apply_use(
                    args.subcommand, args.atom, tuple(args.flags), args.exact
                )

        elif args.command == "keyword":
            if args.subcommand == "show":
                result = service.keyword_show(args.atom)
            else:
                store = ConfigStore(dry_run=args.dry_run)
                mut_svc = MutationService(
                    backend,
                    store,
                    Path(backend.get_setting("PORTAGE_CONFIGROOT", "/")) / "etc/portage",
                )

                kw_list = list(args.keywords)
                if args.subcommand == "set" and getattr(args, "testing", False):
                    arch = backend.get_setting("ARCH", "amd64")
                    kw_list.append(f"~{arch}")

                result = mut_svc.apply_keyword(
                    args.subcommand, args.atom, tuple(kw_list), args.exact
                )

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            for k, v in result.items():
                print(f"{k}: {v}")

        return 0
    except PackageNotFoundError as e:
        if not args.json:
            fatal(str(e), code=3)
        print(json.dumps({"error": str(e)}))
        return 3
    except AmbiguousPackageError as e:
        if not args.json:
            fatal(str(e), code=4)
        print(json.dumps({"error": str(e)}))
        return 4
    except PtoolsError as e:
        if not args.json:
            fatal(str(e), code=1)
        print(json.dumps({"error": str(e)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
