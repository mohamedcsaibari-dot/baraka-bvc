"""
BARAKA v5.0 - Wall Street Level BVC Trading Agent
24h/24 · 7j/7 · Smart Filter · PDF AMMC · Google News
Telegram · Facebook · Volume Profile · Macro Global · Groq LLM
"""

import schedule, time, datetime, json, os, requests, smtplib, re, hashlib, io
import numpy as np
import yfinance as yf
from tradingview_ta import TA_Handler, Interval
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
from urllib.parse import quote

try:
    import pdfplumber
    PDF_OK = True
except:
    PDF_OK = False

try:
    from groq import Groq
    GROQ_OK = True
except:
    GROQ_OK = False

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
GMAIL_USER     = os.environ.get("GMAIL_USER", "mohamed.csaibari@gmail.com")
GMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
TO_EMAIL       = "mohamed.csaibari@gmail.com"
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")

F = {
    "trades":   "trade_log.json",
    "learn":    "baraka_learnings.json",
    "events":   "baraka_events.json",
    "pdf":      "baraka_pdf_cache.json",
    "news":     "baraka_news_cache.json",
    "social":   "baraka_social_cache.json",
    "pending":  "baraka_pending.json",
    "night":    "baraka_night_thesis.json",
    "targets":  "baraka_price_targets.json",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
AMMC_URL = "https://www.ammc.ma/fr/communiques-presse-emetteurs"
VOL_THRESHOLD  = 2.5
URGENCY_LIMIT  = 85   # Score >= 85 → email immédiat, sinon queued

# ═══════════════════════════════════════════════════════════════════════════════
# WATCHLIST BVC COMPLÈTE
# ═══════════════════════════════════════════════════════════════════════════════
BVC = {
    "ATW":    {"n":"Attijariwafa Bank",        "s":"Banque",       "v":85000, "mc":"large","bam":True, "br":False,"ph":False,"yf":"ATW.CS",  "q":"Attijariwafa Bank résultats"},
    "BCP":    {"n":"Banque Centrale Pop.",      "s":"Banque",       "v":60000, "mc":"large","bam":True, "br":False,"ph":False,"yf":"BCP.CS",  "q":"Banque Populaire Maroc"},
    "BMCE":   {"n":"Bank of Africa",            "s":"Banque",       "v":70000, "mc":"large","bam":True, "br":False,"ph":False,"yf":"BMCE.CS", "q":"Bank of Africa BMCE Maroc"},
    "CIH":    {"n":"CIH Bank",                  "s":"Banque",       "v":45000, "mc":"mid",  "bam":True, "br":False,"ph":False,"yf":"CIH.CS",  "q":"CIH Bank Maroc"},
    "CDM":    {"n":"Credit du Maroc",           "s":"Banque",       "v":18000, "mc":"mid",  "bam":True, "br":False,"ph":False,"yf":"CDM.CS",  "q":"Credit du Maroc"},
    "BMCI":   {"n":"BMCI",                      "s":"Banque",       "v":12000, "mc":"mid",  "bam":True, "br":False,"ph":False,"yf":"BMCI.CS", "q":"BMCI BNP Maroc"},
    "CFG":    {"n":"CFG Bank",                  "s":"Banque",       "v":8000,  "mc":"small","bam":True, "br":False,"ph":False,"yf":"CFG.CS",  "q":"CFG Bank Maroc"},
    "WAA":    {"n":"Wafa Assurance",            "s":"Assurance",    "v":6000,  "mc":"mid",  "bam":True, "br":False,"ph":False,"yf":"WAA.CS",  "q":"Wafa Assurance"},
    "ATL":    {"n":"Atlanta",                   "s":"Assurance",    "v":5000,  "mc":"small","bam":True, "br":False,"ph":False,"yf":"ATL.CS",  "q":"Atlanta Assurance Maroc"},
    "SAH":    {"n":"Saham Assurance",           "s":"Assurance",    "v":4000,  "mc":"small","bam":True, "br":False,"ph":False,"yf":"SAH.CS",  "q":"Saham Assurance Maroc"},
    "MCB":    {"n":"Mutuelle Centrale Marocaine","s":"Assurance",   "v":2000,  "mc":"small","bam":True, "br":False,"ph":False,"yf":"MCB.CS",  "q":"Mutuelle Centrale Marocaine"},
    "IAM":    {"n":"Maroc Telecom",             "s":"Telecom",      "v":120000,"mc":"large","bam":False,"br":False,"ph":False,"yf":"IAM.CS",  "q":"Maroc Telecom résultats"},
    "HPS":    {"n":"HighTech Payment Systems",  "s":"Tech",         "v":15000, "mc":"mid",  "bam":False,"br":False,"ph":False,"yf":"HPS.CS",  "q":"HPS paiement Maroc"},
    "M2M":    {"n":"M2M Group",                 "s":"Tech",         "v":2500,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"M2M.CS",  "q":"M2M Group Maroc"},
    "IB":     {"n":"Involys",                   "s":"Tech",         "v":3000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"IB.CS",   "q":"Involys informatique Maroc"},
    "S2M":    {"n":"S2M",                       "s":"Tech",         "v":2000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"S2M.CS",  "q":"S2M paiement Maroc"},
    "OCP":    {"n":"OCP Group",                 "s":"Chimie",       "v":95000, "mc":"large","bam":False,"br":False,"ph":True, "yf":"OCP.CS",  "q":"OCP phosphate Maroc résultats"},
    "SMI":    {"n":"SMI",                       "s":"Mines",        "v":8000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"SMI.CS",  "q":"SMI mines Maroc argent"},
    "CMT":    {"n":"Cie Miniere Touissit",      "s":"Mines",        "v":5000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"CMT.CS",  "q":"Compagnie Miniere Touissit"},
    "MANAGEM":{"n":"Managem",                   "s":"Mines",        "v":12000, "mc":"mid",  "bam":False,"br":False,"ph":False,"yf":"MNG.CS",  "q":"Managem mines Maroc"},
    "SMH":    {"n":"Samine",                    "s":"Mines",        "v":3000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"SMH.CS",  "q":"Samine mines"},
    "ZELLIDJA":{"n":"Zellidja",                 "s":"Mines",        "v":1500,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"ZLD.CS",  "q":"Zellidja mines plomb"},
    "SNEP":   {"n":"SNEP",                      "s":"Chimie",       "v":4000,  "mc":"small","bam":False,"br":False,"ph":True, "yf":"SNP.CS",  "q":"SNEP chimie Maroc"},
    "SCE":    {"n":"Ste Cherifienne Engrais",   "s":"Chimie",       "v":3500,  "mc":"small","bam":False,"br":False,"ph":True, "yf":"SCE.CS",  "q":"Societe Cherifienne Engrais"},
    "FERTIMA":{"n":"Fertima",                   "s":"Chimie",       "v":2500,  "mc":"small","bam":False,"br":False,"ph":True, "yf":"FER.CS",  "q":"Fertima Maroc engrais"},
    "ADH":    {"n":"Addoha",                    "s":"Immobilier",   "v":35000, "mc":"mid",  "bam":True, "br":False,"ph":False,"yf":"ADH.CS",  "q":"Addoha immobilier Maroc"},
    "ALM":    {"n":"Alliances",                 "s":"Immobilier",   "v":15000, "mc":"mid",  "bam":True, "br":False,"ph":False,"yf":"ALM.CS",  "q":"Alliances Developpement Immobilier"},
    "RDS":    {"n":"Residences Dar Saada",      "s":"Immobilier",   "v":8000,  "mc":"small","bam":True, "br":False,"ph":False,"yf":"RDS.CS",  "q":"Residences Dar Saada"},
    "BALIMA": {"n":"Balima",                    "s":"Immobilier",   "v":2000,  "mc":"small","bam":True, "br":False,"ph":False,"yf":"BAL.CS",  "q":"Balima immobilier Maroc"},
    "HOL":    {"n":"Holcim Maroc",              "s":"Construction", "v":12000, "mc":"mid",  "bam":False,"br":False,"ph":False,"yf":"HOL.CS",  "q":"Holcim Maroc ciment"},
    "CMA":    {"n":"Ciments du Maroc",          "s":"Construction", "v":10000, "mc":"mid",  "bam":False,"br":False,"ph":False,"yf":"CMA.CS",  "q":"Ciments du Maroc"},
    "LHM":    {"n":"LafargeHolcim Maroc",       "s":"Construction", "v":9000,  "mc":"mid",  "bam":False,"br":False,"ph":False,"yf":"LHM.CS",  "q":"LafargeHolcim Maroc"},
    "LABEL":  {"n":"Label Vie",                 "s":"Distribution", "v":9000,  "mc":"mid",  "bam":False,"br":False,"ph":False,"yf":"LBV.CS",  "q":"Label Vie supermarché Maroc"},
    "FENIE":  {"n":"Fenie Brossette",           "s":"Distribution", "v":3500,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"FBR.CS",  "q":"Fenie Brossette"},
    "STOKVIS":{"n":"Stokvis Nord Afrique",      "s":"Distribution", "v":2000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"STK.CS",  "q":"Stokvis Nord Afrique"},
    "LAC":    {"n":"Lesieur Cristal",           "s":"Agro",         "v":11000, "mc":"mid",  "bam":False,"br":True, "ph":False,"yf":"LAC.CS",  "q":"Lesieur Cristal huile Maroc"},
    "DARI":   {"n":"Dari Couspate",             "s":"Agro",         "v":4000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"DAR.CS",  "q":"Dari Couspate pates"},
    "COSUMAR":{"n":"Cosumar",                   "s":"Agro",         "v":8000,  "mc":"mid",  "bam":False,"br":False,"ph":False,"yf":"CSR.CS",  "q":"Cosumar sucre Maroc"},
    "OULMES": {"n":"Eaux Minerales Oulmes",     "s":"Agro",         "v":4000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"OUL.CS",  "q":"Oulmes eau minerale"},
    "UNIMER": {"n":"Unimer",                    "s":"Agro",         "v":3000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"UNI.CS",  "q":"Unimer Maroc"},
    "TMA":    {"n":"Total Maroc",               "s":"Energie",      "v":7000,  "mc":"mid",  "bam":False,"br":True, "ph":False,"yf":"TMA.CS",  "q":"Total Maroc energie carburant"},
    "TAQA":   {"n":"Taqa Morocco",              "s":"Energie",      "v":8000,  "mc":"mid",  "bam":False,"br":True, "ph":False,"yf":"TQA.CS",  "q":"Taqa Morocco electricite"},
    "SRM":    {"n":"Sonasid",                   "s":"Siderurgie",   "v":6000,  "mc":"mid",  "bam":False,"br":True, "ph":False,"yf":"SRM.CS",  "q":"Sonasid acier sidérurgie Maroc"},
    "CTM":    {"n":"CTM",                       "s":"Transport",    "v":5000,  "mc":"small","bam":False,"br":True, "ph":False,"yf":"CTM.CS",  "q":"CTM transport voyageurs Maroc"},
    "TIMAR":  {"n":"Timar",                     "s":"Transport",    "v":1500,  "mc":"small","bam":False,"br":True, "ph":False,"yf":"TMR.CS",  "q":"Timar transport logistique"},
    "LBV":    {"n":"Lydec",                     "s":"Services",     "v":5000,  "mc":"mid",  "bam":False,"br":False,"ph":False,"yf":"LYD.CS",  "q":"Lydec eau electricite Casablanca"},
    "AFMA":   {"n":"Afma",                      "s":"Services",     "v":2500,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"AFM.CS",  "q":"Afma courtage assurance"},
    "RIS":    {"n":"Risma",                     "s":"Tourisme",     "v":5000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"RIS.CS",  "q":"Risma Accor hotel Maroc"},
    "SOTHEMA":{"n":"Sothema",                   "s":"Pharma",       "v":6000,  "mc":"mid",  "bam":False,"br":False,"ph":False,"yf":"SOT.CS",  "q":"Sothema laboratoire pharmaceutique"},
    "PROMOPH":{"n":"Promopharm",                "s":"Pharma",       "v":2500,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"PRM.CS",  "q":"Promopharm Maroc"},
    "PHARM":  {"n":"Pharma 5",                  "s":"Pharma",       "v":3000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"PH5.CS",  "q":"Pharma 5 Maroc"},
    "EQDOM":  {"n":"Eqdom",                     "s":"Credit Conso", "v":4000,  "mc":"small","bam":True, "br":False,"ph":False,"yf":"EQD.CS",  "q":"Eqdom credit consommation"},
    "SOFAC":  {"n":"Sofac",                     "s":"Credit Conso", "v":3000,  "mc":"small","bam":True, "br":False,"ph":False,"yf":"SOF.CS",  "q":"Sofac credit auto"},
    "SALAF":  {"n":"Salafin",                   "s":"Credit Conso", "v":3500,  "mc":"small","bam":True, "br":False,"ph":False,"yf":"SAL.CS",  "q":"Salafin credit"},
    "TASLIF": {"n":"Taslif",                    "s":"Credit Conso", "v":1500,  "mc":"small","bam":True, "br":False,"ph":False,"yf":"TSL.CS",  "q":"Taslif"},
    "ACRED":  {"n":"Acred",                     "s":"Credit Conso", "v":2000,  "mc":"small","bam":True, "br":False,"ph":False,"yf":"ACR.CS",  "q":"Acred credit"},
    "DIAC":   {"n":"Diac Salaf",                "s":"Credit Conso", "v":1000,  "mc":"small","bam":True, "br":False,"ph":False,"yf":"DIA.CS",  "q":"Diac Salaf"},
    "MPARK":  {"n":"Maroc Leasing",             "s":"Leasing",      "v":3000,  "mc":"small","bam":True, "br":False,"ph":False,"yf":"MPK.CS",  "q":"Maroc Leasing"},
    "DLM":    {"n":"Delattre Levivier Maroc",   "s":"Industrie",    "v":3000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"DLM.CS",  "q":"Delattre Levivier Maroc"},
    "NEXANS": {"n":"Nexans Maroc",              "s":"Industrie",    "v":3000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"NEX.CS",  "q":"Nexans Maroc cable"},
    "MAGHREB":{"n":"Maghreb Oxygene",           "s":"Industrie",    "v":2000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"MAG.CS",  "q":"Maghreb Oxygene gaz"},
    "STROC":  {"n":"Stroc Industrie",           "s":"Industrie",    "v":2000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"STR.CS",  "q":"Stroc Industrie Maroc"},
    "LGMC":   {"n":"Longometal",                "s":"Industrie",    "v":2000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"LGM.CS",  "q":"Longometal acier Maroc"},
    "COLOROB":{"n":"Colorobbia Maroc",          "s":"Industrie",    "v":1500,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"COL.CS",  "q":"Colorobbia Maroc"},
    "FBR":    {"n":"Fipar Holding",             "s":"Holding",      "v":4000,  "mc":"mid",  "bam":False,"br":False,"ph":False,"yf":"FIP.CS",  "q":"Fipar Holding ONA"},
    "ENNAKL": {"n":"Ennakl",                    "s":"Automobile",   "v":2000,  "mc":"small","bam":False,"br":True, "ph":False,"yf":"ENN.CS",  "q":"Ennakl automobile Maroc"},
    "MED":    {"n":"Meditel",                   "s":"Telecom",      "v":2000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"MED.CS",  "q":"Meditel Orange Maroc telecom"},
    "SDLT":   {"n":"Sodetel",                   "s":"Telecom",      "v":1000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"SDL.CS",  "q":"Sodetel telecom"},
    "SNABT":  {"n":"Sna Btp",                   "s":"Construction", "v":1500,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"SNA.CS",  "q":"SNA BTP travaux"},
    "AFRIC":  {"n":"Africa Industries",         "s":"Industrie",    "v":1000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"AFR.CS",  "q":"Africa Industries Maroc"},
}

# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 1 — SMART FILTER & PENDING QUEUE
# ═══════════════════════════════════════════════════════════════════════════════

URGENCY_MAP = {
    # CRITIQUE >= 85 → email immédiat
    "smart_money":          92,
    "war_conflict":         99,
    "commodity_crash_4pct": 90,
    "rate_surprise_bam":    95,
    "rate_surprise_fed":    88,
    "vix_extreme_35":       88,
    "profit_warning_bvc":   90,
    "circuit_breaker_bvc":  99,
    "ipo_bvc":              86,
    "major_sanctions":      94,
    # NON-CRITIQUE < 85 → queued pour prochain mail programmé
    "volume_2x":            55,
    "macro_shift_normal":   60,
    "commodity_move_2pct":  62,
    "news_company_positive":50,
    "news_company_negative":65,
    "rumeur_consistante":   70,
    "pdf_analysis_done":    40,
    "price_target_updated": 45,
    "social_buzz":          52,
    "bam_news_minor":       58,
    "ammc_publication":     60,
}

# Mots-clés déclencheurs d'urgence absolue
URGENCY_KEYWORDS = {
    "war_conflict":    ["guerre","war","attentat","conflit armé","bombardement","invasion","coup d'état"],
    "rate_surprise_bam":  ["bank al-maghrib annonce","bam réduit","bam hausse","taux directeur surprise","décision urgente bam"],
    "rate_surprise_fed":  ["fed emergency","federal reserve surprise","fomc emergency","fed cuts","powell emergency"],
    "profit_warning_bvc": ["profit warning","avertissement sur résultats","révision à la baisse des prévisions","perte inattendue"],
    "circuit_breaker_bvc":["suspension de cotation","cotation suspendue","circuit breaker bvc"],
    "ipo_bvc":            ["introduction en bourse","ipo bvc","nouvelles cotations","premier jour de cotation"],
    "major_sanctions":    ["sanctions","embargo","gel des avoirs"],
}

def load_pending():
    if os.path.exists(F["pending"]):
        with open(F["pending"],"r",encoding="utf-8") as f: return json.load(f)
    return {"items":[],"last_flush":""}

def save_pending(data):
    with open(F["pending"],"w",encoding="utf-8") as f: json.dump(data,f,indent=2,ensure_ascii=False)

def add_to_pending(category, content, urgency_score=50, ticker=None):
    """Ajoute un élément à la file d'attente pour le prochain mail programmé"""
    if urgency_score >= URGENCY_LIMIT:
        return  # Ne pas ajouter les urgences ici
    p = load_pending()
    p["items"].append({
        "category":    category,
        "content":     content,
        "urgency":     urgency_score,
        "ticker":      ticker,
        "added_at":    str(datetime.datetime.now()),
    })
    # Garder max 100 items en attente
    p["items"] = sorted(p["items"], key=lambda x: -x["urgency"])[:100]
    save_pending(p)

def flush_pending():
    """Récupère et vide la file d'attente"""
    p = load_pending()
    items = p.get("items",[])
    p["items"] = []
    p["last_flush"] = str(datetime.datetime.now())
    save_pending(p)
    return items

def compute_urgency(event_type, magnitude=1.0, keywords_found=None):
    """Calcule le score d'urgence d'un événement"""
    base = URGENCY_MAP.get(event_type, 50)
    # Bonus magnitude
    bonus = min(10, magnitude * 2)
    # Bonus keywords critiques
    kw_bonus = 0
    if keywords_found:
        for kw_type, kw_list in URGENCY_KEYWORDS.items():
            if any(kw in " ".join(keywords_found).lower() for kw in kw_list):
                kw_bonus = 15
                break
    return min(100, base + bonus + kw_bonus)


def groq_call(prompt, max_tokens=400, temp=0.25):
    """Appel Groq centralisé"""
    if not GROQ_OK or not GROQ_API_KEY:
        return ""
    try:
        client = Groq(api_key=GROQ_API_KEY)
        resp   = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role":"user","content":prompt}],
            max_tokens=max_tokens,
            temperature=temp,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[GROQ] {e}")
        return ""


def groq_json(prompt, max_tokens=1200):
    """Appel Groq qui retourne du JSON parsé"""
    raw = groq_call(prompt, max_tokens=max_tokens, temp=0.2)
    try:
        clean = raw.replace("```json","").replace("```","").strip()
        start = clean.find("{"); end = clean.rfind("}")+1
        if start >= 0 and end > start:
            return json.loads(clean[start:end])
    except: pass
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 2 — AMMC PDF ANALYZER
# ═══════════════════════════════════════════════════════════════════════════════

def load_pdf_cache():
    if os.path.exists(F["pdf"]):
        with open(F["pdf"],"r",encoding="utf-8") as f: return json.load(f)
    return {"analyzed":{},"last_scan":"","price_targets":{}}

def save_pdf_cache(data):
    with open(F["pdf"],"w",encoding="utf-8") as f: json.dump(data,f,indent=2,ensure_ascii=False)

def scrape_ammc_publications():
    """Scrape toutes les publications AMMC 2026 depuis communiques-presse-emetteurs"""
    publications = []
    try:
        for page in range(0, 5):
            url = f"{AMMC_URL}?page={page}" if page > 0 else AMMC_URL
            r   = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200: break
            soup = BeautifulSoup(r.text, "html.parser")

            # Chercher les liens PDF dans la page
            for link in soup.find_all("a", href=True):
                href = link["href"]
                text = link.get_text(strip=True)
                if not text or len(text) < 5: continue

                # Filtrer 2026
                parent_text = ""
                parent = link.parent
                for _ in range(3):
                    if parent:
                        parent_text = parent.get_text(" ", strip=True)
                        parent = parent.parent

                if "2026" not in parent_text and "2026" not in text and "2026" not in href:
                    continue

                if href.endswith(".pdf") or "pdf" in href.lower() or "telecharger" in href.lower():
                    full_url = href if href.startswith("http") else f"https://www.ammc.ma{href}"
                    # Identifier la société
                    company_ticker = _identify_company(text + " " + parent_text)
                    publications.append({
                        "url":     full_url,
                        "title":   text[:200],
                        "company": company_ticker,
                        "context": parent_text[:300],
                        "found":   str(datetime.date.today()),
                    })

            time.sleep(1)
    except Exception as e:
        print(f"[AMMC SCRAPE] {e}")

    # Dédupliquer par URL
    seen = set()
    unique = []
    for p in publications:
        if p["url"] not in seen:
            seen.add(p["url"])
            unique.append(p)
    return unique


def _identify_company(text):
    """Identifie le ticker BVC dans un texte"""
    text_upper = text.upper()
    # Match direct par ticker
    for ticker in BVC:
        if ticker in text_upper:
            return ticker
    # Match par nom
    for ticker, info in BVC.items():
        name_parts = info["n"].upper().split()
        if any(p in text_upper for p in name_parts if len(p) > 4):
            return ticker
    return None


def download_pdf_text(url):
    """Télécharge un PDF et extrait son texte"""
    text = ""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200: return ""
        if PDF_OK:
            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                for page in pdf.pages[:15]:  # Max 15 pages
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        else:
            # Fallback: extraire texte brut du PDF sans pdfplumber
            raw = r.content.decode("latin-1", errors="ignore")
            # Extraire les segments lisibles
            segments = re.findall(r'[A-Za-z0-9\s\.,;:\-\+\%éèàùôêâûî]{20,}', raw)
            text = " ".join(segments[:200])
    except Exception as e:
        print(f"[PDF DOWNLOAD] {url}: {e}")
    return text[:8000]  # Limite pour Groq


def analyze_pdf_with_llm(pdf_text, title, ticker):
    """Analyse un rapport PDF avec Groq"""
    if not pdf_text or len(pdf_text) < 100:
        return {}

    ticker_info = BVC.get(ticker, {})
    prompt = f"""Tu es Baraka, analyste financier Wall Street specialisé sur la Bourse de Casablanca.

SOCIETE: {ticker} - {ticker_info.get('n','')} ({ticker_info.get('s','')})
DOCUMENT: {title}

CONTENU DU RAPPORT:
{pdf_text[:4000]}

Analyse ce document et reponds en JSON:
{{
  "type_document": "rapport_annuel|semestriel|trimestriel|prospectus|communique|autre",
  "periode": "S1 2026|S2 2025|T1 2026|annuel 2025|...",
  "chiffres_cles": {{
    "ca": "montant ou null",
    "ca_variation": "+X% ou null",
    "resultat_net": "montant ou null",
    "resultat_variation": "+X% ou null",
    "ebitda": "montant ou null",
    "dette_nette": "montant ou null",
    "dividende": "X MAD ou null"
  }},
  "vs_previsions": "conforme|au_dessus|en_dessous|pas_de_prevision",
  "vs_an_dernier": "meilleur|equivalent|moins_bon",
  "points_positifs": ["point1","point2","point3"],
  "points_negatifs": ["point1","point2"],
  "reaction_marche_prevue": "hausse_forte|hausse_moderee|neutre|baisse_moderee|baisse_forte",
  "cours_cible_1semaine": X.XX,
  "cours_cible_1mois": X.XX,
  "cours_cible_3mois": X.XX,
  "conviction": "forte|moderee|faible",
  "resume_executif": "2-3 phrases pour un trader",
  "signal_trading": "ACHAT_FORT|ACHAT|NEUTRE|VENTE|VENTE_FORTE"
}}

Cours actuel: inconnu (sera rempli séparément).
Base tes cours cibles sur les fondamentaux du document."""

    return groq_json(prompt, max_tokens=1000)


def run_pdf_analysis_background():
    """
    Tourne à 02h00 - Analyse tous les nouveaux PDFs AMMC 2026.
    Résultats stockés en cache, inclus dans le prochain mail programmé.
    """
    print("[BARAKA PDF] Démarrage analyse PDFs AMMC...")
    cache = load_pdf_cache()
    publications = scrape_ammc_publications()

    new_analyses = []
    for pub in publications:
        url = pub["url"]
        if url in cache["analyzed"]:
            continue  # Déjà analysé

        print(f"[BARAKA PDF] Analyse: {pub['title'][:60]}...")
        pdf_text = download_pdf_text(url)
        if not pdf_text:
            continue

        analysis = analyze_pdf_with_llm(pdf_text, pub["title"], pub.get("company"))

        if analysis:
            ticker  = pub.get("company")
            entry   = {
                "url":      url,
                "title":    pub["title"],
                "ticker":   ticker,
                "analysis": analysis,
                "analyzed_at": str(datetime.datetime.now()),
            }
            cache["analyzed"][url] = entry
            new_analyses.append(entry)

            # Mettre à jour les cours cibles
            if ticker and analysis.get("cours_cible_1mois"):
                if ticker not in cache["price_targets"]:
                    cache["price_targets"][ticker] = {}
                cache["price_targets"][ticker].update({
                    "1w":   analysis.get("cours_cible_1semaine"),
                    "1m":   analysis.get("cours_cible_1mois"),
                    "3m":   analysis.get("cours_cible_3mois"),
                    "signal": analysis.get("signal_trading","NEUTRE"),
                    "conviction": analysis.get("conviction","faible"),
                    "source": pub["title"][:80],
                    "updated": str(datetime.date.today()),
                })

            # Ajouter à la file d'attente (non-urgent)
            urgency = 40
            if analysis.get("reaction_marche_prevue") in ["hausse_forte","baisse_forte"]:
                urgency = 72
            elif analysis.get("vs_previsions") == "en_dessous":
                urgency = 68

            add_to_pending(
                "pdf_ammc",
                {
                    "ticker":  ticker,
                    "title":   pub["title"][:100],
                    "signal":  analysis.get("signal_trading","NEUTRE"),
                    "resume":  analysis.get("resume_executif",""),
                    "targets": {
                        "1w": analysis.get("cours_cible_1semaine"),
                        "1m": analysis.get("cours_cible_1mois"),
                        "3m": analysis.get("cours_cible_3mois"),
                    },
                    "reaction": analysis.get("reaction_marche_prevue","neutre"),
                },
                urgency_score=urgency,
                ticker=ticker
            )
            time.sleep(2)  # Respecter rate limits Groq

    cache["last_scan"] = str(datetime.datetime.now())
    save_pdf_cache(cache)
    print(f"[BARAKA PDF] {len(new_analyses)} nouveaux rapports analysés")


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 3 — GOOGLE NEWS PAR SOCIÉTÉ
# ═══════════════════════════════════════════════════════════════════════════════

def load_news_cache():
    if os.path.exists(F["news"]):
        with open(F["news"],"r",encoding="utf-8") as f: return json.load(f)
    return {"company_news":{},"last_scan":"","seen_hashes":[]}

def save_news_cache(data):
    with open(F["news"],"w",encoding="utf-8") as f: json.dump(data,f,indent=2,ensure_ascii=False)


def get_company_google_news(ticker, query):
    """Google News RSS pour une société spécifique"""
    articles = []
    try:
        q   = quote(f"{query} 2026")
        url = f"https://news.google.com/rss/search?q={q}&hl=fr&gl=MA&ceid=MA:fr"
        r   = requests.get(url, headers=HEADERS, timeout=8)
        # Parser RSS
        titles  = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", r.text)
        dates   = re.findall(r"<pubDate>(.*?)</pubDate>", r.text)
        sources = re.findall(r"<source.*?>(.*?)</source>", r.text)
        for i, title in enumerate(titles[1:8]):  # Skip feed title
            clean = re.sub(r"<[^>]+>","",title).strip()
            if len(clean) < 10: continue
            pub_date = dates[i] if i < len(dates) else ""
            source   = sources[i] if i < len(sources) else ""
            h = hashlib.md5(clean[:60].encode()).hexdigest()[:12]
            articles.append({
                "ticker":  ticker,
                "headline":clean[:200],
                "date":    pub_date[:20],
                "source":  source[:50],
                "hash":    h,
            })
    except Exception as e:
        print(f"[GOOGLE NEWS] {ticker}: {e}")
    return articles


def run_company_news_scan():
    """
    Tourne à 06h00 et 20h00 - Scrape Google News pour chaque société BVC.
    Analyse le sentiment, ajoute à la file d'attente si significatif.
    """
    print("[BARAKA NEWS] Scan Google News par société...")
    cache = load_news_cache()
    seen  = set(cache.get("seen_hashes",[]))
    all_new_articles = {}

    # Priorité aux large/mid caps
    priority = [t for t,i in BVC.items() if i["mc"] in ["large","mid"]]
    others   = [t for t,i in BVC.items() if i["mc"] == "small"]
    to_scan  = priority + others[:20]  # Limiter les small caps

    for ticker in to_scan:
        info     = BVC[ticker]
        articles = get_company_google_news(ticker, info["q"])
        new      = [a for a in articles if a["hash"] not in seen]
        if new:
            all_new_articles[ticker] = new
            for a in new:
                seen.add(a["hash"])
        time.sleep(0.5)

    # Analyser le sentiment des nouvelles articles avec Groq (batch)
    if all_new_articles:
        _analyze_news_batch(all_new_articles, cache)

    cache["seen_hashes"] = list(seen)[-2000:]
    cache["last_scan"]   = str(datetime.datetime.now())
    save_news_cache(cache)
    print(f"[BARAKA NEWS] {sum(len(v) for v in all_new_articles.values())} nouvelles articles")


def _analyze_news_batch(articles_by_ticker, cache):
    """Analyse le sentiment des news et ajoute les importantes à la file"""
    for ticker, articles in articles_by_ticker.items():
        if not articles: continue
        headlines = [a["headline"] for a in articles[:5]]
        info      = BVC.get(ticker,{})

        prompt = f"""Analyse ces news sur {ticker} ({info.get('n','')}, secteur {info.get('s','')}).
NEWS: {json.dumps(headlines, ensure_ascii=False)}

Reponds en JSON:
{{"sentiment":"positif|negatif|neutre","impact_cours":"hausse|baisse|neutre","magnitude":"fort|modere|faible","resume":"1 phrase","urgence":0-100,"detail_impact":"1 phrase sur l'impact BVC"}}"""

        result = groq_json(prompt, max_tokens=300)
        if not result: continue

        urgency = result.get("urgence", 50)
        sentiment = result.get("sentiment","neutre")

        # Stocker dans le cache
        if ticker not in cache["company_news"]:
            cache["company_news"][ticker] = []
        cache["company_news"][ticker].insert(0, {
            "articles":  headlines,
            "sentiment": sentiment,
            "impact":    result.get("impact_cours","neutre"),
            "magnitude": result.get("magnitude","faible"),
            "resume":    result.get("resume",""),
            "urgence":   urgency,
            "date":      str(datetime.date.today()),
        })
        cache["company_news"][ticker] = cache["company_news"][ticker][:10]

        # Ajouter à la file d'attente si pertinent
        if urgency >= 40:
            add_to_pending(
                "company_news",
                {
                    "ticker":    ticker,
                    "sentiment": sentiment,
                    "impact":    result.get("impact_cours","neutre"),
                    "magnitude": result.get("magnitude","faible"),
                    "resume":    result.get("resume",""),
                    "detail":    result.get("detail_impact",""),
                    "headlines": headlines[:3],
                },
                urgency_score=urgency,
                ticker=ticker
            )
        time.sleep(1)


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 4 — RÉSEAUX SOCIAUX (Telegram + Facebook)
# ═══════════════════════════════════════════════════════════════════════════════

TELEGRAM_CHANNELS = [
    "boursecasablancaofficiel",
    "boursedecasablanca",
    "bvcmaroc",
    "tradingmaroc",
    "analysebvc",
    "maroctrade",
    "boursemaroc",
    "wallstreetbvc",
    "investisseur_maroc",
]

def load_social_cache():
    if os.path.exists(F["social"]):
        with open(F["social"],"r",encoding="utf-8") as f: return json.load(f)
    return {"telegram":[],"facebook":[],"seen_hashes":[],"rumeurs_validees":{},"last_scan":""}

def save_social_cache(data):
    with open(F["social"],"w",encoding="utf-8") as f: json.dump(data,f,indent=2,ensure_ascii=False)


def scrape_telegram_channel(channel_name):
    """Scrape un canal Telegram public via t.me/s/channel"""
    posts = []
    try:
        url = f"https://t.me/s/{channel_name}"
        r   = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200: return []
        soup = BeautifulSoup(r.text, "html.parser")

        # Messages Telegram
        for msg in soup.select(".tgme_widget_message_text, .js-message_text")[:15]:
            text = msg.get_text(strip=True)
            if len(text) < 15: continue
            posts.append({
                "channel": channel_name,
                "text":    text[:300],
                "source":  "telegram",
                "hash":    hashlib.md5(text[:80].encode()).hexdigest()[:12],
            })
    except Exception as e:
        print(f"[TELEGRAM] {channel_name}: {e}")
    return posts


def scrape_facebook_public_groups():
    """
    Scrape des pages Facebook publiques liées à la bourse marocaine.
    Facebook limite l'accès public, on utilise ce qui est disponible.
    """
    posts = []
    # Pages publiques connues
    fb_pages = [
        "https://www.facebook.com/boursecasablancaofficielle/posts",
        "https://www.facebook.com/boursenews.ma",
    ]
    for url in fb_pages:
        try:
            r = requests.get(url, headers={**HEADERS, "Accept-Language":"fr-FR"}, timeout=10)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "html.parser")
            for el in soup.select("div[data-testid='post_message'], .userContent, p")[:10]:
                text = el.get_text(strip=True)
                if len(text) < 20: continue
                posts.append({
                    "source": "facebook",
                    "page":   url.split("/")[3],
                    "text":   text[:300],
                    "hash":   hashlib.md5(text[:80].encode()).hexdigest()[:12],
                })
        except: continue
    return posts


