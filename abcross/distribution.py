import json
import logging
import shutil
import tempfile
from enum import Enum
from pathlib import PosixPath
from typing import Dict, Any, List
from urllib.parse import urlparse, urlunparse
from urllib.request import urlopen

from .common import Architecture, privileged_call
from .sysroot import Sysroot
from .tar import download_tarball, extract_tarball

RELEASE_URL_BASE = "/aosc-os/"
CACHE_DIR = PosixPath.home() / ".cache" / "abcross"

logger = logging.getLogger("distribution")


class Variant(Enum):
    """
    Supported variants.

    Since this utility is only for cross compiling sysroots the only variants that make sense here are Base / BuildKit.
    Other variants here are listed for completeness
    """
    BASE = "Base"
    BUILDKIT = "BuildKit"
    SERVER = "Server"
    DESKTOP = "Desktop"
    DESKTOP_NVIDIA = "Desktop (with NVIDIA driver)"
    X11 = "X11"  # X11 retro


def get_manifest(mirror: str = "https://repo.aosc.io/") -> Dict[str, Any]:
    """Download manifest from mirror and deserialize"""
    # Validate mirror
    manifest_url_string = mirror + RELEASE_URL_BASE + "/manifest/recipe.json"
    manifest_url = urlparse(manifest_url_string)
    match manifest_url.scheme:
        case "http" | "https" | "file":
            pass
        case _:
            raise ValueError("Manifest URL is invalid")
    # Fetch manifest. urlopen or json load may throw
    with urlopen(urlunparse(manifest_url)) as manifest:
        return json.load(manifest)


def get_release_tarball_info(manifest: Dict[str, Any],
                             architecture: Architecture,
                             variant: Variant = Variant.BUILDKIT) -> Dict[str, int | str] | None:
    """
    Query the manifest and find the latest tarball for architecture and variant, and return relative download path
    If the manifest does not provide this particular combination return None.
    """
    if "variants" not in manifest:
        raise ValueError("Malformed manifest: This stuff doesn't have variants list")
    variants_list: List[Dict[str, Any]] = manifest["variants"]
    # Try to find the variant we want
    tarballs_per_variant: Dict[Variant, List[Dict]] = {}
    for variant_releases in variants_list:
        released_variant = Variant(variant_releases["name"])
        if released_variant not in tarballs_per_variant:
            tarballs_per_variant[released_variant] = []
        if "tarballs" not in variant_releases:
            continue
        for tarball in variant_releases["tarballs"]:
            tarballs_per_variant[released_variant].append(tarball)
    if variant not in tarballs_per_variant:
        return None
    tarballs = tarballs_per_variant[variant]
    # Find releases for the correct architecture
    tarballs_arch = [tarball for tarball in tarballs if Architecture(tarball["arch"]) == architecture]
    if len(tarballs_arch) == 0:
        return None
    # Find the latest release
    latest_release = max(tarballs_arch, key=lambda t: t["date"])
    return latest_release


def get_tarball(tarball_info: Dict[str, int | str],
                dest_dir: PosixPath,
                mirror: str = "https://repo.aosc.io/",
                overwrite: bool = True
                ) -> PosixPath:
    """Download tarball to specified directory, may throw exception if tarball cannot be found."""
    download_url_str: str = mirror + RELEASE_URL_BASE + tarball_info["path"]
    download_url = urlparse(download_url_str)
    expected_sum = tarball_info["sha256sum"]
    tarball_basename = PosixPath(tarball_info["path"]).name
    tarball_save_path = dest_dir.resolve() / tarball_basename
    if overwrite or not tarball_save_path.exists():
        shutil.rmtree(tarball_save_path, ignore_errors=True)
        download_tarball(urlunparse(download_url), tarball_save_path, expected_sum)
        return tarball_save_path
    # If no overwrite and the tarball path exists - most likely we've downloaded this before
    logger.info(f"Found previously downloaded tarball {tarball_save_path}. Reusing.")
    return tarball_save_path


def do_deploy(s: Sysroot, args) -> int:
    """Deploy specified sysroot"""
    manifest = get_manifest(args.mirror)
    tarball = get_release_tarball_info(manifest, s.arch, args.variant)
    if tarball is None:
        logger.error(f"Selected architecture {s.arch} and variant {args.variant} does not have a tarball available!")
        return 1
    logger.info(f"Selected distribution for {s.arch} variant {args.variant}:")
    logger.info("\tRelease Date:  %s" % (tarball["date"]))
    logger.info("\tDownload Size: %d Bytes" % (tarball["downloadSize"]))
    logger.info("\tOn-Disk Size:  %d Bytes" % (tarball["instSize"]))

    # Pre-download check...
    if s.path.is_dir() and next(s.path.iterdir(), None) is not None:
        if not args.force:
            logger.error(f"Destination sysroot {s.path} is not empty. Refusing to overwrite.")
            return 1
        else:
            logger.info(f"You asked for force-redeploy... Deleting existing sysroot.")
            _, _, ret = privileged_call(["rm", "-rf", s.path], interactive=False)
            if ret != 0:
                logger.error(f"Cannot delete non-empty sysroot {s.path}. You are on your own.")
                return 2
            logger.info(f"Old sysroot {s.path} has been deleted.")
    if not s.path.exists():
        _, _, ret = privileged_call(["mkdir", "-p", s.path], interactive=False)
        if ret != 0:
            logger.error(f"Cannot create empty sysroot {s.path}. You are on your own.")
            return 2
    # Find local cache if needed
    download_path = PosixPath()
    if args.cache:
        if CACHE_DIR.exists() and CACHE_DIR.is_dir():
            download_path = CACHE_DIR.resolve()
            logger.info(f"Downloading tarball to {CACHE_DIR}")
        else:
            try:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
            except RuntimeError:
                logger.warning(f"Cache directory {CACHE_DIR} is not available. Writing to tmpfs.")
                args.cache = False
    if not args.cache:
        download_path = PosixPath(tempfile.mkdtemp(prefix="abcross-tarball-"))
    local_tarball = get_tarball(tarball, download_path, args.mirror, overwrite=False)
    extract_tarball(local_tarball, s.path, silent=False)
    logger.info(f"Sysroot for {s.arch} is now ready for use at {s.path}")
    if not args.cache:
        shutil.rmtree(download_path, ignore_errors=True)
    return 0
