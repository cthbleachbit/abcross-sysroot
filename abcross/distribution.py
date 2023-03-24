import json
import logging
from enum import Enum
from pathlib import PosixPath
from urllib.parse import urlparse, urlunparse
from urllib.request import urlopen
from typing import Dict, Any, List

from .common import Architecture
from .tar import download_tarball

release_url_base = "/aosc-os/"

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
    manifest_url_string = mirror + release_url_base + "/manifest/recipe.json"
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
        variant = Variant(variant_releases["name"])
        if variant not in tarballs_per_variant:
            tarballs_per_variant[variant] = []
        if "tarballs" not in variant_releases:
            continue
        for tarball in variant_releases["tarballs"]:
            tarballs_per_variant[variant].append(tarball)
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
                mirror: str = "https://repo.aosc.io/"
                ):
    """Download tarball to specified directory, may throw exception if tarball cannot be found."""
    download_url_str: str = mirror + release_url_base + tarball_info["path"]
    download_url = urlparse(download_url_str)
    expected_sum = tarball_info["sha256sum"]
    tarball_basename = PosixPath(tarball_info["path"]).name
    tarball_save_path = dest_dir.resolve() / tarball_basename
    download_tarball(urlunparse(download_url), tarball_save_path, expected_sum)