def analyze_social_rumors(posts, news_cache):
    """
    Analyse les posts sociaux:
    1. Identifie les rumeurs sur des actions BVC
    2. Évalue la consistance avec les données fondamentales
    3. Croise avec les news Google pour validation
    4. Attribue un score de crédibilité 0-100
    """
    if not posts: return []
    analyzed = []

    # Regrouper les posts mentionnant des tickers BVC
    ticker_posts = {}
    for post in posts:
        text = post["text"].upper()
        for ticker in BVC:
            if ticker in text or BVC[ticker]["n"].upper().split()[0] in text:
                if ticker not in ticker_posts:
                    ticker_posts[ticker] = []
                ticker_posts[ticker].append(post["text"])

    for ticker, mentions in ticker_posts.items():
        if not mentions: continue
        info       = BVC[ticker]
        # News récentes pour croiser
        recent_news = news_cache.get("company_news",{}).get(ticker,[])
        news_summary = [n.get("resume","") for n in recent_news[:3]]

        prompt = f"""Tu es Baraka, analyste BVC. Des posts de réseaux sociaux mentionnent {ticker} ({info['n']}).

POSTS SOCIAUX:
{json.dumps(mentions[:5], ensure_ascii=False)}

NEWS RECENTES SUR CE TITRE:
{json.dumps(news_summary, ensure_ascii=False)}

Analyse:
1. Y a-t-il une rumeur identifiable? (résultats, contrat, fusion, dividende, profit warning...)
2. Cette rumeur est-elle consistante avec les données disponibles?
3. Quelle est sa crédibilité?

Reponds en JSON:
{{"rumeur_detectee":true/false,"type_rumeur":"résultats|contrat|dividende|fusion|autre|aucune","description_rumeur":"courte","consistance_fondamentaux":"forte|moderee|faible|contradictoire","score_credibilite":0-100,"direction_prevue":"hausse|baisse|neutre","recommandation_trader":"entrer|surveiller|ignorer","raisonnement":"1 phrase"}}"""

        result = groq_json(prompt, max_tokens=400)
        if not result or not result.get("rumeur_detectee"): continue

        score = result.get("score_credibilite", 0)
        analyzed.append({
            "ticker":      ticker,
            "rumeur":      result.get("type_rumeur",""),
            "description": result.get("description_rumeur",""),
            "consistance": result.get("consistance_fondamentaux",""),
            "score":       score,
            "direction":   result.get("direction_prevue","neutre"),
            "action":      result.get("recommandation_trader","ignorer"),
            "raison":      result.get("raisonnement",""),
            "posts_count": len(mentions),
        })

        # Ajouter à la file selon crédibilité
        urgency = min(80, 30 + score * 0.5)
        if score >= 60:
            add_to_pending("social_rumeur", result, urgency_score=urgency, ticker=ticker)
        time.sleep(1.5)

    return analyzed


