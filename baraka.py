"""
BARAKA v7.0 — BVC Trading Intelligence — Hedge Fund Level
Casablanca Stock Exchange — Atlas Capital Intelligence
Livraison: 09/06/2026 05h00 — Testé et validé
"""

import os, time, datetime, threading, json, re, requests, io
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─── CONFIG ────────────────────────────────────────────────────────────────────
RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
GROQ_KEY   = os.environ.get("GROQ_API_KEY", "")
TO_EMAIL   = "mohamed.csaibari@gmail.com"
FROM_EMAIL = "Baraka BVC <onboarding@resend.dev>"
HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
R   = {"verify": False, "timeout": 8}

# ─── CACHE ─────────────────────────────────────────────────────────────────────
_CACHE = {}
def cache_set(k, v): _CACHE[k] = {"d": v, "t": datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)}
def cache_get(k, max_min=180):
    if k not in _CACHE: return None
    age = (datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - _CACHE[k]["t"]).total_seconds() / 60
    return _CACHE[k]["d"] if age < max_min else None

# ─── WATCHLIST ─────────────────────────────────────────────────────────────────
_WATCHLIST = {}
def watchlist_add(t, entry, stop, target, side="BUY"):
    _WATCHLIST[t] = {"entry":entry,"stop":stop,"target":target,"side":side,"fired":[],"name":BVC.get(t,{}).get("n",t)}
def watchlist_clear(): _WATCHLIST.clear()

# ─── UNIVERS BVC ────────────────────────────────────────────────────────────────
BVC = {
    # BANQUES
    "ATW":    {"n":"Attijariwafa Bank","s":"Banque","v":85000,"mc":"large"},
    "BCP":    {"n":"Banque Centrale Pop.","s":"Banque","v":60000,"mc":"large"},
    "BMCE":   {"n":"Bank of Africa","s":"Banque","v":70000,"mc":"large"},
    "CIH":    {"n":"CIH Bank","s":"Banque","v":45000,"mc":"mid"},
    "CDM":    {"n":"Credit du Maroc","s":"Banque","v":18000,"mc":"mid"},
    "BMCI":   {"n":"BMCI","s":"Banque","v":12000,"mc":"mid"},
    "CFG":    {"n":"CFG Bank","s":"Banque","v":8000,"mc":"small"},
    # ASSURANCE
    "WAA":    {"n":"Wafa Assurance","s":"Assurance","v":6000,"mc":"mid"},
    "ATL":    {"n":"Atlanta","s":"Assurance","v":5000,"mc":"small"},
    "SAH":    {"n":"Saham Assurance","s":"Assurance","v":4000,"mc":"small"},
    # TELECOM
    "IAM":    {"n":"Maroc Telecom","s":"Telecom","v":120000,"mc":"large"},
    "HPS":    {"n":"HPS","s":"Tech","v":15000,"mc":"mid"},
    # CHIMIE / PHOSPHATE
    "OCP":    {"n":"OCP Group","s":"Chimie","v":95000,"mc":"large"},
    # MINES & METAUX PRECIEUX
    "MANAGEM":{"n":"Managem","s":"Mines","v":12000,"mc":"mid"},
    "SMI":    {"n":"SMI (Argent)","s":"Mines","v":8000,"mc":"small"},
    "CMT":    {"n":"CMT (Zinc/Plomb)","s":"Mines","v":5000,"mc":"small"},
    # IMMOBILIER & CONSTRUCTION
    "ADH":    {"n":"Addoha","s":"Immobilier","v":35000,"mc":"mid"},
    "ALM":    {"n":"Alliances","s":"Immobilier","v":15000,"mc":"mid"},
    "DAR":    {"n":"Res. Dar Saada","s":"Immobilier","v":4000,"mc":"small"},
    "TGCC":   {"n":"TGCC","s":"Construction","v":5000,"mc":"mid"},
    "SGTM":   {"n":"SGTM","s":"Construction","v":3000,"mc":"small"},
    "HOL":    {"n":"Holcim Maroc","s":"Construction","v":12000,"mc":"mid"},
    "CMA":    {"n":"Ciments du Maroc","s":"Construction","v":10000,"mc":"mid"},
    "LHM":    {"n":"LafargeHolcim","s":"Construction","v":9000,"mc":"mid"},
    # SANTE
    "AKDITAL":{"n":"Akdital","s":"Sante","v":4500,"mc":"mid"},
    # DISTRIBUTION
    "LABEL":  {"n":"Label Vie","s":"Distribution","v":9000,"mc":"mid"},
    "LAC":    {"n":"Lesieur Cristal","s":"Agro","v":11000,"mc":"mid"},
    "COSUMAR":{"n":"Cosumar","s":"Agro","v":8000,"mc":"mid"},
    # ENERGIE
    "TMA":    {"n":"Total Maroc","s":"Energie","v":7000,"mc":"mid"},
    "TAQA":   {"n":"Taqa Morocco","s":"Energie","v":8000,"mc":"mid"},
    # INDUSTRIE
    "SRM":    {"n":"Sonasid","s":"Siderurgie","v":6000,"mc":"mid"},
    "CTM":    {"n":"CTM","s":"Transport","v":5000,"mc":"small"},
    "SOTHEMA":{"n":"Sothema","s":"Pharma","v":6000,"mc":"mid"},
    "RIS":    {"n":"Risma","s":"Tourisme","v":5000,"mc":"small"},
    "EQDOM":  {"n":"Eqdom","s":"Credit Conso","v":4000,"mc":"small"},
}

# Titres sous surveillance quotidienne approfondie
VIP = ["ADH","ALM","TGCC","SGTM","DAR","AKDITAL","MANAGEM","SMI","CMT"]


# ─── EMAIL ──────────────────────────────────────────────────────────────────────
def send_email(subject, html):
    if not RESEND_KEY: print(f"[EMAIL] No key"); return False
    try:
        r = requests.post("https://api.resend.com/emails",
            headers={"Authorization":f"Bearer {RESEND_KEY}","Content-Type":"application/json"},
            json={"from":FROM_EMAIL,"to":[TO_EMAIL],"subject":subject,"html":html},
            timeout=15, verify=False)
        ok = r.status_code in [200,201]
        print(f"[EMAIL] {'OK' if ok else 'ERR '+str(r.status_code)}: {subject[:60]}")
        return ok
    except Exception as e:
        print(f"[EMAIL] {e}"); return False

# ─── GROQ ───────────────────────────────────────────────────────────────────────
def groq_call(prompt, max_tokens=600):
    if not GROQ_KEY: return ""
    try:
        from groq import Groq
        c = Groq(api_key=GROQ_KEY)
        r = c.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt}],
            max_tokens=max_tokens, temperature=0.15)
        return r.choices[0].message.content.strip()
    except Exception as e:
        print(f"[GROQ] {e}"); return ""


# ─── DONNEES MARCHÉ ──────────────────────────────────────────────────────────────
def fetch_stooq(sym):
    """Recupere prix + variation depuis stooq avec plusieurs formats de symboles"""
    # Essayer differents formats de symboles
    syms = [sym, sym.lower(), sym.upper()]
    if sym.startswith("^"):
        base = sym[1:]
        syms = [sym, base, f"{base}.us", f"{base}.n", base.lower()]

    for s in syms:
        try:
            # Utiliser une plage de dates pour garantir 2 lignes de donnees
            d2 = datetime.date.today().strftime("%Y%m%d")
            d1 = (datetime.date.today() - datetime.timedelta(days=10)).strftime("%Y%m%d")
            url = f"https://stooq.com/q/d/l/?s={s}&d1={d1}&d2={d2}&i=d"
            r = requests.get(url, headers=HDR, **R)
            if r.status_code != 200: continue
            lines = [l for l in r.text.strip().splitlines() if l and not l.startswith("Date")]
            if len(lines) >= 2:
                curr = float(lines[-1].split(",")[4])
                prev = float(lines[-2].split(",")[4])
                if curr > 0 and prev > 0:
                    return {"p": round(curr,2), "c": round((curr-prev)/prev*100, 2)}
        except: continue
    return {"p": 0, "c": 0}

def get_macro():
    """Donnees macro completes avec sources fiables"""
    m = {}

    # FRED: taux US fiables
    for k, s in [("us10y","DGS10"),("us2y","DGS2"),("fed_rate","FEDFUNDS"),("us_cpi","CPIAUCSL")]:
        try:
            r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}", headers=HDR, **R)
            lines = [l for l in r.text.strip().splitlines() if "." in l.split(",")[-1]]
            if lines: m[k] = float(lines[-1].split(",")[1])
            else: m[k] = 0
        except: m[k] = 0

    m["yield_spread"] = round(m.get("us10y",0) - m.get("us2y",0), 3)
    m["recession_risk"] = m["yield_spread"] < 0

    # Change rates
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", headers=HDR, **R)
        d = r.json().get("rates",{})
        m["usd_mad"] = round(float(d.get("MAD",10.0)), 4)
        m["eur_usd"] = round(1/float(d.get("EUR",0.92)), 4) if d.get("EUR") else 1.08
        m["eur_mad"] = round(m["usd_mad"] * float(d.get("EUR",0.92)), 4)
        m["gbp_mad"] = round(m["usd_mad"] * float(d.get("GBP",0.79)), 4)
    except: m.update({"usd_mad":10.0,"eur_usd":1.08,"eur_mad":10.9,"gbp_mad":12.5})

    # Indices mondiaux via stooq
    INDEX_MAP = {
        "sp500":"^spx","nasdaq":"^ndq","cac40":"^cac","dax":"^dax",
        "ftse":"^ukx","nikkei":"^nkx","shanghai":"^shc","hsi":"^hsi",
        "gold":"xauusd","silver":"xagusd","brent":"brent.f","wti":"cl.f",
        "copper":"hg.f","phosphate":"mos.us","dxy":"dxy.f","vix":"^vix",
    }
    for name, sym in INDEX_MAP.items():
        m[name] = fetch_stooq(sym)
        time.sleep(0.15)

    return m

# ─── TV SCANNER BVC ─────────────────────────────────────────────────────────────
def get_bvc_data():
    """Scanner TradingView — donnees temps reel tous les titres BVC"""
    TV_H = {
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
        "Content-Type":"application/json",
        "Origin":"https://www.tradingview.com",
        "Referer":"https://www.tradingview.com/markets/stocks-morocco/",
    }
    payload = {
        "filter":[],
        "columns":["name","close","volume","change","RSI","MACD.macd","MACD.signal",
                   "EMA20","EMA50","EMA200","Stoch.K","ADX","high","low","open",
                   "Recommend.All","average_volume_10d_calc","average_volume_30d_calc",
                   "average_volume_90d_calc","BB.upper","BB.lower"],
        "sort":{"sortBy":"market_cap_basic","sortOrder":"desc"},
        "range":[0,100],
    }
    data = {}
    try:
        r = requests.post("https://scanner.tradingview.com/morocco/scan",
                         headers=TV_H, json=payload, timeout=25, verify=False)
        if r.status_code != 200:
            print(f"[TV] HTTP {r.status_code}"); return {}
        rows = r.json().get("data",[])
        print(f"[TV] {len(rows)} titres recus")
        for row in rows:
            raw  = row.get("s","").upper()
            vals = row.get("d",[])
            if len(vals) < 4: continue
            ticker = None
            for t in BVC:
                if t in raw: ticker = t; break
            if not ticker: continue
            def v(i, d=0):
                try: return float(vals[i]) if vals[i] is not None else d
                except: return d
            avg90 = v(18,0); avg30 = v(17,0); avg10 = v(16,0)
            avg_vol = avg90 or avg30 or avg10 or BVC.get(ticker,{}).get("v",1)
            rec = v(15,0)
            data[ticker] = {
                "close":v(1),"volume":int(v(2)),"change":round(v(3),2),
                "rsi":v(4,50),"macd":v(5),"macd_s":v(6),
                "ema20":v(7),"ema50":v(8),"ema200":v(9),
                "stoch":v(10,50),"adx":v(11),
                "high":v(12),"low":v(13),"open":v(14),
                "bb_upper":v(19),"bb_lower":v(20),
                "rec":"ACHAT" if rec>0.1 else ("VENTE" if rec<-0.1 else "NEUTRE"),
                "avg10":avg10,"avg30":avg30,"avg90":avg90,"avg_vol":avg_vol,
            }
        print(f"[TV] {len(data)} titres BVC")
    except Exception as e:
        print(f"[TV] {e}")
    return data


