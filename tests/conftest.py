"""
Shared fixtures for all moirai tests.

All tests run against an in-memory mongomock database.  The autouse fixture
patches MongoClient at the source-import level so every DatabaseV1 instance
(including those created inside API handlers) automatically uses the mock.
"""

import hashlib
import json

import mongomock
import pytest

from moirai.database.mongodb import DatabaseV1


def sha512(password: str) -> str:
    h = hashlib.sha512()
    h.update(password.encode())
    return h.hexdigest()


def parse(resp):
    """Parse a Flask test response body as JSON."""
    return json.loads(resp.data)


@pytest.fixture(autouse=True)
def mock_mongo(monkeypatch):
    """Replace MongoClient with mongomock for every test and wipe state after."""
    monkeypatch.setattr("moirai.database.mongodb.MongoClient", mongomock.MongoClient)
    yield
    mongomock.MongoClient().drop_database("moirai")


@pytest.fixture
def db():
    """Return a fresh DatabaseV1 backed by mongomock."""
    return DatabaseV1()


@pytest.fixture
def api(mocker):
    """
    Return a configured APIv1 instance with:
      - Hardware stubbed out (avoids real device access)
      - Server stubbed out (avoids Cheroot trying to bind a port)
      - A 'testpass' password already set in the database
    """
    mocker.patch("moirai.webapi.api.Hardware")
    mocker.patch("moirai.webapi.api.Server")

    from moirai.webapi.api import APIv1

    mock_ph = mocker.MagicMock()
    instance = APIv1(mock_ph, [])
    instance.run()

    instance.database.set_setting("password", sha512("testpass"))
    return instance


@pytest.fixture
def client(api):
    """Return a Flask test client."""
    return api.app.test_client()


@pytest.fixture
def auth_headers(client):
    """Log in and return an Authorization header dict."""
    resp = client.post("/login", json={"password": "testpass"})
    token = json.loads(resp.data)["token"]
    return {"Authorization": f"Bearer {token}"}
