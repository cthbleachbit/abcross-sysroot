import hashlib
import logging
import subprocess
from pathlib import PosixPath
from typing import List
from urllib.request import urlopen

logger = logging.getLogger("tar")


def download_tarball(url: str, dest_file: PosixPath, sha256sum: str | None) -> None:
    """Download a file at specific url to a specific path and verify sha256sum if provided"""
    checksumming = hashlib.sha256()
    count_bytes = 0
    with urlopen(url) as incoming, open(dest_file, "wb") as save:
        length = 1024 * 1024
        print("Downloading...", end='\r')
        while True:
            buf = incoming.read(length)
            if not buf:
                break
            count_bytes += len(buf)
            print(f"Downloading... Bytes: {count_bytes}", end='\r')
            save.write(buf)
            if sha256sum is not None:
                checksumming.update(buf)
        logger.info(f"Tarball downloaded to {dest_file}. Written {count_bytes} bytes.")
    # Verify checksum
    if sha256sum is not None and checksumming.hexdigest() != sha256sum:
        dest_file.unlink(missing_ok=True)
        raise RuntimeError("Downloaded file has wrong checksum!\n"
                           f"Expected: {sha256sum}\n"
                           f"Got:      {checksumming.hexdigest()}"
                           )


def extract_tarball(tarball: PosixPath, extract_dir: PosixPath, silent=True) -> None:
    # Sanity checks
    if not tarball.exists() or not tarball.is_file():
        raise ValueError("Tarball doesn't exist or is not a regular file")
    if not extract_dir.exists() or not extract_dir.is_dir():
        raise ValueError("Destination sysroot is not a directory")
    if next(extract_dir.iterdir(), None) is not None:
        raise ValueError("Destination sysroot is not empty. Refusing to overwrite.")
    # Yeah, I ain't doing this in a pythonic way...
    tar_command: List[str] = ["sudo", "tar", "-xavf", tarball, "-px", "--xattrs", "-C", extract_dir]
    extract = subprocess.Popen(tar_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    count_files = 0
    error_out = ""
    if not silent:
        print("Extracting... Written Files:", end='\r')
    while extract.poll() is None:
        out = extract.stdout.readline()
        count_files += len(out.splitlines())
        if not silent and count_files > 0:
            print(f"Extracting... Written Files: {count_files}", end='\r')
    result = extract.poll()
    if not silent:
        print()
    logger.debug(f"Expanded archive. Written {count_files} files.")
    if result != 0:
        raise OSError(f"tar returned non zero exit status {result}")
