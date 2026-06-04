"""
BARAKA v6.0 — BVC Trading Agent
3 emails par jour : Brief 08h30 / Analyse+Entrees 12h00 / Post-Cloture 15h30
Architecture simple — scheduler UTC — aucun blocage
"""

import os, time, datetime, threading, json, re, requests, io
import numpy as np

# ─── ENV & CONFIG ─────────────────────────────────────────────────────────────
RESEND_KEY  = os.environ.get("RESEND_API_KEY", "")
GROQ_KEY    = os.environ.get("GROQ_API_KEY", "")
TO_EMAIL    = "mohamed.csaibari@gmail.com"
FROM_EMAIL  = "Baraka BVC <onboarding@resend.dev>"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
R = {"verify": False, "timeout": 6}

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─── UNIVERS BVC ──────────────────────────────────────────────────────────────
BVC = {
    "ATW":     {"n":"Attijariwafa Bank",      "s":"Banque",       "v":85000, "mc":"large"},
    "BCP":     {"n":"Banque Centrale Pop.",    "s":"Banque",       "v":60000, "mc":"large"},
    "BMCE":    {"n":"Bank of Africa",          "s":"Banque",       "v":70000, "mc":"large"},
    "CIH":     {"n":"CIH Bank",                "s":"Banque",       "v":45000, "mc":"mid"},
    "CDM":     {"n":"Credit du Maroc",         "s":"Banque",       "v":18000, "mc":"mid"},
    "BMCI":    {"n":"BMCI",                    "s":"Banque",       "v":12000, "mc":"mid"},
    "CFG":     {"n":"CFG Bank",                "s":"Banque",       "v":8000,  "mc":"small"},
    "WAA":     {"n":"Wafa Assurance",          "s":"Assurance",    "v":6000,  "mc":"mid"},
    "ATL":     {"n":"Atlanta",                 "s":"Assurance",    "v":5000,  "mc":"small"},
    "SAH":     {"n":"Saham Assurance",         "s":"Assurance",    "v":4000,  "mc":"small"},
    "IAM":     {"n":"Maroc Telecom",           "s":"Telecom",      "v":120000,"mc":"large"},
    "HPS":     {"n":"HPS",                     "s":"Tech",         "v":15000, "mc":"mid"},
    "OCP":     {"n":"OCP Group",               "s":"Chimie",       "v":95000, "mc":"large"},
    "MANAGEM": {"n":"Managem",                 "s":"Mines",        "v":12000, "mc":"mid"},
    "SMI":     {"n":"SMI",                     "s":"Mines",        "v":8000,  "mc":"small"},
    "CMT":     {"n":"Cie Miniere Touissit",    "s":"Mines",        "v":5000,  "mc":"small"},
    "ADH":     {"n":"Addoha",                  "s":"Immobilier",   "v":35000, "mc":"mid"},
    "ALM":     {"n":"Alliances",               "s":"Immobilier",   "v":15000, "mc":"mid"},
    "HOL":     {"n":"Holcim Maroc",            "s":"Construction", "v":12000, "mc":"mid"},
    "LHM":     {"n":"LafargeHolcim Maroc",     "s":"Construction", "v":9000,  "mc":"mid"},
    "CMA":     {"n":"Ciments du Maroc",        "s":"Construction", "v":10000, "mc":"mid"},
    "LABEL":   {"n":"Label Vie",               "s":"Distribution", "v":9000,  "mc":"mid"},
    "LAC":     {"n":"Lesieur Cristal",         "s":"Agro",         "v":11000, "mc":"mid"},
    "COSUMAR": {"n":"Cosumar",                 "s":"Agro",         "v":8000,  "mc":"mid"},
    "TMA":     {"n":"Total Maroc",             "s":"Energie",      "v":7000,  "mc":"mid"},
    "TAQA":    {"n":"Taqa Morocco",            "s":"Energie",      "v":8000,  "mc":"mid"},
    "SRM":     {"n":"Sonasid",                 "s":"Siderurgie",   "v":6000,  "mc":"mid"},
    "CTM":     {"n":"CTM",                     "s":"Transport",    "v":5000,  "mc":"small"},
    "SOTHEMA": {"n":"Sothema",                 "s":"Pharma",       "v":6000,  "mc":"mid"},
    "RIS":     {"n":"Risma",                   "s":"Tourisme",     "v":5000,  "mc":"small"},
    "EQDOM":   {"n":"Eqdom",                   "s":"Credit Conso", "v":4000,  "mc":"small"},
    "SALAF":   {"n":"Salafin",                 "s":"Credit Conso", "v":3500,  "mc":"small"},
}

# ─── EMAIL ────────────────────────────────────────────────────────────────────
def send_email(subject, html):
    if not RESEND_KEY:
        print(f"[EMAIL] Pas de RESEND_KEY"); return False
    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_KEY}", "Content-Type": "application/json"},
            json={"from": FROM_EMAIL, "to": [TO_EMAIL], "subject": subject, "html": html},
            timeout=15, verify=False,
        )
        ok = r.status_code in [200, 201]
        print(f"[EMAIL] {'OK' if ok else 'ERREUR ' + str(r.status_code)}: {subject[:60]}")
        return ok
    except Exception as e:
        print(f"[EMAIL] {e}"); return False

# ─── GROQ ─────────────────────────────────────────────────────────────────────
def groq_call(prompt, max_tokens=500):
    if not GROQ_KEY: return ""
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_KEY)
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt}],
            max_tokens=max_tokens, temperature=0.2,
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        print(f"[GROQ] {e}"); return ""

# ─── TV SCANNER BVC ──────────────────────────────────────────────────────────
def get_bvc_data():
    """Scanner TradingView — 1 requete pour tous les titres BVC"""
    TV_H = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
        "Content-Type": "application/json",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/markets/stocks-morocco/",
        "Accept": "application/json",
    }
    payload = {
        "filter": [],
        "columns": ["name","close","volume","change","RSI","MACD.macd","MACD.signal",
                    "EMA20","EMA50","EMA200","Stoch.K","ADX","high","low","open","Recommend.All",
                    "average_volume_10d_calc","average_volume_30d_calc","average_volume_90d_calc"],
        "sort": {"sortBy":"market_cap_basic","sortOrder":"desc"},
        "range": [0, 100],
    }
    data = {}
    try:
        r = requests.post("https://scanner.tradingview.com/morocco/scan",
                          headers=TV_H, json=payload, timeout=20, verify=False)
        if r.status_code != 200:
            print(f"[TV] HTTP {r.status_code}"); return {}
        rows = r.json().get("data", [])
        print(f"[TV] {len(rows)} titres recus")
        for row in rows:
            raw  = row.get("s","").upper()
            vals = row.get("d", [])
            if len(vals) < 4: continue
            # Match flexible : CSEMA:ATW → ATW
            ticker = None
            for t in BVC:
                if t in raw:
                    ticker = t; break
            if not ticker: continue
            def v(i, d=0):
                try: return float(vals[i]) if vals[i] is not None else d
                except: return d
            rec    = v(15, 0)
            vol_10 = v(16, 0)
            vol_30 = v(17, 0)
            vol_90 = v(18, 0)
            # Moyenne 90j (smart money reference) - fallback sur BVC dict
            avg90 = vol_90 if vol_90>0 else (vol_30 if vol_30>0 else BVC.get(ticker,{}).get("v",1))
            data[ticker] = {
                "close":  v(1), "volume": int(v(2)), "change": round(v(3),2),
                "rsi":    v(4,50), "macd": v(5), "macd_s": v(6),
                "ema20":  v(7), "ema50": v(8), "ema200": v(9),
                "stoch":  v(10,50), "adx": v(11),
                "high":   v(12), "low": v(13), "open": v(14),
                "rec":    "ACHETER" if rec>0.1 else ("VENDRE" if rec<-0.1 else "NEUTRE"),
                "avg90":  avg90, "avg30": vol_30, "avg10": vol_10,
            }
        print(f"[TV] {len(data)} titres BVC matches")
    except Exception as e:
        print(f"[TV] {e}")
    return data

