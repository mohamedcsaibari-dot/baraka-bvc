"""
BARAKA v5.0 - Wall Street Level BVC Trading Agent
24h/24 - Smart Filter - PDF AMMC - Google News - Telegram - Volume Profile
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

GMAIL_USER     = os.environ.get("GMAIL_USER", "mohamed.csaibari@gmail.com")
GMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
TO_EMAIL       = "mohamed.csaibari@gmail.com"
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")

F = {
    "trades":  "trade_log.json",
    "learn":   "baraka_learnings.json",
    "events":  "baraka_events.json",
    "pdf":     "baraka_pdf_cache.json",
    "news":    "baraka_news_cache.json",
    "social":  "baraka_social_cache.json",
    "pending": "baraka_pending.json",
    "night":   "baraka_night_thesis.json",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
AMMC_URL = "https://www.ammc.ma/fr/communiques-presse-emetteurs"
VOL_THRESHOLD = 2.5
URGENCY_LIMIT = 85

BVC = {
    "ATW":    {"n":"Attijariwafa Bank",        "s":"Banque",       "v":85000, "mc":"large","bam":True, "br":False,"ph":False,"yf":"ATW.CS",  "q":"Attijariwafa Bank resultats"},
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
    "IAM":    {"n":"Maroc Telecom",             "s":"Telecom",      "v":120000,"mc":"large","bam":False,"br":False,"ph":False,"yf":"IAM.CS",  "q":"Maroc Telecom resultats"},
    "HPS":    {"n":"HighTech Payment Systems",  "s":"Tech",         "v":15000, "mc":"mid",  "bam":False,"br":False,"ph":False,"yf":"HPS.CS",  "q":"HPS paiement Maroc"},
    "M2M":    {"n":"M2M Group",                 "s":"Tech",         "v":2500,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"M2M.CS",  "q":"M2M Group Maroc"},
    "IB":     {"n":"Involys",                   "s":"Tech",         "v":3000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"IB.CS",   "q":"Involys informatique Maroc"},
    "S2M":    {"n":"S2M",                       "s":"Tech",         "v":2000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"S2M.CS",  "q":"S2M paiement Maroc"},
    "OCP":    {"n":"OCP Group",                 "s":"Chimie",       "v":95000, "mc":"large","bam":False,"br":False,"ph":True, "yf":"OCP.CS",  "q":"OCP phosphate Maroc resultats"},
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
    "SNABT":  {"n":"Sna Btp",                   "s":"Construction", "v":1500,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"SNA.CS",  "q":"SNA BTP travaux"},
    "LABEL":  {"n":"Label Vie",                 "s":"Distribution", "v":9000,  "mc":"mid",  "bam":False,"br":False,"ph":False,"yf":"LBV.CS",  "q":"Label Vie supermarche Maroc"},
    "FENIE":  {"n":"Fenie Brossette",           "s":"Distribution", "v":3500,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"FBR.CS",  "q":"Fenie Brossette"},
    "STOKVIS":{"n":"Stokvis Nord Afrique",      "s":"Distribution", "v":2000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"STK.CS",  "q":"Stokvis Nord Afrique"},
    "LAC":    {"n":"Lesieur Cristal",           "s":"Agro",         "v":11000, "mc":"mid",  "bam":False,"br":True, "ph":False,"yf":"LAC.CS",  "q":"Lesieur Cristal huile Maroc"},
    "DARI":   {"n":"Dari Couspate",             "s":"Agro",         "v":4000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"DAR.CS",  "q":"Dari Couspate pates"},
    "COSUMAR":{"n":"Cosumar",                   "s":"Agro",         "v":8000,  "mc":"mid",  "bam":False,"br":False,"ph":False,"yf":"CSR.CS",  "q":"Cosumar sucre Maroc"},
    "OULMES": {"n":"Eaux Minerales Oulmes",     "s":"Agro",         "v":4000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"OUL.CS",  "q":"Oulmes eau minerale"},
    "UNIMER": {"n":"Unimer",                    "s":"Agro",         "v":3000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"UNI.CS",  "q":"Unimer Maroc"},
    "TMA":    {"n":"Total Maroc",               "s":"Energie",      "v":7000,  "mc":"mid",  "bam":False,"br":True, "ph":False,"yf":"TMA.CS",  "q":"Total Maroc energie carburant"},
    "TAQA":   {"n":"Taqa Morocco",              "s":"Energie",      "v":8000,  "mc":"mid",  "bam":False,"br":True, "ph":False,"yf":"TQA.CS",  "q":"Taqa Morocco electricite"},
    "SRM":    {"n":"Sonasid",                   "s":"Siderurgie",   "v":6000,  "mc":"mid",  "bam":False,"br":True, "ph":False,"yf":"SRM.CS",  "q":"Sonasid acier siderurgie Maroc"},
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
    "AFRIC":  {"n":"Africa Industries",         "s":"Industrie",    "v":1000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"AFR.CS",  "q":"Africa Industries Maroc"},
    "FBR":    {"n":"Fipar Holding",             "s":"Holding",      "v":4000,  "mc":"mid",  "bam":False,"br":False,"ph":False,"yf":"FIP.CS",  "q":"Fipar Holding ONA"},
    "ENNAKL": {"n":"Ennakl",                    "s":"Automobile",   "v":2000,  "mc":"small","bam":False,"br":True, "ph":False,"yf":"ENN.CS",  "q":"Ennakl automobile Maroc"},
    "MED":    {"n":"Meditel",                   "s":"Telecom",      "v":2000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"MED.CS",  "q":"Meditel Orange Maroc telecom"},
    "SDLT":   {"n":"Sodetel",                   "s":"Telecom",      "v":1000,  "mc":"small","bam":False,"br":False,"ph":False,"yf":"SDL.CS",  "q":"Sodetel telecom"},
}

URGENCY_KEYWORDS = {
    "war_conflict":       ["guerre","war","attentat","conflit arme","bombardement","invasion","coup d'etat"],
    "rate_surprise_bam":  ["bank al-maghrib annonce","bam reduit","bam hausse","taux directeur surprise","decision urgente bam"],
    "rate_surprise_fed":  ["fed emergency","federal reserve surprise","fomc emergency","fed cuts","powell emergency"],
    "profit_warning_bvc": ["profit warning","avertissement sur resultats","revision a la baisse","perte inattendue"],
    "circuit_breaker_bvc":["suspension de cotation","cotation suspendue","circuit breaker bvc"],
    "ipo_bvc":            ["introduction en bourse","ipo bvc","nouvelles cotations","premier jour de cotation"],
    "major_sanctions":    ["sanctions","embargo","gel des avoirs"],
}

TELEGRAM_CHANNELS = [
    "boursecasablancaofficiel","boursedecasablanca","bvcmaroc",
    "tradingmaroc","analysebvc","maroctrade","boursemaroc",
    "wallstreetbvc","investisseur_maroc",
]


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════

def groq_call(prompt, max_tokens=400, temp=0.25):
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
    raw = groq_call(prompt, max_tokens=max_tokens, temp=0.2)
    try:
        clean = raw.replace("```json","").replace("```","").strip()
        start = clean.find("{")
        end   = clean.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(clean[start:end])
    except:
        pass
    return {}

def send_email(subject, html):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = GMAIL_USER
        msg["To"]      = TO_EMAIL
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.ehlo()
            s.starttls()
            s.login(GMAIL_USER, GMAIL_PASSWORD)
            s.sendmail(GMAIL_USER, TO_EMAIL, msg.as_string())
        print(f"[BARAKA] Email: {subject}")
        return True
    except Exception as e:
        print(f"[BARAKA] Email error: {e}")
        return False

# ═══════════════════════════════════════════════════════════
# SMART FILTER & PENDING QUEUE
# ═══════════════════════════════════════════════════════════

def load_pending():
    if os.path.exists(F["pending"]):
        with open(F["pending"], "r", encoding="utf-8") as f:
            return json.load(f)
    return {"items": [], "last_flush": ""}

def save_pending(data):
    with open(F["pending"], "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def add_to_pending(category, content, urgency_score=50, ticker=None):
    if urgency_score >= URGENCY_LIMIT:
        return
    p = load_pending()
    p["items"].append({
        "category": category,
        "content":  content,
        "urgency":  urgency_score,
        "ticker":   ticker,
        "added_at": str(datetime.datetime.now()),
    })
    p["items"] = sorted(p["items"], key=lambda x: -x["urgency"])[:100]
    save_pending(p)

def flush_pending():
    p     = load_pending()
    items = p.get("items", [])
    p["items"]      = []
    p["last_flush"] = str(datetime.datetime.now())
    save_pending(p)
    return items

def compute_urgency(event_type, magnitude=1.0, keywords_found=None):
    base_map = {
        "smart_money": 92, "war_conflict": 99, "commodity_crash_4pct": 90,
        "rate_surprise_bam": 95, "rate_surprise_fed": 88, "vix_extreme_35": 88,
        "profit_warning_bvc": 90, "circuit_breaker_bvc": 99, "ipo_bvc": 86,
        "major_sanctions": 94, "volume_2x": 55, "commodity_move_2pct": 62,
        "news_company": 50, "social_buzz": 52,
    }
    base    = base_map.get(event_type, 50)
    bonus   = min(10, magnitude * 2)
    kw_bonus = 0
    if keywords_found:
        for kw_type, kw_list in URGENCY_KEYWORDS.items():
            if any(kw in " ".join(keywords_found).lower() for kw in kw_list):
                kw_bonus = 15
                break
    return min(100, base + bonus + kw_bonus)

# ═══════════════════════════════════════════════════════════
# PDF AMMC ANALYZER
# ═══════════════════════════════════════════════════════════

def load_pdf_cache():
    if os.path.exists(F["pdf"]):
        with open(F["pdf"], "r", encoding="utf-8") as f:
            return json.load(f)
    return {"analyzed": {}, "last_scan": "", "price_targets": {}}

def save_pdf_cache(data):
    with open(F["pdf"], "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _identify_company(text):
    text_upper = text.upper()
    for ticker in BVC:
        if ticker in text_upper:
            return ticker
    for ticker, info in BVC.items():
        name_parts = info["n"].upper().split()
        if any(p in text_upper for p in name_parts if len(p) > 4):
            return ticker
    return None

def scrape_ammc_publications():
    publications = []
    try:
        for page in range(0, 4):
            url  = f"{AMMC_URL}?page={page}" if page > 0 else AMMC_URL
            r    = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.text, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                text = link.get_text(strip=True)
                if not text or len(text) < 5:
                    continue
                parent_text = ""
                parent = link.parent
                for _ in range(3):
                    if parent:
                        parent_text = parent.get_text(" ", strip=True)
                        parent = parent.parent
                if "2026" not in parent_text and "2026" not in text and "2026" not in href:
                    continue
                if href.endswith(".pdf") or "pdf" in href.lower() or "telecharger" in href.lower():
                    full_url = href if href.startswith("http") else "https://www.ammc.ma" + href
                    company  = _identify_company(text + " " + parent_text)
                    publications.append({
                        "url":     full_url,
                        "title":   text[:200],
                        "company": company,
                        "context": parent_text[:300],
                        "found":   str(datetime.date.today()),
                    })
            time.sleep(1)
    except Exception as e:
        print(f"[AMMC SCRAPE] {e}")
    seen    = set()
    unique  = []
    for p in publications:
        if p["url"] not in seen:
            seen.add(p["url"])
            unique.append(p)
    return unique

def download_pdf_text(url):
    text = ""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return ""
        if PDF_OK:
            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                for page in pdf.pages[:15]:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        else:
            raw      = r.content.decode("latin-1", errors="ignore")
            segments = re.findall(r'[A-Za-z0-9\s\.,;:\-\+\%]{20,}', raw)
            text     = " ".join(segments[:200])
    except Exception as e:
        print(f"[PDF] {url}: {e}")
    return text[:8000]

def analyze_pdf_with_llm(pdf_text, title, ticker):
    if not pdf_text or len(pdf_text) < 100:
        return {}
    info   = BVC.get(ticker, {})
    prompt = (
        "Tu es Baraka, analyste BVC Wall Street.\n"
        f"SOCIETE: {ticker} - {info.get('n','')} ({info.get('s','')})\n"
        f"DOCUMENT: {title}\n"
        f"CONTENU:\n{pdf_text[:4000]}\n\n"
        "Reponds en JSON:\n"
        '{"type_document":"rapport_annuel|semestriel|trimestriel|prospectus|autre",'
        '"periode":"S1 2026|T1 2026|annuel 2025|...",'
        '"chiffres_cles":{"ca":"montant ou null","ca_variation":"+X%","resultat_net":"montant","resultat_variation":"+X%"},'
        '"vs_previsions":"conforme|au_dessus|en_dessous|pas_de_prevision",'
        '"vs_an_dernier":"meilleur|equivalent|moins_bon",'
        '"points_positifs":["point1","point2"],'
        '"points_negatifs":["point1"],'
        '"reaction_marche_prevue":"hausse_forte|hausse_moderee|neutre|baisse_moderee|baisse_forte",'
        '"cours_cible_1semaine":0.0,'
        '"cours_cible_1mois":0.0,'
        '"cours_cible_3mois":0.0,'
        '"conviction":"forte|moderee|faible",'
        '"resume_executif":"2-3 phrases trader",'
        '"signal_trading":"ACHAT_FORT|ACHAT|NEUTRE|VENTE|VENTE_FORTE"}'
    )
    return groq_json(prompt, max_tokens=1000)

def run_pdf_analysis_background():
    print("[BARAKA PDF] Analyse PDFs AMMC...")
    cache        = load_pdf_cache()
    publications = scrape_ammc_publications()
    new_analyses = []
    for pub in publications:
        url = pub["url"]
        if url in cache["analyzed"]:
            continue
        print(f"[PDF] Analyse: {pub['title'][:60]}...")
        pdf_text = download_pdf_text(url)
        if not pdf_text:
            continue
        analysis = analyze_pdf_with_llm(pdf_text, pub["title"], pub.get("company"))
        if analysis:
            ticker = pub.get("company")
            entry  = {
                "url":        url,
                "title":      pub["title"],
                "ticker":     ticker,
                "analysis":   analysis,
                "analyzed_at": str(datetime.datetime.now()),
            }
            cache["analyzed"][url] = entry
            new_analyses.append(entry)
            if ticker and analysis.get("cours_cible_1mois"):
                if ticker not in cache["price_targets"]:
                    cache["price_targets"][ticker] = {}
                cache["price_targets"][ticker].update({
                    "1w":       analysis.get("cours_cible_1semaine"),
                    "1m":       analysis.get("cours_cible_1mois"),
                    "3m":       analysis.get("cours_cible_3mois"),
                    "signal":   analysis.get("signal_trading", "NEUTRE"),
                    "conviction": analysis.get("conviction", "faible"),
                    "source":   pub["title"][:80],
                    "updated":  str(datetime.date.today()),
                })
            urgency = 40
            if analysis.get("reaction_marche_prevue") in ["hausse_forte", "baisse_forte"]:
                urgency = 72
            elif analysis.get("vs_previsions") == "en_dessous":
                urgency = 68
            add_to_pending("pdf_ammc", {
                "ticker":   ticker,
                "title":    pub["title"][:100],
                "signal":   analysis.get("signal_trading", "NEUTRE"),
                "resume":   analysis.get("resume_executif", ""),
                "targets":  {
                    "1w": analysis.get("cours_cible_1semaine"),
                    "1m": analysis.get("cours_cible_1mois"),
                    "3m": analysis.get("cours_cible_3mois"),
                },
                "reaction": analysis.get("reaction_marche_prevue", "neutre"),
            }, urgency_score=urgency, ticker=ticker)
            time.sleep(2)
    cache["last_scan"] = str(datetime.datetime.now())
    save_pdf_cache(cache)
    print(f"[PDF] {len(new_analyses)} rapports analyses")


# ═══════════════════════════════════════════════════════════
# GOOGLE NEWS & SOCIAL MEDIA
# ═══════════════════════════════════════════════════════════

def load_news_cache():
    if os.path.exists(F["news"]):
        with open(F["news"], "r", encoding="utf-8") as f:
            return json.load(f)
    return {"company_news": {}, "last_scan": "", "seen_hashes": []}

def save_news_cache(data):
    with open(F["news"], "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_social_cache():
    if os.path.exists(F["social"]):
        with open(F["social"], "r", encoding="utf-8") as f:
            return json.load(f)
    return {"telegram": [], "facebook": [], "seen_hashes": [], "rumeurs_validees": {}, "last_scan": ""}

def save_social_cache(data):
    with open(F["social"], "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_company_google_news(ticker, query):
    articles = []
    try:
        q   = quote(query + " 2026")
        url = f"https://news.google.com/rss/search?q={q}&hl=fr&gl=MA&ceid=MA:fr"
        r   = requests.get(url, headers=HEADERS, timeout=8)
        titles  = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", r.text)
        dates   = re.findall(r"<pubDate>(.*?)</pubDate>", r.text)
        sources = re.findall(r"<source.*?>(.*?)</source>", r.text)
        for i, title in enumerate(titles[1:8]):
            clean = re.sub(r"<[^>]+>", "", title).strip()
            if len(clean) < 10:
                continue
            h = hashlib.md5(clean[:60].encode()).hexdigest()[:12]
            articles.append({
                "ticker":  ticker,
                "headline": clean[:200],
                "date":    dates[i] if i < len(dates) else "",
                "source":  sources[i] if i < len(sources) else "",
                "hash":    h,
            })
    except Exception as e:
        print(f"[GNEWS] {ticker}: {e}")
    return articles

def get_google_news_general(queries):
    all_news = []
    for query in queries[:6]:
        try:
            q   = quote(query)
            url = f"https://news.google.com/rss/search?q={q}&hl=fr&gl=MA&ceid=MA:fr"
            r   = requests.get(url, headers=HEADERS, timeout=8)
            titles = re.findall(r"<title>(.*?)</title>", r.text)
            for t in titles[1:4]:
                clean = re.sub(r"<[^>]+>", "", t).strip()
                if len(clean) > 15:
                    all_news.append({"query": query, "headline": clean[:180]})
        except:
            pass
        time.sleep(0.3)
    return all_news[:12]

def run_company_news_scan():
    print("[BARAKA NEWS] Scan Google News...")
    cache    = load_news_cache()
    seen     = set(cache.get("seen_hashes", []))
    priority = [t for t, i in BVC.items() if i["mc"] in ["large","mid"]]
    others   = [t for t, i in BVC.items() if i["mc"] == "small"]
    to_scan  = priority + others[:15]
    new_articles = {}
    for ticker in to_scan:
        info     = BVC[ticker]
        articles = get_company_google_news(ticker, info["q"])
        new      = [a for a in articles if a["hash"] not in seen]
        if new:
            new_articles[ticker] = new
            for a in new:
                seen.add(a["hash"])
        time.sleep(0.5)
    if new_articles:
        _analyze_news_batch(new_articles, cache)
    cache["seen_hashes"] = list(seen)[-2000:]
    cache["last_scan"]   = str(datetime.datetime.now())
    save_news_cache(cache)
    print(f"[NEWS] {sum(len(v) for v in new_articles.values())} nouveaux articles")

def _analyze_news_batch(articles_by_ticker, cache):
    for ticker, articles in articles_by_ticker.items():
        if not articles:
            continue
        headlines = [a["headline"] for a in articles[:5]]
        info      = BVC.get(ticker, {})
        prompt    = (
            f"Analyse ces news sur {ticker} ({info.get('n','')}, secteur {info.get('s','')}).\n"
            f"NEWS: {json.dumps(headlines, ensure_ascii=False)}\n\n"
            'Reponds en JSON:\n'
            '{"sentiment":"positif|negatif|neutre","impact_cours":"hausse|baisse|neutre",'
            '"magnitude":"fort|modere|faible","resume":"1 phrase","urgence":0-100,'
            '"detail_impact":"1 phrase impact BVC"}'
        )
        result = groq_json(prompt, max_tokens=300)
        if not result:
            continue
        urgency   = result.get("urgence", 50)
        sentiment = result.get("sentiment", "neutre")
        if ticker not in cache["company_news"]:
            cache["company_news"][ticker] = []
        cache["company_news"][ticker].insert(0, {
            "articles":  headlines,
            "sentiment": sentiment,
            "impact":    result.get("impact_cours", "neutre"),
            "magnitude": result.get("magnitude", "faible"),
            "resume":    result.get("resume", ""),
            "urgence":   urgency,
            "date":      str(datetime.date.today()),
        })
        cache["company_news"][ticker] = cache["company_news"][ticker][:10]
        if urgency >= 40:
            add_to_pending("company_news", {
                "ticker":    ticker,
                "sentiment": sentiment,
                "impact":    result.get("impact_cours", "neutre"),
                "magnitude": result.get("magnitude", "faible"),
                "resume":    result.get("resume", ""),
                "detail":    result.get("detail_impact", ""),
                "headlines": headlines[:3],
            }, urgency_score=urgency, ticker=ticker)
        time.sleep(1)

def scrape_telegram_channel(channel_name):
    posts = []
    try:
        url  = f"https://t.me/s/{channel_name}"
        r    = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        for msg in soup.select(".tgme_widget_message_text, .js-message_text")[:15]:
            text = msg.get_text(strip=True)
            if len(text) < 15:
                continue
            posts.append({
                "channel": channel_name,
                "text":    text[:300],
                "source":  "telegram",
                "hash":    hashlib.md5(text[:80].encode()).hexdigest()[:12],
            })
    except Exception as e:
        print(f"[TELEGRAM] {channel_name}: {e}")
    return posts

def run_social_media_scan():
    print("[BARAKA SOCIAL] Scan reseaux sociaux...")
    cache      = load_social_cache()
    seen       = set(cache.get("seen_hashes", []))
    news_cache = load_news_cache()
    all_posts  = []
    for channel in TELEGRAM_CHANNELS:
        posts = scrape_telegram_channel(channel)
        new   = [p for p in posts if p["hash"] not in seen]
        all_posts.extend(new)
        for p in new:
            seen.add(p["hash"])
        time.sleep(1)
    print(f"[SOCIAL] {len(all_posts)} nouveaux posts")
    if all_posts:
        rumeurs = _analyze_social_rumors(all_posts, news_cache)
        print(f"[SOCIAL] {len(rumeurs)} rumeurs detectees")
        cache["telegram"]     = (cache.get("telegram", []) + all_posts)[-100:]
        cache["seen_hashes"]  = list(seen)[-2000:]
        cache["last_scan"]    = str(datetime.datetime.now())
        for r in rumeurs:
            t = r.get("ticker")
            if t:
                cache["rumeurs_validees"][t] = r
    save_social_cache(cache)

def _analyze_social_rumors(posts, news_cache):
    analyzed     = []
    ticker_posts = {}
    for post in posts:
        text = post["text"].upper()
        for ticker in BVC:
            if ticker in text or BVC[ticker]["n"].upper().split()[0] in text:
                if ticker not in ticker_posts:
                    ticker_posts[ticker] = []
                ticker_posts[ticker].append(post["text"])
    for ticker, mentions in ticker_posts.items():
        if not mentions:
            continue
        info        = BVC[ticker]
        recent_news = news_cache.get("company_news", {}).get(ticker, [])
        news_summary = [n.get("resume", "") for n in recent_news[:3]]
        prompt = (
            f"Posts sociaux sur {ticker} ({info['n']}).\n"
            f"POSTS: {json.dumps(mentions[:5], ensure_ascii=False)}\n"
            f"NEWS RECENTES: {json.dumps(news_summary, ensure_ascii=False)}\n\n"
            'Reponds en JSON:\n'
            '{"rumeur_detectee":true,"type_rumeur":"resultats|contrat|dividende|fusion|autre|aucune",'
            '"description_rumeur":"courte","consistance_fondamentaux":"forte|moderee|faible|contradictoire",'
            '"score_credibilite":0-100,"direction_prevue":"hausse|baisse|neutre",'
            '"recommandation_trader":"entrer|surveiller|ignorer","raisonnement":"1 phrase"}'
        )
        result = groq_json(prompt, max_tokens=400)
        if not result or not result.get("rumeur_detectee"):
            continue
        score = result.get("score_credibilite", 0)
        analyzed.append({
            "ticker":      ticker,
            "rumeur":      result.get("type_rumeur", ""),
            "description": result.get("description_rumeur", ""),
            "consistance": result.get("consistance_fondamentaux", ""),
            "score":       score,
            "direction":   result.get("direction_prevue", "neutre"),
            "action":      result.get("recommandation_trader", "ignorer"),
            "raison":      result.get("raisonnement", ""),
            "posts_count": len(mentions),
        })
        urgency = min(80, 30 + score * 0.5)
        if score >= 60:
            add_to_pending("social_rumeur", result, urgency_score=urgency, ticker=ticker)
        time.sleep(1.5)
    return analyzed

def get_twitter_signals():
    signals  = []
    accounts = [("federalreserve","FED"),("BankAlMaghrib","BAM"),("ecb","ECB"),("IMFNews","FMI"),("ReutersBiz","Reuters")]
    nitter   = ["https://nitter.poast.org","https://nitter.privacydev.net","https://nitter.1d4.us"]
    for account, label in accounts:
        for n in nitter:
            try:
                r = requests.get(f"{n}/{account}/rss", headers=HEADERS, timeout=6)
                if r.status_code != 200:
                    continue
                items = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", r.text)
                for item in items[1:3]:
                    clean = re.sub(r"<[^>]+>","",item).strip()
                    if len(clean) > 20:
                        signals.append({"source": label, "text": clean[:200]})
                break
            except:
                continue
    return signals[:8]


# ═══════════════════════════════════════════════════════════
# MARKET DATA
# ═══════════════════════════════════════════════════════════

def get_tv_analysis(ticker):
    try:
        h = TA_Handler(symbol=ticker, screener="morocco", exchange="CSE", interval=Interval.INTERVAL_15_MINUTES)
        a = h.get_analysis()
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
        }
    except Exception as e:
        print(f"[TV] {ticker}: {e}")
        return None

def get_global_macro():
    macro   = {}
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
                    prev = float(closes.iloc[-2])
                    curr = float(closes.iloc[-1])
                    chg  = (curr - prev) / prev * 100 if prev != 0 else 0
                    macro[name] = {"price": round(curr, 4), "change": round(chg, 3)}
                else:
                    macro[name] = {"price": 0, "change": 0}
            except:
                macro[name] = {"price": 0, "change": 0}
    except Exception as e:
        print(f"[MACRO] {e}")
        for name in symbols:
            macro[name] = {"price": 0, "change": 0}

    vix    = macro.get("vix",   {}).get("price",  20)
    us10y  = macro.get("us10y", {}).get("price",   4.0)
    us2y   = macro.get("us2y",  {}).get("price",   4.5)
    dxy    = macro.get("dxy",   {}).get("price", 103)
    sp_c   = macro.get("sp500", {}).get("change",  0)
    br_c   = macro.get("brent", {}).get("change",  0)
    go_c   = macro.get("gold",  {}).get("change",  0)
    cu_c   = macro.get("copper",{}).get("change",  0)
    ys     = us10y - us2y
    risk_on  = vix < 20 and sp_c > 0 and go_c < 1
    risk_off = vix > 25 or (go_c > 1 and sp_c < 0)
    infl_up  = go_c > 0.5 and br_c > 0.5 and cu_c > 0
    rec_risk = ys < 0

    bvc_out = {
        "Banque":     "POSITIF" if risk_on and not rec_risk else ("NEGATIF" if rec_risk else "NEUTRE"),
        "Mines":      "TRES_POSITIF" if dxy > 105 else ("POSITIF" if infl_up else "NEUTRE"),
        "Chimie":     "TRES_POSITIF" if dxy > 105 else ("POSITIF" if infl_up else "NEUTRE"),
        "Energie":    "POSITIF" if br_c > 1 else ("NEGATIF" if br_c < -2 else "NEUTRE"),
        "Immobilier": "POSITIF" if not rec_risk else "NEGATIF",
        "Telecom":    "POSITIF" if risk_off else "NEUTRE",
        "Agro":       "NEGATIF" if br_c > 2 else ("POSITIF" if br_c < -1 else "NEUTRE"),
        "Transport":  "NEGATIF" if br_c > 2 else ("POSITIF" if br_c < -1 else "NEUTRE"),
    }
    macro["_d"] = {
        "yield_spread": ys,
        "risk_regime":  "RISK_ON" if risk_on else ("RISK_OFF" if risk_off else "NEUTRE"),
        "inflation":    "INFLATION" if infl_up else "STABLE",
        "recession":    rec_risk,
        "vix_level":    "EXTREME" if vix > 35 else ("ELEVE" if vix > 25 else ("NORMAL" if vix > 15 else "FAIBLE")),
        "dollar":       "FORT" if dxy > 105 else ("FAIBLE" if dxy < 100 else "NEUTRE"),
        "bvc_outlook":  bvc_out,
    }
    return macro

def get_rates():
    rates = {"fed": 5.25, "ecb": 3.5, "bam": 3.0, "bam_news": []}
    try:
        r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS", headers=HEADERS, timeout=10)
        lines = r.text.strip().split("\n")
        if len(lines) > 1:
            v = float(lines[-1].split(",")[1])
            if 0 < v < 20:
                rates["fed"] = v
    except:
        pass
    try:
        r    = requests.get("https://www.bkam.ma/Politique-monetaire", headers=HEADERS, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        text = r.text.lower()
        for m in re.findall(r'(\d+[.,]\d+)\s*%', text):
            v = float(m.replace(",","."))
            if 0.5 < v < 10:
                rates["bam"] = v
                break
        for el in soup.select("p,h2,h3,li")[:15]:
            t = el.get_text(strip=True)
            if any(k in t.lower() for k in ["taux","monetaire","inflation","reserve"]):
                if 20 < len(t) < 250:
                    rates["bam_news"].append(t[:200])
        rates["bam_news"] = list(dict.fromkeys(rates["bam_news"]))[:4]
    except:
        pass
    return rates

def get_masi():
    try:
        h = TA_Handler(symbol="MASI", screener="morocco", exchange="CSE", interval=Interval.INTERVAL_15_MINUTES)
        a = h.get_analysis()
        return {
            "close":  a.indicators.get("close", 0),
            "change": a.indicators.get("change", 0),
            "rsi":    a.indicators.get("RSI", 50),
            "rec":    a.summary.get("RECOMMENDATION", "NEUTRAL"),
            "buy":    a.summary.get("BUY", 0),
            "sell":   a.summary.get("SELL", 0),
        }
    except:
        return {"close": 0, "change": 0, "rsi": 50, "rec": "NEUTRAL", "buy": 0, "sell": 0}

def _scrape_boursenews():
    try:
        r    = requests.get("https://www.boursenews.ma/", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        news = [item.get_text(strip=True)[:160] for item in soup.select("article,h2 a,h3 a")[:10] if len(item.get_text(strip=True)) > 20]
        return list(dict.fromkeys(news))[:5]
    except:
        return []

def _scrape_ammc_news():
    try:
        r    = requests.get("https://www.ammc.ma/fr/actualites", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        items = [i.get_text(strip=True)[:160] for i in soup.select(".views-row,article,h3 a,h2 a")[:6] if len(i.get_text(strip=True)) > 20]
        return list(dict.fromkeys(items))[:4]
    except:
        return []

def _scrape_oc():
    try:
        r    = requests.get("https://www.oc.gov.ma/fr/publications", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        items = [i.get_text(strip=True)[:160] for i in soup.select("article,.views-row,h3 a,h2 a")[:5] if len(i.get_text(strip=True)) > 20]
        return list(dict.fromkeys(items))[:3]
    except:
        return []


# ═══════════════════════════════════════════════════════════
# VOLUME PROFILE
# ═══════════════════════════════════════════════════════════

def get_volume_profile(ticker_yf, period="3mo", bins=30):
    try:
        data = yf.download(ticker_yf, period=period, interval="1d", progress=False, auto_adjust=True)
        if data is None or len(data) < 5:
            return None
        data   = data.dropna()
        closes = data["Close"].values.flatten()
        highs  = data["High"].values.flatten()
        lows   = data["Low"].values.flatten()
        vols   = data["Volume"].values.flatten()
        p_min  = float(np.min(lows))
        p_max  = float(np.max(highs))
        if p_max <= p_min:
            return None
        bins_arr     = np.linspace(p_min, p_max, bins + 1)
        vol_at_price = np.zeros(bins)
        for i in range(len(data)):
            h, l, v = float(highs[i]), float(lows[i]), float(vols[i])
            if h == l:
                continue
            for b in range(bins):
                ol = max(l, bins_arr[b])
                oh = min(h, bins_arr[b + 1])
                if oh > ol:
                    vol_at_price[b] += v * (oh - ol) / (h - l)
        poc_idx = int(np.argmax(vol_at_price))
        poc     = float((bins_arr[poc_idx] + bins_arr[poc_idx + 1]) / 2)
        total   = vol_at_price.sum()
        target  = total * 0.70
        sidx    = np.argsort(vol_at_price)[::-1]
        acc, va = 0.0, []
        for idx in sidx:
            acc += vol_at_price[idx]
            va.append(int(idx))
            if acc >= target:
                break
        vah  = float((bins_arr[max(va)] + bins_arr[min(max(va) + 1, bins)]) / 2)
        val  = float((bins_arr[min(va)] + bins_arr[min(min(va) + 1, bins)]) / 2)
        curr = float(closes[-1]) if len(closes) else poc
        if curr < val:
            sig, desc = "ACHAT_FORT", f"Prix sous VAL {val:.2f} - zone achat institutionnel"
        elif curr < poc:
            sig, desc = "ACHAT", f"Entre VAL et POC {poc:.2f} - accumulation"
        elif curr > vah:
            sig, desc = "VENTE", f"Au-dessus VAH {vah:.2f} - distribution"
        elif curr > poc:
            sig, desc = "NEUTRE_HAUT", f"Entre POC et VAH - momentum positif"
        else:
            sig, desc = "NEUTRE", f"Au POC {poc:.2f} - equilibre"
        return {
            "poc": round(poc, 2), "vah": round(vah, 2), "val": round(val, 2),
            "current": round(curr, 2), "signal": sig, "description": desc,
            "dist_poc_pct": round((curr - poc) / poc * 100, 2) if poc else 0,
        }
    except Exception as e:
        print(f"[VP] {ticker_yf}: {e}")
        return None

# ═══════════════════════════════════════════════════════════
# SMART MONEY DETECTION
# ═══════════════════════════════════════════════════════════

def detect_smart_money(analyses):
    smart_money      = []
    sector_activity  = {}
    for ticker, info in BVC.items():
        tv = analyses.get(ticker)
        if not tv:
            continue
        vol     = tv.get("volume", 0)
        avg     = info["v"]
        rsi     = tv.get("rsi", 50)
        close   = tv.get("close", 0)
        ema200  = tv.get("ema200", 0)
        vr      = vol / avg if avg > 0 else 0
        if vr < 4:
            continue
        sm_score = 0
        if vr >= 5:    sm_score += 40
        elif vr >= 4:  sm_score += 25
        if rsi < 35:   sm_score += 25
        elif rsi < 45: sm_score += 15
        if ema200 > 0 and close > ema200 * 0.97:
            sm_score += 15
        buy_sig  = tv.get("buy_signals", 0)
        sell_sig = tv.get("sell_signals", 0)
        if buy_sig > sell_sig * 1.5:
            sm_score += 20
        if sm_score >= 50:
            smart_money.append({
                "ticker":    ticker,
                "name":      info["n"],
                "sector":    info["s"],
                "vol_ratio": round(vr, 1),
                "rsi":       round(rsi, 1),
                "price":     round(close, 2),
                "sm_score":  sm_score,
            })
            sector = info["s"]
            sector_activity[sector] = sector_activity.get(sector, 0) + 1
    sector_coordinated = [s for s, cnt in sector_activity.items() if cnt >= 2]
    return smart_money, sector_coordinated

# ═══════════════════════════════════════════════════════════
# SCORING ADAPTATIF
# ═══════════════════════════════════════════════════════════

def load_learnings():
    if os.path.exists(F["learn"]):
        with open(F["learn"], "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "lessons": [],
        "indicator_weights": {
            "rsi":1.0,"macd":1.0,"ema":1.0,"volume":1.0,"stoch":1.0,"adx":1.0,
            "vp":1.0,"bam_corr":1.0,"brent_corr":1.0,"phos_corr":1.0,
            "macro_regime":1.0,"news_sentiment":1.0,"social_rumeur":1.0,
        },
        "secteurs_favorables": [],
        "secteurs_eviter":     [],
        "accuracy_history":    [],
        "accuracy_rate":       0,
        "total_analyzed":      0,
        "last_updated":        "",
    }

def save_learnings(data):
    with open(F["learn"], "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def score_action(tv, info, vp, macro, rates, learnings, news_data=None, social_data=None):
    if not tv:
        return 0
    w      = learnings.get("indicator_weights", {})
    score  = 50
    rsi    = tv.get("rsi", 50)
    macd   = tv.get("macd", 0)
    macd_s = tv.get("macd_signal", 0)
    macd_h = tv.get("macd_hist", 0)
    close  = tv.get("close", 0)
    ema20  = tv.get("ema20", 0)
    ema50  = tv.get("ema50", 0)
    ema200 = tv.get("ema200", 0)
    vwap   = tv.get("vwap", 0)
    stoch_k = tv.get("stoch_k", 50)
    stoch_d = tv.get("stoch_d", 50)
    adx    = tv.get("adx", 0)
    cci    = tv.get("cci", 0)
    vol    = tv.get("volume", 0)
    avg    = info.get("v", 1)
    buy_s  = tv.get("buy_signals", 0)
    sell_s = tv.get("sell_signals", 0)
    sector = info.get("s", "")
    wr = w.get("rsi", 1)
    wm = w.get("macd", 1)
    we = w.get("ema", 1)
    wv = w.get("volume", 1)
    ws = w.get("stoch", 1)
    wa = w.get("adx", 1)

    if rsi < 25:    score += int(25 * wr)
    elif rsi < 35:  score += int(15 * wr)
    elif rsi < 45:  score += int(7  * wr)
    elif rsi > 75:  score -= int(25 * wr)
    elif rsi > 65:  score -= int(12 * wr)

    if macd > macd_s and macd_h > 0:  score += int(18 * wm)
    elif macd > macd_s:               score += int(8  * wm)
    else:                             score -= int(10 * wm)

    if close > ema20 > ema50 > ema200:    score += int(20 * we)
    elif close > ema20 > ema50:           score += int(12 * we)
    elif close > ema20:                   score += int(5  * we)
    elif close < ema20 < ema50 < ema200:  score -= int(20 * we)
    elif close < ema20 < ema50:           score -= int(12 * we)

    if vwap > 0:
        score += 5 if close > vwap else -5

    if stoch_k < 20 and stoch_k > stoch_d:  score += int(12 * ws)
    elif stoch_k > 80 and stoch_k < stoch_d: score -= int(12 * ws)

    if adx > 30:    score += int(10 * wa)
    elif adx > 20:  score += int(5  * wa)

    if cci < -150:  score += 12
    elif cci < -100: score += 7
    elif cci > 150: score -= 12
    elif cci > 100: score -= 7

    score += int((buy_s - sell_s) * 1.5)

    if avg > 0:
        vr = vol / avg
        if vr > 3:    score += int(18 * wv)
        elif vr > 2:  score += int(12 * wv)
        elif vr > 1.5: score += int(6  * wv)

    if vp:
        wvp = w.get("vp", 1.0)
        sig = vp.get("signal", "NEUTRE")
        if sig == "ACHAT_FORT":  score += int(25 * wvp)
        elif sig == "ACHAT":     score += int(15 * wvp)
        elif sig == "VENTE":     score -= int(20 * wvp)
        d = abs(vp.get("dist_poc_pct", 10))
        if d < 1:  score += int(8 * wvp)
        elif d < 2: score += int(4 * wvp)

    if macro:
        d       = macro.get("_d", {})
        regime  = d.get("risk_regime", "NEUTRE")
        out     = d.get("bvc_outlook", {})
        wma     = w.get("macro_regime", 1.0)
        if regime == "RISK_ON":   score += int(10 * wma)
        elif regime == "RISK_OFF": score -= int(8  * wma)
        so = out.get(sector, "NEUTRE")
        if so == "TRES_POSITIF":  score += int(18 * wma)
        elif so == "POSITIF":     score += int(10 * wma)
        elif so == "NEGATIF":     score -= int(12 * wma)
        vix = macro.get("vix", {}).get("price", 20)
        if vix > 35:   score -= int(20 * wma)
        elif vix > 28: score -= int(10 * wma)
        elif vix < 15: score += int(5  * wma)
        if d.get("recession"): score -= int(10 * wma)

    if rates and info.get("bam"):
        bam_taux = rates.get("bam", 3.0) or 3.0
        wb       = w.get("bam_corr", 1.0)
        if bam_taux <= 2.5:   score += int(15 * wb)
        elif bam_taux <= 3.0: score += int(8  * wb)
        elif bam_taux >= 4.0: score -= int(10 * wb)
        bam_news = " ".join(rates.get("bam_news", [])).lower()
        if any(k in bam_news for k in ["baisse","assouplissement","accomodante"]):
            score += int(10 * wb)
        elif any(k in bam_news for k in ["hausse","restrictive","resserrement","inflation"]):
            score -= int(8  * wb)

    if info.get("br") and macro:
        bc  = macro.get("brent", {}).get("change", 0)
        wb2 = w.get("brent_corr", 1.0)
        if bc > 1:    score += int(8  * wb2)
        elif bc < -2: score -= int(10 * wb2)

    if info.get("ph") and macro:
        dxy = macro.get("dxy", {}).get("price", 103)
        wp  = w.get("phos_corr", 1.0)
        if dxy > 105:  score += int(15 * wp)
        elif dxy < 98: score -= int(8  * wp)

    if news_data:
        wn  = w.get("news_sentiment", 1.0)
        mag = news_data.get("magnitude", "faible")
        imp = news_data.get("impact", "neutre")
        if imp == "hausse" and mag == "fort":    score += int(18 * wn)
        elif imp == "hausse" and mag == "modere": score += int(10 * wn)
        elif imp == "baisse" and mag == "fort":   score -= int(18 * wn)
        elif imp == "baisse" and mag == "modere": score -= int(10 * wn)

    if social_data and social_data.get("score", 0) >= 60:
        wso = w.get("social_rumeur", 1.0)
        if social_data.get("direction") == "hausse":  score += int(12 * wso)
        elif social_data.get("direction") == "baisse": score -= int(12 * wso)

    pdf_cache = load_pdf_cache()
    if close > 0 and info.get("mc") in ["large","mid"]:
        targets = pdf_cache.get("price_targets", {}).get(tv["ticker"], {})
        if targets.get("1m") and targets["1m"] > 0:
            upside = (targets["1m"] - close) / close * 100
            if upside > 5:    score += 10
            elif upside > 2:  score += 5
            elif upside < -5: score -= 10

    if sector in learnings.get("secteurs_favorables", []): score += 10
    if sector in learnings.get("secteurs_eviter", []):      score -= 15
    if info.get("mc") == "large": score += 5

    return max(0, min(100, score))


# ═══════════════════════════════════════════════════════════
# SIGNALS & TRADE LOG
# ═══════════════════════════════════════════════════════════

def run_full_analysis():
    print(f"[BARAKA] Analyse {len(BVC)} titres TV...")
    analyses = {}
    for ticker in BVC:
        a = get_tv_analysis(ticker)
        if a:
            analyses[ticker] = a
        time.sleep(0.35)
    print(f"[BARAKA] {len(analyses)}/{len(BVC)} OK")
    return analyses

def run_vp_for_top(analyses):
    priority = [t for t, i in BVC.items() if i["mc"] in ["large","mid"]]
    top_tv   = sorted(
        [(t, analyses[t].get("buy_signals", 0)) for t in analyses if analyses.get(t, {}).get("buy_signals", 0) > 5],
        key=lambda x: -x[1]
    )[:12]
    tickers  = list(set([t for t, _ in top_tv] + priority))[:18]
    vps      = {}
    for ticker in tickers:
        yf_sym = BVC.get(ticker, {}).get("yf", f"{ticker}.CS")
        vp     = get_volume_profile(yf_sym)
        if vp:
            vps[ticker] = vp
        time.sleep(0.5)
    return vps

def get_top_signals(analyses, vps, macro, rates, learnings, news_c, social_c, n=3):
    news_cache   = news_c.get("company_news", {})
    social_cache = social_c.get("rumeurs_validees", {})
    scored       = []
    pdf_cache    = load_pdf_cache()
    for ticker, info in BVC.items():
        tv  = analyses.get(ticker)
        vp  = vps.get(ticker)
        if not tv:
            continue
        nd = news_cache.get(ticker, [None])[0] if news_cache.get(ticker) else None
        sd = social_cache.get(ticker)
        s  = score_action(tv, info, vp, macro, rates, learnings, nd, sd)
        close = tv.get("close", 0)
        if close <= 0 or s < 55:
            continue
        tp    = 0.06 if s > 80 else 0.05 if s > 70 else 0.04 if s > 60 else 0.03
        proba = min(95, 45 + s * 0.5)
        pt    = pdf_cache.get("price_targets", {}).get(ticker, {})
        scored.append({
            "ticker":         ticker,
            "name":           info["n"],
            "sector":         info["s"],
            "mc":             info.get("mc", "small"),
            "score":          s,
            "price":          close,
            "target":         round(close * (1 + tp), 2),
            "stop":           round(close * 0.98, 2),
            "gain_pct":       round(tp * 100, 1),
            "proba":          round(proba),
            "rsi":            round(tv.get("rsi", 50), 1),
            "macd_cross":     tv.get("macd", 0) > tv.get("macd_signal", 0),
            "adx":            round(tv.get("adx", 0), 1),
            "change":         round(tv.get("change", 0), 2),
            "recommendation": tv.get("recommendation", "NEUTRAL"),
            "buy_signals":    tv.get("buy_signals", 0),
            "sell_signals":   tv.get("sell_signals", 0),
            "volume":         tv.get("volume", 0),
            "avg_volume":     info["v"],
            "stoch_k":        round(tv.get("stoch_k", 50), 1),
            "bam":            info.get("bam", False),
            "brent":          info.get("br", False),
            "phos":           info.get("ph", False),
            "vp_signal":      vp.get("signal", "N/A") if vp else "N/A",
            "vp_poc":         vp.get("poc", 0) if vp else 0,
            "vp_vah":         vp.get("vah", 0) if vp else 0,
            "vp_val":         vp.get("val", 0) if vp else 0,
            "vp_desc":        vp.get("description", "") if vp else "",
            "pdf_target_1m":  pt.get("1m"),
            "pdf_target_3m":  pt.get("3m"),
            "pdf_signal":     pt.get("signal", ""),
            "news_sentiment": nd.get("sentiment", "") if nd else "",
            "social_rumeur":  social_cache.get(ticker, {}).get("description", ""),
        })
    return sorted(scored, key=lambda x: -x["score"])[:n]

def get_bear_signals(analyses, vps, macro, rates, learnings, n=3):
    bear = []
    for ticker, info in BVC.items():
        tv = analyses.get(ticker)
        vp = vps.get(ticker)
        if not tv:
            continue
        s     = score_action(tv, info, vp, macro, rates, learnings)
        close = tv.get("close", 0)
        if close <= 0 or s > 40:
            continue
        reasons = []
        if tv.get("rsi", 50) > 70:
            reasons.append(f"RSI surachete {tv['rsi']:.0f}")
        if tv.get("macd", 0) < tv.get("macd_signal", 0):
            reasons.append("MACD baissier")
        if close < tv.get("ema20", 0) < tv.get("ema50", 0):
            reasons.append("Sous EMA20/50")
        if vp and vp.get("signal") == "VENTE":
            reasons.append(f"Au-dessus VAH {vp.get('vah', 0):.2f}")
        if macro and macro.get("_d", {}).get("risk_regime") == "RISK_OFF":
            reasons.append("Risk-OFF")
        bear.append({
            "ticker": ticker, "name": info["n"], "sector": info["s"],
            "score":  s, "price": close,
            "change": round(tv.get("change", 0), 2),
            "rsi":    round(tv.get("rsi", 50), 1),
            "reason": " . ".join(reasons) or "Score faible",
        })
    return sorted(bear, key=lambda x: x["score"])[:n]

def check_volume_alerts(analyses):
    alerts = []
    for ticker, info in BVC.items():
        a = analyses.get(ticker)
        if not a:
            continue
        vol = a.get("volume", 0)
        avg = info["v"]
        if avg > 0 and vol > avg * VOL_THRESHOLD:
            alerts.append({
                "ticker":     ticker,
                "name":       info["n"],
                "sector":     info["s"],
                "volume":     vol,
                "avg_volume": avg,
                "ratio":      round(vol / avg, 1),
                "price":      a.get("close", 0),
                "change":     a.get("change", 0),
                "rsi":        a.get("rsi", 50),
            })
    return sorted(alerts, key=lambda x: -x["ratio"])

def get_hold_candidates(analyses, vps, macro, rates, learnings, n=2):
    candidates = []
    pdf_cache  = load_pdf_cache()
    for ticker, info in BVC.items():
        tv = analyses.get(ticker)
        vp = vps.get(ticker)
        if not tv:
            continue
        s      = score_action(tv, info, vp, macro, rates, learnings)
        close  = tv.get("close", 0)
        ema200 = tv.get("ema200", 0)
        if close <= 0 or s < 78:
            continue
        if ema200 > 0 and close > ema200 * 0.93:
            pt = pdf_cache.get("price_targets", {}).get(ticker, {})
            candidates.append({
                "ticker":       ticker,
                "name":         info["n"],
                "sector":       info["s"],
                "score":        s,
                "price":        close,
                "target30":     round(close * 1.30, 2),
                "proba":        round(min(82, 40 + s * 0.5)),
                "pdf_target_3m": pt.get("3m"),
                "pdf_signal":   pt.get("signal", ""),
            })
    return sorted(candidates, key=lambda x: -x["score"])[:n]

def load_trades():
    if os.path.exists(F["trades"]):
        with open(F["trades"], "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def get_open_trades():
    return [t for t in load_trades() if t.get("status") == "open"]

def get_week_pnl():
    trades     = load_trades()
    today      = datetime.date.today()
    ws         = today - datetime.timedelta(days=today.weekday())
    wt         = [t for t in trades if t.get("date", "") >= str(ws)]
    pnl        = sum(t.get("pnl_pct", 0) for t in wt if t.get("status") == "closed")
    wins       = sum(1 for t in wt if t.get("pnl_pct", 0) > 0 and t.get("status") == "closed")
    total      = sum(1 for t in wt if t.get("status") == "closed")
    return {
        "total_pnl": round(pnl, 2),
        "wins":      wins,
        "total":     total,
        "open":      len(get_open_trades()),
        "win_rate":  round(wins / total * 100) if total > 0 else 0,
    }


# ═══════════════════════════════════════════════════════════
# HTML BUILDERS - FIXED (no escaped quotes in f-strings)
# ═══════════════════════════════════════════════════════════

def _color_change(v):
    return "#00C87A" if v >= 0 else "#FF4560"

def _sign(v):
    return "+" if v >= 0 else ""

def build_signal_card(s, rank):
    sc    = "#00C87A" if s["score"] >= 70 else "#C9A84C"
    rc    = "#FF4560" if s["rsi"] > 70 else "#00C87A" if s["rsi"] < 35 else "#C9A84C"
    vr    = round(s["volume"] / s["avg_volume"], 1) if s["avg_volume"] > 0 else 1
    vc    = "#00C87A" if vr > 2 else "#F59E0B" if vr > 1.5 else "#9CA3AF"
    cc    = _color_change(s["change"])
    macd_txt = "Haussier" if s["macd_cross"] else "Baissier"
    vp_color = "#00C87A" if "ACHAT" in s.get("vp_signal","") else "#FF4560" if "VENTE" in s.get("vp_signal","") else "#C9A84C"

    # Badges correlation
    badges = ""
    if s.get("bam"):
        badges += "<span style='font-size:9px;background:rgba(0,150,255,0.15);color:#60A5FA;padding:2px 6px;border-radius:3px;margin-left:3px'>BAM</span>"
    if s.get("brent"):
        badges += "<span style='font-size:9px;background:rgba(255,140,0,0.15);color:#FB923C;padding:2px 6px;border-radius:3px;margin-left:3px'>BRENT</span>"
    if s.get("phos"):
        badges += "<span style='font-size:9px;background:rgba(100,200,100,0.15);color:#4ADE80;padding:2px 6px;border-radius:3px;margin-left:3px'>PHOSPHATE</span>"
    if s.get("news_sentiment"):
        sent = s["news_sentiment"].upper()
        badges += f"<span style='font-size:9px;background:rgba(245,158,11,0.15);color:#F59E0B;padding:2px 6px;border-radius:3px;margin-left:3px'>NEWS {sent}</span>"
    if s.get("social_rumeur"):
        badges += "<span style='font-size:9px;background:rgba(139,92,246,0.15);color:#8B5CF6;padding:2px 6px;border-radius:3px;margin-left:3px'>RUMEUR</span>"
    if s.get("pdf_signal"):
        pdf_sig = s["pdf_signal"]
        badges += f"<span style='font-size:9px;background:rgba(0,200,122,0.1);color:#00C87A;padding:2px 6px;border-radius:3px;margin-left:3px'>AMMC {pdf_sig}</span>"

    # PDF target row - pre-computed to avoid quote nesting
    pdf_row = ""
    if s.get("pdf_target_1m"):
        t1m     = s["pdf_target_1m"]
        pdf_sig = s.get("pdf_signal", "")
        pdf_row = (
            "<tr>"
            "<td style='color:#6B7280;padding:3px 0'>AMMC</td>"
            f"<td colspan='3' style='color:#00C87A;text-align:right'>Cible 1M: {t1m:.2f} MAD - Signal: {pdf_sig}</td>"
            "</tr>"
        )

    # Social rumeur row
    social_row = ""
    if s.get("social_rumeur"):
        rumeur_text = s["social_rumeur"][:100]
        social_row  = (
            "<tr>"
            f"<td colspan='4' style='color:#9CA3AF;font-size:11px;padding:3px 0'>{rumeur_text}</td>"
            "</tr>"
        )

    change_str = f"{_sign(s['change'])}{s['change']}%"
    poc_str    = f"{s.get('vp_poc', 0):.2f}"
    vah_str    = f"{s.get('vp_vah', 0):.2f}"
    val_str    = f"{s.get('vp_val', 0):.2f}"

    return (
        f"<div style='background:#171C2C;border-radius:10px;padding:16px;margin-bottom:14px;border-left:4px solid {sc}'>"
        f"<div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px'>"
        f"<div><span style='font-size:20px;font-weight:900;color:{sc};font-family:monospace'>#{rank} {s['ticker']}</span>"
        f"<span style='font-size:10px;color:#6B7280;margin-left:8px'>{s['name']}</span><br>"
        f"<span style='font-size:10px;background:rgba(201,168,76,0.1);color:#C9A84C;padding:2px 6px;border-radius:3px'>{s['sector']}</span>"
        f"{badges}</div>"
        f"<div style='text-align:right'>"
        f"<span style='background:rgba(0,200,122,0.15);color:#00C87A;border:1px solid rgba(0,200,122,0.3);font-size:10px;padding:3px 10px;border-radius:4px;font-weight:700'>ACHAT</span><br>"
        f"<span style='font-size:11px;color:{cc};font-weight:700;display:block;margin-top:3px'>{change_str}</span>"
        f"</div></div>"
        f"<table style='width:100%;font-size:12px;border-collapse:collapse'>"
        f"<tr><td style='color:#6B7280;padding:3px 0'>Entree</td>"
        f"<td style='color:#E8E4D6;font-weight:700;text-align:right'>{s['price']:.2f} MAD</td>"
        f"<td style='color:#6B7280;padding:3px 12px'>Cible</td>"
        f"<td style='color:#00C87A;font-weight:700;text-align:right'>{s['target']:.2f} (+{s['gain_pct']}%)</td></tr>"
        f"<tr><td style='color:#6B7280;padding:3px 0'>Stop</td>"
        f"<td style='color:#FF4560;font-weight:700;text-align:right'>{s['stop']:.2f} MAD</td>"
        f"<td style='color:#6B7280;padding:3px 12px'>RSI</td>"
        f"<td style='color:{rc};font-weight:700;text-align:right'>{s['rsi']}</td></tr>"
        f"<tr><td style='color:#6B7280;padding:3px 0'>MACD</td>"
        f"<td colspan='3' style='color:#9CA3AF;text-align:right'>{macd_txt}</td></tr>"
        f"<tr><td style='color:#6B7280;padding:3px 0'>Volume</td>"
        f"<td colspan='3' style='color:{vc};text-align:right'>x{vr} ({int(s['volume']):,} vs {int(s['avg_volume']):,})</td></tr>"
        f"<tr><td style='color:#6B7280;padding:3px 0'>VP</td>"
        f"<td colspan='3' style='color:{vp_color};text-align:right;font-weight:700'>"
        f"{s.get('vp_signal','N/A')} - POC {poc_str} - VAH {vah_str} - VAL {val_str}</td></tr>"
        f"{pdf_row}{social_row}"
        f"</table>"
        f"<div style='margin-top:8px'>"
        f"<div style='display:flex;justify-content:space-between;font-size:11px;margin-bottom:3px'>"
        f"<span style='color:#6B7280'>Score Baraka</span>"
        f"<span style='color:{sc};font-weight:700'>{s['score']}/100</span></div>"
        f"<div style='background:#0A0D14;border-radius:3px;height:4px'>"
        f"<div style='height:100%;border-radius:3px;background:{sc};width:{s['score']}%'></div></div>"
        f"<div style='display:flex;justify-content:space-between;font-size:11px;margin-top:5px'>"
        f"<span style='color:#6B7280'>Proba +2%</span>"
        f"<span style='color:{sc};font-weight:700'>{s['proba']}%</span></div>"
        f"</div></div>"
    )


def build_pending_section(pending_items):
    if not pending_items:
        return ""
    by_cat = {}
    for item in pending_items:
        cat = item.get("category", "other")
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(item)

    html = (
        "<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);"
        "border-radius:10px;padding:14px;margin-bottom:14px'>"
        "<div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;"
        "margin-bottom:12px'>ANALYSE DE FOND - RAPPORTS ET NEWS</div>"
    )

    # PDFs AMMC
    pdf_items = by_cat.get("pdf_ammc", [])
    if pdf_items:
        html += "<div style='margin-bottom:10px'><div style='font-size:10px;color:#60A5FA;margin-bottom:6px'>RAPPORTS AMMC ANALYSES</div>"
        for item in pdf_items[:4]:
            c      = item.get("content", {})
            ticker = c.get("ticker", "?")
            signal = c.get("signal", "NEUTRE")
            sc_map = {
                "ACHAT_FORT":"#00C87A","ACHAT":"#4ADE80",
                "NEUTRE":"#C9A84C","VENTE":"#FB923C","VENTE_FORTE":"#FF4560"
            }
            sc  = sc_map.get(signal, "#C9A84C")
            t1m = c.get("targets", {}).get("1m")
            t3m = c.get("targets", {}).get("3m")
            t1m_str = f"{t1m:.2f} MAD" if t1m else "N/A"
            t3m_str = f"{t3m:.2f} MAD" if t3m else "N/A"
            resume  = c.get("resume", "")[:120]
            html += (
                f"<div style='background:#171C2C;border-radius:6px;padding:10px;margin-bottom:6px;border-left:2px solid {sc}'>"
                f"<div style='display:flex;justify-content:space-between;align-items:center'>"
                f"<span style='color:{sc};font-weight:700;font-family:monospace'>{ticker}</span>"
                f"<span style='font-size:10px;background:rgba(0,0,0,0.3);color:{sc};padding:2px 8px;border-radius:3px'>{signal}</span></div>"
                f"<div style='font-size:11px;color:#9CA3AF;margin-top:4px'>{resume}</div>"
                f"<div style='font-size:11px;color:#6B7280;margin-top:3px'>"
                f"Cible 1M: <span style='color:{sc}'>{t1m_str}</span> - "
                f"Cible 3M: <span style='color:{sc}'>{t3m_str}</span></div>"
                f"</div>"
            )
        html += "</div>"

    # News societes
    news_items = by_cat.get("company_news", [])
    if news_items:
        html += "<div style='margin-bottom:10px'><div style='font-size:10px;color:#F59E0B;margin-bottom:6px'>NEWS SOCIETES</div>"
        for item in news_items[:5]:
            c      = item.get("content", {})
            ticker = c.get("ticker", "?")
            imp    = c.get("impact", "neutre")
            ic     = "#00C87A" if imp == "hausse" else "#FF4560" if imp == "baisse" else "#C9A84C"
            resume = c.get("resume", "")[:80]
            mag    = c.get("magnitude", "")
            html += (
                f"<div style='display:flex;justify-content:space-between;padding:6px 0;"
                f"border-bottom:1px solid rgba(255,255,255,0.04);font-size:12px'>"
                f"<div><span style='color:#E8E4D6;font-weight:700;font-family:monospace'>{ticker}</span>"
                f"<span style='color:#9CA3AF;font-size:11px;margin-left:6px'>{resume}</span></div>"
                f"<span style='color:{ic};font-weight:700;font-size:10px'>{imp.upper()} {mag}</span></div>"
            )
        html += "</div>"

    # Rumeurs sociales
    social_items = by_cat.get("social_rumeur", [])
    if social_items:
        html += "<div style='margin-bottom:10px'><div style='font-size:10px;color:#8B5CF6;margin-bottom:6px'>RUMEURS RESEAUX SOCIAUX</div>"
        for item in social_items[:3]:
            c      = item.get("content", {})
            ticker = item.get("ticker", "?")
            score  = c.get("score_credibilite", 0)
            sc     = "#00C87A" if score >= 70 else "#F59E0B" if score >= 50 else "#9CA3AF"
            desc   = c.get("description_rumeur", "")[:100]
            raison = c.get("raisonnement", "")[:80]
            html += (
                f"<div style='background:#171C2C;border-radius:6px;padding:8px;margin-bottom:5px'>"
                f"<div style='display:flex;justify-content:space-between'>"
                f"<span style='color:#8B5CF6;font-weight:700;font-family:monospace'>{ticker}</span>"
                f"<span style='color:{sc};font-size:10px'>Credibilite {score}%</span></div>"
                f"<div style='font-size:11px;color:#9CA3AF;margin-top:3px'>{desc} - {raison}</div>"
                f"</div>"
            )
        html += "</div>"

    html += "</div>"
    return html


# ═══════════════════════════════════════════════════════════
# MAIN EMAIL BUILDER
# ═══════════════════════════════════════════════════════════

def run_alert(subject_type):
    print(f"\n[BARAKA] === {subject_type.upper()} ===")
    learnings    = load_learnings()
    analyses     = run_full_analysis()
    macro        = get_global_macro()
    rates        = get_rates()
    masi         = get_masi()
    vps          = run_vp_for_top(analyses)
    news_cache   = load_news_cache()
    social_cache = load_social_cache()
    signals      = get_top_signals(analyses, vps, macro, rates, learnings, news_cache, social_cache, n=3)
    bear_sigs    = get_bear_signals(analyses, vps, macro, rates, learnings, n=3)
    open_trades  = get_open_trades()
    vol_alerts   = check_volume_alerts(analyses)
    week_pnl     = get_week_pnl()
    hold_cands   = get_hold_candidates(analyses, vps, macro, rates, learnings) if subject_type == "cloture" else []
    pending_items = flush_pending()

    if subject_type == "matin":
        with open(f"signals_{datetime.date.today()}.json", "w") as f:
            json.dump(signals, f, ensure_ascii=False)

    # News aggregation
    google_news  = get_google_news_general([
        "Bourse Casablanca 2026","Bank Al-Maghrib taux 2026",
        "OCP Maroc 2026","Maroc economie 2026","Fed rate 2026"
    ])
    twitter_sigs = get_twitter_signals()
    boursenews   = _scrape_boursenews()
    ammc_news    = _scrape_ammc_news()

    # Groq synthesis
    acc     = learnings.get("accuracy_rate", 0)
    derived = macro.get("_d", {})
    pending_summary = [
        f"{p['category']}: {p.get('content',{}).get('ticker','?')} urgence {p['urgency']}"
        for p in (pending_items or [])[:5]
    ]
    prompt = (
        f"Tu es Baraka, trader Wall Street BVC. Il est {subject_type}.\n\n"
        f"REGIME: {derived.get('risk_regime','?')} - VIX: {macro.get('vix',{}).get('price',20):.1f} - MASI: {masi.get('change',0):+.2f}%\n"
        f"BRENT: {macro.get('brent',{}).get('change',0):+.2f}% - OR: {macro.get('gold',{}).get('change',0):+.2f}%\n"
        f"S&P500: {macro.get('sp500',{}).get('change',0):+.2f}% - YIELD SPREAD: {derived.get('yield_spread',0):+.3f}%\n"
        f"BAM: {rates.get('bam',3.0)}% - FED: {rates.get('fed',5.25)}% - ECB: {rates.get('ecb',3.5)}%\n"
        f"TOP SIGNAUX: {[s['ticker']+' score:'+str(s['score'])+' VP:'+s.get('vp_signal','?') for s in signals]}\n"
        f"BEAR: {[b['ticker']+':'+b['reason'][:50] for b in bear_sigs]}\n"
        f"ANALYSES FOND: {pending_summary}\n"
        f"SECTEURS FAVORABLES: {learnings.get('secteurs_favorables',[])}\n"
        f"PRECISION: {acc}%\n\n"
    )
    if subject_type == "matin":
        prompt += "Dis en 4 phrases: 1) Regime et impact BVC 2) Pourquoi ces 3 actions (catalyseur precis) 3) Smart money et VP confirment? 4) Timing et risque principal"
    elif subject_type == "midi":
        prompt += "Dis en 3 phrases: 1) Garder ou vendre les positions? 2) Quelle action switcher? 3) Risque principal"
    else:
        prompt += "Dis en 4 phrases: 1) Bilan seance 2) Cloturer ou tenir? 3) Hold semaine justifie (+30% min)? 4) Setup demain"
    prompt += "\n\nFrancais. Style trader. Pas de markdown."

    synthesis = groq_call(prompt, max_tokens=400, temp=0.2)

    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    if subject_type == "matin":
        window, instr, ch = "FENETRE 1 - 10h00-12h00", "Tu achetes maintenant", "#00C87A"
    elif subject_type == "midi":
        window, instr, ch = "FENETRE 2 - 12h00-14h00", "Point mi-journee", "#F59E0B"
    else:
        window, instr, ch = "CLOTURE - 15h15", "Decision finale", "#C9A84C"

    # Macro section
    regime  = derived.get("risk_regime", "NEUTRE")
    rg_c    = "#00C87A" if regime == "RISK_ON" else "#FF4560" if regime == "RISK_OFF" else "#C9A84C"
    vix_v   = macro.get("vix", {}).get("price", 20)
    bvc_out = derived.get("bvc_outlook", {})
    sp500_c = macro.get("sp500", {}).get("change", 0)
    brent_c = macro.get("brent", {}).get("change", 0)

    outlook_spans = ""
    for k, v in bvc_out.items():
        if v in ["POSITIF","TRES_POSITIF"]:
            oc = "0,200,122"
            tc = "#00C87A"
        elif v == "NEGATIF":
            oc = "255,69,96"
            tc = "#FF4560"
        else:
            oc = "201,168,76"
            tc = "#C9A84C"
        outlook_spans += (
            f"<span style='font-size:10px;background:rgba({oc},0.15);color:{tc};"
            f"padding:2px 8px;border-radius:4px;margin:2px;display:inline-block'>{k}: {v}</span>"
        )

    ys_val  = derived.get("yield_spread", 0)
    ys_c    = "#FF4560" if ys_val < 0 else "#00C87A"
    ys_str  = f"{_sign(ys_val)}{ys_val:.3f}%"
    masi_c  = _color_change(masi.get("change", 0))

    macro_html = (
        "<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);"
        "border-radius:10px;padding:14px;margin-bottom:14px'>"
        "<div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>MACRO GLOBAL - REGIME</div>"
        "<div style='display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap'>"
        f"<div style='flex:1;min-width:70px;background:#171C2C;border-radius:8px;padding:8px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:3px'>REGIME</div>"
        f"<div style='font-size:12px;font-weight:900;color:{rg_c}'>{regime}</div></div>"
        f"<div style='flex:1;min-width:70px;background:#171C2C;border-radius:8px;padding:8px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:3px'>VIX</div>"
        f"<div style='font-size:12px;font-weight:900;color:{'#FF4560' if vix_v > 25 else '#00C87A'}'>{vix_v:.1f}</div></div>"
        f"<div style='flex:1;min-width:70px;background:#171C2C;border-radius:8px;padding:8px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:3px'>S&P500</div>"
        f"<div style='font-size:12px;font-weight:900;color:{_color_change(sp500_c)}'>{_sign(sp500_c)}{sp500_c:.2f}%</div></div>"
        f"<div style='flex:1;min-width:70px;background:#171C2C;border-radius:8px;padding:8px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:3px'>BRENT</div>"
        f"<div style='font-size:12px;font-weight:900;color:{_color_change(brent_c)}'>{_sign(brent_c)}{brent_c:.2f}%</div></div>"
        f"<div style='flex:1;min-width:70px;background:#171C2C;border-radius:8px;padding:8px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:3px'>BAM</div>"
        f"<div style='font-size:12px;font-weight:900;color:#60A5FA'>{rates.get('bam',3.0)}%</div></div>"
        "</div>"
        f"<div style='font-size:11px;color:#6B7280;margin-bottom:6px'>"
        f"Fed: <span style='color:#60A5FA'>{rates.get('fed',5.25)}%</span> - "
        f"ECB: <span style='color:#60A5FA'>{rates.get('ecb',3.5)}%</span> - "
        f"Yield 10Y-2Y: <span style='color:{ys_c}'>{ys_str}</span></div>"
        f"<div>{outlook_spans}</div>"
        "</div>"
    )

    # BAM news
    bam_news_html = ""
    if rates.get("bam_news"):
        bam_rows = ""
        for n in rates["bam_news"][:3]:
            bam_rows += f"<div style='font-size:11px;color:#9CA3AF;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04)'>{n}</div>"
        bam_news_html = (
            "<div style='background:rgba(0,100,255,0.06);border:1px solid rgba(0,100,255,0.2);"
            "border-radius:10px;padding:12px;margin-bottom:14px'>"
            "<div style='font-size:10px;color:#60A5FA;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px'>BAM - PUBLICATIONS</div>"
            f"{bam_rows}</div>"
        )

    # Synthesis
    synth_html = ""
    if synthesis:
        synth_html = (
            "<div style='background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.25);"
            "border-radius:10px;padding:14px;margin-bottom:14px'>"
            f"<div style='font-size:10px;color:#8B5CF6;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px'>SYNTHESE BARAKA - GROQ AI - Precision {acc}%</div>"
            f"<div style='font-size:13px;color:#E8E4D6;line-height:1.8'>{synthesis}</div>"
            "</div>"
        )

    # Signals
    signals_html = "".join(build_signal_card(s, i + 1) for i, s in enumerate(signals))

    # Bear signals
    bear_html = ""
    if bear_sigs:
        bear_rows = ""
        for b in bear_sigs:
            bear_rows += (
                f"<div style='background:#1A0D10;border-radius:8px;padding:10px;margin-bottom:6px;border-left:3px solid #FF4560'>"
                f"<div style='display:flex;justify-content:space-between'>"
                f"<span style='color:#FF4560;font-weight:700;font-family:monospace'>{b['ticker']}</span>"
                f"<span style='font-size:10px;background:rgba(255,69,96,0.15);color:#FF4560;padding:2px 8px;border-radius:4px'>EVITER</span></div>"
                f"<div style='font-size:11px;color:#9CA3AF;margin-top:4px'>Score {b['score']}/100 - RSI {b['rsi']} - {b['reason'][:100]}</div>"
                f"</div>"
            )
        bear_html = (
            "<div style='background:rgba(255,69,96,0.04);border:1px solid rgba(255,69,96,0.2);"
            "border-radius:10px;padding:14px;margin-bottom:14px'>"
            "<div style='font-size:10px;color:#FF4560;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>ACTIONS A EVITER</div>"
            f"{bear_rows}</div>"
        )

    # Open positions
    open_html = ""
    if open_trades:
        open_rows = ""
        for t in open_trades:
            ticker_t = t.get("ticker", "?")
            entry_t  = t.get("entry", 0)
            target_t = t.get("target", 0)
            open_rows += (
                f"<div style='display:flex;justify-content:space-between;padding:6px 0;"
                f"border-bottom:1px solid rgba(255,255,255,0.05);font-size:12px'>"
                f"<span style='color:#00C87A;font-weight:700;font-family:monospace'>{ticker_t}</span>"
                f"<span style='color:#6B7280'>Entree {entry_t:.2f}</span>"
                f"<span style='color:#C9A84C'>Cible {target_t:.2f}</span></div>"
            )
        open_html = (
            "<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);"
            "border-radius:10px;padding:14px;margin-bottom:14px'>"
            "<div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>POSITIONS OUVERTES</div>"
            f"{open_rows}</div>"
        )

    # Hold semaine - FIXED (no escaped quotes)
    hold_html = ""
    if hold_cands and subject_type == "cloture":
        hold_rows = ""
        for h in hold_cands:
            ticker_h  = h["ticker"]
            name_h    = h["name"]
            price_h   = h["price"]
            target30_h = h["target30"]
            # Pre-compute AMMC badge
            ammc_badge = ""
            if h.get("pdf_target_3m"):
                pt3m = h["pdf_target_3m"]
                ammc_badge = f"<span style='color:#00C87A;font-size:10px'>AMMC: {pt3m}</span>"
            hold_rows += (
                f"<div style='background:#171C2C;border-radius:8px;padding:12px;margin-bottom:8px;border-left:3px solid #8B5CF6'>"
                f"<div style='display:flex;justify-content:space-between'>"
                f"<span style='color:#8B5CF6;font-weight:900;font-family:monospace'>{ticker_h}</span>"
                f"<span style='font-size:10px;color:#9CA3AF'>{name_h}</span></div>"
                f"<div style='font-size:12px;margin-top:6px;display:flex;justify-content:space-between'>"
                f"<span style='color:#6B7280'>Entree <span style='color:#E8E4D6'>{price_h:.2f}</span></span>"
                f"<span style='color:#8B5CF6;font-weight:700'>+30%: {target30_h:.2f}</span>"
                f"{ammc_badge}</div>"
                f"</div>"
            )
        hold_html = (
            "<div style='background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.25);"
            "border-radius:10px;padding:14px;margin-bottom:14px'>"
            "<div style='font-size:10px;color:#8B5CF6;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>HOLD SEMAINE - OBJECTIF +30%</div>"
            f"{hold_rows}</div>"
        )

    # Volume alerts
    vol_html = ""
    if vol_alerts:
        vol_rows = ""
        for v in vol_alerts[:5]:
            vol_rows += (
                f"<div style='display:flex;justify-content:space-between;padding:6px 0;"
                f"border-bottom:1px solid rgba(255,255,255,0.04);font-size:12px'>"
                f"<span style='color:#FF4560;font-weight:700;font-family:monospace'>{v['ticker']}</span>"
                f"<span style='color:#6B7280'>{v['name']}</span>"
                f"<span style='color:#FF4560;font-weight:700'>x{v['ratio']}</span>"
                f"<span style='color:#9CA3AF'>RSI {v['rsi']:.0f}</span></div>"
            )
        vol_html = (
            "<div style='background:rgba(255,69,96,0.06);border:1px solid rgba(255,69,96,0.25);"
            "border-radius:10px;padding:14px;margin-bottom:14px'>"
            f"<div style='font-size:10px;color:#FF4560;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>VOLUMES ANORMAUX ({len(vol_alerts)} titres)</div>"
            f"{vol_rows}</div>"
        )

    # Pending
    pending_html = build_pending_section(pending_items)

    # News
    all_news_items = (
        [("BourseNews", n) for n in boursenews[:3]] +
        [("AMMC", n) for n in ammc_news[:2]] +
        [(s["source"], s["text"]) for s in twitter_sigs[:3]] +
        [(n["query"].split()[0], n["headline"]) for n in google_news[:3]]
    )
    news_rows = ""
    for src, n in all_news_items[:10]:
        if src == "AMMC":
            src_c = "#FF4560"
        elif src in ["FED","BAM","ECB","FMI","Reuters"]:
            src_c = "#60A5FA"
        else:
            src_c = "#9CA3AF"
        news_rows += (
            f"<div style='padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.04)'>"
            f"<span style='font-size:9px;color:{src_c};font-weight:700;letter-spacing:1px'>{src}</span>"
            f"<div style='font-size:11px;color:#9CA3AF;margin-top:2px'>{n[:160]}</div>"
            f"</div>"
        )
    news_html = (
        "<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);"
        "border-radius:10px;padding:14px;margin-bottom:14px'>"
        "<div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>FLUX MARCHE - NEWS - TWITTER</div>"
        f"{news_rows}</div>"
    )

    # PnL
    pc    = _color_change(week_pnl["total_pnl"])
    pnl_html = (
        "<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);"
        "border-radius:10px;padding:14px;margin-bottom:14px'>"
        "<div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>PNL SEMAINE</div>"
        "<div style='display:flex;justify-content:space-between;align-items:center'>"
        "<div>"
        f"<div style='font-size:26px;font-weight:900;color:{pc};font-family:monospace'>{_sign(week_pnl['total_pnl'])}{week_pnl['total_pnl']}%</div>"
        f"<div style='font-size:11px;color:#6B7280'>{week_pnl['wins']}/{week_pnl['total']} trades - Win rate {week_pnl['win_rate']}%</div>"
        "</div>"
        "<div style='text-align:right'>"
        "<div style='font-size:11px;color:#6B7280'>Ouvertes</div>"
        f"<div style='font-size:20px;font-weight:700;color:#C9A84C'>{week_pnl['open']}</div>"
        "</div></div></div>"
    )

    # MASI bar
    masi_html = (
        "<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);"
        "border-radius:10px;padding:12px;margin-bottom:14px;"
        "display:flex;justify-content:space-between;align-items:center'>"
        "<div>"
        "<span style='font-size:10px;color:#6B7280;letter-spacing:2px'>MASI</span><br>"
        f"<span style='font-size:18px;font-weight:900;color:#E8E4D6;font-family:monospace'>{masi.get('close',0):,.2f}</span>"
        f"<span style='color:{masi_c};font-weight:700;margin-left:8px'>{_sign(masi.get('change',0))}{masi.get('change',0):.2f}%</span>"
        "</div>"
        f"<div style='text-align:right;font-size:11px;color:#6B7280'>RSI <span style='color:#C9A84C'>{masi.get('rsi',50):.0f}</span><br>{masi.get('rec','')}</div>"
        "</div>"
    )

    html = (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'></head>"
        "<body style='background:#0A0D14;color:#E8E4D6;font-family:Courier New,monospace;margin:0;padding:0'>"
        "<div style='max-width:640px;margin:0 auto;padding:20px'>"
        "<div style='background:#111520;border:1px solid rgba(201,168,76,0.4);border-radius:14px;padding:20px;text-align:center;margin-bottom:16px'>"
        "<div style='font-size:26px;font-weight:900;color:#C9A84C;letter-spacing:6px'>BARAKA v5.0</div>"
        f"<div style='font-size:10px;color:#6B7280;letter-spacing:2px;margin-top:2px'>{now} - WALL STREET - {len(BVC)} SOCIETES - Precision {acc}%</div>"
        f"<div style='display:inline-block;background:rgba(0,200,122,0.1);border:1px solid rgba(0,200,122,0.3);color:{ch};padding:5px 16px;border-radius:20px;font-size:11px;letter-spacing:2px;margin-top:10px'>{window}</div>"
        "</div>"
        f"<div style='background:rgba(201,168,76,0.08);border:1px solid rgba(201,168,76,0.25);border-radius:10px;padding:12px;margin-bottom:16px;text-align:center'>"
        f"<div style='font-size:13px;color:#C9A84C;font-weight:700'>{instr}</div></div>"
        f"{masi_html}{macro_html}{bam_news_html}{synth_html}"
        "<div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px'>TOP 3 SIGNAUX - VP + NEWS + AMMC + SOCIAL</div>"
        f"{signals_html}{bear_html}{open_html}{hold_html}{vol_html}{pending_html}{news_html}{pnl_html}"
        "<div style='text-align:center;font-size:10px;color:#4B5563;margin-top:16px;line-height:1.9'>"
        "Max 3 trades/jour - T-15min - Confirmez manuellement<br>"
        "<strong style='color:#C9A84C'>+5%/jour - Hold semaine = +30% min</strong><br>"
        "TV - VP - AMMC PDF - Google News - Telegram - BAM - FRED - Groq"
        "</div></div></body></html>"
    )

    titles = {
        "matin":   "BARAKA v5 - SIGNAL MATIN - Wall Street Level BVC",
        "midi":    "BARAKA v5 - POINT MIDI - Garder / Vendre / Switcher",
        "cloture": "BARAKA v5 - CLOTURE BVC - Decision + Hold Semaine",
    }
    send_email(titles[subject_type], html)


# ═══════════════════════════════════════════════════════════
# URGENT ALERT
# ═══════════════════════════════════════════════════════════

def load_event_state():
    if os.path.exists(F["events"]):
        with open(F["events"], "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_macro": {}, "seen_hashes": [], "last_alert": "2000-01-01 00:00:00", "events_today": []}

def save_event_state(state):
    with open(F["events"], "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def get_all_news_fast():
    texts = []
    texts.extend(_scrape_boursenews())
    texts.extend(_scrape_ammc_news())
    try:
        r    = requests.get("https://www.bkam.ma/Politique-monetaire", headers=HEADERS, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        for el in soup.select("p,h2,h3")[:10]:
            t = el.get_text(strip=True)
            if len(t) > 20:
                texts.append(t[:200])
    except:
        pass
    sigs = get_twitter_signals()
    texts.extend([s["text"] for s in sigs])
    return texts

def event_check():
    print("[BARAKA EVENT] Check urgences...")
    state = load_event_state()
    now   = datetime.datetime.now()
    try:
        last_dt = datetime.datetime.strptime(state["last_alert"], "%Y-%m-%d %H:%M:%S")
        if (now - last_dt).total_seconds() < 1800:
            print("[BARAKA EVENT] Cooldown actif")
            return
    except:
        pass

    macro    = get_global_macro()
    prev     = state.get("last_macro", {})
    urgent   = []

    # VIX extreme
    vix = macro.get("vix", {}).get("price", 20)
    if vix > 35:
        urgent.append({"type":"vix_extreme_35","detail":f"VIX ATTEINT {vix:.1f} - PANIQUE","score":88,"direction":"DOWN"})

    # Commodity crash > 4%
    for key, label in [("brent","BRENT"),("gold","OR"),("copper","CUIVRE")]:
        chg = macro.get(key, {}).get("change", 0)
        if abs(chg) > 4:
            direction = "DOWN" if chg < 0 else "UP"
            urgent.append({"type":"commodity_crash_4pct","detail":f"{label} {chg:+.2f}% - MOUVEMENT EXTREME","score":90,"direction":direction})

    # Keywords critiques dans les news
    all_news = get_all_news_fast()
    for text in all_news:
        text_low = text.lower()
        for event_type, keywords in URGENCY_KEYWORDS.items():
            if any(kw in text_low for kw in keywords):
                score = compute_urgency(event_type, 1.5, keywords)
                if score >= URGENCY_LIMIT:
                    urgent.append({"type":event_type,"detail":text[:200],"score":score,"direction":"varies"})
                    break

    # Smart money
    try:
        analyses = run_full_analysis()
        sm, sectors_coordinated = detect_smart_money(analyses)
        if sm and (len(sm) >= 2 or (sm and sm[0]["vol_ratio"] >= 6)):
            tickers_sm = ", ".join([s["ticker"] for s in sm[:4]])
            sectors_sm = ", ".join(sectors_coordinated) if sectors_coordinated else "multiple"
            urgent.append({
                "type":        "smart_money",
                "detail":      f"SMART MONEY sur {tickers_sm} - Volumes x{sm[0]['vol_ratio']} - Secteurs: {sectors_sm}",
                "score":       92,
                "direction":   "UP",
                "smart_money": sm[:4],
            })
    except Exception as e:
        print(f"[SM DETECT] {e}")
        analyses = {}

    if urgent:
        rates = get_rates()
        masi  = get_masi()
        _send_urgent_alert(urgent, analyses if analyses else {}, macro, masi, rates)
        state["last_alert"]   = now.strftime("%Y-%m-%d %H:%M:%S")
        state["events_today"] = state.get("events_today", []) + [e["type"] for e in urgent]
    else:
        # Mouvements non-urgents -> pending
        for key, label in [("brent","BRENT"),("gold","OR"),("sp500","S&P500")]:
            curr_p = macro.get(key, {}).get("price", 0)
            prev_p = prev.get(key, {}).get("price", 0)
            if curr_p and prev_p and prev_p > 0:
                chg = (curr_p - prev_p) / prev_p * 100
                if abs(chg) > 2:
                    add_to_pending("commodity_move_2pct", {"asset": label, "change": round(chg, 2), "price": round(curr_p, 4)}, urgency_score=62)

    state["last_macro"] = {k: v for k, v in macro.items() if k != "_d"}
    save_event_state(state)

def _send_urgent_alert(urgent_events, analyses, macro, masi, rates):
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    prompt = (
        "Tu es Baraka, trader Wall Street BVC. ALERTE URGENTE.\n"
        f"EVENEMENTS: {json.dumps([{'type':e['type'],'detail':e['detail'][:100]} for e in urgent_events[:4]], ensure_ascii=False)}\n"
        f"MASI: {masi.get('change',0):+.2f}% - VIX: {macro.get('vix',{}).get('price',20):.1f}\n"
        f"BRENT: {macro.get('brent',{}).get('change',0):+.2f}% - REGIME: {macro.get('_d',{}).get('risk_regime','?')}\n"
        f"BAM: {rates.get('bam',3.0)}%\n\n"
        "3 phrases URGENTES pour trader BVC:\n"
        "1. Impact immediat et direct sur le BVC?\n"
        "2. Quoi faire maintenant (acheter/vendre/attendre)?\n"
        "3. Risque principal a surveiller?\n\n"
        "Style trader. Francais. PAS de markdown."
    )
    synthesis = groq_call(prompt, max_tokens=250, temp=0.15)

    events_html = ""
    for e in urgent_events[:6]:
        direction = e.get("direction", "UP")
        ec        = "#00C87A" if direction == "UP" else "#FF4560"
        ev_type   = e["type"].replace("_", " ").upper()
        events_html += (
            f"<div style='background:#171C2C;border-radius:8px;padding:12px;margin-bottom:8px;border-left:3px solid {ec}'>"
            f"<div style='font-size:10px;color:{ec};font-weight:700;letter-spacing:1px'>{ev_type} - URGENCE {e.get('score',0)}/100</div>"
            f"<div style='font-size:12px;color:#E8E4D6;margin-top:6px'>{e['detail'][:200]}</div>"
            f"</div>"
        )

    sm_html = ""
    for ev in urgent_events:
        if ev.get("smart_money"):
            sm_html += (
                "<div style='background:#111520;border:1px solid rgba(0,200,122,0.3);border-radius:10px;padding:14px;margin-bottom:14px'>"
                "<div style='font-size:10px;color:#00C87A;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>SMART MONEY DETECTE</div>"
            )
            for sm in ev["smart_money"][:4]:
                sm_html += (
                    f"<div style='display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05);font-size:12px'>"
                    f"<span style='color:#00C87A;font-weight:700;font-family:monospace'>{sm['ticker']}</span>"
                    f"<span style='color:#9CA3AF'>{sm['name']} - {sm['sector']}</span>"
                    f"<span style='color:#00C87A;font-weight:700'>x{sm['vol_ratio']} vol - RSI {sm['rsi']}</span></div>"
                )
            sm_html += "</div>"

    masi_c  = _color_change(masi.get("change", 0))
    vix_v   = macro.get("vix", {}).get("price", 20)
    regime  = macro.get("_d", {}).get("risk_regime", "?")
    rg_c    = "#00C87A" if regime == "RISK_ON" else "#FF4560" if regime == "RISK_OFF" else "#C9A84C"

    synth_html = ""
    if synthesis:
        synth_html = (
            "<div style='background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.25);"
            "border-radius:10px;padding:14px;margin-bottom:14px'>"
            "<div style='font-size:10px;color:#8B5CF6;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px'>ANALYSE BARAKA - ACTION IMMEDIATE</div>"
            f"<div style='font-size:13px;color:#E8E4D6;line-height:1.8'>{synthesis}</div>"
            "</div>"
        )

    html = (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'></head>"
        "<body style='background:#0A0D14;color:#E8E4D6;font-family:Courier New,monospace;margin:0;padding:0'>"
        "<div style='max-width:640px;margin:0 auto;padding:20px'>"
        "<div style='background:#111520;border:2px solid rgba(255,69,96,0.6);border-radius:14px;padding:20px;text-align:center;margin-bottom:16px'>"
        "<div style='font-size:26px;font-weight:900;color:#C9A84C;letter-spacing:6px'>BARAKA</div>"
        f"<div style='font-size:10px;color:#6B7280;letter-spacing:2px;margin-top:2px'>ALERTE URGENTE - {now}</div>"
        f"<div style='display:inline-block;background:rgba(255,69,96,0.15);border:1px solid rgba(255,69,96,0.5);color:#FF4560;padding:5px 16px;border-radius:20px;font-size:11px;letter-spacing:2px;margin-top:10px'>{len(urgent_events)} EVENEMENT(S) CRITIQUE(S)</div>"
        "</div>"
        "<div style='display:flex;gap:8px;margin-bottom:14px'>"
        f"<div style='flex:1;background:#171C2C;border-radius:10px;padding:12px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:4px'>MASI</div>"
        f"<div style='font-size:14px;font-weight:900;color:{masi_c}'>{_sign(masi.get('change',0))}{masi.get('change',0):.2f}%</div></div>"
        f"<div style='flex:1;background:#171C2C;border-radius:10px;padding:12px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:4px'>VIX</div>"
        f"<div style='font-size:14px;font-weight:900;color:{'#FF4560' if vix_v>25 else '#00C87A'}'>{vix_v:.1f}</div></div>"
        f"<div style='flex:1;background:#171C2C;border-radius:10px;padding:12px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:4px'>REGIME</div>"
        f"<div style='font-size:12px;font-weight:900;color:{rg_c}'>{regime}</div></div>"
        f"<div style='flex:1;background:#171C2C;border-radius:10px;padding:12px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:4px'>BAM</div>"
        f"<div style='font-size:14px;font-weight:900;color:#60A5FA'>{rates.get('bam',3.0)}%</div></div>"
        "</div>"
        "<div style='background:rgba(255,69,96,0.06);border:1px solid rgba(255,69,96,0.3);"
        "border-radius:10px;padding:14px;margin-bottom:14px'>"
        "<div style='font-size:10px;color:#FF4560;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px'>EVENEMENTS CRITIQUES</div>"
        f"{events_html}</div>"
        f"{synth_html}{sm_html}"
        "<div style='text-align:center;font-size:10px;color:#4B5563;margin-top:16px;line-height:1.9'>"
        "Alerte critique - Reaction moins de 7 minutes - Confirmez avant d'agir<br>"
        "<strong style='color:#FF4560'>BARAKA - Event-Driven - Wall Street Level</strong>"
        "</div></div></body></html>"
    )
    send_email("BARAKA - ALERTE URGENTE - Action requise", html)


# ═══════════════════════════════════════════════════════════
# NIGHT ANALYSIS & PRE-MARKET BRIEF
# ═══════════════════════════════════════════════════════════

def night_analysis():
    if datetime.datetime.now().weekday() >= 5:
        return
    print("[BARAKA] === ANALYSE NUIT 21h ===")
    macro      = get_global_macro()
    rates      = get_rates()
    derived    = macro.get("_d", {})
    boursenews = _scrape_boursenews()
    ammc_news  = _scrape_ammc_news()
    twitter    = get_twitter_signals()
    google_h   = get_google_news_general(["Bourse Casablanca 2026","OCP Maroc 2026","Maroc economie 2026","Federal Reserve 2026"])
    sp500_c = macro.get("sp500",{}).get("change",0)
    nasdaq_c = macro.get("nasdaq",{}).get("change",0)
    vix_v   = macro.get("vix",{}).get("price",20)
    brent_c = macro.get("brent",{}).get("change",0)
    gold_c  = macro.get("gold",{}).get("change",0)
    usd_mad = macro.get("usd_mad",{}).get("price",10)
    regime  = derived.get("risk_regime","?")
    ys      = derived.get("yield_spread",0)
    rec     = derived.get("recession",False)

    news_summary = (
        boursenews[:2] +
        [s["text"][:80] for s in twitter[:2]] +
        [n["headline"][:80] for n in google_h[:2]]
    )

    prompt = (
        "Tu es Baraka, trader Wall Street BVC. Il est 21h, tu prepares la strategie de demain.\n\n"
        f"CLOTURES US/EUROPE:\n"
        f"S&P500: {sp500_c:+.2f}% - Nasdaq: {nasdaq_c:+.2f}%\n"
        f"VIX: {vix_v:.1f} - Regime: {regime}\n"
        f"Brent: {brent_c:+.2f}% - Gold: {gold_c:+.2f}%\n"
        f"USD/MAD: {usd_mad:.4f}\n"
        f"Fed: {rates.get('fed',5.25)}% - ECB: {rates.get('ecb',3.5)}% - BAM: {rates.get('bam',3.0)}%\n"
        f"Yield 10Y-2Y: {ys:+.3f}% {'INVERSION RECESSION' if rec else ''}\n"
        f"NEWS: {json.dumps(news_summary, ensure_ascii=False)}\n\n"
        "Analyse en 5 phrases:\n"
        "1. Sentiment global BVC pour demain?\n"
        "2. Quels secteurs privilegier a l'ouverture et pourquoi?\n"
        "3. Quel event overnight va le plus impacter le BVC?\n"
        "4. Les 2-3 actions a surveiller demain 10h?\n"
        "5. Signal d'alarme a surveiller (si ca arrive = ne pas rentrer)?\n\n"
        "Style trader. Francais. Direct."
    )
    synthesis = groq_call(prompt, max_tokens=400, temp=0.2)

    with open(F["night"], "w") as f:
        json.dump({
            "synthesis": synthesis,
            "macro": {
                "sp500": sp500_c, "brent": brent_c,
                "vix": vix_v, "regime": regime,
            },
            "timestamp": str(datetime.datetime.now()),
        }, f, ensure_ascii=False)

    bvc_mood = "POSITIF" if regime == "RISK_ON" else "PRUDENT" if regime == "RISK_OFF" else "NEUTRE"
    mc       = "#00C87A" if bvc_mood == "POSITIF" else "#FF4560" if bvc_mood == "PRUDENT" else "#C9A84C"

    html = (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'></head>"
        "<body style='background:#0A0D14;color:#E8E4D6;font-family:Courier New,monospace;margin:0;padding:0'>"
        "<div style='max-width:640px;margin:0 auto;padding:20px'>"
        "<div style='background:#111520;border:1px solid rgba(139,92,246,0.4);border-radius:14px;padding:20px;text-align:center;margin-bottom:16px'>"
        "<div style='font-size:26px;font-weight:900;color:#C9A84C;letter-spacing:6px'>BARAKA</div>"
        f"<div style='font-size:10px;color:#6B7280;letter-spacing:2px;margin-top:2px'>ANALYSE NOCTURNE - {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</div>"
        "<div style='display:inline-block;background:rgba(139,92,246,0.12);border:1px solid rgba(139,92,246,0.35);color:#8B5CF6;padding:5px 16px;border-radius:20px;font-size:11px;margin-top:10px'>THESE POUR DEMAIN - PREPARATION SEANCE</div>"
        "</div>"
        "<div style='display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap'>"
        f"<div style='flex:1;min-width:80px;background:#171C2C;border-radius:10px;padding:12px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:4px'>S&P500</div>"
        f"<div style='font-size:14px;font-weight:900;color:{_color_change(sp500_c)}'>{_sign(sp500_c)}{sp500_c:.2f}%</div></div>"
        f"<div style='flex:1;min-width:80px;background:#171C2C;border-radius:10px;padding:12px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:4px'>VIX</div>"
        f"<div style='font-size:14px;font-weight:900;color:{'#FF4560' if vix_v>25 else '#00C87A'}'>{vix_v:.1f}</div></div>"
        f"<div style='flex:1;min-width:80px;background:#171C2C;border-radius:10px;padding:12px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:4px'>BRENT</div>"
        f"<div style='font-size:14px;font-weight:900;color:{_color_change(brent_c)}'>{_sign(brent_c)}{brent_c:.2f}%</div></div>"
        f"<div style='flex:1;min-width:80px;background:#171C2C;border-radius:10px;padding:12px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:4px'>OUTLOOK BVC</div>"
        f"<div style='font-size:13px;font-weight:900;color:{mc}'>{bvc_mood}</div></div>"
        "</div>"
        "<div style='background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.25);"
        "border-radius:10px;padding:14px;margin-bottom:14px'>"
        "<div style='font-size:10px;color:#8B5CF6;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px'>THESE BARAKA - GROQ AI</div>"
        f"<div style='font-size:13px;color:#E8E4D6;line-height:1.8'>{synthesis or 'Analyse en cours...'}</div>"
        "</div>"
        "<div style='text-align:center;font-size:10px;color:#4B5563;margin-top:16px;line-height:1.9'>"
        "Baraka analyse pendant que tu dors - Brief 8h30<br>"
        "<strong style='color:#8B5CF6'>Prochaine alerte: 8h30 pre-marche</strong>"
        "</div></div></body></html>"
    )
    send_email("BARAKA - ANALYSE NOCTURNE - These pour demain", html)
    print("[BARAKA] Analyse nuit OK")


def pre_market_brief():
    if datetime.datetime.now().weekday() >= 5:
        return
    print("[BARAKA] === BRIEF PRE-MARCHE 8h30 ===")
    night  = {}
    if os.path.exists(F["night"]):
        with open(F["night"]) as f:
            night = json.load(f)
    macro   = get_global_macro()
    rates   = get_rates()
    derived = macro.get("_d", {})
    google  = get_google_news_general(["Bourse Casablanca 2026","Bank Al-Maghrib 2026"])
    ammc    = _scrape_ammc_news()
    vix_v   = macro.get("vix",{}).get("price",20)
    sp500_c = macro.get("sp500",{}).get("change",0)
    brent_c = macro.get("brent",{}).get("change",0)
    usd_mad = macro.get("usd_mad",{}).get("price",10)
    regime  = derived.get("risk_regime","?")
    bvc_out = derived.get("bvc_outlook",{})

    prompt = (
        "Baraka, il est 8h30, le marche BVC ouvre dans 1h.\n\n"
        f"THESE HIER SOIR: {night.get('synthesis','')[:200]}\n"
        f"MACRO: VIX {vix_v:.1f} - Regime {regime} - S&P500 {sp500_c:+.2f}% - Brent {brent_c:+.2f}%\n"
        f"BAM: {rates.get('bam',3.0)}% - USD/MAD: {usd_mad:.4f}\n"
        f"NEWS AMMC: {ammc[:2]}\n"
        f"GOOGLE: {[n['headline'][:80] for n in google[:3]]}\n\n"
        "4 phrases ULTRA concretes:\n"
        "1. La these d'hier tient-elle? (oui/non + 1 raison)\n"
        "2. Les 2 actions a surveiller des l'ouverture (ticker + prix entree)\n"
        "3. Signal d'alarme absolu (si ca se passe = sortir ou ne pas entrer)\n"
        "4. Fenetre de trading du jour (10h-12h / 12h-14h / 14h-cloture)?\n\n"
        "Style trader. Francais. Direct."
    )
    synthesis = groq_call(prompt, max_tokens=300, temp=0.2)

    rc = "#00C87A" if regime == "RISK_ON" else "#FF4560" if regime == "RISK_OFF" else "#C9A84C"

    outlook_spans = ""
    for k, v in bvc_out.items():
        if v in ["POSITIF","TRES_POSITIF"]:
            oc = "0,200,122"; tc = "#00C87A"
        elif v == "NEGATIF":
            oc = "255,69,96"; tc = "#FF4560"
        else:
            oc = "201,168,76"; tc = "#C9A84C"
        outlook_spans += (
            f"<span style='font-size:10px;background:rgba({oc},0.15);color:{tc};"
            f"padding:2px 8px;border-radius:4px;margin:2px;display:inline-block'>{k}: {v}</span>"
        )

    html = (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'></head>"
        "<body style='background:#0A0D14;color:#E8E4D6;font-family:Courier New,monospace;margin:0;padding:0'>"
        "<div style='max-width:640px;margin:0 auto;padding:20px'>"
        "<div style='background:#111520;border:1px solid rgba(0,200,122,0.4);border-radius:14px;padding:20px;text-align:center;margin-bottom:16px'>"
        "<div style='font-size:26px;font-weight:900;color:#C9A84C;letter-spacing:6px'>BARAKA</div>"
        f"<div style='font-size:10px;color:#6B7280;letter-spacing:2px;margin-top:2px'>BRIEF PRE-MARCHE - {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')} - OUVERTURE DANS 1H</div>"
        "<div style='display:inline-block;background:rgba(0,200,122,0.12);border:1px solid rgba(0,200,122,0.35);color:#00C87A;padding:5px 16px;border-radius:20px;font-size:11px;margin-top:10px'>STRATEGIE D'OUVERTURE - BVC 9h30</div>"
        "</div>"
        "<div style='display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap'>"
        f"<div style='flex:1;min-width:70px;background:#171C2C;border-radius:10px;padding:10px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:3px'>REGIME</div>"
        f"<div style='font-size:12px;font-weight:900;color:{rc}'>{regime}</div></div>"
        f"<div style='flex:1;min-width:70px;background:#171C2C;border-radius:10px;padding:10px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:3px'>VIX</div>"
        f"<div style='font-size:12px;font-weight:900;color:{'#FF4560' if vix_v>25 else '#00C87A'}'>{vix_v:.1f}</div></div>"
        f"<div style='flex:1;min-width:70px;background:#171C2C;border-radius:10px;padding:10px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:3px'>S&P500</div>"
        f"<div style='font-size:12px;font-weight:900;color:{_color_change(sp500_c)}'>{_sign(sp500_c)}{sp500_c:.2f}%</div></div>"
        f"<div style='flex:1;min-width:70px;background:#171C2C;border-radius:10px;padding:10px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:3px'>BRENT</div>"
        f"<div style='font-size:12px;font-weight:900;color:{_color_change(brent_c)}'>{_sign(brent_c)}{brent_c:.2f}%</div></div>"
        f"<div style='flex:1;min-width:70px;background:#171C2C;border-radius:10px;padding:10px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:3px'>BAM</div>"
        f"<div style='font-size:12px;font-weight:900;color:#60A5FA'>{rates.get('bam',3.0)}%</div></div>"
        "</div>"
        "<div style='background:rgba(0,200,122,0.06);border:1px solid rgba(0,200,122,0.25);"
        "border-radius:10px;padding:14px;margin-bottom:14px'>"
        "<div style='font-size:10px;color:#00C87A;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px'>BRIEF BARAKA - STRATEGIE OUVERTURE</div>"
        f"<div style='font-size:13px;color:#E8E4D6;line-height:1.8'>{synthesis or 'Analyse en cours...'}</div>"
        "</div>"
        "<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:12px;margin-bottom:14px'>"
        "<div style='font-size:10px;color:#C9A84C;margin-bottom:6px'>IMPACT BVC PAR SECTEUR</div>"
        f"{outlook_spans}</div>"
        "<div style='text-align:center;font-size:10px;color:#4B5563;margin-top:16px;line-height:1.9'>"
        "Baraka surveille en continu - Alerte immediate si urgence critique<br>"
        "<strong style='color:#00C87A'>Prochain email: Signal Matin 10h00</strong>"
        "</div></div></body></html>"
    )
    send_email("BARAKA - BRIEF PRE-MARCHE 8h30 - Strategie ouverture", html)
    print("[BARAKA] Brief pre-marche OK")


# ═══════════════════════════════════════════════════════════
# POST-CLOTURE LEARNING
# ═══════════════════════════════════════════════════════════

def post_cloture_learning():
    if datetime.datetime.now().weekday() >= 5:
        return
    print("[BARAKA] === POST-CLOTURE LEARNING ===")
    learnings    = load_learnings()
    trades_today = [t for t in load_trades() if t.get("date", "") == str(datetime.date.today())]
    signals_file = f"signals_{datetime.date.today()}.json"
    signals_today = []
    if os.path.exists(signals_file):
        with open(signals_file) as f:
            signals_today = json.load(f)
    macro   = get_global_macro()
    rates   = get_rates()
    masi    = get_masi()
    derived = macro.get("_d", {})

    market_ctx = {
        "date":         str(datetime.date.today()),
        "masi_change":  masi.get("change", 0),
        "regime":       derived.get("risk_regime", "?"),
        "vix":          macro.get("vix", {}).get("price", 20),
        "brent":        macro.get("brent", {}).get("change", 0),
        "gold":         macro.get("gold", {}).get("change", 0),
        "sp500":        macro.get("sp500", {}).get("change", 0),
        "usd_mad":      macro.get("usd_mad", {}).get("price", 10),
        "bam":          rates.get("bam", 3.0),
        "fed":          rates.get("fed", 5.25),
        "yield_spread": derived.get("yield_spread", 0),
    }

    prompt = (
        "Baraka, analyse la session du jour et apprends.\n"
        f"TRADES: {json.dumps(trades_today, ensure_ascii=False)[:500]}\n"
        f"SIGNAUX: {json.dumps([{'t':s.get('ticker'),'sc':s.get('score'),'vp':s.get('vp_signal')} for s in signals_today[:3]], ensure_ascii=False)}\n"
        f"CONTEXTE: {json.dumps(market_ctx, ensure_ascii=False)}\n"
        f"POIDS ACTUELS: {json.dumps(learnings.get('indicator_weights',{}), ensure_ascii=False)}\n"
        f"LECONS PRECEDENTES: {json.dumps([l.get('lecons',[]) for l in learnings.get('lessons',[])[-3:]], ensure_ascii=False)}\n\n"
        "Reponds UNIQUEMENT en JSON:\n"
        '{"analyse_du_jour":"...","lecons_apprises":["...","...","..."],'
        '"nouveaux_poids":{"rsi":1.0,"macd":1.0,"ema":1.0,"volume":1.0,"stoch":1.0,"adx":1.0,'
        '"vp":1.0,"bam_corr":1.0,"brent_corr":1.0,"phos_corr":1.0,"macro_regime":1.0,'
        '"news_sentiment":1.0,"social_rumeur":1.0},'
        '"secteurs_favorables":["..."],"secteurs_eviter":["..."],'
        '"patterns_detectes":["..."],"score_precision_jour":75,"recommandations_demain":"..."}'
    )
    result = groq_json(prompt, max_tokens=1200)
    if result:
        learnings["lessons"].append({
            "date":      str(datetime.date.today()),
            "analyse":   result.get("analyse_du_jour", ""),
            "lecons":    result.get("lecons_apprises", []),
            "patterns":  result.get("patterns_detectes", []),
            "precision": result.get("score_precision_jour", 0),
            "demain":    result.get("recommandations_demain", ""),
        })
        if len(learnings["lessons"]) > 60:
            learnings["lessons"] = learnings["lessons"][-60:]
        for k, v in result.get("nouveaux_poids", {}).items():
            if k in learnings["indicator_weights"]:
                learnings["indicator_weights"][k] = round(learnings["indicator_weights"][k] * 0.7 + v * 0.3, 3)
        learnings["secteurs_favorables"] = result.get("secteurs_favorables", [])
        learnings["secteurs_eviter"]     = result.get("secteurs_eviter", [])
        learnings["total_analyzed"]      = learnings.get("total_analyzed", 0) + 1
        hist = learnings.get("accuracy_history", [])
        hist.append({"date": str(datetime.date.today()), "score": result.get("score_precision_jour", 0)})
        learnings["accuracy_history"] = hist[-30:]
        learnings["accuracy_rate"]    = round(sum(h["score"] for h in hist) / len(hist), 1)
        learnings["last_updated"]     = str(datetime.datetime.now())
        save_learnings(learnings)
        _send_learning_email(result, learnings)
        print(f"[BARAKA] Learning OK - Precision: {result.get('score_precision_jour',0)}%")

def _send_learning_email(result, learnings):
    acc   = learnings.get("accuracy_rate", 0)
    total = learnings.get("total_analyzed", 0)
    score = result.get("score_precision_jour", 0)
    sc    = "#00C87A" if score >= 70 else "#F59E0B" if score >= 50 else "#FF4560"

    lecons_html = ""
    for l in result.get("lecons_apprises", []):
        lecons_html += f"<div style='padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:12px;color:#9CA3AF'>- {l}</div>"

    weights_html = ""
    for k, v in learnings.get("indicator_weights", {}).items():
        bar_w = min(100, int(v * 50))
        weights_html += (
            f"<div style='display:flex;justify-content:space-between;padding:4px 0;font-size:12px'>"
            f"<span style='color:#6B7280'>{k.upper()}</span>"
            f"<div style='flex:1;margin:0 10px;background:#0A0D14;border-radius:2px;height:6px;margin-top:7px'>"
            f"<div style='height:100%;background:#C9A84C;border-radius:2px;width:{bar_w}%'></div></div>"
            f"<span style='color:#C9A84C;font-weight:700'>{v:.2f}</span>"
            f"</div>"
        )

    sg = ", ".join(learnings.get("secteurs_favorables", [])[:4]) or "Aucun"
    se = ", ".join(learnings.get("secteurs_eviter", [])[:4])     or "Aucun"

    html = (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'></head>"
        "<body style='background:#0A0D14;color:#E8E4D6;font-family:Courier New,monospace;margin:0;padding:0'>"
        "<div style='max-width:620px;margin:0 auto;padding:20px'>"
        "<div style='background:#111520;border:1px solid rgba(139,92,246,0.4);border-radius:14px;padding:20px;text-align:center;margin-bottom:16px'>"
        "<div style='font-size:26px;font-weight:900;color:#C9A84C;letter-spacing:6px'>BARAKA</div>"
        f"<div style='font-size:10px;color:#6B7280;margin-top:2px'>POST-CLOTURE - APPRENTISSAGE #{total} - {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</div>"
        f"<div style='display:inline-block;background:rgba(139,92,246,0.12);border:1px solid rgba(139,92,246,0.35);color:#8B5CF6;padding:5px 16px;border-radius:20px;font-size:11px;margin-top:10px'>SESSION #{total}</div>"
        "</div>"
        "<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:16px;margin-bottom:14px'>"
        "<div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px'>ANALYSE DU JOUR</div>"
        f"<div style='font-size:13px;color:#E8E4D6;line-height:1.7'>{result.get('analyse_du_jour','')}</div>"
        f"<div style='margin-top:10px;font-size:11px;color:#6B7280;font-style:italic'>Demain: {result.get('recommandations_demain','')}</div>"
        "</div>"
        "<div style='display:flex;gap:10px;margin-bottom:14px'>"
        f"<div style='flex:1;background:#171C2C;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:12px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:4px'>PRECISION JOUR</div>"
        f"<div style='font-size:22px;font-weight:900;color:{sc};font-family:monospace'>{score}%</div></div>"
        f"<div style='flex:1;background:#171C2C;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:12px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:4px'>MOY. 30J</div>"
        f"<div style='font-size:22px;font-weight:900;color:#C9A84C;font-family:monospace'>{acc}%</div></div>"
        f"<div style='flex:1;background:#171C2C;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:12px;text-align:center'>"
        f"<div style='font-size:9px;color:#6B7280;margin-bottom:4px'>SESSIONS</div>"
        f"<div style='font-size:22px;font-weight:900;color:#8B5CF6;font-family:monospace'>{total}</div></div>"
        "</div>"
        "<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:16px;margin-bottom:14px'>"
        "<div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px'>LECONS APPRISES</div>"
        f"{lecons_html}</div>"
        "<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:16px;margin-bottom:14px'>"
        "<div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px'>POIDS ADAPTATIFS</div>"
        f"{weights_html}</div>"
        "<div style='background:#111520;border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px;margin-bottom:14px'>"
        "<div style='font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px'>SECTEURS</div>"
        "<div style='display:flex;justify-content:space-between;font-size:12px'>"
        f"<div><div style='color:#00C87A;margin-bottom:4px'>FAVORABLES</div><div style='color:#9CA3AF'>{sg}</div></div>"
        f"<div style='text-align:right'><div style='color:#FF4560;margin-bottom:4px'>A EVITER</div><div style='color:#9CA3AF'>{se}</div></div>"
        "</div></div>"
        "<div style='text-align:center;font-size:10px;color:#4B5563;margin-top:16px;line-height:1.9'>"
        "Baraka apprend de chaque session - Groq llama3-70b - 100% Gratuit<br>"
        f"<strong style='color:#8B5CF6'>Session #{total} - Precision cumulee {acc}%</strong>"
        "</div></div></body></html>"
    )
    send_email(f"BARAKA v5 - POST-CLOTURE - Learning #{total}", html)

# ═══════════════════════════════════════════════════════════
# VOLUME MONITORING
# ═══════════════════════════════════════════════════════════

def monitor_volumes():
    now = datetime.datetime.now()
    if now.weekday() >= 5:
        return
    if not (9 <= now.hour < 16):
        return
    print("[BARAKA] Surveillance volumes...")
    analyses = run_full_analysis()
    alerts   = check_volume_alerts(analyses)
    for a in alerts:
        if a["ratio"] < 5:
            add_to_pending(
                "volume_2x",
                {"ticker": a["ticker"], "ratio": a["ratio"], "price": a["price"]},
                urgency_score=55,
                ticker=a["ticker"]
            )

# ═══════════════════════════════════════════════════════════
# SCHEDULER 24H/24
# ═══════════════════════════════════════════════════════════

def run_scheduler():
    print("""
