"""
Tests for the MongoDB database adapter (moirai/database/mongodb.py).

Covers: settings CRUD, token lifecycle, test-data CRUD, dump/restore.
"""

import time

import pytest

from moirai.database.mongodb import DatabaseV1


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class TestSettings:
    def test_set_and_get(self, db):
        db.set_setting("foo", "bar")
        assert db.get_setting("foo") == "bar"

    def test_overwrite(self, db):
        db.set_setting("key", "first")
        db.set_setting("key", "second")
        assert db.get_setting("key") == "second"

    def test_missing_key_returns_none(self, db):
        assert db.get_setting("nonexistent") is None

    def test_value_types(self, db):
        for value in [42, 3.14, True, [1, 2], {"a": 1}]:
            db.set_setting("typed", value)
            assert db.get_setting("typed") == value


# ---------------------------------------------------------------------------
# Token lifecycle
# ---------------------------------------------------------------------------


class TestTokens:
    def test_generate_returns_string(self, db):
        token = db.generate_token()
        assert isinstance(token, str)
        assert len(token) == 32  # uuid4 hex

    def test_generated_token_is_valid(self, db):
        token = db.generate_token()
        assert db.verify_token(token) is True

    def test_invalid_token_rejected(self, db):
        assert db.verify_token("deadbeef" * 4) is False

    def test_multiple_tokens_all_valid(self, db):
        tokens = [db.generate_token() for _ in range(5)]
        for t in tokens:
            assert db.verify_token(t) is True

    def test_expired_token_rejected(self, db, monkeypatch):
        token = db.generate_token()
        # Advance time past the token lifespan
        future = time.time() + db.token_lifespan + 1
        monkeypatch.setattr("moirai.database.mongodb.time.time", lambda: future)
        db2 = DatabaseV1()
        assert db2.verify_token(token) is False

    def test_verify_refreshes_token(self, db):
        # A valid token should remain valid after multiple verifications
        # (the "refresh on verify" behaviour keeps the token alive)
        token = db.generate_token()
        for _ in range(3):
            assert db.verify_token(token) is True


# ---------------------------------------------------------------------------
# Test data (graphs / sensor values)
# ---------------------------------------------------------------------------


class TestTestData:
    def _date(self, offset=0):
        import datetime
        return datetime.datetime(2024, 1, 1)

    def test_save_and_list(self, db):
        date = self._date()
        db.save_test("MyTest", date)
        tests = db.list_test_data()
        assert len(tests) == 1
        assert tests[0]["name"] == "MyTest"
        assert tests[0]["date"] == date

    def test_multiple_tests(self, db):
        import datetime
        d1 = datetime.datetime(2024, 1, 1)
        d2 = datetime.datetime(2024, 1, 2)
        db.save_test("Test1", d1)
        db.save_test("Test2", d2)
        names = {t["name"] for t in db.list_test_data()}
        assert names == {"Test1", "Test2"}

    def test_save_sensor_int_value(self, db):
        date = self._date()
        gid = db.save_test("T", date)
        db.save_test_sensor_value(gid, "sensor", 5, 0.0)
        data = db.get_test_data("T", date)
        assert data[0]["value"] == 5
        assert isinstance(data[0]["value"], int)

    def test_save_sensor_float_value(self, db):
        date = self._date()
        gid = db.save_test("T", date)
        db.save_test_sensor_value(gid, "sensor", 1.5, 0.0)
        data = db.get_test_data("T", date)
        assert data[0]["value"] == pytest.approx(1.5)
        assert isinstance(data[0]["value"], float)

    def test_save_sensor_bool_stored_as_int(self, db):
        date = self._date()
        gid = db.save_test("T", date)
        db.save_test_sensor_value(gid, "sensor", True, 0.0)
        data = db.get_test_data("T", date)
        assert data[0]["value"] == 1
        assert isinstance(data[0]["value"], int)

    def test_get_test_data_sorted_by_time(self, db):
        date = self._date()
        gid = db.save_test("T", date)
        db.save_test_sensor_value(gid, "s", 3, 3.0)
        db.save_test_sensor_value(gid, "s", 1, 1.0)
        db.save_test_sensor_value(gid, "s", 2, 2.0)
        data = db.get_test_data("T", date)
        times = [d["time"] for d in data]
        assert times == sorted(times)

    def test_get_test_data_skip(self, db):
        date = self._date()
        gid = db.save_test("T", date)
        for i in range(5):
            db.save_test_sensor_value(gid, "s", i, float(i))
        data = db.get_test_data("T", date, skip=3)
        assert len(data) == 2

    def test_get_filtered_test_data(self, db):
        date = self._date()
        gid = db.save_test("T", date)
        db.save_test_sensor_value(gid, "a", 1.0, 0.0)
        db.save_test_sensor_value(gid, "b", 2.0, 0.0)
        db.save_test_sensor_value(gid, "c", 3.0, 0.0)
        result = db.get_filtered_test_data("T", date, ["a", "c"])
        sensors = {r["sensor"] for r in result}
        assert sensors == {"a", "c"}

    def test_remove_single_test(self, db):
        date = self._date()
        gid = db.save_test("T", date)
        db.save_test_sensor_value(gid, "s", 1, 0.0)
        db.remove_test({"name": "T", "date": date})
        assert db.list_test_data() == []

    def test_remove_multiple_tests(self, db):
        import datetime
        d1 = datetime.datetime(2024, 1, 1)
        d2 = datetime.datetime(2024, 1, 2)
        db.save_test("A", d1)
        db.save_test("B", d2)
        db.remove_test([{"name": "A", "date": d1}, {"name": "B", "date": d2}])
        assert db.list_test_data() == []


# ---------------------------------------------------------------------------
# Dump / restore
# ---------------------------------------------------------------------------


class TestDumpRestore:
    def test_dump_returns_settings_and_graphs(self, db):
        settings, graphs = db.dump_database()
        # "version" is set by __init__
        assert any(s["key"] == "version" for s in settings)
        assert isinstance(graphs, list)

    def test_restore_v2_roundtrip(self, db):
        import datetime
        date = datetime.datetime(2024, 6, 1)
        gid = db.save_test("Sim", date)
        db.save_test_sensor_value(gid, "y", 1.0, 0.0)
        db.set_setting("controllers", [{"id": 1, "name": "ctrl"}])

        settings, graphs = db.dump_database()
        db.restore_database_v2(settings, graphs)

        tests = db.list_test_data()
        assert any(t["name"] == "Sim" for t in tests)
        assert db.get_setting("controllers") == [{"id": 1, "name": "ctrl"}]