def run_social_media_scan():
    """
    Tourne à 03h00 et 22h00 - Surveille Telegram + Facebook.
    Analyse rumeurs et leur consistance.
    """
    print("[BARAKA SOCIAL] Scan réseaux sociaux...")
    cache = load_social_cache()
    seen  = set(cache.get("seen_hashes",[]))
    news_cache = load_news_cache()

    all_posts = []

    # Telegram
    for channel in TELEGRAM_CHANNELS:
        posts = scrape_telegram_channel(channel)
        new   = [p for p in posts if p["hash"] not in seen]
        all_posts.extend(new)
        for p in new: seen.add(p["hash"])
        time.sleep(1)

    # Facebook
    fb_posts = scrape_facebook_public_groups()
    new_fb   = [p for p in fb_posts if p["hash"] not in seen]
    all_posts.extend(new_fb)
    for p in new_fb: seen.add(p["hash"])

    print(f"[BARAKA SOCIAL] {len(all_posts)} nouveaux posts")

    # Analyser les rumeurs
    if all_posts:
        rumeurs = analyze_social_rumors(all_posts, news_cache)
        print(f"[BARAKA SOCIAL] {len(rumeurs)} rumeurs détectées")

        # Sauvegarder dans le cache
        cache["telegram"]     = (cache.get("telegram",[]) + [p for p in all_posts if p.get("source")=="telegram"])[-100:]
        cache["facebook"]     = (cache.get("facebook",[]) + [p for p in all_posts if p.get("source")=="facebook"])[-50:]
        cache["seen_hashes"]  = list(seen)[-2000:]
        cache["last_scan"]    = str(datetime.datetime.now())

        for r in rumeurs:
            t = r.get("ticker")
            if t:
                cache["rumeurs_validees"][t] = r

    save_social_cache(cache)


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 5 — DONNÉES MARCHÉS & MACRO
# ═══════════════════════════════════════════════════════════════════════════════

def get_tv_analysis(ticker):
    try:
        h = TA_Handler(symbol=ticker, screener="morocco", exchange="CSE", interval=Interval.INTERVAL_15_MINUTES)
        a = h.get_analysis()
        return {
            "ticker":ticker,"close":a.indicators.get("close",0),"volume":a.indicators.get("volume",0),
            "rsi":a.indicators.get("RSI",50),"macd":a.indicators.get("MACD.macd",0),
            "macd_signal":a.indicators.get("MACD.signal",0),"macd_hist":a.indicators.get("MACD.hist",0),
            "ema20":a.indicators.get("EMA20",0),"ema50":a.indicators.get("EMA50",0),
            "ema200":a.indicators.get("EMA200",0),"vwap":a.indicators.get("VWAP",0),
            "bb_upper":a.indicators.get("BB.upper",0),"bb_lower":a.indicators.get("BB.lower",0),
            "stoch_k":a.indicators.get("Stoch.K",50),"stoch_d":a.indicators.get("Stoch.D",50),
            "adx":a.indicators.get("ADX",0),"cci":a.indicators.get("CCI20",0),
            "atr":a.indicators.get("ATR",0),"change":a.indicators.get("change",0),
            "high":a.indicators.get("high",0),"low":a.indicators.get("low",0),
            "recommendation":a.summary.get("RECOMMENDATION","NEUTRAL"),
            "buy_signals":a.summary.get("BUY",0),"sell_signals":a.summary.get("SELL",0),
        }
    except Exception as e:
        print(f"[TV] {ticker}: {e}")
        return None

def get_global_macro():
    macro = {}
    symbols = {
        "vix":"^VIX","sp500":"^GSPC","nasdaq":"^IXIC","stoxx50":"^STOXX50E",
        "dax":"^GDAXI","cac40":"^FCHI","us10y":"^TNX","us2y":"^IRX","us30y":"^TYX",
        "gold":"GC=F","brent":"BZ=F","oil_wti":"CL=F","silver":"SI=F","copper":"HG=F",
        "natgas":"NG=F","eur_usd":"EURUSD=X","usd_mad":"USDMAD=X","eur_mad":"EURMAD=X",
        "dxy":"DX-Y.NYB",
    }
    try:
        data = yf.download(list(symbols.values()), period="2d", interval="1d", progress=False, auto_adjust=True)
        for name, sym in symbols.items():
            try:
                closes = data["Close"][sym].dropna()
                if len(closes) >= 2:
                    prev = float(closes.iloc[-2]); curr = float(closes.iloc[-1])
                    macro[name] = {"price":round(curr,4),"change":round((curr-prev)/prev*100,3) if prev else 0}
                else:
                    macro[name] = {"price":0,"change":0}
            except: macro[name] = {"price":0,"change":0}
    except Exception as e:
        print(f"[MACRO] {e}")
        for name in symbols: macro[name] = {"price":0,"change":0}

    # Calculs dérivés
    vix  = macro.get("vix",{}).get("price",20)
    us10y= macro.get("us10y",{}).get("price",4.0)
    us2y = macro.get("us2y",{}).get("price",4.5)
    dxy  = macro.get("dxy",{}).get("price",103)
    sp_c = macro.get("sp500",{}).get("change",0)
    br_c = macro.get("brent",{}).get("change",0)
    go_c = macro.get("gold",{}).get("change",0)
    cu_c = macro.get("copper",{}).get("change",0)
    ys   = us10y - us2y
    risk_on  = vix<20 and sp_c>0 and go_c<1
    risk_off = vix>25 or (go_c>1 and sp_c<0)
    infl_up  = go_c>0.5 and br_c>0.5 and cu_c>0
    rec_risk = ys < 0

    bvc_out = {
        "Banque":     "POSITIF" if risk_on and not rec_risk else ("NEGATIF" if rec_risk else "NEUTRE"),
        "Mines":      "TRES_POSITIF" if dxy>105 else ("POSITIF" if infl_up else "NEUTRE"),
        "Chimie":     "TRES_POSITIF" if dxy>105 else ("POSITIF" if infl_up else "NEUTRE"),
        "Energie":    "POSITIF" if br_c>1 else ("NEGATIF" if br_c<-2 else "NEUTRE"),
        "Immobilier": "POSITIF" if not rec_risk else "NEGATIF",
        "Telecom":    "POSITIF" if risk_off else "NEUTRE",
        "Agro":       "NEGATIF" if br_c>2 else ("POSITIF" if br_c<-1 else "NEUTRE"),
        "Transport":  "NEGATIF" if br_c>2 else ("POSITIF" if br_c<-1 else "NEUTRE"),
    }
    macro["_d"] = {
        "yield_spread":ys,"risk_regime":"RISK_ON" if risk_on else ("RISK_OFF" if risk_off else "NEUTRE"),
        "inflation":"INFLATION" if infl_up else "STABLE","recession":rec_risk,
        "vix_level":"EXTREME" if vix>35 else ("ELEVE" if vix>25 else ("NORMAL" if vix>15 else "FAIBLE")),
        "dollar":"FORT" if dxy>105 else ("FAIBLE" if dxy<100 else "NEUTRE"),
        "bvc_outlook":bvc_out,
    }
    return macro

def get_rates():
    rates = {"fed":5.25,"ecb":3.5,"bam":3.0,"bam_news":[]}
    try:
        r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS",headers=HEADERS,timeout=10)
        lines = r.text.strip().split("\n")
        if len(lines)>1:
            v = float(lines[-1].split(",")[1])
            if 0 < v < 20: rates["fed"] = v
    except: pass
    try:
        r    = requests.get("https://www.bkam.ma/Politique-monetaire",headers=HEADERS,timeout=12)
        soup = BeautifulSoup(r.text,"html.parser")
        text = r.text.lower()
        for m in re.findall(r'(\d+[.,]\d+)\s*%',text):
            v = float(m.replace(",","."))
            if 0.5<v<10: rates["bam"]=v; break
        for el in soup.select("p,h2,h3,li")[:15]:
            t = el.get_text(strip=True)
            if any(k in t.lower() for k in ["taux","monetaire","inflation","reserve"]):
                if 20<len(t)<250: rates["bam_news"].append(t[:200])
        rates["bam_news"] = list(dict.fromkeys(rates["bam_news"]))[:4]
    except: pass
    return rates

def get_masi():
    try:
        h = TA_Handler(symbol="MASI",screener="morocco",exchange="CSE",interval=Interval.INTERVAL_15_MINUTES)
        a = h.get_analysis()
        return {"close":a.indicators.get("close",0),"change":a.indicators.get("change",0),
                "rsi":a.indicators.get("RSI",50),"rec":a.summary.get("RECOMMENDATION","NEUTRAL"),
                "buy":a.summary.get("BUY",0),"sell":a.summary.get("SELL",0)}
    except: return {"close":0,"change":0,"rsi":50,"rec":"NEUTRAL","buy":0,"sell":0}

def _scrape_boursenews():
    try:
        r    = requests.get("https://www.boursenews.ma/",headers=HEADERS,timeout=10)
        soup = BeautifulSoup(r.text,"html.parser")
        news = [item.get_text(strip=True)[:160] for item in soup.select("article,h2 a,h3 a")[:10] if len(item.get_text(strip=True))>20]
        return list(dict.fromkeys(news))[:5]
    except: return []

def _scrape_ammc_news():
    try:
        r    = requests.get("https://www.ammc.ma/fr/actualites",headers=HEADERS,timeout=10)
        soup = BeautifulSoup(r.text,"html.parser")
        items = [i.get_text(strip=True)[:160] for i in soup.select(".views-row,article,h3 a,h2 a")[:6] if len(i.get_text(strip=True))>20]
        return list(dict.fromkeys(items))[:4]
    except: return []

