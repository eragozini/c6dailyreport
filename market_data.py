"""Coleta, validação e cálculo dos dados do fechamento diário."""

from __future__ import annotations

import base64
import json
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

BRT = ZoneInfo("America/Sao_Paulo")
HTTP_HEADERS = {"User-Agent": "c6dailyreport/2.0 (+https://github.com/eragozini/c6dailyreport)"}


@dataclass(frozen=True)
class Instrument:
    key: str
    symbol: str
    label: str
    value_format: Literal["points0", "points2", "brl2", "fx4", "usd2", "usd4"]
    critical: bool = True


@dataclass(frozen=True)
class MarketMetric:
    value: float
    day_change: float
    month_change: float
    year_change: float
    as_of: date
    source: str


@dataclass
class MarketSnapshot:
    generated_at: datetime
    report_date: date
    metrics: dict[str, MarketMetric]
    di_ytd: float | None
    warnings: list[str]

    def as_dict(self) -> dict:
        result = asdict(self)
        result["generated_at"] = self.generated_at.isoformat()
        result["report_date"] = self.report_date.isoformat()
        for metric in result["metrics"].values():
            metric["as_of"] = metric["as_of"].isoformat()
        return result


INSTRUMENTS = (
    Instrument("ibov", "^BVSP", "Ibovespa", "points0"),
    Instrument("smal11", "SMAL11.SA", "SMAL11", "brl2"),
    Instrument("sp500", "^GSPC", "S&P 500", "points2"),
    Instrument("dow", "^DJI", "Dow Jones", "points2"),
    Instrument("nasdaq", "^IXIC", "Nasdaq", "points2"),
    Instrument("vix", "^VIX", "VIX", "points2"),
    Instrument("usd_brl", "BRL=X", "USD/BRL", "brl2"),
    Instrument("eur_brl", "EURBRL=X", "EUR/BRL", "brl2"),
    Instrument("gbp_brl", "GBPBRL=X", "GBP/BRL", "brl2"),
    Instrument("eur_usd", "EURUSD=X", "EUR/USD", "fx4"),
    Instrument("gbp_usd", "GBPUSD=X", "GBP/USD", "fx4"),
    Instrument("dxy", "DX-Y.NYB", "Dollar Index (DXY)", "points2"),
    Instrument("wti", "CL=F", "WTI Crude", "usd2"),
    Instrument("brent", "BZ=F", "Brent Crude", "usd2"),
    Instrument("gold", "GC=F", "Gold", "usd2"),
    Instrument("silver", "SI=F", "Silver", "usd2"),
    Instrument("copper", "HG=F", "Copper", "usd4"),
)


class MarketDataError(RuntimeError):
    """Dados insuficientes ou incoerentes para publicar o relatório."""


def _normalized_close(frame: pd.DataFrame | pd.Series) -> pd.Series:
    close = frame["Close"] if isinstance(frame, pd.DataFrame) else frame
    close = pd.to_numeric(close, errors="coerce").dropna().astype(float)
    if isinstance(close.index, pd.DatetimeIndex):
        close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close[~close.index.duplicated(keep="last")].sort_index()


def _download_yahoo(start: date, end: date, attempts: int = 3) -> dict[str, pd.Series]:
    symbols = [instrument.symbol for instrument in INSTRUMENTS]
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            frame = yf.download(
                symbols,
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                auto_adjust=False,
                actions=False,
                progress=False,
                group_by="ticker",
                threads=True,
                timeout=20,
            )
            if frame.empty:
                raise MarketDataError("Yahoo Finance retornou uma tabela vazia")
            series: dict[str, pd.Series] = {}
            for instrument in INSTRUMENTS:
                try:
                    ticker_frame = frame[instrument.symbol]
                    close = _normalized_close(ticker_frame)
                except (KeyError, TypeError):
                    close = pd.Series(dtype=float)
                if not close.empty:
                    series[instrument.key] = close
            missing = [instrument.symbol for instrument in INSTRUMENTS if instrument.key not in series]
            if not missing:
                return series
            raise MarketDataError("tickers ausentes no Yahoo Finance: " + ", ".join(missing))
        except Exception as exc:  # yfinance levanta exceções de vários tipos
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise MarketDataError(f"falha ao consultar Yahoo Finance: {last_error}")


def _parse_b3_number(raw: object) -> float | None:
    if raw in (None, ""):
        return None
    try:
        return float(Decimal(str(raw).replace(".", "").replace(",", ".")))
    except InvalidOperation as exc:
        raise MarketDataError(f"valor inválido retornado pela B3: {raw!r}") from exc