# ─── MACRO ────────────────────────────────────────────────────────────────────
def _stooq(sym):
    """Prix + variation depuis stooq.com"""
    try:
        r = requests.get(f"https://stooq.com/q/d/l/?s={sym}&i=d", headers=HEADERS, **R)
        lines = r.text.strip().splitlines()
        if len(lines) >= 3:
            curr = float(lines[-1].split(",")[4])
            prev = float(lines[-2].split(",")[4])
            return {"p":round(curr,2),"c":round((curr-prev)/prev*100,2)}
    except: pass
    return {"p":0,"c":0}

def get_macro():
    """Donnees macro completes : US + Europe + Asie + MAD + Maroc"""
    m = {}
    # ── FRED : taux US ──────────────────────────────────────────────
    for k, s in [("us10y","DGS10"),("us2y","DGS2"),("fed_rate","FEDFUNDS")]:
        try:
            r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}",
                             headers=HEADERS, **R)
            lines = r.text.strip().splitlines()
            if len(lines) >= 2: m[k] = float(lines[-1].split(",")[1])
            else: m[k] = 0
        except: m[k] = 0
    m["yield_spread"] = round(m.get("us10y",0) - m.get("us2y",0), 3)

    # ── Exchange rates (USD base) ────────────────────────────────────
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", headers=HEADERS, **R)
        d = r.json().get("rates",{})
        m["usd_mad"] = round(float(d.get("MAD",10.0)),4)
        m["eur_usd"] = round(1/float(d.get("EUR",0.92)),4) if d.get("EUR") else 1.08
        m["eur_mad"] = round(m["usd_mad"] * float(d.get("EUR",0.92)),4)
        m["gbp_mad"] = round(m["usd_mad"] * float(d.get("GBP",0.79)),4) if d.get("GBP") else 0
    except:
        m.update({"usd_mad":10.0,"eur_usd":1.08,"eur_mad":10.9,"gbp_mad":12.5})

    # ── Indices mondiaux (Stooq) ─────────────────────────────────────
    indices = {
        "sp500":"^spx","nasdaq":"^ndx","cac40":"^cac",
        "dax":"^dax","ftse100":"^ukx","nikkei":"^nkx",
        "shanghai":"^shc","em":"eems.us",   # EM ETF proxy
        "gold":"xauusd","silver":"xagusd",
        "brent":"brent.f","oil_wti":"cl.f",
        "copper":"hg.f","phosphate_idx":"mos.us",  # Mosaic = proxy phosphate
        "dxy":"dxy.f",
    }
    for name, sym in indices.items():
        m[name] = _stooq(sym)

    # Spread 10Y-2Y → recession signal
    m["recession_risk"] = m["yield_spread"] < 0

    return m

# ─── AMMC ─────────────────────────────────────────────────────────────────────
def get_ammc_pubs():
    """Toutes les publications PDF recentes AMMC"""
    pubs = []
    try:
        from bs4 import BeautifulSoup
        for page in range(0, 5):
            url = f"https://www.ammc.ma/fr/communiques-presse-emetteurs?page={page}" if page > 0 else \
                  "https://www.ammc.ma/fr/communiques-presse-emetteurs"
            r = requests.get(url, headers=HEADERS, **R)
            if r.status_code != 200: break
            soup = BeautifulSoup(r.text, "html.parser")
            found = 0
            for link in soup.find_all("a", href=True):
                href = link["href"]
                text = link.get_text(strip=True)
                if not text or len(text) < 5: continue
                is_pdf = any(x in href.lower() for x in [".pdf","telecharger","download"])
                if not is_pdf: continue
                full = href if href.startswith("http") else "https://www.ammc.ma"+href
                ticker = None
                text_up = text.upper()
                for t, info in BVC.items():
                    if t in text_up or info["n"].split()[0].upper() in text_up:
                        ticker = t; break
                pubs.append({"url":full,"title":text[:150],"ticker":ticker})
                found += 1
            if found == 0: break
            time.sleep(0.5)
        print(f"[AMMC] {len(pubs)} publications trouvees")
    except Exception as e:
        print(f"[AMMC] {e}")
    # Deduplicate
    seen = set()
    unique = []
    for p in pubs:
        if p["url"] not in seen:
            seen.add(p["url"]); unique.append(p)
    return unique[:30]

def ammc_for(ticker, pubs):
    return [p for p in pubs if p.get("ticker")==ticker][:3]

# ─── NEWS ─────────────────────────────────────────────────────────────────────
def gnews(query, n=4):
    items = []
    try:
        from urllib.parse import quote
        url = f"https://news.google.com/rss/search?q={quote(query)}&hl=fr&gl=MA&ceid=MA:fr"
        r = requests.get(url, headers=HEADERS, **R)
        titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", r.text)
        for t in titles[1:n+1]:
            clean = re.sub(r"<[^>]+>","",t).strip()
            if len(clean)>15: items.append(clean[:180])
    except: pass
    return items

def boursenews():
    try:
        from bs4 import BeautifulSoup
        r = requests.get("https://www.boursenews.ma/", headers=HEADERS, **R)
        soup = BeautifulSoup(r.text,"html.parser")
        return list(dict.fromkeys([
            el.get_text(strip=True)[:180]
            for el in soup.select("article h2,article h3,.entry-title")
            if len(el.get_text(strip=True))>20
        ]))[:6]
    except: return []

def telegram_bvc():
    posts = []
    for ch in ["boursecasablancaofficiel","bvcmaroc","tradingmaroc"]:
        try:
            from bs4 import BeautifulSoup
            r = requests.get(f"https://t.me/s/{ch}", headers=HEADERS, **R)
            soup = BeautifulSoup(r.text,"html.parser")
            for msg in soup.select(".tgme_widget_message_text")[:2]:
                t = msg.get_text(strip=True)
                if len(t)>20: posts.append({"ch":ch,"t":t[:200]})
        except: pass
        time.sleep(0.3)
    return posts[:5]

def bkam_news():
    """BAM publications : taux directeur + bons du tresor + inflation Maroc"""
    results = {"bam_news":[], "inflation_news":[], "bdt_info":""}
    try:
        from bs4 import BeautifulSoup
        r = requests.get("https://www.bkam.ma/Politique-monetaire", headers=HEADERS, **R)
        soup = BeautifulSoup(r.text,"html.parser")
        for el in soup.select("p,h2,h3")[:10]:
            t = el.get_text(strip=True)
            if 20<len(t)<300:
                results["bam_news"].append(t[:200])
        results["bam_news"] = results["bam_news"][:3]
    except: pass
    # News inflation Maroc + taux
    results["inflation_news"] = gnews("inflation Maroc HCP taux directeur BAM 2026", 3)
    # BDT / Bons du Tresor
    results["bdt_news"] = gnews("bons tresor Maroc BDT taux adjudication 2026", 2)
    return results

