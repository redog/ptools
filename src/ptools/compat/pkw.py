import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Legacy pkw compatibility wrapper")
    parser.add_argument("--change", "-c", action="store_true")
    parser.add_argument("--remove", "-r", action="store_true")
    parser.add_argument("--any", "-a", action="store_true")
    parser.add_argument("--exact", "-e", action="store_true")
    parser.add_argument("--unall", "-u", action="store_true")
    parser.add_argument("atom", nargs="?")
    parser.add_argument("keywords", nargs="*")

    args, _unknown = parser.parse_known_args()

    if not args.atom:
        parser.print_help()
        return 1

    cmd = ["ptools", "keyword"]

    if args.change:
        cmd.append("set")
        cmd.append(args.atom)
        if args.unall:
            cmd.append("-*")
        else:
            cmd.append("--testing")

        cmd.extend(args.keywords)

        if args.exact:
            cmd.append("--exact")

    elif args.remove:
        cmd.append("unset")
        cmd.append(args.atom)
        cmd.extend(args.keywords)

        if args.exact:
            cmd.append("--exact")
    else:
        parser.print_help()
        return 1

    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
