#!/usr/bin/env python3
"""
build_single_page.py — C6 Daily Market Close.
Puxa dados reais via yfinance e gera PDF no layout C6 Invest.
Created by Enzo Ragozini.
"""
import sys
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import yfinance as yf
import pandas as pd

HERE     = Path(__file__).parent
TEMPLATE = HERE / "assets" / "template_cover.png"
OUT      = HERE / "out"
OUT.mkdir(exist_ok=True)

# Fontes commitadas no repo
FL = str(HERE / "assets" / "fonts" / "Poppins-Light.ttf")
FR = str(HERE / "assets" / "fonts" / "Poppins-Regular.ttf")
FM = str(HERE / "assets" / "fonts" / "Poppins-Medium.ttf")
FB = str(HERE / "assets" / "fonts" / "Poppins-Bold.ttf")

W, H  = 2160, 3840
BRT   = ZoneInfo("America/Sao_Paulo")

UP    = (74, 222, 128)
DOWN  = (248, 113, 113)
WHITE = (255, 255, 255)
LGRAY = (200, 200, 200)
MGRAY = (130, 130, 130)
DIM   = (80, 80, 80)
BG    = (0, 0, 0)
CA    = (34, 34, 34)
CB    = (22, 22, 22)
SEP   = (50, 50, 50)

# ─────────────────────────────────────────────────────────────
# DATA FETCH via yfinance
# ─────────────────────────────────────────────────────────────

def fetch(ticker, period="5d"):
    try:
        df = yf.Ticker(ticker).history(period=period, auto_adjust=False)
        if df.empty or len(df) < 2:
            return None, None, None
        last = float(df["Close"].iloc[-1])
        prev = float(df["Close"].iloc[-2])
        chg  = (last / prev - 1) * 100
        return last, prev, chg
    except Exception as e:
        print(f"WARN: {ticker} → {e}")
        return None, None, None

def fetch_all():
    """Fetch all market data. Returns dict of {key: (value_str, chg_pct)}."""
    data = {}

    # --- Índices ---
    tickers = {
        "ibov":    "^BVSP",
        "smal11":  "SMAL11.SA",
        "xfix11":  "XFIX11.SA",
        "ifix":    "XFIX11.SA",   # proxy
        "sp500":   "^GSPC",
        "dow":     "^DJI",
        "nasdaq":  "^IXIC",
        "vix":     "^VIX",
        "usd_brl": "BRL=X",
        "eur_brl": "EURBRL=X",
        "gbp_brl": "GBPBRL=X",
        "eur_usd": "EURUSD=X",
        "gbp_usd": "GBPUSD=X",
        "dxy":     "DX-Y.NYB",
        "wti":     "CL=F",
        "brent":   "BZ=F",
        "gold":    "GC=F",
        "silver":  "SI=F",
        "copper":  "HG=F",
    }

    for key, tkr in tickers.items():
        last, prev, chg = fetch(tkr)
        if last is None:
            data[key] = (None, 0.0)
            continue

        # Format value string
        if key == "ibov":
            val = f"{last:,.0f}".replace(",", ".")
        elif key in ("sp500", "dow", "nasdaq"):
            val = f"{last:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        elif key == "vix":
            val = f"{last:.2f}".replace(".", ",")
        elif key in ("smal11", "xfix11", "ifix"):
            val = f"{last:.2f}".replace(".", ",")
        elif key in ("usd_brl", "eur_brl", "gbp_brl"):
            val = f"R$ {last:.2f}".replace(".", ",")
        elif key in ("eur_usd", "gbp_usd"):
            val = f"{last:.4f}".replace(".", ",")
        elif key == "dxy":
            val = f"{last:.2f}".replace(".", ",")
        elif key in ("wti", "brent"):
            val = f"US$ {last:.2f}".replace(".", ",")
        elif key == "gold":
            val = f"US$ {last:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        elif key == "silver":
            val = f"US$ {last:.2f}".replace(".", ",")
        elif key == "copper":
            val = f"US$ {last:.4f}".replace(".", ",")
        else:
            val = f"{last:.2f}"

        data[key] = (val, chg)

    return data

def safe_val(data, key, fallback="—"):
    v, _ = data.get(key, (None, 0))
    return v if v is not None else fallback

def safe_chg(data, key):
    _, c = data.get(key, (None, 0))
    return c if c is not None else 0.0

def month_chg(ticker):
    """Approximate month-to-date change."""
    try:
        df = yf.Ticker(ticker).history(period="1mo", auto_adjust=False)
        if df.empty or len(df) < 2:
            return 0.0
        return (float(df["Close"].iloc[-1]) / float(df["Close"].iloc[0]) - 1) * 100
    except:
        return 0.0