def _scrape_oc():
    try:
        r    = requests.get("https://www.oc.gov.ma/fr/publications",headers=HEADERS,timeout=10)
        soup = BeautifulSoup(r.text,"html.parser")
        items = [i.get_text(strip=True)[:160] for i in soup.select("article,.views-row,h3 a,h2 a")[:5] if len(i.get_text(strip=True))>20]
        return list(dict.fromkeys(items))[:3]
    except: return []

def get_google_news_general(queries):
    all_news = []
    for query in queries[:6]:
        try:
            q   = quote(query)
            url = f"https://news.google.com/rss/search?q={q}&hl=fr&gl=MA&ceid=MA:fr"
            r   = requests.get(url,headers=HEADERS,timeout=8)
            titles = re.findall(r"<title>(.*?)</title>",r.text)
            for t in titles[1:4]:
                clean = re.sub(r"<[^>]+>","",t).strip()
                if len(clean)>15: all_news.append({"query":query,"headline":clean[:180]})
        except: pass
        time.sleep(0.3)
    return all_news[:12]

def get_twitter_signals():
    signals = []
    accounts = [("federalreserve","FED"),("BankAlMaghrib","BAM"),("ecb","ECB"),("IMFNews","FMI"),("ReutersBiz","Reuters")]
    nitter   = ["https://nitter.poast.org","https://nitter.privacydev.net","https://nitter.1d4.us"]
    for account, label in accounts:
        for n in nitter:
            try:
                r = requests.get(f"{n}/{account}/rss",headers=HEADERS,timeout=6)
                if r.status_code != 200: continue
                items = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>",r.text)
                for item in items[1:3]:
                    clean = re.sub(r"<[^>]+>","",item).strip()
                    if len(clean)>20: signals.append({"source":label,"text":clean[:200]})
                break
            except: continue
    return signals[:8]


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 6 — VOLUME PROFILE
# ═══════════════════════════════════════════════════════════════════════════════

def get_volume_profile(ticker_yf, period="3mo", bins=30):
    try:
        data = yf.download(ticker_yf, period=period, interval="1d", progress=False, auto_adjust=True)
        if data is None or len(data) < 5: return None
        data = data.dropna()
        closes = data["Close"].values.flatten()
        highs  = data["High"].values.flatten()
        lows   = data["Low"].values.flatten()
        vols   = data["Volume"].values.flatten()
        p_min  = float(np.min(lows)); p_max = float(np.max(highs))
        if p_max <= p_min: return None
        bins_arr    = np.linspace(p_min, p_max, bins+1)
        vol_at_price = np.zeros(bins)
        for i in range(len(data)):
            h,l,v = float(highs[i]),float(lows[i]),float(vols[i])
            if h==l: continue
            for b in range(bins):
                ol=max(l,bins_arr[b]); oh=min(h,bins_arr[b+1])
                if oh>ol: vol_at_price[b] += v*(oh-ol)/(h-l)
        poc_idx   = int(np.argmax(vol_at_price))
        poc       = float((bins_arr[poc_idx]+bins_arr[poc_idx+1])/2)
        total     = vol_at_price.sum()
        target    = total*0.70
        sidx      = np.argsort(vol_at_price)[::-1]
        acc,va    = 0.0,[]
        for idx in sidx:
            acc+=vol_at_price[idx]; va.append(int(idx))
            if acc>=target: break
        vah = float((bins_arr[max(va)]+bins_arr[min(max(va)+1,bins)])/2)
        val = float((bins_arr[min(va)]+bins_arr[min(min(va)+1,bins)])/2)
        curr = float(closes[-1]) if len(closes) else poc
        if curr<val:    sig,desc = "ACHAT_FORT",f"Prix sous VAL {val:.2f} — zone achat institutionnel"
        elif curr<poc:  sig,desc = "ACHAT",f"Entre VAL et POC {poc:.2f} — accumulation"
        elif curr>vah:  sig,desc = "VENTE",f"Au-dessus VAH {vah:.2f} — distribution"
        elif curr>poc:  sig,desc = "NEUTRE_HAUT",f"Entre POC et VAH — momentum positif"
        else:           sig,desc = "NEUTRE",f"Au POC {poc:.2f} — équilibre"
        return {"poc":round(poc,2),"vah":round(vah,2),"val":round(val,2),"current":round(curr,2),
                "signal":sig,"description":desc,"dist_poc_pct":round((curr-poc)/poc*100,2) if poc else 0}
    except Exception as e:
        print(f"[VP] {ticker_yf}: {e}"); return None


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 7 — SMART MONEY DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def detect_smart_money(analyses):
    """
    Détecte l'accumulation institutionnelle:
    - Volume > 4x la moyenne
    - RSI survendu (< 40)
    - Prix proche support / POC
    - Mouvement coordonné sur plusieurs titres du même secteur
    """
    smart_money = []
    sector_activity = {}

    for ticker, info in BVC.items():
        tv = analyses.get(ticker)
        if not tv: continue
        vol    = tv.get("volume",0)
        avg    = info["v"]
        rsi    = tv.get("rsi",50)
        close  = tv.get("close",0)
        ema200 = tv.get("ema200",0)
        vr     = vol/avg if avg>0 else 0

        if vr < 4: continue  # Seuil smart money: 4x

        # Score smart money
        sm_score = 0
        if vr >= 5:    sm_score += 40
        elif vr >= 4:  sm_score += 25
        if rsi < 35:   sm_score += 25
        elif rsi < 45: sm_score += 15
        if ema200>0 and close>ema200*0.97: sm_score += 15
        buy_sig = tv.get("buy_signals",0); sell_sig = tv.get("sell_signals",0)
        if buy_sig > sell_sig*1.5: sm_score += 20

        if sm_score >= 50:
            smart_money.append({
                "ticker":ticker,"name":info["n"],"sector":info["s"],
                "vol_ratio":round(vr,1),"rsi":round(rsi,1),
                "price":round(close,2),"sm_score":sm_score,
            })
            sector = info["s"]
            sector_activity[sector] = sector_activity.get(sector,0) + 1

    # Détecter si plusieurs titres d'un même secteur bougent ensemble
    sector_coordinated = [s for s,cnt in sector_activity.items() if cnt>=2]

    return smart_money, sector_coordinated


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 8 — SCORING ADAPTATIF
# ═══════════════════════════════════════════════════════════════════════════════

def load_learnings():
    if os.path.exists(F["learn"]):
        with open(F["learn"],"r",encoding="utf-8") as f: return json.load(f)
    return {"lessons":[],"indicator_weights":{"rsi":1.0,"macd":1.0,"ema":1.0,"volume":1.0,"stoch":1.0,"adx":1.0,"vp":1.0,"bam_corr":1.0,"brent_corr":1.0,"phos_corr":1.0,"macro_regime":1.0,"news_sentiment":1.0,"social_rumeur":1.0},"secteurs_favorables":[],"secteurs_eviter":[],"accuracy_history":[],"accuracy_rate":0,"total_analyzed":0,"last_updated":""}

def save_learnings(data):
    with open(F["learn"],"w",encoding="utf-8") as f: json.dump(data,f,indent=2,ensure_ascii=False)

def score_action(tv, info, vp, macro, rates, learnings, news_data=None, social_data=None):
    if not tv: return 0
    w     = learnings.get("indicator_weights",{})
    score = 50
    rsi   = tv.get("rsi",50); macd=tv.get("macd",0); macd_s=tv.get("macd_signal",0)
    macd_h= tv.get("macd_hist",0); close=tv.get("close",0)
    ema20 = tv.get("ema20",0); ema50=tv.get("ema50",0); ema200=tv.get("ema200",0)
    vwap  = tv.get("vwap",0); stoch_k=tv.get("stoch_k",50); stoch_d=tv.get("stoch_d",50)
    adx   = tv.get("adx",0); cci=tv.get("cci",0); vol=tv.get("volume",0); avg=info.get("v",1)
    buy_s = tv.get("buy_signals",0); sell_s=tv.get("sell_signals",0); sector=info.get("s","")

    wr=w.get("rsi",1); wm=w.get("macd",1); we=w.get("ema",1); wv=w.get("volume",1)
    ws=w.get("stoch",1); wa=w.get("adx",1); wvp=w.get("vp",1)

    if rsi<25:   score+=int(25*wr)
    elif rsi<35: score+=int(15*wr)
    elif rsi<45: score+=int(7*wr)
    elif rsi>75: score-=int(25*wr)
    elif rsi>65: score-=int(12*wr)

    if macd>macd_s and macd_h>0: score+=int(18*wm)
    elif macd>macd_s:             score+=int(8*wm)
    else:                         score-=int(10*wm)

    if close>ema20>ema50>ema200:   score+=int(20*we)
    elif close>ema20>ema50:        score+=int(12*we)
    elif close>ema20:              score+=int(5*we)
    elif close<ema20<ema50<ema200: score-=int(20*we)
    elif close<ema20<ema50:        score-=int(12*we)

    if vwap>0:
        if close>vwap: score+=5
        else: score-=5

    if stoch_k<20 and stoch_k>stoch_d: score+=int(12*ws)
    elif stoch_k>80 and stoch_k<stoch_d: score-=int(12*ws)

    if adx>30: score+=int(10*wa)
    elif adx>20: score+=int(5*wa)

    if cci<-150: score+=12
    elif cci<-100: score+=7
    elif cci>150: score-=12
    elif cci>100: score-=7

    score+=int((buy_s-sell_s)*1.5)

    if avg>0:
        vr=vol/avg
        if vr>3:   score+=int(18*wv)
        elif vr>2: score+=int(12*wv)
        elif vr>1.5: score+=int(6*wv)

    # Volume Profile
    if vp:
        sig=vp.get("signal","NEUTRE")
        if sig=="ACHAT_FORT": score+=int(25*wvp)
        elif sig=="ACHAT":    score+=int(15*wvp)
        elif sig=="VENTE":    score-=int(20*wvp)
        d=abs(vp.get("dist_poc_pct",10))
        if d<1: score+=int(8*wvp)
        elif d<2: score+=int(4*wvp)

    # Macro
    if macro:
        d=macro.get("_d",{}); regime=d.get("risk_regime","NEUTRE")
        out=d.get("bvc_outlook",{}); wma=w.get("macro_regime",1.0)
        if regime=="RISK_ON": score+=int(10*wma)
        elif regime=="RISK_OFF": score-=int(8*wma)
        so=out.get(sector,"NEUTRE")
        if so=="TRES_POSITIF": score+=int(18*wma)
        elif so=="POSITIF":    score+=int(10*wma)
        elif so=="NEGATIF":    score-=int(12*wma)
        vix=macro.get("vix",{}).get("price",20)
        if vix>35: score-=int(20*wma)
        elif vix>28: score-=int(10*wma)
        elif vix<15: score+=int(5*wma)
        if d.get("recession"): score-=int(10*wma)

    # BAM
    if rates and info.get("bam"):
        bam=rates.get("bam",3.0) or 3.0; wb=w.get("bam_corr",1.0)
        if bam<=2.5: score+=int(15*wb)
        elif bam<=3.0: score+=int(8*wb)
        elif bam>=4.0: score-=int(10*wb)
        bam_news=" ".join(rates.get("bam_news",[])).lower()
        if any(k in bam_news for k in ["baisse","assouplissement","accomodante"]): score+=int(10*wb)
        elif any(k in bam_news for k in ["hausse","restrictive","resserrement","inflation"]): score-=int(8*wb)

    # Brent
    if info.get("br") and macro:
        bc=macro.get("brent",{}).get("change",0); wb2=w.get("brent_corr",1.0)
        if bc>1: score+=int(8*wb2)
        elif bc<-2: score-=int(10*wb2)

    # Phosphate
    if info.get("ph") and macro:
        dxy=macro.get("dxy",{}).get("price",103); wp=w.get("phos_corr",1.0)
        if dxy>105: score+=int(15*wp)
        elif dxy<98: score-=int(8*wp)

    # News sentiment
    if news_data:
        wn=w.get("news_sentiment",1.0)
        mag=news_data.get("magnitude","faible")
        impact=news_data.get("impact","neutre")
        if impact=="hausse" and mag=="fort":   score+=int(18*wn)
        elif impact=="hausse" and mag=="modere": score+=int(10*wn)
        elif impact=="baisse" and mag=="fort":   score-=int(18*wn)
        elif impact=="baisse" and mag=="modere": score-=int(10*wn)

    # Rumeurs sociales
    if social_data and social_data.get("score",0)>=60:
        wso=w.get("social_rumeur",1.0)
        if social_data.get("direction")=="hausse": score+=int(12*wso)
        elif social_data.get("direction")=="baisse": score-=int(12*wso)

    # PDF AMMC target vs cours actuel
    pdf_cache = load_pdf_cache()
    if close>0 and info.get("mc") in ["large","mid"]:
        targets = pdf_cache.get("price_targets",{}).get(tv["ticker"],{})
        if targets.get("1m") and targets["1m"]>0:
            upside=(targets["1m"]-close)/close*100
            if upside>5:   score+=10
            elif upside>2: score+=5
            elif upside<-5: score-=10

    # Secteurs appris
    if sector in learnings.get("secteurs_favorables",[]): score+=10
    if sector in learnings.get("secteurs_eviter",[]): score-=15
    if info.get("mc")=="large": score+=5

    return max(0,min(100,score))


def run_full_analysis():
    print(f"[BARAKA] Analyse {len(BVC)} titres TV...")
    analyses={}
    for ticker in BVC:
        a=get_tv_analysis(ticker)
        if a: analyses[ticker]=a
        time.sleep(0.35)
    print(f"[BARAKA] {len(analyses)}/{len(BVC)} OK")
    return analyses

def run_vp_for_top(analyses):
    priority=[t for t,i in BVC.items() if i["mc"] in ["large","mid"]]
    top_tv=sorted([(t,analyses[t].get("buy_signals",0)) for t in analyses if analyses.get(t,{}).get("buy_signals",0)>5],key=lambda x:-x[1])[:12]
    tickers=list(set([t for t,_ in top_tv]+priority))[:18]
    vps={}
    for ticker in tickers:
        yf_sym=BVC.get(ticker,{}).get("yf",f"{ticker}.CS")
        vp=get_volume_profile(yf_sym)
        if vp: vps[ticker]=vp
        time.sleep(0.5)
    return vps

def get_top_signals(analyses,vps,macro,rates,learnings,news_c,social_c,n=3):
    news_cache  = news_c.get("company_news",{})
    social_cache= social_c.get("rumeurs_validees",{})
    scored=[]
    for ticker,info in BVC.items():
        tv=analyses.get(ticker); vp=vps.get(ticker)
        if not tv: continue
        nd=news_cache.get(ticker,[None])[0]; sd=social_cache.get(ticker)
        s=score_action(tv,info,vp,macro,rates,learnings,nd,sd)
        close=tv.get("close",0)
        if close<=0 or s<55: continue
        tp=0.06 if s>80 else 0.05 if s>70 else 0.04 if s>60 else 0.03
        proba=min(95,45+s*0.5)
        pdf_targets=load_pdf_cache().get("price_targets",{}).get(ticker,{})
        scored.append({
            "ticker":ticker,"name":info["n"],"sector":info["s"],"mc":info.get("mc","small"),
            "score":s,"price":close,"target":round(close*(1+tp),2),"stop":round(close*0.98,2),
            "gain_pct":round(tp*100,1),"proba":round(proba),
            "rsi":round(tv.get("rsi",50),1),"macd_cross":tv.get("macd",0)>tv.get("macd_signal",0),
            "adx":round(tv.get("adx",0),1),"change":round(tv.get("change",0),2),
            "recommendation":tv.get("recommendation","NEUTRAL"),
            "buy_signals":tv.get("buy_signals",0),"sell_signals":tv.get("sell_signals",0),
            "volume":tv.get("volume",0),"avg_volume":info["v"],
            "stoch_k":round(tv.get("stoch_k",50),1),
            "bam":info.get("bam",False),"brent":info.get("br",False),"phos":info.get("ph",False),
            "vp_signal":vp.get("signal","N/A") if vp else "N/A",
            "vp_poc":vp.get("poc",0) if vp else 0,"vp_vah":vp.get("vah",0) if vp else 0,
            "vp_val":vp.get("val",0) if vp else 0,"vp_desc":vp.get("description","") if vp else "",
            "pdf_target_1m":pdf_targets.get("1m"),"pdf_signal":pdf_targets.get("signal",""),
            "news_sentiment":nd.get("sentiment","") if nd else "",
            "social_rumeur":social_cache.get(ticker,{}).get("description",""),
        })
    return sorted(scored,key=lambda x:-x["score"])[:n]

