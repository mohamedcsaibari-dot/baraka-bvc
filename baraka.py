"""
BARAKA v4.0 - Wall Street Level BVC Trading Agent
Volume Profile · Macro Regime · Twitter/X · Fed/ECB/BAM
Global Macro Correlation · Bear Signals · 100% Gratuit · Groq LLM
"""

import schedule, time, datetime, json, os, requests, smtplib, re
import numpy as np
import yfinance as yf
from tradingview_ta import TA_Handler, Interval
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except:
    GROQ_AVAILABLE = False

GMAIL_USER     = os.environ.get("GMAIL_USER", "mohamed.csaibari@gmail.com")
GMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
TO_EMAIL       = "mohamed.csaibari@gmail.com"
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")
TRADE_LOG_FILE = "trade_log.json"
LEARNING_FILE  = "baraka_learnings.json"
VOLUME_ALERT_THRESHOLD = 2.5

# ─── BVC WATCHLIST COMPLETE (75 societes) ─────────────────────────────────────
BVC_WATCHLIST = {
    "ATW":    {"name":"Attijariwafa Bank",         "sector":"Banque",       "avg_vol":85000,  "mc":"large","bam":True, "brent":False,"phos":False,"yf":"ATW.CS"},
    "BCP":    {"name":"Banque Centrale Pop.",       "sector":"Banque",       "avg_vol":60000,  "mc":"large","bam":True, "brent":False,"phos":False,"yf":"BCP.CS"},
    "BMCE":   {"name":"Bank of Africa",             "sector":"Banque",       "avg_vol":70000,  "mc":"large","bam":True, "brent":False,"phos":False,"yf":"BMCE.CS"},
    "CIH":    {"name":"CIH Bank",                   "sector":"Banque",       "avg_vol":45000,  "mc":"mid",  "bam":True, "brent":False,"phos":False,"yf":"CIH.CS"},
    "CDM":    {"name":"Credit du Maroc",            "sector":"Banque",       "avg_vol":18000,  "mc":"mid",  "bam":True, "brent":False,"phos":False,"yf":"CDM.CS"},
    "BMCI":   {"name":"BMCI",                       "sector":"Banque",       "avg_vol":12000,  "mc":"mid",  "bam":True, "brent":False,"phos":False,"yf":"BMCI.CS"},
    "CFG":    {"name":"CFG Bank",                   "sector":"Banque",       "avg_vol":8000,   "mc":"small","bam":True, "brent":False,"phos":False,"yf":"CFG.CS"},
    "WAA":    {"name":"Wafa Assurance",             "sector":"Assurance",    "avg_vol":6000,   "mc":"mid",  "bam":True, "brent":False,"phos":False,"yf":"WAA.CS"},
    "ATL":    {"name":"Atlanta",                    "sector":"Assurance",    "avg_vol":5000,   "mc":"small","bam":True, "brent":False,"phos":False,"yf":"ATL.CS"},
    "SAH":    {"name":"Saham Assurance",            "sector":"Assurance",    "avg_vol":4000,   "mc":"small","bam":True, "brent":False,"phos":False,"yf":"SAH.CS"},
    "MCB":    {"name":"Mutuelle Centrale Marocaine","sector":"Assurance",    "avg_vol":2000,   "mc":"small","bam":True, "brent":False,"phos":False,"yf":"MCB.CS"},
    "IAM":    {"name":"Maroc Telecom",              "sector":"Telecom",      "avg_vol":120000, "mc":"large","bam":False,"brent":False,"phos":False,"yf":"IAM.CS"},
    "HPS":    {"name":"HighTech Payment Systems",   "sector":"Tech",         "avg_vol":15000,  "mc":"mid",  "bam":False,"brent":False,"phos":False,"yf":"HPS.CS"},
    "M2M":    {"name":"M2M Group",                  "sector":"Tech",         "avg_vol":2500,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"M2M.CS"},
    "IB":     {"name":"Involys",                    "sector":"Tech",         "avg_vol":3000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"IB.CS"},
    "S2M":    {"name":"S2M",                        "sector":"Tech",         "avg_vol":2000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"S2M.CS"},
    "OCP":    {"name":"OCP Group",                  "sector":"Chimie",       "avg_vol":95000,  "mc":"large","bam":False,"brent":False,"phos":True, "yf":"OCP.CS"},
    "SMI":    {"name":"SMI",                        "sector":"Mines",        "avg_vol":8000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"SMI.CS"},
    "CMT":    {"name":"Cie Miniere Touissit",       "sector":"Mines",        "avg_vol":5000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"CMT.CS"},
    "MANAGEM":{"name":"Managem",                    "sector":"Mines",        "avg_vol":12000,  "mc":"mid",  "bam":False,"brent":False,"phos":False,"yf":"MNG.CS"},
    "SMH":    {"name":"Samine",                     "sector":"Mines",        "avg_vol":3000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"SMH.CS"},
    "ZELLIDJA":{"name":"Zellidja",                  "sector":"Mines",        "avg_vol":1500,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"ZLD.CS"},
    "SNEP":   {"name":"SNEP",                       "sector":"Chimie",       "avg_vol":4000,   "mc":"small","bam":False,"brent":False,"phos":True, "yf":"SNP.CS"},
    "SCE":    {"name":"Ste Cherifienne Engrais",    "sector":"Chimie",       "avg_vol":3500,   "mc":"small","bam":False,"brent":False,"phos":True, "yf":"SCE.CS"},
    "FERTIMA":{"name":"Fertima",                    "sector":"Chimie",       "avg_vol":2500,   "mc":"small","bam":False,"brent":False,"phos":True, "yf":"FER.CS"},
    "ADH":    {"name":"Addoha",                     "sector":"Immobilier",   "avg_vol":35000,  "mc":"mid",  "bam":True, "brent":False,"phos":False,"yf":"ADH.CS"},
    "ALM":    {"name":"Alliances",                  "sector":"Immobilier",   "avg_vol":15000,  "mc":"mid",  "bam":True, "brent":False,"phos":False,"yf":"ALM.CS"},
    "RDS":    {"name":"Residences Dar Saada",       "sector":"Immobilier",   "avg_vol":8000,   "mc":"small","bam":True, "brent":False,"phos":False,"yf":"RDS.CS"},
    "BALIMA": {"name":"Balima",                     "sector":"Immobilier",   "avg_vol":2000,   "mc":"small","bam":True, "brent":False,"phos":False,"yf":"BAL.CS"},
    "HOL":    {"name":"Holcim Maroc",               "sector":"Construction", "avg_vol":12000,  "mc":"mid",  "bam":False,"brent":False,"phos":False,"yf":"HOL.CS"},
    "CMA":    {"name":"Ciments du Maroc",           "sector":"Construction", "avg_vol":10000,  "mc":"mid",  "bam":False,"brent":False,"phos":False,"yf":"CMA.CS"},
    "LHM":    {"name":"LafargeHolcim Maroc",        "sector":"Construction", "avg_vol":9000,   "mc":"mid",  "bam":False,"brent":False,"phos":False,"yf":"LHM.CS"},
    "SNABT":  {"name":"Sna Btp",                    "sector":"Construction", "avg_vol":1500,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"SNA.CS"},
    "LABEL":  {"name":"Label Vie",                  "sector":"Distribution", "avg_vol":9000,   "mc":"mid",  "bam":False,"brent":False,"phos":False,"yf":"LBV.CS"},
    "FENIE":  {"name":"Fenie Brossette",            "sector":"Distribution", "avg_vol":3500,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"FBR.CS"},
    "STOKVIS":{"name":"Stokvis Nord Afrique",       "sector":"Distribution", "avg_vol":2000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"STK.CS"},
    "LAC":    {"name":"Lesieur Cristal",            "sector":"Agro",         "avg_vol":11000,  "mc":"mid",  "bam":False,"brent":True, "phos":False,"yf":"LAC.CS"},
    "DARI":   {"name":"Dari Couspate",              "sector":"Agro",         "avg_vol":4000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"DAR.CS"},
    "COSUMAR":{"name":"Cosumar",                    "sector":"Agro",         "avg_vol":8000,   "mc":"mid",  "bam":False,"brent":False,"phos":False,"yf":"CSR.CS"},
    "OULMES": {"name":"Eaux Minerales Oulmes",      "sector":"Agro",         "avg_vol":4000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"OUL.CS"},
    "UNIMER": {"name":"Unimer",                     "sector":"Agro",         "avg_vol":3000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"UNI.CS"},
    "TMA":    {"name":"Total Maroc",                "sector":"Energie",      "avg_vol":7000,   "mc":"mid",  "bam":False,"brent":True, "phos":False,"yf":"TMA.CS"},
    "TAQA":   {"name":"Taqa Morocco",               "sector":"Energie",      "avg_vol":8000,   "mc":"mid",  "bam":False,"brent":True, "phos":False,"yf":"TQA.CS"},
    "SRM":    {"name":"Sonasid",                    "sector":"Siderurgie",   "avg_vol":6000,   "mc":"mid",  "bam":False,"brent":True, "phos":False,"yf":"SRM.CS"},
    "CTM":    {"name":"CTM",                        "sector":"Transport",    "avg_vol":5000,   "mc":"small","bam":False,"brent":True, "phos":False,"yf":"CTM.CS"},
    "TIMAR":  {"name":"Timar",                      "sector":"Transport",    "avg_vol":1500,   "mc":"small","bam":False,"brent":True, "phos":False,"yf":"TMR.CS"},
    "LBV":    {"name":"Lydec",                      "sector":"Services",     "avg_vol":5000,   "mc":"mid",  "bam":False,"brent":False,"phos":False,"yf":"LYD.CS"},
    "AFMA":   {"name":"Afma",                       "sector":"Services",     "avg_vol":2500,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"AFM.CS"},
    "RIS":    {"name":"Risma",                      "sector":"Tourisme",     "avg_vol":5000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"RIS.CS"},
    "SOTHEMA":{"name":"Sothema",                    "sector":"Pharma",       "avg_vol":6000,   "mc":"mid",  "bam":False,"brent":False,"phos":False,"yf":"SOT.CS"},
    "PROMOPH":{"name":"Promopharm",                 "sector":"Pharma",       "avg_vol":2500,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"PRM.CS"},
    "PHARM":  {"name":"Pharma 5",                   "sector":"Pharma",       "avg_vol":3000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"PH5.CS"},
    "EQDOM":  {"name":"Eqdom",                      "sector":"Credit Conso", "avg_vol":4000,   "mc":"small","bam":True, "brent":False,"phos":False,"yf":"EQD.CS"},
    "SOFAC":  {"name":"Sofac",                      "sector":"Credit Conso", "avg_vol":3000,   "mc":"small","bam":True, "brent":False,"phos":False,"yf":"SOF.CS"},
    "SALAF":  {"name":"Salafin",                    "sector":"Credit Conso", "avg_vol":3500,   "mc":"small","bam":True, "brent":False,"phos":False,"yf":"SAL.CS"},
    "TASLIF": {"name":"Taslif",                     "sector":"Credit Conso", "avg_vol":1500,   "mc":"small","bam":True, "brent":False,"phos":False,"yf":"TSL.CS"},
    "ACRED":  {"name":"Acred",                      "sector":"Credit Conso", "avg_vol":2000,   "mc":"small","bam":True, "brent":False,"phos":False,"yf":"ACR.CS"},
    "DIAC":   {"name":"Diac Salaf",                 "sector":"Credit Conso", "avg_vol":1000,   "mc":"small","bam":True, "brent":False,"phos":False,"yf":"DIA.CS"},
    "MPARK":  {"name":"Maroc Leasing",              "sector":"Leasing",      "avg_vol":3000,   "mc":"small","bam":True, "brent":False,"phos":False,"yf":"MPK.CS"},
    "DLM":    {"name":"Delattre Levivier Maroc",    "sector":"Industrie",    "avg_vol":3000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"DLM.CS"},
    "NEXANS": {"name":"Nexans Maroc",               "sector":"Industrie",    "avg_vol":3000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"NEX.CS"},
    "MAGHREB":{"name":"Maghreb Oxygene",            "sector":"Industrie",    "avg_vol":2000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"MAG.CS"},
    "STROC":  {"name":"Stroc Industrie",            "sector":"Industrie",    "avg_vol":2000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"STR.CS"},
    "LGMC":   {"name":"Longometal",                 "sector":"Industrie",    "avg_vol":2000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"LGM.CS"},
    "COLOROB":{"name":"Colorobbia Maroc",           "sector":"Industrie",    "avg_vol":1500,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"COL.CS"},
    "AFRIC":  {"name":"Africa Industries",          "sector":"Industrie",    "avg_vol":1000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"AFR.CS"},
    "FBR":    {"name":"Fipar Holding",              "sector":"Holding",      "avg_vol":4000,   "mc":"mid",  "bam":False,"brent":False,"phos":False,"yf":"FIP.CS"},
    "ENNAKL": {"name":"Ennakl",                     "sector":"Automobile",   "avg_vol":2000,   "mc":"small","bam":False,"brent":True, "phos":False,"yf":"ENN.CS"},
    "MED":    {"name":"Meditel",                    "sector":"Telecom",      "avg_vol":2000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"MED.CS"},
    "SDLT":   {"name":"Sodetel",                    "sector":"Telecom",      "avg_vol":1000,   "mc":"small","bam":False,"brent":False,"phos":False,"yf":"SDL.CS"},
}

# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 1 — VOLUME PROFILE (POC · VAH · VAL · HVN · LVN)
# ═══════════════════════════════════════════════════════════════════════════════

def get_volume_profile(ticker_yf, period="3mo", bins=30):
    """
    Calcule le Volume Profile institutionnel:
    POC  = Point of Control (prix avec max volume)
    VAH  = Value Area High (70% du volume - borne haute)
    VAL  = Value Area Low (70% du volume - borne basse)
    HVN  = High Volume Node (zones d'accumulation)
    LVN  = Low Volume Node (zones de faible resistance)
    """
    try:
        data = yf.download(ticker_yf, period=period, interval="1d", progress=False, auto_adjust=True)
        if data is None or len(data) < 5:
            return None
        data = data.dropna()
        if len(data) < 5:
            return None

        closes = data["Close"].values.flatten()
        highs  = data["High"].values.flatten()
        lows   = data["Low"].values.flatten()
        vols   = data["Volume"].values.flatten()

        price_min = float(np.min(lows))
        price_max = float(np.max(highs))
        if price_max <= price_min:
            return None

        price_bins   = np.linspace(price_min, price_max, bins + 1)
        vol_at_price = np.zeros(bins)

        for i in range(len(data)):
            h, l, v = float(highs[i]), float(lows[i]), float(vols[i])
            if h == l:
                continue
            for b in range(bins):
                bl, bh = price_bins[b], price_bins[b + 1]
                ol = max(l, bl)
                oh = min(h, bh)
                if oh > ol:
                    vol_at_price[b] += v * (oh - ol) / (h - l)

        # POC
        poc_idx   = int(np.argmax(vol_at_price))
        poc_price = float((price_bins[poc_idx] + price_bins[poc_idx + 1]) / 2)

        # Value Area (70% du volume)
        total_vol  = vol_at_price.sum()
        target_vol = total_vol * 0.70
        sorted_idx = np.argsort(vol_at_price)[::-1]
        accumulated, va_bins = 0.0, []
        for idx in sorted_idx:
            accumulated += vol_at_price[idx]
            va_bins.append(int(idx))
            if accumulated >= target_vol:
                break

        vah_idx = max(va_bins)
        val_idx = min(va_bins)
        vah = float((price_bins[vah_idx] + price_bins[min(vah_idx + 1, bins)]) / 2)
        val = float((price_bins[val_idx] + price_bins[min(val_idx + 1, bins)]) / 2)

        # HVN / LVN
        mean_vol  = vol_at_price.mean()
        hvn_prices = [float((price_bins[i] + price_bins[i + 1]) / 2)
                      for i in range(bins) if vol_at_price[i] > mean_vol * 1.5]
        lvn_prices = [float((price_bins[i] + price_bins[i + 1]) / 2)
                      for i in range(bins) if vol_at_price[i] < mean_vol * 0.5]

        current = float(closes[-1]) if len(closes) > 0 else poc_price

        # Signal Volume Profile
        if current < val:
            vp_signal, vp_desc = "ACHAT_FORT", f"Prix sous VAL {val:.2f} — zone d'achat institutionnelle"
        elif current < poc_price:
            vp_signal, vp_desc = "ACHAT", f"Prix entre VAL et POC {poc_price:.2f} — accumulation"
        elif current > vah:
            vp_signal, vp_desc = "VENTE", f"Prix au-dessus VAH {vah:.2f} — zone de distribution"
        elif current > poc_price:
            vp_signal, vp_desc = "NEUTRE_HAUT", f"Prix entre POC et VAH — momentum positif"
        else:
            vp_signal, vp_desc = "NEUTRE", f"Prix au POC {poc_price:.2f} — equilibre offre/demande"

        return {
            "poc":          round(poc_price, 2),
            "vah":          round(vah, 2),
            "val":          round(val, 2),
            "current":      round(current, 2),
            "hvn":          [round(p, 2) for p in hvn_prices[:3]],
            "lvn":          [round(p, 2) for p in lvn_prices[:3]],
            "signal":       vp_signal,
            "description":  vp_desc,
            "below_val":    current < val,
            "in_va":        val <= current <= vah,
            "above_vah":    current > vah,
            "dist_poc_pct": round((current - poc_price) / poc_price * 100, 2),
        }
    except Exception as e:
        print(f"[VP] {ticker_yf}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 2 — MACRO GLOBAL (Fed · ECB · VIX · DXY · Yields · Commodities)
# ═══════════════════════════════════════════════════════════════════════════════

def get_global_macro():
    """
    Données macro globales via yfinance:
    - Fed Funds Rate (proxy via SOFR/T-bills)
    - VIX (fear index)
    - DXY (dollar index)
    - US Yields (2Y, 10Y, 30Y)
    - Yield spread (2Y-10Y = recession indicator)
    - Commodities (Gold, Oil, Silver, Copper, Phosphate proxy)
    - Indices mondiaux
    - EUR/USD, USD/MAD
    """
    macro = {}
    symbols = {
        "vix":     "^VIX",
        "sp500":   "^GSPC",
        "nasdaq":  "^IXIC",
        "stoxx50": "^STOXX50E",
        "dax":     "^GDAXI",
        "cac40":   "^FCHI",
        "us10y":   "^TNX",
        "us2y":    "^IRX",
        "us30y":   "^TYX",
        "gold":    "GC=F",
        "brent":   "BZ=F",
        "oil_wti": "CL=F",
        "silver":  "SI=F",
        "copper":  "HG=F",
        "natgas":  "NG=F",
        "eur_usd": "EURUSD=X",
        "usd_mad": "USDMAD=X",
        "eur_mad": "EURMAD=X",
        "gbp_usd": "GBPUSD=X",
        "jpy_usd": "JPY=X",
        "dxy":     "DX-Y.NYB",
        "bitcoin": "BTC-USD",
    }
    try:
        tickers = yf.download(
            list(symbols.values()),
            period="2d",
            interval="1d",
            progress=False,
            auto_adjust=True
        )
        for name, sym in symbols.items():
            try:
                closes = tickers["Close"][sym].dropna()
                if len(closes) >= 2:
                    prev  = float(closes.iloc[-2])
                    curr  = float(closes.iloc[-1])
                    chg   = (curr - prev) / prev * 100 if prev != 0 else 0
                    macro[name] = {"price": round(curr, 4), "change": round(chg, 3)}
                else:
                    macro[name] = {"price": 0, "change": 0}
            except:
                macro[name] = {"price": 0, "change": 0}
    except Exception as e:
        print(f"[MACRO] yfinance error: {e}")
        for name in symbols:
            macro[name] = {"price": 0, "change": 0}

    # Calculs dérivés importants
    vix_val    = macro.get("vix", {}).get("price", 20)
    us10y_val  = macro.get("us10y", {}).get("price", 4.0)
    us2y_val   = macro.get("us2y", {}).get("price", 4.5)
    dxy_val    = macro.get("dxy", {}).get("price", 103)
    gold_chg   = macro.get("gold", {}).get("change", 0)
    brent_chg  = macro.get("brent", {}).get("change", 0)
    sp500_chg  = macro.get("sp500", {}).get("change", 0)
    copper_chg = macro.get("copper", {}).get("change", 0)

    # Regime detection
    yield_spread   = us10y_val - us2y_val  # Positif = normale, Negatif = inversion (recession)
    risk_on        = vix_val < 20 and sp500_chg > 0 and gold_chg < 1
    risk_off       = vix_val > 25 or (gold_chg > 1 and sp500_chg < 0)
    inflation_up   = gold_chg > 0.5 and brent_chg > 0.5 and copper_chg > 0
    recession_risk = yield_spread < 0

    macro["_derived"] = {
        "yield_spread":   round(yield_spread, 3),
        "risk_regime":    "RISK_ON" if risk_on else ("RISK_OFF" if risk_off else "NEUTRE"),
        "inflation_regime": "INFLATION" if inflation_up else "DEFLATION" if not inflation_up and brent_chg < -1 else "STABLE",
        "recession_risk": recession_risk,
        "vix_level":     "FAIBLE" if vix_val < 15 else "NORMAL" if vix_val < 20 else "ELEVE" if vix_val < 30 else "EXTREME",
        "dollar_trend":  "FORT" if dxy_val > 105 else "FAIBLE" if dxy_val < 100 else "NEUTRE",
        "bvc_outlook":   _compute_bvc_outlook(risk_on, risk_off, inflation_up, recession_risk, dxy_val, brent_chg),
    }
    return macro


def _compute_bvc_outlook(risk_on, risk_off, inflation_up, recession_risk, dxy, brent_chg):
    """Traduction du regime macro en impact BVC secteur par secteur"""
    outlook = {}
    # Banques: favorisees par taux hauts et risk-on
    outlook["Banque"]      = "POSITIF" if risk_on and not recession_risk else ("NEGATIF" if recession_risk else "NEUTRE")
    # Mines/Chimie: favorisees par inflation et hausse matieres premieres
    outlook["Mines"]       = "POSITIF" if inflation_up else "NEGATIF" if not inflation_up and brent_chg < -1 else "NEUTRE"
    outlook["Chimie"]      = "POSITIF" if inflation_up else "NEUTRE"
    # Energie: correle positivement au brent
    outlook["Energie"]     = "POSITIF" if brent_chg > 1 else ("NEGATIF" if brent_chg < -2 else "NEUTRE")
    # Immobilier: favorise par taux bas
    outlook["Immobilier"]  = "POSITIF" if not recession_risk else "NEGATIF"
    # Telecom/Tech: defensif, tient bien en risk-off
    outlook["Telecom"]     = "POSITIF" if risk_off else "NEUTRE"
    outlook["Tech"]        = "POSITIF" if risk_on else "NEUTRE"
    # Agro: favorable si commodites stables
    outlook["Agro"]        = "NEGATIF" if brent_chg > 2 else "POSITIF" if brent_chg < -1 else "NEUTRE"
    # Dollar fort = MAD faible = exportateurs favorises (OCP, Managem)
    if dxy > 105:
        outlook["Mines"] = "TRES_POSITIF"
        outlook["Chimie"] = "TRES_POSITIF"
    return outlook


def get_fed_ecb_bam_rates():
    """Scrape les taux des banques centrales via sources publiques"""
    rates = {"fed": None, "ecb": None, "bam": None, "bam_news": [], "fed_news": [], "ecb_news": []}
    headers = {"User-Agent": "Mozilla/5.0"}

    # Fed (FRED)
    try:
        r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS",
                         headers=headers, timeout=10)
        lines = r.text.strip().split("\n")
        if len(lines) > 1:
            last = lines[-1].split(",")
            if len(last) == 2:
                rates["fed"] = float(last[1])
    except: pass

    # BAM
    try:
        r = requests.get("https://www.bkam.ma/Politique-monetaire", headers=headers, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        text = r.text.lower()
        for m in re.findall(r'(\d+[.,]\d+)\s*%', text):
            try:
                v = float(m.replace(",", "."))
                if 0.5 < v < 10:
                    rates["bam"] = v
                    break
            except: pass
        for el in soup.select("p,h2,h3,li")[:15]:
            t = el.get_text(strip=True)
            if any(kw in t.lower() for kw in ["taux","monetaire","inflation","reserve","politique"]):
                if 20 < len(t) < 250:
                    rates["bam_news"].append(t[:200])
        rates["bam_news"] = list(dict.fromkeys(rates["bam_news"]))[:4]
    except Exception as e:
        print(f"[BAM] {e}")

    # ECB
    try:
        r = requests.get("https://www.ecb.europa.eu/press/pr/activities/mopo/html/index.en.html",
                         headers=headers, timeout=10)
        text = r.text.lower()
        for m in re.findall(r'(\d+[.,]\d+)\s*%', text):
            try:
                v = float(m.replace(",", "."))
                if 0 < v < 8:
                    rates["ecb"] = v
                    break
            except: pass
    except: pass

    if not rates["fed"]:   rates["fed"] = 5.25
    if not rates["bam"]:   rates["bam"] = 3.0
    if not rates["ecb"]:   rates["ecb"] = 3.5

    return rates


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 3 — SOCIAL MEDIA & NEWS (Twitter/X · Google News · Reuters · Bloomberg)
# ═══════════════════════════════════════════════════════════════════════════════

def get_twitter_signals():
    """
    Scrape Twitter/X via instances Nitter publiques (sans API)
    Comptes surveilles: Fed, ECB, BAM, analystes macro, BVC news
    """
    signals = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"}

    # Comptes cles a surveiller
    accounts = [
        ("federalreserve", "FED"),
        ("BankAlMaghrib",  "BAM"),
        ("ecb",            "ECB"),
        ("IMFNews",        "FMI"),
        ("WorldBank",      "BM"),
        ("ReutersBiz",     "Reuters"),
    ]

    nitter_instances = [
        "https://nitter.poast.org",
        "https://nitter.privacydev.net",
        "https://nitter.1d4.us",
        "https://nitter.lunar.icu",
    ]

    for account, label in accounts:
        for nitter in nitter_instances:
            try:
                url  = f"{nitter}/{account}/rss"
                r    = requests.get(url, headers=headers, timeout=8)
                if r.status_code != 200:
                    continue
                # Parse RSS
                items = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", r.text)
                for item in items[1:4]:  # Skip feed title
                    clean = re.sub(r"<[^>]+>", "", item).strip()
                    if len(clean) > 20:
                        signals.append({"source": label, "text": clean[:200], "account": account})
                break
            except:
                continue

    return signals[:12]


def get_google_news(queries):
    """
    Google News RSS - gratuit, aucune auth
    Surveille: Fed, BVC, OCP, IAM, BAM, macro maroc, etc.
    """
    all_news = []
    headers  = {"User-Agent": "Mozilla/5.0"}
    for query in queries[:6]:
        try:
            q   = requests.utils.quote(query)
            url = f"https://news.google.com/rss/search?q={q}&hl=fr&gl=MA&ceid=MA:fr"
            r   = requests.get(url, headers=headers, timeout=8)
            # Parse RSS items
            titles = re.findall(r"<title>(.*?)</title>", r.text)
            for t in titles[1:4]:
                clean = re.sub(r"<[^>]+>", "", t).strip()
                if len(clean) > 15 and "Google News" not in clean:
                    all_news.append({"query": query, "headline": clean[:180]})
        except:
            continue
        time.sleep(0.3)
    return all_news[:15]


def get_all_news(bvc_watchlist_tickers):
    """Agregation complete de toutes les sources news"""
    queries = [
        "Bourse Casablanca BVC",
        "Bank Al-Maghrib taux directeur",
        "OCP Maroc phosphate",
        "Maroc telecom IAM résultats",
        "Federal Reserve interest rate",
        "BCE taux BCE politique monetaire",
        "petrole brent OPEC",
        "or gold inflation",
        "economie Maroc croissance PIB",
        "AMMC Maroc publication",
    ]
    google_news   = get_google_news(queries)
    twitter_sigs  = get_twitter_signals()
    boursenews    = _scrape_boursenews()
    ammc_news     = _scrape_ammc()
    oc_news       = _scrape_oc()

    return {
        "google":   google_news,
        "twitter":  twitter_sigs,
        "boursenews": boursenews,
        "ammc":     ammc_news,
        "oc":       oc_news,
    }


def _scrape_boursenews():
    try:
        r    = requests.get("https://www.boursenews.ma/", headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        news = []
        for item in soup.select("article,h2 a,h3 a,.title a")[:10]:
            t = item.get_text(strip=True)
            if len(t) > 20: news.append(t[:160])
        return list(dict.fromkeys(news))[:5]
    except: return []

def _scrape_ammc():
    try:
        r    = requests.get("https://www.ammc.ma/fr/actualites", headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        items = []
        for item in soup.select(".views-row,article,h3 a,h2 a")[:6]:
            t = item.get_text(strip=True)
            if len(t) > 20: items.append(t[:160])
        return list(dict.fromkeys(items))[:4]
    except: return []

def _scrape_oc():
    try:
        r    = requests.get("https://www.oc.gov.ma/fr/publications", headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        items = []
        for item in soup.select("article,.views-row,h3 a,h2 a")[:5]:
            t = item.get_text(strip=True)
            if len(t) > 20: items.append(t[:160])
        return list(dict.fromkeys(items))[:3]
    except: return []


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 4 — TRADINGVIEW ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def get_tv_analysis(ticker):
    try:
        handler = TA_Handler(symbol=ticker, screener="morocco", exchange="CSE", interval=Interval.INTERVAL_15_MINUTES)
        a = handler.get_analysis()
        return {
            "ticker":         ticker,
            "close":          a.indicators.get("close", 0),
            "volume":         a.indicators.get("volume", 0),
            "rsi":            a.indicators.get("RSI", 50),
            "macd":           a.indicators.get("MACD.macd", 0),
            "macd_signal":    a.indicators.get("MACD.signal", 0),
            "macd_hist":      a.indicators.get("MACD.hist", 0),
            "ema20":          a.indicators.get("EMA20", 0),
            "ema50":          a.indicators.get("EMA50", 0),
            "ema200":         a.indicators.get("EMA200", 0),
            "vwap":           a.indicators.get("VWAP", 0),
            "bb_upper":       a.indicators.get("BB.upper", 0),
            "bb_lower":       a.indicators.get("BB.lower", 0),
            "stoch_k":        a.indicators.get("Stoch.K", 50),
            "stoch_d":        a.indicators.get("Stoch.D", 50),
            "adx":            a.indicators.get("ADX", 0),
            "cci":            a.indicators.get("CCI20", 0),
            "atr":            a.indicators.get("ATR", 0),
            "change":         a.indicators.get("change", 0),
            "high":           a.indicators.get("high", 0),
            "low":            a.indicators.get("low", 0),
            "recommendation": a.summary.get("RECOMMENDATION", "NEUTRAL"),
            "buy_signals":    a.summary.get("BUY", 0),
            "sell_signals":   a.summary.get("SELL", 0),
            "neutral_signals":a.summary.get("NEUTRAL", 0),
        }
    except Exception as e:
        print(f"[TV] {ticker}: {e}")
        return None

def get_masi():
    try:
        h = TA_Handler(symbol="MASI", screener="morocco", exchange="CSE", interval=Interval.INTERVAL_15_MINUTES)
        a = h.get_analysis()
        return {"close":a.indicators.get("close",0),"change":a.indicators.get("change",0),
                "rsi":a.indicators.get("RSI",50),"rec":a.summary.get("RECOMMENDATION","NEUTRAL"),
                "buy":a.summary.get("BUY",0),"sell":a.summary.get("SELL",0)}
    except:
        return {"close":0,"change":0,"rsi":50,"rec":"NEUTRAL","buy":0,"sell":0}


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 5 — SCORING ADAPTATIF WALL STREET LEVEL
# ═══════════════════════════════════════════════════════════════════════════════

def score_action(tv, info, vp, macro, rates, learnings):
    """
    Score 0-100 multi-facteurs Wall Street:
    - Technique (RSI, MACD, EMA, Stoch, ADX) pondéré adaptatif
    - Volume Profile (POC, VAH, VAL)
    - Macro regime (risk-on/off, inflation, taux)
    - Corrélations (BAM, Brent, Phosphate)
    - Secteur favorisé par macro globale
    """
    if not tv: return 0
    w = learnings.get("indicator_weights", {
        "rsi":1.0,"macd":1.0,"ema":1.0,"volume":1.0,
        "stoch":1.0,"adx":1.0,"vp":1.0,"bam_corr":1.0,
        "brent_corr":1.0,"phos_corr":1.0,"macro_regime":1.0
    })
    score = 50

    rsi      = tv.get("rsi", 50)
    macd     = tv.get("macd", 0)
    macd_sig = tv.get("macd_signal", 0)
    macd_h   = tv.get("macd_hist", 0)
    close    = tv.get("close", 0)
    ema20    = tv.get("ema20", 0)
    ema50    = tv.get("ema50", 0)
    ema200   = tv.get("ema200", 0)
    vwap     = tv.get("vwap", 0)
    stoch_k  = tv.get("stoch_k", 50)
    stoch_d  = tv.get("stoch_d", 50)
    adx      = tv.get("adx", 0)
    cci      = tv.get("cci", 0)
    buy_sig  = tv.get("buy_signals", 0)
    sell_sig = tv.get("sell_signals", 0)
    vol      = tv.get("volume", 0)
    avg_vol  = info.get("avg_vol", 1)
    sector   = info.get("sector", "")

    # RSI
    if rsi < 25:   score += int(25 * w.get("rsi", 1))
    elif rsi < 35: score += int(15 * w.get("rsi", 1))
    elif rsi < 45: score += int(7  * w.get("rsi", 1))
    elif rsi > 75: score -= int(25 * w.get("rsi", 1))
    elif rsi > 65: score -= int(12 * w.get("rsi", 1))

    # MACD
    if macd > macd_sig and macd_h > 0: score += int(18 * w.get("macd", 1))
    elif macd > macd_sig:               score += int(8  * w.get("macd", 1))
    else:                               score -= int(10 * w.get("macd", 1))

    # EMA cascade
    if close > ema20 > ema50 > ema200:   score += int(20 * w.get("ema", 1))
    elif close > ema20 > ema50:          score += int(12 * w.get("ema", 1))
    elif close > ema20:                  score += int(5  * w.get("ema", 1))
    elif close < ema20 < ema50 < ema200: score -= int(20 * w.get("ema", 1))
    elif close < ema20 < ema50:          score -= int(12 * w.get("ema", 1))

    # VWAP
    if vwap > 0:
        if close > vwap: score += 5
        else:            score -= 5

    # Stochastique
    if stoch_k < 20 and stoch_k > stoch_d: score += int(12 * w.get("stoch", 1))
    elif stoch_k > 80 and stoch_k < stoch_d: score -= int(12 * w.get("stoch", 1))

    # ADX (force tendance)
    if adx > 30: score += int(10 * w.get("adx", 1))
    elif adx > 20: score += int(5 * w.get("adx", 1))

    # CCI
    if cci < -150: score += 12
    elif cci < -100: score += 7
    elif cci > 150: score -= 12
    elif cci > 100: score -= 7

    # Signaux TV (26 indicateurs)
    score += int((buy_sig - sell_sig) * 1.5)

    # Volume
    if avg_vol > 0:
        vr = vol / avg_vol
        if vr > 3:     score += int(18 * w.get("volume", 1))
        elif vr > 2:   score += int(12 * w.get("volume", 1))
        elif vr > 1.5: score += int(6  * w.get("volume", 1))

    # ─── VOLUME PROFILE ───────────────────────────────────────────────────────
    if vp:
        wvp = w.get("vp", 1.0)
        sig = vp.get("signal", "NEUTRE")
        if sig == "ACHAT_FORT":  score += int(25 * wvp)
        elif sig == "ACHAT":     score += int(15 * wvp)
        elif sig == "VENTE":     score -= int(20 * wvp)
        elif sig == "NEUTRE_HAUT": score += int(5 * wvp)
        # Prix proche POC = support fort
        dist = abs(vp.get("dist_poc_pct", 10))
        if dist < 1:  score += int(8 * wvp)
        elif dist < 2: score += int(4 * wvp)

    # ─── MACRO REGIME ─────────────────────────────────────────────────────────
    if macro:
        derived = macro.get("_derived", {})
        regime  = derived.get("risk_regime", "NEUTRE")
        bvc_out = derived.get("bvc_outlook", {})
        wm      = w.get("macro_regime", 1.0)

        # Regime global
        if regime == "RISK_ON":   score += int(10 * wm)
        elif regime == "RISK_OFF": score -= int(8  * wm)

        # Outlook sectoriel
        sector_out = bvc_out.get(sector, "NEUTRE")
        if sector_out == "TRES_POSITIF": score += int(18 * wm)
        elif sector_out == "POSITIF":    score += int(10 * wm)
        elif sector_out == "NEGATIF":    score -= int(12 * wm)

        # VIX
        vix_val = macro.get("vix", {}).get("price", 20)
        if vix_val > 30: score -= int(15 * wm)
        elif vix_val < 15: score += int(5 * wm)

        # Recession risk
        if derived.get("recession_risk"): score -= int(10 * wm)

    # ─── CORRÉLATIONS TAUX (BAM / Fed / ECB) ─────────────────────────────────
    if rates and info.get("bam"):
        bam_taux = rates.get("bam", 3.0) or 3.0
        fed_taux = rates.get("fed", 5.0) or 5.0
        wb       = w.get("bam_corr", 1.0)
        if bam_taux <= 2.5:   score += int(15 * wb)
        elif bam_taux <= 3.0: score += int(8  * wb)
        elif bam_taux >= 4.0: score -= int(10 * wb)
        bam_news = " ".join(rates.get("bam_news", [])).lower()
        if any(k in bam_news for k in ["baisse","assouplissement","accomodante","reduction"]):
            score += int(10 * wb)
        elif any(k in bam_news for k in ["hausse","restrictive","resserrement","inflation"]):
            score -= int(8 * wb)

    # Brent correlation
    if info.get("brent") and macro:
        brent_chg = macro.get("brent", {}).get("change", 0)
        wb2 = w.get("brent_corr", 1.0)
        if brent_chg > 1:    score += int(8 * wb2)
        elif brent_chg < -2: score -= int(10 * wb2)

    # Phosphate correlation
    if info.get("phos") and macro:
        gold_chg = macro.get("gold", {}).get("change", 0)
        dxy_val  = macro.get("dxy", {}).get("price", 103)
        wp = w.get("phos_corr", 1.0)
        if dxy_val > 105:  score += int(12 * wp)  # Dollar fort = exportateurs favorises
        if gold_chg > 0.5: score += int(5  * wp)

    # Secteurs appris
    favs   = learnings.get("secteurs_favorables", [])
    eviter = learnings.get("secteurs_eviter", [])
    if sector in favs:   score += 10
    if sector in eviter: score -= 15

    # Large cap bonus
    if info.get("mc") == "large": score += 5

    return max(0, min(100, score))


def get_top_signals(analyses, vps, macro, rates, learnings, n=3):
    """Génère les TOP N signaux haussiers"""
    scored = []
    for ticker, info in BVC_WATCHLIST.items():
        tv   = analyses.get(ticker)
        vp   = vps.get(ticker)
        if not tv: continue
        s     = score_action(tv, info, vp, macro, rates, learnings)
        close = tv.get("close", 0)
        if close <= 0 or s < 55: continue
        if s > 80:   tp = 0.06
        elif s > 70: tp = 0.05
        elif s > 60: tp = 0.04
        else:        tp = 0.03
        proba = min(95, 45 + s * 0.5)
        vp_signal = vp.get("signal", "N/A") if vp else "N/A"
        vp_poc    = vp.get("poc", 0) if vp else 0
        vp_vah    = vp.get("vah", 0) if vp else 0
        vp_val    = vp.get("val", 0) if vp else 0
        scored.append({
            "ticker":tv["ticker"],"name":info["name"],"sector":info["sector"],"mc":info.get("mc","small"),
            "score":s,"price":close,"target":round(close*(1+tp),2),"stop":round(close*0.98,2),
            "gain_pct":round(tp*100,1),"proba":round(proba),
            "rsi":round(tv.get("rsi",50),1),"macd_cross":tv.get("macd",0)>tv.get("macd_signal",0),
            "adx":round(tv.get("adx",0),1),"change":round(tv.get("change",0),2),
            "recommendation":tv.get("recommendation","NEUTRAL"),
            "buy_signals":tv.get("buy_signals",0),"sell_signals":tv.get("sell_signals",0),
            "volume":tv.get("volume",0),"avg_volume":info["avg_vol"],"stoch_k":round(tv.get("stoch_k",50),1),
            "bam":info.get("bam",False),"brent":info.get("brent",False),"phos":info.get("phos",False),
            "vp_signal":vp_signal,"vp_poc":vp_poc,"vp_vah":vp_vah,"vp_val":vp_val,
            "vp_desc":vp.get("description","") if vp else "",
        })
    return sorted(scored, key=lambda x: x["score"], reverse=True)[:n]


def get_bear_signals(analyses, vps, macro, rates, learnings, n=3):
    """
    Génère les signaux BAISSIERS — actions a éviter ou shorter
    Utile pour savoir ou ne pas rentrer
    """
    bear = []
    for ticker, info in BVC_WATCHLIST.items():
        tv = analyses.get(ticker)
        vp = vps.get(ticker)
        if not tv: continue
        s     = score_action(tv, info, vp, macro, rates, learnings)
        close = tv.get("close", 0)
        if close <= 0 or s > 40: continue
        rsi     = tv.get("rsi", 50)
        sell_sig = tv.get("sell_signals", 0)
        buy_sig  = tv.get("buy_signals", 0)
        vol      = tv.get("volume", 0)
        avg_vol  = info.get("avg_vol", 1)
        vr       = vol / avg_vol if avg_vol > 0 else 1
        vp_signal = vp.get("signal", "NEUTRE") if vp else "NEUTRE"
        risk_pct = round((40 - s) / 40 * 5, 2)
        bear.append({
            "ticker":ticker,"name":info["name"],"sector":info["sector"],
            "score":s,"price":close,"change":round(tv.get("change",0),2),
            "rsi":round(rsi,1),"sell_signals":sell_sig,"buy_signals":buy_sig,
            "vol_ratio":round(vr,1),"vp_signal":vp_signal,
            "risk_pct":risk_pct,
            "reason":_bear_reason(tv, vp, macro, info, rates),
        })
    return sorted(bear, key=lambda x: x["score"])[:n]


def _bear_reason(tv, vp, macro, info, rates):
    reasons = []
    rsi = tv.get("rsi", 50)
    if rsi > 72: reasons.append(f"RSI surachete {rsi:.0f}")
    if tv.get("macd", 0) < tv.get("macd_signal", 0): reasons.append("MACD baissier")
    close = tv.get("close", 0)
    ema20 = tv.get("ema20", 0)
    ema50 = tv.get("ema50", 0)
    if close < ema20 < ema50: reasons.append("Sous EMA20/50")
    if vp and vp.get("signal") == "VENTE": reasons.append(f"Prix au-dessus VAH {vp.get('vah',0):.2f}")
    if macro:
        derived = macro.get("_derived", {})
        if derived.get("risk_regime") == "RISK_OFF": reasons.append("Regime Risk-OFF")
        if derived.get("recession_risk"): reasons.append("Risque recession")
    return " · ".join(reasons) if reasons else "Score technique faible"


def check_volume_alerts(analyses):
    alerts = []
    for ticker, info in BVC_WATCHLIST.items():
        a = analyses.get(ticker)
        if not a: continue
        vol = a.get("volume", 0)
        avg = info["avg_vol"]
        if avg > 0 and vol > avg * VOLUME_ALERT_THRESHOLD:
            alerts.append({"ticker":ticker,"name":info["name"],"sector":info["sector"],
                           "volume":vol,"avg_volume":avg,"ratio":round(vol/avg,1),
                           "price":a.get("close",0),"change":a.get("change",0),"rsi":a.get("rsi",50)})
    return sorted(alerts, key=lambda x: x["ratio"], reverse=True)


def get_hold_candidates(analyses, vps, macro, rates, learnings):
    candidates = []
    for ticker, info in BVC_WATCHLIST.items():
        tv = analyses.get(ticker)
        vp = vps.get(ticker)
        if not tv: continue
        s = score_action(tv, info, vp, macro, rates, learnings)
        close  = tv.get("close", 0)
        ema200 = tv.get("ema200", 0)
        if close <= 0 or s < 78: continue
        if ema200 > 0 and close > ema200 * 0.93:
            candidates.append({"ticker":ticker,"name":info["name"],"sector":info["sector"],
                               "score":s,"price":close,"target30":round(close*1.30,2),
                               "proba":round(min(82,40+s*0.5))})
    return sorted(candidates, key=lambda x: x["score"], reverse=True)[:2]


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 6 — GROQ WALL STREET SYNTHESIS (Gratuit)
# ═══════════════════════════════════════════════════════════════════════════════

def wall_street_synthesis(signals, bear_signals, spread_opps, macro, rates,
                           vps, all_news, masi, learnings):
    """
    Synthese Wall Street complète via Groq LLM llama3-70b
    Pense comme un PM de hedge fund top tier:
    - Regime macro
    - Catalyseurs
    - Conviction et timing
    - Risques
    """
    if not GROQ_AVAILABLE or not GROQ_API_KEY:
        return ""
    try:
        client  = Groq(api_key=GROQ_API_KEY)
        derived = macro.get("_derived", {}) if macro else {}
        twitter_highlights = [s["text"][:100] for s in all_news.get("twitter", [])[:5]]
        google_highlights  = [n["headline"][:100] for n in all_news.get("google", [])[:5]]
        bvc_outlook = derived.get("bvc_outlook", {})

        prompt = f"""Tu es Baraka, un trader quantitatif de niveau Wall Street specialise sur la Bourse de Casablanca (BVC).
Tu analyses comme un PM de hedge fund top tier. Tu dois ANTICIPER le marche, pas le suivre.

=== REGIME MACRO GLOBAL ===
Risk Regime: {derived.get('risk_regime','N/A')}
Inflation: {derived.get('inflation_regime','N/A')}
VIX: {macro.get('vix',{}).get('price',20):.1f} ({derived.get('vix_level','N/A')})
Dollar: {derived.get('dollar_trend','N/A')} (DXY: {macro.get('dxy',{}).get('price',103):.1f})
Yield Spread 10Y-2Y: {derived.get('yield_spread',0):.2f}% ({'INVERSION - SIGNAL RECESSION' if derived.get('recession_risk') else 'Normal'})
S&P500: {macro.get('sp500',{}).get('change',0):+.2f}%
Brent: {macro.get('brent',{}).get('change',0):+.2f}%
Gold: {macro.get('gold',{}).get('change',0):+.2f}%
Copper: {macro.get('copper',{}).get('change',0):+.2f}%

=== BANQUES CENTRALES ===
Fed Rate: {rates.get('fed',5.25)}%
ECB Rate: {rates.get('ecb',3.5)}%
BAM Rate: {rates.get('bam',3.0)}%
BAM News: {' | '.join(rates.get('bam_news',[])[:2])}

=== IMPACT BVC PAR SECTEUR ===
{json.dumps(bvc_outlook, ensure_ascii=False)}

=== MASI ===
MASI: {masi.get('change',0):+.2f}% · RSI: {masi.get('rsi',50):.0f} · Signal: {masi.get('rec','NEUTRAL')}

=== TOP 3 SIGNAUX HAUSSIERS ===
{json.dumps([{{'ticker':s['ticker'],'score':s['score'],'sector':s['sector'],'vp_signal':s.get('vp_signal',''),'rsi':s['rsi'],'gain_pct':s['gain_pct']}} for s in signals], ensure_ascii=False)}

=== SIGNAUX BAISSIERS (EVITER) ===
{json.dumps([{{'ticker':b['ticker'],'score':b['score'],'reason':b['reason']}} for b in bear_signals], ensure_ascii=False)}

=== VOLUME PROFILE CLES ===
{json.dumps({s['ticker']: {'poc':s.get('vp_poc',0),'vah':s.get('vp_vah',0),'val':s.get('vp_val',0),'signal':s.get('vp_signal','')} for s in signals}, ensure_ascii=False)}

=== NEWS & SENTIMENT ===
Twitter/Banques centrales: {twitter_highlights[:3]}
Google News Maroc: {google_highlights[:3]}
BourseNews: {all_news.get('boursenews',[])[:2]}
AMMC: {all_news.get('ammc',[])[:2]}

=== LEARNINGS PRECEDENTS ===
Precision: {learnings.get('accuracy_rate',0)}% · Sessions: {learnings.get('total_analyzed',0)}
Secteurs favorables: {learnings.get('secteurs_favorables',[])}
Derniere lecon: {learnings.get('lessons',[''])[-1].get('analyse','') if learnings.get('lessons') else 'Premier jour'}

Analyse en 4-5 phrases TRES CONCISES et ACTIONNABLES:
1. Quel est le regime et comment il impacte le BVC aujourd'hui?
2. Pourquoi ces 3 actions specifiquement? Quel est le catalyseur?
3. Ou est le smart money (Volume Profile)?
4. Quels sont les principaux risques a surveiller?
5. Une recommandation de timing precise (10h-12h, 12h-14h, 14h-cloture)?

Reponds en francais, direct, comme un trader, pas comme un analyste. Pas de markdown, pas de listes."""

        resp = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.25,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[GROQ SYNTHESIS] {e}")
        return ""


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 7 — CARNET D'ORDRES (Wafabourse)
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_order_book(ticker, tv_data=None):
    """Carnet d'ordres + estimation spread via TV si Wafa indisponible"""
    ob = {"ticker":ticker,"best_bid":0,"best_ask":0,"spread_pct":0,"spread_mad":0,
          "quick_gain_pct":0,"liquidity_score":0,"total_depth_mad":0,
          "spread_opportunity":False,"source":"N/A"}
    headers = {"User-Agent":"Mozilla/5.0","Referer":"https://www.wafabourse.com/"}
    for url in [f"https://www.wafabourse.com/cours/{ticker.lower()}",
                f"https://www.casablanca-bourse.com/bourseweb/cours-societe.aspx?codeValeur={ticker}"]:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code != 200: continue
            text = r.text.lower()
            bids, asks = [], []
            for pat in [r'offre["\s:]+([0-9]+[.,][0-9]+)',r'bid["\s:]+([0-9]+[.,][0-9]+)']:
                for m in re.findall(pat, text):
                    try:
                        v = float(m.replace(",","."))
                        if 1 < v < 100000: bids.append(v)
                    except: pass
            for pat in [r'demande["\s:]+([0-9]+[.,][0-9]+)',r'ask["\s:]+([0-9]+[.,][0-9]+)']:
                for m in re.findall(pat, text):
                    try:
                        v = float(m.replace(",","."))
                        if 1 < v < 100000: asks.append(v)
                    except: pass
            if bids and asks:
                bb = max(bids[:3])
                ba = min(asks[:3])
                if ba > bb > 0:
                    sp = (ba - bb) / bb * 100
                    ob.update({"best_bid":round(bb,2),"best_ask":round(ba,2),
                               "spread_pct":round(sp,2),"spread_mad":round(ba-bb,2),
                               "quick_gain_pct":round(sp*0.6,2),"source":url.split("/")[2],
                               "spread_opportunity":sp>=1.5})
                    break
        except: continue
    # Fallback TV
    if ob["best_bid"] == 0 and tv_data:
        close = tv_data.get("close",0)
        high  = tv_data.get("high",0)
        low   = tv_data.get("low",0)
        if close > 0 and high > low:
            sp = (high - low) / close * 100
            bb = low + (high - low) * 0.35
            ba = low + (high - low) * 0.65
            vol_depth = tv_data.get("volume",0) * close * 0.25
            ob.update({"best_bid":round(bb,2),"best_ask":round(ba,2),
                       "spread_pct":round(sp,2),"spread_mad":round(ba-bb,2),
                       "quick_gain_pct":round(sp*0.5,2),"source":"TV (estime)",
                       "spread_opportunity":sp>=1.5,"total_depth_mad":round(vol_depth),
                       "liquidity_score":min(95,int(vol_depth/10000))})
    return ob

def analyze_spread_opportunities(analyses):
    """Detecte les meilleures opportunites de spread BVC"""
    opps = []
    priority = [t for t,i in BVC_WATCHLIST.items() if i.get("mc") in ["large","mid"] and i["avg_vol"]>=5000]
    for ticker in priority:
        tv = analyses.get(ticker)
        ob = scrape_order_book(ticker, tv)
        time.sleep(0.4)
        if not ob["spread_opportunity"]: continue
        if ob["liquidity_score"] < 35: continue
        if ob["quick_gain_pct"] < 1.5: continue
        if tv and tv.get("rsi",50) > 72: continue
        rsi = tv.get("rsi",50) if tv else 50
        sp  = ob["spread_pct"]
        liq = ob["liquidity_score"]
        opp_score = min(40,sp*15) + min(30,liq*0.3) + min(20,ob["quick_gain_pct"]*8)
        if BVC_WATCHLIST[ticker].get("mc") == "large": opp_score += 10
        opps.append({**ob,"sector":BVC_WATCHLIST[ticker]["sector"],
                     "name":BVC_WATCHLIST[ticker]["name"],"opp_score":round(opp_score,1),"rsi":rsi,
                     "volume":tv.get("volume",0) if tv else 0,
                     "avg_volume":BVC_WATCHLIST[ticker]["avg_vol"]})
    return sorted(opps, key=lambda x: x["opp_score"], reverse=True)[:3]


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 8 — TRADE LOG & PNL
# ═══════════════════════════════════════════════════════════════════════════════

def load_learnings():
    if os.path.exists(LEARNING_FILE):
        with open(LEARNING_FILE,"r",encoding="utf-8") as f: return json.load(f)
    return {"lessons":[],"indicator_weights":{"rsi":1.0,"macd":1.0,"ema":1.0,"volume":1.0,"stoch":1.0,"adx":1.0,"vp":1.0,"bam_corr":1.0,"brent_corr":1.0,"phos_corr":1.0,"macro_regime":1.0},
            "secteurs_favorables":[],"secteurs_eviter":[],"accuracy_history":[],"accuracy_rate":0,"total_analyzed":0,"last_updated":""}

def save_learnings(data):
    with open(LEARNING_FILE,"w",encoding="utf-8") as f: json.dump(data,f,indent=2,ensure_ascii=False)

def load_trades():
    if os.path.exists(TRADE_LOG_FILE):
        with open(TRADE_LOG_FILE,"r",encoding="utf-8") as f: return json.load(f)
    return []

def get_open_trades():
    return [t for t in load_trades() if t.get("status")=="open"]

def get_week_pnl():
    trades = load_trades()
    today  = datetime.date.today()
    ws     = today - datetime.timedelta(days=today.weekday())
    wt     = [t for t in trades if t.get("date","") >= str(ws)]
    pnl    = sum(t.get("pnl_pct",0) for t in wt if t.get("status")=="closed")
    wins   = sum(1 for t in wt if t.get("pnl_pct",0)>0 and t.get("status")=="closed")
    total  = sum(1 for t in wt if t.get("status")=="closed")
    return {"total_pnl":round(pnl,2),"wins":wins,"total":total,
            "open":len(get_open_trades()),"win_rate":round(wins/total*100) if total>0 else 0}


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 9 — EMAIL BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def send_email(subject, html):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = GMAIL_USER
        msg["To"]      = TO_EMAIL
        msg.attach(MIMEText(html,"html"))
        with smtplib.SMTP_SSL("smtp.gmail.com",465) as s:
            s.login(GMAIL_USER,GMAIL_PASSWORD)
            s.sendmail(GMAIL_USER,TO_EMAIL,msg.as_string())
        print(f"[BARAKA] Email: {subject}")
        return True
    except Exception as e:
        print(f"[BARAKA] Email error: {e}")
        return False


def build_signal_card(s, rank):
    color  = "#00C87A" if s["score"]>=70 else "#C9A84C"
    rc     = "#FF4560" if s["rsi"]>70 else "#00C87A" if s["rsi"]<35 else "#C9A84C"
    vr     = round(s["volume"]/s["avg_volume"],1) if s["avg_volume"]>0 else 1
    vc     = "#00C87A" if vr>2 else "#F59E0B" if vr>1.5 else "#9CA3AF"
    cc     = "#00C87A" if s["change"]>=0 else "#FF4560"
    corr   = ""
    if s.get("bam"):   corr+="<span style='font-size:9px;background:rgba(0,150,255,0.15);color:#60A5FA;padding:2px 6px;border-radius:3px;margin-left:3px'>BAM</span>"
    if s.get("brent"): corr+="<span style='font-size:9px;background:rgba(255,140,0,0.15);color:#FB923C;padding:2px 6px;border-radius:3px;margin-left:3px'>BRENT</span>"
    if s.get("phos"):  corr+="<span style='font-size:9px;background:rgba(100,200,100,0.15);color:#4ADE80;padding:2px 6px;border-radius:3px;margin-left:3px'>PHOSPHATE</span>"
    vp_color = "#00C87A" if "ACHAT" in s.get("vp_signal","") else "#FF4560" if "VENTE" in s.get("vp_signal","") else "#C9A84C"
    return f"""<div style="background:#171C2C;border-radius:10px;padding:16px;margin-bottom:14px;border-left:4px solid {color}">
<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px">
<div><span style="font-size:20px;font-weight:900;color:{color};font-family:monospace">#{rank} {s['ticker']}</span>
<span style="font-size:10px;color:#6B7280;margin-left:8px">{s['name']}</span><br>
<span style="font-size:10px;background:rgba(201,168,76,0.1);color:#C9A84C;padding:2px 6px;border-radius:3px">{s['sector']}</span>{corr}</div>
<div style="text-align:right"><span style="background:rgba(0,200,122,0.15);color:#00C87A;border:1px solid rgba(0,200,122,0.3);font-size:10px;padding:3px 10px;border-radius:4px;font-weight:700">ACHAT</span><br>
<span style="font-size:11px;color:{cc};font-weight:700;display:block;margin-top:3px">{'+' if s['change']>=0 else ''}{s['change']}%</span></div></div>
<table style="width:100%;font-size:12px;border-collapse:collapse">
<tr><td style="color:#6B7280;padding:3px 0">Entree</td><td style="color:#E8E4D6;font-weight:700;text-align:right">{s['price']:.2f} MAD</td>
<td style="color:#6B7280;padding:3px 12px">Cible</td><td style="color:#00C87A;font-weight:700;text-align:right">{s['target']:.2f} (+{s['gain_pct']}%)</td></tr>
<tr><td style="color:#6B7280;padding:3px 0">Stop</td><td style="color:#FF4560;font-weight:700;text-align:right">{s['stop']:.2f} MAD</td>
<td style="color:#6B7280;padding:3px 12px">RSI</td><td style="color:{rc};font-weight:700;text-align:right">{s['rsi']}</td></tr>
<tr><td style="color:#6B7280;padding:3px 0">MACD</td><td colspan="3" style="color:#9CA3AF;text-align:right">{'Haussier' if s['macd_cross'] else 'Baissier'}</td></tr>
<tr><td style="color:#6B7280;padding:3px 0">Volume</td><td colspan="3" style="color:{vc};text-align:right">x{vr} ({int(s['volume']):,} vs {int(s['avg_volume']):,})</td></tr>
<tr><td style="color:#6B7280;padding:3px 0">VP Signal</td>
<td colspan="3" style="color:{vp_color};text-align:right;font-weight:700">{s.get('vp_signal','N/A')} · POC:{s.get('vp_poc',0):.2f} · VAH:{s.get('vp_vah',0):.2f} · VAL:{s.get('vp_val',0):.2f}</td></tr>
<tr><td style="color:#6B7280;padding:3px 0;font-size:11px" colspan="4" style="color:#9CA3AF">{s.get('vp_desc','')}</td></tr>
</table>
<div style="margin-top:8px">
<div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:3px">
<span style="color:#6B7280">Score Baraka (adaptatif)</span><span style="color:{color};font-weight:700">{s['score']}/100</span></div>
<div style="background:#0A0D14;border-radius:3px;height:4px"><div style="height:100%;border-radius:3px;background:{color};width:{s['score']}%"></div></div>
<div style="display:flex;justify-content:space-between;font-size:11px;margin-top:5px">
<span style="color:#6B7280">Proba +2%</span><span style="color:{color};font-weight:700">{s['proba']}%</span></div>
</div></div>"""


def build_bear_card(b):
    rc = "#FF4560" if b["rsi"]>70 else "#F59E0B" if b["rsi"]>60 else "#9CA3AF"
    return f"""<div style="background:#1A0D10;border-radius:8px;padding:12px;margin-bottom:8px;border-left:3px solid #FF4560">
<div style="display:flex;justify-content:space-between;align-items:center">
<div><span style="font-size:16px;font-weight:900;color:#FF4560;font-family:monospace">{b['ticker']}</span>
<span style="font-size:10px;color:#6B7280;margin-left:6px">{b['name']} · {b['sector']}</span></div>
<span style="background:rgba(255,69,96,0.15);color:#FF4560;font-size:9px;padding:2px 8px;border-radius:4px;font-weight:700">EVITER</span></div>
<div style="font-size:11px;color:#9CA3AF;margin-top:6px">Score: <span style="color:#FF4560;font-weight:700">{b['score']}/100</span> · RSI: <span style="color:{rc}">{b['rsi']}</span> · {b.get('reason','')}</div>
</div>"""


def build_macro_section(macro, rates):
    if not macro: return ""
    derived = macro.get("_derived", {})
    regime  = derived.get("risk_regime","NEUTRE")
    rc      = "#00C87A" if regime=="RISK_ON" else "#FF4560" if regime=="RISK_OFF" else "#C9A84C"
    inf_reg = derived.get("inflation_regime","STABLE")
    ic      = "#FF4560" if inf_reg=="INFLATION" else "#00C87A" if inf_reg=="DEFLATION" else "#C9A84C"
    ys      = derived.get("yield_spread",0)
    yc      = "#FF4560" if ys < 0 else "#00C87A"
    vix_v   = macro.get("vix",{}).get("price",20)
    vix_c   = "#00C87A" if vix_v<15 else "#F59E0B" if vix_v<25 else "#FF4560"
    items   = [
        ("S&P500",    macro.get("sp500",{}).get("change",0),    "%"),
        ("Brent",     macro.get("brent",{}).get("change",0),    "%"),
        ("Or",        macro.get("gold",{}).get("change",0),     "%"),
        ("Copper",    macro.get("copper",{}).get("change",0),   "%"),
        ("DXY",       macro.get("dxy",{}).get("price",103),     ""),
        ("USD/MAD",   macro.get("usd_mad",{}).get("price",10),  ""),
        ("US 10Y",    macro.get("us10y",{}).get("price",4),     "%"),
        ("US 2Y",     macro.get("us2y",{}).get("price",4.5),    "%"),
    ]
    rows = ""
    for name, val, unit in items:
        c = "#00C87A" if val>0 else "#FF4560"
        fmt = f"{'+' if val>0 and unit=='%' else ''}{val:.2f}{unit}" if unit else f"{val:.3f}"
        rows += f"<div style='display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:12px'><span style='color:#6B7280'>{name}</span><span style='color:{c};font-weight:700'>{fmt}</span></div>"
    bvc_outlook = derived.get("bvc_outlook",{})
    outlook_html = "".join(f"<span style='font-size:10px;background:rgba({'0,200,122' if v in ['POSITIF','TRES_POSITIF'] else '255,69,96' if v=='NEGATIF' else '201,168,76'},0.15);color:{'#00C87A' if v in ['POSITIF','TRES_POSITIF'] else '#FF4560' if v=='NEGATIF' else '#C9A84C'};padding:2px 8px;border-radius:4px;margin:2px;display:inline-block'>{k}: {v}</span>" for k,v in bvc_outlook.items())
    return f"""<div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px;margin-bottom:14px">
<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">MACRO GLOBAL · REGIME</div>
<div style="display:flex;gap:10px;margin-bottom:12px">
<div style="flex:1;background:#171C2C;border-radius:8px;padding:10px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:4px">REGIME</div>
<div style="font-size:14px;font-weight:900;color:{rc}">{regime}</div></div>
<div style="flex:1;background:#171C2C;border-radius:8px;padding:10px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:4px">INFLATION</div>
<div style="font-size:14px;font-weight:900;color:{ic}">{inf_reg}</div></div>
<div style="flex:1;background:#171C2C;border-radius:8px;padding:10px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:4px">VIX</div>
<div style="font-size:14px;font-weight:900;color:{vix_c}">{vix_v:.1f}</div></div>
<div style="flex:1;background:#171C2C;border-radius:8px;padding:10px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:4px">YIELD SPR.</div>
<div style="font-size:14px;font-weight:900;color:{yc}">{ys:+.2f}%</div></div>
</div>
{rows}
<div style="margin-top:10px"><div style="font-size:9px;color:#6B7280;margin-bottom:6px">IMPACT BVC PAR SECTEUR</div>{outlook_html}</div>
<div style="margin-top:10px;font-size:11px;color:#6B7280">Fed: <span style='color:#60A5FA'>{rates.get('fed',5.25)}%</span> · ECB: <span style='color:#60A5FA'>{rates.get('ecb',3.5)}%</span> · BAM: <span style='color:#60A5FA'>{rates.get('bam',3.0)}%</span></div>
</div>"""


def build_main_email(subject_type, signals, bear_signals, spread_opps, open_trades, hold_cands,
                     all_news, macro, rates, masi, vol_alerts, week_pnl, synthesis, learnings):
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    acc = learnings.get("accuracy_rate",0)
    if subject_type=="matin":   window,instr,ch="FENETRE 1 · 10h00-12h00","Tu achetes maintenant","#00C87A"
    elif subject_type=="midi":  window,instr,ch="FENETRE 2 · 12h00-14h00","Point mi-journee","#F59E0B"
    else:                       window,instr,ch="CLOTURE · 15h15","Decision finale","#C9A84C"

    signals_html = "".join(build_signal_card(s,i+1) for i,s in enumerate(signals))
    bear_html    = "".join(build_bear_card(b) for b in bear_signals)
    bear_section = f"""<div style="background:rgba(255,69,96,0.04);border:1px solid rgba(255,69,96,0.2);border-radius:10px;padding:14px;margin-bottom:14px"><div style="font-size:10px;color:#FF4560;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px">ACTIONS A EVITER AUJOURD'HUI</div>{bear_html}</div>""" if bear_html else ""

    spread_html = ""
    if spread_opps:
        cards = "".join(f"""<div style="background:#171C2C;border-radius:8px;padding:12px;margin-bottom:8px;border-left:3px solid #F59E0B">
<div style="display:flex;justify-content:space-between"><span style="color:#F59E0B;font-weight:900;font-family:monospace">{o['ticker']}</span><span style="font-size:10px;color:#9CA3AF">{o['name']}</span></div>
<div style="font-size:12px;margin-top:6px;display:flex;justify-content:space-between">
<span style="color:#6B7280">Bid <span style="color:#00C87A;font-weight:700">{o['best_bid']:.2f}</span></span>
<span style="color:#6B7280">Ask <span style="color:#FF4560;font-weight:700">{o['best_ask']:.2f}</span></span>
<span style="color:#F59E0B;font-weight:700">Spread {o['spread_pct']:.2f}%</span>
<span style="color:#00C87A;font-weight:700">Gain {o['quick_gain_pct']:.2f}%</span>
<span style="color:#6B7280">Liq {o['liquidity_score']}/100</span></div></div>""" for o in spread_opps)
        spread_html = f"""<div style="background:rgba(245,158,11,0.05);border:1px solid rgba(245,158,11,0.25);border-radius:10px;padding:14px;margin-bottom:14px"><div style="font-size:10px;color:#F59E0B;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px">OPPORTUNITES SPREAD · CARNET D'ORDRES</div>{cards}</div>"""

    macro_html = build_macro_section(macro, rates)

    masi_c = "#00C87A" if masi.get("change",0)>=0 else "#FF4560"
    masi_h = f"""<div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:12px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center">
<div><span style="font-size:10px;color:#6B7280;letter-spacing:2px">MASI</span><br>
<span style="font-size:18px;font-weight:900;color:#E8E4D6;font-family:monospace">{masi.get('close',0):,.2f}</span>
<span style="color:{masi_c};font-weight:700;margin-left:8px">{'+' if masi.get('change',0)>=0 else ''}{masi.get('change',0):.2f}%</span></div>
<div style="text-align:right;font-size:11px;color:#6B7280">RSI <span style="color:#C9A84C">{masi.get('rsi',50):.0f}</span><br>{masi.get('rec','')}</div></div>"""

    synth_html = f"""<div style="background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.25);border-radius:10px;padding:14px;margin-bottom:14px">
<div style="font-size:10px;color:#8B5CF6;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px">SYNTHESE WALL STREET · GROQ AI (Precision {acc}%)</div>
<div style="font-size:12px;color:#E8E4D6;line-height:1.8">{synthesis}</div></div>""" if synthesis else ""

    open_h = ""
    if open_trades:
        rows = "".join(f"<div style='display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05);font-size:12px'><span style='color:#00C87A;font-weight:700;font-family:monospace'>{t.get('ticker','?')}</span><span style='color:#6B7280'>Entree {t.get('entry',0):.2f}</span><span style='color:#C9A84C'>Cible {t.get('target',0):.2f}</span></div>" for t in open_trades)
        open_h = f"<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px;margin-bottom:14px'><div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>POSITIONS OUVERTES</div>{rows}</div>"

    hold_h = ""
    if hold_cands and subject_type=="cloture":
        rows = "".join(f"<div style='background:#171C2C;border-radius:8px;padding:12px;margin-bottom:8px;border-left:3px solid #8B5CF6'><div style='display:flex;justify-content:space-between'><span style='color:#8B5CF6;font-weight:900;font-family:monospace'>{h['ticker']}</span><span style='font-size:10px;color:#9CA3AF'>{h['name']}</span></div><div style='font-size:12px;margin-top:6px;display:flex;justify-content:space-between'><span style='color:#6B7280'>Entree <span style='color:#E8E4D6'>{h['price']:.2f}</span></span><span style='color:#8B5CF6;font-weight:700'>+30%: {h['target30']:.2f}</span></div></div>" for h in hold_cands)
        hold_h = f"<div style='background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.25);border-radius:10px;padding:14px;margin-bottom:14px'><div style='font-size:10px;color:#8B5CF6;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>HOLD SEMAINE · OBJECTIF +30%</div>{rows}</div>"

    vol_h = ""
    if vol_alerts:
        rows = "".join(f"<div style='display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:12px'><span style='color:#FF4560;font-weight:700;font-family:monospace'>{v['ticker']}</span><span style='color:#6B7280'>{v['name']}</span><span style='color:#FF4560;font-weight:700'>x{v['ratio']}</span></div>" for v in vol_alerts[:5])
        vol_h = f"<div style='background:rgba(255,69,96,0.06);border:1px solid rgba(255,69,96,0.25);border-radius:10px;padding:14px;margin-bottom:14px'><div style='font-size:10px;color:#FF4560;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>ALERTES VOLUMES ({len(vol_alerts)} actions)</div>{rows}</div>"

    all_news_items = (
        [("BourseNews",n) for n in all_news.get("boursenews",[])[:3]] +
        [("AMMC",n) for n in all_news.get("ammc",[])[:2]] +
        [("Office Changes",n) for n in all_news.get("oc",[])[:1]] +
        [(n["source"],n["text"]) for n in all_news.get("twitter",[])[:3]] +
        [(n["query"].split()[0],n["headline"]) for n in all_news.get("google",[])[:3]]
    )
    news_rows = "".join(f"<div style='padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.04)'><span style='font-size:9px;color:{'#FF4560' if s=='AMMC' else '#60A5FA' if s in ['FED','ECB','BAM','FMI','BM'] else '#F59E0B' if s=='Office Changes' else '#9CA3AF'};font-weight:700;letter-spacing:1px'>{s}</span><div style='font-size:11px;color:#9CA3AF;margin-top:2px'>{n[:160]}</div></div>" for s,n in all_news_items[:12])
    news_h = f"<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px;margin-bottom:14px'><div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>FLUX MARCHE · NEWS · RESEAUX SOCIAUX</div>{news_rows}</div>"

    pc   = "#00C87A" if week_pnl["total_pnl"]>=0 else "#FF4560"
    pnl_h = f"<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px;margin-bottom:14px'><div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>PNL SEMAINE</div><div style='display:flex;justify-content:space-between;align-items:center'><div><div style='font-size:26px;font-weight:900;color:{pc};font-family:monospace'>{'+' if week_pnl['total_pnl']>=0 else ''}{week_pnl['total_pnl']}%</div><div style='font-size:11px;color:#6B7280'>{week_pnl['wins']}/{week_pnl['total']} trades · Win rate {week_pnl['win_rate']}%</div></div><div style='text-align:right'><div style='font-size:11px;color:#6B7280'>Ouvertes</div><div style='font-size:20px;font-weight:700;color:#C9A84C'>{week_pnl['open']}</div></div></div></div>"

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="background:#0A0D14;color:#E8E4D6;font-family:'Courier New',monospace;margin:0;padding:0">
<div style="max-width:640px;margin:0 auto;padding:20px">
<div style="background:#111520;border:1px solid rgba(201,168,76,0.4);border-radius:14px;padding:20px;text-align:center;margin-bottom:16px">
<div style="font-size:26px;font-weight:900;color:#C9A84C;letter-spacing:6px">BARAKA v4.0</div>
<div style="font-size:10px;color:#6B7280;letter-spacing:2px;margin-top:2px">{now} · WALL STREET LEVEL · {len(BVC_WATCHLIST)} SOCIETES · Precision {acc}%</div>
<div style="display:inline-block;background:rgba(0,200,122,0.1);border:1px solid rgba(0,200,122,0.3);color:{ch};padding:5px 16px;border-radius:20px;font-size:11px;letter-spacing:2px;margin-top:10px">{window}</div></div>
<div style="background:rgba(201,168,76,0.08);border:1px solid rgba(201,168,76,0.25);border-radius:10px;padding:12px;margin-bottom:16px;text-align:center">
<div style="font-size:13px;color:#C9A84C;font-weight:700">{instr}</div></div>
{masi_h}{macro_html}{synth_html}
<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">TOP 3 SIGNAUX HAUSSIERS · VOLUME PROFILE</div>
{signals_html}{spread_html}{bear_section}{open_h}{hold_h}{vol_h}{news_h}{pnl_h}
<div style="text-align:center;font-size:10px;color:#4B5563;margin-top:16px;line-height:1.9">
Confirmez chaque trade manuellement · Max 3/jour · T-15min<br>
<strong style="color:#C9A84C">+5%/jour · Hold semaine = +30% min</strong><br>
TradingView · Wafabourse · yfinance · AMMC · BAM · FRED · Google News · Twitter · Groq LLM</div>
</div></body></html>"""


def send_volume_alert(vol_alerts):
    rows = "".join(f"<tr><td style='color:#FF4560;font-weight:700;padding:8px;font-family:monospace'>{v['ticker']}</td><td style='padding:8px'>{v['name']}</td><td style='padding:8px;color:#FF4560;font-weight:700'>x{v['ratio']}</td><td style='padding:8px;color:#C9A84C'>{int(v['volume']):,}</td><td style='padding:8px;color:#6B7280'>{int(v['avg_volume']):,}</td><td style='padding:8px'>{v['price']:.2f} MAD</td></tr>" for v in vol_alerts)
    html = f"""<body style="background:#0A0D14;color:#E8E4D6;font-family:monospace;padding:20px"><div style="max-width:650px;margin:0 auto">
<div style="background:#111520;border:1px solid rgba(255,69,96,0.4);border-radius:12px;padding:16px;text-align:center;margin-bottom:16px">
<div style="font-size:22px;font-weight:900;color:#C9A84C;letter-spacing:4px">BARAKA</div>
<div style="color:#FF4560;font-size:13px;margin-top:6px;font-weight:700">ALERTE VOLUME ANORMAL · {len(vol_alerts)} ACTION(S) · {datetime.datetime.now().strftime('%H:%M')}</div></div>
<table style="width:100%;border-collapse:collapse;background:#111520;border-radius:10px">
<thead><tr style="background:#171C2C;font-size:10px;color:#6B7280">
<th style="padding:10px;text-align:left">TICKER</th><th style="padding:10px;text-align:left">SOCIETE</th>
<th style="padding:10px;text-align:left">RATIO</th><th style="padding:10px;text-align:left">VOLUME</th>
<th style="padding:10px;text-align:left">MOY.</th><th style="padding:10px;text-align:left">COURS</th>
</tr></thead><tbody>{rows}</tbody></table></div></body>"""
    send_email(f"BARAKA · VOLUME ANORMAL · {', '.join(v['ticker'] for v in vol_alerts[:4])}", html)


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 10 — POST-CLOTURE APPRENTISSAGE
# ═══════════════════════════════════════════════════════════════════════════════

def post_cloture_learning():
    if datetime.datetime.now().weekday() >= 5: return
    print("[BARAKA] === POST-CLOTURE LEARNING ===")
    learnings    = load_learnings()
    trades_today = [t for t in load_trades() if t.get("date","") == str(datetime.date.today())]
    signals_file = f"signals_{datetime.date.today()}.json"
    signals_today = json.load(open(signals_file)) if os.path.exists(signals_file) else []
    macro        = get_global_macro()
    rates        = get_fed_ecb_bam_rates()
    masi         = get_masi()
    market_ctx   = {
        "date":str(datetime.date.today()), "masi":masi,
        "brent":macro.get("brent",{}),"gold":macro.get("gold",{}),"vix":macro.get("vix",{}),
        "sp500":macro.get("sp500",{}),"usd_mad":macro.get("usd_mad",{}),
        "regime":macro.get("_derived",{}).get("risk_regime","NEUTRE"),
        "fed":rates.get("fed"),"ecb":rates.get("ecb"),"bam":rates.get("bam"),
    }
    if not GROQ_AVAILABLE or not GROQ_API_KEY:
        print("[BARAKA] Groq non disponible")
        return
    try:
        client  = Groq(api_key=GROQ_API_KEY)
        prompt  = f"""Tu es Baraka, agent Wall Street BVC. Analyse la session et apprends.
TRADES: {json.dumps(trades_today, ensure_ascii=False)}
SIGNAUX RECOMMANDES: {json.dumps(signals_today[:3], ensure_ascii=False)}
CONTEXTE: {json.dumps(market_ctx, ensure_ascii=False)}
POIDS ACTUELS: {json.dumps(learnings.get("indicator_weights",{}), ensure_ascii=False)}
LECONS PRECEDENTES: {json.dumps(learnings.get("lessons",[])[-5:], ensure_ascii=False)}

Reponds UNIQUEMENT en JSON valide:
{{"analyse_du_jour":"...","lecons_apprises":["...","...","..."],"nouveaux_poids":{{"rsi":1.0,"macd":1.0,"ema":1.0,"volume":1.0,"stoch":1.0,"adx":1.0,"vp":1.0,"bam_corr":1.0,"brent_corr":1.0,"phos_corr":1.0,"macro_regime":1.0}},"secteurs_favorables":["..."],"secteurs_eviter":["..."],"patterns_detectes":["..."],"score_precision_jour":75,"recommandations_demain":"..."}}"""
        resp   = client.chat.completions.create(model="llama3-70b-8192", messages=[{"role":"user","content":prompt}], max_tokens=1200, temperature=0.25)
        text   = resp.choices[0].message.content.strip()
        clean  = text.replace("```json","").replace("```","").strip()
        start  = clean.find("{"); end = clean.rfind("}")+1
        result = json.loads(clean[start:end]) if start>=0 and end>start else None
        if result:
            learnings["lessons"].append({"date":str(datetime.date.today()),"analyse":result.get("analyse_du_jour",""),"lecons":result.get("lecons_apprises",[]),"patterns":result.get("patterns_detectes",[]),"precision":result.get("score_precision_jour",0),"demain":result.get("recommandations_demain","")})
            if len(learnings["lessons"]) > 60: learnings["lessons"] = learnings["lessons"][-60:]
            for k,v in result.get("nouveaux_poids",{}).items():
                if k in learnings["indicator_weights"]:
                    learnings["indicator_weights"][k] = round(learnings["indicator_weights"][k]*0.7+v*0.3,3)
            learnings["secteurs_favorables"] = result.get("secteurs_favorables",[])
            learnings["secteurs_eviter"]     = result.get("secteurs_eviter",[])
            learnings["total_analyzed"]      = learnings.get("total_analyzed",0)+1
            hist = learnings.get("accuracy_history",[])
            hist.append({"date":str(datetime.date.today()),"score":result.get("score_precision_jour",0)})
            learnings["accuracy_history"] = hist[-30:]
            learnings["accuracy_rate"]    = round(sum(h["score"] for h in hist)/len(hist),1)
            learnings["last_updated"]     = str(datetime.datetime.now())
            save_learnings(learnings)
            _send_learning_email(result, learnings)
            print(f"[BARAKA] Learning OK · Precision: {result.get('score_precision_jour',0)}%")
    except Exception as e:
        print(f"[BARAKA LEARNING] {e}")


def _send_learning_email(result, learnings):
    acc   = learnings.get("accuracy_rate",0)
    total = learnings.get("total_analyzed",0)
    score = result.get("score_precision_jour",0)
    sc    = "#00C87A" if score>=70 else "#F59E0B" if score>=50 else "#FF4560"
    lecons = "".join(f"<div style='padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:12px;color:#9CA3AF'>• {l}</div>" for l in result.get("lecons_apprises",[]))
    weights_h = "".join(f"<div style='display:flex;justify-content:space-between;padding:4px 0;font-size:12px'><span style='color:#6B7280'>{k.upper()}</span><div style='flex:1;margin:0 10px;background:#0A0D14;border-radius:2px;height:6px;margin-top:7px'><div style='height:100%;background:#C9A84C;border-radius:2px;width:{min(100,int(v*50))}%'></div></div><span style='color:#C9A84C;font-weight:700'>{v:.2f}</span></div>" for k,v in learnings.get("indicator_weights",{}).items())
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="background:#0A0D14;color:#E8E4D6;font-family:'Courier New',monospace;margin:0;padding:0">
<div style="max-width:620px;margin:0 auto;padding:20px">
<div style="background:#111520;border:1px solid rgba(139,92,246,0.4);border-radius:14px;padding:20px;text-align:center;margin-bottom:16px">
<div style="font-size:26px;font-weight:900;color:#C9A84C;letter-spacing:6px">BARAKA v4.0</div>
<div style="font-size:10px;color:#6B7280;margin-top:2px">POST-CLOTURE · APPRENTISSAGE WALL STREET · {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</div>
<div style="display:inline-block;background:rgba(139,92,246,0.12);border:1px solid rgba(139,92,246,0.35);color:#8B5CF6;padding:5px 16px;border-radius:20px;font-size:11px;margin-top:10px">SESSION #{total}</div></div>
<div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:16px;margin-bottom:14px">
<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">ANALYSE BARAKA DU JOUR</div>
<div style="font-size:13px;color:#E8E4D6;line-height:1.7">{result.get('analyse_du_jour','')}</div>
<div style="margin-top:10px;font-size:11px;color:#6B7280;font-style:italic">Demain: {result.get('recommandations_demain','')}</div></div>
<div style="display:flex;gap:10px;margin-bottom:14px">
<div style="flex:1;background:#171C2C;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:12px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:4px">PRECISION JOUR</div><div style="font-size:22px;font-weight:900;color:{sc};font-family:monospace">{score}%</div></div>
<div style="flex:1;background:#171C2C;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:12px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:4px">MOY. 30J</div><div style="font-size:22px;font-weight:900;color:#C9A84C;font-family:monospace">{acc}%</div></div>
<div style="flex:1;background:#171C2C;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:12px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:4px">SESSIONS</div><div style="font-size:22px;font-weight:900;color:#8B5CF6;font-family:monospace">{total}</div></div></div>
<div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:16px;margin-bottom:14px">
<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">LECONS APPRISES</div>{lecons}</div>
<div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:16px;margin-bottom:14px">
<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">POIDS ADAPTATIFS</div>{weights_h}</div>
<div style="text-align:center;font-size:10px;color:#4B5563;margin-top:16px;line-height:1.9">
Baraka apprend chaque soir · Volume Profile + Macro + Twitter + Groq<br>
<strong style="color:#8B5CF6">Session #{total} · Precision cumulee {acc}%</strong></div>
</div></body></html>"""
    send_email(f"BARAKA v4 · POST-CLOTURE · Learning Session #{total}", html)


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 11 — ANALYSE PRINCIPALE & SCHEDULER
# ═══════════════════════════════════════════════════════════════════════════════

def run_full_analysis():
    """Lance l'analyse complète de tous les titres BVC"""
    print(f"[BARAKA] Analyse {len(BVC_WATCHLIST)} societes...")
    analyses = {}
    for ticker in BVC_WATCHLIST:
        a = get_tv_analysis(ticker)
        if a: analyses[ticker] = a
        time.sleep(0.35)
    print(f"[BARAKA] TV: {len(analyses)}/{len(BVC_WATCHLIST)} OK")
    return analyses


def run_vp_analysis(analyses, priority_tickers=None):
    """Lance Volume Profile sur les tickers prioritaires via yfinance"""
    vps = {}
    tickers = priority_tickers or [t for t,i in BVC_WATCHLIST.items() if i.get("mc") in ["large","mid"]]
    print(f"[BARAKA] Volume Profile: {len(tickers)} tickers...")
    for ticker in tickers[:20]:  # Limiter pour eviter timeout
        yf_ticker = BVC_WATCHLIST.get(ticker, {}).get("yf", f"{ticker}.CS")
        vp = get_volume_profile(yf_ticker)
        if vp: vps[ticker] = vp
        time.sleep(0.5)
    print(f"[BARAKA] VP: {len(vps)} OK")
    return vps


def run_alert(subject_type):
    print(f"\n[BARAKA] ═══ {subject_type.upper()} ═══")
    learnings   = load_learnings()
    analyses    = run_full_analysis()
    macro       = get_global_macro()
    rates       = get_fed_ecb_bam_rates()
    masi        = get_masi()
    # VP sur les top actions + celles detectees par TV
    top_tv = sorted([(t,analyses[t].get("buy_signals",0)) for t in analyses if analyses[t].get("buy_signals",0)>6], key=lambda x:-x[1])[:15]
    vp_tickers = [t for t,_ in top_tv] + [t for t,i in BVC_WATCHLIST.items() if i.get("mc")=="large"]
    vps         = run_vp_analysis(analyses, list(set(vp_tickers)))
    signals     = get_top_signals(analyses, vps, macro, rates, learnings, n=3)
    bear_sigs   = get_bear_signals(analyses, vps, macro, rates, learnings, n=3)
    spread_opps = analyze_spread_opportunities(analyses)
    open_trades = get_open_trades()
    all_news    = get_all_news(list(BVC_WATCHLIST.keys()))
    vol_alerts  = check_volume_alerts(analyses)
    week_pnl    = get_week_pnl()
    hold_cands  = get_hold_candidates(analyses, vps, macro, rates, learnings) if subject_type=="cloture" else []

    if subject_type == "matin":
        with open(f"signals_{datetime.date.today()}.json","w") as f:
            json.dump(signals, f, ensure_ascii=False)

    synthesis = wall_street_synthesis(signals, bear_sigs, spread_opps, macro, rates, vps, all_news, masi, learnings)

    html = build_main_email(subject_type, signals, bear_sigs, spread_opps, open_trades, hold_cands,
                            all_news, macro, rates, masi, vol_alerts, week_pnl, synthesis, learnings)

    titles = {
        "matin":   "BARAKA v4 · SIGNAL MATIN · Wall Street Level · BVC",
        "midi":    "BARAKA v4 · POINT MIDI · Garder / Vendre / Switcher",
        "cloture": "BARAKA v4 · CLOTURE BVC · Decision + Hold Semaine",
    }
    send_email(titles[subject_type], html)
    if vol_alerts: send_volume_alert(vol_alerts)


def monitor_volumes():
    now = datetime.datetime.now()
    if now.weekday() >= 5: return
    if not (9 <= now.hour < 16): return
    print("[BARAKA] Surveillance volumes...")
    learnings = load_learnings()
    analyses  = run_full_analysis()
    alerts    = check_volume_alerts(analyses)
    if alerts:
        print(f"[BARAKA] {len(alerts)} alerte(s) volume!")
        send_volume_alert(alerts)


def run_scheduler():
    print("""
╔══════════════════════════════════════════════════════╗
║      BARAKA v4.0 · WALL STREET LEVEL · BVC           ║
║  Volume Profile · Macro Global · Twitter · Groq LLM  ║
╠══════════════════════════════════════════════════════╣
║  10h00 → Signal Matin (VP + Macro + Bear Signals)   ║
║  12h00 → Point Midi                                  ║
║  15h15 → Cloture + Hold semaine +30%                ║
║  16h30 → Post-Cloture Apprentissage Groq            ║
║  /15min → Surveillance Volumes Anormaux             ║
╚══════════════════════════════════════════════════════╝
    """)
    days = [schedule.every().monday, schedule.every().tuesday,
            schedule.every().wednesday, schedule.every().thursday, schedule.every().friday]
    for d in days:
        d.at("10:00").do(run_alert, "matin")
        d.at("12:00").do(run_alert, "midi")
        d.at("15:15").do(run_alert, "cloture")
        d.at("16:30").do(post_cloture_learning)
    schedule.every(15).minutes.do(monitor_volumes)
    print("[BARAKA] Scheduler actif. Baraka anticipe le marche...")
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    run_scheduler()
