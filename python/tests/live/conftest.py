import os

import pytest

API_KEY_ENV_VAR = "HERASCRAPE_API_KEY"


@pytest.fixture(autouse=True)
def require_api_key() -> None:
    """Skip every live test unless the API key is in the environment."""
    if not os.environ.get(API_KEY_ENV_VAR):
        pytest.skip(f"{API_KEY_ENV_VAR} is not set")