def get_bear_signals(analyses,vps,macro,rates,learnings,n=3):
    bear=[]
    for ticker,info in BVC.items():
        tv=analyses.get(ticker); vp=vps.get(ticker)
        if not tv: continue
        s=score_action(tv,info,vp,macro,rates,learnings)
        close=tv.get("close",0)
        if close<=0 or s>40: continue
        reasons=[]
        if tv.get("rsi",50)>70: reasons.append(f"RSI surachete {tv['rsi']:.0f}")
        if tv.get("macd",0)<tv.get("macd_signal",0): reasons.append("MACD baissier")
        if close<tv.get("ema20",0)<tv.get("ema50",0): reasons.append("Sous EMA20/50")
        if vp and vp.get("signal")=="VENTE": reasons.append(f"Au-dessus VAH {vp.get('vah',0):.2f}")
        if macro and macro.get("_d",{}).get("risk_regime")=="RISK_OFF": reasons.append("Risk-OFF")
        bear.append({"ticker":ticker,"name":info["n"],"sector":info["s"],"score":s,"price":close,
                     "change":round(tv.get("change",0),2),"rsi":round(tv.get("rsi",50),1),
                     "reason":" · ".join(reasons) or "Score faible"})
    return sorted(bear,key=lambda x:x["score"])[:n]

def check_volume_alerts(analyses):
    alerts=[]
    for ticker,info in BVC.items():
        a=analyses.get(ticker)
        if not a: continue
        vol=a.get("volume",0); avg=info["v"]
        if avg>0 and vol>avg*VOL_THRESHOLD:
            alerts.append({"ticker":ticker,"name":info["n"],"sector":info["s"],
                           "volume":vol,"avg_volume":avg,"ratio":round(vol/avg,1),
                           "price":a.get("close",0),"change":a.get("change",0),"rsi":a.get("rsi",50)})
    return sorted(alerts,key=lambda x:-x["ratio"])

def get_hold_candidates(analyses,vps,macro,rates,learnings,n=2):
    candidates=[]
    pdf_targets=load_pdf_cache().get("price_targets",{})
    for ticker,info in BVC.items():
        tv=analyses.get(ticker); vp=vps.get(ticker)
        if not tv: continue
        s=score_action(tv,info,vp,macro,rates,learnings)
        close=tv.get("close",0); ema200=tv.get("ema200",0)
        if close<=0 or s<78: continue
        if ema200>0 and close>ema200*0.93:
            pt=pdf_targets.get(ticker,{})
            candidates.append({
                "ticker":ticker,"name":info["n"],"sector":info["s"],
                "score":s,"price":close,"target30":round(close*1.30,2),
                "proba":round(min(82,40+s*0.5)),
                "pdf_target_3m":pt.get("3m"),"pdf_signal":pt.get("signal",""),
            })
    return sorted(candidates,key=lambda x:-x["score"])[:n]


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 9 — EVENT DETECTION (Urgences uniquement)
# ═══════════════════════════════════════════════════════════════════════════════

def load_event_state():
    if os.path.exists(F["events"]):
        with open(F["events"],"r",encoding="utf-8") as f: return json.load(f)
    return {"last_macro":{},"seen_hashes":[],"last_alert":"2000-01-01 00:00:00","events_today":[]}

def save_event_state(state):
    with open(F["events"],"w",encoding="utf-8") as f: json.dump(state,f,indent=2,ensure_ascii=False)

def event_check():
    """
    Toutes les 7 min — détecte les événements URGENTS uniquement.
    Tout le reste va dans la file d'attente.
    """
    print("[BARAKA EVENT] Check urgences...")
    state = load_event_state()
    now   = datetime.datetime.now()

    # Cooldown 30 min entre alertes urgentes
    try:
        last_dt = datetime.datetime.strptime(state["last_alert"],"%Y-%m-%d %H:%M:%S")
        if (now-last_dt).total_seconds() < 1800:
            print("[BARAKA EVENT] Cooldown actif")
            return
    except: pass

    macro   = get_global_macro()
    prev    = state.get("last_macro",{})
    urgent  = []

    # ─── Détection urgences ───────────────────────────────────────────────────

    # 1. VIX extrême
    vix = macro.get("vix",{}).get("price",20)
    if vix > 35:
        urgent.append({"type":"vix_extreme_35","detail":f"VIX ATTEINT {vix:.1f} — PANIQUE MARCHES","score":88,"direction":"DOWN"})

    # 2. Chute commodités > 4%
    for key,label in [("brent","BRENT"),("gold","OR"),("copper","CUIVRE")]:
        chg = macro.get(key,{}).get("change",0)
        if abs(chg) > 4:
            direction = "DOWN" if chg < 0 else "UP"
            urgent.append({"type":"commodity_crash_4pct","detail":f"{label} {chg:+.2f}% — MOUVEMENT EXTREME","score":90,"direction":direction})

    # 3. News urgentes — recherche mots-clés critiques
    all_news = get_all_news_fast()
    for text in all_news:
        text_low = text.lower()
        for event_type, keywords in URGENCY_KEYWORDS.items():
            if any(kw in text_low for kw in keywords):
                score = compute_urgency(event_type, 1.5, keywords)
                if score >= URGENCY_LIMIT:
                    urgent.append({"type":event_type,"detail":text[:200],"score":score,"direction":"varies"})
                    break

    # 4. Smart money detection
    try:
        analyses = run_full_analysis()
        sm, sectors_coordinated = detect_smart_money(analyses)
        if sm and (len(sm)>=2 or (sm and sm[0]["vol_ratio"]>=6)):
            urgent.append({
                "type": "smart_money",
                "detail": f"SMART MONEY DETECTE sur {', '.join([s['ticker'] for s in sm[:4]])} — Volumes x{sm[0]['vol_ratio']} | Secteurs: {', '.join(sectors_coordinated) if sectors_coordinated else 'multiple'}",
                "score": 92,
                "direction": "UP",
                "smart_money": sm[:4],
            })
    except Exception as e:
        print(f"[SM DETECT] {e}")
        analyses = {}

    if urgent:
        # Construire et envoyer l'alerte
        rates    = get_rates()
        masi     = get_masi()
        _send_urgent_alert(urgent, analyses if analyses else {}, macro, masi, rates)
        state["last_alert"]   = now.strftime("%Y-%m-%d %H:%M:%S")
        state["events_today"] = state.get("events_today",[]) + [e["type"] for e in urgent]
    else:
        # Détecter mouvements non-urgents → pending queue
        _detect_non_urgent(macro, prev, all_news)

    state["last_macro"] = {k:v for k,v in macro.items() if k!="_d"}
    save_event_state(state)


def get_all_news_fast():
    """Scrape rapide de toutes les sources pour la détection d'urgence"""
    texts = []
    texts.extend(_scrape_boursenews())
    texts.extend(_scrape_ammc_news())
    try:
        r = requests.get("https://www.bkam.ma/Politique-monetaire",headers=HEADERS,timeout=8)
        soup = BeautifulSoup(r.text,"html.parser")
        for el in soup.select("p,h2,h3")[:10]:
            t = el.get_text(strip=True)
            if len(t)>20: texts.append(t[:200])
    except: pass
    # Twitter
    sigs = get_twitter_signals()
    texts.extend([s["text"] for s in sigs])
    return texts


def _detect_non_urgent(macro, prev, news_texts):
    """Détecte les mouvements importants mais non-urgents → pending queue"""
    if not prev: return

    for key,label in [("brent","BRENT"),("gold","OR"),("copper","CUIVRE"),("sp500","S&P500")]:
        curr_p = macro.get(key,{}).get("price",0)
        prev_p = prev.get(key,{}).get("price",0)
        if curr_p and prev_p and prev_p>0:
            chg = (curr_p-prev_p)/prev_p*100
            if abs(chg)>2:
                add_to_pending(
                    "commodity_move_2pct",
                    {"asset":label,"change":round(chg,2),"price":round(curr_p,4)},
                    urgency_score=62
                )


def _send_urgent_alert(urgent_events, analyses, macro, masi, rates):
    """Envoie l'email d'alerte urgente — uniquement pour les vraies urgences"""
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    # Synthèse Groq
    prompt = f"""Tu es Baraka, trader Wall Street BVC. ALERTE URGENTE.

EVENEMENTS: {json.dumps([{"type":e["type"],"detail":e["detail"][:100]} for e in urgent_events[:4]], ensure_ascii=False)}
MASI: {masi.get('change',0):+.2f}% · VIX: {macro.get('vix',{}).get('price',20):.1f}
BRENT: {macro.get('brent',{}).get('change',0):+.2f}% · REGIME: {macro.get('_d',{}).get('risk_regime','?')}
BAM: {rates.get('bam',3.0)}%

3 phrases URGENTES pour un trader BVC:
1. Quel est l'impact immédiat et direct sur le BVC?
2. Quoi faire maintenant (acheter/vendre/attendre)?
3. Quel est le risque principal à surveiller?

Style trader. Francais. PAS de markdown."""

    synthesis = groq_call(prompt, max_tokens=250, temp=0.15)

    # Smart money section si présent
    sm_html = ""
    for ev in urgent_events:
        if ev.get("smart_money"):
            sm_html += """<div style="background:#111520;border:1px solid rgba(0,200,122,0.3);border-radius:10px;padding:14px;margin-bottom:14px">
<div style="font-size:10px;color:#00C87A;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px">SMART MONEY DETECTÉ</div>"""
            for sm in ev["smart_money"][:4]:
                sm_html += f"""<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05);font-size:12px">
<span style="color:#00C87A;font-weight:700;font-family:monospace">{sm['ticker']}</span>
<span style="color:#9CA3AF">{sm['name']} · {sm['sector']}</span>
<span style="color:#00C87A;font-weight:700">x{sm['vol_ratio']} vol · RSI {sm['rsi']}</span></div>"""
            sm_html += "</div>"

    events_html = ""
    for e in urgent_events[:6]:
        d = "UP" if e.get("direction")=="UP" else "DOWN"
        ec = "#00C87A" if d=="UP" else "#FF4560"
        events_html += f"""<div style="background:#171C2C;border-radius:8px;padding:12px;margin-bottom:8px;border-left:3px solid {ec}">
<div style="font-size:10px;color:{ec};font-weight:700;letter-spacing:1px">{e['type'].replace('_',' ').upper()} · URGENCE {e.get('score',0)}/100</div>
<div style="font-size:12px;color:#E8E4D6;margin-top:6px">{e['detail'][:200]}</div></div>"""

    masi_c = "#00C87A" if masi.get("change",0)>=0 else "#FF4560"
    vix_v  = macro.get("vix",{}).get("price",20)
    regime = macro.get("_d",{}).get("risk_regime","?")
    rg_c   = "#00C87A" if regime=="RISK_ON" else "#FF4560" if regime=="RISK_OFF" else "#C9A84C"

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="background:#0A0D14;color:#E8E4D6;font-family:'Courier New',monospace;margin:0;padding:0">
<div style="max-width:640px;margin:0 auto;padding:20px">
<div style="background:#111520;border:2px solid rgba(255,69,96,0.6);border-radius:14px;padding:20px;text-align:center;margin-bottom:16px">
<div style="font-size:26px;font-weight:900;color:#C9A84C;letter-spacing:6px">BARAKA</div>
<div style="font-size:10px;color:#6B7280;letter-spacing:2px;margin-top:2px">ALERTE URGENTE · {now}</div>
<div style="display:inline-block;background:rgba(255,69,96,0.15);border:1px solid rgba(255,69,96,0.5);color:#FF4560;padding:5px 16px;border-radius:20px;font-size:11px;letter-spacing:2px;margin-top:10px">
{len(urgent_events)} EVENEMENT(S) CRITIQUE(S) DETECTE(S)</div></div>

<div style="display:flex;gap:8px;margin-bottom:14px">
<div style="flex:1;background:#171C2C;border-radius:10px;padding:12px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:4px">MASI</div>
<div style="font-size:14px;font-weight:900;color:{masi_c}">{masi.get('change',0):+.2f}%</div></div>
<div style="flex:1;background:#171C2C;border-radius:10px;padding:12px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:4px">VIX</div>
<div style="font-size:14px;font-weight:900;color:{'#FF4560' if vix_v>25 else '#00C87A'}">{vix_v:.1f}</div></div>
<div style="flex:1;background:#171C2C;border-radius:10px;padding:12px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:4px">REGIME</div>
<div style="font-size:12px;font-weight:900;color:{rg_c}">{regime}</div></div>
<div style="flex:1;background:#171C2C;border-radius:10px;padding:12px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:4px">BAM</div>
<div style="font-size:14px;font-weight:900;color:#60A5FA">{rates.get('bam',3.0)}%</div></div>
</div>

<div style="background:rgba(255,69,96,0.06);border:1px solid rgba(255,69,96,0.3);border-radius:10px;padding:14px;margin-bottom:14px">
<div style="font-size:10px;color:#FF4560;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">EVENEMENTS CRITIQUES</div>
{events_html}</div>

{"<div style='background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.25);border-radius:10px;padding:14px;margin-bottom:14px'><div style='font-size:10px;color:#8B5CF6;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px'>ANALYSE BARAKA · ACTION IMMEDIATE</div><div style='font-size:13px;color:#E8E4D6;line-height:1.8'>" + synthesis + "</div></div>" if synthesis else ""}

{sm_html}

<div style="text-align:center;font-size:10px;color:#4B5563;margin-top:16px;line-height:1.9">
Alerte critique · Réaction &lt; 7 minutes · Confirmez avant d'agir<br>
<strong style="color:#FF4560">BARAKA · Event-Driven · Wall Street Level</strong></div>
</div></body></html>"""

    send_email("🚨 BARAKA · ALERTE URGENTE · Action requise", html)


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 10 — EMAILS PROGRAMMÉS (avec pending items intégrés)
# ═══════════════════════════════════════════════════════════════════════════════

def load_trades():
    if os.path.exists(F["trades"]):
        with open(F["trades"],"r",encoding="utf-8") as f: return json.load(f)
    return []

def get_open_trades():
    return [t for t in load_trades() if t.get("status")=="open"]

def get_week_pnl():
    trades=load_trades(); today=datetime.date.today()
    ws=today-datetime.timedelta(days=today.weekday())
    wt=[t for t in trades if t.get("date","")>=str(ws)]
    pnl=sum(t.get("pnl_pct",0) for t in wt if t.get("status")=="closed")
    wins=sum(1 for t in wt if t.get("pnl_pct",0)>0 and t.get("status")=="closed")
    total=sum(1 for t in wt if t.get("status")=="closed")
    return {"total_pnl":round(pnl,2),"wins":wins,"total":total,
            "open":len(get_open_trades()),"win_rate":round(wins/total*100) if total>0 else 0}

def send_email(subject, html):
    try:
        msg=MIMEMultipart("alternative"); msg["Subject"]=subject; msg["From"]=GMAIL_USER; msg["To"]=TO_EMAIL
        msg.attach(MIMEText(html,"html"))
        with smtplib.SMTP_SSL("smtp.gmail.com",465) as s:
            s.login(GMAIL_USER,GMAIL_PASSWORD); s.sendmail(GMAIL_USER,TO_EMAIL,msg.as_string())
        print(f"[BARAKA] Email: {subject}"); return True
    except Exception as e:
        print(f"[BARAKA] Email error: {e}"); return False


def build_pending_section(pending_items):
    """Construit la section HTML pour les items en attente non-urgents"""
    if not pending_items: return ""
    by_cat = {}
    for item in pending_items:
        cat = item.get("category","other")
        if cat not in by_cat: by_cat[cat] = []
        by_cat[cat].append(item)

    html = """<div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px;margin-bottom:14px">
