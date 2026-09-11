from datetime import date

import pandas as pd
import pytest

from market_data import MarketDataError, _parse_b3_number, calculate_metric


def test_calculate_metric_uses_previous_month_and_year_closes() -> None:
    closes = pd.Series(
        [100.0, 110.0, 120.0, 121.0, 132.0],
        index=pd.to_datetime(["2025-12-30", "2026-01-02", "2026-08-31", "2026-09-01", "2026-09-10"]),
    )

    metric = calculate_metric(closes, "fixture")

    assert metric.as_of == date(2026, 9, 10)
    assert metric.day_change == pytest.approx((132 / 121 - 1) * 100)
    assert metric.month_change == pytest.approx(10.0)
    assert metric.year_change == pytest.approx(32.0)


def test_calculate_metric_rejects_missing_period_bases() -> None:
    closes = pd.Series(
        [100.0, 101.0],
        index=pd.to_datetime(["2026-09-01", "2026-09-02"]),
    )

    with pytest.raises(MarketDataError, match="histórico insuficiente"):
        calculate_metric(closes, "fixture")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("3.746,97", 3746.97), ("102,50", 102.5), (None, None), ("", None)],
)
def test_parse_b3_number(raw: object, expected: float | None) -> None:
    assert _parse_b3_number(raw) == expected
