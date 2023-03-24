import logging
import tempfile
from dataclasses import dataclass
from pathlib import PosixPath
from typing import List

from .common import Architecture, privileged_call, regular_call

logger = logging.getLogger("sysroot")


@dataclass
class Sysroot:
    """Represents a sysroot installation point"""
    arch: Architecture
    path: PosixPath

    def dpkg_call(self, argv: List[str],
                  containerize: bool = False,
                  sudo: bool = True,
                  interactive: bool = True,
                  nspawn_args: List[str] = None) -> (str, str, int):
        """
        Call dpkg into the sysroot
        :param interactive: whether this call should be interactive
        :param nspawn_args:  extra arguments to pass to nspawn
        :param argv: dpkg arguments
        :param sudo: whether sudo should be used on a non-entering call
        :param containerize: whether this call should be executed inside qemu from the container
        :return: stdout, stderr, exit code
        """
        dpkg_call = ["dpkg"]
        if not containerize:
            dpkg_call.append(f"--root={self.path}")
        dpkg_call.extend(argv)

        if containerize:
            return self.containerize(dpkg_call, interactive=interactive, nspawn_args=nspawn_args)
        else:
            return privileged_call(dpkg_call, interactive=interactive) \
                if sudo else regular_call(dpkg_call, interactive=interactive)

    def apt_call(self, argv: List[str],
                 containerize: bool = True,
                 sudo: bool = True,
                 interactive: bool = False,
                 nspawn_args: List[str] = None) -> (str, str, int):
        """
        Call apt into the sysroot
        :param interactive: whether this call should be interactive
        :param nspawn_args:  extra arguments to pass to nspawn
        :param argv: dpkg arguments
        :param sudo: whether sudo should be used on a non-entering call
        :param containerize: whether this call should be executed inside qemu from the container
        :return: stdout, stderr, exit code
        """
        apt_call = ["apt"]
        if not containerize:
            apt_call.extend(["-o", f"RootDir={self.path}"])
        apt_call.extend(argv)

        if containerize:
            return self.containerize(apt_call, interactive=interactive, nspawn_args=nspawn_args)
        else:
            return privileged_call(apt_call, interactive=interactive) \
                if sudo else regular_call(apt_call, interactive=interactive)

    def containerize(self,
                     argv: List[str] | None = None,
                     nspawn_args: List[str] = None,
                     interactive: bool = True) -> (str, str, int):
        """
        Spawns a shell session into this Sysroot and optionally run argv as pid 2

        :param interactive:
        whether subprocess should have interactive access. Under interactive stdout, stderr are not captured.
        :param argv: argv to run inside the nspawn - or /bin/sh if argv is None
        :param nspawn_args: extra nspawn arguments to pass to systemd nspawn
        :return: stdout, stderr, exit code
        """
        if argv is None:
            argv = ["/bin/sh"]
        # Checks if we can execute stuff in this Sysroot...
        if not self.arch.match_current_arch() and not self.arch.have_qemu():
            logger.error(f"You can't run program built for {self.arch}. Install {self.arch.qemu_bin()} first.")
            return None
        # Form systemd-nspawn call.
        container_call = [
            "systemd-nspawn", f"--hostname=abcross-{self.arch.value}",
            "-D", self.path.resolve(),
        ]
        if nspawn_args:
            container_call.extend(nspawn_args)
        container_call.append("--as-pid2")
        container_call.extend(argv)

        return privileged_call(container_call, interactive=interactive)

    def unpack(self, packages: List[str], update: bool = False) -> None:
        """
        Unpacks a list of deb packages into the sysroot. By "unpacking" I mean literally unpacking only. This operation
        will NOT maintain dependency consistency NOR trigger post-install configuration.

        It should be obvious, but DO NOT expect to see a "bootable" sysroot or any program would run when you call
        enter() on it. dpkg might panic at the situation if you try to qemu-user emulate the sysroot.

        :param update:
        Whether sysroot should be fully upgraded before unpacking over it - note: this step is likely to fail.
        :param packages: the list of names of packages to install.
        :return: None - if error occurs exception will be thrown.
        """
        dpkg_admin_dir = (self.path / "var/lib/dpkg").resolve()
        # Sanity check: admin dir must exist and is a directory.
        if not dpkg_admin_dir.is_dir():
            raise EnvironmentError(f"{dpkg_admin_dir} in sysroot doesn't exist or is not a directory.")
        # Before this we need to refresh APT sources inside the container...
        logger.info("Refreshing source metadata...")
        _, _, ret = self.apt_call(["update", "-yy"], containerize=True, interactive=True)
        if update:
            logger.info("You have requested full system upgrade...")
            _, _, ret = self.apt_call(["full-upgrade", "-yy", "-o", "Dpkg::Options::=--force-confnew"],
                                      containerize=True, interactive=True)
            if ret != 0:
                raise OSError(f"Cannot upgrade in the sysroot. Apt returned {ret}. You may need to manually correct "
                              f"this problem.")
        # Download those packages.
        logger.info("Downloading packages...")
        temp_download_dir = tempfile.mkdtemp(prefix="abcross-download-")
        download_args = ["install", "--download-only", "-yy", "-o", "Dir::Cache::archives=/root"]
        download_args.extend(packages)
        _, _, ret = self.apt_call(
            download_args,
            containerize=True,
            interactive=True,
            nspawn_args=[
                f"--bind={temp_download_dir}:/root",
            ])
        if ret != 0:
            raise OSError(f"Cannot retrieve packages from the sysroot. Apt returned {ret}.")
        debs_iter = PosixPath(temp_download_dir).iterdir()
        debs = [deb.resolve() for deb in debs_iter if deb.name.endswith(".deb")]
        if len(debs) == 0:
            logger.warning(f"Requested to install {len(packages)} but apt downloaded 0 packages.")
            logger.warning(f"This is because some packages might have already been unpacked into this sysroot before.")
            logger.debug(f"Requested packages: {packages}")
            return None
        # Now unpack stuff over
        logger.info("Unpacking packages...")
        dpkg_call = [
            "--force-architecture",  # We are almost certainly going to see some exotic packages...
            "--force-depends", "--force-depends-version",  # Screw dependencies
            "--no-triggers",
            "--unpack",
        ]
        dpkg_call.extend(debs)
        _, _, ret = self.dpkg_call(dpkg_call, containerize=False, sudo=True)
        if ret != 0:
            raise OSError(f"Cannot unpack packages into the sysroot. Dpkg returned {ret}.")
        # Get rid of installed packages
        logger.info("Cleaning up...")
        _, _, ret = privileged_call(["rm", "-rf", temp_download_dir], interactive=False)
        if ret != 0:
            raise OSError(f"Cannot remove temporary download directory {temp_download_dir}")