<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">ANALYSE DE FOND · RAPPORTS & NEWS</div>"""

    # PDFs AMMC
    pdf_items = by_cat.get("pdf_ammc",[])
    if pdf_items:
        html += "<div style='margin-bottom:10px'><div style='font-size:10px;color:#60A5FA;margin-bottom:6px'>RAPPORTS AMMC ANALYSÉS</div>"
        for item in pdf_items[:4]:
            c=item.get("content",{}); ticker=c.get("ticker","?"); signal=c.get("signal","NEUTRE")
            sc={"ACHAT_FORT":"#00C87A","ACHAT":"#4ADE80","NEUTRE":"#C9A84C","VENTE":"#FB923C","VENTE_FORTE":"#FF4560"}.get(signal,"#C9A84C")
            t1m=c.get("targets",{}).get("1m"); t3m=c.get("targets",{}).get("3m")
            html += f"""<div style="background:#171C2C;border-radius:6px;padding:10px;margin-bottom:6px;border-left:2px solid {sc}">
<div style="display:flex;justify-content:space-between;align-items:center">
<span style="color:{sc};font-weight:700;font-family:monospace">{ticker}</span>
<span style="font-size:10px;background:rgba(0,0,0,0.3);color:{sc};padding:2px 8px;border-radius:3px">{signal}</span></div>
<div style="font-size:11px;color:#9CA3AF;margin-top:4px">{c.get('resume','')[:120]}</div>
<div style="font-size:11px;color:#6B7280;margin-top:3px">Cible 1M: <span style="color:{sc}">{f'{t1m:.2f} MAD' if t1m else 'N/A'}</span> · Cible 3M: <span style="color:{sc}">{f'{t3m:.2f} MAD' if t3m else 'N/A'}</span></div></div>"""
        html += "</div>"

    # News sociétés
    news_items = by_cat.get("company_news",[])
    if news_items:
        html += "<div style='margin-bottom:10px'><div style='font-size:10px;color:#F59E0B;margin-bottom:6px'>NEWS SOCIÉTÉS</div>"
        for item in news_items[:5]:
            c=item.get("content",{}); ticker=c.get("ticker","?")
            imp=c.get("impact","neutre"); ic="#00C87A" if imp=="hausse" else "#FF4560" if imp=="baisse" else "#C9A84C"
            html += f"""<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:12px">
<div><span style="color:#E8E4D6;font-weight:700;font-family:monospace">{ticker}</span>
<span style="color:#9CA3AF;font-size:11px;margin-left:6px">{c.get('resume','')[:80]}</span></div>
<span style="color:{ic};font-weight:700;font-size:10px">{imp.upper()} {c.get('magnitude','')}</span></div>"""
        html += "</div>"

    # Rumeurs sociales
    social_items = by_cat.get("social_rumeur",[])
    if social_items:
        html += "<div style='margin-bottom:10px'><div style='font-size:10px;color:#8B5CF6;margin-bottom:6px'>RUMEURS RÉSEAUX SOCIAUX</div>"
        for item in social_items[:3]:
            c=item.get("content",{}); ticker=item.get("ticker","?")
            score=c.get("score_credibilite",0)
            sc="#00C87A" if score>=70 else "#F59E0B" if score>=50 else "#9CA3AF"
            html += f"""<div style="background:#171C2C;border-radius:6px;padding:8px;margin-bottom:5px">
<div style="display:flex;justify-content:space-between">
<span style="color:#8B5CF6;font-weight:700;font-family:monospace">{ticker}</span>
<span style="color:{sc};font-size:10px">Crédibilité {score}%</span></div>
<div style="font-size:11px;color:#9CA3AF;margin-top:3px">{c.get('description_rumeur','')[:100]} · {c.get('raisonnement','')[:80]}</div></div>"""
        html += "</div>"

    # Mouvements macro non-urgents
    macro_items = [i for i in pending_items if i.get("category") in ["commodity_move_2pct","macro_shift_normal"]]
    if macro_items:
        html += "<div><div style='font-size:10px;color:#9CA3AF;margin-bottom:6px'>MOUVEMENTS MACRO</div>"
        for item in macro_items[:4]:
            c=item.get("content",{}); chg=c.get("change",0)
            cc="#00C87A" if chg>=0 else "#FF4560"
            html += f"<div style='font-size:12px;color:#9CA3AF;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04)'><span style='color:#6B7280'>{c.get('asset','?')}</span><span style='color:{cc};font-weight:700;margin-left:8px'>{chg:+.2f}%</span></div>"
        html += "</div>"

    html += "</div>"
    return html


def build_signal_card(s, rank):
    color={"ACHAT_FORT":"#00C87A","ACHAT":"#00C87A","NEUTRE_HAUT":"#C9A84C","VENTE":"#FF4560"}.get(s.get("vp_signal",""),"#C9A84C")
    sc="#00C87A" if s["score"]>=70 else "#C9A84C"
    rc="#FF4560" if s["rsi"]>70 else "#00C87A" if s["rsi"]<35 else "#C9A84C"
    vr=round(s["volume"]/s["avg_volume"],1) if s["avg_volume"]>0 else 1
    vc="#00C87A" if vr>2 else "#F59E0B" if vr>1.5 else "#9CA3AF"
    cc="#00C87A" if s["change"]>=0 else "#FF4560"
    corr=""
    if s.get("bam"):  corr+="<span style='font-size:9px;background:rgba(0,150,255,0.15);color:#60A5FA;padding:2px 6px;border-radius:3px;margin-left:3px'>BAM</span>"
    if s.get("brent"):corr+="<span style='font-size:9px;background:rgba(255,140,0,0.15);color:#FB923C;padding:2px 6px;border-radius:3px;margin-left:3px'>BRENT</span>"
    if s.get("phos"): corr+="<span style='font-size:9px;background:rgba(100,200,100,0.15);color:#4ADE80;padding:2px 6px;border-radius:3px;margin-left:3px'>PHOSPHATE</span>"
    news_badge = f"<span style='font-size:9px;background:rgba(245,158,11,0.15);color:#F59E0B;padding:2px 6px;border-radius:3px;margin-left:3px'>NEWS {s.get('news_sentiment','').upper()}</span>" if s.get("news_sentiment") else ""
    social_badge = f"<span style='font-size:9px;background:rgba(139,92,246,0.15);color:#8B5CF6;padding:2px 6px;border-radius:3px;margin-left:3px'>RUMEUR</span>" if s.get("social_rumeur") else ""
    pdf_badge = f"<span style='font-size:9px;background:rgba(0,200,122,0.1);color:#00C87A;padding:2px 6px;border-radius:3px;margin-left:3px'>AMMC {s.get('pdf_signal','')}</span>" if s.get("pdf_signal") else ""
    vp_color = "#00C87A" if "ACHAT" in s.get("vp_signal","") else "#FF4560" if "VENTE" in s.get("vp_signal","") else "#C9A84C"

    return f"""<div style="background:#171C2C;border-radius:10px;padding:16px;margin-bottom:14px;border-left:4px solid {sc}">
<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px">
<div><span style="font-size:20px;font-weight:900;color:{sc};font-family:monospace">#{rank} {s['ticker']}</span>
<span style="font-size:10px;color:#6B7280;margin-left:8px">{s['name']}</span><br>
<span style="font-size:10px;background:rgba(201,168,76,0.1);color:#C9A84C;padding:2px 6px;border-radius:3px">{s['sector']}</span>{corr}{news_badge}{social_badge}{pdf_badge}</div>
<div style="text-align:right"><span style="background:rgba(0,200,122,0.15);color:#00C87A;border:1px solid rgba(0,200,122,0.3);font-size:10px;padding:3px 10px;border-radius:4px;font-weight:700">ACHAT</span><br>
<span style="font-size:11px;color:{cc};font-weight:700;display:block;margin-top:3px">{'+' if s['change']>=0 else ''}{s['change']}%</span></div></div>
<table style="width:100%;font-size:12px;border-collapse:collapse">
<tr><td style="color:#6B7280;padding:3px 0">Entrée</td><td style="color:#E8E4D6;font-weight:700;text-align:right">{s['price']:.2f} MAD</td>
<td style="color:#6B7280;padding:3px 12px">Cible</td><td style="color:#00C87A;font-weight:700;text-align:right">{s['target']:.2f} (+{s['gain_pct']}%)</td></tr>
<tr><td style="color:#6B7280;padding:3px 0">Stop</td><td style="color:#FF4560;font-weight:700;text-align:right">{s['stop']:.2f} MAD</td>
<td style="color:#6B7280;padding:3px 12px">RSI</td><td style="color:{rc};font-weight:700;text-align:right">{s['rsi']}</td></tr>
<tr><td style="color:#6B7280;padding:3px 0">Volume</td><td colspan="3" style="color:{vc};text-align:right">x{vr} ({int(s['volume']):,} vs {int(s['avg_volume']):,})</td></tr>
<tr><td style="color:#6B7280;padding:3px 0">VP</td><td colspan="3" style="color:{vp_color};text-align:right;font-weight:700">{s.get('vp_signal','N/A')} · POC {s.get('vp_poc',0):.2f} · VAH {s.get('vp_vah',0):.2f} · VAL {s.get('vp_val',0):.2f}</td></tr>
{"<tr><td style='color:#6B7280;padding:3px 0'>AMMC</td><td colspan='3' style='color:#00C87A;text-align:right'>Cible 1M: " + f"{s['pdf_target_1m']:.2f} MAD · Signal: {s['pdf_signal']}" + "</td></tr>" if s.get("pdf_target_1m") else ""}
{"<tr><td style='color:#6B7280;padding:3px 0;font-size:11px' colspan='4'><span style='color:#9CA3AF'>" + s['social_rumeur'][:100] + "</span></td></tr>" if s.get("social_rumeur") else ""}
</table>
<div style="margin-top:8px">
<div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:3px">
<span style="color:#6B7280">Score Baraka</span><span style="color:{sc};font-weight:700">{s['score']}/100</span></div>
<div style="background:#0A0D14;border-radius:3px;height:4px"><div style="height:100%;border-radius:3px;background:{sc};width:{s['score']}%"></div></div>
<div style="display:flex;justify-content:space-between;font-size:11px;margin-top:5px">
<span style="color:#6B7280">Proba +2%</span><span style="color:{sc};font-weight:700">{s['proba']}%</span></div>
</div></div>"""