def get_correlations_context(macro):
    """
    Calcule et formate les correlations importantes pour la BVC.
    France/CAC40 = 1er partenaire commercial Maroc.
    Brent/energie = impact inflation + CTM/TMA.
    Phosphate = OCP = 50% export Maroc.
    Or = Managem/SMI.
    USD/MAD = importations + pouvoir d achat.
    """
    cac  = macro.get("cac40",{}).get("c",0)
    sp   = macro.get("sp500",{}).get("c",0)
    brent= macro.get("brent",{}).get("c",0)
    gold = macro.get("gold",{}).get("c",0)
    phos = macro.get("phosphate_idx",{}).get("c",0)
    dxy  = macro.get("dxy",{}).get("c",0)
    mad  = macro.get("usd_mad",10.0)
    eur_mad = macro.get("eur_mad",10.9)
    spread = macro.get("yield_spread",0)
    recession = macro.get("recession_risk",False)

    ctx = []

    # France/Europe → BVC corrélation forte
    if abs(cac) > 0.5:
        ctx.append(f"CAC40 {cac:+.2f}% → France 1er partenaire Maroc → {'impact positif' if cac>0 else 'pression'} sur BVC à l ouverture")

    # USD/MAD → pouvoir d achat import inflation
    if mad > 10.2:
        ctx.append(f"USD/MAD={mad} fort → importations cheres → inflation Maroc → pression sur la consommation et marges (COSUMAR, LABEL, LAC)")
    elif mad < 9.8:
        ctx.append(f"USD/MAD={mad} faible → importations moins cheres → soulagement inflation → positif consommation")

    # Brent → inflation + energie
    if abs(brent) > 1.5:
        ctx.append(f"Brent {brent:+.2f}% → {'renchérissement carburant Maroc → inflation transport → CTM/TMA sous pression' if brent>0 else 'petrole moins cher → positif CTM/TMA/industrie'}")

    # Phosphate → OCP
    if abs(phos) > 1:
        ctx.append(f"Indice phosphate {phos:+.2f}% → {'positif OCP/SNEP/Fertima' if phos>0 else 'attention OCP'}")

    # Or → mines
    if abs(gold) > 0.5:
        ctx.append(f"Or {gold:+.2f}% → {'Managem/SMI en vue' if gold>0 else 'pression sur miniers'}")

    # Yield spread → arbitrage BDT vs actions
    if spread < 0:
        ctx.append(f"Courbe inversee US ({spread:+.3f}%) → signal recession → les salles de marche arbitrent vers les BDT Maroc (plus securises) au détriment des actions")
    elif spread > 1.5:
        ctx.append(f"Spread 10Y-2Y={spread:+.3f}% → economie saine → appetit pour les actions vs BDT")

    # DXY → MAD et imports
    if abs(dxy) > 0.3:
        ctx.append(f"Dollar index {dxy:+.2f}% → impact direct USD/MAD → {'MAD s affaiblit → importations cheres Maroc' if dxy>0 else 'MAD se renforce → importations allégées'}")

    return ctx[:6]  # Max 6 correlations

# ─── SCORING ─────────────────────────────────────────────────────────────────
def score(d, info, macro=None):
    """
    Score 0-100 : technique (70%) + macro sectoriel (30%)
    Integre les correlations mondiales directement dans le score
    """
    if not d or not d.get("close"): return 0
    s = 50
    rsi   = d.get("rsi",50)
    close = d.get("close",0)
    ema20,ema50,ema200 = d.get("ema20",0),d.get("ema50",0),d.get("ema200",0)
    macd,macd_s = d.get("macd",0),d.get("macd_s",0)
    vol   = d.get("volume",0)
    avg   = d.get("avg90",0) or d.get("avg30",0) or info.get("v",1)
    adx   = d.get("adx",0)
    sect  = info.get("s","")
    mc    = info.get("mc","small")

    # ── SIGNAUX TECHNIQUES (70 pts max) ─────────────────────────────
    # RSI
    if rsi<25: s+=22
    elif rsi<35: s+=14
    elif rsi<45: s+=6
    elif rsi>75: s-=22
    elif rsi>65: s-=12
    elif rsi>55: s-=5

    # MACD croisement
    if macd>macd_s: s+=12
    else: s-=8

    # Position vs EMA200 (tendance long terme)
    if ema200>0:
        if close>ema200: s+=10
        else: s-=8

    # Alignement EMA20/50 (tendance court terme)
    if close>ema20>ema50: s+=15
    elif close>ema20: s+=6
    elif close<ema20<ema50: s-=15
    elif close<ema20: s-=6

    # Volume vs moyenne 90j (smart money)
    if avg>0:
        vr = vol/avg
        if vr>4: s+=20
        elif vr>3: s+=14
        elif vr>2: s+=8
        elif vr>1.5: s+=4

    # ADX (force de tendance)
    if adx>30: s+=10
    elif adx>20: s+=5

    # Capitalisaton (liquidite)
    if mc=="large": s+=5
    elif mc=="mid": s+=2

    # ── BONUS MACRO SECTORIEL (30 pts max) ──────────────────────────
    if macro:
        cac_c   = macro.get("cac40",{}).get("c",0)
        brent_c = macro.get("brent",{}).get("c",0)
        gold_c  = macro.get("gold",{}).get("c",0)
        phos_c  = macro.get("phosphate_idx",{}).get("c",0)
        sp_c    = macro.get("sp500",{}).get("c",0)
        usd_mad = macro.get("usd_mad",10.0)
        spread  = macro.get("yield_spread",0)
        rec     = macro.get("recession_risk",False)

        # CAC40 : 1er partenaire Maroc -> correlation forte BVC
        if cac_c>1: s+=8
        elif cac_c>0.3: s+=4
        elif cac_c<-1: s-=6
        elif cac_c<-0.3: s-=3

        # S&P500 : influence globale
        if sp_c>1: s+=5
        elif sp_c<-1: s-=4

        # BRENT -> secteurs energie et transport
        if sect in ["Energie","Transport","Distribution","Agro"]:
            if brent_c>2: s-=10   # Coût energie monte
            elif brent_c>1: s-=5
            elif brent_c<-2: s+=10  # Energie moins chere
            elif brent_c<-1: s+=5

        # OR -> mines precieux
        if sect=="Mines":
            if gold_c>1: s+=12
            elif gold_c>0.5: s+=7
            elif gold_c<-1: s-=10

        # PHOSPHATE -> OCP, chimie
        if sect in ["Chimie","Mines"]:
            if phos_c>2: s+=12
            elif phos_c>1: s+=6
            elif phos_c<-2: s-=8

        # USD/MAD fort -> exportateurs gagnent, importateurs perdent
        if usd_mad>10.3:  # MAD faible
            if sect=="Chimie": s+=8      # OCP exporte en USD
            if sect in ["Agro","Distribution"]: s-=6  # importent en USD
        elif usd_mad<9.7:  # MAD fort
            if sect=="Chimie": s-=5
            if sect in ["Agro","Distribution"]: s+=5

        # BANQUES -> taux + recession
        if sect=="Banque":
            if spread>1: s+=8    # Courbe normale -> banques profitent
            elif spread<0: s-=10  # Courbe inversee -> risque recession
            if rec: s-=8

        # ASSURANCE
        if sect=="Assurance":
            if spread>0.5: s+=5
            elif spread<0: s-=5

        # IMMOBILIER -> taux
        if sect=="Immobilier":
            if spread<0: s-=8  # Taux eleves mauvais pour immo
            elif spread>1: s+=5

        # TELECOM -> valeur refuge en risk-off
        if sect=="Telecom":
            if sp_c<-1 and cac_c<-1: s+=5  # Refuge en baisse

    return max(0,min(100,s))

