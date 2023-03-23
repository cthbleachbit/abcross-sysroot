import logging
import subprocess
from dataclasses import dataclass
from pathlib import PosixPath
from typing import List

from .common import Architecture

logger = logging.getLogger("sysroot")


@dataclass
class Sysroot:
    """Represents a sysroot installation point"""
    arch: Architecture
    path: PosixPath

    def enter(self, argv: List[str] | None = None, extra_nspawn_args: List[str] = None) -> None:
        """
        Spawns a shell session into this Sysroot and optionally run argv as pid 2

        :param argv: argv to run inside the nspawn - or /bin/sh if argv is None
        :param dry_run: whether we should actually launch this stuff
        :param extra_nspawn_args: extra nspawn arguments to pass to systemd nspawn
        """
        if argv is None:
            argv = ["/bin/sh"]
        # Checks if we can execute stuff in this Sysroot...
        if not self.arch.match_current_arch() and not self.arch.has_qemu_program():
            logger.error(f"You can't run program built for {self.arch}. Install {self.arch.qemu_bin()} first.")
            return None
        # Form systemd-nspawn call.
        container_call = ["sudo", "systemd-nspawn", "-D", self.path.resolve(), "--as-pid2"]
        container_call.extend(argv)
        if extra_nspawn_args:
            container_call.extend(extra_nspawn_args)

        ret = subprocess.run(container_call)
        if ret.returncode != 0:
            logger.error(f"Command to start container returned non-zero exit status {ret.returncode}")
            logger.debug(f"Command used: {container_call}")
