import json
from datetime import date, datetime

from build_single_page import H, W, build, write_artifacts
from market_data import BRT, INSTRUMENTS, MarketMetric, MarketSnapshot


def fixture_snapshot() -> MarketSnapshot:
    keys = [instrument.key for instrument in INSTRUMENTS] + ["ifix"]
    metrics = {
        key: MarketMetric(
            value=1000.0 + index,
            day_change=(-1) ** index * 0.5,
            month_change=1.25,
            year_change=8.75,
            as_of=date(2026, 9, 10),
            source="fixture",
        )
        for index, key in enumerate(keys)
    }
    return MarketSnapshot(
        generated_at=datetime(2026, 9, 10, 19, 0, tzinfo=BRT),
        report_date=date(2026, 9, 10),
        metrics=metrics,
        di_ytd=9.87,
        warnings=[],
    )


def test_build_has_expected_dimensions() -> None:
    image = build(fixture_snapshot())
    assert image.size == (W, H)
    assert image.mode == "RGB"


def test_write_artifacts_includes_audit_json(tmp_path) -> None:
    pdf, png, audit = write_artifacts(fixture_snapshot(), tmp_path)

    assert pdf.read_bytes().startswith(b"%PDF")
    assert png.read_bytes().startswith(b"\x89PNG")
    document = json.loads(audit.read_text(encoding="utf-8"))
    assert document["report_date"] == "2026-09-10"
    assert document["metrics"]["ifix"]["source"] == "fixture"