def smart_money(bvc_data):
    """Smart money base sur moyenne 90j reelle (TV scanner) ou fallback BVC dict"""
    sm=[]
    for t,d in bvc_data.items():
        info = BVC.get(t,{})
        vol  = d.get("volume",0)
        # Priorite: moyenne 90j TV > moyenne 30j TV > moyenne BVC dict
        avg  = d.get("avg90",0) or d.get("avg30",0) or info.get("v",1)
        if avg <= 0: continue
        ratio = vol/avg
        if ratio >= 2.5:  # Volume 2.5x la moyenne 90j = smart money
            sm.append({
                "t":t,"n":info.get("n",""),"s":info.get("s",""),
                "vr":round(ratio,1),"c":d.get("close",0),
                "chg":d.get("change",0),"rsi":d.get("rsi",50),
                "avg90":round(avg,0),"vol":vol,
            })
    return sorted(sm,key=lambda x:-x["vr"])

# ─── HTML CSS ─────────────────────────────────────────────────────────────────
CSS = """<style>
*{box-sizing:border-box}
body{background:#0A0D14;color:#E8E4D6;font-family:'Courier New',monospace;margin:0;padding:0}
.w{max-width:640px;margin:0 auto;padding:14px}
.hdr{background:#111520;border:1px solid rgba(201,168,76,.4);border-radius:12px;padding:18px;text-align:center;margin-bottom:12px}
.logo{font-size:26px;font-weight:900;color:#C9A84C;letter-spacing:6px}
.sub{font-size:10px;color:#6B7280;letter-spacing:2px;margin-top:3px}
.bdg{display:inline-block;border:1px solid;padding:4px 14px;border-radius:20px;font-size:11px;margin-top:8px}
.sec{background:#111520;border:1px solid rgba(201,168,76,.2);border-radius:10px;padding:13px;margin-bottom:10px}
.t{font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:9px}
.mg{display:flex;gap:6px;flex-wrap:wrap}
.mb{flex:1;min-width:75px;background:#171C2C;border-radius:7px;padding:9px;text-align:center}
.ml{font-size:9px;color:#6B7280;margin-bottom:3px}
.mv{font-size:14px;font-weight:900}
.g{color:#00C87A}.r{color:#FF4560}.go{color:#C9A84C}.b{color:#60A5FA}.pu{color:#8B5CF6}
.ni{padding:5px 0;border-bottom:1px solid rgba(255,255,255,.05);font-size:12px;color:#9CA3AF}
.src{font-size:9px;font-weight:700;margin-right:6px}
.card{background:#171C2C;border-radius:10px;padding:14px;margin-bottom:10px}
.ch{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px}
.tn{font-size:18px;font-weight:900;font-family:monospace}
.tc{font-size:10px;color:#6B7280;margin-top:2px}
.lv{background:rgba(0,200,122,.06);border:1px solid rgba(0,200,122,.2);border-radius:8px;padding:11px;margin:9px 0}
.lr{display:flex;justify-content:space-between;padding:3px 0;font-size:13px}
.tb{width:100%;font-size:11px;border-collapse:collapse;margin:6px 0}
.tb td{padding:3px 4px;color:#6B7280}
.sb{background:#0A0D14;border-radius:3px;height:4px;margin-top:3px}
.sf{height:100%;border-radius:3px;background:#C9A84C}
.sy{background:rgba(139,92,246,.06);border:1px solid rgba(139,92,246,.25);border-radius:10px;padding:13px;margin-bottom:10px}
.syt{font-size:10px;color:#8B5CF6;letter-spacing:3px;text-transform:uppercase;margin-bottom:7px}
.sytx{font-size:13px;line-height:1.8}
.ft{text-align:center;font-size:10px;color:#4B5563;margin-top:12px;line-height:1.9}
</style>"""

def col(v): return "g" if v>=0 else "r"
def sg(v): return "+" if v>=0 else ""
def pct(v): return f"{sg(v)}{v:.2f}%"

