from datetime import date

import pytest

from send_email import build_message, report_date_from_path


def test_report_date_is_read_from_exact_filename(tmp_path) -> None:
    path = tmp_path / "fechamento_20260910.pdf"
    assert report_date_from_path(path) == date(2026, 9, 10)


def test_report_date_rejects_ambiguous_filename(tmp_path) -> None:
    with pytest.raises(ValueError):
        report_date_from_path(tmp_path / "latest.pdf")


def test_message_has_pdf_and_report_date(tmp_path) -> None:
    pdf = tmp_path / "fechamento_20260910.pdf"
    pdf.write_bytes(b"%PDF-fixture")

    message = build_message(pdf, date(2026, 9, 10), "from@example.com", ["to@example.com"])

    assert "10/09/2026" in message["Subject"]
    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "fechamento_10_09_2026.pdf"