+============================================================+
|    BARAKA v5.0 - WALL STREET LEVEL - 24h/24 - 7j/7        |
|  Smart Filter - PDF AMMC - Google News - Telegram          |
+============================================================+
|  /7min     -> Event check URGENCES uniquement              |
|  /15min    -> Surveillance volumes (heures marche)         |
|  02h00     -> Analyse PDFs AMMC (background)               |
|  03h00     -> Scan reseaux sociaux Telegram/Facebook       |
|  06h00     -> Scan Google News par societe                 |
|  08h30     -> Brief pre-marche                             |
|  10h00     -> Signal Matin (tout integre)                  |
|  12h00     -> Point Midi                                   |
|  15h15     -> Cloture + Hold semaine +30%                  |
|  16h30     -> Post-Cloture Apprentissage Groq              |
|  20h00     -> Scan Google News par societe (soir)          |
|  21h00     -> Analyse Nocturne + These demain              |
|  22h00     -> Scan reseaux sociaux (soir)                  |
+============================================================+
    """)

    days = [
        schedule.every().monday,
        schedule.every().tuesday,
        schedule.every().wednesday,
        schedule.every().thursday,
        schedule.every().friday,
    ]
    for d in days:
        d.at("08:30").do(pre_market_brief)
        d.at("10:00").do(run_alert, "matin")
        d.at("12:00").do(run_alert, "midi")
        d.at("15:15").do(run_alert, "cloture")
        d.at("16:30").do(post_cloture_learning)
        d.at("21:00").do(night_analysis)

    # Background workers 7j/7
    schedule.every().day.at("02:00").do(run_pdf_analysis_background)
    schedule.every().day.at("03:00").do(run_social_media_scan)
    schedule.every().day.at("06:00").do(run_company_news_scan)
    schedule.every().day.at("20:00").do(run_company_news_scan)
    schedule.every().day.at("22:00").do(run_social_media_scan)

    # Event monitoring urgences 7j/7 24h/24
    schedule.every(7).minutes.do(event_check)

    # Surveillance volumes heures marche
    schedule.every(15).minutes.do(monitor_volumes)

    print("[BARAKA] Actif 24h/24 - Smart Filter active - Baraka anticipe le marche...")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    run_scheduler()