# ─── EMAIL 1 : BRIEF OUVERTURE 08h30 ─────────────────────────────────────────
def brief_ouverture():
    print("[BARAKA] === BRIEF OUVERTURE 08h30 ===")
    try:
        macro   = get_macro()
        ammc    = get_ammc_pubs()
        bn      = boursenews()
        tg      = telegram_bvc()
        bkam    = bkam_news()
        correl  = get_correlations_context(macro)
        n_bvc   = gnews("Bourse Casablanca 2026", 4)
        n_mac   = gnews("taux banque centrale Fed Reserve BCE 2026", 3)
        n_geo   = gnews("guerre conflit geopolitique mondial impact economie 2026", 3)
        n_usa   = gnews("Federal Reserve inflation USA economie 2026", 3)
        n_eur   = gnews("BCE Europe taux inflation recession 2026", 3)
        n_china = gnews("Chine economie commerce mondial 2026", 2)
        n_maroc = gnews("Maroc economie inflation BAM BDT 2026", 3)
        n_intl  = gnews("BFM Business Reuters Bloomberg marche mondial 2026", 3)
        now     = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        # Groq synthesis
        sp_c = macro.get("sp500",{}).get("c",0)
        cac_c = macro.get("cac40",{}).get("c",0)
        nik_c = macro.get("nikkei",{}).get("c",0)
        phos_c = macro.get("phosphate_idx",{}).get("c",0)
        eur_mad = macro.get("eur_mad",10.9)
        spread = macro.get("yield_spread",0)

        ctx = (
            f"Il est 08h30 Casablanca, BVC ouvre dans 1h.\n"
            f"=== MARCHÉS MONDIAUX NUIT ===\n"
            f"USD/MAD:{macro.get('usd_mad',10)} EUR/MAD:{eur_mad} | DXY:{macro.get('dxy',{}).get('c',0):+.2f}%\n"
            f"S&P500:{sp_c:+.2f}% | Nasdaq:{macro.get('nasdaq',{}).get('c',0):+.2f}% | "
            f"CAC40:{cac_c:+.2f}% | DAX:{macro.get('dax',{}).get('c',0):+.2f}% | Nikkei:{nik_c:+.2f}%\n"
            f"Or:{macro.get('gold',{}).get('c',0):+.2f}% | Brent:{macro.get('brent',{}).get('c',0):+.2f}% | "
            f"Phosphate:{phos_c:+.2f}%\n"
            f"US10Y:{macro.get('us10y',0)}% | Spread 10Y-2Y:{spread:+.3f}% | Fed:{macro.get('fed_rate',5.25)}%\n"
            f"=== CORRÉLATIONS BVC ===\n"
            f"{chr(10).join(correl)}\n"
            f"=== FONDAMENTAUX MAROC ===\n"
            f"AMMC aujourd hui: {[p['title'][:70] for p in ammc[:4]]}\n"
            f"BAM/Politique monetaire: {bkam.get('bam_news',[])}\n"
            f"Inflation Maroc: {bkam.get('inflation_news',[])}\n"
            f"BDT/Bons Tresor: {bkam.get('bdt_news',[])}\n"
            f"=== NEWS GEOPOLITIQUE MONDIALE ===\n"
            f"Géopolitique: {n_geo[:2]}\n"
            f"USA/Fed: {n_usa[:2]}\n"
            f"Europe/BCE: {n_eur[:2]}\n"
            f"Chine: {n_china[:1]}\n"
            f"Maroc: {n_maroc[:2]}\n"
            f"News BVC: {n_bvc[:3]}\n"
        )
        prompt = (
            ctx +
            "\nEn 5 phrases trader (NE PAS utiliser de markdown) :\n"
            "1. Ambiance marchés mondiaux cette nuit et corrélation directe avec la BVC\n"
            "2. Événement géopolitique/économique MONDIAL qui peut impacter le Maroc aujourd hui (inflation, matières premières, partenaires commerciaux)\n"
            "3. Impact USD/MAD et EUR/MAD sur les entreprises marocaines (pouvoir achat, marges, imports)\n"
            "4. Arbitrage BDT vs actions : où vont les salles de marché ce matin ?\n"
            "5. Publications AMMC + secteurs prioritaires à surveiller à l ouverture\n"
            "Français. Direct. Style trader professionnel."
        )
        synth = groq_call(prompt, 500) or "Analyse Groq indisponible — consultez les données ci-dessus."

        sp_p = macro.get("sp500",{}).get("p",0)
        go_p = macro.get("gold",{}).get("p",0)
        go_c = macro.get("gold",{}).get("c",0)
        br_p = macro.get("brent",{}).get("p",0)
        br_c = macro.get("brent",{}).get("c",0)
        mad  = macro.get("usd_mad",10.0)
        t10  = macro.get("us10y",0)
        fed  = macro.get("fed_rate",5.25)

        cac_c  = macro.get("cac40",{}).get("c",0)
        dax_c  = macro.get("dax",{}).get("c",0)
        nik_c2 = macro.get("nikkei",{}).get("c",0)
        nas_c  = macro.get("nasdaq",{}).get("c",0)
        cop_c  = macro.get("copper",{}).get("c",0)
        phos_c2= macro.get("phosphate_idx",{}).get("c",0)
        eur_mad2 = macro.get("eur_mad",10.9)
        spread2= macro.get("yield_spread",0)
        rec_risk = macro.get("recession_risk",False)

        macro_html = f"""
        <div style="margin-bottom:8px;font-size:9px;color:#6B7280;letter-spacing:2px">CHANGE</div>
        <div class="mg" style="margin-bottom:10px">
          <div class="mb"><div class="ml">USD/MAD</div><div class="mv b">{mad}</div></div>
          <div class="mb"><div class="ml">EUR/MAD</div><div class="mv b">{eur_mad2}</div></div>
          <div class="mb"><div class="ml">DXY</div><div class="mv {col(macro.get('dxy',{{'c':0}})['c'])}">{pct(macro.get('dxy',{{'c':0}})['c'])}</div></div>
        </div>
        <div style="margin-bottom:8px;font-size:9px;color:#6B7280;letter-spacing:2px">INDICES ACTIONS</div>
        <div class="mg" style="margin-bottom:10px">
          <div class="mb"><div class="ml">S&P 500</div><div class="mv {col(sp_c)}">{pct(sp_c)}</div></div>
          <div class="mb"><div class="ml">NASDAQ</div><div class="mv {col(nas_c)}">{pct(nas_c)}</div></div>
          <div class="mb"><div class="ml">CAC40</div><div class="mv {col(cac_c)}">{pct(cac_c)}</div></div>
          <div class="mb"><div class="ml">DAX</div><div class="mv {col(dax_c)}">{pct(dax_c)}</div></div>
          <div class="mb"><div class="ml">NIKKEI</div><div class="mv {col(nik_c2)}">{pct(nik_c2)}</div></div>
        </div>
        <div style="margin-bottom:8px;font-size:9px;color:#6B7280;letter-spacing:2px">MATIÈRES PREMIÈRES</div>
        <div class="mg" style="margin-bottom:10px">
          <div class="mb"><div class="ml">OR</div><div class="mv {col(go_c)}">{pct(go_c)}</div></div>
          <div class="mb"><div class="ml">BRENT</div><div class="mv {col(br_c)}">{pct(br_c)}</div></div>
          <div class="mb"><div class="ml">CUIVRE</div><div class="mv {col(cop_c)}">{pct(cop_c)}</div></div>
          <div class="mb"><div class="ml">PHOSPHATE</div><div class="mv {col(phos_c2)}">{pct(phos_c2)}</div></div>
        </div>
        <div style="margin-bottom:8px;font-size:9px;color:#6B7280;letter-spacing:2px">TAUX</div>
        <div class="mg">
          <div class="mb"><div class="ml">US 10Y</div><div class="mv b">{t10}%</div></div>
          <div class="mb"><div class="ml">Spread</div><div class="mv {'r' if spread2<0 else 'g'}">{spread2:+.3f}%</div></div>
          <div class="mb"><div class="ml">FED</div><div class="mv go">{fed}%</div></div>
          {'<div class="mb"><div class="ml">⚠️ RÉCESSION</div><div class="mv r">Courbe inv.</div></div>' if rec_risk else ''}
        </div>"""

        def ni(items, src, color="b"):
            if not items: return f'<div class="ni"><span class="src" style="color:#4B5563">{src}</span>Aucune news disponible</div>'
            return "".join(f'<div class="ni"><span class="src {color}">{src}</span>{n}</div>' for n in items)

        ammc_html = "".join(
            f'<div class="ni"><span class="src r">AMMC</span>{p["title"][:120]}'
            f'{" — <strong>"+p["ticker"]+"</strong>" if p.get("ticker") else ""}</div>'
            for p in ammc[:6]
        ) or '<div class="ni" style="color:#4B5563">Aucune publication aujourd\'hui</div>'

        tg_html = "".join(
            f'<div class="ni"><span class="src pu">TELEGRAM</span>{p["t"][:130]}</div>'
            for p in tg
        ) or '<div class="ni" style="color:#4B5563">Aucun buzz détecté</div>'

        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="w">
<div class="hdr">
  <div class="logo">BARAKA</div>
  <div class="sub">BRIEF OUVERTURE — {now}</div>
  <span class="bdg g" style="border-color:rgba(0,200,122,.3);background:rgba(0,200,122,.1)">🔔 BVC OUVRE DANS 1H</span>
</div>

<div class="sec"><div class="t">MACRO MONDIALE — NUIT</div>{macro_html}</div>

<div class="sy"><div class="syt">SYNTHÈSE BARAKA — GROQ AI</div><div class="sytx">{synth}</div></div>

<div class="sec">
  <div class="t">⚡ CORRÉLATIONS MARCHÉ MONDIAL → BVC</div>
  {"".join(f'<div class="ni"><span class="src go">→</span>{c}</div>' for c in correl) or '<div class="ni" style="color:#4B5563">Données en attente</div>'}
</div>

<div class="sec"><div class="t">PUBLICATIONS AMMC DU JOUR</div>{ammc_html}</div>

<div class="sec"><div class="t">NEWS BVC — BOURSENEWS</div>{ni(bn[:4],"BourseNews")}</div>

