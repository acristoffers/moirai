"""
Tests for the REST API (moirai/webapi/api.py).

All tests use the `client` and `auth_headers` fixtures from conftest.py which
patch out Hardware and Server so no real device or socket is needed.
"""

import datetime
import io
import json
import zipfile

import pytest
from bson import json_util


def parse(resp):
    return json.loads(resp.data)


# ---------------------------------------------------------------------------
# Public endpoints (no token required)
# ---------------------------------------------------------------------------


class TestPublicEndpoints:
    def test_root_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_root_body(self, client):
        assert b"Moirai" in client.get("/").data

    def test_version_returns_version_key(self, client):
        resp = client.get("/version")
        assert resp.status_code == 200
        data = parse(resp)
        assert "version" in data

    def test_login_success(self, client):
        resp = client.post("/login", json={"password": "testpass"})
        assert resp.status_code == 200
        data = parse(resp)
        assert "token" in data
        assert len(data["token"]) == 32

    def test_login_wrong_password(self, client):
        resp = client.post("/login", json={"password": "wrong"})
        assert resp.status_code == 403

    def test_login_empty_password(self, client):
        resp = client.post("/login", json={"password": ""})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Auth guard — every protected endpoint returns 403 without a valid token
# ---------------------------------------------------------------------------


PROTECTED_ENDPOINTS = [
    ("GET", "/last_error"),
    ("GET", "/hardware/drivers"),
    ("GET", "/hardware/configuration"),
    ("POST", "/hardware/configuration"),
    ("GET", "/system_response/tests"),
    ("POST", "/system_response/tests"),
    ("POST", "/system_response/test/run"),
    ("GET", "/system_response/test/stop"),
    ("GET", "/live_graph/tests"),
    ("POST", "/live_graph/test"),
    ("POST", "/live_graph/test/remove"),
    ("POST", "/controllers"),
    ("GET", "/controllers"),
    ("POST", "/controllers/run"),
    ("GET", "/controllers/stop"),
    ("GET", "/db/dump"),
    ("POST", "/set-password"),
]


@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
def test_requires_auth(client, method, path):
    func = getattr(client, method.lower())
    resp = func(path, json={})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Hardware configuration
# ---------------------------------------------------------------------------


class TestHardwareConfiguration:
    def test_get_empty(self, client, auth_headers):
        resp = client.get("/hardware/configuration", headers=auth_headers)
        assert resp.status_code == 200
        assert parse(resp) == {}

    def test_set_and_get(self, client, auth_headers):
        config = {
            "name": "TestDriver",
            "ports": [{"id": 1, "alias": "out1", "type": 8}],
            "interlocks": [],
        }
        resp = client.post(
            "/hardware/configuration", json=config, headers=auth_headers
        )
        assert resp.status_code == 200

        resp = client.get("/hardware/configuration", headers=auth_headers)
        assert resp.status_code == 200
        assert parse(resp) == config


# ---------------------------------------------------------------------------
# System response tests
# ---------------------------------------------------------------------------


class TestSystemResponseTests:
    def test_get_empty(self, client, auth_headers):
        resp = client.get("/system_response/tests", headers=auth_headers)
        assert resp.status_code == 200
        assert parse(resp) == []

    def test_set_and_get(self, client, auth_headers):
        tests = [{"id": 1, "name": "step", "type": "step", "inputs": [], "output": []}]
        resp = client.post("/system_response/tests", json=tests, headers=auth_headers)
        assert resp.status_code == 200

        resp = client.get("/system_response/tests", headers=auth_headers)
        assert parse(resp) == tests


# ---------------------------------------------------------------------------
# Live graph
# ---------------------------------------------------------------------------


