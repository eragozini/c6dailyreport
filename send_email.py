#!/usr/bin/env python3
"""Envia um PDF de fechamento por SMTP com validação explícita."""

from __future__ import annotations

import argparse
import os
import re
import smtplib
import ssl
from datetime import date, datetime
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"variável obrigatória ausente: {name}")
    return value


def recipient_list(*groups: str) -> list[str]:
    """Combina listas separadas por vírgula, removendo vazios e duplicados."""
    recipients: dict[str, str] = {}
    for group in groups:
        for raw_address in group.split(","):
            address = raw_address.strip()
            if address:
                recipients.setdefault(address.casefold(), address)
    return list(recipients.values())


def report_date_from_path(path: Path) -> date:
    match = re.fullmatch(r"fechamento_(\d{8})\.pdf", path.name)
    if not match:
        raise ValueError("o PDF deve seguir o nome fechamento_YYYYMMDD.pdf ou receber --report-date")
    return datetime.strptime(match.group(1), "%Y%m%d").date()


def build_message(pdf_path: Path, report_date: date, sender: str, recipients: list[str]) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message["Date"] = formatdate(localtime=True)
    message["Subject"] = f"Fechamento de Mercado — {report_date:%d/%m/%Y}"
    message.set_content(
        "Segue em anexo o fechamento diário de mercado.\n\n"
        "Documento informativo; não constitui recomendação de investimento."
    )
    message.add_attachment(
        pdf_path.read_bytes(),
        maintype="application",
        subtype="pdf",
        filename=f"fechamento_{report_date:%d_%m_%Y}.pdf",
    )
    return message


def send(message: EmailMessage, recipients: list[str]) -> None:
    host = required_env("SMTP_HOST")
    port = int(required_env("SMTP_PORT"))
    user = required_env("SMTP_USER")
    password = required_env("SMTP_PASS")
    timeout = float(os.getenv("SMTP_TIMEOUT", "30"))
    security = os.getenv("SMTP_SECURITY", "starttls").strip().lower()
    context = ssl.create_default_context()

    if security == "ssl":
        client: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
    elif security in {"starttls", "none"}:
        client = smtplib.SMTP(host, port, timeout=timeout)
    else:
        raise RuntimeError("SMTP_SECURITY deve ser starttls, ssl ou none")

    with client:
        if security == "starttls":
            client.starttls(context=context)
        client.login(user, password)
        refused = client.send_message(message, from_addr=message["From"], to_addrs=recipients)
    if refused:
        addresses = ", ".join(sorted(refused))
        raise RuntimeError(f"SMTP recusou destinatários: {addresses}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--report-date", type=date.fromisoformat)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf_path = args.pdf.resolve()
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        raise FileNotFoundError(f"PDF não encontrado: {pdf_path}")

    recipients = recipient_list(required_env("SMTP_TO"), os.getenv("SMTP_EXTRA_TO", ""))
    if not recipients:
        raise RuntimeError("SMTP_TO não contém destinatários válidos")
    sender = os.getenv("SMTP_FROM", required_env("SMTP_USER")).strip()
    report_date = args.report_date or report_date_from_path(pdf_path)
    message = build_message(pdf_path, report_date, sender, recipients)
    send(message, recipients)
    print(f"Enviado para {len(recipients)} destinatário(s): fechamento de {report_date:%d/%m/%Y}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