<div class="sec">
  <div class="t">GÉOPOLITIQUE MONDIALE</div>
  {ni(n_geo[:3],"🌍 Monde","r")}
  {ni(n_usa[:2],"🇺🇸 USA/Fed")}
  {ni(n_eur[:2],"🇪🇺 Europe")}
  {ni(n_china[:2],"🇨🇳 Chine")}
</div>

<div class="sec">
  <div class="t">MAROC — ÉCONOMIE & INFLATION</div>
  {ni(bkam.get("inflation_news",[])[:3],"📊 Inflation","r")}
  {ni(bkam.get("bdt_news",[])[:2],"🏛️ BDT")}
  {ni(n_maroc[:3],"🇲🇦 Maroc")}
  {ni(bkam.get("bam_news",[])[:2],"BAM")}
</div>

<div class="sec"><div class="t">NEWS BVC — BOURSENEWS</div>{ni(n_bvc[:3],"BVC")}{ni(n_intl[:3],"Intl")}</div>

<div class="sec"><div class="t">BUZZ TELEGRAM BVC</div>{tg_html}</div>

<div class="ft">Prochaine analyse : 12h00 — Entrées BVC avec AMMC + Technique<br>
<strong class="go">BARAKA v6 — 3 emails/jour</strong></div>
</div></body></html>"""

        send_email("BARAKA — BRIEF OUVERTURE BVC 08h30", html)
    except Exception as e:
        print(f"[BRIEF] {e}")
        send_email("BARAKA — BRIEF OUVERTURE 08h30",
            f"<div style='background:#0A0D14;color:#E8E4D6;padding:20px;font-family:monospace'>"
            f"<h2 style='color:#C9A84C'>BRIEF OUVERTURE {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</h2>"
            f"<p style='color:#FF4560'>{str(e)[:300]}</p></div>")

# ─── EMAIL 2 : ANALYSE + ENTRÉES 12h00 ───────────────────────────────────────
def analyse_entrees():
    print("[BARAKA] === ANALYSE + ENTRÉES 12h00 ===")
    try:
        bvc  = get_bvc_data()
        ammc = get_ammc_pubs()
        macro = get_macro()
        now  = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        # Macro pour scoring contextuel
        macro = get_macro()

        # Top 3 signaux avec score technique + macro sectoriel
        scored = sorted(
            [{"t":t,"sc":score(d,BVC.get(t,{}),macro),"d":d,"i":BVC.get(t,{})}
             for t,d in bvc.items() if d.get("close")],
            key=lambda x:-x["sc"]
        )[:3]

        # Volumes anormaux
        sm = smart_money(bvc)

        cards = ""
        for item in scored:
            t,d,info,sc = item["t"],item["d"],item["i"],item["sc"]
            close = d.get("close",0)
            rsi   = d.get("rsi",50)
            ammc_t = ammc_for(t, ammc)

            # Niveaux
            is_buy = d.get("macd",0) > d.get("macd_s",0) and rsi < 65
            if is_buy:
                target = round(close*1.06, 2)
                stop   = round(close*0.97, 2)
                dir_label, dir_col = "ACHAT", "#00C87A"
            else:
                target = round(close*0.95, 2)
                stop   = round(close*1.02, 2)
                dir_label, dir_col = "VENTE", "#FF4560"

            rr = round(abs(target-close)/abs(close-stop),2) if abs(close-stop)>0 else 0
            vr = round(d.get("volume",0)/info.get("v",1),1) if info.get("v",1)>0 else 0

            # Groq par ticker
            ammc_ctx = " | ".join([p["title"][:80] for p in ammc_t]) if ammc_t else "Aucune publication AMMC récente"
            # Context macro pour ce ticker
            brent_c = macro.get("brent",{}).get("c",0)
            gold_c  = macro.get("gold",{}).get("c",0)
            cac_c   = macro.get("cac40",{}).get("c",0)
            usd_mad = macro.get("usd_mad",10.0)
            phos_c  = macro.get("phosphate_idx",{}).get("c",0)
            sect    = info.get("s","")

            macro_ticker_ctx = ""
            if sect=="Mines" and gold_c!=0:
                macro_ticker_ctx = f"Or {gold_c:+.2f}% ce matin. "
            if sect in ["Energie","Transport"] and brent_c!=0:
                macro_ticker_ctx = f"Brent {brent_c:+.2f}%. "
            if sect=="Chimie" and phos_c!=0:
                macro_ticker_ctx = f"Phosphate {phos_c:+.2f}%, USD/MAD={usd_mad}. "
            if sect=="Banque":
                macro_ticker_ctx = f"CAC40 {cac_c:+.2f}%, spread 10Y-2Y={macro.get('yield_spread',0):+.3f}%. "

            prompt = (
                f"TITRE: {t} — {info.get('n','')} ({sect})\n"
                f"RSI={rsi:.0f}, MACD={'haussier' if d.get('macd',0)>d.get('macd_s',0) else 'baissier'}, "
                f"Cours={close:.2f} MAD, EMA20={d.get('ema20',0):.2f}, EMA50={d.get('ema50',0):.2f}, EMA200={d.get('ema200',0):.2f}\n"
                f"Volume: {d.get('volume',0):,} vs moyenne 90j {int(avg):,} (x{vr} — {'fort signal institutionnel' if vr>2 else 'normal'})\n"
                f"Contexte macro sectoriel: {macro_ticker_ctx or 'CAC40 '+str(cac_c)+chr(37)+', USD/MAD='+str(usd_mad)}\n"
                f"Score Baraka: {sc}/100 (technique + macro)\n"
                f"Publications AMMC: {ammc_ctx}\n\n"
                "2 phrases MAX — trader professionnel (sans markdown) :\n"
                "1. Catalyseur PRÉCIS technique + fondamental + macro pour entrer maintenant\n"
                "2. Risque principal à surveiller (niveau et condition de sortie)\n"
                "Français. Direct."
            )
            analyse = groq_call(prompt, 200) or "Signaux techniques alignés — confirmation AMMC disponible."

            ammc_pubs_html = ""
            if ammc_t:
                ammc_pubs_html = "<div style='margin-top:8px;padding:8px;background:rgba(0,100,255,.06);border-radius:6px'>"
                ammc_pubs_html += "<div style='font-size:9px;color:#60A5FA;margin-bottom:4px;letter-spacing:2px'>PUBLICATIONS AMMC</div>"
                for p in ammc_t[:3]:
                    ammc_pubs_html += f"<div style='font-size:10px;color:#9CA3AF;padding:2px 0'>📄 {p['title'][:110]}</div>"
                ammc_pubs_html += "</div>"

            tgt_pct = round((target-close)/close*100,1)
            stp_pct = round(abs(close-stop)/close*100,1)

            cards += f"""<div class="card" style="border-left:4px solid {dir_col}">
  <div class="ch">
    <div>
      <div class="tn" style="color:{dir_col}">{t}</div>
      <div class="tc">{info.get('n','')} — {info.get('s','')}</div>
    </div>
    <span style="background:{dir_col}15;color:{dir_col};border:1px solid {dir_col}40;font-size:10px;padding:3px 10px;border-radius:4px">{dir_label}</span>
  </div>
  <div class="lv">
    <div style="font-size:9px;color:#C9A84C;margin-bottom:7px;letter-spacing:2px">NIVEAUX DE TRADING</div>
    <div class="lr"><span style="color:#6B7280">💰 Entree</span><strong style="color:#E8E4D6">{close:.2f} MAD</strong></div>
    <div class="lr"><span style="color:#6B7280">🎯 Cible</span><strong style="color:#00C87A">{target:.2f} MAD ({sg(tgt_pct)}{tgt_pct}%)</strong></div>
    <div class="lr"><span style="color:#6B7280">🛑 Stop</span><strong style="color:#FF4560">{stop:.2f} MAD (-{stp_pct}%)</strong></div>
    <div class="lr"><span style="color:#6B7280">Risque/Rendement</span><strong style="color:#C9A84C">R/R {rr}</strong></div>
  </div>
  <table class="tb"><tr>
    <td>RSI</td><td style="color:{'#FF4560' if rsi>70 else '#00C87A' if rsi<35 else '#C9A84C'};font-weight:700">{rsi:.0f}</td>
    <td>MACD</td><td style="color:{'#00C87A' if d.get('macd',0)>d.get('macd_s',0) else '#FF4560'}">{'Haussier' if d.get('macd',0)>d.get('macd_s',0) else 'Baissier'}</td>
    <td>Volume</td><td style="color:{'#00C87A' if vr>2 else '#C9A84C'}">x{vr}</td>
  </tr><tr>
    <td>ADX</td><td style="color:#9CA3AF">{d.get('adx',0):.0f}</td>
    <td>EMA200</td><td style="color:{'#00C87A' if close>d.get('ema200',0)>0 else '#FF4560'}">{'Au-dessus' if close>d.get('ema200',0)>0 else 'En-dessous'}</td>
    <td>Score</td><td style="color:#C9A84C;font-weight:700">{sc}/100</td>
  </tr></table>
  {ammc_pubs_html}
  <div style="font-size:12px;color:#9CA3AF;margin-top:8px;line-height:1.7">{analyse}</div>
  <div style="margin-top:8px">
    <div style="display:flex;justify-content:space-between;font-size:10px;margin-bottom:2px">
      <span style="color:#6B7280">Score Baraka (technique + macro)</span>
      <span style="color:#C9A84C;font-weight:700">{sc}/100</span>
    </div>
    <div class="sb"><div class="sf" style="width:{sc}%"></div></div>
    <div style="font-size:9px;color:#4B5563;margin-top:3px">
      {'🟢 Momentum fort' if sc>=80 else ('🟡 Signal modéré' if sc>=65 else '⚪ Signal faible')} — 
      {'Technique + macro alignés' if sc>=75 else 'Technique seul'}
    </div>
  </div>
