"""
BARAKA - BVC Trading Agent
Analyse automatique + Alertes Gmail
3 messages/jour : 10h00, 12h00, 15h15
Macro: Or, Argent, EUR/USD, Taux US, Taux EUR + correlations BVC
"""

import schedule
import time
import datetime
import json
import os
import requests
from tradingview_ta import TA_Handler, Interval
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

GMAIL_USER     = os.environ.get("GMAIL_USER", "mohamed.csaibari@gmail.com")
GMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
TO_EMAIL       = "mohamed.csaibari@gmail.com"

BVC_WATCHLIST = {
    "IAM":    {"name": "Maroc Telecom",           "sector": "Telecom",      "tv": "IAM",     "avg_vol": 120000},
    "ATW":    {"name": "Attijariwafa Bank",        "sector": "Banque",       "tv": "ATW",     "avg_vol": 85000},
    "BCP":    {"name": "Banque Centrale Pop.",     "sector": "Banque",       "tv": "BCP",     "avg_vol": 60000},
    "OCP":    {"name": "OCP Group",                "sector": "Chimie",       "tv": "OCP",     "avg_vol": 95000},
    "BMCE":   {"name": "Bank of Africa",           "sector": "Banque",       "tv": "BMCE",    "avg_vol": 70000},
    "CIH":    {"name": "CIH Bank",                 "sector": "Banque",       "tv": "CIH",     "avg_vol": 45000},
    "HPS":    {"name": "HighTech Payment Sys.",    "sector": "Tech",         "tv": "HPS",     "avg_vol": 15000},
    "SMI":    {"name": "SMI",                      "sector": "Mines",        "tv": "SMI",     "avg_vol": 8000},
    "CMT":    {"name": "Compagnie Miniere Toura.", "sector": "Mines",        "tv": "CMT",     "avg_vol": 5000},
    "MANAGEM":{"name": "Managem",                  "sector": "Mines",        "tv": "MANAGEM", "avg_vol": 12000},
    "LABEL":  {"name": "Label Vie",                "sector": "Distribution", "tv": "LABEL",   "avg_vol": 9000},
    "TMA":    {"name": "Total Maroc",              "sector": "Energie",      "tv": "TMA",     "avg_vol": 7000},
    "WAA":    {"name": "Wafa Assurance",           "sector": "Assurance",    "tv": "WAA",     "avg_vol": 6000},
    "LAC":    {"name": "Lesieur Cristal",          "sector": "Agro",         "tv": "LAC",     "avg_vol": 11000},
    "CDM":    {"name": "Credit du Maroc",          "sector": "Banque",       "tv": "CDM",     "avg_vol": 18000},
}

# Correlations macro -> secteurs BVC
# Positif = correle positivement, Negatif = correle negativement
MACRO_CORRELATIONS = {
    "gold_up": {
        "positif": ["SMI", "MANAGEM", "CMT"],
        "negatif": [],
        "message": "Or en hausse -> mines auriferes favorisees (SMI, Managem, CMT)"
    },
    "silver_up": {
        "positif": ["SMI", "MANAGEM"],
        "negatif": [],
        "message": "Argent en hausse -> mines metaux precieux favorisees"
    },
    "phosphate_up": {
        "positif": ["OCP"],
        "negatif": [],
        "message": "Phosphate en hausse -> OCP directement favorise"
    },
    "brent_up": {
        "positif": ["TMA"],
        "negatif": ["LAC", "LABEL"],
        "message": "Brent en hausse -> TMA favorise, couts transport penalisent LAC/Label Vie"
    },
    "usd_mad_up": {
        "positif": ["OCP", "MANAGEM", "SMI", "CMT"],
        "negatif": ["IAM", "BMCE"],
        "message": "USD fort -> exportateurs (OCP, mines) favorises, importateurs penalises"
    },
    "eur_mad_up": {
        "positif": ["ATW", "BMCE", "BCP"],
        "negatif": [],
        "message": "EUR fort -> banques a exposition Europe favorisees (ATW, BMCE, BCP)"
    },
    "eurusd_up": {
        "positif": ["ATW", "BMCE", "BCP", "CIH"],
        "negatif": ["OCP"],
        "message": "EUR/USD hausse -> flux capitaux europeens vers Maroc, bancaire favorise"
    },
    "us_rates_up": {
        "positif": [],
        "negatif": ["ATW", "BCP", "BMCE", "CIH", "CDM", "WAA"],
        "message": "Taux US en hausse -> fuite capitaux emergents, bancaire marocain sous pression"
    },
    "eur_rates_up": {
        "positif": [],
        "negatif": ["ATW", "BMCE", "BCP"],
        "message": "Taux BCE en hausse -> penalise les banques marocaines exposees zone euro"
    },
    "us_rates_down": {
        "positif": ["ATW", "BCP", "BMCE", "CIH", "CDM", "HPS"],
        "negatif": [],
        "message": "Taux US en baisse -> flux vers emergents, bancaire et tech marocain favorises"
    },
}