def run_alert(subject_type):
    print(f"\n[BARAKA] ═══ {subject_type.upper()} ═══")
    learnings   = load_learnings()
    analyses    = run_full_analysis()
    macro       = get_global_macro()
    rates       = get_rates()
    masi        = get_masi()
    vps         = run_vp_for_top(analyses)
    news_cache  = load_news_cache()
    social_cache= load_social_cache()
    signals     = get_top_signals(analyses,vps,macro,rates,learnings,news_cache,social_cache,n=3)
    bear_sigs   = [{"ticker":b["ticker"],"name":b["name"],"sector":b["sector"],"score":b["score"],"price":b["price"],"change":b["change"],"rsi":b["rsi"],"reason":b["reason"]} for b in get_bear_signals(analyses,vps,macro,rates,learnings,n=3)]
    open_trades = get_open_trades()
    vol_alerts  = check_volume_alerts(analyses)
    week_pnl    = get_week_pnl()
    hold_cands  = get_hold_candidates(analyses,vps,macro,rates,learnings) if subject_type=="cloture" else []

    # Récupérer et vider la file d'attente
    pending_items = flush_pending()

    # Agrégation news
    google_news   = get_google_news_general(["Bourse Casablanca 2026","Bank Al-Maghrib taux 2026","OCP Maroc 2026","Maroc économie 2026","Fed rate 2026"])
    twitter_sigs  = get_twitter_signals()
    boursenews    = _scrape_boursenews()
    ammc_news     = _scrape_ammc_news()

    # Sauvegarder signaux du matin
    if subject_type=="matin":
        with open(f"signals_{datetime.date.today()}.json","w") as f:
            json.dump(signals,f,ensure_ascii=False)

    # Synthèse Wall Street via Groq
    acc    = learnings.get("accuracy_rate",0)
    derived= macro.get("_d",{})
    pending_summary = [f"{p['category']}: {p.get('content',{}).get('ticker','?')} urgence {p['urgency']}" for p in (pending_items or [])[:5]]

    prompt = f"""Tu es Baraka, trader Wall Street BVC. Il est {subject_type}.

REGIME: {derived.get('risk_regime','?')} · VIX: {macro.get('vix',{}).get('price',20):.1f} · MASI: {masi.get('change',0):+.2f}%
BRENT: {macro.get('brent',{}).get('change',0):+.2f}% · OR: {macro.get('gold',{}).get('change',0):+.2f}%
S&P500: {macro.get('sp500',{}).get('change',0):+.2f}% · YIELD SPREAD: {derived.get('yield_spread',0):+.3f}%
BAM: {rates.get('bam',3.0)}% · FED: {rates.get('fed',5.25)}% · ECB: {rates.get('ecb',3.5)}%
TOP SIGNAUX: {[s['ticker']+' score:'+str(s['score'])+' VP:'+s.get('vp_signal','?') for s in signals]}
BEAR: {[b['ticker']+':'+b['reason'][:50] for b in bear_sigs]}
ANALYSES FOND: {pending_summary}
SECTEURS FAVORABLES: {learnings.get('secteurs_favorables',[])}
PRECISION: {acc}%

{'Dis en 4 phrases: 1) Regime et impact BVC 2) Pourquoi ces 3 actions maintenant (catalyseur precis) 3) Smart money et VP confirment? 4) Timing recommande et risque principal' if subject_type=='matin' else 'Dis en 3 phrases: 1) Garder ou vendre les positions ouvertes? 2) Quelle action switcher? 3) Risque principal cet apres-midi' if subject_type=='midi' else 'Dis en 4 phrases: 1) Bilan seance 2) Cloturer ou tenir jusqua demain? 3) Hold semaine justifie? (conditions: +30% min) 4) Setup demain matin'}

Francais. Style trader. Pas de markdown."""

    synthesis = groq_call(prompt, max_tokens=400, temp=0.2)

    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    if subject_type=="matin":   window,instr,ch="FENETRE 1 · 10h-12h","Tu achètes maintenant","#00C87A"
    elif subject_type=="midi":  window,instr,ch="FENETRE 2 · 12h-14h","Point mi-journée","#F59E0B"
    else:                       window,instr,ch="CLOTURE · 15h15","Décision finale","#C9A84C"

    # ─── SECTIONS HTML ────────────────────────────────────────────────────────
    masi_c = "#00C87A" if masi.get("change",0)>=0 else "#FF4560"
    vix_v  = macro.get("vix",{}).get("price",20)
    bvc_out= derived.get("bvc_outlook",{})
    rg_c   = "#00C87A" if derived.get("risk_regime")=="RISK_ON" else "#FF4560" if derived.get("risk_regime")=="RISK_OFF" else "#C9A84C"

    # Macro section
    outlook_h = "".join(f"<span style='font-size:10px;background:rgba({'0,200,122' if v in ['POSITIF','TRES_POSITIF'] else '255,69,96' if v=='NEGATIF' else '201,168,76'},0.15);color:{'#00C87A' if v in ['POSITIF','TRES_POSITIF'] else '#FF4560' if v=='NEGATIF' else '#C9A84C'};padding:2px 8px;border-radius:4px;margin:2px;display:inline-block'>{k}: {v}</span>" for k,v in bvc_out.items())

    macro_h = f"""<div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px;margin-bottom:14px">
<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px">MACRO GLOBAL · REGIME</div>
<div style="display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap">
<div style="flex:1;min-width:70px;background:#171C2C;border-radius:8px;padding:8px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:3px">REGIME</div><div style="font-size:12px;font-weight:900;color:{rg_c}">{derived.get('risk_regime','?')}</div></div>
<div style="flex:1;min-width:70px;background:#171C2C;border-radius:8px;padding:8px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:3px">VIX</div><div style="font-size:12px;font-weight:900;color:{'#FF4560' if vix_v>25 else '#00C87A'}">{vix_v:.1f}</div></div>
<div style="flex:1;min-width:70px;background:#171C2C;border-radius:8px;padding:8px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:3px">S&P500</div><div style="font-size:12px;font-weight:900;color:{'#00C87A' if macro.get('sp500',{}).get('change',0)>=0 else '#FF4560'}">{macro.get('sp500',{}).get('change',0):+.2f}%</div></div>
<div style="flex:1;min-width:70px;background:#171C2C;border-radius:8px;padding:8px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:3px">BRENT</div><div style="font-size:12px;font-weight:900;color:{'#00C87A' if macro.get('brent',{}).get('change',0)>=0 else '#FF4560'}">{macro.get('brent',{}).get('change',0):+.2f}%</div></div>
<div style="flex:1;min-width:70px;background:#171C2C;border-radius:8px;padding:8px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:3px">BAM</div><div style="font-size:12px;font-weight:900;color:#60A5FA">{rates.get('bam',3.0)}%</div></div>
</div>
<div style="font-size:11px;color:#6B7280;margin-bottom:6px">Fed: <span style='color:#60A5FA'>{rates.get('fed',5.25)}%</span> · ECB: <span style='color:#60A5FA'>{rates.get('ecb',3.5)}%</span> · Yield 10Y-2Y: <span style='color:{'#FF4560' if derived.get('yield_spread',0)<0 else '#00C87A'}'>{derived.get('yield_spread',0):+.3f}%</span></div>
<div>{outlook_h}</div></div>"""

    # BAM news section
    bam_news_h = ""
    if rates.get("bam_news"):
        bam_rows = "".join(f"<div style='font-size:11px;color:#9CA3AF;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04)'>{n}</div>" for n in rates["bam_news"][:3])
        bam_news_h = f"""<div style="background:rgba(0,100,255,0.06);border:1px solid rgba(0,100,255,0.2);border-radius:10px;padding:12px;margin-bottom:14px">
<div style="font-size:10px;color:#60A5FA;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px">BAM · PUBLICATIONS</div>{bam_rows}</div>"""

    # Synthèse
    synth_h = f"""<div style="background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.25);border-radius:10px;padding:14px;margin-bottom:14px">
<div style="font-size:10px;color:#8B5CF6;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px">SYNTHESE BARAKA · GROQ AI · Précision {acc}%</div>
<div style="font-size:13px;color:#E8E4D6;line-height:1.8">{synthesis}</div></div>""" if synthesis else ""

    # Signaux
    signals_html = "".join(build_signal_card(s,i+1) for i,s in enumerate(signals))

    # Bear
    bear_h = ""
    if bear_sigs:
        bear_rows = "".join(f"<div style='background:#1A0D10;border-radius:8px;padding:10px;margin-bottom:6px;border-left:3px solid #FF4560'><div style='display:flex;justify-content:space-between'><span style='color:#FF4560;font-weight:700;font-family:monospace'>{b['ticker']}</span><span style='font-size:10px;background:rgba(255,69,96,0.15);color:#FF4560;padding:2px 8px;border-radius:4px'>ÉVITER</span></div><div style='font-size:11px;color:#9CA3AF;margin-top:4px'>Score {b['score']}/100 · RSI {b['rsi']} · {b['reason'][:100]}</div></div>" for b in bear_sigs)
        bear_h = f"<div style='background:rgba(255,69,96,0.04);border:1px solid rgba(255,69,96,0.2);border-radius:10px;padding:14px;margin-bottom:14px'><div style='font-size:10px;color:#FF4560;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>ACTIONS À ÉVITER</div>{bear_rows}</div>"

    # Vol alerts
    vol_h = ""
    if vol_alerts:
        rows = "".join(f"<div style='display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:12px'><span style='color:#FF4560;font-weight:700;font-family:monospace'>{v['ticker']}</span><span style='color:#6B7280'>{v['name']}</span><span style='color:#FF4560;font-weight:700'>x{v['ratio']}</span><span style='color:#9CA3AF'>RSI {v['rsi']:.0f}</span></div>" for v in vol_alerts[:5])
        vol_h = f"<div style='background:rgba(255,69,96,0.06);border:1px solid rgba(255,69,96,0.25);border-radius:10px;padding:14px;margin-bottom:14px'><div style='font-size:10px;color:#FF4560;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>VOLUMES ANORMAUX ({len(vol_alerts)} titres)</div>{rows}</div>"

    # Positions
    open_h = ""
    if open_trades:
        rows = "".join(f"<div style='display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05);font-size:12px'><span style='color:#00C87A;font-weight:700;font-family:monospace'>{t.get('ticker','?')}</span><span style='color:#6B7280'>Entrée {t.get('entry',0):.2f}</span><span style='color:#C9A84C'>Cible {t.get('target',0):.2f}</span></div>" for t in open_trades)
        open_h = f"<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px;margin-bottom:14px'><div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>POSITIONS OUVERTES</div>{rows}</div>"

    # Hold semaine
    hold_h = ""
    if hold_cands and subject_type=="cloture":
        rows = "".join(f"<div style='background:#171C2C;border-radius:8px;padding:12px;margin-bottom:8px;border-left:3px solid #8B5CF6'><div style='display:flex;justify-content:space-between'><span style='color:#8B5CF6;font-weight:900;font-family:monospace'>{h['ticker']}</span><span style='font-size:10px;color:#9CA3AF'>{h['name']}</span></div><div style='font-size:12px;margin-top:6px;display:flex;justify-content:space-between'><span style='color:#6B7280'>Entrée <span style='color:#E8E4D6'>{h['price']:.2f}</span></span><span style='color:#8B5CF6;font-weight:700'>+30%: {h['target30']:.2f}</span>{'<span style=\"color:#00C87A;font-size:10px\">AMMC: '+str(h[\"pdf_target_3m\"])+'</span>' if h.get('pdf_target_3m') else ''}</div></div>" for h in hold_cands)
        hold_h = f"<div style='background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.25);border-radius:10px;padding:14px;margin-bottom:14px'><div style='font-size:10px;color:#8B5CF6;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>HOLD SEMAINE · OBJECTIF +30%</div>{rows}</div>"

    # News flux
    all_news_items = (
        [("BourseNews",n) for n in boursenews[:3]] +
        [("AMMC",n) for n in ammc_news[:2]] +
        [(s["source"],s["text"]) for s in twitter_sigs[:3]] +
        [(n["query"].split()[0],n["headline"]) for n in google_news[:3]]
    )
    news_rows = "".join(f"<div style='padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.04)'><span style='font-size:9px;color:{'#FF4560' if s=='AMMC' else '#60A5FA' if s in ['FED','BAM','ECB','FMI'] else '#F59E0B' if s=='AMMC' else '#9CA3AF'};font-weight:700;letter-spacing:1px'>{s}</span><div style='font-size:11px;color:#9CA3AF;margin-top:2px'>{n[:160]}</div></div>" for s,n in all_news_items[:10])
    news_h = f"<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px;margin-bottom:14px'><div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>FLUX MARCHÉ · NEWS · TWITTER</div>{news_rows}</div>"

    # Pending items
    pending_h = build_pending_section(pending_items)

    # PnL
    pc = "#00C87A" if week_pnl["total_pnl"]>=0 else "#FF4560"
    pnl_h = f"<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px;margin-bottom:14px'><div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>PNL SEMAINE</div><div style='display:flex;justify-content:space-between;align-items:center'><div><div style='font-size:26px;font-weight:900;color:{pc};font-family:monospace'>{'+' if week_pnl['total_pnl']>=0 else ''}{week_pnl['total_pnl']}%</div><div style='font-size:11px;color:#6B7280'>{week_pnl['wins']}/{week_pnl['total']} trades · Win rate {week_pnl['win_rate']}%</div></div><div style='text-align:right'><div style='font-size:11px;color:#6B7280'>Ouvertes</div><div style='font-size:20px;font-weight:700;color:#C9A84C'>{week_pnl['open']}</div></div></div></div>"

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="background:#0A0D14;color:#E8E4D6;font-family:'Courier New',monospace;margin:0;padding:0">
<div style="max-width:640px;margin:0 auto;padding:20px">
<div style="background:#111520;border:1px solid rgba(201,168,76,0.4);border-radius:14px;padding:20px;text-align:center;margin-bottom:16px">
<div style="font-size:26px;font-weight:900;color:#C9A84C;letter-spacing:6px">BARAKA v5.0</div>
<div style="font-size:10px;color:#6B7280;letter-spacing:2px;margin-top:2px">{now} · 24h/24 · {len(BVC)} SOCIÉTÉS · PDF AMMC · Telegram · Precision {acc}%</div>
<div style="display:inline-block;background:rgba(0,200,122,0.1);border:1px solid rgba(0,200,122,0.3);color:{ch};padding:5px 16px;border-radius:20px;font-size:11px;letter-spacing:2px;margin-top:10px">{window}</div></div>
<div style="background:rgba(201,168,76,0.08);border:1px solid rgba(201,168,76,0.25);border-radius:10px;padding:12px;margin-bottom:16px;text-align:center">
<div style="font-size:13px;color:#C9A84C;font-weight:700">{instr}</div></div>
<div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:12px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center">
<div><span style="font-size:10px;color:#6B7280;letter-spacing:2px">MASI</span><br>
<span style="font-size:18px;font-weight:900;color:#E8E4D6;font-family:monospace">{masi.get('close',0):,.2f}</span>
<span style="color:{masi_c};font-weight:700;margin-left:8px">{'+' if masi.get('change',0)>=0 else ''}{masi.get('change',0):.2f}%</span></div>
<div style="text-align:right;font-size:11px;color:#6B7280">RSI <span style="color:#C9A84C">{masi.get('rsi',50):.0f}</span><br>{masi.get('rec','')}</div></div>
{macro_h}{bam_news_h}{synth_h}
<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">TOP 3 SIGNAUX · VP + NEWS + AMMC + SOCIAL</div>
{signals_html}{bear_h}{open_h}{hold_h}{vol_h}{pending_h}{news_h}{pnl_h}
<div style="text-align:center;font-size:10px;color:#4B5563;margin-top:16px;line-height:1.9">
Max 3 trades/jour · T-15min · Confirmez manuellement<br>
<strong style="color:#C9A84C">+5%/jour · Hold semaine = +30% min</strong><br>
TV · VP · AMMC PDF · Google News · Telegram · Facebook · BAM · FRED · Groq</div>
</div></body></html>"""

    titles = {
        "matin":   "BARAKA v5 · SIGNAL MATIN · Wall Street Level BVC",
        "midi":    "BARAKA v5 · POINT MIDI · Garder / Vendre / Switcher",
        "cloture": "BARAKA v5 · CLOTURE BVC · Décision + Hold Semaine",
    }
    send_email(titles[subject_type], html)


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 11 — ANALYSE NUIT & PRE-MARCHE
# ═══════════════════════════════════════════════════════════════════════════════

def night_analysis():
    if datetime.datetime.now().weekday()>=5: return
    print("[BARAKA] === ANALYSE NUIT 21h ===")
    macro   = get_global_macro()
    rates   = get_rates()
    derived = macro.get("_d",{})
    boursenews = _scrape_boursenews()
    ammc_news  = _scrape_ammc_news()
    twitter    = get_twitter_signals()
    google_h   = get_google_news_general(["Bourse Casablanca 2026","OCP Maroc 2026","Maroc économie 2026","Federal Reserve 2026"])

    prompt = f"""Tu es Baraka, trader Wall Street BVC. Il est 21h, tu prépares la stratégie de demain.

CLOTURES US/EUROPE:
S&P500: {macro.get('sp500',{}).get('change',0):+.2f}% · Nasdaq: {macro.get('nasdaq',{}).get('change',0):+.2f}%
VIX: {macro.get('vix',{}).get('price',20):.1f} · Regime: {derived.get('risk_regime','?')}
Brent: {macro.get('brent',{}).get('change',0):+.2f}% · Gold: {macro.get('gold',{}).get('change',0):+.2f}%
Copper: {macro.get('copper',{}).get('change',0):+.2f}% · USD/MAD: {macro.get('usd_mad',{}).get('price',10):.4f}
Fed: {rates.get('fed',5.25)}% · ECB: {rates.get('ecb',3.5)}% · BAM: {rates.get('bam',3.0)}%
Yield 10Y-2Y: {derived.get('yield_spread',0):+.3f}% {'⚠️ INVERSION RECESSION' if derived.get('recession') else ''}
NEWS: {boursenews[:2]+[s['text'][:80] for s in twitter[:2]]+[n['headline'][:80] for n in google_h[:2]]}

Analyse en 5 phrases:
1. Sentiment global BVC pour demain — hausse ou prudence?
2. Quels secteurs privilegier a l'ouverture et pourquoi?
3. Quel event overnight va le plus impacter le BVC?
4. Les 2-3 actions a surveiller en priorite demain 10h?
5. Signal d'alarme a surveiller (si ca arrive = ne pas rentrer)?

Style trader. Francais. Direct."""

    synthesis = groq_call(prompt, max_tokens=400, temp=0.2)

    with open(F["night"],"w") as f:
        json.dump({"synthesis":synthesis,"macro":{"sp500":macro.get('sp500',{}).get('change',0),"brent":macro.get('brent',{}).get('change',0),"vix":macro.get('vix',{}).get('price',20),"regime":derived.get('risk_regime','?')},"timestamp":str(datetime.datetime.now())},f,ensure_ascii=False)

    bvc_mood = "POSITIF" if derived.get("risk_regime")=="RISK_ON" else "PRUDENT" if derived.get("risk_regime")=="RISK_OFF" else "NEUTRE"
    mc = "#00C87A" if bvc_mood=="POSITIF" else "#FF4560" if bvc_mood=="PRUDENT" else "#C9A84C"

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="background:#0A0D14;color:#E8E4D6;font-family:'Courier New',monospace;margin:0;padding:0">
<div style="max-width:640px;margin:0 auto;padding:20px">
<div style="background:#111520;border:1px solid rgba(139,92,246,0.4);border-radius:14px;padding:20px;text-align:center;margin-bottom:16px">
<div style="font-size:26px;font-weight:900;color:#C9A84C;letter-spacing:6px">BARAKA</div>
<div style="font-size:10px;color:#6B7280;letter-spacing:2px;margin-top:2px">ANALYSE NOCTURNE · {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</div>
<div style="display:inline-block;background:rgba(139,92,246,0.12);border:1px solid rgba(139,92,246,0.35);color:#8B5CF6;padding:5px 16px;border-radius:20px;font-size:11px;margin-top:10px">THÈSE POUR DEMAIN · PRÉPARATION SÉANCE</div></div>

<div style="display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap">
<div style="flex:1;min-width:80px;background:#171C2C;border-radius:10px;padding:12px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:4px">S&P500</div>
<div style="font-size:14px;font-weight:900;color:{'#00C87A' if macro.get('sp500',{}).get('change',0)>=0 else '#FF4560'}">{macro.get('sp500',{}).get('change',0):+.2f}%</div></div>
<div style="flex:1;min-width:80px;background:#171C2C;border-radius:10px;padding:12px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:4px">VIX</div>
<div style="font-size:14px;font-weight:900;color:{'#FF4560' if macro.get('vix',{}).get('price',20)>25 else '#00C87A'}">{macro.get('vix',{}).get('price',20):.1f}</div></div>
<div style="flex:1;min-width:80px;background:#171C2C;border-radius:10px;padding:12px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:4px">BRENT</div>
<div style="font-size:14px;font-weight:900;color:{'#00C87A' if macro.get('brent',{}).get('change',0)>=0 else '#FF4560'}">{macro.get('brent',{}).get('change',0):+.2f}%</div></div>
<div style="flex:1;min-width:80px;background:#171C2C;border-radius:10px;padding:12px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:4px">OUTLOOK BVC</div>
<div style="font-size:13px;font-weight:900;color:{mc}">{bvc_mood}</div></div>
</div>

<div style="background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.25);border-radius:10px;padding:14px;margin-bottom:14px">
<div style="font-size:10px;color:#8B5CF6;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px">THÈSE BARAKA · GROQ AI</div>
<div style="font-size:13px;color:#E8E4D6;line-height:1.8">{synthesis or 'Analyse en cours...'}</div></div>

<div style="text-align:center;font-size:10px;color:#4B5563;margin-top:16px;line-height:1.9">
Baraka analyse pendant que tu dors · Brief 8h30<br>
<strong style="color:#8B5CF6">Prochaine alerte: 8h30 pre-marché</strong></div>
</div></body></html>"""

    send_email("BARAKA · ANALYSE NOCTURNE · Thèse pour demain", html)
    print("[BARAKA] Analyse nuit OK")


