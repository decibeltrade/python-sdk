from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from decibel.abi import AbiRegistry


@pytest.fixture
def config() -> dict[str, Any]:
    """Provide test configuration."""
    # Placeholder - will be implemented with actual Config class
    return {}


@pytest.fixture
def abi_registry() -> "AbiRegistry":
    """Provide ABI registry for tests."""
    from decibel.abi import AbiRegistry

    return AbiRegistry()


@pytest.fixture
def read_client() -> None:
    """Provide read-only client for tests."""
    # Placeholder - will be implemented with DecibelRead
    return None


@pytest.fixture
def write_client() -> None:
    """Provide write client for tests."""
    # Placeholder - will be implemented with DecibelWrite
    return None
