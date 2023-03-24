import argparse
import logging
import sys
from pathlib import PosixPath

from .common import Architecture
from .distribution import Variant, do_deploy
from .sysroot import Sysroot


def handle_arguments():
    parser = argparse.ArgumentParser(description="AOSC OS cross-compiling sysroot manager")
    parser.add_argument("-a", "--arch",
                        required=True,
                        help="Work on the sysroot for specified architecture",
                        type=Architecture
                        )
    parser.add_argument("-s", "--sysroot",
                        required=False,
                        help="Path to the sysroot. Default to \"/var/ab/cross-root/<arch>\"",
                        type=PosixPath,
                        default=None
                        )
    subparsers = parser.add_subparsers(
        title="commands",
        dest="command",
        required=True,
        help="Sub-commands. Use \"--help\" after command to see command-specific options."
    )
    subparser_deploy = subparsers.add_parser("deploy", help="Download and deploy a cross compile sysroot.")
    subparser_deploy.add_argument(
        "-m", "--mirror",
        help="Use specified mirror. Default to \"https://repo.aosc.io/\"",
        type=str,
        default="https://repo.aosc.io/"
    )
    subparser_deploy.add_argument(
        "-v", "--variant",
        help="Download tarball of specified variant. Default to Buildkit.",
        type=Variant,
        default=Variant.BUILDKIT
    )
    subparser_deploy.add_argument(
        "-f", "--force",
        help="Force overwriting a sysroot directory with existing data.",
        action="store_true"
    )
    subparser_deploy.add_argument(
        "-c", "--cache",
        help="Save tarballs to ~/.cache/abcross/. Otherwise they are saved to tmpfs and deleted once we're done.",
        action="store_true"
    )
    subparser_enter = subparsers.add_parser("enter",
                                            help="Start an interactive shell or program in the sysroot.")
    subparser_enter.add_argument(
        "argv",
        nargs='*',
        help="Space separated argv to spawn in the container. Default to \"/bin/bash\".",
        default=["/bin/bash"]
    )
    subparsers_unpack = subparsers.add_parser("unpack",
                                              help="Unpack packages and their dependencies in the sysroot.")
    subparsers_unpack.add_argument(
        "-u", "--update",
        action="store_true",
        help="Do a full upgrade before unpacking specified packages"
    )
    subparsers_unpack.add_argument(
        "packages",
        nargs='+',
        help="Space separated list of package names to install."
    )
    return parser.parse_args()


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s', )
    args = handle_arguments()
    a: Architecture = args.arch
    p: PosixPath = a.standard_sysroot() if args.sysroot is None else args.sysroot
    s = Sysroot(a, PosixPath(p))
    match args.command:
        case "enter":
            s.containerize(args.argv, interactive=True)
        case "unpack":
            s.unpack(args.packages, update=args.update)
        case _:
            sys.exit(do_deploy(s, args))


if __name__ == "__main__":
    main()
