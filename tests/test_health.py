from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_application_starts(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200


def test_health_returns_http_200(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200


def test_health_returns_expected_json(client: TestClient) -> None:
    response = client.get("/health")

    assert response.json() == {"status": "healthy", "service": "EduSearch"}
