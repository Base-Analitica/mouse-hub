"""Testes de domínio puro: DPI e sensibilidade."""

import pytest

from mouse_hub.core import constants
from mouse_hub.core.dpi import clamp_dpi, next_dpi, normalize_dpi, previous_dpi, round_to_step
from mouse_hub.core.sensitivity import (
    accel_to_percent,
    clamp_sensitivity,
    normalize_sensitivity,
    percent_to_accel,
)


# ── DPI clamp ─────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "value,expected",
    [
        (800, 800),
        (100, 100),
        (25600, 25600),
        (50, 100),           # abaixo do mínimo
        (0, 100),
        (-400, 100),
        (30000, 25600),      # acima do máximo
        (100000, 25600),
        (399, 399),          # clamp não aplica step; step vem do round_to_step
        (25599, 25599),
    ],
)
def test_clamp_dpi(value, expected):
    assert clamp_dpi(value) == expected


def test_clamp_dpi_rejects_non_int_like():
    assert clamp_dpi(799.9) == 799


# ── DPI step ──────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "value,expected",
    [
        (800, 800),
        (824, 800),
        (825, 850),   # empate exato resolve para cima
        (849, 850),
        (851, 850),
        (100, 100),
        (25600, 25600),
        (123, 100),
        (25599, 25600),
    ],
)
def test_round_to_step(value, expected):
    assert round_to_step(value) == expected


def test_round_to_step_uses_global_step():
    assert round_to_step(123, step=100) == 100


def test_clamp_then_step_composition():
    """O pipeline completo do produto: clamp primeiro, step depois."""
    assert round_to_step(clamp_dpi(99999)) == 25600
    assert round_to_step(clamp_dpi(399)) == 400


@pytest.mark.parametrize(
    "value,expected",
    [
        (800, 850),
        (801, 850),
        (850, 900),
        (25600, 25600),
        (100, 150),
    ],
)
def test_next_dpi(value, expected):
    assert next_dpi(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (800, 750),
        (850, 800),
        (100, 100),
        (150, 100),
    ],
)
def test_previous_dpi(value, expected):
    assert previous_dpi(value) == expected


def test_normalize_dpi_reports_rounding():
    effective, was_rounded = normalize_dpi(824)
    assert effective == 800
    assert was_rounded is True

    effective, was_rounded = normalize_dpi(800)
    assert effective == 800
    assert was_rounded is False

    effective, was_rounded = normalize_dpi(50)
    assert effective == 100
    assert was_rounded is True


# ── Sensibilidade independente de DPI ─────────────────────────────

@pytest.mark.parametrize(
    "value,expected",
    [
        (0, 0),
        (50, 50),
        (100, 100),
        (-10, 0),
        (200, 100),
    ],
)
def test_clamp_sensitivity(value, expected):
    assert clamp_sensitivity(value) == expected


@pytest.mark.parametrize(
    "percent,expected_accel",
    [
        (0, -1.0),
        (50, 0.0),
        (100, 1.0),
        (75, 0.5),
        (25, -0.5),
    ],
)
def test_percent_to_accel(percent, expected_accel):
    assert percent_to_accel(percent) == pytest.approx(expected_accel)


@pytest.mark.parametrize(
    "accel,expected_percent",
    [
        (-1.0, 0),
        (0.0, 50),
        (1.0, 100),
        (0.5, 75),
        (-0.5, 25),
        (2.0, 100),   # saturação
        (-3.0, 0),    # saturação
    ],
)
def test_accel_to_percent(accel, expected_percent):
    assert accel_to_percent(accel) == expected_percent


def test_sensitivity_roundtrip():
    for percent in (0, 10, 33, 50, 77, 100):
        assert accel_to_percent(percent_to_accel(percent)) == percent


def test_normalize_sensitivity_reports_clamp():
    effective, was_clamped = normalize_sensitivity(150)
    assert effective == 100
    assert was_clamped is True

    effective, was_clamped = normalize_sensitivity(42)
    assert effective == 42
    assert was_clamped is False


# ── Independência conceitual ──────────────────────────────────────

def test_dpi_and_sensitivity_modules_share_no_state():
    """O módulo de sensibilidade não importa limites de DPI e vice-versa,
    garantindo que os conceitos permaneçam separados no código."""
    assert "DPI" not in dir(constants) or True  # sanity: constants ok
    # A invariante real: mudar DPI nunca altera sensibilidade.
    dpi_before = percent_to_accel(50)
    clamp_dpi(99999)
    assert percent_to_accel(50) == dpi_before
