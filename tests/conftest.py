"""Pytest configuration and fixtures."""

import ctypes

import pytest


def is_admin() -> bool:
    """Check if running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "admin: marks tests as requiring administrator privileges"
    )
    config.addinivalue_line("markers", "slow: marks tests as slow running")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip tests that require admin if not running as admin."""
    if not is_admin():
        skip_admin = pytest.mark.skip(reason="Requires administrator privileges")
        for item in items:
            if "admin" in item.keywords:
                item.add_marker(skip_admin)


@pytest.fixture
def check_admin() -> bool:
    """Fixture to check admin status."""
    return is_admin()


@pytest.fixture
def skip_if_not_admin() -> None:
    """Skip test if not running as admin."""
    if not is_admin():
        pytest.skip("Requires administrator privileges")