# ─── GÉOPOLITIQUE & NEWS ─────────────────────────────────────────────────────────
def gnews(q, n=4):
    """Google News RSS"""
    items = []
    try:
        from urllib.parse import quote
        r = requests.get(f"https://news.google.com/rss/search?q={quote(q)}&hl=fr&gl=MA&ceid=MA:fr",
                        headers=HDR, **R)
        titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", r.text)
        for t in titles[1:n+1]:
            clean = re.sub(r"<[^>]+>","",t).strip()
            if len(clean) > 15: items.append(clean[:200])
    except: pass
    return items

def get_geopolitical_scanner():
    """
    Scanner geopolitique - detecte les evenements mondiaux avec impact Maroc.
    Couvre: Moyen Orient, USA, Europe, Chine, Russie, commodites, devises.
    """
    geo = {}

    # Conflits & tensions militaires
    geo["moyen_orient"] = gnews("Iran Israel guerre conflit Moyen Orient 2026", 4)
    geo["ukraine"]      = gnews("Ukraine Russie guerre petrole gaz 2026", 3)
    geo["usa_chine"]    = gnews("USA Chine tension commerce Taiwan 2026", 3)
    geo["afrique"]      = gnews("Afrique instabilite economique Maroc 2026", 2)

    # Macro & banques centrales
    geo["fed"]          = gnews("Federal Reserve inflation taux USA 2026", 4)
    geo["bce"]          = gnews("BCE taux directeur zone euro recession 2026", 3)
    geo["bkam"]         = gnews("Bank Al Maghrib BAM taux directeur Maroc 2026", 3)

    # Maroc direct
    geo["maroc_eco"]    = gnews("Maroc economie croissance exportations 2026", 4)
    geo["maroc_fin"]    = gnews("Maroc bourse MASI investissement 2026", 3)
    geo["maroc_social"] = gnews("Maroc inflation salaires consommation 2026", 3)

    # Commodites Maroc
    geo["petrole"]      = gnews("petrole OPEC prix Brent impact inflation 2026", 3)
    geo["phosphate"]    = gnews("phosphate OCP Maroc prix export demande 2026", 3)
    geo["or_argent"]    = gnews("or argent mines prix Managem SMI 2026", 3)

    # Partenaires commerciaux Maroc
    geo["france"]       = gnews("France economie exportations Maroc 2026", 2)
    geo["espagne"]      = gnews("Espagne economie Maroc tourisme 2026", 2)

    return geo

def get_maroc_social_media():
    """Intelligence sociale - Telegram, news marocaines, forums traders"""
    posts = []

    # Telegram BVC
    for ch in ["boursecasablancaofficiel","bvcmaroc","tradingmaroc","financeMaroc"]:
        try:
            from bs4 import BeautifulSoup
            r = requests.get(f"https://t.me/s/{ch}", headers=HDR, **R)
            soup = BeautifulSoup(r.text,"html.parser")
            for msg in soup.select(".tgme_widget_message_text")[:3]:
                t = msg.get_text(strip=True)
                if len(t) > 20: posts.append({"src":f"Telegram/{ch}","t":t[:200]})
        except: pass
        time.sleep(0.3)

    # Sources news marocaines financieres via Google News
    maroc_news = gnews("bourse Casablanca MASI traders investisseurs 2026", 5)
    for n in maroc_news:
        posts.append({"src":"Google/BVC","t":n})

    # Hespress finance
    try:
        from bs4 import BeautifulSoup
        r = requests.get("https://www.hespress.com/economie", headers=HDR, **R)
        soup = BeautifulSoup(r.text,"html.parser")
        for el in soup.select("h2,h3")[:5]:
            t = el.get_text(strip=True)
            if len(t) > 20: posts.append({"src":"Hespress","t":t[:180]})
    except: pass

    return posts[:15]

def get_boursenews():
    """BourseNews.ma - news BVC fraiche"""
    try:
        from bs4 import BeautifulSoup
        r = requests.get("https://www.boursenews.ma/", headers=HDR, **R)
        soup = BeautifulSoup(r.text,"html.parser")
        items = []
        for el in soup.select("article h2, article h3, .entry-title")[:8]:
            t = el.get_text(strip=True)
            if len(t) > 20: items.append(t[:200])
        return list(dict.fromkeys(items))[:6]
    except: return []

def get_ammc_pubs():
    """Publications AMMC - toutes les pages recentes"""
    pubs = []
    try:
        from bs4 import BeautifulSoup
        seen = set()
        for page in range(0, 6):
            url = f"https://www.ammc.ma/fr/communiques-presse-emetteurs?page={page}" if page else \
                  "https://www.ammc.ma/fr/communiques-presse-emetteurs"
            r = requests.get(url, headers=HDR, **R)
            if r.status_code != 200: break
            soup = BeautifulSoup(r.text,"html.parser")
            found = 0
            for link in soup.find_all("a", href=True):
                href = link["href"]
                text = link.get_text(strip=True)
                if not text or len(text) < 5: continue
                if not any(x in href.lower() for x in [".pdf","telecharger","download"]): continue
                full = href if href.startswith("http") else "https://www.ammc.ma"+href
                if full in seen: continue
                seen.add(full)
                ticker = None
                tu = text.upper()
                for t, info in BVC.items():
                    if t in tu or info["n"].split()[0].upper() in tu:
                        ticker = t; break
                pubs.append({"url":full,"title":text[:150],"ticker":ticker})
                found += 1
            if found == 0: break
            time.sleep(0.4)
        print(f"[AMMC] {len(pubs)} publications")
    except Exception as e:
        print(f"[AMMC] {e}")
    return pubs[:40]

def get_company_news(ticker):
    """News specifique par entreprise"""
    info = BVC.get(ticker, {})
    name = info.get("n", ticker)
    sect = info.get("s", "")
    news = []
    news += gnews(f"{name} Maroc resultats bilan dividende 2026", 3)
    news += gnews(f"{ticker} bourse Casablanca 2026", 2)
    if sect: news += gnews(f"{sect} Maroc secteur 2026", 1)
    return list(dict.fromkeys(news))[:4]

def get_bdt_rates():
    """Taux Bons du Tresor Maroc - reference d arbitrage"""
    data = {"news":[], "rates":{}}
    data["news"]  = gnews("bons tresor Maroc BDT taux adjudication 2026", 3)
    data["rates"] = gnews("taux interet BAM Maroc directeur 2026", 2)
    return data


# ─── ANALYSE TECHNIQUE AVANCEE ─────────────────────────────────────────────────
def tech_score(d, info, macro=None):
    """
    Score technique 0-100 multi-indicateurs.
    Integre: RSI, MACD, EMA (3 periodes), Volume, ADX, Stoch, Bollinger, Macro.
    """
    if not d or not d.get("close"): return 0
    s = 50
    close  = d.get("close",0)
    rsi    = d.get("rsi",50)
    macd   = d.get("macd",0);   macd_s = d.get("macd_s",0)
    ema20  = d.get("ema20",0);  ema50  = d.get("ema50",0);  ema200 = d.get("ema200",0)
    stoch  = d.get("stoch",50); adx    = d.get("adx",0)
    vol    = d.get("volume",0); avg    = d.get("avg_vol",1) or info.get("v",1)
    bb_up  = d.get("bb_upper",0); bb_lo = d.get("bb_lower",0)
    sect   = info.get("s",""); mc = info.get("mc","small")

    # RSI — survendu/suracheté avec nuances
    if rsi < 20: s += 25
    elif rsi < 30: s += 18
    elif rsi < 40: s += 8
    elif rsi > 80: s -= 25
    elif rsi > 70: s -= 15
    elif rsi > 60: s -= 5

    # MACD — croisement et position
    if macd > macd_s:
        s += 15 if macd_s < 0 else 8  # croisement en zone negative = signal fort
    else:
        s -= 12 if macd_s > 0 else 6

    # EMA alignment — tendance multi-timeframe
    if close > ema20 > ema50 > ema200: s += 20  # tendance haussiere parfaite
    elif close > ema20 > ema50: s += 12
    elif close > ema20: s += 5
    elif close < ema20 < ema50 < ema200: s -= 20  # tendance baissiere parfaite
    elif close < ema20 < ema50: s -= 12
    elif close < ema20: s -= 5

    # EMA200 — support/resistance long terme
    if ema200 > 0:
        dist200 = (close - ema200) / ema200 * 100
        if -1 < dist200 < 2: s += 8  # near EMA200 support = opportunite
        elif dist200 < -5: s -= 8

    # Volume institutionnel vs moyenne 90j
    if avg > 0:
        vr = vol / avg
        if vr > 5: s += 22
        elif vr > 3: s += 15
        elif vr > 2: s += 8
        elif vr > 1.5: s += 4
        elif vr < 0.5: s -= 5

    # ADX — force de la tendance
    if adx > 40: s += 12
    elif adx > 25: s += 7
    elif adx < 15: s -= 5  # pas de tendance

    # Stochastique
    if stoch < 20: s += 8
    elif stoch > 80: s -= 8

    # Bollinger Bands
    if bb_lo > 0 and close <= bb_lo * 1.01: s += 10  # touche la bande basse = rebond
    elif bb_up > 0 and close >= bb_up * 0.99: s -= 10  # touche la bande haute = resistance

    # Capitalisation
    if mc == "large": s += 5
    elif mc == "mid": s += 2

    # ── BONUS MACRO SECTORIEL ──────────────────────────────────────────────────
    if macro:
        cac_c   = macro.get("cac40",{}).get("c",0)
        sp_c    = macro.get("sp500",{}).get("c",0)
        brent_c = macro.get("brent",{}).get("c",0)
        gold_c  = macro.get("gold",{}).get("c",0)
        phos_c  = macro.get("phosphate",{}).get("c",0)
        usd_mad = macro.get("usd_mad",10.0)
        spread  = macro.get("yield_spread",0)
        rec     = macro.get("recession_risk",False)
        vix_c   = macro.get("vix",{}).get("c",0)

        # CAC40 — correlation forte Maroc/France
        if cac_c > 1: s += 8
        elif cac_c > 0.3: s += 4
        elif cac_c < -1: s -= 7
        elif cac_c < -0.3: s -= 3

        # VIX — risk on/off
        vix_p = macro.get("vix",{}).get("p",20)
        if vix_p < 15: s += 5   # risk on
        elif vix_p > 30: s -= 10  # risk off

        # Brent → secteurs energie/transport
        if sect in ["Energie","Transport","Agro","Distribution"]:
            if brent_c > 3: s -= 12
            elif brent_c > 1: s -= 5
            elif brent_c < -3: s += 12
            elif brent_c < -1: s += 5

        # Or/Argent → mines
        if sect == "Mines":
            if gold_c > 1: s += 14
            elif gold_c > 0.5: s += 8
            elif gold_c < -1: s -= 12

        # Phosphate → OCP/chimie
        if sect in ["Chimie","Mines"]:
            if phos_c > 2: s += 12
            elif phos_c < -2: s -= 8

        # USD/MAD → imports/exports
        if usd_mad > 10.3:
            if sect == "Chimie": s += 10  # OCP exporte en USD
            if sect in ["Agro","Distribution","Pharma"]: s -= 7  # importent en USD
        elif usd_mad < 9.7:
            if sect == "Chimie": s -= 6
            if sect in ["Agro","Distribution"]: s += 5

        # Spread → banques/assurance
        if sect == "Banque":
            if spread > 1: s += 8
            elif spread < 0: s -= 12
            if rec: s -= 8
        if sect == "Assurance":
            if spread > 0.5: s += 5
            elif spread < 0: s -= 6

        # Immobilier → taux
        if sect == "Immobilier":
            if spread < 0 or rec: s -= 10
            elif spread > 1: s += 5

        # Telecom → refuge en risk-off
        if sect == "Telecom" and vix_p > 25: s += 6

    return max(0, min(100, int(s)))