def pre_market_brief():
    if datetime.datetime.now().weekday()>=5: return
    print("[BARAKA] === BRIEF PRE-MARCHE 8h30 ===")
    night  = json.load(open(F["night"])) if os.path.exists(F["night"]) else {}
    macro  = get_global_macro(); rates=get_rates(); derived=macro.get("_d",{})
    google = get_google_news_general(["Bourse Casablanca 2026","Bank Al-Maghrib 2026"])
    ammc   = _scrape_ammc_news()
    vix    = macro.get("vix",{}).get("price",20)
    sp500  = macro.get("sp500",{}).get("change",0)
    brent  = macro.get("brent",{}).get("change",0)
    usd_mad= macro.get("usd_mad",{}).get("price",10)
    regime = derived.get("risk_regime","?")

    prompt = f"""Baraka, il est 8h30, marché BVC ouvre dans 1h.

THESE HIER SOIR: {night.get('synthesis','')[:200]}
MACRO MAINTENANT: VIX {vix:.1f} · Regime {regime} · S&P500 {sp500:+.2f}% · Brent {brent:+.2f}%
BAM: {rates.get('bam',3.0)}% · USD/MAD: {usd_mad:.4f}
NEWS AMMC: {ammc[:2]} · GOOGLE: {[n['headline'][:80] for n in google[:3]]}

4 phrases ULTRA concretes:
1. La these d'hier tient-elle? (oui/non + 1 raison)
2. Les 2 actions a surveiller des l'ouverture (ticker + prix entree)
3. Signal d'alarme absolu (si ca se passe = sortir ou ne pas entrer)
4. Fenetre de trading du jour (10h-12h / 12h-14h / 14h-cloture)?

Style trader. Francais. Direct."""

    synthesis = groq_call(prompt, max_tokens=300, temp=0.2)
    rc = "#00C87A" if regime=="RISK_ON" else "#FF4560" if regime=="RISK_OFF" else "#C9A84C"
    bvc_out = derived.get("bvc_outlook",{})
    out_h = "".join(f"<span style='font-size:10px;background:rgba({'0,200,122' if v in ['POSITIF','TRES_POSITIF'] else '255,69,96' if v=='NEGATIF' else '201,168,76'},0.15);color:{'#00C87A' if v in ['POSITIF','TRES_POSITIF'] else '#FF4560' if v=='NEGATIF' else '#C9A84C'};padding:2px 8px;border-radius:4px;margin:2px;display:inline-block'>{k}: {v}</span>" for k,v in bvc_out.items())

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="background:#0A0D14;color:#E8E4D6;font-family:'Courier New',monospace;margin:0;padding:0">
<div style="max-width:640px;margin:0 auto;padding:20px">
<div style="background:#111520;border:1px solid rgba(0,200,122,0.4);border-radius:14px;padding:20px;text-align:center;margin-bottom:16px">
<div style="font-size:26px;font-weight:900;color:#C9A84C;letter-spacing:6px">BARAKA</div>
<div style="font-size:10px;color:#6B7280;letter-spacing:2px;margin-top:2px">BRIEF PRÉ-MARCHÉ · {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')} · OUVERTURE DANS 1H</div>
<div style="display:inline-block;background:rgba(0,200,122,0.12);border:1px solid rgba(0,200,122,0.35);color:#00C87A;padding:5px 16px;border-radius:20px;font-size:11px;margin-top:10px">STRATÉGIE D'OUVERTURE · BVC 9h30</div></div>
<div style="display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap">
<div style="flex:1;min-width:70px;background:#171C2C;border-radius:10px;padding:10px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:3px">REGIME</div><div style="font-size:12px;font-weight:900;color:{rc}">{regime}</div></div>
<div style="flex:1;min-width:70px;background:#171C2C;border-radius:10px;padding:10px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:3px">VIX</div><div style="font-size:12px;font-weight:900;color:{'#FF4560' if vix>25 else '#00C87A'}">{vix:.1f}</div></div>
<div style="flex:1;min-width:70px;background:#171C2C;border-radius:10px;padding:10px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:3px">S&P500</div><div style="font-size:12px;font-weight:900;color:{'#00C87A' if sp500>=0 else '#FF4560'}">{sp500:+.2f}%</div></div>
<div style="flex:1;min-width:70px;background:#171C2C;border-radius:10px;padding:10px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:3px">BRENT</div><div style="font-size:12px;font-weight:900;color:{'#00C87A' if brent>=0 else '#FF4560'}">{brent:+.2f}%</div></div>
<div style="flex:1;min-width:70px;background:#171C2C;border-radius:10px;padding:10px;text-align:center">
<div style="font-size:9px;color:#6B7280;margin-bottom:3px">BAM</div><div style="font-size:12px;font-weight:900;color:#60A5FA">{rates.get('bam',3.0)}%</div></div>
</div>
<div style="background:rgba(0,200,122,0.06);border:1px solid rgba(0,200,122,0.25);border-radius:10px;padding:14px;margin-bottom:14px">
<div style="font-size:10px;color:#00C87A;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px">BRIEF BARAKA · STRATÉGIE OUVERTURE</div>
<div style="font-size:13px;color:#E8E4D6;line-height:1.8">{synthesis or 'Analyse en cours...'}</div></div>
<div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:12px;margin-bottom:14px">
<div style="font-size:10px;color:#C9A84C;margin-bottom:6px">IMPACT BVC PAR SECTEUR</div>{out_h}</div>
<div style="text-align:center;font-size:10px;color:#4B5563;margin-top:16px;line-height:1.9">
Baraka surveille en continu · Alerte immédiate si urgence critique<br>
<strong style="color:#00C87A">Prochain email: Signal Matin 10h00</strong></div>
</div></body></html>"""

    send_email("BARAKA · BRIEF PRÉ-MARCHÉ 8h30 · Stratégie ouverture", html)
    print("[BARAKA] Brief pre-marche OK")


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 12 — POST-CLOTURE APPRENTISSAGE
# ═══════════════════════════════════════════════════════════════════════════════

def post_cloture_learning():
    if datetime.datetime.now().weekday()>=5: return
    print("[BARAKA] === POST-CLOTURE LEARNING ===")
    learnings = load_learnings()
    trades_today = [t for t in load_trades() if t.get("date","")==str(datetime.date.today())]
    signals_today = json.load(open(f"signals_{datetime.date.today()}.json")) if os.path.exists(f"signals_{datetime.date.today()}.json") else []
    macro = get_global_macro(); rates = get_rates(); masi = get_masi()
    derived = macro.get("_d",{})

    market_ctx = {
        "date":str(datetime.date.today()),"masi_change":masi.get("change",0),
        "regime":derived.get("risk_regime","?"),"vix":macro.get("vix",{}).get("price",20),
        "brent":macro.get("brent",{}).get("change",0),"gold":macro.get("gold",{}).get("change",0),
        "sp500":macro.get("sp500",{}).get("change",0),"usd_mad":macro.get("usd_mad",{}).get("price",10),
        "bam":rates.get("bam",3.0),"fed":rates.get("fed",5.25),
        "yield_spread":derived.get("yield_spread",0),
    }

    prompt = f"""Baraka, analyse la session du jour et apprends.
TRADES: {json.dumps(trades_today,ensure_ascii=False)[:500]}
SIGNAUX: {json.dumps([{{'t':s.get('ticker'),'sc':s.get('score'),'vp':s.get('vp_signal')}} for s in signals_today[:3]],ensure_ascii=False)}
CONTEXTE: {json.dumps(market_ctx,ensure_ascii=False)}
POIDS ACTUELS: {json.dumps(learnings.get("indicator_weights",{}),ensure_ascii=False)}
LECONS PRECEDENTES: {json.dumps([l.get('lecons',[]) for l in learnings.get('lessons',[])[-3:]],ensure_ascii=False)}

Reponds UNIQUEMENT en JSON:
{{"analyse_du_jour":"...","lecons_apprises":["...","...","..."],"nouveaux_poids":{{"rsi":1.0,"macd":1.0,"ema":1.0,"volume":1.0,"stoch":1.0,"adx":1.0,"vp":1.0,"bam_corr":1.0,"brent_corr":1.0,"phos_corr":1.0,"macro_regime":1.0,"news_sentiment":1.0,"social_rumeur":1.0}},"secteurs_favorables":["..."],"secteurs_eviter":["..."],"patterns_detectes":["..."],"score_precision_jour":75,"recommandations_demain":"..."}}"""

    result = groq_json(prompt, max_tokens=1200)
    if result:
        learnings["lessons"].append({"date":str(datetime.date.today()),"analyse":result.get("analyse_du_jour",""),"lecons":result.get("lecons_apprises",[]),"patterns":result.get("patterns_detectes",[]),"precision":result.get("score_precision_jour",0),"demain":result.get("recommandations_demain","")})
        if len(learnings["lessons"])>60: learnings["lessons"]=learnings["lessons"][-60:]
        for k,v in result.get("nouveaux_poids",{}).items():
            if k in learnings["indicator_weights"]:
                learnings["indicator_weights"][k]=round(learnings["indicator_weights"][k]*0.7+v*0.3,3)
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

def _send_learning_email(result, learnings):
    acc=learnings.get("accuracy_rate",0); total=learnings.get("total_analyzed",0)
    score=result.get("score_precision_jour",0); sc="#00C87A" if score>=70 else "#F59E0B" if score>=50 else "#FF4560"
    lecons="".join(f"<div style='padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:12px;color:#9CA3AF'>• {l}</div>" for l in result.get("lecons_apprises",[]))
    w_h="".join(f"<div style='display:flex;justify-content:space-between;padding:4px 0;font-size:12px'><span style='color:#6B7280'>{k.upper()}</span><div style='flex:1;margin:0 10px;background:#0A0D14;border-radius:2px;height:6px;margin-top:7px'><div style='height:100%;background:#C9A84C;border-radius:2px;width:{min(100,int(v*50))}%'></div></div><span style='color:#C9A84C;font-weight:700'>{v:.2f}</span></div>" for k,v in learnings.get("indicator_weights",{}).items())
    sg=", ".join(learnings.get("secteurs_favorables",[])[:4]) or "Aucun"
    se=", ".join(learnings.get("secteurs_eviter",[])[:4]) or "Aucun"
    html=f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="background:#0A0D14;color:#E8E4D6;font-family:'Courier New',monospace;margin:0;padding:0">
<div style="max-width:620px;margin:0 auto;padding:20px">
<div style="background:#111520;border:1px solid rgba(139,92,246,0.4);border-radius:14px;padding:20px;text-align:center;margin-bottom:16px">
<div style="font-size:26px;font-weight:900;color:#C9A84C;letter-spacing:6px">BARAKA</div>
<div style="font-size:10px;color:#6B7280;margin-top:2px">POST-CLOTURE · APPRENTISSAGE #{total} · {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</div>
<div style="display:inline-block;background:rgba(139,92,246,0.12);border:1px solid rgba(139,92,246,0.35);color:#8B5CF6;padding:5px 16px;border-radius:20px;font-size:11px;margin-top:10px">SESSION #{total}</div></div>
<div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:16px;margin-bottom:14px">
<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">ANALYSE DU JOUR</div>
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
<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">LEÇONS APPRISES</div>{lecons}</div>
<div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:16px;margin-bottom:14px">
<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px">POIDS ADAPTATIFS</div>{w_h}</div>
<div style="background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px;margin-bottom:14px">
<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px">SECTEURS</div>
<div style="display:flex;justify-content:space-between;font-size:12px">
<div><div style="color:#00C87A;margin-bottom:4px">FAVORABLES</div><div style="color:#9CA3AF">{sg}</div></div>
<div style="text-align:right"><div style="color:#FF4560;margin-bottom:4px">À ÉVITER</div><div style="color:#9CA3AF">{se}</div></div></div></div>
<div style="text-align:center;font-size:10px;color:#4B5563;margin-top:16px;line-height:1.9">
Baraka apprend de chaque session · Groq llama3-70b · 100% Gratuit<br>
<strong style="color:#8B5CF6">Session #{total} · Précision cumulée {acc}%</strong></div>
</div></body></html>"""
    send_email(f"BARAKA v5 · POST-CLOTURE · Learning #{total}", html)


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 13 — SCHEDULER 24H/24
# ═══════════════════════════════════════════════════════════════════════════════

def monitor_volumes():
    now = datetime.datetime.now()
    if now.weekday()>=5: return
    if not (9<=now.hour<16): return
    print("[BARAKA] Surveillance volumes...")
    analyses = run_full_analysis()
    alerts   = check_volume_alerts(analyses)
    # Les volumes non-urgents vont en pending
    for a in alerts:
        if a["ratio"]>=5:  # >= 5x → urgent
            pass  # Géré par event_check
        else:
            add_to_pending("volume_2x",{"ticker":a["ticker"],"ratio":a["ratio"],"price":a["price"]},urgency_score=55,ticker=a["ticker"])


def run_scheduler():
    print("""
╔════════════════════════════════════════════════════════════════╗
║    BARAKA v5.0 · WALL STREET LEVEL · 24h/24 · 7j/7           ║
║  Smart Filter · PDF AMMC · Google News · Telegram · Facebook   ║
╠════════════════════════════════════════════════════════════════╣
║  /7min     → Event check URGENCES uniquement                  ║
║  /15min    → Surveillance volumes (heures marché)             ║
║  02h00     → Analyse PDFs AMMC (background)                   ║
║  03h00     → Scan réseaux sociaux Telegram/Facebook           ║
║  06h00     → Scan Google News par société                     ║
║  08h30     → Brief pré-marché                                 ║
║  10h00     → Signal Matin (tout intégré)                      ║
║  12h00     → Point Midi                                       ║
║  15h15     → Clôture + Hold semaine +30%                      ║
║  16h30     → Post-Clôture Apprentissage Groq                  ║
║  20h00     → Scan Google News par société (soir)              ║
║  21h00     → Analyse Nocturne + Thèse demain                  ║
║  22h00     → Scan réseaux sociaux (soir)                      ║
╚════════════════════════════════════════════════════════════════╝
    """)

    days = [schedule.every().monday, schedule.every().tuesday,
            schedule.every().wednesday, schedule.every().thursday,
            schedule.every().friday]

    # ─── Emails programmés (lun-ven) ─────────────────────────────────────────
    for d in days:
        d.at("08:30").do(pre_market_brief)
        d.at("10:00").do(run_alert, "matin")
        d.at("12:00").do(run_alert, "midi")
        d.at("15:15").do(run_alert, "cloture")
        d.at("16:30").do(post_cloture_learning)
        d.at("21:00").do(night_analysis)

    # ─── Background workers (7j/7) ────────────────────────────────────────────
    schedule.every().day.at("02:00").do(run_pdf_analysis_background)
    schedule.every().day.at("03:00").do(run_social_media_scan)
    schedule.every().day.at("06:00").do(run_company_news_scan)
    schedule.every().day.at("20:00").do(run_company_news_scan)
    schedule.every().day.at("22:00").do(run_social_media_scan)

    # ─── Event monitoring URGENCES (7j/7, 24h/24) ────────────────────────────
    schedule.every(7).minutes.do(event_check)

    # ─── Surveillance volumes (heures marché seulement) ───────────────────────
    schedule.every(15).minutes.do(monitor_volumes)

    print("[BARAKA] Actif 24h/24 · Smart Filter activé · Baraka anticipe le marché...")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    run_scheduler()
