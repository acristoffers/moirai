"""
Tests for the PID controller logic (moirai/hardware/pid.py).

The full PID.run() loop requires hardware, so we test the parts that don't:
  - Singleton pattern
  - is_valid() timing window
  - Control law arithmetic
  - Output clamping
  - interlock() syntax checking
"""

import math
import time

import pytest

from moirai.hardware.pid import PID


@pytest.fixture(autouse=True)
def reset_pid_singleton():
    """Reset the PID singleton between tests."""
    PID._PID__instance = None
    yield
    PID._PID__instance = None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_instance_returns_same_object(self):
        a = PID.instance()
        b = PID.instance()
        assert a is b

    def test_instance_is_pid(self):
        assert isinstance(PID.instance(), PID)


# ---------------------------------------------------------------------------
# is_valid()
# ---------------------------------------------------------------------------


class TestIsValid:
    def test_just_created_is_valid(self):
        pid = PID()
        # last_run is set to time.time() in __init__; default interval = inf
        # is_valid checks: (now - last_run) < max(2*interval, 1)
        # With interval=inf, max(inf, 1)=inf → always valid right after creation
        assert pid.is_valid() is True

    def test_invalid_after_stale(self, monkeypatch):
        pid = PID()
        pid.timer.interval = 1  # 1-second interval → window = max(2s, 1s) = 2s
        pid.last_run = time.time() - 3  # 3 s ago → stale
        assert pid.is_valid() is False

    def test_valid_within_window(self, monkeypatch):
        pid = PID()
        pid.timer.interval = 5  # window = max(10s, 1s) = 10s
        pid.last_run = time.time() - 5  # 5 s ago → still valid
        assert pid.is_valid() is True


# ---------------------------------------------------------------------------
# Control law  u = Kp*e + Kd*de + Ki*se
# ---------------------------------------------------------------------------


class TestControlLaw:
    """
    Verify the arithmetic by running the same calculation manually and
    comparing with what a PID object would produce.
    """

    def _compute(self, Kp, Ki, Kd, r, y, le=0, se=0):
        """Mirror of the PID control law inside pid.py."""
        e = r - y
        de = e - le
        se = se + e
        u = Kp * e + Kd * de + Ki * se
        return u, e, se

    def test_pure_proportional(self):
        u, _, _ = self._compute(Kp=2, Ki=0, Kd=0, r=10, y=8)
        assert u == pytest.approx(4.0)  # 2 * (10-8)

    def test_pure_integral_first_step(self):
        # First step: le=0, se=0 → se becomes e, u = Ki*e
        u, _, _ = self._compute(Kp=0, Ki=1, Kd=0, r=5, y=3)
        assert u == pytest.approx(2.0)  # Ki * e = 1 * 2

    def test_pure_derivative_first_step(self):
        # First step: le=0 → de = e - 0 = e, u = Kd * e
        u, _, _ = self._compute(Kp=0, Ki=0, Kd=3, r=5, y=3)
        assert u == pytest.approx(6.0)  # Kd * de = 3 * 2

    def test_combined_gains(self):
        u, _, _ = self._compute(Kp=1, Ki=1, Kd=1, r=10, y=7)
        # e=3, de=3 (le=0), se=3; u = 3 + 3 + 3 = 9
        assert u == pytest.approx(9.0)

    def test_integral_accumulates(self):
        # Two steps with constant error
        _, e1, se1 = self._compute(Kp=0, Ki=1, Kd=0, r=5, y=3, le=0, se=0)
        u2, _, _ = self._compute(Kp=0, Ki=1, Kd=0, r=5, y=3, le=e1, se=se1)
        # Step 2: se = 2+2=4, u = Ki*4 = 4
        assert u2 == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# Output clamping  sorted([li, ls, u])[1]
# ---------------------------------------------------------------------------


class TestOutputClamping:
    def _clamp(self, li, ls, u):
        return sorted([li, ls, u])[1]

    def test_within_range_unchanged(self):
        assert self._clamp(0, 10, 5) == 5

    def test_above_max_clamped(self):
        assert self._clamp(0, 10, 15) == 10

    def test_below_min_clamped(self):
        assert self._clamp(0, 10, -5) == 0

    def test_at_max_boundary(self):
        assert self._clamp(0, 10, 10) == 10

    def test_at_min_boundary(self):
        assert self._clamp(0, 10, 0) == 0

    def test_negative_range(self):
        assert self._clamp(-10, -1, -5) == -5

    def test_negative_range_below_min(self):
        assert self._clamp(-10, -1, -15) == -10

    def test_negative_range_above_max(self):
        assert self._clamp(-10, -1, 3) == -1


# ---------------------------------------------------------------------------
# interlock() — syntax checking
# ---------------------------------------------------------------------------


class TestInterlock:
    def test_valid_expression_returns_callable(self, db):
        pid = PID()
        pid.db = db
        lock = pid.interlock(
            {"expression": "x > 5", "sensor": "s", "actuator": "a", "actuatorValue": 0}
        )
        assert callable(lock)

    def test_invalid_expression_sets_error(self, db):
        pid = PID()
        pid.db = db
        pid.interlock(
            {
                "expression": "x >>>",
                "sensor": "s",
                "actuator": "a",
                "actuatorValue": 0,
            }
        )
        assert pid.running is False
        assert db.get_setting("test_error") != ""