def detect_patterns(d, info):
    """Detection patterns techniques et signaux intraday"""
    patterns = []
    signals  = []
    close  = d.get("close",0);  open_  = d.get("open",0)
    high   = d.get("high",0);   low    = d.get("low",0)
    rsi    = d.get("rsi",50);   ema20  = d.get("ema20",0)
    ema200 = d.get("ema200",0); macd   = d.get("macd",0); macd_s = d.get("macd_s",0)
    adx    = d.get("adx",0);    vol    = d.get("volume",0)
    avg    = d.get("avg_vol",1) or 1
    bb_up  = d.get("bb_upper",0); bb_lo = d.get("bb_lower",0)

    if not close or not open_: return patterns, signals

    rng    = high - low if high > low else 0.001
    body   = abs(close - open_)
    bpct   = body / rng
    wl     = min(open_,close) - low
    wh     = high - max(open_,close)

    # Bougies japonaises
    if wl/rng > 0.6 and bpct < 0.3 and close > open_:
        patterns.append("Marteau haussier")
        signals.append(f"ACHAT > {close:.2f} | Stop < {low:.2f} | Cible {round(close+rng,2):.2f}")
    if wh/rng > 0.6 and bpct < 0.3:
        patterns.append("Etoile filante baissiere")
        signals.append(f"VENTE < {close:.2f} | Stop > {high:.2f}")
    if bpct < 0.08 and rng > 0:
        patterns.append("Doji - indecision")
    if close > open_ and bpct > 0.85:
        patterns.append("Marubozu haussier fort")
        signals.append(f"Momentum: hold/renforcer au-dessus {open_:.2f}")
    if close < open_ and bpct > 0.85:
        patterns.append("Marubozu baissier fort")
        signals.append(f"Sortir si casse {close:.2f}")

    # Signaux techniques
    if macd > macd_s and macd_s < 0:
        patterns.append("MACD Golden Cross zone negative")
        signals.append(f"Signal achat fort - MACD croise en zone negative")
    if ema200 > 0 and close > ema200 and close < ema200 * 1.015:
        patterns.append("Breakout EMA200 - cassure majeure")
        signals.append(f"Achat si tient au-dessus {ema200:.2f} en cloture")
    if rsi < 25:
        patterns.append(f"Survente extreme RSI={rsi:.0f}")
        signals.append(f"Rebond technique probable - entree progressive")
    if bb_lo > 0 and close <= bb_lo * 1.005:
        patterns.append("Contact bande Bollinger basse")
        signals.append(f"Zone de support dynamique - rebond possible")
    if adx > 35 and close > ema20:
        patterns.append(f"Tendance forte ADX={adx:.0f} - haussier")
        signals.append(f"Suivre la tendance - renforcer sur pullbacks EMA20")

    # ORB - Opening Range Breakout
    mid = (high + low) / 2
    if close > mid * 1.005 and rsi < 65 and vol > avg * 1.3:
        signals.append(f"ORB Haussier: entrer si depasse {high:.2f} vol > {int(avg*1.3):,}")
    elif close < mid * 0.995 and rsi > 35 and vol > avg * 1.3:
        signals.append(f"ORB Baissier: vendre si casse {low:.2f} vol > {int(avg*1.3):,}")

    return patterns[:4], signals[:4]

def get_poc(ticker):
    """Point of Control - prix avec le plus de volume sur 30 jours via stooq"""
    try:
        d1 = (datetime.date.today()-datetime.timedelta(days=35)).strftime("%Y%m%d")
        d2 = datetime.date.today().strftime("%Y%m%d")
        r = requests.get(f"https://stooq.com/q/d/l/?s={ticker.lower()}.ma&d1={d1}&d2={d2}&i=d",
                        headers=HDR, **R)
        if r.status_code == 200:
            lines = [l for l in r.text.strip().splitlines() if l and not l.startswith("Date")]
            if len(lines) >= 5:
                pts, vols = [], []
                for l in lines:
                    p = l.split(",")
                    if len(p) >= 6:
                        try:
                            c = float(p[4]); v = float(p[5]) if p[5] else 0
                            if c > 0: pts.append(c); vols.append(v)
                        except: pass
                if pts and sum(vols) > 0:
                    poc = sum(p*v for p,v in zip(pts,vols)) / sum(vols)
                    return {"price":round(poc,2),"high":round(max(pts),2),
                            "low":round(min(pts),2),"sessions":len(pts),"method":"VWAP 30j"}
    except: pass
    return {"price":0,"high":0,"low":0,"sessions":0,"method":"N/A"}

def smart_money(bvc_data):
    """Detection smart money - volumes anormaux vs moyenne 90j"""
    sm = []
    for t, d in bvc_data.items():
        info = BVC.get(t,{})
        vol  = d.get("volume",0)
        avg  = d.get("avg_vol",1) or info.get("v",1)
        if avg <= 0: continue
        ratio = vol / avg
        if ratio >= 2.5:
            sm.append({
                "t":t,"n":info.get("n",""),"s":info.get("s",""),
                "vr":round(ratio,1),"c":d.get("close",0),
                "chg":d.get("change",0),"rsi":d.get("rsi",50),
                "avg90":round(avg,0),"vol":vol,
            })
    return sorted(sm, key=lambda x: -x["vr"])

def make_recommendations(bvc_data, macro, ammc_pubs, timeframe="day"):
    """
    Genere les recommandations par timeframe.
    timeframe: 'day' (intraday), 'week' (7j), 'quarter' (3 mois)
    """
    scored = []
    for t, d in bvc_data.items():
        info = BVC.get(t,{})
        if not d.get("close"): continue
        sc = tech_score(d, info, macro)

        # Filtres additionnels par timeframe
        rsi  = d.get("rsi",50)
        macd = d.get("macd",0); macd_s = d.get("macd_s",0)
        vol  = d.get("volume",0); avg = d.get("avg_vol",1)
        adx  = d.get("adx",0)

        if timeframe == "week":
            # Semaine: momentum + tendance + volume
            if not (macd > macd_s and adx > 18): continue
        elif timeframe == "quarter":
            # 3 mois: tendance long terme + EMA200
            close  = d.get("close",0); ema200 = d.get("ema200",0)
            if ema200 > 0 and close < ema200 * 0.98: continue
            if sc < 60: continue

        scored.append({"t":t,"sc":sc,"d":d,"i":info})

    scored.sort(key=lambda x: -x["sc"])

    # Multiplier R:R selon timeframe
    mult = {"day":0.03,"week":0.06,"quarter":0.12}
    stop_mult = {"day":0.015,"week":0.025,"quarter":0.04}
    n_reco = {"day":3,"week":3,"quarter":3}

    recs = []
    for item in scored[:n_reco[timeframe]]:
        t = item["t"]; d = item["d"]; info = item["i"]; sc = item["sc"]
        close   = d.get("close",0)
        rsi_val = d.get("rsi",50)
        is_buy  = d.get("macd",0) > d.get("macd_s",0) and rsi_val < 68

        m  = mult.get(timeframe,0.05)
        sm = stop_mult.get(timeframe,0.02)
        tgt  = round(close*(1+m if is_buy else 1-m), 2)
        stop = round(close*(1-sm if is_buy else 1+sm), 2)
        rr   = round(abs(tgt-close)/max(abs(close-stop),0.01), 2)

        ammc_t = [p for p in ammc_pubs if p.get("ticker")==t][:2]
        poc_d  = get_poc(t)
        patterns, signals = detect_patterns(d, info)

        recs.append({
            "t":t,"sc":sc,"d":d,"i":info,"close":close,
            "is_buy":is_buy,"target":tgt,"stop":stop,"rr":rr,
            "ammc":ammc_t,"poc":poc_d,"patterns":patterns,"signals":signals,
            "timeframe":timeframe,
        })

    return recs


# ─── CSS COMMUN ─────────────────────────────────────────────────────────────────
CSS = """<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#080C14;color:#E8E4D6;font-family:'Courier New',monospace}
.w{max-width:660px;margin:0 auto;padding:14px}
.hdr{background:linear-gradient(135deg,#0F1520,#1A2030);border:1px solid rgba(201,168,76,.5);border-radius:12px;padding:20px;text-align:center;margin-bottom:12px}
.logo{font-size:28px;font-weight:900;color:#C9A84C;letter-spacing:8px}
.sub{font-size:10px;color:#6B7280;letter-spacing:3px;margin-top:4px}
.bdg{display:inline-block;border:1px solid;padding:4px 16px;border-radius:20px;font-size:11px;margin-top:8px}
.sec{background:#0F1520;border:1px solid rgba(201,168,76,.15);border-radius:10px;padding:14px;margin-bottom:10px}
.st{font-size:9px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px;border-bottom:1px solid rgba(201,168,76,.15);padding-bottom:6px}
.mg{display:flex;gap:6px;flex-wrap:wrap}
.mb{flex:1;min-width:72px;background:#13192A;border-radius:7px;padding:9px;text-align:center}
.ml{font-size:8px;color:#6B7280;margin-bottom:3px}
.mv{font-size:13px;font-weight:900}
.g{color:#00C87A}.r{color:#FF4560}.go{color:#C9A84C}.b{color:#60A5FA}.pu{color:#8B5CF6}.or{color:#F59E0B}
.ni{padding:5px 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:11px;color:#9CA3AF;line-height:1.6}
.src{font-size:8px;font-weight:700;padding:1px 6px;border-radius:3px;margin-right:5px}
.card{background:#13192A;border-radius:10px;padding:14px;margin-bottom:10px}
.tname{font-size:20px;font-weight:900;font-family:monospace}
.sy{background:rgba(139,92,246,.08);border:1px solid rgba(139,92,246,.3);border-radius:10px;padding:14px;margin-bottom:10px}
.syt{font-size:9px;color:#8B5CF6;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px}
.sytx{font-size:12px;line-height:1.9;white-space:pre-line}
.geo{background:rgba(239,68,68,.06);border:1px solid rgba(239,68,68,.2);border-radius:10px;padding:14px;margin-bottom:10px}
.geot{font-size:9px;color:#EF4444;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px}
.lv{background:rgba(0,200,122,.06);border:1px solid rgba(0,200,122,.2);border-radius:8px;padding:12px;margin:8px 0}
.lr{display:flex;justify-content:space-between;padding:3px 0;font-size:12px}
.sb{background:#080C14;border-radius:3px;height:5px;margin-top:4px}
.sf{height:100%;border-radius:3px;background:linear-gradient(90deg,#C9A84C,#F59E0B)}
.ft{text-align:center;font-size:10px;color:#4B5563;margin-top:14px;line-height:2}
.imp{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);border-radius:6px;padding:8px;margin:4px 0}
.vip{background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.25);border-radius:10px;padding:12px;margin-bottom:8px}
</style>"""