VOLUME_ALERT_THRESHOLD = 2.5
TRADE_LOG_FILE = "trade_log.json"


def get_tv_analysis(ticker, screener="morocco", exchange="CSE", interval=None):
    try:
        handler = TA_Handler(
            symbol=ticker,
            screener=screener,
            exchange=exchange,
            interval=interval or Interval.INTERVAL_15_MINUTES
        )
        analysis = handler.get_analysis()
        return {
            "ticker":          ticker,
            "close":           analysis.indicators.get("close", 0),
            "volume":          analysis.indicators.get("volume", 0),
            "rsi":             analysis.indicators.get("RSI", 50),
            "macd":            analysis.indicators.get("MACD.macd", 0),
            "macd_signal":     analysis.indicators.get("MACD.signal", 0),
            "ema20":           analysis.indicators.get("EMA20", 0),
            "ema50":           analysis.indicators.get("EMA50", 0),
            "bb_upper":        analysis.indicators.get("BB.upper", 0),
            "bb_lower":        analysis.indicators.get("BB.lower", 0),
            "change":          analysis.indicators.get("change", 0),
            "recommendation":  analysis.summary.get("RECOMMENDATION", "NEUTRAL"),
            "buy_signals":     analysis.summary.get("BUY", 0),
            "sell_signals":    analysis.summary.get("SELL", 0),
            "neutral_signals": analysis.summary.get("NEUTRAL", 0),
        }
    except Exception as e:
        print(f"[TV ERROR] {ticker}: {e}")
        return None


def get_macro():
    """
    Recupere toutes les donnees macro pertinentes pour BVC:
    - Metaux: Or, Argent, Cuivre, Phosphate, Brent
    - Forex: USD/MAD, EUR/MAD, EUR/USD
    - Taux: US 10Y, EUR 10Y (via ETF proxy TLT/BUND)
    - Indices: S&P500, CAC40, MSCI EM
    """
    macro = {}

    sources = {
        # Metaux precieux
        "gold":       ("GOLD",    "cfd",   "OANDA",  Interval.INTERVAL_1_DAY),
        "silver":     ("SILVER",  "cfd",   "OANDA",  Interval.INTERVAL_1_DAY),
        "copper":     ("COPPER",  "cfd",   "OANDA",  Interval.INTERVAL_1_DAY),
        "brent":      ("USOIL",   "cfd",   "OANDA",  Interval.INTERVAL_1_DAY),
        # Forex
        "usd_mad":    ("USDMAD",  "forex", "FX_IDC", Interval.INTERVAL_1_DAY),
        "eur_mad":    ("EURMAD",  "forex", "FX_IDC", Interval.INTERVAL_1_DAY),
        "eur_usd":    ("EURUSD",  "forex", "FX_IDC", Interval.INTERVAL_1_DAY),
        "usd_index":  ("DXY",     "cfd",   "OANDA",  Interval.INTERVAL_1_DAY),
        # Taux US (proxy via futures)
        "us_10y":     ("US10Y",   "bond",  "CBOE",   Interval.INTERVAL_1_DAY),
        "us_2y":      ("US02Y",   "bond",  "CBOE",   Interval.INTERVAL_1_DAY),
        # Taux EUR (proxy Bund)
        "eur_10y":    ("DE10Y",   "bond",  "CBOE",   Interval.INTERVAL_1_DAY),
        # Indices mondiaux
        "sp500":      ("SPX",     "index", "SP",     Interval.INTERVAL_1_DAY),
        "cac40":      ("CAC40",   "index", "EURONEXT", Interval.INTERVAL_1_DAY),
        "msci_em":    ("EEM",     "fund",  "AMEX",   Interval.INTERVAL_1_DAY),
    }

    for name, (symbol, screener, exchange, interval) in sources.items():
        try:
            handler = TA_Handler(
                symbol=symbol,
                screener=screener,
                exchange=exchange,
                interval=interval
            )
            analysis = handler.get_analysis()
            macro[name] = {
                "price":  round(analysis.indicators.get("close", 0), 4),
                "change": round(analysis.indicators.get("change", 0), 3),
                "rsi":    round(analysis.indicators.get("RSI", 50), 1),
            }
            print(f"[MACRO] {name}: {macro[name]['price']} ({macro[name]['change']:+.2f}%)")
        except Exception as e:
            print(f"[MACRO ERROR] {name}: {e}")
            macro[name] = {"price": 0, "change": 0, "rsi": 50}
        time.sleep(0.3)

    return macro