class TestLiveGraph:
    def _save_test(self, api):
        date = datetime.datetime(2024, 3, 15)
        gid = api.database.save_test("MyGraph", date)
        api.database.save_test_sensor_value(gid, "y", 1.0, 0.0)
        api.database.save_test_sensor_value(gid, "y", 2.0, 0.1)
        return date

    def test_list_tests(self, client, auth_headers, api):
        self._save_test(api)
        resp = client.get("/live_graph/tests", headers=auth_headers)
        assert resp.status_code == 200
        data = parse(resp)
        assert len(data) == 1
        assert data[0]["name"] == "MyGraph"

    def test_list_empty(self, client, auth_headers):
        resp = client.get("/live_graph/tests", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.data == b"[]"

    def test_get_test_data(self, client, auth_headers, api):
        date = self._save_test(api)
        resp = client.post(
            "/live_graph/test",
            json={"test": "MyGraph", "start_time": date.isoformat()},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = parse(resp)
        assert len(data) == 2

    def test_get_test_data_with_skip(self, client, auth_headers, api):
        date = self._save_test(api)
        resp = client.post(
            "/live_graph/test",
            json={"test": "MyGraph", "start_time": date.isoformat(), "skip": 1},
            headers=auth_headers,
        )
        assert len(parse(resp)) == 1

    def test_remove_single_test(self, client, auth_headers, api):
        date = self._save_test(api)
        resp = client.post(
            "/live_graph/test/remove",
            json={"test": "MyGraph", "start_time": date.isoformat()},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert api.database.list_test_data() == []

    def test_remove_multiple_tests(self, client, auth_headers, api):
        date1 = datetime.datetime(2024, 3, 15)
        date2 = datetime.datetime(2024, 3, 16)
        api.database.save_test("G1", date1)
        api.database.save_test("G2", date2)
        resp = client.post(
            "/live_graph/test/remove",
            json=[
                {"test": "G1", "start_time": date1.isoformat()},
                {"test": "G2", "start_time": date2.isoformat()},
            ],
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert api.database.list_test_data() == []


# ---------------------------------------------------------------------------
# Controllers
# ---------------------------------------------------------------------------


class TestControllers:
    def test_get_empty(self, client, auth_headers):
        resp = client.get("/controllers", headers=auth_headers)
        assert resp.status_code == 200
        assert parse(resp) == []

    def test_set_and_get(self, client, auth_headers):
        cs = [{"id": 1, "name": "PID", "tau": 0.1}]
        client.post("/controllers", json=cs, headers=auth_headers)
        resp = client.get("/controllers", headers=auth_headers)
        assert parse(resp) == cs

    def test_stop_returns_200(self, client, auth_headers):
        resp = client.get("/controllers/stop", headers=auth_headers)
        assert resp.status_code == 200

    def test_export_and_import(self, client, auth_headers):
        cs = [{"id": 1, "name": "C1", "tau": 0.5}]
        client.post("/controllers", json=cs, headers=auth_headers)

        # Export
        resp = client.post(
            "/controllers/export",
            json={"controllers": [1]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        zip_bytes = resp.data

        # Clear and import
        client.post("/controllers", json=[], headers=auth_headers)
        data = io.BytesIO(zip_bytes)
        resp = client.post(
            "/controllers/import",
            data={"file": (data, "dump.zip")},
            content_type="multipart/form-data",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        imported = parse(client.get("/controllers", headers=auth_headers))
        assert len(imported) == 1
        assert imported[0]["name"] == "C1"


# ---------------------------------------------------------------------------
# Set password
# ---------------------------------------------------------------------------


class TestSetPassword:
    def test_change_password(self, client, auth_headers):
        resp = client.post(
            "/set-password", json={"password": "newpass"}, headers=auth_headers
        )
        assert resp.status_code == 200
        # Old password no longer works
        assert client.post("/login", json={"password": "testpass"}).status_code == 403
        # New password works
        assert client.post("/login", json={"password": "newpass"}).status_code == 200


# ---------------------------------------------------------------------------
# Last error
# ---------------------------------------------------------------------------


class TestLastError:
    def test_last_error_empty(self, client, auth_headers, api):
        resp = client.get("/last_error", headers=auth_headers)
        assert resp.status_code == 200
        assert "message" in parse(resp)

    def test_last_error_value(self, client, auth_headers, api):
        api.database.set_setting("test_error", "division by zero")
        resp = client.get("/last_error", headers=auth_headers)
        assert parse(resp)["message"] == "division by zero"


# ---------------------------------------------------------------------------
# DB dump / restore
# ---------------------------------------------------------------------------


class TestDatabaseDumpRestore:
    def test_dump_returns_zip(self, client, auth_headers):
        resp = client.get("/db/dump", headers=auth_headers)
        assert resp.status_code == 200
        buf = io.BytesIO(resp.data)
        assert zipfile.is_zipfile(buf)

    def test_dump_contains_settings(self, client, auth_headers):
        resp = client.get("/db/dump", headers=auth_headers)
        buf = io.BytesIO(resp.data)
        with zipfile.ZipFile(buf, "r") as zf:
            d = json.loads(zf.read("dump"), object_hook=json_util.object_hook)
        assert "settings" in d
        assert "graphs" in d

    def test_restore_roundtrip(self, client, auth_headers, api):
        api.database.set_setting("controllers", [{"id": 99}])

        # Dump
        dump_resp = client.get("/db/dump", headers=auth_headers)
        zip_bytes = dump_resp.data

        # Clear
        api.database.set_setting("controllers", [])

        # Restore
        data = io.BytesIO(zip_bytes)
        resp = client.post(
            "/db/restore",
            data={"file": (data, "dump.zip")},
            content_type="multipart/form-data",
            headers=auth_headers,
        )
        assert resp.status_code == 200

        # Re-login (restore resets the DB including the password)
        resp = client.post("/login", json={"password": "testpass"})
        if resp.status_code == 200:
            token = parse(resp)["token"]
            h = {"Authorization": f"Bearer {token}"}
            cs = parse(client.get("/controllers", headers=h))
            assert any(c["id"] == 99 for c in cs)