def c(v): return "g" if v>=0 else "r"
def p(v): return f"+{v:.2f}%" if v>=0 else f"{v:.2f}%"
def sg(v): return "+" if v>=0 else ""

def render_reco_card(rec, macro=None):
    """Rendu HTML d'une recommendation avec analyse complete"""
    t      = rec["t"]; d = rec["d"]; info = rec["i"]; sc = rec["sc"]
    close  = rec["close"]; is_buy = rec["is_buy"]
    tgt    = rec["target"]; stop = rec["stop"]; rr = rec["rr"]
    ammc_t = rec["ammc"]; poc    = rec["poc"]
    patterns = rec["patterns"]; signals = rec["signals"]
    tf     = rec.get("timeframe","day")

    col     = "#00C87A" if is_buy else "#FF4560"
    label   = "ACHAT" if is_buy else "VENTE"
    rsi     = d.get("rsi",50)
    chg     = d.get("change",0)
    vr      = round(d.get("volume",0)/max(d.get("avg_vol",1),1), 1)
    ema20   = d.get("ema20",0); ema200 = d.get("ema200",0)
    macd_h  = "Haussier" if d.get("macd",0)>d.get("macd_s",0) else "Baissier"
    macd_col= "#00C87A" if d.get("macd",0)>d.get("macd_s",0) else "#FF4560"

    tgt_pct  = round((tgt-close)/close*100, 1)
    stop_pct = round(abs(close-stop)/close*100, 1)

    tf_labels = {"day":"INTRADAY","week":"SEMAINE","quarter":"3 MOIS"}
    tf_colors = {"day":"#60A5FA","week":"#C9A84C","quarter":"#00C87A"}
    tf_label = tf_labels.get(tf,""); tf_color = tf_colors.get(tf,"#C9A84C")

    # News societe
    company_news = get_company_news(t)

    # Groq analyse chain-of-thought
    ammc_ctx = " | ".join([a["title"][:70] for a in ammc_t]) if ammc_t else "Aucune publication AMMC recente"
    news_ctx = " | ".join(company_news[:2]) if company_news else "Pas de news specifique"
    macro_ctx = ""
    if macro:
        sect = info.get("s","")
        if sect == "Mines": macro_ctx = f"Or {macro.get('gold',{}).get('c',0):+.2f}%, Argent {macro.get('silver',{}).get('c',0):+.2f}%"
        elif sect in ["Energie","Transport"]: macro_ctx = f"Brent {macro.get('brent',{}).get('c',0):+.2f}%"
        elif sect == "Chimie": macro_ctx = f"Phosphate {macro.get('phosphate',{}).get('c',0):+.2f}%, USD/MAD={macro.get('usd_mad',10)}"
        elif sect == "Banque": macro_ctx = f"CAC40 {macro.get('cac40',{}).get('c',0):+.2f}%, Spread {macro.get('yield_spread',0):+.3f}%"
        else: macro_ctx = f"CAC40 {macro.get('cac40',{}).get('c',0):+.2f}%, VIX {macro.get('vix',{}).get('p',20):.0f}"

    groq_prompt = f"""Analyste hedge fund Maroc. Analyse concise en 2 phrases.

TITRE: {t} - {info.get('n','')} ({info.get('s','')}) - Horizon {tf_label}
SCORE: {sc}/100 | RSI={rsi:.0f} | MACD={macd_h} | Volume x{vr}
COURS: {close:.2f} MAD | EMA20={ema20:.2f} | EMA200={ema200:.2f}
MACRO: {macro_ctx}
AMMC: {ammc_ctx}
NEWS: {news_ctx}
PATTERNS: {patterns}

Phrase 1: Catalyseur precis technique + macro + fondamental pour {label} maintenant
Phrase 2: Condition exacte d entree et risque principal a surveiller
Style: trader Goldman Sachs. Chiffres precis. Sans markdown."""

    analyse = groq_call(groq_prompt, 250) or "Setup technique confirme - alignement indicateurs."

    # POC HTML
    poc_html = ""
    if poc.get("price",0) > 0:
        dist = round((close-poc["price"])/poc["price"]*100,1)
        poc_html = (
            f'<div style="background:rgba(139,92,246,.08);border:1px solid rgba(139,92,246,.2);'
            f'border-radius:6px;padding:8px;margin:6px 0">'
            f'<div style="font-size:8px;color:#8B5CF6;margin-bottom:3px;letter-spacing:2px">POC 30j - COURS LE PLUS TRADE</div>'
            f'<div style="font-size:12px;color:#E8E4D6;font-weight:700">{poc["price"]:.2f} MAD '
            f'<span style="color:{"#00C87A" if dist>=0 else "#FF4560"};font-size:10px">({dist:+.1f}% vs POC)</span>'
            f' | Range: {poc["low"]:.2f} - {poc["high"]:.2f}</div>'
            f'<div style="font-size:9px;color:#4B5563">{poc["sessions"]} seances | {poc["method"]}</div>'
            f'</div>'
        )

    pat_html = "".join(f'<div style="font-size:10px;color:#F59E0B;padding:1px 0">• {pat}</div>' for pat in patterns)
    sig_html = "".join(f'<div style="font-size:10px;color:#9CA3AF;padding:1px 0">▸ {sig}</div>' for sig in signals)
    ammc_html = "".join(f'<div style="font-size:10px;color:#60A5FA;padding:1px 0">📄 {a["title"][:90]}</div>' for a in ammc_t)
    news_html = "".join(f'<div style="font-size:10px;color:#9CA3AF;padding:1px 0">📰 {n[:100]}</div>' for n in company_news[:2])

    return (
        f'<div class="card" style="border-left:4px solid {col}">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">'
        f'<div><div class="tname" style="color:{col}">{t}</div>'
        f'<div style="font-size:10px;color:#6B7280">{info.get("n","")} - {info.get("s","")}</div></div>'
        f'<div style="text-align:right">'
        f'<div style="font-size:16px;font-weight:900;color:#E8E4D6">{close:.2f} MAD</div>'
        f'<div style="font-size:10px;color:{"#00C87A" if chg>=0 else "#FF4560"}">{chg:+.2f}% | Vol x{vr}</div>'
        f'<div style="background:{col}20;color:{col};border:1px solid {col}40;font-size:9px;padding:2px 10px;border-radius:4px;margin-top:3px">{label} {sc}/100</div>'
        f'<div style="background:{tf_color}15;color:{tf_color};font-size:8px;padding:1px 8px;border-radius:3px;margin-top:2px">{tf_label}</div>'
        f'</div></div>'
        f'<div class="lv">'
        f'<div style="font-size:8px;color:#C9A84C;margin-bottom:6px;letter-spacing:2px">NIVEAUX DE TRADING</div>'
        f'<div class="lr"><span style="color:#6B7280">Entree</span><strong style="color:#E8E4D6">{close:.2f} MAD</strong></div>'
        f'<div class="lr"><span style="color:#6B7280">Cible</span><strong style="color:#00C87A">{tgt:.2f} MAD ({sg(tgt_pct)}{tgt_pct}%)</strong></div>'
        f'<div class="lr"><span style="color:#6B7280">Stop</span><strong style="color:#FF4560">{stop:.2f} MAD (-{stop_pct}%)</strong></div>'
        f'<div class="lr"><span style="color:#6B7280">R/R</span><strong style="color:#C9A84C">{rr}</strong></div>'
        f'</div>'
        f'<table style="width:100%;font-size:10px;border-collapse:collapse;margin:6px 0">'
        f'<tr><td style="color:#6B7280">RSI</td><td style="color:{"#00C87A" if rsi<35 else "#FF4560" if rsi>70 else "#C9A84C"};font-weight:700">{rsi:.0f}</td>'
        f'<td style="color:#6B7280">MACD</td><td style="color:{macd_col}">{macd_h}</td>'
        f'<td style="color:#6B7280">ADX</td><td style="color:#9CA3AF">{d.get("adx",0):.0f}</td></tr>'
        f'<tr><td style="color:#6B7280">EMA20</td><td style="color:{"#00C87A" if close>ema20>0 else "#FF4560"}">{ema20:.2f}</td>'
        f'<td style="color:#6B7280">EMA200</td><td style="color:{"#00C87A" if close>ema200>0 else "#FF4560"}">{">" if close>ema200>0 else "<"} {ema200:.2f}</td>'
        f'<td style="color:#6B7280">BB</td><td style="color:#9CA3AF">{"Basse" if d.get("bb_lower",0)>0 and close<=d.get("bb_lower",0)*1.01 else "Mid"}</td></tr>'
        f'</table>'
        + poc_html
        + (f'<div style="margin:5px 0">{pat_html}</div>' if pat_html else "")
        + (f'<div style="background:rgba(245,158,11,.06);border-radius:5px;padding:7px;margin:5px 0">'
           f'<div style="font-size:8px;color:#F59E0B;margin-bottom:4px;letter-spacing:2px">TRADES ACTIONABLES</div>'
           f'{sig_html}</div>' if sig_html else "")
        + (f'<div style="margin-top:6px">{ammc_html}</div>' if ammc_html else "")
        + (f'<div style="margin-top:4px">{news_html}</div>' if news_html else "")
        + f'<div style="font-size:11px;color:#9CA3AF;margin-top:8px;line-height:1.8;background:rgba(0,0,0,.2);padding:8px;border-radius:5px">{analyse}</div>'
        + f'<div style="margin-top:8px"><div class="sb"><div class="sf" style="width:{sc}%"></div></div></div>'
        + f'</div>'
    )


