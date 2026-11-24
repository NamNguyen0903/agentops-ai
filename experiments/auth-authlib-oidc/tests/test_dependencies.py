from importlib.metadata import version

import pytest

from authlib_oidc_poc.oidc_client import register_authlib_client


@pytest.mark.parametrize("package,expected", [
    ("Authlib", "1.9.10"),
    ("fastapi", "0.165.0"),
    ("starlette", "1.10.0"),
    ("SQLAlchemy", "2.0.58"),
    ("httpx2", "2.16.2"),
    ("pytest", "9.2.0"),
])
def test_p01_pinned_dependencies(package, expected):
    assert version(package) == expected


def test_p01_client_registration(config):
    assert register_authlib_client(config) is not None