</div>"""

        if not cards:
            cards = '<div style="text-align:center;padding:20px;color:#6B7280">Aucun signal qualifié ce matin — attendre confirmation.</div>'

        # Volumes anormaux
        sm_html = ""
        if sm:
            sm_rows = "".join(f"""<div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.05);font-size:12px">
  <span style="color:#F59E0B;font-weight:700;font-family:monospace">{s['t']}</span>
  <span style="color:#9CA3AF">{s['n']}</span>
  <span style="color:#F59E0B;font-weight:700">x{s['vr']}</span>
  <span class="{col(s['chg'])}">{pct(s['chg'])}</span>
</div>""" for s in sm[:5])
            sm_html = f'<div class="sec"><div class="t">⚡ VOLUMES ANORMAUX</div>{sm_rows}</div>'

        sp_c = macro.get("sp500",{}).get("c",0)
        mad  = macro.get("usd_mad",10.0)

        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="w">
<div class="hdr">
  <div class="logo">BARAKA</div>
  <div class="sub">ANALYSE + ENTRÉES — {now}</div>
  <span class="bdg go" style="border-color:rgba(201,168,76,.3);background:rgba(201,168,76,.1)">📊 {len(scored)} RECOMMANDATIONS</span>
</div>

<div style="display:flex;gap:8px;margin-bottom:10px">
  <div class="mb" style="background:#171C2C;border-radius:8px;padding:9px;text-align:center;flex:1"><div class="ml">S&P500</div><div class="mv {col(sp_c)}">{pct(sp_c)}</div></div>
  <div class="mb" style="background:#171C2C;border-radius:8px;padding:9px;text-align:center;flex:1"><div class="ml">USD/MAD</div><div class="mv b">{mad}</div></div>
  <div class="mb" style="background:#171C2C;border-radius:8px;padding:9px;text-align:center;flex:1"><div class="ml">Titres BVC</div><div class="mv go">{len(bvc)}/32</div></div>
</div>

<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px">RECOMMANDATIONS — TECHNIQUE + AMMC INTÉGRÉ</div>
{cards}
{sm_html}

<div class="ft">Prochaine analyse : 15h30 — Smart Money & Paris Demain<br>
<strong class="go">Max 3 trades/jour — Confirmez manuellement avant d'entrer</strong></div>
</div></body></html>"""

        send_email("BARAKA — ANALYSE + ENTRÉES 12h00", html)
    except Exception as e:
        print(f"[ANALYSE] {e}")
        send_email("BARAKA — ANALYSE 12h00",
            f"<div style='background:#0A0D14;color:#E8E4D6;padding:20px;font-family:monospace'>"
            f"<h2 style='color:#C9A84C'>ANALYSE {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</h2>"
            f"<p style='color:#FF4560'>{str(e)[:300]}</p></div>")