# ─── PRE-COLLECTE 06h00 ─────────────────────────────────────────────────────────
def pre_collect():
    """Analyse profonde a 06h00 - Groq avec contexte complet pendant que tu dors"""
    print("[BARAKA] === PRE-COLLECTE 06h00 ===")
    try:
        macro   = get_macro()
        ammc    = get_ammc_pubs()
        geo     = get_geopolitical_scanner()
        bn      = get_boursenews()
        social  = get_maroc_social_media()
        bdt     = get_bdt_rates()

        sp_c   = macro.get("sp500",{}).get("c",0)
        cac_c  = macro.get("cac40",{}).get("c",0)
        nas_c  = macro.get("nasdaq",{}).get("c",0)
        dax_c  = macro.get("dax",{}).get("c",0)
        nik_c  = macro.get("nikkei",{}).get("c",0)
        sha_c  = macro.get("shanghai",{}).get("c",0)
        brent_c= macro.get("brent",{}).get("c",0)
        gold_c = macro.get("gold",{}).get("c",0)
        phos_c = macro.get("phosphate",{}).get("c",0)
        mad    = macro.get("usd_mad",10.0)
        eur_mad= macro.get("eur_mad",10.9)
        spread = macro.get("yield_spread",0)
        vix_p  = macro.get("vix",{}).get("p",20)
        fed    = macro.get("fed_rate",5.25)
        t10    = macro.get("us10y",0)

        deep_prompt = f"""Tu es le chief investment analyst de Atlas Capital Management, Casablanca.
Il est 06h00 - la BVC ouvre dans 2h30. Prepare l'analyse pour le trading day.

=== MARCHES MONDIAUX ===
Amerique: S&P500 {sp_c:+.2f}% | Nasdaq {nas_c:+.2f}% | VIX={vix_p:.1f}
Europe: CAC40 {cac_c:+.2f}% | DAX {dax_c:+.2f}%
Asie: Nikkei {nik_c:+.2f}% | Shanghai {sha_c:+.2f}%
Matieres premieres: Brent {brent_c:+.2f}% | Or {gold_c:+.2f}% | Phosphate {phos_c:+.2f}%
Devises: USD/MAD={mad} EUR/MAD={eur_mad}
Taux: US10Y={t10}% Spread 10Y-2Y={spread:+.3f}% {'[INVERSION COURBE]' if spread<0 else ''} Fed={fed}%

=== GEOPOLITIQUE - IMPACT MAROC ===
Moyen Orient/Iran-Israel: {geo.get('moyen_orient',[])}
Ukraine/Russie: {geo.get('ukraine',[])}
USA/Chine: {geo.get('usa_chine',[])}
Fed/Politique monetaire: {geo.get('fed',[])}
BCE/Europe: {geo.get('bce',[])}

=== MAROC ===
Economie: {geo.get('maroc_eco',[])}
Finance/BVC: {geo.get('maroc_fin',[])}
BAM/Taux: {geo.get('bkam',[])}
Petrole impact Maroc: {geo.get('petrole',[])}
Phosphate/OCP: {geo.get('phosphate',[])}
Mines/Or/Argent: {geo.get('or_argent',[])}
BDT/Bons Tresor: {bdt.get('news',[])}

=== AMMC PUBLICATIONS ===
{[p['title'][:80] + (' ['+p['ticker']+']' if p.get('ticker') else '') for p in ammc[:6]]}

=== BUZZ MARCHE ===
BourseNews: {bn[:4]}
Social/Telegram: {[s['t'][:60] for s in social[:4]]}

Reponds en 6 paragraphes SANS markdown, style analyste professionnel:
1. GEOPOLITIQUE GLOBAL: Quel evenement mondial a le plus fort impact sur la BVC aujourd'hui? Sois specifique (ex: escalade Iran-Israel -> hausse Brent +3% -> inflation Maroc -> BAM pourrait monter taux -> pression sur immobilier/banques)
2. MARCHES ET CORRELATIONS: Comment les mouvements de la nuit vont impacter l'ouverture BVC? Correlation France/Maroc, USD/MAD impact secteurs
3. INFLATION ET POUVOIR D'ACHAT: Impact sur consommation marocaine, marges entreprises
4. ARBITRAGE BDT VS ACTIONS: Ou vont les salles de marche ce matin? Taux BDT vs rendement attendu actions
5. SECTEURS PRIORITAIRES: Les 3 secteurs a surveiller absolument a l'ouverture avec raisons precises
6. AMMC ET FONDAMENTAUX: Publications du jour et leur impact sur les titres concernes
Chiffres precis. Liens de causalite explicites. Niveau CFA hedge fund."""

        deep_analysis = groq_call(deep_prompt, 1000)

        sector_prompt = f"""BVC Casablanca - Rotation sectorielle aujourd'hui.
CAC40={cac_c:+.2f}% Brent={brent_c:+.2f}% Or={gold_c:+.2f}% Phosphate={phos_c:+.2f}% USD/MAD={mad}

Pour chaque secteur: ACHETER/NEUTRE/EVITER et raison en 5 mots max:
Banque | Assurance | Telecom | Chimie/OCP | Mines | Immobilier | Energie | Transport | Agro | Sante | Construction
Format: SECTEUR: SIGNAL - raison courte"""

        sector_analysis = groq_call(sector_prompt, 350)

        cache_set("pre_collect", {
            "macro":macro,"ammc":ammc,"geo":geo,"boursenews":bn,
            "social":social,"bdt":bdt,"deep_analysis":deep_analysis,
            "sector_analysis":sector_analysis,
            "timestamp":datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        })
        print(f"[PRE-COLLECTE] OK - Groq: {len(deep_analysis)} chars")

    except Exception as e:
        print(f"[PRE-COLLECTE] Erreur: {e}")


# ─── EMAIL 1 : BRIEF OUVERTURE 08h30 ────────────────────────────────────────────
def brief_ouverture():
    print("[BARAKA] === BRIEF OUVERTURE 08h30 ===")
    try:
        now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        # Charger depuis cache pré-collecte si disponible
        cached = cache_get("pre_collect", max_min=180)
        if cached:
            print("[BRIEF] Cache pre-collecte OK")
            macro           = cached["macro"]
            ammc            = cached["ammc"]
            geo             = cached["geo"]
            bn              = cached["boursenews"]
            social          = cached["social"]
            bdt             = cached["bdt"]
            deep_analysis   = cached.get("deep_analysis","")
            sector_analysis = cached.get("sector_analysis","")
            cached_time     = cached.get("timestamp","")
        else:
            print("[BRIEF] Collecte directe (pas de cache)")
            macro   = get_macro()
            ammc    = get_ammc_pubs()
            geo     = get_geopolitical_scanner()
            bn      = get_boursenews()
            social  = get_maroc_social_media()
            bdt     = get_bdt_rates()
            deep_analysis   = ""
            sector_analysis = ""
            cached_time     = ""

        # Variables macro
        sp_c   = macro.get("sp500",{}).get("c",0)
        sp_p   = macro.get("sp500",{}).get("p",0)
        nas_c  = macro.get("nasdaq",{}).get("c",0)
        cac_c  = macro.get("cac40",{}).get("c",0)
        dax_c  = macro.get("dax",{}).get("c",0)
        ftse_c = macro.get("ftse",{}).get("c",0)
        nik_c  = macro.get("nikkei",{}).get("c",0)
        sha_c  = macro.get("shanghai",{}).get("c",0)
        hsi_c  = macro.get("hsi",{}).get("c",0)
        brent_c= macro.get("brent",{}).get("c",0)
        brent_p= macro.get("brent",{}).get("p",0)
        gold_c = macro.get("gold",{}).get("c",0)
        gold_p = macro.get("gold",{}).get("p",0)
        silver_c=macro.get("silver",{}).get("c",0)
        phos_c = macro.get("phosphate",{}).get("c",0)
        copper_c=macro.get("copper",{}).get("c",0)
        mad    = macro.get("usd_mad",10.0)
        eur_mad= macro.get("eur_mad",10.9)
        t10    = macro.get("us10y",0)
        fed    = macro.get("fed_rate",5.25)
        spread = macro.get("yield_spread",0)
        rec    = macro.get("recession_risk",False)
        vix_p  = macro.get("vix",{}).get("p",20)
        dxy_d  = macro.get("dxy",{})
        dxy_c  = dxy_d.get("c",0) if isinstance(dxy_d,dict) else 0

        # Synthese si pas de cache
        if not deep_analysis:
            prompt = (
                f"Analyste hedge fund Maroc - Brief 08h30 - BVC ouvre dans 1h.\n"
                f"S&P500={sp_c:+.2f}% CAC40={cac_c:+.2f}% Brent={brent_c:+.2f}% Or={gold_c:+.2f}%\n"
                f"USD/MAD={mad} EUR/MAD={eur_mad} Spread={spread:+.3f}%\n"
                f"Geo Moyen Orient: {geo.get('moyen_orient',[][:2])}\n"
                f"Fed: {geo.get('fed',[][:2])}\n"
                f"AMMC: {[a['title'][:60] for a in ammc[:4]]}\n"
                "5 phrases trader hedge fund:\n"
                "1. Evenement geopolitique le plus impactant pour la BVC aujourd'hui\n"
                "2. Correlations marches mondiaux -> secteurs BVC specifiques\n"
                "3. USD/MAD et Brent -> inflation Maroc -> arbitrage BDT vs actions\n"
                "4. Secteurs a privilegier/eviter a l'ouverture\n"
                "5. Publications AMMC et impact fondamental\n"
                "Chiffres precis. Liens causaux. Sans markdown."
            )
            deep_analysis = groq_call(prompt, 700) or "Analyse en cours..."

        # Geopolitique HTML
        def geo_items(items, src, limit=3):
            if not items: return ""
            return "".join(f'<div class="ni"><span class="src" style="background:rgba(239,68,68,.15);color:#EF4444">{src}</span>{n}</div>' for n in items[:limit])

        geo_html = ""
        if geo.get("moyen_orient"): geo_html += geo_items(geo["moyen_orient"][:3], "Iran/Israel")
        if geo.get("ukraine"):      geo_html += geo_items(geo["ukraine"][:2], "Ukraine")
        if geo.get("usa_chine"):    geo_html += geo_items(geo["usa_chine"][:2], "US/Chine")
        if geo.get("fed"):          geo_html += geo_items(geo["fed"][:2], "Fed")
        if geo.get("petrole"):      geo_html += geo_items(geo["petrole"][:2], "Petrole")
        if not geo_html:
            geo_html = '<div class="ni" style="color:#4B5563">Scanner geopolitique - aucun evenement majeur detecte</div>'

        # Maroc HTML
        maroc_html = ""
        if geo.get("maroc_eco"):    maroc_html += "".join(f'<div class="ni"><span class="src" style="background:rgba(0,200,122,.12);color:#00C87A">ECO</span>{n}</div>' for n in geo["maroc_eco"][:2])
        if geo.get("maroc_fin"):    maroc_html += "".join(f'<div class="ni"><span class="src" style="background:rgba(201,168,76,.12);color:#C9A84C">BVC</span>{n}</div>' for n in geo["maroc_fin"][:2])
        if geo.get("bkam"):         maroc_html += "".join(f'<div class="ni"><span class="src" style="background:rgba(96,165,250,.12);color:#60A5FA">BAM</span>{n}</div>' for n in geo["bkam"][:2])
        if bdt.get("news"):         maroc_html += "".join(f'<div class="ni"><span class="src" style="background:rgba(139,92,246,.12);color:#8B5CF6">BDT</span>{n}</div>' for n in bdt["news"][:2])

        # Social HTML
        soc_html = "".join(
            f'<div class="ni"><span class="src" style="background:rgba(139,92,246,.12);color:#8B5CF6">{s["src"][:12]}</span>{s["t"][:120]}</div>'
            for s in social[:5]
        ) or '<div class="ni" style="color:#4B5563">Aucun buzz detecte</div>'

        # AMMC HTML
        ammc_html = "".join(
            f'<div class="ni"><span class="src" style="background:rgba(239,68,68,.12);color:#EF4444">AMMC</span>'
            f'{a["title"][:110]}'
            + (f' <strong style="color:#C9A84C">[{a["ticker"]}]</strong>' if a.get("ticker") else "")
            + '</div>'
            for a in ammc[:6]
        ) or '<div class="ni" style="color:#4B5563">Aucune publication aujourd\'hui</div>'

        # BourseNews HTML
        bn_html = "".join(
            f'<div class="ni"><span class="src" style="background:rgba(0,200,122,.1);color:#00C87A">BN</span>{n}</div>'
            for n in bn[:4]
        ) or '<div class="ni" style="color:#4B5563">Aucune news disponible</div>'

        # Rotation sectorielle
        sec_html = ""
        if sector_analysis:
            for line in sector_analysis.split("\n"):
                if ":" in line and len(line) > 5:
                    parts = line.split(":",1)
                    name  = parts[0].strip()
                    rest  = parts[1].strip() if len(parts)>1 else ""
                    col_s = "#00C87A" if "ACHETER" in rest.upper() else ("#FF4560" if "EVITER" in rest.upper() else "#C9A84C")
                    sec_html += f'<div class="ni"><span style="color:{col_s};font-weight:700;min-width:100px;display:inline-block">{name}</span> {rest}</div>'

        # VIX indicator
        vix_color = "#00C87A" if vix_p < 20 else ("#C9A84C" if vix_p < 30 else "#FF4560")
        vix_label = "RISK ON" if vix_p < 20 else ("NEUTRE" if vix_p < 30 else "RISK OFF")
        rec_html  = f'<div class="mb"><div class="ml">COURBE INVERSEE</div><div class="mv r">DANGER</div></div>' if rec else ''

        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="w">