def analyze_macro_impact(macro):
    """
    Analyse l'impact des donnees macro sur les secteurs BVC.
    Retourne une liste de signaux macro avec tickers impactes.
    """
    signals = []
    threshold = 0.3  # variation significative en %

    checks = [
        ("gold",      "gold_up",      "gold_down",     "Or"),
        ("silver",    "silver_up",    None,            "Argent"),
        ("brent",     "brent_up",     None,            "Brent"),
        ("usd_mad",   "usd_mad_up",   None,            "USD/MAD"),
        ("eur_mad",   "eur_mad_up",   None,            "EUR/MAD"),
        ("eur_usd",   "eurusd_up",    None,            "EUR/USD"),
        ("us_10y",    "us_rates_up",  "us_rates_down", "Taux US 10Y"),
        ("eur_10y",   "eur_rates_up", None,            "Taux EUR 10Y"),
    ]

    for key, signal_up, signal_down, label in checks:
        data = macro.get(key, {})
        chg  = data.get("change", 0)

        if chg > threshold and signal_up and signal_up in MACRO_CORRELATIONS:
            corr = MACRO_CORRELATIONS[signal_up]
            signals.append({
                "label":    label,
                "change":   chg,
                "direction": "hausse",
                "message":  corr["message"],
                "favorise": corr["positif"],
                "penalise": corr["negatif"],
            })
        elif chg < -threshold and signal_down and signal_down in MACRO_CORRELATIONS:
            corr = MACRO_CORRELATIONS[signal_down]
            signals.append({
                "label":    label,
                "change":   chg,
                "direction": "baisse",
                "message":  corr["message"],
                "favorise": corr["positif"],
                "penalise": corr["negatif"],
            })

    return signals


def get_macro_score_bonus(ticker, macro_signals):
    """Bonus/malus de score base sur correlations macro"""
    bonus = 0
    for sig in macro_signals:
        if ticker in sig["favorise"]:
            bonus += 12
        if ticker in sig["penalise"]:
            bonus -= 10
    return bonus