def ytd_chg(ticker):
    """Year-to-date change."""
    try:
        df = yf.Ticker(ticker).history(period="ytd", auto_adjust=False)
        if df.empty or len(df) < 2:
            return 0.0
        return (float(df["Close"].iloc[-1]) / float(df["Close"].iloc[0]) - 1) * 100
    except:
        return 0.0

def di_acumulado():
    try:
        import urllib.request, json
        from datetime import date
        inicio = f"01/01/{date.today().year}"
        fim    = date.today().strftime("%d/%m/%Y")
        url    = (
            f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados"
            f"?formato=json&dataInicial={inicio}&dataFinal={fim}"
        )
        with urllib.request.urlopen(url, timeout=10) as r:
            dados = json.loads(r.read())
        fator = 1.0
        for d in dados:
            fator *= (1 + float(d["valor"]) / 100)
        acum = (fator - 1) * 100
        return f"{acum:.2f}%".replace(".", ",")
    except Exception as e:
        print(f"WARN DI BCB: {e}")
        return "—"

# ─────────────────────────────────────────────────────────────
# Helpers de renderização
# ─────────────────────────────────────────────────────────────
def fnt(p, s): return ImageFont.truetype(p, s)
def pct2(x):
    return (("+" if x>=0 else "") + f"{x:.2f}%").replace(".", ",")
def clr(x): return UP if x >= 0 else DOWN

def hline(d, y, x0=140, x1=2020, color=SEP, w=2):
    d.line([(x0, y), (x1, y)], fill=color, width=w)

