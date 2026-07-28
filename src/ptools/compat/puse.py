import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Legacy puse compatibility wrapper")
    parser.add_argument("--show", "-s", action="store_true")
    parser.add_argument("--change", "-c", action="store_true")
    parser.add_argument("--remove", "-r", action="store_true")
    parser.add_argument("--any", "-a", action="store_true")
    parser.add_argument("--exact", "-e", action="store_true")
    parser.add_argument("--not", "-n", action="store_true", dest="not_flag")
    parser.add_argument("atom", nargs="?")
    parser.add_argument("flags", nargs="*")

    args, _unknown = parser.parse_known_args()

    if not args.atom:
        parser.print_help()
        return 1

    cmd = ["ptools", "use"]

    if args.show:
        cmd.append("show")
        cmd.append(args.atom)
    elif args.change:
        cmd.append("set")
        cmd.append(args.atom)

        flags = []
        for flag in args.flags:
            if args.not_flag:
                flags.append(f"-{flag}")
            else:
                flags.append(flag)
        cmd.extend(flags)

        if args.exact:
            cmd.append("--exact")

    elif args.remove:
        cmd.append("unset")
        cmd.append(args.atom)
        cmd.extend(args.flags)

        if args.exact:
            cmd.append("--exact")
    else:
        parser.print_help()
        return 1

    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