# ─── EMAIL 3 : POST-CLÔTURE 15h30 ────────────────────────────────────────────
def post_cloture():
    print("[BARAKA] === POST-CLÔTURE 15h30 ===")
    try:
        bvc  = get_bvc_data()
        ammc = get_ammc_pubs()
        news = gnews("Bourse Casablanca cloture 2026", 4)
        now  = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        sm = smart_money(bvc)
        top_demain = sorted(
            [{"t":t,"sc":score(d,BVC.get(t,{})),"d":d}
             for t,d in bvc.items() if d.get("close")],
            key=lambda x:-x["sc"]
        )[:5]

        # Groq analyse
        sm_ctx = "\n".join([f"{s['t']}: vol x{s['vr']}, {s['chg']:+.2f}%, RSI={s['rsi']:.0f}" for s in sm[:5]])
        macro_pc = get_macro()
        correl_pc = get_correlations_context(macro_pc)
        prompt = (
            f"Post-cloture BVC {datetime.date.today().strftime('%d/%m/%Y')}.\n"
            f"SMART MONEY (base moyenne 90j):\n{sm_ctx or 'Aucun mouvement anormal'}\n"
            f"CORRÉLATIONS MARCHÉ: {correl_pc[:3]}\n"
            f"USD/MAD:{macro_pc.get('usd_mad',10)} | Brent:{macro_pc.get('brent',{}).get('c',0):+.2f}% | "
            f"Or:{macro_pc.get('gold',{}).get('c',0):+.2f}% | CAC40:{macro_pc.get('cac40',{}).get('c',0):+.2f}%\n"
            f"Spread 10Y-2Y:{macro_pc.get('yield_spread',0):+.3f}% ({'INVERSION=danger' if macro_pc.get('recession_risk') else 'OK'})\n"
            f"TOP SIGNAUX DEMAIN: {[x['t'] for x in top_demain[:3]]}\n"
            f"NEWS: {news[:2]}\n\n"
            "5 phrases trader (sans markdown) :\n"
            "1. Où est allé le smart money aujourd hui et POURQUOI (lien avec macro/news)\n"
            "2. Arbitrage BDT vs actions : les salles de marche ont-elles vendu des actions pour aller sur les bons du trésor ?\n"
            "3. Signal technique qui se prépare pour demain matin\n"
            "4. Les 2 titres à surveiller demain à l ouverture avec prix d entrée précis\n"
            "5. Signal d alarme (si ça se passe demain = ne pas entrer du tout)\n"
            "Français. Direct. Professionnel."
        )
        synth = groq_call(prompt, 500) or "Analyse en cours..."

        # SM cards
        sm_cards = ""
        for s in sm[:5]:
            t = s["t"]
            info = BVC.get(t,{})
            ammc_t = ammc_for(t, ammc)
            ammc_line = f"<div style='font-size:10px;color:#60A5FA;margin-top:3px'>📄 {ammc_t[0]['title'][:100]}</div>" if ammc_t else ""
            avg90_disp = f"{int(s.get('avg90',0)):,}" if s.get('avg90',0) > 0 else "N/A"
            sm_cards += f"""<div class="card" style="border-left:3px solid #F59E0B">
  <div style="display:flex;justify-content:space-between">
    <span style="color:#F59E0B;font-weight:900;font-family:monospace;font-size:16px">{t}</span>
    <span style="color:#F59E0B;font-weight:700">VOLUME x{s['vr']}</span>
  </div>
  <div style="color:#9CA3AF;font-size:11px">{info.get('n','')} — {info.get('s','')}</div>
  <div style="font-size:12px;margin-top:5px;display:flex;gap:14px;flex-wrap:wrap">
    <span style="color:#6B7280">Cloture <strong style="color:#E8E4D6">{s['c']:.2f} MAD</strong></span>
    <span class="{col(s['chg'])}" style="font-weight:700">{pct(s['chg'])}</span>
    <span style="color:#9CA3AF">RSI {s['rsi']:.0f}</span>
    <span style="color:#6B7280;font-size:10px">Moy.90j: {avg90_disp}</span>
  </div>
  {ammc_line}
</div>"""

        # Paris demain
        paris = ""
        for item in top_demain[:3]:
            t = item["t"]
            d = item["d"]
            info = BVC.get(t,{})
            close = d.get("close",0)
            target = round(close*1.05,2)
            stop   = round(close*0.97,2)
            paris += f"""<div style="background:#171C2C;border-radius:8px;padding:10px;margin-bottom:7px">
  <div style="display:flex;justify-content:space-between">
    <span style="color:#C9A84C;font-weight:900;font-family:monospace">{t}</span>
    <span style="color:#9CA3AF;font-size:11px">{info.get('n','')} — Score {item['sc']}/100</span>
  </div>
  <div style="font-size:11px;color:#6B7280;margin-top:5px">
    Entree: <strong style="color:#E8E4D6">{close:.2f}</strong> —
    Cible: <strong style="color:#00C87A">{target:.2f}</strong> —
    Stop: <strong style="color:#FF4560">{stop:.2f}</strong>
  </div>
</div>"""

        news_html = "".join(f'<div class="ni">{n}</div>' for n in news[:4])

        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="w">
<div class="hdr">
  <div class="logo">BARAKA</div>
  <div class="sub">POST-CLÔTURE — {now}</div>
  <span class="bdg" style="color:#F59E0B;border-color:rgba(245,158,11,.3);background:rgba(245,158,11,.1)">🔍 {len(sm)} MOUVEMENTS SMART MONEY</span>
</div>

<div class="sy"><div class="syt">ANALYSE BARAKA — GROQ AI</div><div class="sytx">{synth}</div></div>

<div class="sec">
  <div class="t">⚡ SMART MONEY — OÙ EST PARTI L'ARGENT</div>
  {sm_cards or '<div style="color:#6B7280;font-size:12px">Aucun mouvement anormal détecté</div>'}
</div>

<div class="sec">
  <div class="t">🎯 PARIS POUR DEMAIN — NIVEAUX D'ENTRÉE</div>
  {paris}
</div>

<div class="sec"><div class="t">NEWS CLÔTURE</div>{news_html}</div>

<div class="ft">Prochain email : demain 08h30 — Brief Ouverture<br>
<strong class="go">Baraka analyse pendant que tu dors</strong></div>
</div></body></html>"""

        send_email("BARAKA — POST-CLÔTURE + SMART MONEY 15h30", html)
    except Exception as e:
        print(f"[CLOTURE] {e}")
        send_email("BARAKA — POST-CLÔTURE 15h30",
            f"<div style='background:#0A0D14;color:#E8E4D6;padding:20px;font-family:monospace'>"
            f"<h2 style='color:#C9A84C'>CLÔTURE {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</h2>"
            f"<p style='color:#FF4560'>{str(e)[:300]}</p></div>")

# ─── FLASK KEEP-ALIVE + TRIGGER ──────────────────────────────────────────────
def start_flask():
    try:
        from flask import Flask
        app = Flask(__name__)
        JOBS = {"brief": brief_ouverture, "analyse": analyse_entrees, "cloture": post_cloture}

        @app.route("/")
        def idx(): return f"BARAKA v6 — ACTIVE — {datetime.datetime.now().strftime('%H:%M:%S')}", 200

        @app.route("/ping")
        def ping(): return "OK", 200

        @app.route("/trigger/<name>")
        def trigger(name):
            if name not in JOBS: return f"Options: {list(JOBS.keys())}", 400
            threading.Thread(target=JOBS[name], daemon=True).start()
            return f"'{name}' declenche — email dans 2 min.", 200

        port = int(os.environ.get("PORT", 8080))
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"[FLASK] {e}")

# ─── SCHEDULER SIMPLE UTC ────────────────────────────────────────────────────
def run_scheduler():
    print("""
╔═══════════════════════════════════════════════╗
║  BARAKA v6.0 — BVC — 3 emails/jour            ║
╠═══════════════════════════════════════════════╣
║  07:30 UTC → 08:30 Casa — BRIEF OUVERTURE     ║
║  11:00 UTC → 12:00 Casa — ANALYSE + ENTRÉES    ║
║  14:30 UTC → 15:30 Casa — POST-CLÔTURE        ║
╚═══════════════════════════════════════════════╝
    """)

    threading.Thread(target=start_flask, daemon=True).start()
    fired = {}

    while True:
        try:
            now = datetime.datetime.utcnow()
            today = str(now.date())
            h, m, wd = now.hour, now.minute, now.weekday()

            if h == 0 and m == 0:
                fired = {}

            if wd < 5:  # Lundi-Vendredi seulement
                if h==7 and 30<=m<45 and f"brief_{today}" not in fired:
                    fired[f"brief_{today}"] = True
                    threading.Thread(target=brief_ouverture, daemon=True).start()

                elif h==11 and 0<=m<15 and f"analyse_{today}" not in fired:
                    fired[f"analyse_{today}"] = True
                    threading.Thread(target=analyse_entrees, daemon=True).start()

                elif h==14 and 30<=m<45 and f"cloture_{today}" not in fired:
                    fired[f"cloture_{today}"] = True
                    threading.Thread(target=post_cloture, daemon=True).start()

        except Exception as e:
            print(f"[SCHEDULER] {e}")

        time.sleep(30)


if __name__ == "__main__":
    run_scheduler()