def tl(d, t, x, yc, f, c):
    b = d.textbbox((0,0), t, font=f)
    d.text((x-b[0], yc-(b[3]-b[1])//2-b[1]), t, font=f, fill=c)

def tc(d, t, cx, yc, f, c):
    b = d.textbbox((0,0), t, font=f)
    d.text((cx-(b[2]-b[0])//2-b[0], yc-(b[3]-b[1])//2-b[1]), t, font=f, fill=c)

def tr(d, t, rx, yc, f, c):
    b = d.textbbox((0,0), t, font=f)
    d.text((rx-(b[2]-b[0])-b[0], yc-(b[3]-b[1])//2-b[1]), t, font=f, fill=c)

def clip(d, text, max_px, f):
    b = d.textbbox((0,0), text, font=f)
    if b[2]-b[0] <= max_px: return text
    while len(text) > 2:
        text = text[:-1]
        b2 = d.textbbox((0,0), text+"…", font=f)
        if b2[2]-b2[0] <= max_px: return text+"…"
    return text

# ─────────────────────────────────────────────────────────────
# LAYOUT CONSTANTS
# ─────────────────────────────────────────────────────────────
MARGIN_L = 140
MARGIN_R = 2020

COV_DIA_CX = 834
COV_MES_CX = 1120
COV_ANO_CX = 1414
COV_VAL_RX = 1980

COL_GAP = 60
COL_W   = (MARGIN_R - MARGIN_L - COL_GAP) // 2
COL_X   = [MARGIN_L, MARGIN_L + COL_W + COL_GAP]

def dcx(cx): return cx + int(COL_W * 0.61)
def vrx(cx): return cx + COL_W - 8
def nm_max(cx): return int(COL_W * 0.46)

# ─────────────────────────────────────────────────────────────
# BUILD
# ─────────────────────────────────────────────────────────────
def build(data, date_str):
    img = Image.new("RGB", (W, H), BG)

    # Logo
    tpl  = Image.open(TEMPLATE).convert("RGBA")
    logo = tpl.crop((820, 660, 1340, 755))
    lw, lh = int(logo.width * 1.55), int(logo.height * 1.55)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    LOGO_Y = 110
    img.paste(logo.convert("RGB"), (MARGIN_L, LOGO_Y), mask=logo.split()[3])

    d = ImageDraw.Draw(img)

    # Título
    TITLE_SIZE        = 148
    LINE_GAP          = 162
    LOGO_TO_TITLE_GAP = 140
    TITLE_Y1 = LOGO_Y + lh + LOGO_TO_TITLE_GAP + TITLE_SIZE // 2
    TITLE_Y2 = TITLE_Y1 + LINE_GAP

    f_light = fnt(FL, TITLE_SIZE)
    f_bold  = fnt(FB, TITLE_SIZE)
    f_pill  = fnt(FR, 74)

    tl(d, "Fechamento", MARGIN_L, TITLE_Y1, f_light, WHITE)
    tl(d, "diário",     MARGIN_L, TITLE_Y2, f_bold,  WHITE)

    # Date pill
    bp = d.textbbox((0,0), date_str, font=f_pill)
    pw, ph = bp[2]-bp[0], bp[3]-bp[1]
    px, py = 40, 24
    prx = MARGIN_R
    plx = prx - pw - 2*px
    pt  = TITLE_Y2 - ph//2 - py - 4
    pbt = TITLE_Y2 + ph//2 + py + 4
    d.rounded_rectangle([(plx, pt), (prx, pbt)], radius=15, outline=WHITE, width=3)
    tc(d, date_str, (plx+prx)//2, (pt+pbt)//2, f_pill, WHITE)

    # Sep 1
    SEP1_Y = TITLE_Y2 + 110
    hline(d, SEP1_Y, color=(38, 38, 38), w=2)

    # Cover table
    HDR_Y  = SEP1_Y + 54
    CT_TOP = HDR_Y + 42
    CT_RH  = 126

    f_chdr = fnt(FM, 46)
    f_lbl  = fnt(FR, 54)
    f_pct  = fnt(FM, 52)
    f_val  = fnt(FR, 52)

    tc(d, "DIA",  COV_DIA_CX, HDR_Y, f_chdr, MGRAY)
    tc(d, "MÊS",  COV_MES_CX, HDR_Y, f_chdr, MGRAY)
    tc(d, "ANO",  COV_ANO_CX, HDR_Y, f_chdr, MGRAY)

    cover_rows = [
        ("IBOVESPA", safe_chg(data,"ibov"),   month_chg("^BVSP"),  ytd_chg("^BVSP"),  safe_val(data,"ibov")),
        ("S&P 500",  safe_chg(data,"sp500"),  month_chg("^GSPC"),  ytd_chg("^GSPC"),  safe_val(data,"sp500")),
        ("DÓLAR",    safe_chg(data,"usd_brl"),month_chg("BRL=X"),  ytd_chg("BRL=X"),  safe_val(data,"usd_brl")),
        ("IFIX",     safe_chg(data,"ifix"),   month_chg("XFIX11.SA"), ytd_chg("XFIX11.SA"), safe_val(data,"ifix")),
        ("EURO",     safe_chg(data,"eur_brl"),month_chg("EURBRL=X"),ytd_chg("EURBRL=X"),safe_val(data,"eur_brl")),
    ]

    for i, (name, dia, mes, ano, val) in enumerate(cover_rows):
        yt = CT_TOP + i * CT_RH
        yc = yt + CT_RH // 2
        d.rectangle([(MARGIN_L, yt), (MARGIN_R, yt+CT_RH-6)],
                     fill=CA if i%2==0 else CB)
        tl(d, name,       MARGIN_L+18, yc, f_lbl, WHITE)
        tc(d, pct2(dia),  COV_DIA_CX,  yc, f_pct, clr(dia))
        tc(d, pct2(mes),  COV_MES_CX,  yc, f_pct, clr(mes))
        tc(d, pct2(ano),  COV_ANO_CX,  yc, f_pct, clr(ano))
        tr(d, val,        COV_VAL_RX,  yc, f_val, WHITE)

    # DI row
    DI_TOP = CT_TOP + len(cover_rows) * CT_RH + 8
    DI_H   = 100
    d.rectangle([(MARGIN_L, DI_TOP), (MARGIN_R, DI_TOP+DI_H)], fill=CB)
    tl(d, "DI Acumulado 2026", MARGIN_L+18, DI_TOP+DI_H//2, fnt(FR, 50), LGRAY)
    tr(d, di_acumulado(),      MARGIN_R,    DI_TOP+DI_H//2, fnt(FM, 50), WHITE)

    # Sep 2
    SEP2_Y = DI_TOP + DI_H + 32
    hline(d, SEP2_Y)

    # Detail block
    SEC_PRE  = 56; SEC_H = 52; HDR2_H = 38; BLK_PAD = 14; BLK_POST = 44
    SEC_FIXED = SEC_PRE + SEC_H + HDR2_H + BLK_PAD + BLK_POST
    available = H - SEP2_Y - 130 - 40
    max_rows  = 10
    ROW_H     = max(108, (available - 2*SEC_FIXED) // max_rows)

    f_sec  = fnt(FM, 44)
    f_chd2 = fnt(FL, 34)
    f_lbl2 = fnt(FR, 46)
    f_num  = fnt(FM, 44)
    f_val2 = fnt(FR, 42)

    indices_br = [
        ("Ibovespa",    safe_chg(data,"ibov"),   safe_val(data,"ibov")),
        ("SMAL11",      safe_chg(data,"smal11"),  safe_val(data,"smal11")),
        ("IFIX", safe_chg(data,"xfix11"),  safe_val(data,"xfix11")),
    ]
    indices_us = [
        ("S&P 500",   safe_chg(data,"sp500"),  safe_val(data,"sp500")),
        ("Dow Jones", safe_chg(data,"dow"),    safe_val(data,"dow")),
        ("Nasdaq",    safe_chg(data,"nasdaq"), safe_val(data,"nasdaq")),
        ("VIX",       safe_chg(data,"vix"),    safe_val(data,"vix")),
    ]
    fx = [
        ("USD/BRL",            safe_chg(data,"usd_brl"), safe_val(data,"usd_brl")),
        ("EUR/BRL",            safe_chg(data,"eur_brl"), safe_val(data,"eur_brl")),
        ("GBP/BRL",            safe_chg(data,"gbp_brl"), safe_val(data,"gbp_brl")),
        ("EUR/USD",            safe_chg(data,"eur_usd"), safe_val(data,"eur_usd")),
        ("GBP/USD",            safe_chg(data,"gbp_usd"), safe_val(data,"gbp_usd")),
        ("Dollar Index (DXY)", safe_chg(data,"dxy"),     safe_val(data,"dxy")),
    ]
    commodities = [
        ("WTI Crude",   safe_chg(data,"wti"),    safe_val(data,"wti")),
        ("Brent Crude", safe_chg(data,"brent"),  safe_val(data,"brent")),
        ("Gold",        safe_chg(data,"gold"),   safe_val(data,"gold")),
        ("Silver",      safe_chg(data,"silver"), safe_val(data,"silver")),
        ("Copper",      safe_chg(data,"copper"), safe_val(data,"copper")),
    ]

    def draw_section(cx, y, title, rows, fmt_fn=pct2):
        y += SEC_PRE
        tl(d, title.upper(), cx, y + SEC_H//2, f_sec, LGRAY)
        y += SEC_H + 8
        dx = dcx(cx); vx = vrx(cx)
        tc(d, "DIA",   dx, y + HDR2_H//2, f_chd2, MGRAY)
        tr(d, "VALOR", vx,  y + HDR2_H//2, f_chd2, MGRAY)
        y += HDR2_H + BLK_PAD
        for i, (name, delta, val) in enumerate(rows):
            yt = y + i*ROW_H; yc = yt + ROW_H//2
            d.rectangle([(cx, yt),(cx+COL_W, yt+ROW_H-4)],
                         fill=CA if i%2==0 else CB)
            nm = clip(d, name, nm_max(cx), f_lbl2)
            tl(d, nm,            cx+12, yc, f_lbl2, WHITE)
            tc(d, fmt_fn(delta), dx,    yc, f_num,  clr(delta))
            tr(d, val,           vx,    yc, f_val2, WHITE)
        return y + len(rows)*ROW_H + BLK_POST

    y_l = SEP2_Y + 30
    y_r = SEP2_Y + 30
    y_l = draw_section(COL_X[0], y_l, "Brasil",         indices_br)
    y_l = draw_section(COL_X[0], y_l, "Câmbio",         fx)
    y_r = draw_section(COL_X[1], y_r, "Estados Unidos", indices_us)
    y_r = draw_section(COL_X[1], y_r, "Commodities",    commodities)

    # Disclaimer
    DISC_Y = H - 130
    hline(d, DISC_Y, color=(38, 38, 38))
    tc(d, "Não constitui recomendação de investimento.",
       W//2, DISC_Y + 65, fnt(FL, 32), DIM)

    return img


def main():
    now      = datetime.now(BRT)
    date_str = now.strftime("%d/%m/%y")
    stamp    = now.strftime("%Y%m%d")

    print(f"Fetching market data for {date_str}…")
    data = fetch_all()
    print("Data fetched. Building PDF…")

    img = build(data, date_str)

    pdf_path = OUT / f"fechamento_{stamp}.pdf"
    png_path = OUT / f"fechamento_{stamp}.png"
    img.save(str(png_path), format="PNG")
    img_rgb = Image.open(str(png_path)).convert("RGB")
    img_rgb.save(str(pdf_path), "PDF", resolution=300.0)
    print(f"✓ PDF → {pdf_path}")


if __name__ == "__main__":
    main()
