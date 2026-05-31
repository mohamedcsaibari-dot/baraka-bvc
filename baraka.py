"""
BARAKA v3.0 - BVC Trading Agent
100% Gratuit · LLM Groq · Carnet d'Ordres · 75 Societes
"""

import schedule, time, datetime, json, os, requests, smtplib, re
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

TRADE_LOG_FILE  = "trade_log.json"
LEARNING_FILE   = "baraka_learnings.json"
VOLUME_ALERT_THRESHOLD = 2.5

BVC_WATCHLIST = {
    "ATW":     {"name":"Attijariwafa Bank",         "sector":"Banque",       "avg_vol":85000,  "mc":"large","bam":True, "brent":False,"phos":False},
    "BCP":     {"name":"Banque Centrale Pop.",       "sector":"Banque",       "avg_vol":60000,  "mc":"large","bam":True, "brent":False,"phos":False},
    "BMCE":    {"name":"Bank of Africa",             "sector":"Banque",       "avg_vol":70000,  "mc":"large","bam":True, "brent":False,"phos":False},
    "CIH":     {"name":"CIH Bank",                   "sector":"Banque",       "avg_vol":45000,  "mc":"mid",  "bam":True, "brent":False,"phos":False},
    "CDM":     {"name":"Credit du Maroc",            "sector":"Banque",       "avg_vol":18000,  "mc":"mid",  "bam":True, "brent":False,"phos":False},
    "BMCI":    {"name":"BMCI",                       "sector":"Banque",       "avg_vol":12000,  "mc":"mid",  "bam":True, "brent":False,"phos":False},
    "CFG":     {"name":"CFG Bank",                   "sector":"Banque",       "avg_vol":8000,   "mc":"small","bam":True, "brent":False,"phos":False},
    "WAA":     {"name":"Wafa Assurance",             "sector":"Assurance",    "avg_vol":6000,   "mc":"mid",  "bam":True, "brent":False,"phos":False},
    "ATL":     {"name":"Atlanta",                    "sector":"Assurance",    "avg_vol":5000,   "mc":"small","bam":True, "brent":False,"phos":False},
    "SAH":     {"name":"Saham Assurance",            "sector":"Assurance",    "avg_vol":4000,   "mc":"small","bam":True, "brent":False,"phos":False},
    "MCB":     {"name":"Mutuelle Centrale Marocaine","sector":"Assurance",    "avg_vol":2000,   "mc":"small","bam":True, "brent":False,"phos":False},
    "IAM":     {"name":"Maroc Telecom",              "sector":"Telecom",      "avg_vol":120000, "mc":"large","bam":False,"brent":False,"phos":False},
    "HPS":     {"name":"HighTech Payment Systems",   "sector":"Tech",         "avg_vol":15000,  "mc":"mid",  "bam":False,"brent":False,"phos":False},
    "M2M":     {"name":"M2M Group",                  "sector":"Tech",         "avg_vol":2500,   "mc":"small","bam":False,"brent":False,"phos":False},
    "IB":      {"name":"Involys",                    "sector":"Tech",         "avg_vol":3000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "S2M":     {"name":"S2M",                        "sector":"Tech",         "avg_vol":2000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "NASS":    {"name":"Nassim",                     "sector":"Tech",         "avg_vol":1500,   "mc":"small","bam":False,"brent":False,"phos":False},
    "OCP":     {"name":"OCP Group",                  "sector":"Chimie",       "avg_vol":95000,  "mc":"large","bam":False,"brent":False,"phos":True},
    "SMI":     {"name":"SMI",                        "sector":"Mines",        "avg_vol":8000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "CMT":     {"name":"Cie Miniere Touissit",       "sector":"Mines",        "avg_vol":5000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "MANAGEM": {"name":"Managem",                    "sector":"Mines",        "avg_vol":12000,  "mc":"mid",  "bam":False,"brent":False,"phos":False},
    "SMH":     {"name":"Samine",                     "sector":"Mines",        "avg_vol":3000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "ZELLIDJA":{"name":"Zellidja",                   "sector":"Mines",        "avg_vol":1500,   "mc":"small","bam":False,"brent":False,"phos":False},
    "SNEP":    {"name":"SNEP",                       "sector":"Chimie",       "avg_vol":4000,   "mc":"small","bam":False,"brent":False,"phos":True},
    "SCE":     {"name":"Ste Cherifienne Engrais",    "sector":"Chimie",       "avg_vol":3500,   "mc":"small","bam":False,"brent":False,"phos":True},
    "FERTIMA": {"name":"Fertima",                    "sector":"Chimie",       "avg_vol":2500,   "mc":"small","bam":False,"brent":False,"phos":True},
    "ADH":     {"name":"Addoha",                     "sector":"Immobilier",   "avg_vol":35000,  "mc":"mid",  "bam":True, "brent":False,"phos":False},
    "ALM":     {"name":"Alliances",                  "sector":"Immobilier",   "avg_vol":15000,  "mc":"mid",  "bam":True, "brent":False,"phos":False},
    "RDS":     {"name":"Residences Dar Saada",       "sector":"Immobilier",   "avg_vol":8000,   "mc":"small","bam":True, "brent":False,"phos":False},
    "BALIMA":  {"name":"Balima",                     "sector":"Immobilier",   "avg_vol":2000,   "mc":"small","bam":True, "brent":False,"phos":False},
    "HOL":     {"name":"Holcim Maroc",               "sector":"Construction", "avg_vol":12000,  "mc":"mid",  "bam":False,"brent":False,"phos":False},
    "CMA":     {"name":"Ciments du Maroc",           "sector":"Construction", "avg_vol":10000,  "mc":"mid",  "bam":False,"brent":False,"phos":False},
    "LHM":     {"name":"LafargeHolcim Maroc",        "sector":"Construction", "avg_vol":9000,   "mc":"mid",  "bam":False,"brent":False,"phos":False},
    "SNABT":   {"name":"Sna Btp",                    "sector":"Construction", "avg_vol":1500,   "mc":"small","bam":False,"brent":False,"phos":False},
    "LABEL":   {"name":"Label Vie",                  "sector":"Distribution", "avg_vol":9000,   "mc":"mid",  "bam":False,"brent":False,"phos":False},
    "FENIE":   {"name":"Fenie Brossette",            "sector":"Distribution", "avg_vol":3500,   "mc":"small","bam":False,"brent":False,"phos":False},
    "STOKVIS": {"name":"Stokvis Nord Afrique",       "sector":"Distribution", "avg_vol":2000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "LAC":     {"name":"Lesieur Cristal",            "sector":"Agro",         "avg_vol":11000,  "mc":"mid",  "bam":False,"brent":True, "phos":False},
    "DARI":    {"name":"Dari Couspate",              "sector":"Agro",         "avg_vol":4000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "COSUMAR": {"name":"Cosumar",                    "sector":"Agro",         "avg_vol":8000,   "mc":"mid",  "bam":False,"brent":False,"phos":False},
    "OULMES":  {"name":"Eaux Minerales Oulmes",      "sector":"Agro",         "avg_vol":4000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "UNIMER":  {"name":"Unimer",                     "sector":"Agro",         "avg_vol":3000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "TMA":     {"name":"Total Maroc",                "sector":"Energie",      "avg_vol":7000,   "mc":"mid",  "bam":False,"brent":True, "phos":False},
    "TAQA":    {"name":"Taqa Morocco",               "sector":"Energie",      "avg_vol":8000,   "mc":"mid",  "bam":False,"brent":True, "phos":False},
    "SRM":     {"name":"Sonasid",                    "sector":"Siderurgie",   "avg_vol":6000,   "mc":"mid",  "bam":False,"brent":True, "phos":False},
    "CTM":     {"name":"CTM",                        "sector":"Transport",    "avg_vol":5000,   "mc":"small","bam":False,"brent":True, "phos":False},
    "TIMAR":   {"name":"Timar",                      "sector":"Transport",    "avg_vol":1500,   "mc":"small","bam":False,"brent":True, "phos":False},
    "LBV":     {"name":"Lydec",                      "sector":"Services",     "avg_vol":5000,   "mc":"mid",  "bam":False,"brent":False,"phos":False},
    "AFMA":    {"name":"Afma",                       "sector":"Services",     "avg_vol":2500,   "mc":"small","bam":False,"brent":False,"phos":False},
    "RIS":     {"name":"Risma",                      "sector":"Tourisme",     "avg_vol":5000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "SOTHEMA": {"name":"Sothema",                    "sector":"Pharma",       "avg_vol":6000,   "mc":"mid",  "bam":False,"brent":False,"phos":False},
    "PROMOPH": {"name":"Promopharm",                 "sector":"Pharma",       "avg_vol":2500,   "mc":"small","bam":False,"brent":False,"phos":False},
    "PHARM":   {"name":"Pharma 5",                   "sector":"Pharma",       "avg_vol":3000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "EQDOM":   {"name":"Eqdom",                      "sector":"Credit Conso", "avg_vol":4000,   "mc":"small","bam":True, "brent":False,"phos":False},
    "SOFAC":   {"name":"Sofac",                      "sector":"Credit Conso", "avg_vol":3000,   "mc":"small","bam":True, "brent":False,"phos":False},
    "SALAF":   {"name":"Salafin",                    "sector":"Credit Conso", "avg_vol":3500,   "mc":"small","bam":True, "brent":False,"phos":False},
    "TASLIF":  {"name":"Taslif",                     "sector":"Credit Conso", "avg_vol":1500,   "mc":"small","bam":True, "brent":False,"phos":False},
    "ACRED":   {"name":"Acred",                      "sector":"Credit Conso", "avg_vol":2000,   "mc":"small","bam":True, "brent":False,"phos":False},
    "DIAC":    {"name":"Diac Salaf",                 "sector":"Credit Conso", "avg_vol":1000,   "mc":"small","bam":True, "brent":False,"phos":False},
    "MPARK":   {"name":"Maroc Leasing",              "sector":"Leasing",      "avg_vol":3000,   "mc":"small","bam":True, "brent":False,"phos":False},
    "DLM":     {"name":"Delattre Levivier Maroc",    "sector":"Industrie",    "avg_vol":3000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "NEXANS":  {"name":"Nexans Maroc",               "sector":"Industrie",    "avg_vol":3000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "MAGHREB": {"name":"Maghreb Oxygene",            "sector":"Industrie",    "avg_vol":2000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "STROC":   {"name":"Stroc Industrie",            "sector":"Industrie",    "avg_vol":2000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "LGMC":    {"name":"Longometal",                 "sector":"Industrie",    "avg_vol":2000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "COLOROB": {"name":"Colorobbia Maroc",           "sector":"Industrie",    "avg_vol":1500,   "mc":"small","bam":False,"brent":False,"phos":False},
    "AFRIC":   {"name":"Africa Industries",          "sector":"Industrie",    "avg_vol":1000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "FBR":     {"name":"Fipar Holding",              "sector":"Holding",      "avg_vol":4000,   "mc":"mid",  "bam":False,"brent":False,"phos":False},
    "MED":     {"name":"Meditel",                    "sector":"Telecom",      "avg_vol":2000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "SDLT":    {"name":"Sodetel",                    "sector":"Telecom",      "avg_vol":1000,   "mc":"small","bam":False,"brent":False,"phos":False},
    "ENNAKL":  {"name":"Ennakl",                     "sector":"Automobile",   "avg_vol":2000,   "mc":"small","bam":False,"brent":True, "phos":False},
}

# ─── CARNET D'ORDRES WAFABOURSE ───────────────────────────────────────────────

def scrape_order_book(ticker):
    """Scrape carnet d'ordres depuis Wafabourse + BVC direct"""
    order_book = {
        "ticker": ticker,
        "bids": [],
        "asks": [],
        "spread_pct": 0,
        "spread_mad": 0,
        "best_bid": 0,
        "best_ask": 0,
        "depth_bid_mad": 0,
        "depth_ask_mad": 0,
        "total_depth_mad": 0,
        "liquidity_score": 0,
        "spread_opportunity": False,
        "quick_gain_pct": 0,
        "source": "unavailable",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9",
        "Referer": "https://www.wafabourse.com/",
    }
    urls_to_try = [
        f"https://www.wafabourse.com/cours/{ticker.lower()}",
        f"https://www.wafabourse.com/bourse/cours/{ticker}",
        f"https://www.casablanca-bourse.com/bourseweb/cours-societe.aspx?codeValeur={ticker}",
        f"https://www.leboursier.ma/cours/{ticker.lower()}",
    ]
    for url in urls_to_try:
        try:
            r = requests.get(url, headers=headers, timeout=12)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            text = r.text

            # Chercher prix bid/ask dans le HTML
            bid_patterns  = [r'offre["\s:]+([0-9]+[.,][0-9]+)', r'bid["\s:]+([0-9]+[.,][0-9]+)', r'achat["\s:]+([0-9]+[.,][0-9]+)']
            ask_patterns  = [r'demande["\s:]+([0-9]+[.,][0-9]+)', r'ask["\s:]+([0-9]+[.,][0-9]+)', r'vente["\s:]+([0-9]+[.,][0-9]+)']
            vol_patterns  = [r'volume["\s:]+([0-9\s]+)', r'quantite["\s:]+([0-9]+)', r'qte["\s:]+([0-9]+)']

            bids_found, asks_found = [], []
            text_lower = text.lower()

            for pat in bid_patterns:
                matches = re.findall(pat, text_lower)
                for m in matches:
                    try:
                        val = float(m.replace(",", ".").replace(" ", ""))
                        if 1 < val < 100000:
                            bids_found.append(val)
                    except: pass

            for pat in ask_patterns:
                matches = re.findall(pat, text_lower)
                for m in matches:
                    try:
                        val = float(m.replace(",", ".").replace(" ", ""))
                        if 1 < val < 100000:
                            asks_found.append(val)
                    except: pass

            # Tables carnet d'ordres
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = [td.get_text(strip=True) for td in row.find_all(["td","th"])]
                    if len(cells) >= 2:
                        for i, cell in enumerate(cells):
                            try:
                                val = float(cell.replace(",",".").replace(" ","").replace("\xa0",""))
                                if 1 < val < 100000:
                                    # Heuristique: premier prix = bid, deuxieme = ask
                                    if not bids_found:
                                        bids_found.append(val)
                                    elif not asks_found and val != bids_found[0]:
                                        asks_found.append(val)
                            except: pass

            if bids_found and asks_found:
                best_bid = max(bids_found[:3])
                best_ask = min(asks_found[:3])
                if best_ask > best_bid > 0:
                    spread_pct = (best_ask - best_bid) / best_bid * 100
                    order_book.update({
                        "best_bid": round(best_bid, 2),
                        "best_ask": round(best_ask, 2),
                        "spread_pct": round(spread_pct, 2),
                        "spread_mad": round(best_ask - best_bid, 2),
                        "source": url.split("/")[2],
                    })
                    break
        except Exception as e:
            print(f"[ORDER BOOK] {ticker} - {url}: {e}")
            continue

    # Calculer opportunite spread
    if order_book["best_bid"] > 0 and order_book["best_ask"] > 0:
        spread_pct = order_book["spread_pct"]
        # Gain potentiel = acheter au bid, vendre a l'ask
        quick_gain = spread_pct * 0.6  # 60% du spread apres frais
        order_book["quick_gain_pct"] = round(quick_gain, 2)
        order_book["spread_opportunity"] = spread_pct >= 1.5

    return order_book


def enrich_order_book_with_tv(order_book, tv_analysis):
    """Complete carnet d'ordres avec donnees TradingView si Wafabourse indisponible"""
    if not tv_analysis:
        return order_book
    close  = tv_analysis.get("close", 0)
    high   = tv_analysis.get("high", 0)
    low    = tv_analysis.get("low", 0)
    atr    = tv_analysis.get("atr", 0)

    if close > 0 and order_book["best_bid"] == 0:
        # Estimer spread via ATR et prix high/low du jour
        estimated_spread_pct = (high - low) / close * 100 if high > low else (atr / close * 100 if atr > 0 else 0.5)
        estimated_bid = close * (1 - 0.002)
        estimated_ask = close * (1 + 0.002)
        if high > 0 and low > 0:
            estimated_bid = low + (high - low) * 0.3
            estimated_ask = low + (high - low) * 0.7

        order_book.update({
            "best_bid": round(estimated_bid, 2),
            "best_ask": round(estimated_ask, 2),
            "spread_pct": round(estimated_spread_pct, 2),
            "spread_mad": round(estimated_ask - estimated_bid, 2),
            "source": "TradingView (estime)",
            "quick_gain_pct": round(estimated_spread_pct * 0.5, 2),
            "spread_opportunity": estimated_spread_pct >= 1.5,
        })

    # Liquidite basee sur volume
    vol = tv_analysis.get("volume", 0)
    if close > 0 and vol > 0:
        depth_mad = vol * close * 0.3  # 30% du volume = profondeur estimee
        order_book["depth_bid_mad"]   = round(depth_mad / 2)
        order_book["depth_ask_mad"]   = round(depth_mad / 2)
        order_book["total_depth_mad"] = round(depth_mad)

    # Score liquidite 0-100
    total_depth = order_book["total_depth_mad"]
    avg_vol     = 50000  # reference
    if total_depth > 500000:   order_book["liquidity_score"] = 95
    elif total_depth > 200000: order_book["liquidity_score"] = 80
    elif total_depth > 100000: order_book["liquidity_score"] = 65
    elif total_depth > 50000:  order_book["liquidity_score"] = 50
    elif total_depth > 20000:  order_book["liquidity_score"] = 35
    else:                      order_book["liquidity_score"] = 20

    return order_book


def analyze_spread_opportunities(analyses):
    """Detecte les meilleures opportunites de spread sur tout le marche"""
    opportunities = []
    print("[BARAKA] Analyse carnet d'ordres en cours...")

    priority_tickers = [t for t, info in BVC_WATCHLIST.items()
                        if info.get("mc") in ["large","mid"] and info["avg_vol"] >= 5000]

    for ticker in priority_tickers:
        tv_data    = analyses.get(ticker)
        order_book = scrape_order_book(ticker)
        order_book = enrich_order_book_with_tv(order_book, tv_data)
        time.sleep(0.5)

        if not order_book["spread_opportunity"]:
            continue

        spread_pct      = order_book["spread_pct"]
        liquidity_score = order_book["liquidity_score"]
        quick_gain      = order_book["quick_gain_pct"]
        info            = BVC_WATCHLIST[ticker]

        # Filtres obligatoires
        if liquidity_score < 40:
            continue
        if quick_gain < 1.5:
            continue

        # Validation fondamentale / technique
        tech_ok = True
        if tv_data:
            rsi     = tv_data.get("rsi", 50)
            buy_sig = tv_data.get("buy_signals", 0)
            sell_sig = tv_data.get("sell_signals", 0)
            if rsi > 72:
                tech_ok = False  # Surachete
            if sell_sig > buy_sig * 1.5:
                tech_ok = False  # Signal TV negatif

        if not tech_ok:
            continue

        # Score opportunite spread
        opp_score = 0
        opp_score += min(40, spread_pct * 15)
        opp_score += min(30, liquidity_score * 0.3)
        opp_score += min(20, quick_gain * 8)
        if info["mc"] == "large": opp_score += 10
        elif info["mc"] == "mid": opp_score += 5

        opportunities.append({
            "ticker":           ticker,
            "name":             info["name"],
            "sector":           info["sector"],
            "market_cap":       info["mc"],
            "best_bid":         order_book["best_bid"],
            "best_ask":         order_book["best_ask"],
            "spread_pct":       spread_pct,
            "spread_mad":       order_book["spread_mad"],
            "quick_gain_pct":   quick_gain,
            "liquidity_score":  liquidity_score,
            "total_depth_mad":  order_book["total_depth_mad"],
            "opp_score":        round(opp_score, 1),
            "source":           order_book["source"],
            "rsi":              round(tv_data.get("rsi", 50), 1) if tv_data else 50,
            "volume":           tv_data.get("volume", 0) if tv_data else 0,
            "avg_volume":       info["avg_vol"],
        })

    return sorted(opportunities, key=lambda x: x["opp_score"], reverse=True)[:3]


# ─── LLM GRATUIT (GROQ) ──────────────────────────────────────────────────────

def load_learnings():
    if os.path.exists(LEARNING_FILE):
        with open(LEARNING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "lessons": [],
        "indicator_weights": {
            "rsi":1.0,"macd":1.0,"ema":1.0,"volume":1.0,
            "stoch":1.0,"adx":1.0,"bam_corr":1.0,"spread":1.0,
            "liquidity":1.0,"phosphate_corr":1.0,"brent_corr":1.0
        },
        "secteurs_favorables": [],
        "secteurs_eviter": [],
        "spread_min_viable": 1.5,
        "liquidity_min_score": 40,
        "accuracy_history": [],
        "accuracy_rate": 0,
        "total_analyzed": 0,
        "last_updated": "",
    }

def save_learnings(data):
    with open(LEARNING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def llm_post_cloture(trades_today, signals_today, spread_opps, market_ctx, learnings):
    """Analyse post-cloture via Groq LLM (100% gratuit)"""
    if not GROQ_AVAILABLE or not GROQ_API_KEY:
        print("[BARAKA LLM] Groq non disponible - apprentissage desactive")
        return None
    try:
        client = Groq(api_key=GROQ_API_KEY)
        prompt = f"""Tu es Baraka, agent de trading expert sur la Bourse de Casablanca (BVC).
Analyse la session d'aujourd'hui et apprends pour demain.

TRADES EXECUTES AUJOURD'HUI: {json.dumps(trades_today, ensure_ascii=False)}
SIGNAUX RECOMMANDES: {json.dumps(signals_today[:3] if signals_today else [], ensure_ascii=False)}
OPPORTUNITES SPREAD DETECTEES: {json.dumps(spread_opps[:3] if spread_opps else [], ensure_ascii=False)}
CONTEXTE MARCHE: {json.dumps(market_ctx, ensure_ascii=False)}
POIDS ACTUELS: {json.dumps(learnings.get("indicator_weights",{}), ensure_ascii=False)}
LECONS PRECEDENTES (5 dernieres): {json.dumps(learnings.get("lessons",[])[-5:], ensure_ascii=False)}

Reponds UNIQUEMENT en JSON valide, sans markdown:
{{
  "analyse_du_jour": "analyse courte",
  "lecons_apprises": ["lecon1","lecon2","lecon3"],
  "nouveaux_poids": {{"rsi":1.0,"macd":1.0,"ema":1.0,"volume":1.0,"stoch":1.0,"adx":1.0,"bam_corr":1.0,"spread":1.0,"liquidity":1.0,"phosphate_corr":1.0,"brent_corr":1.0}},
  "secteurs_favorables": ["secteur1"],
  "secteurs_eviter": ["secteur1"],
  "spread_min_viable": 1.5,
  "liquidity_min_score": 40,
  "patterns_detectes": ["pattern1"],
  "score_precision_jour": 75,
  "recommandations_demain": "conseil court"
}}"""
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role":"user","content":prompt}],
            max_tokens=1200,
            temperature=0.3,
        )
        text  = response.choices[0].message.content.strip()
        clean = text.replace("```json","").replace("```","").strip()
        start = clean.find("{")
        end   = clean.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(clean[start:end])
        return None
    except Exception as e:
        print(f"[BARAKA LLM] Erreur Groq: {e}")
        return None


def llm_insight(signals, spread_opps, commodities, masi, bam_ctx, learnings):
    """Genere un insight contextuel court via Groq"""
    if not GROQ_AVAILABLE or not GROQ_API_KEY:
        return ""
    try:
        client = Groq(api_key=ANTHROPIC_KEY if False else GROQ_API_KEY)
        prompt = f"""Tu es Baraka, expert BVC. En 3 phrases MAX, analyse contextuelle du marche aujourd'hui.
TOP SIGNAUX: {[s['ticker']+' score:'+str(s['score']) for s in signals]}
SPREAD OPPS: {[o['ticker']+' spread:'+str(o['spread_pct'])+'%' for o in spread_opps]}
MASI: {masi.get('change',0):.2f}% RSI:{masi.get('rsi',50):.0f}
BRENT: {commodities.get('brent',{}).get('change',0):.2f}%
BAM: {bam_ctx}
SECTEURS OK: {learnings.get('secteurs_favorables',[])}
Reponds en francais, direct, sans markdown."""
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role":"user","content":prompt}],
            max_tokens=200,
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[BARAKA INSIGHT] Erreur: {e}")
        return ""


# ─── DONNÉES MARCHÉ ───────────────────────────────────────────────────────────

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
        }
    except Exception as e:
        print(f"[TV] {ticker}: {e}")
        return None

def get_commodities():
    result = {}
    pairs  = {
        "brent":   ("USOIL","cfd","OANDA"),
        "gold":    ("GOLD","cfd","OANDA"),
        "silver":  ("SILVER","cfd","OANDA"),
        "usd_mad": ("USDMAD","forex","FX_IDC"),
        "eur_mad": ("EURMAD","forex","FX_IDC"),
        "eur_usd": ("EURUSD","forex","FX_IDC"),
        "us10y":   ("US10Y","cfd","TVC"),
        "sp500":   ("SPX","cfd","SP"),
        "stoxx50": ("SX5E","cfd","EUREX"),
    }
    for name,(symbol,screener,exchange) in pairs.items():
        try:
            h = TA_Handler(symbol=symbol,screener=screener,exchange=exchange,interval=Interval.INTERVAL_1_DAY)
            a = h.get_analysis()
            result[name] = {"price":a.indicators.get("close",0),"change":a.indicators.get("change",0)}
        except:
            result[name] = {"price":0,"change":0}
        time.sleep(0.3)
    return result

def get_masi():
    try:
        h = TA_Handler(symbol="MASI",screener="morocco",exchange="CSE",interval=Interval.INTERVAL_15_MINUTES)
        a = h.get_analysis()
        return {"close":a.indicators.get("close",0),"change":a.indicators.get("change",0),
                "rsi":a.indicators.get("RSI",50),"rec":a.summary.get("RECOMMENDATION","NEUTRAL"),
                "buy":a.summary.get("BUY",0),"sell":a.summary.get("SELL",0)}
    except:
        return {"close":0,"change":0,"rsi":50,"rec":"NEUTRAL","buy":0,"sell":0}

def scrape_bam():
    data = {"taux_directeur":3.0,"news":[]}
    try:
        r = requests.get("https://www.bkam.ma/Politique-monetaire",headers={"User-Agent":"Mozilla/5.0"},timeout=12)
        soup = BeautifulSoup(r.text,"html.parser")
        for el in soup.select("p,h2,h3,li")[:15]:
            text = el.get_text(strip=True)
            if any(kw in text.lower() for kw in ["taux","monetaire","inflation","reserve","politique"]):
                if 20 < len(text) < 250:
                    data["news"].append(text[:200])
        data["news"] = list(dict.fromkeys(data["news"]))[:4]
        # Essayer de trouver le taux
        full_text = r.text.lower()
        matches = re.findall(r'(\d+[.,]\d+)\s*%', full_text)
        for m in matches:
            try:
                val = float(m.replace(",","."))
                if 0.5 < val < 10:
                    data["taux_directeur"] = val
                    break
            except: pass
    except Exception as e:
        print(f"[BAM] {e}")
    return data

def scrape_boursenews():
    try:
        r = requests.get("https://www.boursenews.ma/",headers={"User-Agent":"Mozilla/5.0"},timeout=10)
        soup = BeautifulSoup(r.text,"html.parser")
        news = []
        for item in soup.select("article,h2 a,h3 a,.title a")[:10]:
            t = item.get_text(strip=True)
            if len(t) > 20: news.append(t[:160])
        return list(dict.fromkeys(news))[:5]
    except: return []

def scrape_ammc():
    try:
        r = requests.get("https://www.ammc.ma/fr/actualites",headers={"User-Agent":"Mozilla/5.0"},timeout=10)
        soup = BeautifulSoup(r.text,"html.parser")
        items = []
        for item in soup.select(".views-row,article,h3 a,h2 a")[:6]:
            t = item.get_text(strip=True)
            if len(t) > 20: items.append(t[:160])
        return list(dict.fromkeys(items))[:4]
    except: return []

def scrape_oc():
    try:
        r = requests.get("https://www.oc.gov.ma/fr/publications",headers={"User-Agent":"Mozilla/5.0"},timeout=10)
        soup = BeautifulSoup(r.text,"html.parser")
        items = []
        for item in soup.select("article,.views-row,h3 a,h2 a")[:5]:
            t = item.get_text(strip=True)
            if len(t) > 20: items.append(t[:160])
        return list(dict.fromkeys(items))[:3]
    except: return []


# ─── SCORING ADAPTATIF ────────────────────────────────────────────────────────

def score_action(analysis, info, learnings, commodities, bam_data):
    if not analysis: return 0
    w = learnings.get("indicator_weights",{
        "rsi":1.0,"macd":1.0,"ema":1.0,"volume":1.0,
        "stoch":1.0,"adx":1.0,"bam_corr":1.0,"spread":1.0,
        "liquidity":1.0,"phosphate_corr":1.0,"brent_corr":1.0
    })
    score    = 50
    rsi      = analysis.get("rsi",50)
    macd     = analysis.get("macd",0)
    macd_sig = analysis.get("macd_signal",0)
    macd_h   = analysis.get("macd_hist",0)
    close    = analysis.get("close",0)
    ema20    = analysis.get("ema20",0)
    ema50    = analysis.get("ema50",0)
    ema200   = analysis.get("ema200",0)
    stoch_k  = analysis.get("stoch_k",50)
    stoch_d  = analysis.get("stoch_d",50)
    adx      = analysis.get("adx",0)
    cci      = analysis.get("cci",0)
    buy_sig  = analysis.get("buy_signals",0)
    sell_sig = analysis.get("sell_signals",0)
    vol      = analysis.get("volume",0)
    avg_vol  = info.get("avg_vol",1)

    if rsi < 25:   score += int(25*w.get("rsi",1))
    elif rsi < 35: score += int(15*w.get("rsi",1))
    elif rsi < 45: score += int(7*w.get("rsi",1))
    elif rsi > 75: score -= int(25*w.get("rsi",1))
    elif rsi > 65: score -= int(12*w.get("rsi",1))

    if macd > macd_sig and macd_h > 0: score += int(18*w.get("macd",1))
    elif macd > macd_sig:               score += int(8*w.get("macd",1))
    else:                               score -= int(10*w.get("macd",1))

    if close > ema20 > ema50 > ema200:   score += int(20*w.get("ema",1))
    elif close > ema20 > ema50:          score += int(12*w.get("ema",1))
    elif close > ema20:                  score += int(5*w.get("ema",1))
    elif close < ema20 < ema50 < ema200: score -= int(20*w.get("ema",1))
    elif close < ema20 < ema50:          score -= int(12*w.get("ema",1))

    if stoch_k < 20 and stoch_k > stoch_d: score += int(12*w.get("stoch",1))
    elif stoch_k > 80 and stoch_k < stoch_d: score -= int(12*w.get("stoch",1))

    if adx > 30: score += int(10*w.get("adx",1))
    elif adx > 20: score += int(5*w.get("adx",1))

    if cci < -100: score += 8
    elif cci > 100: score -= 8

    score += int((buy_sig - sell_sig) * 1.5)

    if avg_vol > 0:
        vr = vol / avg_vol
        if vr > 3:   score += int(18*w.get("volume",1))
        elif vr > 2: score += int(12*w.get("volume",1))
        elif vr > 1.5: score += int(6*w.get("volume",1))

    # BAM
    if info.get("bam") and bam_data:
        taux = bam_data.get("taux_directeur", 3.0) or 3.0
        wb = w.get("bam_corr",1.0)
        if taux <= 2.5:   score += int(15*wb)
        elif taux <= 3.0: score += int(8*wb)
        elif taux >= 4.0: score -= int(10*wb)
        news_txt = " ".join(bam_data.get("news",[])).lower()
        if any(kw in news_txt for kw in ["baisse","assouplissement","accomodante","reduction"]):
            score += int(10*wb)
        elif any(kw in news_txt for kw in ["hausse","restrictive","resserrement","inflation"]):
            score -= int(8*wb)

    # Phosphate
    if info.get("phos") and commodities:
        brent_chg = commodities.get("brent",{}).get("change",0)
        wp = w.get("phosphate_corr",1.0)
        if brent_chg > 1:    score += int(10*wp)
        elif brent_chg < -1: score -= int(8*wp)

    # Brent
    if info.get("brent") and commodities:
        brent_chg = commodities.get("brent",{}).get("change",0)
        wb2 = w.get("brent_corr",1.0)
        if brent_chg > 1:    score += int(8*wb2)
        elif brent_chg < -1: score -= int(10*wb2)

    if info.get("sector","") in learnings.get("secteurs_favorables",[]): score += 10
    if info.get("sector","") in learnings.get("secteurs_eviter",[]):     score -= 15
    if info.get("mc") == "large": score += 5

    return max(0, min(100, score))


def check_volume_alerts(analyses):
    alerts = []
    for ticker,info in BVC_WATCHLIST.items():
        a = analyses.get(ticker)
        if not a: continue
        vol = a.get("volume",0)
        avg = info["avg_vol"]
        if avg > 0 and vol > avg * VOLUME_ALERT_THRESHOLD:
            alerts.append({"ticker":ticker,"name":info["name"],"sector":info["sector"],
                           "volume":vol,"avg_volume":avg,"ratio":round(vol/avg,1),
                           "price":a.get("close",0),"change":a.get("change",0),
                           "rsi":a.get("rsi",50),"recommendation":a.get("recommendation","NEUTRAL")})
    return sorted(alerts, key=lambda x: x["ratio"], reverse=True)


def get_top_signals(analyses, learnings, commodities, bam_data, n=3):
    scored = []
    for ticker,info in BVC_WATCHLIST.items():
        a = analyses.get(ticker)
        if not a: continue
        s     = score_action(a, info, learnings, commodities, bam_data)
        close = a.get("close",0)
        if close <= 0 or s < 55: continue
        if s > 80:   tp = 0.06
        elif s > 70: tp = 0.05
        elif s > 60: tp = 0.04
        else:        tp = 0.03
        scored.append({
            "ticker":ticker,"name":info["name"],"sector":info["sector"],"mc":info.get("mc","small"),
            "score":s,"price":close,"target":round(close*(1+tp),2),"stop":round(close*0.98,2),
            "gain_pct":round(tp*100,1),"proba":round(min(95,45+s*0.5)),
            "rsi":round(a.get("rsi",50),1),"macd_cross":a.get("macd",0)>a.get("macd_signal",0),
            "adx":round(a.get("adx",0),1),"change":round(a.get("change",0),2),
            "recommendation":a.get("recommendation","NEUTRAL"),
            "buy_signals":a.get("buy_signals",0),"sell_signals":a.get("sell_signals",0),
            "volume":a.get("volume",0),"avg_volume":info["avg_vol"],"stoch_k":round(a.get("stoch_k",50),1),
            "bam":info.get("bam",False),"brent":info.get("brent",False),"phos":info.get("phos",False),
        })
    return sorted(scored, key=lambda x: x["score"], reverse=True)[:n]


def get_hold_candidates(analyses, learnings, commodities, bam_data):
    candidates = []
    for ticker,info in BVC_WATCHLIST.items():
        a = analyses.get(ticker)
        if not a: continue
        s = score_action(a,info,learnings,commodities,bam_data)
        close  = a.get("close",0)
        ema200 = a.get("ema200",0)
        if close <= 0 or s < 78: continue
        if ema200 > 0 and close > ema200*0.93:
            candidates.append({"ticker":ticker,"name":info["name"],"sector":info["sector"],
                               "score":s,"price":close,"target30":round(close*1.30,2),
                               "proba":round(min(82,40+s*0.5))})
    return sorted(candidates, key=lambda x: x["score"], reverse=True)[:2]


# ─── TRADE LOG ────────────────────────────────────────────────────────────────

def load_trades():
    if os.path.exists(TRADE_LOG_FILE):
        with open(TRADE_LOG_FILE,"r",encoding="utf-8") as f: return json.load(f)
    return []

def get_open_trades():
    return [t for t in load_trades() if t.get("status")=="open"]

def get_week_pnl():
    trades      = load_trades()
    today       = datetime.date.today()
    week_start  = today - datetime.timedelta(days=today.weekday())
    wt          = [t for t in trades if t.get("date","") >= str(week_start)]
    total_pnl   = sum(t.get("pnl_pct",0) for t in wt if t.get("status")=="closed")
    wins        = sum(1 for t in wt if t.get("pnl_pct",0)>0 and t.get("status")=="closed")
    total_closed= sum(1 for t in wt if t.get("status")=="closed")
    return {"total_pnl":round(total_pnl,2),"wins":wins,"total":total_closed,
            "open":len(get_open_trades()),"win_rate":round(wins/total_closed*100) if total_closed>0 else 0}


# ─── EMAIL ────────────────────────────────────────────────────────────────────

def send_email(subject, html):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = GMAIL_USER
        msg["To"]      = TO_EMAIL
        msg.attach(MIMEText(html,"html"))
        with smtplib.SMTP_SSL("smtp.gmail.com",465) as s:
            s.login(GMAIL_USER, GMAIL_PASSWORD)
            s.sendmail(GMAIL_USER, TO_EMAIL, msg.as_string())
        print(f"[BARAKA] Email: {subject}")
        return True
    except Exception as e:
        print(f"[BARAKA] Email erreur: {e}")
        return False


def build_signal_card(s, rank):
    color    = "#00C87A" if s["score"]>=70 else "#C9A84C"
    rc       = "#FF4560" if s["rsi"]>70 else "#00C87A" if s["rsi"]<35 else "#C9A84C"
    vr       = round(s["volume"]/s["avg_volume"],1) if s["avg_volume"]>0 else 1
    vc       = "#00C87A" if vr>2 else "#F59E0B" if vr>1.5 else "#9CA3AF"
    cc       = "#00C87A" if s["change"]>=0 else "#FF4560"
    corr     = ""
    if s.get("bam"):   corr += "<span style='font-size:9px;background:rgba(0,150,255,0.15);color:#60A5FA;padding:2px 6px;border-radius:3px;margin-left:3px'>BAM</span>"
    if s.get("brent"): corr += "<span style='font-size:9px;background:rgba(255,140,0,0.15);color:#FB923C;padding:2px 6px;border-radius:3px;margin-left:3px'>BRENT</span>"
    if s.get("phos"):  corr += "<span style='font-size:9px;background:rgba(100,200,100,0.15);color:#4ADE80;padding:2px 6px;border-radius:3px;margin-left:3px'>PHOSPHATE</span>"
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
<tr><td style="color:#6B7280;padding:3px 0">MACD</td><td colspan="3" style="color:#9CA3AF;text-align:right">{'Croisement haussier' if s['macd_cross'] else 'Pas encore croise'}</td></tr>
<tr><td style="color:#6B7280;padding:3px 0">Volume</td><td colspan="3" style="color:{vc};text-align:right">x{vr} ({int(s['volume']):,} vs {int(s['avg_volume']):,})</td></tr>
<tr><td style="color:#6B7280;padding:3px 0">TV</td><td colspan="3" style="color:#9CA3AF;text-align:right">{s['buy_signals']} BUY / {s['sell_signals']} SELL · {s['recommendation']}</td></tr>
</table>
<div style="margin-top:8px">
<div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:3px"><span style="color:#6B7280">Score Baraka (adaptatif)</span><span style="color:{color};font-weight:700">{s['score']}/100</span></div>
<div style="background:#0A0D14;border-radius:3px;height:4px"><div style="height:100%;border-radius:3px;background:{color};width:{s['score']}%"></div></div>
<div style="display:flex;justify-content:space-between;font-size:11px;margin-top:5px"><span style="color:#6B7280">Proba +2%</span><span style="color:{color};font-weight:700">{s['proba']}%</span></div>
</div></div>"""


def build_spread_card(o):
    liq_color = "#00C87A" if o["liquidity_score"]>=70 else "#F59E0B" if o["liquidity_score"]>=45 else "#FF4560"
    gain_color = "#00C87A" if o["quick_gain_pct"]>=2 else "#F59E0B"
    return f"""<div style="background:#171C2C;border-radius:10px;padding:14px;margin-bottom:10px;border-left:4px solid #F59E0B">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
<div><span style="font-size:18px;font-weight:900;color:#F59E0B;font-family:monospace">{o['ticker']}</span>
<span style="font-size:10px;color:#6B7280;margin-left:8px">{o['name']} · {o['sector']}</span></div>
<span style="background:rgba(245,158,11,0.15);color:#F59E0B;border:1px solid rgba(245,158,11,0.3);font-size:10px;padding:3px 10px;border-radius:4px;font-weight:700">SPREAD OPP.</span>
</div>
<table style="width:100%;font-size:12px;border-collapse:collapse">
<tr><td style="color:#6B7280;padding:3px 0">Meilleur Bid</td><td style="color:#00C87A;font-weight:700;text-align:right">{o['best_bid']:.2f} MAD</td>
<td style="color:#6B7280;padding:3px 12px">Meilleur Ask</td><td style="color:#FF4560;font-weight:700;text-align:right">{o['best_ask']:.2f} MAD</td></tr>
<tr><td style="color:#6B7280;padding:3px 0">Spread</td><td style="color:#F59E0B;font-weight:700;text-align:right">{o['spread_pct']:.2f}% ({o['spread_mad']:.2f} MAD)</td>
<td style="color:#6B7280;padding:3px 12px">Gain rapide</td><td style="color:{gain_color};font-weight:700;text-align:right">{o['quick_gain_pct']:.2f}%</td></tr>
<tr><td style="color:#6B7280;padding:3px 0">Liquidite</td><td style="color:{liq_color};font-weight:700;text-align:right">{o['liquidity_score']}/100</td>
<td style="color:#6B7280;padding:3px 12px">Profondeur</td><td style="color:#9CA3AF;text-align:right">{int(o['total_depth_mad']):,} MAD</td></tr>
<tr><td style="color:#6B7280;padding:3px 0">RSI</td><td style="color:#E8E4D6;text-align:right">{o['rsi']}</td>
<td style="color:#6B7280;padding:3px 12px">Source</td><td style="color:#6B7280;text-align:right;font-size:10px">{o['source']}</td></tr>
</table>
<div style="margin-top:8px;font-size:11px;color:#9CA3AF">Strategie: acheter au bid {o['best_bid']:.2f} · vendre a l'ask {o['best_ask']:.2f} · gain net estime {o['quick_gain_pct']:.2f}%</div>
<div style="margin-top:4px;font-size:11px;color:#6B7280">Score opportunite: <span style="color:#F59E0B;font-weight:700">{o['opp_score']}/100</span></div>
</div>"""


def build_email(subject_type, signals, spread_opps, open_trades, hold_candidates,
                news, ammc_news, oc_news, commodities, masi, bam_data,
                vol_alerts, week_pnl, llm_insight_text, learnings):
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    acc = learnings.get("accuracy_rate", 0)

    if subject_type=="matin":   window,instr,ch="FENETRE 1 - 10h00-12h00","Tu achetes maintenant - vends avant midi","#00C87A"
    elif subject_type=="midi":  window,instr,ch="FENETRE 2 - 12h00-14h00","Point mi-journee - garde ou switche","#F59E0B"
    else:                       window,instr,ch="CLOTURE - 15h15","Decision finale - cloture ou hold max 1 semaine","#C9A84C"

    signals_html   = "".join(build_signal_card(s,i+1) for i,s in enumerate(signals))
    spread_html    = "".join(build_spread_card(o) for o in spread_opps) if spread_opps else ""
    spread_section = f"""<div style="font-size:10px;color:#F59E0B;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">OPPORTUNITES SPREAD CARNET D'ORDRES</div>{spread_html}""" if spread_opps else ""

    masi_c = "#00C87A" if masi.get("change",0)>=0 else "#FF4560"
    masi_h = f"""<div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:12px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center">
<div><span style="font-size:10px;color:#6B7280;letter-spacing:2px">MASI</span><br>
<span style="font-size:18px;font-weight:900;color:#E8E4D6;font-family:monospace">{masi.get('close',0):,.2f}</span>
<span style="color:{masi_c};font-weight:700;margin-left:8px">{'+' if masi.get('change',0)>=0 else ''}{masi.get('change',0):.2f}%</span></div>
<div style="text-align:right;font-size:11px;color:#6B7280">RSI <span style="color:#C9A84C">{masi.get('rsi',50):.0f}</span><br>
{masi.get('rec','')}</div></div>"""

    taux   = bam_data.get("taux_directeur",3.0) or 3.0
    bam_c  = "#00C87A" if taux<=3 else "#FF4560"
    bam_news_h = "".join(f"<div style='font-size:11px;color:#9CA3AF;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04)'>{n}</div>" for n in bam_data.get("news",[])[:3])
    bam_h  = f"""<div style="background:rgba(0,100,255,0.06);border:1px solid rgba(0,100,255,0.2);border-radius:10px;padding:14px;margin-bottom:14px">
<div style="font-size:10px;color:#60A5FA;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px">BANQUE AL-MAGHRIB (BAM)</div>
<div style="display:flex;justify-content:space-between;margin-bottom:10px">
<div><span style="font-size:10px;color:#6B7280">TAUX DIRECTEUR</span><br>
<span style="font-size:20px;font-weight:900;color:#60A5FA;font-family:monospace">{taux}%</span></div>
<div style="text-align:right;font-size:11px;color:#6B7280">Impact bancaire:<br><span style="color:{bam_c}">{'Favorable' if taux<=3 else 'Defavorable'}</span></div></div>
{bam_news_h}</div>"""

    insight_h = f"""<div style="background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.25);border-radius:10px;padding:14px;margin-bottom:14px">
<div style="font-size:10px;color:#8B5CF6;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px">ANALYSE BARAKA · LLM GROQ (Precision {acc}%)</div>
<div style="font-size:12px;color:#E8E4D6;line-height:1.7">{llm_insight_text}</div></div>""" if llm_insight_text else ""

    open_h = ""
    if open_trades:
        rows = "".join(f"<div style='display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05);font-size:12px'><span style='color:#00C87A;font-weight:700;font-family:monospace'>{t.get('ticker','?')}</span><span style='color:#6B7280'>Entree {t.get('entry',0):.2f} MAD</span><span style='color:#C9A84C'>Cible {t.get('target',0):.2f}</span></div>" for t in open_trades)
        open_h = f"<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px;margin-bottom:14px'><div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>POSITIONS OUVERTES</div>{rows}</div>"

    hold_h = ""
    if hold_candidates and subject_type=="cloture":
        rows = "".join(f"<div style='background:#171C2C;border-radius:8px;padding:12px;margin-bottom:8px;border-left:3px solid #8B5CF6'><div style='display:flex;justify-content:space-between'><span style='color:#8B5CF6;font-weight:900;font-family:monospace'>{h['ticker']}</span><span style='font-size:10px;color:#9CA3AF'>{h['name']}</span></div><div style='font-size:12px;margin-top:6px;display:flex;justify-content:space-between'><span style='color:#6B7280'>Entree <span style='color:#E8E4D6'>{h['price']:.2f}</span></span><span style='color:#8B5CF6;font-weight:700'>+30%: {h['target30']:.2f}</span><span style='color:#9CA3AF'>Score {h['score']}/100</span></div></div>" for h in hold_candidates)
        hold_h = f"<div style='background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.25);border-radius:10px;padding:14px;margin-bottom:14px'><div style='font-size:10px;color:#8B5CF6;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>HOLD SEMAINE - OBJECTIF +30%</div>{rows}</div>"

    vol_h = ""
    if vol_alerts:
        rows = "".join(f"<div style='display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:12px'><div><span style='color:#FF4560;font-weight:700;font-family:monospace'>{v['ticker']}</span><span style='color:#6B7280;margin-left:6px;font-size:11px'>{v['name']}</span></div><span style='color:#FF4560;font-weight:700'>x{v['ratio']}</span></div>" for v in vol_alerts[:5])
        vol_h = f"<div style='background:rgba(255,69,96,0.06);border:1px solid rgba(255,69,96,0.25);border-radius:10px;padding:14px;margin-bottom:14px'><div style='font-size:10px;color:#FF4560;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>ALERTES VOLUMES ({len(vol_alerts)} actions)</div>{rows}</div>"

    labels = {"brent":("Brent","Energie"),"gold":("Or","Refuge"),"silver":("Argent","Indus."),"usd_mad":("USD/MAD","Forex"),"eur_mad":("EUR/MAD","Forex"),"eur_usd":("EUR/USD","Forex"),"us10y":("US 10Y","Taux"),"sp500":("S&P 500","US"),"stoxx50":("STOXX 50","EU")}
    comm_rows = "".join(f"<div style='display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:12px'><span style='color:#6B7280'>{lb} <span style='font-size:10px;color:#4B5563'>({cat})</span></span><span style='color:{'#00C87A' if commodities.get(k,{}).get('change',0)>=0 else '#FF4560'};font-weight:700'>{'+' if commodities.get(k,{}).get('change',0)>=0 else ''}{commodities.get(k,{}).get('change',0):.2f}%</span></div>" for k,(lb,cat) in labels.items())
    comm_h = f"<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px;margin-bottom:14px'><div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>MATIERES PREMIERES & MARCHES</div>{comm_rows}</div>"

    all_news = [("BourseNews",n) for n in news[:3]]+[("AMMC",n) for n in ammc_news[:2]]+[("Office Changes",n) for n in oc_news[:2]]
    news_rows = "".join(f"<div style='padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.04)'><span style='font-size:9px;color:{'#FF4560' if s=='AMMC' else '#F59E0B' if s=='Office Changes' else '#9CA3AF'};font-weight:700;letter-spacing:1px'>{s}</span><div style='font-size:11px;color:#9CA3AF;margin-top:2px'>{n}</div></div>" for s,n in all_news)
    news_h = f"<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px;margin-bottom:14px'><div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>FLUX MARCHE & PUBLICATIONS</div>{news_rows}</div>"

    pc = "#00C87A" if week_pnl["total_pnl"]>=0 else "#FF4560"
    pnl_h = f"<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px;margin-bottom:14px'><div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>PNL SEMAINE</div><div style='display:flex;justify-content:space-between;align-items:center'><div><div style='font-size:26px;font-weight:900;color:{pc};font-family:monospace'>{'+' if week_pnl['total_pnl']>=0 else ''}{week_pnl['total_pnl']}%</div><div style='font-size:11px;color:#6B7280'>{week_pnl['wins']}/{week_pnl['total']} trades · Win rate {week_pnl['win_rate']}%</div></div><div style='text-align:right'><div style='font-size:11px;color:#6B7280'>Ouvertes</div><div style='font-size:20px;font-weight:700;color:#C9A84C'>{week_pnl['open']}</div></div></div></div>"

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="background:#0A0D14;color:#E8E4D6;font-family:'Courier New',monospace;margin:0;padding:0">
<div style="max-width:620px;margin:0 auto;padding:20px">
<div style="background:#111520;border:1px solid rgba(201,168,76,0.4);border-radius:14px;padding:20px;text-align:center;margin-bottom:16px">
<div style="font-size:28px;font-weight:900;color:#C9A84C;letter-spacing:6px">BARAKA v3.0</div>
<div style="font-size:10px;color:#6B7280;letter-spacing:2px;margin-top:2px">{now} · {len(BVC_WATCHLIST)} SOCIETES · GROQ LLM GRATUIT · Precision {acc}%</div>
<div style="display:inline-block;background:rgba(0,200,122,0.1);border:1px solid rgba(0,200,122,0.3);color:{ch};padding:5px 16px;border-radius:20px;font-size:11px;letter-spacing:2px;margin-top:10px">{window}</div></div>
<div style="background:rgba(201,168,76,0.08);border:1px solid rgba(201,168,76,0.25);border-radius:10px;padding:12px;margin-bottom:16px;text-align:center">
<div style="font-size:13px;color:#C9A84C;font-weight:700">{instr}</div></div>
{masi_h}{bam_h}{insight_h}
<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">TOP 3 SIGNAUX DU JOUR</div>
{signals_html}{spread_section}{open_h}{hold_h}{vol_h}{comm_h}{news_h}{pnl_h}
<div style="text-align:center;font-size:10px;color:#4B5563;margin-top:16px;line-height:1.9">
Confirmez chaque trade manuellement · Max 3 trades/jour · T-15min<br>
<strong style="color:#C9A84C">+5%/jour · Hold semaine = +30% min</strong><br>
TradingView · Wafabourse · AMMC · BAM · Office des Changes · Groq LLM</div>
</div></body></html>"""


# ─── ANALYSE PRINCIPALE ───────────────────────────────────────────────────────

def run_analysis():
    print(f"[BARAKA] Analyse {len(BVC_WATCHLIST)} societes...")
    analyses = {}
    for ticker in BVC_WATCHLIST:
        a = get_tv_analysis(ticker)
        if a: analyses[ticker] = a
        time.sleep(0.35)
    print(f"[BARAKA] {len(analyses)}/{len(BVC_WATCHLIST)} OK")
    return analyses


def run_alert(subject_type):
    print(f"[BARAKA] === {subject_type.upper()} ===")
    learnings   = load_learnings()
    analyses    = run_analysis()
    commodities = get_commodities()
    bam_data    = scrape_bam()
    masi        = get_masi()
    signals     = get_top_signals(analyses, learnings, commodities, bam_data, n=3)
    spread_opps = analyze_spread_opportunities(analyses)
    open_trades = get_open_trades()
    news        = scrape_boursenews()
    ammc_news   = scrape_ammc()
    oc_news     = scrape_oc()
    vol_alerts  = check_volume_alerts(analyses)
    week_pnl    = get_week_pnl()
    hold_cands  = get_hold_candidates(analyses,learnings,commodities,bam_data) if subject_type=="cloture" else []

    # Sauvegarder signaux du matin
    if subject_type=="matin":
        with open(f"signals_{datetime.date.today()}.json","w") as f:
            json.dump(signals, f, ensure_ascii=False)

    # Sauvegarder opportunites spread
    if spread_opps:
        with open(f"spreads_{datetime.date.today()}.json","w") as f:
            json.dump(spread_opps, f, ensure_ascii=False)

    bam_ctx = f"Taux {bam_data.get('taux_directeur',3.0)}% · {' | '.join(bam_data.get('news',[])[:2])}"
    insight = llm_insight(signals, spread_opps, commodities, masi, bam_ctx, learnings)

    html = build_email(subject_type, signals, spread_opps, open_trades, hold_cands,
                       news, ammc_news, oc_news, commodities, masi, bam_data,
                       vol_alerts, week_pnl, insight, learnings)

    titles = {
        "matin":   "BARAKA v3 · SIGNAL MATIN - 3 signaux + spreads BVC",
        "midi":    "BARAKA v3 · POINT MIDI - Garder / Vendre / Switcher",
        "cloture": "BARAKA v3 · CLOTURE BVC - Decision finale",
    }
    send_email(titles[subject_type], html)
    if vol_alerts: send_volume_alert(vol_alerts)


def post_cloture_analysis():
    """16h30 - apprentissage LLM post-cloture"""
    now = datetime.datetime.now()
    if now.weekday() >= 5: return
    print("[BARAKA] === POST-CLOTURE APPRENTISSAGE ===")
    learnings = load_learnings()
    trades_today = [t for t in load_trades() if t.get("date","") == str(datetime.date.today())]
    signals_file = f"signals_{datetime.date.today()}.json"
    signals_today = []
    if os.path.exists(signals_file):
        with open(signals_file,"r") as f: signals_today = json.load(f)
    spreads_file = f"spreads_{datetime.date.today()}.json"
    spread_opps = []
    if os.path.exists(spreads_file):
        with open(spreads_file,"r") as f: spread_opps = json.load(f)

    commodities = get_commodities()
    masi        = get_masi()
    bam_data    = scrape_bam()

    market_ctx = {
        "date":     str(datetime.date.today()),
        "masi":     masi,
        "brent":    commodities.get("brent",{}),
        "gold":     commodities.get("gold",{}),
        "usd_mad":  commodities.get("usd_mad",{}),
        "sp500":    commodities.get("sp500",{}),
        "bam_taux": bam_data.get("taux_directeur"),
        "bam_news": bam_data.get("news",[]),
    }

    result = llm_post_cloture(trades_today, signals_today, spread_opps, market_ctx, learnings)

    if result:
        learnings["lessons"].append({
            "date":      str(datetime.date.today()),
            "analyse":   result.get("analyse_du_jour",""),
            "lecons":    result.get("lecons_apprises",[]),
            "patterns":  result.get("patterns_detectes",[]),
            "precision": result.get("score_precision_jour",0),
            "demain":    result.get("recommandations_demain",""),
        })
        if len(learnings["lessons"]) > 60:
            learnings["lessons"] = learnings["lessons"][-60:]
        # Mise a jour poids (EMA 70/30)
        for k,v in result.get("nouveaux_poids",{}).items():
            if k in learnings["indicator_weights"]:
                old = learnings["indicator_weights"][k]
                learnings["indicator_weights"][k] = round(old*0.7 + v*0.3, 3)
        learnings["secteurs_favorables"]  = result.get("secteurs_favorables",[])
        learnings["secteurs_eviter"]      = result.get("secteurs_eviter",[])
        learnings["spread_min_viable"]    = result.get("spread_min_viable", 1.5)
        learnings["liquidity_min_score"]  = result.get("liquidity_min_score", 40)
        learnings["last_updated"]         = str(datetime.datetime.now())
        learnings["total_analyzed"]       = learnings.get("total_analyzed",0) + 1
        hist = learnings.get("accuracy_history",[])
        hist.append({"date":str(datetime.date.today()),"score":result.get("score_precision_jour",0)})
        learnings["accuracy_history"] = hist[-30:]
        learnings["accuracy_rate"]    = round(sum(h["score"] for h in hist)/len(hist),1)
        save_learnings(learnings)
        send_post_cloture_email(result, learnings, trades_today)
        print(f"[BARAKA] Apprentissage OK · Precision: {result.get('score_precision_jour',0)}%")


def send_post_cloture_email(result, learnings, trades_today):
    now   = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    acc   = learnings.get("accuracy_rate",0)
    total = learnings.get("total_analyzed",0)
    score = result.get("score_precision_jour",0)
    sc    = "#00C87A" if score>=70 else "#F59E0B" if score>=50 else "#FF4560"
    weights = learnings.get("indicator_weights",{})

    lecons_h  = "".join(f"<div style='padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:12px;color:#9CA3AF'>• {l}</div>" for l in result.get("lecons_apprises",[]))
    patterns_h= "".join(f"<span style='background:rgba(139,92,246,0.15);color:#8B5CF6;font-size:10px;padding:3px 8px;border-radius:4px;margin:2px;display:inline-block'>{p}</span>" for p in result.get("patterns_detectes",[]))
    weights_h = "".join(f"<div style='display:flex;justify-content:space-between;padding:4px 0;font-size:12px'><span style='color:#6B7280'>{k.upper()}</span><div style='flex:1;margin:0 10px;background:#0A0D14;border-radius:2px;height:6px;margin-top:7px'><div style='height:100%;background:#C9A84C;border-radius:2px;width:{min(100,int(v*50))}%'></div></div><span style='color:#C9A84C;font-weight:700'>{v:.2f}</span></div>" for k,v in weights.items())
    sg = ", ".join(learnings.get("secteurs_favorables",[])[:4]) or "Aucun"
    se = ", ".join(learnings.get("secteurs_eviter",[])[:4])     or "Aucun"

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="background:#0A0D14;color:#E8E4D6;font-family:'Courier New',monospace;margin:0;padding:0">
<div style="max-width:620px;margin:0 auto;padding:20px">
<div style="background:#111520;border:1px solid rgba(139,92,246,0.4);border-radius:14px;padding:20px;text-align:center;margin-bottom:16px">
<div style="font-size:26px;font-weight:900;color:#C9A84C;letter-spacing:6px">BARAKA</div>
<div style="font-size:10px;color:#6B7280;letter-spacing:2px;margin-top:2px">POST-CLOTURE · APPRENTISSAGE LLM GROQ · {now}</div>
<div style="display:inline-block;background:rgba(139,92,246,0.12);border:1px solid rgba(139,92,246,0.35);color:#8B5CF6;padding:5px 16px;border-radius:20px;font-size:11px;letter-spacing:2px;margin-top:10px">SESSION #{total}</div></div>

<div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:16px;margin-bottom:14px">
<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">ANALYSE DU JOUR</div>
<div style="font-size:13px;color:#E8E4D6;line-height:1.7">{result.get("analyse_du_jour","")}</div>
<div style="margin-top:10px;font-size:11px;color:#6B7280;font-style:italic">Pour demain: {result.get("recommandations_demain","")}</div></div>

<div style="display:flex;gap:10px;margin-bottom:14px">
<div style="flex:1;background:#171C2C;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:12px;text-align:center">
<div style="font-size:10px;color:#6B7280;margin-bottom:4px">PRECISION DU JOUR</div>
<div style="font-size:24px;font-weight:900;color:{sc};font-family:monospace">{score}%</div></div>
<div style="flex:1;background:#171C2C;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:12px;text-align:center">
<div style="font-size:10px;color:#6B7280;margin-bottom:4px">MOY. 30 JOURS</div>
<div style="font-size:24px;font-weight:900;color:#C9A84C;font-family:monospace">{acc}%</div></div>
<div style="flex:1;background:#171C2C;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:12px;text-align:center">
<div style="font-size:10px;color:#6B7280;margin-bottom:4px">SESSIONS TOTAL</div>
<div style="font-size:24px;font-weight:900;color:#8B5CF6;font-family:monospace">{total}</div></div></div>

<div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:16px;margin-bottom:14px">
<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">LECONS APPRISES</div>
{lecons_h}
<div style="margin-top:12px">{patterns_h}</div></div>

<div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:16px;margin-bottom:14px">
<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">POIDS ADAPTATIFS (Groq LLM)</div>
{weights_h}</div>

<div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px;margin-bottom:14px">
<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px">SECTEURS APPRIS</div>
<div style="display:flex;justify-content:space-between;font-size:12px">
<div><div style="color:#00C87A;margin-bottom:4px">FAVORABLES</div><div style="color:#9CA3AF">{sg}</div></div>
<div style="text-align:right"><div style="color:#FF4560;margin-bottom:4px">A EVITER</div><div style="color:#9CA3AF">{se}</div></div></div>
<div style="margin-top:10px;font-size:11px;color:#6B7280">Seuil spread viable: <span style="color:#F59E0B">{learnings.get('spread_min_viable',1.5)}%</span> · Liquidite min: <span style="color:#F59E0B">{learnings.get('liquidity_min_score',40)}/100</span></div></div>

<div style="text-align:center;font-size:10px;color:#4B5563;margin-top:16px;line-height:1.9">
Baraka apprend de chaque session · Gratuit via Groq llama3-70b<br>
<strong style="color:#8B5CF6">Session #{total} · Precision cumulee {acc}%</strong></div>
</div></body></html>"""
    send_email("BARAKA v3 · POST-CLOTURE - Apprentissage & Precision du jour", html)


def send_volume_alert(vol_alerts):
    rows = "".join(f"<tr><td style='color:#FF4560;font-weight:700;padding:8px;font-family:monospace'>{v['ticker']}</td><td style='padding:8px;color:#E8E4D6'>{v['name']}</td><td style='padding:8px;color:#FF4560;font-weight:700'>x{v['ratio']}</td><td style='padding:8px;color:#C9A84C'>{int(v['volume']):,}</td><td style='padding:8px;color:#6B7280'>{int(v['avg_volume']):,}</td><td style='padding:8px'>{v['price']:.2f} MAD</td></tr>" for v in vol_alerts)
    html = f"""<body style="background:#0A0D14;color:#E8E4D6;font-family:monospace;padding:20px"><div style="max-width:650px;margin:0 auto">
<div style="background:#111520;border:1px solid rgba(255,69,96,0.4);border-radius:12px;padding:16px;text-align:center;margin-bottom:16px">
<div style="font-size:22px;font-weight:900;color:#C9A84C;letter-spacing:4px">BARAKA</div>
<div style="color:#FF4560;font-size:13px;margin-top:6px;font-weight:700">ALERTE VOLUME ANORMAL - {len(vol_alerts)} ACTION(S)</div></div>
<table style="width:100%;border-collapse:collapse;background:#111520;border-radius:10px">
<thead><tr style="background:#171C2C;font-size:10px;color:#6B7280">
<th style="padding:10px;text-align:left">TICKER</th><th style="padding:10px;text-align:left">SOCIETE</th>
<th style="padding:10px;text-align:left">RATIO</th><th style="padding:10px;text-align:left">VOLUME</th>
<th style="padding:10px;text-align:left">MOYENNE</th><th style="padding:10px;text-align:left">COURS</th>
</tr></thead><tbody>{rows}</tbody></table>
</div></body>"""
    send_email(f"BARAKA · ALERTE VOLUME - {', '.join(v['ticker'] for v in vol_alerts[:4])}", html)


def monitor_volumes():
    now = datetime.datetime.now()
    if now.weekday() >= 5: return
    if not (9 <= now.hour < 16): return
    print("[BARAKA] Surveillance volumes...")
    learnings = load_learnings()
    analyses  = run_analysis()
    alerts    = check_volume_alerts(analyses)
    if alerts:
        print(f"[BARAKA] {len(alerts)} alerte(s)!")
        send_volume_alert(alerts)


# ─── SCHEDULER ───────────────────────────────────────────────────────────────

def run_scheduler():
    print("""
╔══════════════════════════════════════════════╗
║    BARAKA v3.0 · 100% GRATUIT · GROQ LLM    ║
║  75 Societes · Carnet Ordres · BAM · Spread  ║
╠══════════════════════════════════════════════╣
║  10h00 → Signal Matin + Spread Opps         ║
║  12h00 → Point Midi                          ║
║  15h15 → Cloture + Hold semaine             ║
║  16h30 → Post-Cloture Apprentissage Groq    ║
║  /15min → Surveillance Volumes              ║
╚══════════════════════════════════════════════╝
    """)
    days = [schedule.every().monday, schedule.every().tuesday,
            schedule.every().wednesday, schedule.every().thursday, schedule.every().friday]
    for d in days:
        d.at("10:00").do(run_alert, "matin")
        d.at("12:00").do(run_alert, "midi")
        d.at("15:15").do(run_alert, "cloture")
        d.at("16:30").do(post_cloture_analysis)
    schedule.every(15).minutes.do(monitor_volumes)
    print("[BARAKA] Scheduler actif. En attente...")
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    run_scheduler()