def scrape_boursenews():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get("https://www.boursenews.ma/", headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        news = []
        for item in soup.select("article, .news-item, h2 a, h3 a")[:8]:
            text = item.get_text(strip=True)
            if len(text) > 20:
                news.append(text[:150])
        return news[:5]
    except Exception as e:
        print(f"[BOURSENEWS ERROR] {e}")
        return ["Impossible de recuperer les news"]


def check_volume_alerts(analyses):
    alerts = []
    for ticker, info in BVC_WATCHLIST.items():
        a = analyses.get(ticker)
        if not a:
            continue
        vol = a.get("volume", 0)
        avg = info["avg_vol"]
        if avg > 0 and vol > avg * VOLUME_ALERT_THRESHOLD:
            alerts.append({
                "ticker":         ticker,
                "name":           info["name"],
                "volume":         vol,
                "avg_volume":     avg,
                "ratio":          round(vol / avg, 1),
                "price":          a.get("close", 0),
                "recommendation": a.get("recommendation", "NEUTRAL"),
            })
    return sorted(alerts, key=lambda x: x["ratio"], reverse=True)


def score_action(analysis, info, macro_signals=None):
    if not analysis:
        return 0
    score    = 50
    rsi      = analysis.get("rsi", 50)
    macd     = analysis.get("macd", 0)
    macd_sig = analysis.get("macd_signal", 0)
    close    = analysis.get("close", 0)
    ema20    = analysis.get("ema20", 0)
    ema50    = analysis.get("ema50", 0)
    buy_sig  = analysis.get("buy_signals", 0)
    sell_sig = analysis.get("sell_signals", 0)
    vol      = analysis.get("volume", 0)
    avg_vol  = info.get("avg_vol", 1)

    if rsi < 30:   score += 20
    elif rsi < 40: score += 10
    elif rsi > 70: score -= 20
    elif rsi > 60: score -= 10

    if macd > macd_sig: score += 15
    else:               score -= 10

    if close > ema20 > ema50:   score += 15
    elif close < ema20 < ema50: score -= 15

    score += (buy_sig - sell_sig) * 2

    if avg_vol > 0 and vol > avg_vol * 1.5:
        score += 10

    if macro_signals:
        score += get_macro_score_bonus(info["tv"], macro_signals)

    return max(0, min(100, score))


def get_top_signals(analyses, macro_signals, n=3):
    scored = []
    for ticker, info in BVC_WATCHLIST.items():
        a = analyses.get(ticker)
        if not a:
            continue
        s     = score_action(a, info, macro_signals)
        close = a.get("close", 0)
        if close <= 0:
            continue
        target_pct = 0.05 if s > 75 else 0.04 if s > 60 else 0.03
        proba      = min(95, 50 + s * 0.45)
        scored.append({
            "ticker":         ticker,
            "name":           info["name"],
            "sector":         info["sector"],
            "score":          s,
            "price":          close,
            "target":         round(close * (1 + target_pct), 2),
            "stop":           round(close * 0.98, 2),
            "gain_pct":       round(target_pct * 100, 1),
            "proba":          round(proba),
            "rsi":            round(a.get("rsi", 50), 1),
            "macd_cross":     a.get("macd", 0) > a.get("macd_signal", 0),
            "recommendation": a.get("recommendation", "NEUTRAL"),
            "volume":         a.get("volume", 0),
            "avg_volume":     info["avg_vol"],
        })
    return sorted(scored, key=lambda x: x["score"], reverse=True)[:n]


def load_trades():
    if os.path.exists(TRADE_LOG_FILE):
        with open(TRADE_LOG_FILE, "r") as f:
            return json.load(f)
    return []

def get_open_trades():
    return [t for t in load_trades() if t.get("status") == "open"]

def get_week_pnl():
    trades       = load_trades()
    today        = datetime.date.today()
    week_start   = today - datetime.timedelta(days=today.weekday())
    week_trades  = [t for t in trades if t.get("date", "") >= str(week_start)]
    total_pnl    = sum(t.get("pnl_pct", 0) for t in week_trades if t.get("status") == "closed")
    wins         = sum(1 for t in week_trades if t.get("pnl_pct", 0) > 0 and t.get("status") == "closed")
    total_closed = sum(1 for t in week_trades if t.get("status") == "closed")
    return {
        "total_pnl": round(total_pnl, 2),
        "wins":      wins,
        "total":     total_closed,
        "open":      len(get_open_trades()),
        "win_rate":  round(wins / total_closed * 100) if total_closed > 0 else 0,
    }


def build_macro_html(macro, macro_signals):
    def row(label, key, unit="", decimals=2):
        d   = macro.get(key, {})
        chg = d.get("change", 0)
        px  = d.get("price", 0)
        col = "#00C87A" if chg >= 0 else "#FF4560"
        sgn = "+" if chg >= 0 else ""
        return f"<tr><td style='color:#6B7280;padding:4px 0;font-size:12px'>{label}</td><td style='color:#E8E4D6;font-weight:700;text-align:right;font-size:12px'>{px:.{decimals}f}{unit}</td><td style='color:{col};font-weight:700;text-align:right;font-size:12px'>{sgn}{chg:.2f}%</td></tr>"

    signals_html = ""
    for sig in macro_signals:
        col = "#00C87A" if sig["direction"] == "hausse" else "#FF4560"
        fav = ", ".join(sig["favorise"]) if sig["favorise"] else "-"
        pen = ", ".join(sig["penalise"]) if sig["penalise"] else "-"
        signals_html += f"""
        <div style="background:#0A0D14;border-radius:6px;padding:10px;margin-bottom:6px;border-left:2px solid {col}">
          <div style="font-size:11px;color:{col};font-weight:700">{sig['label']} {'+' if sig['direction']=='hausse' else ''}{sig['change']:.2f}%</div>
          <div style="font-size:10px;color:#9CA3AF;margin-top:3px">{sig['message']}</div>
          <div style="font-size:10px;margin-top:4px">
            <span style="color:#00C87A">Favorise: {fav}</span>
            {'  |  <span style="color:#FF4560">Penalise: ' + pen + '</span>' if sig['penalise'] else ''}
          </div>
        </div>"""

    return f"""
    <div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:12px;padding:16px;margin-bottom:16px">
      <div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid rgba(201,168,76,0.15)">MACRO GLOBAL & CORRELATIONS BVC</div>
      <table style="width:100%;border-collapse:collapse;margin-bottom:14px">
        <tr style="font-size:9px;color:#4B5563;letter-spacing:2px">
          <th style="text-align:left;padding-bottom:6px">ACTIF</th>
          <th style="text-align:right;padding-bottom:6px">COURS</th>
          <th style="text-align:right;padding-bottom:6px">VAR. J</th>
        </tr>
        {row("Or (XAU/USD)", "gold", " $", 0)}
        {row("Argent (XAG/USD)", "silver", " $", 2)}
        {row("Cuivre", "copper", " $", 3)}
        {row("Brent (USD)", "brent", " $", 1)}
        {row("USD/MAD", "usd_mad", "", 4)}
        {row("EUR/MAD", "eur_mad", "", 4)}
        {row("EUR/USD", "eur_usd", "", 4)}
        {row("Dollar Index (DXY)", "usd_index", "", 2)}
        {row("Taux US 10Y", "us_10y", "%", 3)}
        {row("Taux US 2Y", "us_2y", "%", 3)}
        {row("Taux EUR 10Y (Bund)", "eur_10y", "%", 3)}
        {row("S&P 500", "sp500", "", 0)}
        {row("CAC 40", "cac40", "", 0)}
        {row("MSCI EM (EEM)", "msci_em", " $", 2)}
      </table>
      {"<div style='font-size:10px;color:#C9A84C;letter-spacing:2px;margin-bottom:8px'>IMPACTS SUR BVC</div>" + signals_html if signals_html else "<div style='font-size:11px;color:#6B7280'>Aucun signal macro significatif aujourd'hui</div>"}
    </div>"""


def build_signal_html(s, idx):
    color     = "#00C87A" if s["score"] >= 65 else "#C9A84C"
    rsi_color = "#FF4560" if s["rsi"] > 70 else "#00C87A" if s["rsi"] < 35 else "#C9A84C"
    macd_txt  = "Croisement haussier" if s["macd_cross"] else "Pas encore croise"
    vol_ratio = round(s["volume"] / s["avg_volume"], 1) if s["avg_volume"] > 0 else 1
    vol_color = "#00C87A" if vol_ratio > 1.5 else "#9CA3AF"
    return f"""
    <div style="background:#171C2C;border-radius:10px;padding:16px;margin-bottom:12px;border-left:3px solid {color}">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <div>
          <span style="font-size:20px;font-weight:900;color:{color};font-family:monospace">{s['ticker']}</span>
          <span style="font-size:11px;color:#6B7280;margin-left:8px">{s['name']} - {s['sector']}</span>
        </div>
        <span style="font-size:10px;background:rgba(0,200,122,0.15);color:#00C87A;border:1px solid rgba(0,200,122,0.3);padding:3px 10px;border-radius:4px;font-weight:700">ACHAT #{idx+1}</span>
      </div>
      <table style="width:100%;font-size:12px;border-collapse:collapse">
        <tr>
          <td style="color:#6B7280;padding:4px 0">Entree</td>
          <td style="color:#E8E4D6;font-weight:700;text-align:right">{s['price']:.2f} MAD</td>
          <td style="color:#6B7280;padding:4px 12px">Cible</td>
          <td style="color:#00C87A;font-weight:700;text-align:right">{s['target']:.2f} MAD (+{s['gain_pct']}%)</td>
        </tr>
        <tr>
          <td style="color:#6B7280;padding:4px 0">Stop loss</td>
          <td style="color:#FF4560;font-weight:700;text-align:right">{s['stop']:.2f} MAD (-2%)</td>
          <td style="color:#6B7280;padding:4px 12px">RSI</td>
          <td style="color:{rsi_color};font-weight:700;text-align:right">{s['rsi']}</td>
        </tr>
        <tr>
          <td style="color:#6B7280;padding:4px 0">MACD</td>
          <td colspan="3" style="color:#9CA3AF;text-align:right">{macd_txt}</td>
        </tr>
        <tr>
          <td style="color:#6B7280;padding:4px 0">Volume</td>
          <td colspan="3" style="color:{vol_color};text-align:right">x{vol_ratio} vs moyenne ({int(s['volume']):,} vs {int(s['avg_volume']):,})</td>
        </tr>
      </table>
      <div style="margin-top:10px">
        <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:4px">
          <span style="color:#6B7280">Proba gain min 2%</span>
          <span style="color:{color};font-weight:700">{s['proba']}%</span>
        </div>
        <div style="background:#0A0D14;border-radius:3px;height:5px">
          <div style="height:100%;border-radius:3px;background:{color};width:{s['proba']}%"></div>
        </div>
      </div>
      <div style="margin-top:8px;font-size:11px;color:#9CA3AF;border-top:1px solid rgba(255,255,255,0.06);padding-top:6px">
        Score Baraka: <strong style="color:{color}">{s['score']}/100</strong> - Signal TV: {s['recommendation']}
      </div>
    </div>"""


def build_email_html(subject_type, signals, open_trades, news, macro, macro_signals, volume_alerts, week_pnl):
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    if subject_type == "matin":
        window      = "FENETRE 1 - 10h00 a 12h00"
        instruction = "Tu achetes maintenant - vends avant midi"
        emoji       = "SIGNAL MATIN"
    elif subject_type == "midi":
        window      = "FENETRE 2 - 12h00 a 14h00"
        instruction = "Point mi-journee - tu gardes ou tu switiches"
        emoji       = "POINT MIDI"
    else:
        window      = "CLOTURE - 15h15"
        instruction = "Decision finale - cloture ou hold max 1 semaine (+30% min)"
        emoji       = "CLOTURE BVC"

    signals_html = "".join(build_signal_html(s, i) for i, s in enumerate(signals))

    open_html = ""
    if open_trades:
        rows = "".join(f"""
        <div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid rgba(255,255,255,0.05);font-size:12px">
          <span style="color:#00C87A;font-weight:700">{t.get('ticker','?')}</span>
          <span style="color:#6B7280">Entre a {t.get('entry',0):.2f} MAD</span>
          <span style="color:#C9A84C">Cible: {t.get('target',0):.2f} MAD</span>
        </div>""" for t in open_trades)
        open_html = f"""
        <div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:16px;margin-bottom:16px">
          <div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid rgba(201,168,76,0.15)">POSITIONS OUVERTES</div>
          {rows}
        </div>"""

    vol_html = ""
    if volume_alerts:
        rows = "".join(f"""
        <div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid rgba(255,255,255,0.05);font-size:12px">
          <span style="color:#FF4560;font-weight:700">{v['ticker']}</span>
          <span style="color:#6B7280">{v['name']}</span>
          <span style="color:#FF4560;font-weight:700">x{v['ratio']} vol. habituel</span>
          <span style="color:#C9A84C">{v['price']:.2f} MAD</span>
        </div>""" for v in volume_alerts[:3])
        vol_html = f"""
        <div style="background:rgba(255,69,96,0.06);border:1px solid rgba(255,69,96,0.25);border-radius:10px;padding:16px;margin-bottom:16px">
          <div style="font-size:10px;color:#FF4560;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">ALERTES VOLUMES ANORMAUX</div>
          {rows}
        </div>"""

    news_html = ""
    if news:
        items = "".join(f"<div style='font-size:11px;color:#9CA3AF;padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.04)'>- {n}</div>" for n in news)
        news_html = f"""
        <div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:16px;margin-bottom:16px">
          <div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid rgba(201,168,76,0.15)">FLUX MARCHE BOURSENEWS</div>
          {items}
        </div>"""

    pnl_color = "#00C87A" if week_pnl["total_pnl"] >= 0 else "#FF4560"
    pnl_sign  = "+" if week_pnl["total_pnl"] >= 0 else ""

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="background:#0A0D14;color:#E8E4D6;font-family:'Courier New',monospace;margin:0;padding:0">
<div style="max-width:620px;margin:0 auto;padding:20px">

  <div style="background:#111520;border:1px solid rgba(201,168,76,0.3);border-radius:12px;padding:20px;margin-bottom:16px;text-align:center">
    <div style="font-size:30px;font-weight:900;color:#C9A84C;letter-spacing:6px">BARAKA</div>
    <div style="font-size:10px;color:#6B7280;letter-spacing:3px;margin-top:2px">BVC TRADING AGENT - {now}</div>
    <div style="display:inline-block;background:rgba(0,200,122,0.1);border:1px solid rgba(0,200,122,0.3);color:#00C87A;padding:4px 14px;border-radius:20px;font-size:11px;letter-spacing:2px;margin-top:10px">{window}</div>
  </div>

  <div style="background:rgba(201,168,76,0.08);border:1px solid rgba(201,168,76,0.25);border-radius:10px;padding:12px;margin-bottom:16px;text-align:center">
    <div style="font-size:13px;color:#C9A84C;font-weight:700">{emoji} - {instruction}</div>
  </div>

  <div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">TOP 3 SIGNAUX DU JOUR</div>
  {signals_html}

  {open_html}
  {vol_html}
  {build_macro_html(macro, macro_signals)}
  {news_html}

  <div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:16px;margin-bottom:16px">
    <div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">PNL SEMAINE</div>
    <div style="display:flex;justify-content:space-between;align-items:center">
      <div>
        <div style="font-size:28px;font-weight:900;color:{pnl_color}">{pnl_sign}{week_pnl['total_pnl']}%</div>
        <div style="font-size:11px;color:#6B7280">{week_pnl['wins']}/{week_pnl['total']} trades gagnants - Win rate {week_pnl['win_rate']}%</div>
      </div>
      <div style="text-align:right">
        <div style="font-size:11px;color:#6B7280">Positions ouvertes</div>
        <div style="font-size:20px;font-weight:700;color:#C9A84C">{week_pnl['open']}</div>
      </div>
    </div>
  </div>

  <div style="text-align:center;font-size:10px;color:#4B5563;margin-top:16px;line-height:1.9">
    Confirmez chaque trade manuellement - Donnees T-15min - Max 3 trades/jour<br>
    <strong style="color:#C9A84C">Objectif journalier +5% - Hold semaine min +30%</strong>
  </div>

</div></body></html>"""


def send_email(subject, html_body):
    try:
        msg            = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = GMAIL_USER
        msg["To"]      = TO_EMAIL
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, TO_EMAIL, msg.as_string())
        print(f"[BARAKA] Email envoye: {subject}")
        return True
    except Exception as e:
        print(f"[BARAKA] Erreur email: {e}")
        return False


def run_analysis():
    print("[BARAKA] Analyse BVC en cours...")
    analyses = {}
    for ticker, info in BVC_WATCHLIST.items():
        a = get_tv_analysis(info["tv"])
        if a:
            analyses[ticker] = a
        time.sleep(0.5)
    return analyses


def run_full_analysis():
    analyses      = run_analysis()
    macro         = get_macro()
    macro_signals = analyze_macro_impact(macro)
    signals       = get_top_signals(analyses, macro_signals, n=3)
    open_trades   = get_open_trades()
    news          = scrape_boursenews()
    vol_alerts    = check_volume_alerts(analyses)
    week_pnl      = get_week_pnl()
    return analyses, macro, macro_signals, signals, open_trades, news, vol_alerts, week_pnl


def alert_matin():
    print("[BARAKA] Signal Matin 10h00")
    analyses, macro, macro_signals, signals, open_trades, news, vol_alerts, week_pnl = run_full_analysis()
    html = build_email_html("matin", signals, open_trades, news, macro, macro_signals, vol_alerts, week_pnl)
    send_email("BARAKA - SIGNAL MATIN - 3 opportunites BVC", html)
    if vol_alerts:
        alert_volumes(vol_alerts)


def alert_midi():
    print("[BARAKA] Point Midi 12h00")
    analyses, macro, macro_signals, signals, open_trades, news, vol_alerts, week_pnl = run_full_analysis()
    html = build_email_html("midi", signals, open_trades, news, macro, macro_signals, vol_alerts, week_pnl)
    send_email("BARAKA - POINT MIDI - Garder / Vendre / Switcher", html)


def alert_cloture():
    print("[BARAKA] Cloture 15h15")
    analyses, macro, macro_signals, signals, open_trades, news, vol_alerts, week_pnl = run_full_analysis()
    html = build_email_html("cloture", signals, open_trades, news, macro, macro_signals, vol_alerts, week_pnl)
    send_email("BARAKA - CLOTURE BVC - Decision finale", html)


def alert_volumes(vol_alerts):
    if not vol_alerts:
        return
    rows = "".join(f"""
    <tr>
      <td style="color:#FF4560;font-weight:700;padding:8px;font-family:monospace">{v['ticker']}</td>
      <td style="color:#E8E4D6;padding:8px">{v['name']}</td>
      <td style="color:#FF4560;font-weight:700;padding:8px">x{v['ratio']}</td>
      <td style="color:#C9A84C;padding:8px">{int(v['volume']):,}</td>
      <td style="color:#6B7280;padding:8px">{int(v['avg_volume']):,}</td>
      <td style="color:#E8E4D6;padding:8px">{v['price']:.2f} MAD</td>
    </tr>""" for v in vol_alerts)

    html = f"""<body style="background:#0A0D14;color:#E8E4D6;font-family:monospace;padding:20px">
    <div style="max-width:600px;margin:0 auto">
      <div style="background:#111520;border:1px solid rgba(255,69,96,0.4);border-radius:12px;padding:20px;text-align:center;margin-bottom:20px">
        <div style="font-size:24px;font-weight:900;color:#C9A84C;letter-spacing:4px">BARAKA</div>
        <div style="color:#FF4560;font-size:14px;margin-top:8px;font-weight:700">ALERTE VOLUME ANORMAL DETECTE</div>
      </div>
      <table style="width:100%;border-collapse:collapse;background:#111520;border-radius:10px">
        <thead><tr style="background:#171C2C;font-size:10px;color:#6B7280;letter-spacing:2px">
          <th style="padding:10px;text-align:left">TICKER</th>
          <th style="padding:10px;text-align:left">SOCIETE</th>
          <th style="padding:10px;text-align:left">RATIO</th>
          <th style="padding:10px;text-align:left">VOL. ACT.</th>
          <th style="padding:10px;text-align:left">VOL. MOY.</th>
          <th style="padding:10px;text-align:left">COURS</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
      <div style="margin-top:16px;font-size:11px;color:#6B7280;text-align:center">
        Verifiez les news et publications AMMC associees a ces titres
      </div>
    </div></body>"""
    send_email(f"BARAKA - ALERTE VOLUME - {', '.join(v['ticker'] for v in vol_alerts[:3])}", html)


def monitor_volumes():
    now = datetime.datetime.now()
    if now.weekday() >= 5:
        return
    if not (9 <= now.hour < 16):
        return
    print("[BARAKA] Surveillance volumes...")
    analyses   = run_analysis()
    vol_alerts = check_volume_alerts(analyses)
    if vol_alerts:
        print(f"[BARAKA] {len(vol_alerts)} alerte(s) volume!")
        alert_volumes(vol_alerts)


def run_scheduler():
    print("""
    BARAKA - BVC TRADING AGENT
    Wall Street Level - Casablanca Stock Exchange
    10h00 -> Signal Matin
    12h00 -> Point Midi
    15h15 -> Alerte Cloture
    /15min -> Surveillance Volumes
    """)

    for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
        getattr(schedule.every(), day).at("10:00").do(alert_matin)
        getattr(schedule.every(), day).at("12:00").do(alert_midi)
        getattr(schedule.every(), day).at("15:15").do(alert_cloture)

    schedule.every(15).minutes.do(monitor_volumes)

    print("[BARAKA] Scheduler actif. En attente...")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    run_scheduler()