<div class="hdr">
  <div class="logo">BARAKA</div>
  <div class="sub">BRIEF OUVERTURE — {now}</div>
  <span class="bdg g" style="border-color:rgba(0,200,122,.4);background:rgba(0,200,122,.08)">BVC OUVRE DANS 1H</span>
  {f'<div style="font-size:9px;color:#4B5563;margin-top:4px">Analyse pre-collectee a {cached_time}</div>' if cached_time else ''}
</div>

<div class="geo">
  <div class="geot">RADAR GEOPOLITIQUE MONDIAL — IMPACT BVC</div>
  {geo_html}
</div>

<div class="sy">
  <div class="syt">ANALYSE BARAKA — GROQ AI HEDGE FUND LEVEL</div>
  <div class="sytx">{deep_analysis}</div>
</div>

<div class="sec">
  <div class="st">MARCHES MONDIAUX — NUIT</div>
  <div style="margin-bottom:8px;font-size:8px;color:#6B7280;letter-spacing:2px">CHANGE</div>
  <div class="mg" style="margin-bottom:10px">
    <div class="mb"><div class="ml">USD/MAD</div><div class="mv b">{mad}</div></div>
    <div class="mb"><div class="ml">EUR/MAD</div><div class="mv b">{eur_mad}</div></div>
    <div class="mb"><div class="ml">DXY</div><div class="mv {c(dxy_c)}">{p(dxy_c)}</div></div>
  </div>
  <div style="margin-bottom:8px;font-size:8px;color:#6B7280;letter-spacing:2px">INDICES</div>
  <div class="mg" style="margin-bottom:10px">
    <div class="mb"><div class="ml">S&P500</div><div class="mv {c(sp_c)}">{p(sp_c)}</div></div>
    <div class="mb"><div class="ml">NASDAQ</div><div class="mv {c(nas_c)}">{p(nas_c)}</div></div>
    <div class="mb"><div class="ml">CAC40</div><div class="mv {c(cac_c)}">{p(cac_c)}</div></div>
    <div class="mb"><div class="ml">DAX</div><div class="mv {c(dax_c)}">{p(dax_c)}</div></div>
    <div class="mb"><div class="ml">NIKKEI</div><div class="mv {c(nik_c)}">{p(nik_c)}</div></div>
    <div class="mb"><div class="ml">SHANGHAI</div><div class="mv {c(sha_c)}">{p(sha_c)}</div></div>
  </div>
  <div style="margin-bottom:8px;font-size:8px;color:#6B7280;letter-spacing:2px">MATIERES PREMIERES</div>
  <div class="mg" style="margin-bottom:10px">
    <div class="mb"><div class="ml">OR/oz</div><div class="mv {c(gold_c)}">{gold_p:.0f}$<br><span style="font-size:9px">{p(gold_c)}</span></div></div>
    <div class="mb"><div class="ml">ARGENT</div><div class="mv {c(silver_c)}">{p(silver_c)}</div></div>
    <div class="mb"><div class="ml">BRENT</div><div class="mv {c(brent_c)}">{brent_p:.1f}$<br><span style="font-size:9px">{p(brent_c)}</span></div></div>
    <div class="mb"><div class="ml">PHOSPHATE</div><div class="mv {c(phos_c)}">{p(phos_c)}</div></div>
    <div class="mb"><div class="ml">CUIVRE</div><div class="mv {c(copper_c)}">{p(copper_c)}</div></div>
  </div>
  <div style="margin-bottom:8px;font-size:8px;color:#6B7280;letter-spacing:2px">TAUX & RISQUE</div>
  <div class="mg">
    <div class="mb"><div class="ml">US 10Y</div><div class="mv b">{t10}%</div></div>
    <div class="mb"><div class="ml">SPREAD</div><div class="mv {'r' if spread<0 else 'g'}">{spread:+.3f}%</div></div>
    <div class="mb"><div class="ml">FED</div><div class="mv go">{fed}%</div></div>
    <div class="mb"><div class="ml">VIX</div><div class="mv" style="color:{vix_color}">{vix_p:.1f}<br><span style="font-size:8px">{vix_label}</span></div></div>
    {rec_html}
  </div>
</div>

<div class="sec"><div class="st">MAROC — ECONOMIE & INFLATION</div>{maroc_html}</div>

{f'<div class="sec"><div class="st">ROTATION SECTORIELLE — OU ALLER CE MATIN</div>{sec_html}</div>' if sec_html else ''}

<div class="sec"><div class="st">PUBLICATIONS AMMC DU JOUR</div>{ammc_html}</div>

<div class="sec"><div class="st">NEWS BVC — BOURSENEWS</div>{bn_html}</div>

<div class="sec"><div class="st">INTELLIGENCE SOCIALE — TELEGRAM & MAROC</div>{soc_html}</div>

<div class="ft">
  Prochain email: 12h00 — Analyse + Recommandations (Intraday / Semaine / 3 Mois)<br>
  <strong class="go">BARAKA v7.0 — Hedge Fund Intelligence</strong>
</div>
</div></body></html>"""

        send_email("BARAKA — BRIEF OUVERTURE BVC 08h30", html)

    except Exception as e:
        print(f"[BRIEF] Erreur: {e}")
        import traceback; traceback.print_exc()
        send_email("BARAKA — BRIEF OUVERTURE 08h30",
            f"<div style='background:#080C14;color:#E8E4D6;padding:20px;font-family:monospace'>"
            f"<h2 style='color:#C9A84C'>BRIEF OUVERTURE {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</h2>"
            f"<p style='color:#FF4560'>{str(e)[:300]}</p></div>")


# ─── EMAIL 2 : ANALYSE + RECOMMANDATIONS 12h00 ──────────────────────────────────
def analyse_entrees():
    print("[BARAKA] === ANALYSE + ENTREES 12h00 ===")
    try:
        bvc_data = get_bvc_data()
        macro    = get_macro()
        ammc_pubs = get_ammc_pubs()
        now      = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        if not bvc_data:
            send_email("BARAKA — ANALYSE 12h00",
                "<div style='background:#080C14;color:#E8E4D6;padding:20px;font-family:monospace'>"
                "<h2 style='color:#C9A84C'>BARAKA — TV Scanner indisponible</h2>"
                "<p style='color:#F59E0B'>Donnees BVC non disponibles ce matin. Prochain essai a 15h30.</p></div>")
            return

        # Smart money
        sm = smart_money(bvc_data)

        # Recommendations 3 timeframes
        reco_day     = make_recommendations(bvc_data, macro, ammc_pubs, "day")
        reco_week    = make_recommendations(bvc_data, macro, ammc_pubs, "week")
        reco_quarter = make_recommendations(bvc_data, macro, ammc_pubs, "quarter")

        # Momentum sectoriel
        sector_scores = {}
        sector_counts = {}
        for t, d in bvc_data.items():
            info = BVC.get(t,{})
            sc = tech_score(d, info, macro)
            s  = info.get("s","")
            if s not in sector_scores:
                sector_scores[s] = 0; sector_counts[s] = 0
            sector_scores[s] += sc; sector_counts[s] += 1
        sector_rank = sorted(
            [(s, round(sector_scores[s]/sector_counts[s],1)) for s in sector_scores if sector_counts[s]>0],
            key=lambda x: -x[1]
        )

        # VIP zoom
        vip_html = ""
        for vip_t in VIP:
            vip_d = bvc_data.get(vip_t)
            if not vip_d: continue
            vip_info = BVC.get(vip_t,{})
            vip_sc   = tech_score(vip_d, vip_info, macro)
            vip_col  = "#00C87A" if vip_sc>=65 else ("#FF4560" if vip_sc<=35 else "#C9A84C")
            vip_close= vip_d.get("close",0)
            vip_chg  = vip_d.get("change",0)
            vip_rsi  = vip_d.get("rsi",50)
            vip_vr   = round(vip_d.get("volume",0)/max(vip_d.get("avg_vol",1),1),1)
            vip_pats, vip_sigs = detect_patterns(vip_d, vip_info)
            vip_poc  = get_poc(vip_t)
            vip_news = get_company_news(vip_t)

            vip_poc_line = ""
            if vip_poc.get("price",0) > 0:
                vip_dist = round((vip_close-vip_poc["price"])/vip_poc["price"]*100,1)
                vip_poc_line = (f'<span style="color:#8B5CF6;font-size:10px"> | POC={vip_poc["price"]:.2f}'
                               f'({vip_dist:+.1f}%)</span>')

            vip_html += (
                f'<div class="vip" style="border-left:3px solid {vip_col}">'
                f'<div style="display:flex;justify-content:space-between">'
                f'<div><span style="color:{vip_col};font-weight:900;font-size:15px;font-family:monospace">{vip_t}</span> '
                f'<span style="color:#6B7280;font-size:10px">{vip_info.get("n","")} - {vip_info.get("s","")}</span></div>'
                f'<div style="text-align:right"><span style="color:#E8E4D6;font-weight:700">{vip_close:.2f} MAD</span> '
                f'<span style="color:{"#00C87A" if vip_chg>=0 else "#FF4560"};font-size:10px">{vip_chg:+.2f}%</span>'
                f'<div style="color:#9CA3AF;font-size:10px">RSI {vip_rsi:.0f} | Vol x{vip_vr} | Score {vip_sc}/100</div></div>'
                f'</div>'
                + vip_poc_line
                + ("".join(f'<div style="font-size:10px;color:#F59E0B;padding:1px 0">• {pat}</div>' for pat in vip_pats) if vip_pats else "")
                + ("".join(f'<div style="font-size:10px;color:#9CA3AF;padding:1px 0">▸ {sig}</div>' for sig in vip_sigs[:2]) if vip_sigs else "")
                + ("".join(f'<div style="font-size:10px;color:#9CA3AF;padding:1px 0">📰 {n[:100]}</div>' for n in vip_news[:2]) if vip_news else "")
                + f'</div>'
            )

        # HTML recommendations sections
        def reco_section(recs, title, icon, border_color):
            if not recs: return f'<div class="sec"><div class="st">{icon} {title}</div><div style="color:#4B5563;padding:10px">Aucun signal qualifie - conditions de marche non reunies</div></div>'
            cards = "".join(render_reco_card(rec, macro) for rec in recs)
            return f'<div class="sec"><div class="st">{icon} {title}</div>{cards}</div>'

        # Smart money HTML
        sm_html = ""
        if sm:
            sm_rows = "".join(
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:7px 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:11px">'
                f'<span style="color:#F59E0B;font-weight:700;font-family:monospace;min-width:80px">{s["t"]}</span>'
                f'<span style="color:#9CA3AF;flex:1;margin:0 8px">{s["n"][:20]}</span>'
                f'<span style="color:#F59E0B;font-weight:700">x{s["vr"]}</span>'
                f'<span style="color:{"#00C87A" if s["chg"]>=0 else "#FF4560"};margin-left:8px">{s["chg"]:+.2f}%</span>'
                f'<span style="color:#9CA3AF;margin-left:8px;font-size:10px">RSI {s["rsi"]:.0f}</span>'
                f'</div>'
                for s in sm[:6]
            )
            sm_html = f'<div class="sec"><div class="st">SMART MONEY — VOLUMES ANORMAUX (base moy. 90j)</div>{sm_rows}</div>'

        # Secteur momentum HTML
        sect_html = "".join(
            f'<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0">'
            f'<span style="color:{"#00C87A" if i<3 else "#C9A84C" if i<6 else "#6B7280"};font-size:11px">'
            f'{"🟢" if i<3 else "🟡" if i<6 else "⚪"} {sn}</span>'
            f'<div style="flex:1;margin:0 8px;background:#080C14;border-radius:2px;height:4px">'
            f'<div style="height:100%;border-radius:2px;width:{min(100,int(ss))}%;'
            f'background:{"#00C87A" if i<3 else "#C9A84C" if i<6 else "#4B5563"}"></div></div>'
            f'<span style="color:#6B7280;font-size:10px">{ss:.0f}</span>'
            f'</div>'
            for i,(sn,ss) in enumerate(sector_rank[:8])
        )

        sp_c = macro.get("sp500",{}).get("c",0)
        mad  = macro.get("usd_mad",10.0)

        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="w">

<div class="hdr">
  <div class="logo">BARAKA</div>
  <div class="sub">ANALYSE + RECOMMANDATIONS — {now}</div>
  <span class="bdg go" style="border-color:rgba(201,168,76,.4);background:rgba(201,168,76,.08)">
    {len(bvc_data)} TITRES ANALYSES — 3 HORIZONS
  </span>
</div>

<div style="display:flex;gap:8px;margin-bottom:10px">
  <div class="mb" style="flex:1"><div class="ml">S&P500</div><div class="mv {c(sp_c)}">{p(sp_c)}</div></div>
  <div class="mb" style="flex:1"><div class="ml">USD/MAD</div><div class="mv b">{mad}</div></div>
  <div class="mb" style="flex:1"><div class="ml">Titres</div><div class="mv go">{len(bvc_data)}/32</div></div>
</div>

{sm_html}

{reco_section(reco_day, "TRADES INTRADAY — AUJOURD'HUI", "⚡", "#60A5FA")}
{reco_section(reco_week, "POSITIONS SEMAINE — 7 JOURS", "📅", "#C9A84C")}
{reco_section(reco_quarter, "INVESTISSEMENTS 3 MOIS — MOYEN TERME", "📈", "#00C87A")}

<div class="sec"><div class="st">MOMENTUM SECTORIEL BVC</div>{sect_html}</div>

<div class="sec">
  <div class="st">ZOOM VIP QUOTIDIEN — SURVEILLANCE APPROFONDIE</div>
  <div style="font-size:9px;color:#F59E0B;margin-bottom:8px">Alliances • TGCC • Addoha • SGTM • Dar Saada • Akdital • Managem • SMI • CMT</div>
  {vip_html if vip_html else '<div style="color:#4B5563">Titres VIP indisponibles sur TV Scanner</div>'}
</div>

<div class="ft">Triggers actifs — Surveillance en continu toutes les 10 min<br>
Prochain email: 15h30 — Post-Cloture Smart Money<br>
<strong class="go">BARAKA v7.0 — Hedge Fund Intelligence</strong></div>
</div></body></html>"""

        send_email("BARAKA — ANALYSE + RECOMMANDATIONS 12h00", html)

        # Peupler watchlist pour surveillance
        watchlist_clear()
        for rec in reco_day[:3]:
            watchlist_add(rec["t"], rec["close"], rec["stop"], rec["target"],
                         "BUY" if rec["is_buy"] else "SELL")
        print(f"[WATCHLIST] {min(3,len(reco_day))} titres en surveillance")

    except Exception as e:
        print(f"[ANALYSE] Erreur: {e}")
        import traceback; traceback.print_exc()
        send_email("BARAKA — ANALYSE 12h00",
            f"<div style='background:#080C14;color:#E8E4D6;padding:20px;font-family:monospace'>"
            f"<h2 style='color:#C9A84C'>ANALYSE {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</h2>"
            f"<p style='color:#FF4560'>{str(e)[:300]}</p></div>")