def _fetch_b3_index_year(code: str, year: int, attempts: int = 3) -> pd.Series:
    payload = base64.b64encode(
        json.dumps(
            {"language": "pt-br", "index": code, "year": str(year)},
            separators=(",", ":"),
        ).encode()
    ).decode()
    url = f"https://sistemaswebb3-listados.b3.com.br/indexStatisticsProxy/IndexCall/GetPortfolioDay/{payload}"
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = requests.get(url, headers=HTTP_HEADERS, timeout=20)
            response.raise_for_status()
            document = response.json()
            points: dict[pd.Timestamp, float] = {}
            for row in document.get("results", []):
                day = int(row["day"])
                for month in range(1, 13):
                    value = _parse_b3_number(row.get(f"rateValue{month}"))
                    if value is None:
                        continue
                    try:
                        observed = date(year, month, day)
                    except ValueError:
                        continue
                    points[pd.Timestamp(observed)] = value
            if not points:
                raise MarketDataError(f"B3 não retornou observações para {code}/{year}")
            return pd.Series(points, dtype=float).sort_index()
        except (requests.RequestException, ValueError, KeyError, MarketDataError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise MarketDataError(f"falha ao consultar o índice {code} na B3: {last_error}")


def fetch_b3_ifix(start: date, end: date) -> pd.Series:
    """Obtém o IFIX real em pontos, sem usar ETF como proxy."""
    yearly = [_fetch_b3_index_year("IFIX", year) for year in range(start.year, end.year + 1)]
    combined = pd.concat(yearly).sort_index()
    return combined.loc[pd.Timestamp(start) : pd.Timestamp(end)]


def calculate_metric(series: pd.Series, source: str) -> MarketMetric:
    close = _normalized_close(series)
    if len(close) < 2:
        raise MarketDataError(f"{source}: menos de dois fechamentos disponíveis")

    latest_at = close.index[-1]
    latest = float(close.iloc[-1])
    previous = float(close.iloc[-2])
    month_start = pd.Timestamp(latest_at.year, latest_at.month, 1)
    year_start = pd.Timestamp(latest_at.year, 1, 1)
    before_month = close.loc[close.index < month_start]
    before_year = close.loc[close.index < year_start]
    if before_month.empty or before_year.empty:
        raise MarketDataError(f"{source}: histórico insuficiente para MTD/YTD")

    month_base = float(before_month.iloc[-1])
    year_base = float(before_year.iloc[-1])
    return MarketMetric(
        value=latest,
        day_change=(latest / previous - 1) * 100,
        month_change=(latest / month_base - 1) * 100,
        year_change=(latest / year_base - 1) * 100,
        as_of=latest_at.date(),
        source=source,
    )


def fetch_di_ytd(report_date: date) -> float:
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados"
    params = {
        "formato": "json",
        "dataInicial": date(report_date.year, 1, 1).strftime("%d/%m/%Y"),
        "dataFinal": report_date.strftime("%d/%m/%Y"),
    }
    try:
        response = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=20)
        response.raise_for_status()
        observations = response.json()
        if not observations:
            raise MarketDataError("BCB não retornou a série Selic diária")
        factor = Decimal("1")
        for observation in observations:
            factor *= Decimal("1") + Decimal(observation["valor"].replace(",", ".")) / 100
        return float((factor - 1) * 100)
    except (requests.RequestException, ValueError, KeyError, InvalidOperation) as exc:
        raise MarketDataError(f"falha ao consultar a Selic diária no BCB: {exc}") from exc


def fetch_market_snapshot(now: datetime | None = None) -> MarketSnapshot:
    generated_at = now.astimezone(BRT) if now else datetime.now(BRT)
    through = generated_at.date()
    start = date(through.year - 1, 12, 1)
    yahoo_series = _download_yahoo(start, through)

    metrics: dict[str, MarketMetric] = {}
    errors: list[str] = []
    for instrument in INSTRUMENTS:
        try:
            metrics[instrument.key] = calculate_metric(
                yahoo_series[instrument.key], f"Yahoo Finance ({instrument.symbol})"
            )
        except (KeyError, MarketDataError) as exc:
            if instrument.critical:
                errors.append(f"{instrument.label}: {exc}")

    try:
        metrics["ifix"] = calculate_metric(fetch_b3_ifix(start, through), "B3 (IFIX)")
    except MarketDataError as exc:
        errors.append(f"IFIX: {exc}")

    if errors:
        raise MarketDataError("dados críticos ausentes:\n- " + "\n- ".join(errors))

    report_date = metrics["ibov"].as_of
    warnings = [
        f"{key}: fechamento de {metric.as_of:%d/%m/%Y}, diferente da data-base do relatório"
        for key, metric in metrics.items()
        if metric.as_of != report_date
    ]
    return MarketSnapshot(
        generated_at=generated_at,
        report_date=report_date,
        metrics=metrics,
        di_ytd=fetch_di_ytd(report_date),
        warnings=warnings,
    )
