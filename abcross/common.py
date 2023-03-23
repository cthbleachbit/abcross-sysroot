import logging
import platform
from enum import Enum
from pathlib import PosixPath
from typing import Optional

logger = logging.getLogger("common")


class Architecture(Enum):
    """Hardware architecture supported by AOSC OS"""
    AMD64 = "amd64"
    ARM64 = "arm64"
    LOONGSON3 = "loongson3"
    POWERPC = "powerpc"
    PPC64EL = "ppc64el"
    RISCV64 = "riscv64"
    MIPS64R6EL = "mips64r6el"

    def qemu_arch(self) -> str:
        """Return architecture name in qemu nomenclature"""
        match self:
            case Architecture.AMD64:
                return "amd64"
            case Architecture.ARM64:
                return "aarch64"
            case Architecture.LOONGSON3:
                return "mips64el"
            case Architecture.POWERPC:
                return "ppc"
            case Architecture.PPC64EL:
                return "ppc64le"
            case Architecture.RISCV64:
                return "riscv64"
            case Architecture.MIPS64R6EL:
                return "mips64el"
            case _:
                raise ValueError

    def qemu_bin(self) -> str:
        return f"qemu-{self.qemu_arch()}-static"

    @staticmethod
    def match_current_arch() -> Optional["Architecture"]:
        """Check whether current system architecture is any of the possible targets"""
        match platform.machine():
            case "x86_64":
                return Architecture.AMD64
            case "aarch64":
                return Architecture.ARM64
            case "riscv64":
                return Architecture.RISCV64
            case "ppc":
                return Architecture.POWERPC
            case "ppc64le":
                return Architecture.PPC64EL
            case "mips64":
                # FIXME: python can't tell apart loongson3 / other flavor of mips
                return None
            case _:
                return None

    def has_qemu_program(self) -> str | None:
        """Return whether qemu static binary or none if this is not found on the system"""
        base_name = self.qemu_bin()
        binfmt_reg_name = f"/proc/sys/fs/binfmt_misc/qemu-{self.qemu_arch()}"
        try:
            with open(binfmt_reg_name, 'r') as binfmt_reg:
                binfmt_reg_content = binfmt_reg.readlines()
        except OSError as e:
            logger.critical(f"Architecture {self} is not registered with binfmt: {e.strerror}")
            return None
        if binfmt_reg_content[0].strip() != "enabled":
            logger.critical(f"Architecture {self} is not enabled with binfmt")
            logger.critical(f"Content of binfmt descriptor:\n{binfmt_reg_content}")
            return None
        match_interp = re.match(f"interpreter (?P<path>.+{base_name})", binfmt_reg_content[1])
        if not match_interp:
            logger.critical(f"Architecture {self} does not have valid interpreter")
            return None
        path_interp = match_interp.group("path")
        if PosixPath(path_interp).resolve().name != base_name:
            logger.critical(f"Architecture {self} has incorrect interpreter {path_interp} instead of {base_name}")
            return None
        return path_interp

    def standard_sysroot(self) -> PosixPath:
        """Returns standard sysroot location for AOSC OS"""
        return PosixPath(f"/var/ab/cross-root/{self}")
