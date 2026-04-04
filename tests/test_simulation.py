"""
Tests for ModelSimulation (moirai/hardware/model_simulation.py).

The simulation class internally creates a DatabaseV1 and saves results —
those writes go to mongomock thanks to the autouse fixture in conftest.py.
"""

import json
import math

import pytest

from moirai.hardware.model_simulation import ModelSimulation


def run(model, x0="[]", u="1", duration="5"):
    data = {"model": model, "x0": x0, "u": u, "duration": duration}
    return json.loads(ModelSimulation(data).run())


# ---------------------------------------------------------------------------
# Transfer function (2-element model list)
# ---------------------------------------------------------------------------


class TestTransferFunction:
    def test_first_order_returns_y(self):
        result = run("[[1],[1,1]]")
        assert "error" not in result
        assert "y" in result
        assert "t" in result
        assert "u" in result

    def test_output_length_matches_time(self):
        result = run("[[1],[1,1]]")
        assert len(result["y"]) == len(result["t"])

    def test_step_response_increases_monotonically(self):
        result = run("[[1],[1,1]]", u="1", duration="20")
        y = result["y"]
        # DC gain of 1/(s+1) is 1; output should approach 1
        assert all(y[i] <= y[i + 1] + 1e-9 for i in range(len(y) - 1))

    def test_step_response_dc_gain(self):
        # First-order TF 1/(s+1): DC gain = 1
        result = run("[[1],[1,1]]", u="1", duration="30")
        assert math.isclose(result["y"][-1], 1.0, abs_tol=0.05)

    def test_time_starts_at_zero(self):
        result = run("[[1],[1,1]]")
        assert result["t"][0] == pytest.approx(0.0)

    def test_u_list_preserved(self):
        u_values = [1, 1, 0, 0, 1]
        result = run("[[1],[1,1]]", u=str(u_values), duration=str(len(u_values)))
        assert result["u"] == u_values


# ---------------------------------------------------------------------------
# Continuous state-space (4-element model list)
# ---------------------------------------------------------------------------


class TestContinuousStateSpace:
    def test_ss_returns_y_and_x(self):
        # Single-state, single-output: A=[-1], B=[1], C=[1], D=[0]
        # x0 as column vector [[0]] to avoid broadcast issues
        result = run("[[-1],[1],[1],[0]]", x0="[[0]]")
        assert "error" not in result
        assert "y" in result
        assert "x1" in result

    def test_ss_output_matches_tf(self):
        # 1/(s+1) in SS form, column-vector x0
        tf_result = run("[[1],[1,1]]", duration="20")
        ss_result = run("[[-1],[1],[1],[0]]", x0="[[0]]", duration="20")
        assert math.isclose(tf_result["y"][-1], ss_result["y"][-1], rel_tol=0.05)

    def test_multiple_states(self):
        # Stable 2-state system: diagonal A, column-vector x0
        # A=[[-1,0],[0,-2]], B=[[1],[1]], C=[[1,0]], D=[[0]]
        model = "[[[-1,0],[0,-2]],[[1],[1]],[[1,0]],[[0]]]"
        result = run(model, x0="[[0],[0]]", duration="10")
        assert "error" not in result
        assert "x1" in result
        assert "x2" in result


# ---------------------------------------------------------------------------
# Discrete state-space (5-element model list with dt)
# ---------------------------------------------------------------------------


class TestDiscreteStateSpace:
    def test_discrete_ss_returns_y(self):
        # Discrete: A=[0.9], B=[0.1], C=[1], D=[0], dt=0.1
        # Column-vector x0
        result = run("[[0.9],[0.1],[1],[0],0.1]", x0="[[0]]", duration="10")
        assert "error" not in result
        assert "y" in result

    def test_discrete_ss_monotone_approach(self):
        result = run("[[0.9],[0.1],[1],[0],0.1]", x0="[[0]]", duration="30")
        y = result["y"]
        assert all(y[i] <= y[i + 1] + 1e-9 for i in range(len(y) - 1))


# ---------------------------------------------------------------------------
# Multiple outputs
# ---------------------------------------------------------------------------


class TestMultipleOutputs:
    def test_two_outputs(self):
        # 2-state, 2-output diagonal system
        # A=[[-1,0],[0,-2]], B=[[1],[1]], C=[[1,0],[0,1]], D=[[0],[0]]
        model = "[[[-1,0],[0,-2]],[[1],[1]],[[1,0],[0,1]],[[0],[0]]]"
        result = run(model, x0="[[0],[0]]", duration="5")
        assert "error" not in result
        assert "y1" in result
        assert "y2" in result
        assert "y" not in result  # single 'y' key only when C has 1 row


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestSimulationErrors:
    def test_invalid_model(self):
        result = run("this is not python", x0="[0]")
        assert result.get("error") == "Invalid Model"

    def test_invalid_x0(self):
        result = run("[[1],[1,1]]", x0="not_valid")
        assert result.get("error") == "Invalid x0"

    def test_invalid_u(self):
        result = run("[[1],[1,1]]", x0="[]", u="not_valid_u")
        assert result.get("error") == "Invalid U"

    def test_invalid_duration(self):
        result = run("[[1],[1,1]]", x0="[]", u="1", duration="abc")
        assert result.get("error") == "Invalid Duration"
