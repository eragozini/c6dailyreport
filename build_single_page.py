#!/usr/bin/env python3
"""Gera o fechamento diário em PNG, PDF e JSON auditável."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from market_data import BRT, INSTRUMENTS, MarketDataError, MarketMetric, MarketSnapshot, fetch_market_snapshot

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "assets" / "template_cover.png"
DEFAULT_OUT = HERE / "out"

FL = str(HERE / "assets" / "fonts" / "Poppins-Light.ttf")
FR = str(HERE / "assets" / "fonts" / "Poppins-Regular.ttf")
FM = str(HERE / "assets" / "fonts" / "Poppins-Medium.ttf")
FB = str(HERE / "assets" / "fonts" / "Poppins-Bold.ttf")

W, H = 2160, 3840
UP = (74, 222, 128)
DOWN = (248, 113, 113)
WHITE = (255, 255, 255)
LGRAY = (200, 200, 200)
MGRAY = (130, 130, 130)
DIM = (80, 80, 80)
BG = (0, 0, 0)
CA = (34, 34, 34)
CB = (22, 22, 22)
SEP = (50, 50, 50)

MARGIN_L = 140
MARGIN_R = 2020
COV_DIA_CX = 834
COV_MES_CX = 1120
COV_ANO_CX = 1414
COV_VAL_RX = 1980
COL_GAP = 60
COL_W = (MARGIN_R - MARGIN_L - COL_GAP) // 2
COL_X = [MARGIN_L, MARGIN_L + COL_W + COL_GAP]

FORMATS = {instrument.key: instrument.value_format for instrument in INSTRUMENTS}
FORMATS["ifix"] = "points2"


def fnt(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def pct2(value: float | None) -> str:
    if value is None:
        return "—"
    return (("+" if value >= 0 else "") + f"{value:.2f}%").replace(".", ",")


def color_for(value: float | None) -> tuple[int, int, int]:
    if value is None:
        return MGRAY
    return UP if value >= 0 else DOWN


def br_number(value: float, decimals: int) -> str:
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_value(key: str, value: float | None) -> str:
    if value is None:
        return "—"
    kind = FORMATS[key]
    if kind == "points0":
        return br_number(value, 0)
    if kind == "points2":
        return br_number(value, 2)
    if kind == "brl2":
        return f"R$ {br_number(value, 2)}"
    if kind == "fx4":
        return br_number(value, 4)
    if kind == "usd2":
        return f"US$ {br_number(value, 2)}"
    if kind == "usd4":
        return f"US$ {br_number(value, 4)}"
    raise ValueError(f"formato desconhecido: {kind}")


def hline(
    draw: ImageDraw.ImageDraw,
    y: int,
    x0: int = 140,
    x1: int = 2020,
    color: tuple[int, int, int] = SEP,
    width: int = 2,
) -> None:
    draw.line([(x0, y), (x1, y)], fill=color, width=width)


def tl(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    yc: int,
    font: ImageFont.FreeTypeFont,
    color: tuple[int, int, int],
) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    draw.text((x - box[0], yc - (box[3] - box[1]) // 2 - box[1]), text, font=font, fill=color)


def tc(
    draw: ImageDraw.ImageDraw,
    text: str,
    cx: int,
    yc: int,
    font: ImageFont.FreeTypeFont,
    color: tuple[int, int, int],
) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(
        (cx - (box[2] - box[0]) // 2 - box[0], yc - (box[3] - box[1]) // 2 - box[1]),
        text,
        font=font,
        fill=color,
    )


def tr(
    draw: ImageDraw.ImageDraw,
    text: str,
    rx: int,
    yc: int,
    font: ImageFont.FreeTypeFont,
    color: tuple[int, int, int],
) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(
        (rx - (box[2] - box[0]) - box[0], yc - (box[3] - box[1]) // 2 - box[1]),
        text,
        font=font,
        fill=color,
    )


def clip(draw: ImageDraw.ImageDraw, text: str, max_px: int, font: ImageFont.FreeTypeFont) -> str:
    if draw.textlength(text, font=font) <= max_px:
        return text
    while len(text) > 2:
        text = text[:-1]
        if draw.textlength(text + "…", font=font) <= max_px:
            return text + "…"
    return text


def dcx(cx: int) -> int:
    return cx + int(COL_W * 0.61)


def vrx(cx: int) -> int:
    return cx + COL_W - 8


def nm_max(_cx: int) -> int:
    return int(COL_W * 0.46)


def build(snapshot: MarketSnapshot) -> Image.Image:
    """Renderiza uma imagem sem realizar chamadas de rede."""
    metrics = snapshot.metrics
    img = Image.new("RGB", (W, H), BG)

    with Image.open(TEMPLATE) as template:
        tpl = template.convert("RGBA")
        logo = tpl.crop((820, 660, 1340, 755))
    lw, lh = int(logo.width * 1.55), int(logo.height * 1.55)
    logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)
    logo_y = 110
    img.paste(logo.convert("RGB"), (MARGIN_L, logo_y), mask=logo.getchannel("A"))

    draw = ImageDraw.Draw(img)
    title_size = 148
    line_gap = 162
    title_y1 = logo_y + lh + 140 + title_size // 2
    title_y2 = title_y1 + line_gap

    tl(draw, "Fechamento", MARGIN_L, title_y1, fnt(FL, title_size), WHITE)
    tl(draw, "diário", MARGIN_L, title_y2, fnt(FB, title_size), WHITE)

    date_str = snapshot.report_date.strftime("%d/%m/%y")
    pill_font = fnt(FR, 74)
    box = draw.textbbox((0, 0), date_str, font=pill_font)
    pw, ph = box[2] - box[0], box[3] - box[1]
    prx = MARGIN_R
    plx = prx - pw - 80
    pt = title_y2 - ph // 2 - 28
    pbt = title_y2 + ph // 2 + 28
    draw.rounded_rectangle([(plx, pt), (prx, pbt)], radius=15, outline=WHITE, width=3)
    tc(draw, date_str, (plx + prx) // 2, (pt + pbt) // 2, pill_font, WHITE)

    sep1_y = title_y2 + 110
    hline(draw, sep1_y, color=(38, 38, 38))
    hdr_y = sep1_y + 54
    ct_top = hdr_y + 42
    ct_rh = 126
    f_chdr, f_lbl, f_pct, f_val = fnt(FM, 46), fnt(FR, 54), fnt(FM, 52), fnt(FR, 52)
    tc(draw, "DIA", COV_DIA_CX, hdr_y, f_chdr, MGRAY)
    tc(draw, "MÊS", COV_MES_CX, hdr_y, f_chdr, MGRAY)
    tc(draw, "ANO", COV_ANO_CX, hdr_y, f_chdr, MGRAY)

    cover_rows = [
        ("IBOVESPA", "ibov"),
        ("S&P 500", "sp500"),
        ("DÓLAR", "usd_brl"),
        ("IFIX", "ifix"),
        ("EURO", "eur_brl"),
    ]
    for i, (name, key) in enumerate(cover_rows):
        metric = metrics[key]
        yt = ct_top + i * ct_rh
        yc = yt + ct_rh // 2
        draw.rectangle([(MARGIN_L, yt), (MARGIN_R, yt + ct_rh - 6)], fill=CA if i % 2 == 0 else CB)
        tl(draw, name, MARGIN_L + 18, yc, f_lbl, WHITE)
        tc(draw, pct2(metric.day_change), COV_DIA_CX, yc, f_pct, color_for(metric.day_change))
        tc(draw, pct2(metric.month_change), COV_MES_CX, yc, f_pct, color_for(metric.month_change))
        tc(draw, pct2(metric.year_change), COV_ANO_CX, yc, f_pct, color_for(metric.year_change))
        tr(draw, format_value(key, metric.value), COV_VAL_RX, yc, f_val, WHITE)

    di_top = ct_top + len(cover_rows) * ct_rh + 8
    di_h = 100
    draw.rectangle([(MARGIN_L, di_top), (MARGIN_R, di_top + di_h)], fill=CB)
    tl(
        draw,
        f"Selic diária acumulada {snapshot.report_date.year}",
        MARGIN_L + 18,
        di_top + di_h // 2,
        fnt(FR, 50),
        LGRAY,
    )
    tr(draw, pct2(snapshot.di_ytd).lstrip("+"), MARGIN_R, di_top + di_h // 2, fnt(FM, 50), WHITE)

    sep2_y = di_top + di_h + 32
    hline(draw, sep2_y)
    sec_pre, sec_h, hdr2_h, block_pad, block_post = 56, 52, 38, 14, 44
    available = H - sep2_y - 130 - 40
    row_h = max(108, (available - 2 * (sec_pre + sec_h + hdr2_h + block_pad + block_post)) // 10)
    f_sec, f_chd2 = fnt(FM, 44), fnt(FL, 34)
    f_lbl2, f_num, f_val2 = fnt(FR, 46), fnt(FM, 44), fnt(FR, 42)

    def rows(items: list[tuple[str, str]]) -> list[tuple[str, MarketMetric, str]]:
        return [(name, metrics[key], key) for name, key in items]

    brazil = rows([("Ibovespa", "ibov"), ("SMAL11", "smal11"), ("IFIX", "ifix")])
    usa = rows([("S&P 500", "sp500"), ("Dow Jones", "dow"), ("Nasdaq", "nasdaq"), ("VIX", "vix")])
    fx = rows(
        [
            ("USD/BRL", "usd_brl"),
            ("EUR/BRL", "eur_brl"),
            ("GBP/BRL", "gbp_brl"),
            ("EUR/USD", "eur_usd"),
            ("GBP/USD", "gbp_usd"),
            ("Dollar Index (DXY)", "dxy"),
        ]
    )
    commodities = rows(
        [
            ("WTI Crude", "wti"),
            ("Brent Crude", "brent"),
            ("Gold", "gold"),
            ("Silver", "silver"),
            ("Copper", "copper"),
        ]
    )

    def draw_section(cx: int, y: int, title: str, section_rows: list[tuple[str, MarketMetric, str]]) -> int:
        y += sec_pre
        tl(draw, title.upper(), cx, y + sec_h // 2, f_sec, LGRAY)
        y += sec_h + 8
        delta_x, value_x = dcx(cx), vrx(cx)
        tc(draw, "DIA", delta_x, y + hdr2_h // 2, f_chd2, MGRAY)
        tr(draw, "VALOR", value_x, y + hdr2_h // 2, f_chd2, MGRAY)
        y += hdr2_h + block_pad
        for i, (name, metric, key) in enumerate(section_rows):
            yt, yc = y + i * row_h, y + i * row_h + row_h // 2
            draw.rectangle([(cx, yt), (cx + COL_W, yt + row_h - 4)], fill=CA if i % 2 == 0 else CB)
            tl(draw, clip(draw, name, nm_max(cx), f_lbl2), cx + 12, yc, f_lbl2, WHITE)
            tc(draw, pct2(metric.day_change), delta_x, yc, f_num, color_for(metric.day_change))
            tr(draw, format_value(key, metric.value), value_x, yc, f_val2, WHITE)
        return y + len(section_rows) * row_h + block_post

    y_l = draw_section(COL_X[0], sep2_y + 30, "Brasil", brazil)
    draw_section(COL_X[0], y_l, "Câmbio", fx)
    y_r = draw_section(COL_X[1], sep2_y + 30, "Estados Unidos", usa)
    draw_section(COL_X[1], y_r, "Commodities", commodities)

    disc_y = H - 130
    hline(draw, disc_y, color=(38, 38, 38))
    tc(
        draw,
        "Fontes: B3, Banco Central do Brasil e Yahoo Finance. Não constitui recomendação.",
        W // 2,
        disc_y + 65,
        fnt(FL, 30),
        DIM,
    )
    return img


def _set_github_outputs(**values: object) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as output:
        for key, value in values.items():
            output.write(f"{key}={value}\n")


def write_artifacts(snapshot: MarketSnapshot, out_dir: Path) -> tuple[Path, Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = snapshot.report_date.strftime("%Y%m%d")
    pdf_path = out_dir / f"fechamento_{stamp}.pdf"
    png_path = out_dir / f"fechamento_{stamp}.png"
    json_path = out_dir / f"fechamento_{stamp}.json"
    pdf_tmp, png_tmp, json_tmp = (
        path.with_suffix(path.suffix + ".tmp") for path in (pdf_path, png_path, json_path)
    )

    image = build(snapshot)
    image.save(png_tmp, format="PNG")
    image.save(pdf_tmp, format="PDF", resolution=300.0)
    json_tmp.write_text(json.dumps(snapshot.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    png_tmp.replace(png_path)
    pdf_tmp.replace(pdf_path)
    json_tmp.replace(json_path)
    return pdf_path, png_path, json_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--skip-stale",
        action="store_true",
        help="não publica se o último fechamento do Ibovespa não for da data BRT atual",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        snapshot = fetch_market_snapshot()
        today_brt = snapshot.generated_at.astimezone(BRT).date()
        if args.skip_stale and snapshot.report_date != today_brt:
            print(
                f"SKIP: último fechamento B3 é {snapshot.report_date:%d/%m/%Y}; hoje é {today_brt:%d/%m/%Y}."
            )
            _set_github_outputs(should_send="false", report_date=snapshot.report_date.isoformat())
            return 0

        pdf_path, png_path, json_path = write_artifacts(snapshot, args.out_dir)
        for warning in snapshot.warnings:
            print(f"WARN: {warning}")
        print(f"PDF: {pdf_path}")
        print(f"PNG: {png_path}")
        print(f"AUDITORIA: {json_path}")
        _set_github_outputs(
            should_send="true",
            pdf_path=pdf_path.as_posix(),
            report_date=snapshot.report_date.isoformat(),
        )
        return 0
    except MarketDataError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        _set_github_outputs(should_send="false")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
