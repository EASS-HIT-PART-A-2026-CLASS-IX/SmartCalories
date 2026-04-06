import warnings

warnings.filterwarnings("ignore")

import pytest
from fastapi.testclient import TestClient

from calorie_tracker.main import app, reset_storage


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    reset_storage()
    yield
    reset_storage()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