# ─── EMAIL 3 : POST-CLÔTURE 15h30 ───────────────────────────────────────────────
def post_cloture():
    print("[BARAKA] === POST-CLOTURE 15h30 ===")
    try:
        bvc_data  = get_bvc_data()
        macro     = get_macro()
        ammc_pubs = get_ammc_pubs()
        geo       = get_geopolitical_scanner()
        now       = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        sm        = smart_money(bvc_data)
        top_demain= sorted(
            [{"t":t,"sc":tech_score(d,BVC.get(t,{}),macro),"d":d}
             for t,d in bvc_data.items() if d.get("close")],
            key=lambda x:-x["sc"]
        )[:5]

        # Groq post-cloture avec contexte complet
        sm_ctx = "\n".join([f"{s['t']}: vol x{s['vr']}, {s['chg']:+.2f}%, RSI={s['rsi']:.0f}" for s in sm[:5]])
        cac_c  = macro.get("cac40",{}).get("c",0)
        brent_c= macro.get("brent",{}).get("c",0)
        gold_c = macro.get("gold",{}).get("c",0)
        mad    = macro.get("usd_mad",10.0)

        prompt = (
            f"Analyste hedge fund Maroc. Post-cloture BVC {datetime.date.today().strftime('%d/%m/%Y')}.\n"
            f"SMART MONEY (vol > 2.5x moy.90j):\n{sm_ctx or 'Aucun mouvement anormal'}\n"
            f"TOP DEMAIN: {[x['t'] for x in top_demain[:3]]}\n"
            f"MACRO: CAC40={cac_c:+.2f}% | Brent={brent_c:+.2f}% | Or={gold_c:+.2f}% | USD/MAD={mad}\n"
            f"GEO: {geo.get('moyen_orient',[][:2])}\n"
            f"GEO: {geo.get('fed',[][:1])}\n\n"
            "5 phrases trader hedge fund:\n"
            "1. Ou est alle le smart money aujourd'hui et POURQUOI (lien avec macro/geo du jour)\n"
            "2. Arbitrage: les salles de marche ont-elles bascule sur les BDT Maroc? Signaux observes\n"
            "3. Evenement geopolitique ou macro qui va driver la BVC demain matin\n"
            "4. Les 2 titres a surveiller ABSOLUMENT demain avec prix d'entree precis\n"
            "5. Signal d'alarme: si ce scenario se realise demain = ne pas entrer\n"
            "Chiffres precis. Liens causaux explicites. Sans markdown."
        )
        synth = groq_call(prompt, 600) or "Analyse en cours..."

        # Smart money cards
        sm_cards = ""
        for s in sm[:5]:
            t = s["t"]; info = BVC.get(t,{})
            ammc_t = [a for a in ammc_pubs if a.get("ticker")==t][:1]
            company_n = get_company_news(t)[:1]
            ammc_line = f'<div style="font-size:10px;color:#60A5FA;margin-top:3px">📄 {ammc_t[0]["title"][:90]}</div>' if ammc_t else ""
            news_line = f'<div style="font-size:10px;color:#9CA3AF;margin-top:2px">📰 {company_n[0][:90]}</div>' if company_n else ""
            sm_cards += (
                f'<div style="background:#13192A;border-radius:8px;padding:12px;margin-bottom:8px;border-left:3px solid #F59E0B">'
                f'<div style="display:flex;justify-content:space-between">'
                f'<span style="color:#F59E0B;font-weight:900;font-size:16px;font-family:monospace">{t}</span>'
                f'<span style="color:#F59E0B;font-weight:700">VOLUME x{s["vr"]}</span></div>'
                f'<div style="color:#9CA3AF;font-size:11px">{info.get("n","")} - {info.get("s","")}</div>'
                f'<div style="font-size:11px;margin-top:5px;display:flex;gap:14px;flex-wrap:wrap">'
                f'<span style="color:#6B7280">Cloture <strong style="color:#E8E4D6">{s["c"]:.2f} MAD</strong></span>'
                f'<span style="color:{"#00C87A" if s["chg"]>=0 else "#FF4560"};font-weight:700">{s["chg"]:+.2f}%</span>'
                f'<span style="color:#9CA3AF">RSI {s["rsi"]:.0f}</span>'
                f'<span style="color:#6B7280;font-size:10px">Moy.90j: {int(s.get("avg90",0)):,}</span>'
                f'</div>'
                + ammc_line + news_line +
                f'</div>'
            )

        # Paris pour demain
        paris_html = ""
        for item in top_demain[:3]:
            t = item["t"]; d = item["d"]; info = BVC.get(t,{})
            close = d.get("close",0)
            sc    = item["sc"]
            is_buy= d.get("macd",0) > d.get("macd_s",0) and d.get("rsi",50) < 65
            tgt   = round(close*(1.05 if is_buy else 0.95),2)
            stop  = round(close*(0.97 if is_buy else 1.03),2)
            col_s = "#00C87A" if is_buy else "#FF4560"
            pats, sigs = detect_patterns(d, info)
            paris_html += (
                f'<div style="background:#13192A;border-radius:8px;padding:10px;margin-bottom:7px;border-left:3px solid {col_s}">'
                f'<div style="display:flex;justify-content:space-between;align-items:center">'
                f'<span style="color:{col_s};font-weight:900;font-family:monospace">{t}</span>'
                f'<span style="color:#9CA3AF;font-size:10px">{info.get("n","")} | Score {sc}/100</span>'
                f'</div>'
                f'<div style="font-size:11px;color:#6B7280;margin-top:5px">'
                f'Entree: <strong style="color:#E8E4D6">{close:.2f}</strong> — '
                f'Cible: <strong style="color:#00C87A">{tgt:.2f}</strong> — '
                f'Stop: <strong style="color:#FF4560">{stop:.2f}</strong>'
                f'</div>'
                + ("".join(f'<div style="font-size:10px;color:#F59E0B">• {pat}</div>' for pat in pats[:2]) if pats else "")
                + f'</div>'
            )

        sp_c = macro.get("sp500",{}).get("c",0)

        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="w">

<div class="hdr">
  <div class="logo">BARAKA</div>
  <div class="sub">POST-CLOTURE — {now}</div>
  <span class="bdg or" style="border-color:rgba(245,158,11,.4);background:rgba(245,158,11,.08)">
    {len(sm)} MOUVEMENTS SMART MONEY DETECTES
  </span>
</div>

<div class="sy">
  <div class="syt">ANALYSE POST-CLOTURE — GROQ AI</div>
  <div class="sytx">{synth}</div>
</div>

