import argparse
import sys

from .common import Architecture
from .distribution import Variant


def main():
    parser = argparse.ArgumentParser(description="AOSC OS cross-compiling sysroot manager")
    parser.add_argument("-a", "--arch",
                        required=True,
                        help="Work on the sysroot for specified architecture",
                        type=Architecture
                        )
    subparsers = parser.add_subparsers(
        title="commands",
        dest="command",
        help="Task to do. \n"
             "Use \"install\" to download a new sysroot.\n"
             "Use \"enter\" to launch a shell in the sysroot for maintenance."
    )
    subparser_install = subparsers.add_parser("install", help="Download and deploy a cross compile sysroot.")
    subparser_install.add_argument(
        "-m", "--mirror",
        help="Use specified mirror. Default to \"https://repo.aosc.io/\"",
        type=str,
        default="https://repo.aosc.io/"
    )
    subparser_install.add_argument(
        "-v", "--variant",
        help="Download tarball of specified variant. Default to Buildkit.",
        type=Variant,
        default=Variant.BUILDKIT
    )
    subparser_install.add_argument(
        "-f", "--force",
        help="Force overwriting a sysroot directory with existing data.",
        action="store_true"
    )
    subparser_enter = subparsers.add_parser("enter", help="Start an interactive shell or program in the sysroot.")
    subparser_enter.add_argument(
        "argv",
        nargs='*',
        help="Space separated argv to spawn in the container. Default to \"/bin/bash\".",
        default=["/bin/bash"]
    )

    args = parser.parse_args()
    print(args)
    sys.exit(5)


if __name__ == "__main__":
    main()
