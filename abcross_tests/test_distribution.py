from types import NoneType
from typing import Type

import pytest

from abcross.distribution import Variant, get_release_tarball_info, get_manifest
from abcross.common import Architecture


class TestDistribution:
    test_manifest_valid = {
        "bulletin": {
            "body": "AOSC OS strives to simplify your user experience and improve your day-to-day productivity.",
            "body-tr": "bulletin-body",
            "title": "Thank You for Choosing AOSC OS",
            "title-tr": "bulletin-title",
            "type": "info"
        },
        "mirrors": [
            {
                "loc": "China",
                "loc-tr": "lzu-loc",
                "name": "LZUOSS at Lanzhou University",
                "name-tr": "lzu-name",
                "url": "https://mirror.lzu.edu.cn/anthon/aosc-os/"
            },
            {
                "loc": "Hong Kong",
                "loc-tr": "koddos-loc",
                "name": "KoDDoS HK",
                "name-tr": "koddos-name",
                "url": "https://mirror-hk.koddos.net/anthon/aosc-os/"
            },
        ],
        "variants": [
            {
                "description": "Server releases are base system releases with additional tools for hosting remote files"
                               "and Web contents, providing network routing, and other functions that enriches network "
                               "access and resources for client devices.",
                "description-tr": "server-description",
                "name": "Server",
                "retro": False,
                "tarballs": [
                    {
                        "arch": "amd64",
                        "date": "20220508",
                        "downloadSize": 998131172,
                        "instSize": 4979393024,
                        "path": "os-amd64/server/aosc-os_server_20220508_amd64.tar.xz",
                        "sha256sum": "fab1e57ed1596b7c135976e9695f6ebeb29481139756d8327382bc4dfb0d7f6f"
                    },
                ]
            },
            {
                "description": "The Base variant provides a minimal set of features, just enough for you to get "
                               "started. Base is still a pre-configured variant like other AOSC OS variants. "
                               "Therefore, Base is suitable for performance constrained devices and servers.",
                "description-tr": "base-description",
                "name": "Base",
                "retro": False,
                "tarballs": [
                    {
                        "arch": "riscv64",
                        "date": "20220508",
                        "downloadSize": 638466720,
                        "instSize": 3457007616,
                        "path": "os-riscv64/base/aosc-os_base_20220508_riscv64.tar.xz",
                        "sha256sum": "0a2ddd7e5db9d8b8454a48c208817db769bf9f9d8529936b2d96b542e80bc85d"
                    },
                    {
                        "arch": "amd64",
                        "date": "20220508",
                        "downloadSize": 794907932,
                        "instSize": 3919198720,
                        "path": "os-amd64/base/aosc-os_base_20220508_amd64.tar.xz",
                        "sha256sum": "39818e36c668d2dd5436bca07b3097e3b1d731d29a8006182fd5694f655fafdd"
                    },
                    {
                        "arch": "amd64",
                        "date": "20220826",
                        "downloadSize": 985854784,
                        "instSize": 3629212160,
                        "path": "os-amd64/base/aosc-os_base_20220826_amd64.tar.xz",
                        "sha256sum": "31d2e11c771dbcf25deb1fbbf55ec9f79157902be6a7531273684051b5f7ec3b"
                    },
                ]
            }
        ]
    }

    @pytest.mark.parametrize(
        "arch, variant, expect_sha256",
        [
            (Architecture.AMD64, Variant.BASE, "31d2e11c771dbcf25deb1fbbf55ec9f79157902be6a7531273684051b5f7ec3b"),
            (Architecture.RISCV64, Variant.BASE, "0a2ddd7e5db9d8b8454a48c208817db769bf9f9d8529936b2d96b542e80bc85d"),
            (Architecture.ARM64, Variant.BASE, None),
            (Architecture.ARM64, Variant.BUILDKIT, None),
        ]
    )
    def test_get_release_tarball_info(self, arch: Architecture, variant: Variant, expect_sha256: str | None):
        actual = get_release_tarball_info(TestDistribution.test_manifest_valid, arch, variant)
        assert (actual is None) == (expect_sha256 is None)
        if actual is not None:
            assert actual["sha256sum"] == expect_sha256

    @pytest.mark.parametrize("mirror, expect_raise",
                             [
                                 ("https://repo.aosc.io", NoneType),
                                 ("https://mirror-hk.koddos.net/anthon/", NoneType),
                                 ("malformed_stuff", ValueError),
                             ]
                             )
    def test_get_manifest(self, mirror: str, expect_raise: Type):
        actual = None
        try:
            get_manifest(mirror)
        except Exception as e:
            actual = e

        assert type(actual) == expect_raise