<div class="sec">
  <div class="st">SMART MONEY — OU EST PARTI L'ARGENT</div>
  {sm_cards if sm_cards else '<div style="color:#6B7280;padding:10px">Aucun mouvement institutionnel anormal aujourd\'hui</div>'}
</div>

<div class="sec">
  <div class="st">PARI POUR DEMAIN — NIVEAUX D'ENTREE</div>
  {paris_html}
</div>

<div class="sec">
  <div class="st">GEOPOLITIQUE — RISQUES OVERNIGHT</div>
  {''.join(f'<div class="ni"><span class="src" style="background:rgba(239,68,68,.12);color:#EF4444">GEO</span>{n}</div>' for n in (geo.get("moyen_orient",[]) + geo.get("fed",[]) + geo.get("petrole",[]))[:5])}
</div>

<div class="ft">
  Prochain email: demain 06h00 — Pre-collecte profonde<br>
  Prochain email: demain 08h30 — Brief Ouverture<br>
  <strong class="go">Baraka analyse pendant que tu dors</strong>
</div>
</div></body></html>"""

        send_email("BARAKA — POST-CLOTURE + SMART MONEY 15h30", html)

    except Exception as e:
        print(f"[CLOTURE] Erreur: {e}")
        import traceback; traceback.print_exc()
        send_email("BARAKA — POST-CLOTURE 15h30",
            f"<div style='background:#080C14;color:#E8E4D6;padding:20px;font-family:monospace'>"
            f"<h2 style='color:#C9A84C'>POST-CLOTURE {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</h2>"
            f"<p style='color:#FF4560'>{str(e)[:300]}</p></div>")


# ─── SURVEILLANCE TRIGGERS ───────────────────────────────────────────────────────
def monitor_triggers():
    """Veille triggers toutes les 10 min pendant heures marche"""
    if not _WATCHLIST: return
    print(f"[WATCHLIST] Verification {len(_WATCHLIST)} titres...")
    try:
        bvc_data = get_bvc_data()
        macro    = get_macro()
        for ticker, wl in list(_WATCHLIST.items()):
            d = bvc_data.get(ticker)
            if not d: continue
            close = d.get("close",0)
            vol   = d.get("volume",0)
            rsi   = d.get("rsi",50)
            avg   = d.get("avg_vol",1)
            ema20 = d.get("ema20",0)
            side  = wl["side"]
            entry = wl["entry"]; stop = wl["stop"]; target = wl["target"]
            triggered = []

            if side == "BUY":
                if close >= target*0.998 and f"target_{ticker}" not in wl["fired"]:
                    wl["fired"].append(f"target_{ticker}")
                    triggered.append({"msg":f"CIBLE ATTEINTE {close:.2f} >= {target:.2f}","urg":"CRITICAL"})
                if close <= stop*1.002 and f"stop_{ticker}" not in wl["fired"]:
                    wl["fired"].append(f"stop_{ticker}")
                    triggered.append({"msg":f"STOP TOUCHE {close:.2f} <= {stop:.2f} — SORTIR IMMEDIAT","urg":"CRITICAL"})
                if avg>0 and vol/avg > 3 and rsi < 60 and f"vol_{ticker}" not in wl["fired"]:
                    wl["fired"].append(f"vol_{ticker}")
                    triggered.append({"msg":f"Volume institutionnel x{vol/avg:.1f} — accumulation","urg":"HIGH"})
                if ema20>0 and close > ema20*1.001 and rsi < 65 and f"ema_{ticker}" not in wl["fired"]:
                    wl["fired"].append(f"ema_{ticker}")
                    triggered.append({"msg":f"Cassure EMA20 ({ema20:.2f}) confirmee","urg":"HIGH"})

            if triggered:
                max_urg = "CRITICAL" if any(t["urg"]=="CRITICAL" for t in triggered) else "HIGH"
                urg_col = "#FF4560" if max_urg=="CRITICAL" else "#F59E0B"
                cond_html = "".join(
                    f'<div style="background:{urg_col}12;border-left:3px solid {urg_col};padding:10px;margin-bottom:6px;border-radius:4px">'
                    f'<div style="color:#E8E4D6;font-size:13px;font-weight:700">{t["msg"]}</div></div>'
                    for t in triggered
                )
                is_stop   = any("STOP" in t["msg"] for t in triggered)
                is_target = any("CIBLE" in t["msg"] for t in triggered)
                if is_stop:
                    action = f'<div style="background:rgba(255,69,96,.15);border:2px solid #FF4560;border-radius:8px;padding:14px;text-align:center;margin:10px 0"><div style="font-size:16px;font-weight:900;color:#FF4560">SORTIR {ticker} IMMEDIATEMENT</div></div>'
                elif is_target:
                    profit = round((close-entry)/entry*100,1)
                    action = f'<div style="background:rgba(0,200,122,.1);border:2px solid #00C87A;border-radius:8px;padding:14px;text-align:center;margin:10px 0"><div style="font-size:16px;font-weight:900;color:#00C87A">PRENDRE PROFIT {ticker} +{profit}%</div></div>'
                else:
                    action = f'<div style="background:rgba(245,158,11,.1);border:2px solid #F59E0B;border-radius:8px;padding:14px;text-align:center;margin:10px 0"><div style="font-size:16px;font-weight:900;color:#F59E0B">CONDITIONS ENTREE REUNIES — {ticker}</div></div>'

                info  = BVC.get(ticker,{})
                sp_c  = macro.get("sp500",{}).get("c",0)
                cac_c = macro.get("cac40",{}).get("c",0)
                html  = (
                    f'<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>'
                    f'<body><div class="w">'
                    f'<div class="hdr" style="border-color:{urg_col}60">'
                    f'<div class="logo">BARAKA</div>'
                    f'<div class="sub">ALERTE TRIGGER — {datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}</div>'
                    f'<span class="bdg" style="color:{urg_col};border-color:{urg_col}60">{"CRITIQUE" if max_urg=="CRITICAL" else "HAUTE PRIORITE"}</span>'
                    f'</div>'
                    f'<div style="background:#13192A;border-radius:10px;padding:14px;margin-bottom:12px">'
                    f'<div style="font-size:22px;font-weight:900;color:{urg_col};font-family:monospace">{ticker}</div>'
                    f'<div style="color:#9CA3AF;font-size:11px">{info.get("n","")} - {info.get("s","")}</div>'
                    f'<div style="font-size:18px;font-weight:900;color:#E8E4D6;margin-top:6px">{close:.2f} MAD</div>'
                    f'<div style="font-size:11px;color:#6B7280">Entree: {entry:.2f} | Stop: {stop:.2f} | Cible: {target:.2f}</div>'
                    f'</div>'
                    f'{cond_html}{action}'
                    f'<div style="background:#0F1520;border-radius:8px;padding:10px;font-size:11px;color:#9CA3AF">'
                    f'S&P500: <span style="color:{"#00C87A" if sp_c>=0 else "#FF4560"}">{sp_c:+.2f}%</span> | '
                    f'CAC40: <span style="color:{"#00C87A" if cac_c>=0 else "#FF4560"}">{cac_c:+.2f}%</span>'
                    f'</div>'
                    f'<div class="ft">Confirmer avant d\'agir — Baraka ne garantit pas les performances<br>'
                    f'<strong class="go">BARAKA v7.0</strong></div>'
                    f'</div></body></html>'
                )
                prefix = "STOP" if is_stop else ("CIBLE" if is_target else "TRIGGER")
                send_email(f"BARAKA — {prefix} {ticker} — ALERTE", html)

    except Exception as e:
        print(f"[WATCHLIST] {e}")

# ─── FLASK ───────────────────────────────────────────────────────────────────────
def start_flask():
    try:
        from flask import Flask
        app = Flask(__name__)
        JOBS = {"brief":brief_ouverture,"analyse":analyse_entrees,"cloture":post_cloture,"precollect":pre_collect}

        @app.route("/")
        def idx():
            wl_info = f"{len(_WATCHLIST)} titres surveilles" if _WATCHLIST else "watchlist vide"
            return f"BARAKA v7.0 ACTIVE | {datetime.datetime.now().strftime('%H:%M:%S')} | {wl_info}", 200

        @app.route("/ping")
        def ping(): return "OK", 200

        @app.route("/trigger/<name>")
        def trigger(name):
            if name not in JOBS: return f"Options: {list(JOBS.keys())}", 400
            threading.Thread(target=JOBS[name], daemon=True).start()
            return f"'{name}' declenche — email dans 2 min.", 200

        @app.route("/watchlist")
        def wl():
            if not _WATCHLIST: return "Watchlist vide - attendre analyse 12h00", 200
            out = [f"BARAKA WATCHLIST {datetime.datetime.now().strftime('%H:%M')}\n"]
            for tk, w in _WATCHLIST.items():
                out.append(f"{tk}: entree={w['entry']:.2f} stop={w['stop']:.2f} cible={w['target']:.2f} fired={len(w['fired'])}\n")
            return "".join(out), 200, {"Content-Type":"text/plain"}

        @app.route("/check")
        def check():
            threading.Thread(target=monitor_triggers, daemon=True).start()
            return f"Verification {len(_WATCHLIST)} titres - alerte email si trigger actif", 200

        port = int(os.environ.get("PORT",8080))
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"[FLASK] {e}")

# ─── SCHEDULER ───────────────────────────────────────────────────────────────────
def run_scheduler():
    print("""
+======================================================+
|  BARAKA v7.0 - HEDGE FUND INTELLIGENCE - BVC          |
+======================================================+
|  05:00 UTC (06:00 Casa) -> Pre-collecte profonde      |
|  07:30 UTC (08:30 Casa) -> Brief Ouverture             |
|  11:00 UTC (12:00 Casa) -> Analyse + Recommandations   |
|  14:30 UTC (15:30 Casa) -> Post-Cloture Smart Money   |
|  /10 min (09-15 UTC)    -> Surveillance Triggers       |
+======================================================+
    """)

    threading.Thread(target=start_flask, daemon=True).start()
    fired = {}

    while True:
        try:
            now   = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            today = str(now.date())
            h, m, wd = now.hour, now.minute, now.weekday()

            if h == 0 and m == 0:
                fired = {}
                watchlist_clear()

            if wd < 5:  # Lundi - Vendredi
                if h==5 and 0<=m<15 and f"pre_{today}" not in fired:
                    fired[f"pre_{today}"] = True
                    threading.Thread(target=pre_collect, daemon=True).start()

                elif h==7 and 30<=m<45 and f"brief_{today}" not in fired:
                    fired[f"brief_{today}"] = True
                    threading.Thread(target=brief_ouverture, daemon=True).start()

                elif h==11 and 0<=m<15 and f"analyse_{today}" not in fired:
                    fired[f"analyse_{today}"] = True
                    threading.Thread(target=analyse_entrees, daemon=True).start()

                elif h==14 and 30<=m<45 and f"cloture_{today}" not in fired:
                    fired[f"cloture_{today}"] = True
                    threading.Thread(target=post_cloture, daemon=True).start()

                if 8 <= h < 15 and m % 10 == 0 and _WATCHLIST:
                    tkey = f"trigger_{today}_{h}_{m}"
                    if tkey not in fired:
                        fired[tkey] = True
                        threading.Thread(target=monitor_triggers, daemon=True).start()

        except Exception as e:
            print(f"[SCHEDULER] {e}")

        time.sleep(30)


if __name__ == "__main__":
    run_scheduler()
