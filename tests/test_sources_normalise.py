import pytest

from rate_card.sources._normalise import round_per_million

_TOKENS_PER_MILLION = 1_000_000


@pytest.mark.parametrize(
    ("cost_per_token", "expected"),
    [
        (4e-07, 0.4),
        (1e-07, 0.1),
        (8e-07, 0.8),
        (1.25e-07, 0.125),
        (2.5e-08, 0.025),
        (3e-06, 3.0),
    ],
)
def test_round_per_million_fp_noise(cost_per_token: float, expected: float) -> None:
    result = round_per_million(cost_per_token * _TOKENS_PER_MILLION)
    assert result == expected


def test_round_per_million_zero() -> None:
    assert round_per_million(0.0) == 0.0


def test_round_per_million_exact_integer() -> None:
    assert round_per_million(15.0) == 15.0


def test_round_per_million_six_decimal_precision() -> None:
    result = round_per_million(1.1234567)
    assert result == 1.123457


def test_round_per_million_large_value() -> None:
    assert round_per_million(1000.0) == 1000.0
