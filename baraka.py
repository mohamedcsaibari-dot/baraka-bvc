"""
BARAKA v7.2 - BVC Trading Intelligence - Hedge Fund Level
Modules intégrés: fundamentals.py (élasticité SMI/MNG) + alerts.py (alertes ±1% XAG/XAU)
"""

import os, time, datetime, threading, json, re, requests, io
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Modules élasticité + alertes mines (v7.3) ──────────────────────────────
from fundamentals import (smi_fair_value, mng_fair_value, cmt_fair_value,
                           smi_local_beta, smi_elasticity,
                           mng_elasticity, mng_copper_delta,
                           cmt_local_beta_ag, cmt_elasticity,
                           valuation_signal)
from alerts import set_daily_reference, check_alerts, THRESHOLD_PCT

RESEND_KEY = os.environ.get("RESEND_API_KEY","")
GROQ_KEY   = os.environ.get("GROQ_API_KEY","")
TO_EMAIL   = os.environ.get("TO_EMAIL","mohamed.csaibari@gmail.com")
FROM_EMAIL = "Baraka BVC <onboarding@resend.dev>"
HDR = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
R   = {"verify":False,"timeout":8}

_CACHE     = {}
_WATCHLIST = {}
_MKT_PREV  = {}
_NEWS_SEEN = set()
_FUNDAMENTALS = {}

def cache_set(k,v): _CACHE[k]={"d":v,"t":datetime.datetime.utcnow()}
def cache_get(k,max_min=180):
    if k not in _CACHE: return None
    age=(datetime.datetime.utcnow()-_CACHE[k]["t"]).total_seconds()/60
    return _CACHE[k]["d"] if age<max_min else None

def watchlist_add(t,entry,stop,target,side="BUY"):
    _WATCHLIST[t]={"entry":entry,"stop":stop,"target":target,"side":side,"fired":[],"name":BVC.get(t,{}).get("n",t)}
def watchlist_clear(): _WATCHLIST.clear()

import hashlib
def dedup_news(items, reset_daily=False):
    global _NEWS_SEEN
    if reset_daily: _NEWS_SEEN = set()
    fresh = []
    for item in items:
        h = hashlib.md5(item[:80].lower().encode()).hexdigest()
        if h not in _NEWS_SEEN:
            _NEWS_SEEN.add(h); fresh.append(item)
    return fresh

def scrape_rss(url, limit=5):
    try:
        r = requests.get(url, headers=HDR, **R)
        titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", r.text)
        items = []
        for t1, t2 in titles[1:limit+3]:
            t = (t1 or t2).strip()
            clean = re.sub(r"<[^>]+>","",t).strip()
            if len(clean)>15: items.append(clean[:200])
        return dedup_news(items[:limit])
    except: return []

# ─── UNIVERS BVC ──────────────────────────────────────────────────────────────
BVC = {
    "ATW":{"n":"Attijariwafa Bank","s":"Banque","v":85000,"mc":"large"},
    "BCP":{"n":"Banque Centrale Pop.","s":"Banque","v":60000,"mc":"large"},
    "BMCE":{"n":"Bank of Africa","s":"Banque","v":70000,"mc":"large"},
    "CIH":{"n":"CIH Bank","s":"Banque","v":45000,"mc":"mid"},
    "CDM":{"n":"Credit du Maroc","s":"Banque","v":18000,"mc":"mid"},
    "BMCI":{"n":"BMCI","s":"Banque","v":12000,"mc":"mid"},
    "CFG":{"n":"CFG Bank","s":"Banque","v":8000,"mc":"small"},
    "WAA":{"n":"Wafa Assurance","s":"Assurance","v":6000,"mc":"mid"},
    "ATL":{"n":"Atlanta","s":"Assurance","v":5000,"mc":"small"},
    "SAH":{"n":"Saham Assurance","s":"Assurance","v":4000,"mc":"small"},
    "IAM":{"n":"Maroc Telecom","s":"Telecom","v":120000,"mc":"large"},
    "HPS":{"n":"HPS","s":"Tech","v":15000,"mc":"mid"},
    "OCP":{"n":"OCP Group","s":"Chimie","v":95000,"mc":"large"},
    "MANAGEM":{"n":"Managem","s":"Mines","v":12000,"mc":"mid"},
    "SMI":{"n":"SMI (Argent)","s":"Mines","v":8000,"mc":"small"},
    "CMT":{"n":"CMT (Zinc/Plomb)","s":"Mines","v":5000,"mc":"small"},
    "ADH":{"n":"Addoha","s":"Immobilier","v":35000,"mc":"mid"},
    "ALM":{"n":"Alliances","s":"Immobilier","v":15000,"mc":"mid"},
    "DAR":{"n":"Res. Dar Saada","s":"Immobilier","v":4000,"mc":"small"},
    "TGCC":{"n":"TGCC","s":"Construction","v":5000,"mc":"mid"},
    "SGTM":{"n":"SGTM","s":"Construction","v":3000,"mc":"small"},
    "HOL":{"n":"Holcim Maroc","s":"Construction","v":12000,"mc":"mid"},
    "CMA":{"n":"Ciments du Maroc","s":"Construction","v":10000,"mc":"mid"},
    "LHM":{"n":"LafargeHolcim","s":"Construction","v":9000,"mc":"mid"},
    "AKDITAL":{"n":"Akdital","s":"Sante","v":4500,"mc":"mid"},
    "LABEL":{"n":"Label Vie","s":"Distribution","v":9000,"mc":"mid"},
    "LAC":{"n":"Lesieur Cristal","s":"Agro","v":11000,"mc":"mid"},
    "COSUMAR":{"n":"Cosumar","s":"Agro","v":8000,"mc":"mid"},
    "TMA":{"n":"Total Maroc","s":"Energie","v":7000,"mc":"mid"},
    "TAQA":{"n":"Taqa Morocco","s":"Energie","v":8000,"mc":"mid"},
    "SRM":{"n":"Sonasid","s":"Siderurgie","v":6000,"mc":"mid"},
    "CTM":{"n":"CTM","s":"Transport","v":5000,"mc":"small"},
    "SOTHEMA":{"n":"Sothema","s":"Pharma","v":6000,"mc":"mid"},
    "RIS":{"n":"Risma","s":"Tourisme","v":5000,"mc":"small"},
    "EQDOM":{"n":"Eqdom","s":"Credit Conso","v":4000,"mc":"small"},
}
VIP = ["ADH","ALM","TGCC","SGTM","DAR","AKDITAL","MANAGEM","SMI","CMT"]

BVC_DAILY_CAP = 10.0
def cap_move(pct): return max(-BVC_DAILY_CAP, min(BVC_DAILY_CAP, pct))
def cap_price(close, target_pct): return round(close * (1 + cap_move(target_pct)/100), 2)
def at_limit(chg): return abs(chg) >= 9.5

MINING_BETAS = {
    "SMI":     {"silver":1.85,"gold":0.35,"dxy":-0.85,"lead_driver":"silver","lead_min":20},
    "MANAGEM": {"gold":1.05,"copper":0.55,"silver":0.45,"dxy":-0.70,"lead_driver":"gold","lead_min":30},
    "CMT":     {"copper":0.70,"silver":0.35,"gold":0.30,"dxy":-0.50,"lead_driver":"copper","lead_min":30},
}

def mining_fair_value(ticker, d, macro):
    betas = MINING_BETAS.get(ticker)
    if not betas or not d or not d.get("close"): return None
    drivers = {
        "silver": macro.get("silver",{}).get("c",0),
        "gold":   macro.get("gold",{}).get("c",0),
        "copper": macro.get("copper",{}).get("c",0),
        "dxy":    macro.get("dxy",{}).get("c",0),
    }
    contributions = {}; implied = 0.0
    for k, beta in betas.items():
        if k in drivers:
            contrib = beta * drivers[k]; contributions[k] = round(contrib,2); implied += contrib
    implied = cap_move(round(implied,2))
    actual = d.get("change",0); gap = round(implied - actual,2)
    dominant = max(contributions.items(), key=lambda x:abs(x[1])) if contributions else ("",0)
    lead_driver = betas.get("lead_driver","silver"); lead_move = drivers.get(lead_driver,0)
    lead_min = betas.get("lead_min",20); lag_signal = ""
    if abs(lead_move) > 0.8 and abs(actual) < abs(lead_move)*0.4:
        direction = "haussier" if lead_move > 0 else "baissier"
        lag_signal = f"{lead_driver.upper()} {lead_move:+.1f}% mais {ticker} encore a {actual:+.1f}% — fenetre {lead_min}min, rattrapage {direction} probable"
    if gap > 1.5:   verdict, signal = "SOUS-EVALUE vs drivers — potentiel rattrapage HAUSSIER", "ACHAT"
    elif gap < -1.5: verdict, signal = "DECROCHE de ses drivers (sur-reaction) — prudence/prise profit", "PRUDENCE"
    else:            verdict, signal = "aligne avec ses drivers — pas d'ecart exploitable", "NEUTRE"
    return {"ticker":ticker,"implied":implied,"actual":actual,"gap":gap,
            "contributions":contributions,"dominant":dominant,"drivers":drivers,
            "verdict":verdict,"signal":signal,"lag_signal":lag_signal,"lead_driver":lead_driver}

def mining_intelligence(bvc_data, macro):
    out = []
    for t in ["SMI","MANAGEM","CMT"]:
        d = bvc_data.get(t)
        if not d: continue
        fv = mining_fair_value(t, d, macro)
        if fv: out.append(fv)
    return out

SECTOR_BETAS = {
    "Banque":      {"us10y":0.45,"yield_spread":0.60,"cac40":0.55,"vix":-0.30,"_logic":"Taux+ -> NIM+ ; spread+ -> rentabilite+"},
    "Assurance":   {"us10y":0.50,"yield_spread":0.35,"cac40":0.40,"vix":-0.25,"_logic":"Taux+ -> rendement placements+"},
    "Immobilier":  {"us10y":-0.85,"yield_spread":-0.50,"cac40":0.35,"brent":-0.20,"_logic":"Taux+ -> credit immo cher"},
    "Construction":{"brent":-0.55,"us10y":-0.45,"cac40":0.40,"copper":0.25,"_logic":"Brent+ -> cout ciment+"},
    "Telecom":     {"vix":0.25,"cac40":0.30,"us10y":-0.20,"_logic":"Defensif -> surperforme en risk-off"},
    "Chimie":      {"dxy":0.45,"brent":-0.30,"cac40":0.40,"copper":0.30,"_logic":"USD fort -> export phosphate+"},
    "Mines":       {"gold":0.90,"silver":0.70,"copper":0.45,"dxy":-0.70,"_logic":"Metaux precieux+ -> valorisation+"},
    "Energie":     {"brent":0.35,"cac40":0.30,"usd_mad":-0.25,"_logic":"Brent+ -> CA+ mais marge compressee"},
    "Transport":   {"brent":-0.70,"cac40":0.35,"dxy":-0.20,"_logic":"Brent+ -> carburant+ -> marge-"},
    "Agro":        {"usd_mad":-0.50,"brent":-0.35,"cac40":0.25,"_logic":"MAD faible -> intrants importes chers"},
    "Distribution":{"brent":-0.40,"usd_mad":-0.40,"vix":-0.20,"cac40":0.30,"_logic":"Inflation/brent+ -> pouvoir achat-"},
    "Sante":       {"vix":0.20,"cac40":0.35,"us10y":-0.25,"_logic":"Defensif + croissance structurelle"},
    "Pharma":      {"usd_mad":-0.35,"vix":0.15,"cac40":0.25,"_logic":"Defensif ; intrants importes"},
    "Siderurgie":  {"copper":0.50,"brent":-0.40,"cac40":0.45,"dxy":-0.25,"_logic":"Metaux industriels+"},
    "Tourisme":    {"brent":-0.45,"cac40":0.40,"vix":-0.35,"eur_mad":0.30,"_logic":"Brent+ -> cout voyage-"},
    "Credit Conso":{"us10y":0.30,"yield_spread":0.40,"vix":-0.30,"_logic":"Taux+ -> marge+ mais defaut+"},
    "Tech":        {"sp500":0.50,"cac40":0.40,"vix":-0.30,"_logic":"Correle tech mondiale"},
}

GEO_EVENTS = {
    "ormuz":       {"keywords":["ormuz","hormuz","detroit","strait","blocus petrolier"],
                    "chain":"Fermeture Ormuz -> Brent +15-30% -> inflation importee Maroc -> BAM hawkish","winners":["MANAGEM","SMI"],"losers":["ADH","ALM","DAR","TGCC","CTM"]},
    "iran_escalade":{"keywords":["iran","israel","frappe","missile","guerre","attaque"],
                    "chain":"Escalade -> prime risque petrole + or refuge -> MAIS si DXY monte, metaux peuvent CHUTER (paradoxe deleveraging)","winners":["MANAGEM","SMI"],"losers":[]},
    "fed_hike":    {"keywords":["fed hausse","rate hike","powell hawkish","taux directeur hausse","resserrement"],
                    "chain":"Hausse taux Fed -> DXY+ -> pression MAD -> POSITIF banques, NEGATIF immobilier + mines","winners":["ATW","BCP","BMCE","CIH"],"losers":["ADH","ALM","DAR","MANAGEM","SMI"]},
    "fed_cut":     {"keywords":["fed baisse","rate cut","powell dovish","assouplissement","baisse taux"],
                    "chain":"Baisse taux Fed -> DXY- -> metaux+ -> POSITIF mines + immobilier","winners":["MANAGEM","SMI","ADH","ALM"],"losers":[]},
    "douane_taxe": {"keywords":["douane","tarif","taxe import","droits douane","barriere"],
                    "chain":"Hausse droits douane -> cout intrants importes+ -> NEGATIF agro/distribution","winners":["SRM","LHM","CMA","HOL"],"losers":["LABEL","LAC","COSUMAR"]},
}

def detect_geo_event(geo_news):
    if not geo_news: return None
    blob = " ".join(geo_news).lower() if isinstance(geo_news, list) else str(geo_news).lower()
    for event_id, ev in GEO_EVENTS.items():
        if any(kw in blob for kw in ev["keywords"]): return {"id":event_id, **ev}
    return None

def _delta(curr, prev):
    try: return round((curr - prev)*100, 2)
    except: return 0

def _pct_dev(val, base):
    try: return round((val-base)/base*100, 2)
    except: return 0

def sector_transmission(ticker, d, macro):
    info = BVC.get(ticker,{}); sect = info.get("s","")
    if not d or not d.get("close"): return None
    if sect == "Mines" and ticker in MINING_BETAS:
        fv = mining_fair_value(ticker, d, macro)
        if fv: fv["sector"] = sect
        return fv
    betas = SECTOR_BETAS.get(sect)
    if not betas: return None
    drivers = {
        "brent":macro.get("brent",{}).get("c",0),"gold":macro.get("gold",{}).get("c",0),
        "silver":macro.get("silver",{}).get("c",0),"copper":macro.get("copper",{}).get("c",0),
        "dxy":macro.get("dxy",{}).get("c",0),"vix":macro.get("vix",{}).get("c",0),
        "cac40":macro.get("cac40",{}).get("c",0),"sp500":macro.get("sp500",{}).get("c",0),
        "us10y":max(-5,min(5,macro.get("us10y_chg",0))),
        "yield_spread":max(-2,min(2,macro.get("yield_spread",0))),
        "usd_mad":_pct_dev(macro.get("usd_mad",10.0),10.0),
        "eur_mad":_pct_dev(macro.get("eur_mad",10.9),10.9),
    }
    contributions = {}; implied = 0.0
    for k, beta in betas.items():
        if k.startswith("_"): continue
        if k in drivers:
            c = beta * drivers[k]; contributions[k] = round(c,2); implied += c
    implied = cap_move(round(implied,2)); actual = d.get("change",0); gap = round(implied - actual,2)
    dominant = max(contributions.items(), key=lambda x:abs(x[1])) if contributions else ("",0)
    fond_notes = []
    if _FUNDAMENTALS:
        ov = fundamental_overlay(sect, _FUNDAMENTALS)
        if ov["bias"] != 0:
            implied = cap_move(round(implied + ov["bias"]*2, 2)); gap = round(implied - actual,2)
            fond_notes = ov["notes"]
    if gap > 1.5:    verdict, signal = "Sous-reagit a sa macro sectorielle — rattrapage possible", "ACHAT"
    elif gap < -1.5: verdict, signal = "Decroche de sa macro (sur-reaction) — prudence", "PRUDENCE"
    else:            verdict, signal = "Aligne avec sa macro sectorielle", "NEUTRE"
    return {"ticker":ticker,"sector":sect,"implied":implied,"actual":actual,"gap":gap,
            "contributions":contributions,"dominant":dominant,"verdict":verdict,"signal":signal,
            "logic":betas.get("_logic",""),"fond_notes":fond_notes}

def bvc_transmission_scan(bvc_data, macro):
    signals = []
    for t, d in bvc_data.items():
        st = sector_transmission(t, d, macro)
        if st and abs(st["gap"]) >= 1.0: signals.append(st)
    return sorted(signals, key=lambda x:-abs(x["gap"]))

# ════════ MODULE FONDAMENTAUX HCP/PPI/BAM ════════════════════════════════════
def _extract_pct(text):
    m = re.search(r"([+-]?\d+[.,]?\d*)\s*%", text)
    if m:
        try: return float(m.group(1).replace(",","."))
        except: return None
    return None

def get_fundamentals():
    cached = cache_get("fundamentals", max_min=720)
    if cached: return cached
    f = {"ipc":None,"ipc_news":[],"ppi":{},"ppi_news":[],"bam_rate":None,"bam_proj":None,"bam_news":[],"ts":datetime.datetime.now().strftime("%d/%m/%Y")}
    ipc_news = gnews("HCP Maroc IPC inflation indice prix consommation 2026", 4)
    f["ipc_news"] = ipc_news
    for n in ipc_news:
        v = _extract_pct(n)
        if v is not None and 0 < v < 20: f["ipc"] = v; break
    ppi_news = gnews("Maroc indice prix production industrielle PPI secteur 2026", 4)
    f["ppi_news"] = ppi_news
    for n in ppi_news:
        nl = n.lower(); v = _extract_pct(n)
        if v is None: continue
        if any(w in nl for w in ["ciment","construction","materiaux"]): f["ppi"]["Construction"] = v
        if any(w in nl for w in ["chimi","phosphate","engrais"]): f["ppi"]["Chimie"] = v
        if any(w in nl for w in ["aliment","agro"]): f["ppi"]["Agro"] = v
        if any(w in nl for w in ["energie","petrol","carburant"]): f["ppi"]["Energie"] = v
        if any(w in nl for w in ["metal","siderur","acier"]): f["ppi"]["Siderurgie"] = v
    bam_news = gnews("Bank Al Maghrib BAM taux directeur decision projection inflation 2026", 4)
    f["bam_news"] = bam_news
    for n in bam_news:
        nl = n.lower(); v = _extract_pct(n)
        if v is None: continue
        if "taux directeur" in nl and 0 < v < 10: f["bam_rate"] = v
        if "inflation" in nl and 0 < v < 15: f["bam_proj"] = v
    cache_set("fundamentals", f)
    print(f"[FOND] IPC={f['ipc']} BAM={f['bam_rate']} PPI={list(f['ppi'].keys())}")
    return f

def fundamental_overlay(sector, fundamentals):
    bias = 0.0; notes = []; ppi = fundamentals.get("ppi",{}); ipc = fundamentals.get("ipc"); bam_proj = fundamentals.get("bam_proj")
    if sector in ppi:
        p = ppi[sector]
        if p > 2: bias -= 0.4; notes.append(f"PPI {sector} +{p}% -> pression couts/marges")
        elif p < -1: bias += 0.3; notes.append(f"PPI {sector} {p}% -> detente couts")
    if ipc and ipc > 3:
        if sector in ["Immobilier","Construction","Credit Conso"]: bias -= 0.3; notes.append(f"Inflation {ipc}% -> risque hausse taux")
        elif sector in ["Banque","Assurance"]: bias += 0.3; notes.append(f"Inflation {ipc}% -> marge {sector}+")
    if bam_proj and bam_proj > 3 and sector == "Banque": bias += 0.2; notes.append(f"Projection inflation BAM {bam_proj}%")
    return {"bias":round(bias,2),"notes":notes}

# ════════ SCORECARD / BACKTEST FORWARD ═══════════════════════════════════════
SCORECARD_PATH = os.environ.get("SCORECARD_PATH","/data/baraka_scorecard.json")

def _scorecard_load():
    try:
        if os.path.exists(SCORECARD_PATH):
            with open(SCORECARD_PATH) as f: return json.load(f)
    except: pass
    return {"open":[],"closed":[]}

def _scorecard_save(sc):
    try:
        os.makedirs(os.path.dirname(SCORECARD_PATH), exist_ok=True)
        with open(SCORECARD_PATH,"w") as f: json.dump(sc, f)
        return True
    except:
        try:
            alt = "/home/claude/baraka_scorecard.json"
            with open(alt,"w") as f: json.dump(sc, f)
            return True
        except: return False

def log_recos(recs):
    if not recs: return
    sc = _scorecard_load(); today = str(datetime.date.today())
    for r in recs:
        sc["open"].append({"date":today,"ticker":r["t"],"side":"BUY" if r["is_buy"] else "SELL",
                           "entry":r["close"],"target":r["target"],"stop":r["stop"],"tf":r["timeframe"],"score":r["sc"]})
    sc["open"] = sc["open"][-200:]; _scorecard_save(sc)
    print(f"[SCORECARD] {len(recs)} recos loggees")

def update_scorecard(bvc_data):
    sc = _scorecard_load(); still_open = []; horizons = {"day":1,"week":7,"quarter":90}
    today = datetime.date.today()
    for rec in sc.get("open",[]):
        d = bvc_data.get(rec["ticker"])
        if not d: still_open.append(rec); continue
        close = d.get("close",0)
        if not close: still_open.append(rec); continue
        try: rec_date = datetime.date.fromisoformat(rec["date"]); age = (today - rec_date).days
        except: age = 0
        is_buy = rec["side"]=="BUY"
        hit_target = (close >= rec["target"]) if is_buy else (close <= rec["target"])
        hit_stop   = (close <= rec["stop"])   if is_buy else (close >= rec["stop"])
        horizon = horizons.get(rec["tf"],7)
        if hit_target:
            rec["outcome"]="WIN"; rec["exit"]=close; rec["pnl"]=round((close-rec["entry"])/rec["entry"]*100*(1 if is_buy else -1),2); sc["closed"].append(rec)
        elif hit_stop:
            rec["outcome"]="LOSS"; rec["exit"]=close; rec["pnl"]=round((close-rec["entry"])/rec["entry"]*100*(1 if is_buy else -1),2); sc["closed"].append(rec)
        elif age > horizon:
            rec["outcome"]="EXPIRED"; rec["exit"]=close; rec["pnl"]=round((close-rec["entry"])/rec["entry"]*100*(1 if is_buy else -1),2); sc["closed"].append(rec)
        else: still_open.append(rec)
    sc["open"] = still_open; sc["closed"] = sc["closed"][-500:]
    _scorecard_save(sc); return sc

def scorecard_stats(sc=None):
    if sc is None: sc = _scorecard_load()
    closed = sc.get("closed",[])
    if not closed: return {"total":0,"wins":0,"hit_rate":0,"avg_pnl":0,"by_tf":{},"open":len(sc.get("open",[]))}
    wins = [c for c in closed if c.get("outcome")=="WIN"]; losses = [c for c in closed if c.get("outcome")=="LOSS"]
    decisive = len(wins)+len(losses)
    hit_rate = round(len(wins)/decisive*100,1) if decisive>0 else 0
    avg_pnl = round(sum(c.get("pnl",0) for c in closed)/len(closed),2)
    by_tf = {}
    for tf in ["day","week","quarter"]:
        tf_closed = [c for c in closed if c.get("tf")==tf]; tf_dec = [c for c in tf_closed if c.get("outcome") in ("WIN","LOSS")]; tf_wins = [c for c in tf_closed if c.get("outcome")=="WIN"]
        if tf_dec: by_tf[tf] = {"hit":round(len(tf_wins)/len(tf_dec)*100,1),"n":len(tf_dec)}
    return {"total":len(closed),"wins":len(wins),"losses":len(losses),"hit_rate":hit_rate,"avg_pnl":avg_pnl,"by_tf":by_tf,"open":len(sc.get("open",[]))}

# ─── CSS ──────────────────────────────────────────────────────────────────────
CSS = """<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#080C14;color:#E8E4D6;font-family:'Courier New',monospace}
.w{max-width:660px;margin:0 auto;padding:14px}
.hdr{background:linear-gradient(135deg,#0F1520,#1A2030);border:1px solid rgba(201,168,76,.5);border-radius:12px;padding:18px;text-align:center;margin-bottom:12px}
.logo{font-size:26px;font-weight:900;color:#C9A84C;letter-spacing:8px}
.sub{font-size:10px;color:#6B7280;letter-spacing:3px;margin-top:3px}
.bdg{display:inline-block;border:1px solid;padding:4px 14px;border-radius:20px;font-size:11px;margin-top:7px}
.sec{background:#0F1520;border:1px solid rgba(201,168,76,.15);border-radius:10px;padding:13px;margin-bottom:10px}
.st{font-size:9px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:9px;border-bottom:1px solid rgba(201,168,76,.15);padding-bottom:5px}
.mg{display:flex;gap:6px;flex-wrap:wrap}
.mb{flex:1;min-width:70px;background:#13192A;border-radius:7px;padding:8px;text-align:center}
.ml{font-size:8px;color:#6B7280;margin-bottom:2px}
.mv{font-size:13px;font-weight:900}
.g{color:#00C87A}.r{color:#FF4560}.go{color:#C9A84C}.b{color:#60A5FA}.pu{color:#8B5CF6}.or{color:#F59E0B}
.ni{padding:5px 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:11px;color:#9CA3AF;line-height:1.6}
.src{font-size:8px;font-weight:700;padding:1px 5px;border-radius:3px;margin-right:5px}
.card{background:#13192A;border-radius:10px;padding:13px;margin-bottom:10px}
.geo{background:rgba(239,68,68,.06);border:1px solid rgba(239,68,68,.2);border-radius:10px;padding:13px;margin-bottom:10px}
.geot{font-size:9px;color:#EF4444;letter-spacing:3px;text-transform:uppercase;margin-bottom:7px}
.imp{background:rgba(239,68,68,.12);border-left:3px solid #EF4444;border-radius:4px;padding:8px;margin-bottom:5px}
.lv{background:rgba(0,200,122,.06);border:1px solid rgba(0,200,122,.2);border-radius:8px;padding:11px;margin:7px 0}
.lr{display:flex;justify-content:space-between;padding:3px 0;font-size:12px}
.sy{background:rgba(139,92,246,.06);border:1px solid rgba(139,92,246,.25);border-radius:10px;padding:13px;margin-bottom:10px}
.syt{font-size:9px;color:#8B5CF6;letter-spacing:3px;text-transform:uppercase;margin-bottom:7px}
.sytx{font-size:12px;line-height:1.8}
.sb{background:#080C14;border-radius:3px;height:4px;margin-top:3px}
.sf{height:100%;border-radius:3px;background:linear-gradient(90deg,#C9A84C,#F59E0B)}
.ft{text-align:center;font-size:10px;color:#4B5563;margin-top:12px;line-height:2}
.exc{background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.25);border-radius:8px;padding:10px;margin-bottom:7px}
.vip{background:rgba(245,158,11,.05);border:1px solid rgba(245,158,11,.2);border-radius:8px;padding:10px;margin-bottom:7px}
</style>"""

def cv(v): return "g" if v>=0 else "r"
def pv(v): return f"+{v:.2f}%" if v>=0 else f"{v:.2f}%"
def sg(v): return "+" if v>=0 else ""
def cv_hex(v): return "#00C87A" if v>=0 else "#FF4560"

def ammc_badge(ptype):
    badges = {"warning":("#FF4560","🚨 WARNING"),"resultats":("#60A5FA","📊 RESULTATS"),"dividende":("#00C87A","💰 DIVIDENDE"),"operation":("#F59E0B","🏦 OPERATION")}
    return badges.get(ptype, ("#EF4444",""))

# ═══════════════════════════════════════════════════════════════════════════════
# RENDER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def render_mining_block(mining_data, macro):
    if not mining_data: return ""
    silver_c = macro.get("silver",{}).get("c",0); silver_p = macro.get("silver",{}).get("p",0)
    gold_c   = macro.get("gold",{}).get("c",0);   gold_p   = macro.get("gold",{}).get("p",0)
    copper_c = macro.get("copper",{}).get("c",0)
    dxy_c    = macro.get("dxy",{}).get("c",0);     dxy_p    = macro.get("dxy",{}).get("p",0)
    drivers_html = (
        f'<div class="mg" style="margin-bottom:10px">'
        f'<div class="mb"><div class="ml">ARGENT</div><div class="mv {cv(silver_c)}">{silver_p:.2f}$<br><span style="font-size:9px">{pv(silver_c)}</span></div></div>'
        f'<div class="mb"><div class="ml">OR</div><div class="mv {cv(gold_c)}">{gold_p:.0f}$<br><span style="font-size:9px">{pv(gold_c)}</span></div></div>'
        f'<div class="mb"><div class="ml">CUIVRE</div><div class="mv {cv(copper_c)}">{pv(copper_c)}</div></div>'
        f'<div class="mb"><div class="ml">DXY</div><div class="mv {cv(-dxy_c)}">{dxy_p:.1f}<br><span style="font-size:9px">{pv(dxy_c)}</span></div></div>'
        f'</div>'
    )
    cards = ""
    for fv in mining_data:
        t = fv["ticker"]; info = BVC.get(t,{})
        gap = fv["gap"]; sig = fv["signal"]
        sig_col = "#00C87A" if sig=="ACHAT" else ("#FF4560" if sig=="PRUDENCE" else "#C9A84C")
        gap_col = "#00C87A" if gap>0 else "#FF4560"
        contrib_html = ""
        for k, v in sorted(fv["contributions"].items(), key=lambda x:-abs(x[1])):
            cc = "#00C87A" if v>=0 else "#FF4560"
            contrib_html += f'<span style="display:inline-block;margin-right:10px;font-size:10px"><span style="color:#6B7280">{k}</span> <span style="color:{cc};font-weight:700">{v:+.2f}%</span></span>'
        lag_html = ""
        if fv["lag_signal"]:
            lag_html = (f'<div style="background:rgba(245,158,11,.1);border-left:3px solid #F59E0B;border-radius:4px;padding:8px;margin-top:6px">'
                       f'<span style="color:#F59E0B;font-size:11px;font-weight:700">⚡ LEAD/LAG: </span>'
                       f'<span style="color:#E8E4D6;font-size:11px">{fv["lag_signal"]}</span></div>')
        cards += (
            f'<div class="card" style="border-left:4px solid {sig_col}">'
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">'
            f'<div><span style="font-size:18px;font-weight:900;color:{sig_col};font-family:monospace">{t}</span>'
            f' <span style="color:#6B7280;font-size:10px">{info.get("n","")}</span></div>'
            f'<span style="background:{sig_col}18;color:{sig_col};border:1px solid {sig_col}40;font-size:10px;padding:2px 10px;border-radius:4px">{sig}</span></div>'
            f'<div style="display:flex;gap:8px;margin-bottom:8px">'
            f'<div style="flex:1;text-align:center;background:#0F1520;border-radius:6px;padding:8px"><div style="font-size:8px;color:#6B7280">IMPLICITE (drivers)</div><div style="font-size:15px;font-weight:900;color:{cv_hex(fv["implied"])}">{fv["implied"]:+.2f}%</div></div>'
            f'<div style="flex:1;text-align:center;background:#0F1520;border-radius:6px;padding:8px"><div style="font-size:8px;color:#6B7280">REEL (marche)</div><div style="font-size:15px;font-weight:900;color:{cv_hex(fv["actual"])}">{fv["actual"]:+.2f}%</div></div>'
            f'<div style="flex:1;text-align:center;background:{gap_col}12;border-radius:6px;padding:8px;border:1px solid {gap_col}40"><div style="font-size:8px;color:#6B7280">GAP (signal)</div><div style="font-size:15px;font-weight:900;color:{gap_col}">{gap:+.2f}%</div></div>'
            f'</div><div style="margin-bottom:6px">{contrib_html}</div>'
            f'<div style="font-size:11px;color:#B0B8C8;background:rgba(0,0,0,.2);padding:7px;border-radius:5px">{fv["verdict"]}</div>'
            f'{lag_html}</div>'
        )
    return (
        '<div class="sec" style="border-color:rgba(139,92,246,.3)">'
        '<div class="st" style="color:#8B5CF6">MOTEUR CORRELATIONS MINIERES — FAIR VALUE vs MARCHE</div>'
        '<div style="font-size:9px;color:#6B7280;margin-bottom:8px">Mouvement implicite = betas appliques aux metaux temps reel. Gap = ecart exploitable.</div>'
        + drivers_html + cards +
        '<div style="font-size:9px;color:#4B5563;margin-top:6px">Betas calibrables via backtest. Argent mene SMI ~20min, Or mene Managem ~30min.</div>'
        '</div>'
    )

def render_fundamentals_block(fundamentals):
    f = fundamentals
    if not f: return ""
    rows = ""
    if f.get("ipc") is not None: rows += f'<div class="ni"><span class="src b">HCP</span>Inflation IPC: <strong style="color:#C9A84C">{f["ipc"]}%</strong></div>'
    if f.get("bam_rate") is not None: rows += f'<div class="ni"><span class="src" style="background:rgba(96,165,250,.12);color:#60A5FA">BAM</span>Taux directeur: <strong style="color:#C9A84C">{f["bam_rate"]}%</strong></div>'
    if f.get("bam_proj") is not None: rows += f'<div class="ni"><span class="src" style="background:rgba(96,165,250,.12);color:#60A5FA">BAM</span>Projection inflation: <strong style="color:#C9A84C">{f["bam_proj"]}%</strong></div>'
    for sect, val in f.get("ppi",{}).items():
        col = "#FF4560" if val>2 else ("#00C87A" if val<-1 else "#9CA3AF")
        rows += f'<div class="ni"><span class="src" style="background:rgba(139,92,246,.12);color:#8B5CF6">PPI</span>{sect}: <strong style="color:{col}">{val:+.1f}%</strong></div>'
    allnews = dedup_news((f.get("ipc_news",[]) + f.get("bam_news",[]) + f.get("ppi_news",[]))[:4])
    for n in allnews[:3]: rows += f'<div class="ni"><span class="src go">FOND</span>{n}</div>'
    if not rows: rows = '<div class="ni" style="color:#4B5563">Donnees fondamentales en cours de collecte</div>'
    return ('<div class="sec" style="border-color:rgba(139,92,246,.25)">'
            '<div class="st" style="color:#8B5CF6">FONDAMENTAUX MAROC — HCP / PPI / BAM</div>'
            '<div style="font-size:9px;color:#6B7280;margin-bottom:8px">Donnees periodiques — ajustent le biais sectoriel de la matrice.</div>'
            + rows + '</div>')

def render_scorecard_block(stats):
    if not stats or stats["total"]==0:
        return ('<div class="sec"><div class="st">SCORECARD — SUIVI PERFORMANCE</div>'
                f'<div style="font-size:11px;color:#6B7280">Collecte en cours. ({stats.get("open",0) if stats else 0} positions suivies).</div></div>')
    hr = stats["hit_rate"]; hr_col = "#00C87A" if hr>=55 else ("#C9A84C" if hr>=45 else "#FF4560")
    pnl_col = "#00C87A" if stats["avg_pnl"]>=0 else "#FF4560"
    tf_rows = ""
    for tf, lbl in [("day","Intraday"),("week","Semaine"),("quarter","3 Mois")]:
        if tf in stats["by_tf"]:
            d = stats["by_tf"][tf]; c = "#00C87A" if d["hit"]>=55 else ("#C9A84C" if d["hit"]>=45 else "#FF4560")
            tf_rows += f'<div class="ni"><span style="color:#6B7280;min-width:80px;display:inline-block">{lbl}</span> <strong style="color:{c}">{d["hit"]}%</strong> <span style="color:#4B5563">({d["n"]} trades)</span></div>'
    return ('<div class="sec" style="border-color:rgba(0,200,122,.25)">'
            '<div class="st" style="color:#00C87A">SCORECARD — EDGE PROUVE (suivi forward reel)</div>'
            '<div class="mg" style="margin-bottom:8px">'
            f'<div class="mb"><div class="ml">HIT-RATE</div><div class="mv" style="color:{hr_col}">{hr}%</div></div>'
            f'<div class="mb"><div class="ml">P&L MOYEN</div><div class="mv" style="color:{pnl_col}">{stats["avg_pnl"]:+.1f}%</div></div>'
            f'<div class="mb"><div class="ml">CLOTUREES</div><div class="mv go">{stats["total"]}</div></div>'
            f'<div class="mb"><div class="ml">SUIVIES</div><div class="mv b">{stats["open"]}</div></div>'
            '</div>' + tf_rows +
            '<div style="font-size:9px;color:#4B5563;margin-top:6px">Suivi forward reel. L\'edge se construit seance apres seance.</div></div>')

def render_geo_event(ev):
    if not ev: return ""
    win = " ".join(f'<span style="color:#00C87A;font-weight:700">{w}</span>' for w in ev.get("winners",[]))
    los = " ".join(f'<span style="color:#FF4560;font-weight:700">{l}</span>' for l in ev.get("losers",[]))
    return ('<div class="geo" style="border-color:rgba(245,158,11,.4)">'
            '<div class="geot" style="color:#F59E0B">EVENEMENT STRUCTURANT DETECTE — CHAINE D\'IMPACT</div>'
            f'<div style="font-size:12px;color:#E8E4D6;line-height:1.7;margin-bottom:8px">{ev["chain"]}</div>'
            + (f'<div style="font-size:11px"><span style="color:#6B7280">Beneficiaires: </span>{win}</div>' if win else "")
            + (f'<div style="font-size:11px;margin-top:3px"><span style="color:#6B7280">Sous pression: </span>{los}</div>' if los else "")
            + '</div>')

def render_transmission_block(signals, macro, geo_event=None):
    geo_html = render_geo_event(geo_event)
    if not signals and not geo_html: return ""
    rows = ""
    for s in signals[:10]:
        sig_col = "#00C87A" if s["signal"]=="ACHAT" else ("#FF4560" if s["signal"]=="PRUDENCE" else "#C9A84C")
        gap_col = "#00C87A" if s["gap"]>0 else "#FF4560"; dom = s.get("dominant",("",0))
        rows += (f'<div style="display:flex;align-items:center;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:11px">'
                 f'<span style="color:{sig_col};font-weight:700;font-family:monospace;min-width:64px">{s["ticker"]}</span>'
                 f'<span style="color:#6B7280;min-width:96px;font-size:10px">{s["sector"]}</span>'
                 f'<span style="color:#9CA3AF;flex:1">impl <strong style="color:{cv_hex(s["implied"])}">{s["implied"]:+.1f}%</strong> vs reel <strong style="color:{cv_hex(s["actual"])}">{s["actual"]:+.1f}%</strong></span>'
                 f'<span style="color:{gap_col};font-weight:700;min-width:60px;text-align:right">gap {s["gap"]:+.1f}%</span>'
                 f'<span style="color:#6B7280;min-width:78px;text-align:right;font-size:9px">{dom[0]} {dom[1]:+.1f}%</span></div>')
    matrix = ('<div class="sec" style="border-color:rgba(96,165,250,.3)">'
              '<div class="st" style="color:#60A5FA">MATRICE DE TRANSMISSION MACRO -> SECTEUR -> ACTION</div>'
              '<div style="font-size:9px;color:#6B7280;margin-bottom:8px">Gap = ecart exploitable.</div>'
              + (rows if rows else '<div style="color:#4B5563;font-size:11px">BVC alignee avec sa macro aujourd\'hui</div>')
              + '</div>')
    return geo_html + matrix

# ═══════════════════════════════════════════════════════════════════════════════
# [v7.2] ÉLASTICITÉ PRIX SMI / MANAGEM — nouveaux blocs HTML
# ═══════════════════════════════════════════════════════════════════════════════

def render_elasticity_block(bvc_data, macro):
    """
    Bloc HTML valorisation SMI / MANAGEM / CMT par élasticité prix.
    [v7.3] MNG: modèle bi-facteur or+cuivre | CMT: argent 65%+zinc 35%
    bvc_data=None → mode pré-ouverture (BVC fermé).
    """
    ag  = macro.get("silver",{}).get("p",0) or 58.0
    au  = macro.get("gold",{}).get("p",0)   or 4000.0
    cu  = macro.get("copper",{}).get("p",0) or 0.0
    zn  = macro.get("zinc",{}).get("p",0)   or 0.0

    smi_p = bvc_data.get("SMI",{}).get("close",0)     if bvc_data else 0
    mng_p = bvc_data.get("MANAGEM",{}).get("close",0)  if bvc_data else 0
    cmt_p = bvc_data.get("CMT",{}).get("close",0)      if bvc_data else 0
    smi_o = bvc_data.get("SMI",{}).get("open",0)       if bvc_data else 0
    mng_o = bvc_data.get("MANAGEM",{}).get("open",0)   if bvc_data else 0
    cmt_o = bvc_data.get("CMT",{}).get("open",0)       if bvc_data else 0

    smi_fv  = smi_fair_value(ag)
    mng_fv  = mng_fair_value(au, cu)
    cmt_fv  = cmt_fair_value(ag, zn)
    smi_bet = smi_local_beta(ag)
    smi_el  = smi_elasticity(ag, smi_p or smi_fv)
    mng_el  = mng_elasticity(au, mng_p or mng_fv, cu)
    cmt_bet = cmt_local_beta_ag(ag, cmt_p or cmt_fv)
    cmt_el  = cmt_elasticity(ag, cmt_p or cmt_fv, zn)
    ag_smi  = smi_bet * ag * 0.01
    au_mng  = 3.43 * au * 0.01
    ag_cmt  = cmt_bet * ag * 0.01

    def stock_card(name, bvc, fv, el, lim_o, plus1, drv_sym, drv_price, color="#C9A84C", note=""):
        if bvc > 0:
            sig, gap = valuation_signal(bvc, fv)
            gc  = "#00C87A" if gap > 0 else "#FF4560"
            top = (
                f'<div style="display:flex;gap:6px;margin-bottom:6px">'
                f'<div style="flex:1;background:#0F1520;border-radius:6px;padding:8px;text-align:center">'
                f'<div style="font-size:8px;color:#6B7280">BVC</div>'
                f'<div style="font-size:14px;font-weight:900;color:#E8E4D6">{bvc:,.0f}</div></div>'
                f'<div style="flex:1;background:#0F1520;border-radius:6px;padding:8px;text-align:center">'
                f'<div style="font-size:8px;color:#6B7280">FV</div>'
                f'<div style="font-size:14px;font-weight:900;color:{color}">{fv:,.0f}</div></div>'
                f'<div style="flex:1;background:{gc}12;border:1px solid {gc}40;border-radius:6px;padding:8px;text-align:center">'
                f'<div style="font-size:8px;color:#6B7280">GAP</div>'
                f'<div style="font-size:14px;font-weight:900;color:{gc}">{gap:+.1f}%</div></div></div>'
                f'<div style="font-size:10px;color:#B0B8C8;background:rgba(0,0,0,.2);padding:6px;border-radius:4px;margin-bottom:6px">{sig}</div>'
            )
        else:
            top = (
                f'<div style="background:#0F1520;border-radius:6px;padding:10px;text-align:center;margin-bottom:6px">'
                f'<div style="font-size:8px;color:#6B7280">{drv_sym} ${drv_price:.1f} → FV (BVC fermé)</div>'
                f'<div style="font-size:17px;font-weight:900;color:{color}">{fv:,.0f} MAD</div></div>'
            )
        lh = round(lim_o * 1.10) if lim_o > 0 else 0
        lb = round(lim_o * 0.90) if lim_o > 0 else 0
        return (
            f'<div style="font-size:11px;color:{color};font-weight:700;margin-bottom:6px;font-family:monospace">{name}</div>'
            + top
            + '<div class="mg">'
            + f'<div class="mb"><div class="ml">+1%→MAD</div><div class="mv g">+{plus1:,.0f}</div></div>'
            + f'<div class="mb"><div class="ml">Él.</div><div class="mv go">{el:.2f}×</div></div>'
            + (f'<div class="mb"><div class="ml">Lim▲</div><div class="mv b">{lh:,}</div></div>' if lh else '')
            + (f'<div class="mb"><div class="ml">Lim▼</div><div class="mv r">{lb:,}</div></div>' if lb else '')
            + '</div>'
            + (f'<div style="font-size:9px;color:#4B5563;margin-top:4px">{note}</div>' if note else '')
        )

    cu_note = (f" | Cu${cu:,.0f}/T {(cu-9200)/9200*100:+.1f}%vs ref" if cu > 0 else " | Cu n.d.")
    zn_note = (f" | Zn${zn:,.0f}/T" if zn > 0 else " | Zn n.d.")

    smi_card = stock_card("SMI / IMITER",  smi_p, smi_fv, smi_el, smi_o, ag_smi, "Ag", ag,
                          "#38bdf8", f"pure argent | β={smi_bet:.0f} MAD/$/oz")
    mng_card = stock_card("MANAGEM",       mng_p, mng_fv, mng_el, mng_o, au_mng, "Au", au,
                          "#fbbf24", f"or 48%+Cu 25%{cu_note}")
    cmt_card = stock_card("CMT / TIGHZA",  cmt_p, cmt_fv, cmt_el, cmt_o, ag_cmt, "Ag", ag,
                          "#a78bfa", f"Ag 65%+Zn+Pb 35%{zn_note} | 95g/t Ag Tighza")

    return (
        '<div class="sec" style="border-color:rgba(201,168,76,.3)">'
        '<div class="st" style="color:#C9A84C">ELASTICITE PRIX — VALORISATION SMI / MANAGEM / CMT</div>'
        f'<div style="font-size:9px;color:#6B7280;margin-bottom:10px">'
        f'Ag${ag:.2f} · β_smi={smi_bet:.0f} · el={smi_el:.2f}x &nbsp;|&nbsp; '
        f'Au${au:,.0f} · β_mng=3.43 · el={mng_el:.2f}x &nbsp;|&nbsp; '
        f'CMT β_ag={cmt_bet:.0f} · el={cmt_el:.2f}x</div>'
        '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">'
        + smi_card + mng_card + cmt_card
        + '</div>'
        + '<div style="font-size:9px;color:#4B5563;margin-top:8px">'
        + 'MNG: base or beta calibre + ajust. Cu 25% CA | CMT: Ag 65%+Zn+Pb 35% CA (mine Tighza polymetal.)'
        + '</div></div>'
    )


def render_mines_alert_email(mine_alerts):
    """Email HTML Baraka pour alertes mines ±1% XAG/XAU."""
    a0    = mine_alerts[0]
    arrow = "▲" if a0["move_pct"] > 0 else "▼"
    subject = (
        f"⚡ BARAKA ALERT — {a0['commodity']} "
        f"{arrow}{abs(a0['move_pct']):.1f}% — "
        f"{a0['stock']} théo {a0['fv_mad']:,} MAD"
    )
    th    = THRESHOLD_PCT
    cards = ""
    for a in mine_alerts:
        sig_col = "#00C87A" if a["move_pct"] > 0 else "#FF4560"
        arr     = "▲" if a["move_pct"] > 0 else "▼"
        el      = a["elasticity"]
        fv      = a["fv_mad"]

        if a["bvc_mad"] and a["gap_pct"] is not None:
            gc      = "#00C87A" if a["gap_pct"] > 0 else "#FF4560"
            gap_lbl = ("← retard BVC" if a["gap_pct"] > 3 else
                       "← BVC en avance" if a["gap_pct"] < -3 else "← aligné")
            gap_row = (
                f'<div style="display:flex;gap:6px;margin-bottom:8px">'
                f'<div style="flex:1;background:#0F1520;border-radius:6px;padding:8px;text-align:center">'
                f'<div style="font-size:8px;color:#6B7280">BVC</div>'
                f'<div style="font-size:15px;font-weight:900;color:#E8E4D6">{a["bvc_mad"]:,}</div></div>'
                f'<div style="flex:1;background:#0F1520;border-radius:6px;padding:8px;text-align:center">'
                f'<div style="font-size:8px;color:#6B7280">THÉORIQUE</div>'
                f'<div style="font-size:15px;font-weight:900;color:#C9A84C">{fv:,}</div></div>'
                f'<div style="flex:1;background:{gc}12;border:1px solid {gc}40;border-radius:6px;padding:8px;text-align:center">'
                f'<div style="font-size:8px;color:#6B7280">GAP</div>'
                f'<div style="font-size:14px;font-weight:900;color:{gc}">{a["gap_pct"]:+.1f}%</div></div></div>'
                f'<div style="font-size:10px;color:#9CA3AF;margin-bottom:8px">{gap_lbl}</div>'
            )
        else:
            gap_row = (
                f'<div style="background:#0F1520;border-radius:6px;padding:10px;text-align:center;margin-bottom:8px">'
                f'<div style="font-size:8px;color:#6B7280">THÉORIQUE</div>'
                f'<div style="font-size:18px;font-weight:900;color:#C9A84C">{fv:,} MAD</div></div>'
            )

        cards += (
            f'<div class="card" style="border-left:4px solid {sig_col}">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
            f'<div><span style="font-size:18px;font-weight:900;color:{sig_col};font-family:monospace">{arr} {a["commodity"]}</span>'
            f'<div style="font-size:10px;color:#6B7280">Réf: ${a["price_ref"]:.2f} → maintenant ${a["price_now"]:.2f}/oz</div></div>'
            f'<div style="text-align:right"><div style="font-size:24px;font-weight:900;color:{sig_col}">{a["move_pct"]:+.2f}%</div>'
            f'<div style="font-size:10px;color:#6B7280">{a["stock"]}</div></div></div>'
            f'<div class="mg" style="margin-bottom:8px">'
            f'<div class="mb"><div class="ml">β local</div><div class="mv go">{a["beta"]} MAD/$</div></div>'
            f'<div class="mb"><div class="ml">Élasticité</div><div class="mv go">{el:.2f}×</div></div>'
            f'<div class="mb"><div class="ml">Palier</div><div class="mv or">±{th:.0f}%</div></div></div>'
            + gap_row +
            f'<div style="font-size:10px;color:#6B7280;margin-bottom:6px">Prochains steps :</div>'
            f'<div class="mg">'
            f'<div class="mb" style="border:1px solid rgba(0,200,122,.3)"><div class="ml">+{th:.0f}%</div><div class="mv g">{round(fv*(1+el*th/100)):,}</div></div>'
            f'<div class="mb" style="border:1px solid rgba(255,69,96,.3)"><div class="ml">−{th:.0f}%</div><div class="mv r">{round(fv*(1-el*th/100)):,}</div></div>'
            f'</div></div>'
        )

    html = (
        f'<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>'
        f'<body><div class="w">'
        f'<div class="hdr" style="border-color:rgba(245,158,11,.5)">'
        f'<div class="logo">BARAKA</div>'
        f'<div class="sub">⚡ ALERTE MINES ±{th:.0f}% — {datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}</div>'
        f'</div>'
        + cards
        + f'<div class="ft"><strong class="go">BARAKA v7.2 — Alerte Temps Réel</strong></div>'
        f'</div></body></html>'
    )
    return subject, html

# ─── EMAIL & GROQ ─────────────────────────────────────────────────────────────
def send_email(subject, html):
    if not RESEND_KEY: print("[EMAIL] No key"); return False
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

def groq_call(prompt, max_tokens=500, system="Tu es un analyste BVC hedge fund. Reponds UNIQUEMENT en bullets courts, jamais en paragraphes."):
    if not GROQ_KEY: return ""
    try:
        from groq import Groq
        c = Groq(api_key=GROQ_KEY)
        msgs = [{"role":"system","content":system},{"role":"user","content":prompt}]
        r = c.chat.completions.create(model="llama-3.3-70b-versatile",messages=msgs,max_tokens=max_tokens,temperature=0.1)
        return r.choices[0].message.content.strip()
    except Exception as e:
        print(f"[GROQ] {e}"); return ""

# ─── DONNEES MARCHE ───────────────────────────────────────────────────────────
def fred_last_valid(series_id):
    try:
        r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}", headers=HDR, **R)
        vals = []
        for line in reversed(r.text.strip().splitlines()):
            parts = line.split(",")
            if len(parts) < 2: continue
            try:
                v = float(parts[1]); vals.append(v)
                if len(vals) == 2: break
            except: continue
        if len(vals) >= 2: return {"curr":vals[0],"prev":vals[1],"chg":round((vals[0]-vals[1])/vals[1]*100,2)}
        elif len(vals) == 1: return {"curr":vals[0],"prev":vals[0],"chg":0}
    except: pass
    return {"curr":0,"prev":0,"chg":0}

def tv_quotes(tickers):
    TV_H = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
            "Content-Type":"application/json","Origin":"https://www.tradingview.com","Referer":"https://www.tradingview.com/","Accept":"application/json"}
    payload = {"symbols":{"tickers":tickers,"query":{"types":[]}},"columns":["close","change","change_abs"]}
    out = {}
    for endpoint in ["https://scanner.tradingview.com/global/scan","https://scanner.tradingview.com/america/scan"]:
        try:
            r = requests.post(endpoint, headers=TV_H, json=payload, timeout=20, verify=False)
            if r.status_code != 200: continue
            for row in r.json().get("data",[]):
                sym = row.get("s",""); vals = row.get("d",[])
                if len(vals) >= 2 and vals[0] is not None:
                    try: out[sym] = {"p":round(float(vals[0]),2),"c":round(float(vals[1]),2) if vals[1] is not None else 0}
                    except: pass
            if out: break
        except Exception as e: print(f"[TV-Q] {endpoint}: {e}")
    return out

TV_MAP = {
    "sp500":"SP:SPX","nasdaq":"NASDAQ:IXIC","cac40":"EURONEXT:PX1","dax":"XETR:DAX",
    "ftse":"TVC:UKX","nikkei":"TVC:NI225","shanghai":"SSE:000001","hsi":"TVC:HSI",
    "gold":"TVC:GOLD","silver":"TVC:SILVER","brent":"TVC:UKOIL","wti":"TVC:USOIL",
    "copper":"CAPITALCOM:COPPER","dxy":"TVC:DXY","vix":"TVC:VIX","us10y":"TVC:US10Y",
    "us2y":"TVC:US02Y","usd_mad":"FX_IDC:USDMAD","eur_mad":"FX_IDC:EURMAD","eur_usd":"FX_IDC:EURUSD",
    # [v7.3] Métaux industriels — drivers CMT (zinc+plomb) et contexte MNG
    "zinc":"CAPITALCOM:ZINC",   # LME Zinc $/T — CMT: 20% CA + proxy plomb
    "lead":"CAPITALCOM:LEAD",   # LME Plomb $/T — CMT: 15% CA
}

def get_macro():
    m = {}; syms = list(TV_MAP.values()); q = tv_quotes(syms); inv = {v:k for k,v in TV_MAP.items()}; got = 0
    for tv_sym, data in q.items():
        name = inv.get(tv_sym)
        if name: m[name] = data; got += 1
    print(f"[MACRO] TradingView: {got}/{len(syms)} symboles")
    defaults = {"sp500":{"p":0,"c":0},"nasdaq":{"p":0,"c":0},"cac40":{"p":0,"c":0},"dax":{"p":0,"c":0},"ftse":{"p":0,"c":0},"nikkei":{"p":0,"c":0},"shanghai":{"p":0,"c":0},"hsi":{"p":0,"c":0},"gold":{"p":0,"c":0},"silver":{"p":0,"c":0},"brent":{"p":0,"c":0},"wti":{"p":0,"c":0},"copper":{"p":0,"c":0},"dxy":{"p":0,"c":0},"vix":{"p":20,"c":0},"us10y":{"p":0,"c":0},"us2y":{"p":0,"c":0},"zinc":{"p":0,"c":0},"lead":{"p":0,"c":0}}
    for k,v in defaults.items():
        if k not in m: m[k] = v
    m["us10y_chg"] = m["us10y"]["c"] if isinstance(m["us10y"],dict) else 0
    m["us10y_val"] = m["us10y"]["p"] if m["us10y"]["p"]>0 else fred_last_valid("DGS10")["curr"]
    m["us2y_val"]  = m["us2y"]["p"]  if m["us2y"]["p"]>0  else fred_last_valid("DGS2")["curr"]
    m["us10y"] = m["us10y_val"]; m["us2y"] = m["us2y_val"]
    m["fed_rate"] = fred_last_valid("FEDFUNDS")["curr"] or 5.25
    m["yield_spread"] = round(m["us10y_val"] - m["us2y_val"], 3)
    m["recession_risk"] = m["yield_spread"] < 0
    for fx in ["usd_mad","eur_mad","eur_usd"]:
        if fx not in m or not isinstance(m[fx],dict): m[fx] = {"p":0,"c":0}
    if m["usd_mad"]["p"] > 0:
        m["eur_mad_v"] = m["eur_mad"]["p"] if m["eur_mad"]["p"]>0 else round(m["usd_mad"]["p"]*0.92,4)
        m["eur_usd"]   = m["eur_usd"]["p"] if m["eur_usd"]["p"]>0 else 1.08
        m["gbp_mad"]   = round(m["usd_mad"]["p"]*1.27,4)
        m["usd_mad"]   = m["usd_mad"]["p"]; m["eur_mad"] = m["eur_mad_v"]
    else:
        try:
            r = requests.get("https://open.er-api.com/v6/latest/USD", headers=HDR, **R)
            d = r.json().get("rates",{})
            m["usd_mad"] = round(float(d.get("MAD",10.0)),4)
            m["eur_mad"] = round(m["usd_mad"]*float(d.get("EUR",0.92)),4)
            m["gbp_mad"] = round(m["usd_mad"]*float(d.get("GBP",0.79)),4)
            m["eur_usd"] = round(1/float(d.get("EUR",0.92)),4) if d.get("EUR") else 1.08
        except: m.update({"usd_mad":10.0,"eur_mad":10.9,"gbp_mad":12.5,"eur_usd":1.08})
    m["phosphate"] = {"p":0,"c":0}
    return m

def get_bvc_data():
    TV_H = {"User-Agent":"Mozilla/5.0","Content-Type":"application/json","Origin":"https://www.tradingview.com","Referer":"https://www.tradingview.com/markets/stocks-morocco/"}
    payload = {"filter":[],"columns":["name","close","volume","change","RSI","MACD.macd","MACD.signal","EMA20","EMA50","EMA200","Stoch.K","ADX","high","low","open","Recommend.All","average_volume_10d_calc","average_volume_30d_calc","average_volume_90d_calc","BB.upper","BB.lower"],"sort":{"sortBy":"market_cap_basic","sortOrder":"desc"},"range":[0,100]}
    data = {}
    try:
        r = requests.post("https://scanner.tradingview.com/morocco/scan", headers=TV_H, json=payload, timeout=25, verify=False)
        if r.status_code != 200: print(f"[TV] HTTP {r.status_code}"); return {}
        rows = r.json().get("data",[]); print(f"[TV] {len(rows)} titres recus")
        for row in rows:
            raw = row.get("s","").upper(); vals = row.get("d",[])
            if len(vals) < 4: continue
            ticker = None
            for t in BVC:
                if t in raw: ticker = t; break
            if not ticker: continue
            def v(i,d=0):
                try: return float(vals[i]) if vals[i] is not None else d
                except: return d
            avg90=v(18,0); avg30=v(17,0); avg10=v(16,0)
            avg_vol = avg90 or avg30 or avg10 or BVC.get(ticker,{}).get("v",1)
            rec = v(15,0)
            data[ticker] = {"close":v(1),"volume":int(v(2)),"change":round(v(3),2),"rsi":v(4,50),"macd":v(5),"macd_s":v(6),"ema20":v(7),"ema50":v(8),"ema200":v(9),"stoch":v(10,50),"adx":v(11),"high":v(12),"low":v(13),"open":v(14),"bb_upper":v(19),"bb_lower":v(20),"rec":"ACHAT" if rec>0.1 else ("VENTE" if rec<-0.1 else "NEUTRE"),"avg10":avg10,"avg30":avg30,"avg90":avg90,"avg_vol":avg_vol}
        print(f"[TV] {len(data)} titres BVC")
    except Exception as e: print(f"[TV] {e}")
    return data

def gnews(q, n=4):
    try:
        from urllib.parse import quote
        r = requests.get(f"https://news.google.com/rss/search?q={quote(q)}&hl=fr&gl=MA&ceid=MA:fr", headers=HDR, **R)
        titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", r.text)
        items = []
        for t in titles[1:n+1]:
            clean = re.sub(r"<[^>]+>","",t).strip()
            if len(clean)>15: items.append(clean[:180])
        return items
    except: return []

def get_geo():
    return {
        "iran_usa":     gnews("Iran USA attaque 2026", 3),
        "israel":       gnews("Israel frappe attaque 2026", 3),
        "ukraine":      gnews("Ukraine Russie guerre 2026", 3),
        "usa_chine":    gnews("USA Chine tensions 2026", 2),
        "fed":          gnews("Fed Reserve taux 2026", 3),
        "bce":          gnews("BCE taux Euro 2026", 2),
        "petrole":      gnews("petrole Brent prix 2026", 3),
        "marche_crash": gnews("bourse chute crash 2026", 3),
        "maroc_bvc":    gnews("Maroc bourse MASI 2026", 4),
        "maroc_bam":    gnews("BAM Maroc taux 2026", 3),
        "phosphate":    gnews("phosphate OCP prix 2026", 2),
        "or_mines":     gnews("or argent mines 2026", 2),
    }

def get_ammc():
    pubs = []
    try:
        from bs4 import BeautifulSoup
        seen = set()
        for page in range(0,6):
            url = f"https://www.ammc.ma/fr/communiques-presse-emetteurs?page={page}" if page else "https://www.ammc.ma/fr/communiques-presse-emetteurs"
            r = requests.get(url, headers=HDR, **R)
            if r.status_code != 200: break
            soup = BeautifulSoup(r.text,"html.parser"); found = 0
            for link in soup.find_all("a",href=True):
                href = link["href"]; text = link.get_text(strip=True)
                if not text or len(text)<5: continue
                if not any(x in href.lower() for x in [".pdf","telecharger","download"]): continue
                full = href if href.startswith("http") else "https://www.ammc.ma"+href
                if full in seen: continue
                seen.add(full)
                ticker = None; tu = text.upper()
                for t,info in BVC.items():
                    if t in tu or info["n"].split()[0].upper() in tu: ticker = t; break
                tl = text.upper()
                ptype = "normal"
                if any(w in tl for w in ["PROFIT WARNING","AVERTISSEMENT","REVISION","PERTE"]): ptype="warning"
                elif any(w in tl for w in ["DIVIDENDE","DISTRIBUTION"]): ptype="dividende"
                elif any(w in tl for w in ["RESULTATS","CHIFFRE","BILAN","BENEFICE"]): ptype="resultats"
                elif any(w in tl for w in ["ACQUISITION","FUSION","OPA"]): ptype="operation"
                pubs.append({"url":full,"title":text[:150],"ticker":ticker,"type":ptype}); found += 1
            if found==0: break
            time.sleep(0.4)
        print(f"[AMMC] {len(pubs)} pubs")
    except Exception as e: print(f"[AMMC] {e}")
    return pubs[:40]

def get_boursenews():
    try:
        from bs4 import BeautifulSoup
        r = requests.get("https://www.boursenews.ma/", headers=HDR, **R)
        soup = BeautifulSoup(r.text,"html.parser"); items = []
        for el in soup.select("article h2,article h3,.entry-title")[:8]:
            t = el.get_text(strip=True)
            if len(t)>20: items.append(t[:200])
        return list(dict.fromkeys(items))[:6]
    except: return []

def get_social():
    posts = []
    for ch in ["boursecasablancaofficiel","bvcmaroc","tradingmaroc"]:
        try:
            from bs4 import BeautifulSoup
            r = requests.get(f"https://t.me/s/{ch}", headers=HDR, **R)
            soup = BeautifulSoup(r.text,"html.parser")
            for msg in soup.select(".tgme_widget_message_text")[:2]:
                t = msg.get_text(strip=True)
                if len(t)>20: posts.append({"src":"Telegram","t":t[:180]})
        except: pass
        time.sleep(0.3)
    for n in gnews("bourse Casablanca MASI investisseurs 2026",4):
        posts.append({"src":"Google","t":n})
    return posts[:10]

def detect_crisis(macro):
    alerts=[]
    sp_c=macro.get("sp500",{}).get("c",0); brent_c=macro.get("brent",{}).get("c",0)
    gold_c=macro.get("gold",{}).get("c",0); vix_p=macro.get("vix",{}).get("p",20)
    if sp_c<-1: alerts.append(f"S&P500 {sp_c:.1f}% EN FORTE BAISSE — BVC ouverture negative attendue")
    if sp_c<-2: alerts.append(f"S&P500 {sp_c:.1f}% CRASH POSSIBLE — risk off mondial")
    if brent_c>3: alerts.append(f"BRENT +{brent_c:.1f}% CHOC PETROLIER — inflation Maroc, CTM/TMA sous pression")
    if brent_c<-3: alerts.append(f"Brent {brent_c:.1f}% effondrement — soulagement inflation")
    if gold_c<-1.5: alerts.append(f"OR {gold_c:.1f}% VENTE FORCEE — deleveraging, Managem/SMI sous pression")
    if gold_c>2: alerts.append(f"OR +{gold_c:.1f}% REFUGE — Managem/SMI en hausse")
    if vix_p>25 and vix_p<999: alerts.append(f"VIX={vix_p:.0f} VOLATILITE ELEVEE")
    if vix_p>35 and vix_p<999: alerts.append(f"VIX={vix_p:.0f} PANIQUE — risk off fort")
    return alerts

# ─── MEDIA SOURCES ────────────────────────────────────────────────────────────
def get_cac40_premarket(macro):
    result = {"cac_open_chg":0.0,"cac_current":0.0,"cac_prev":0.0,"signal":"NEUTRE","impact":"","news_cac":[]}
    try:
        cac = macro.get("cac40",{}); chg = cac.get("c",0); prix = cac.get("p",0)
        result["cac_current"] = prix; result["cac_open_chg"] = chg
        bvc_implied = round(chg * 0.7, 2)
        if chg > 0.5:   result["signal"] = "HAUSSIER"; result["impact"] = f"CAC40 +{chg:.2f}% → BVC implied +{bvc_implied:.2f}%"
        elif chg < -0.5: result["signal"] = "BAISSIER"; result["impact"] = f"CAC40 {chg:.2f}% → BVC implied {bvc_implied:.2f}%"
        else:            result["signal"] = "NEUTRE";   result["impact"] = f"CAC40 {chg:+.2f}% → ouverture BVC stable"
        result["news_cac"] = dedup_news(gnews("CAC40 bourse Paris ouverture 2026", 3))
    except Exception as e: print(f"[CAC40] {e}")
    return result

def get_trump_signals():
    items = []
    for q in ["Trump tweet declaration tarifs 2026","Trump Fed taux interet 2026","Trump sanctions Iran petrole 2026","Trump Chine commerce guerre 2026","Donald Trump market economy 2026"]:
        for r in gnews(q, 2):
            if any(w in r.lower() for w in ["trump","donald","maison blanche","white house"]): items.append(r)
    return dedup_news(items)[:6]

def scrape_bfm():
    items = []
    items += scrape_rss("https://www.bfmtv.com/rss/economie/economie.xml", 4)
    items += scrape_rss("https://www.bfmtv.com/rss/bourse.xml", 3)
    if not items: items += gnews("BFM Business economie bourse 2026", 4)
    return dedup_news(items)[:5]

def scrape_reuters_bloomberg():
    items = []
    items += [f"[Reuters] {n}" for n in gnews("Reuters economie marche finance 2026", 4)]
    items += [f"[Bloomberg] {n}" for n in gnews("Bloomberg marche finance Fed 2026", 3)]
    items += scrape_rss("https://feeds.reuters.com/reuters/businessNews", 3)
    return dedup_news(items)[:6]

def scrape_alphabourse():
    items = []
    try:
        from bs4 import BeautifulSoup
        for url in ["https://www.alphabourse.com/","https://www.alphabourse.com/actualites"]:
            try:
                r = requests.get(url, headers=HDR, **R)
                if r.status_code != 200: continue
                soup = BeautifulSoup(r.text,"html.parser")
                for el in soup.select("h2,h3,.article-title,.post-title,article h2,article h3")[:10]:
                    t = el.get_text(strip=True)
                    if len(t)>15: items.append(t[:180])
            except: pass
    except: pass
    if not items: items += gnews("alphabourse BVC analyse technique 2026", 4)
    return dedup_news(items)[:5]

def scrape_lavieeco():
    items = []
    try:
        from bs4 import BeautifulSoup
        r = requests.get("https://lavieeco.com/", headers=HDR, **R)
        soup = BeautifulSoup(r.text,"html.parser")
        for el in soup.select("h2,h3,.entry-title,article h2")[:8]:
            t = el.get_text(strip=True)
            if len(t)>15: items.append(t[:180])
    except: pass
    items += scrape_rss("https://lavieeco.com/feed/", 4)
    if not items: items += gnews("La Vie Economique Maroc finance 2026", 4)
    return dedup_news(items)[:5]

def scrape_leconomiste():
    items = []
    try:
        from bs4 import BeautifulSoup
        r = requests.get("https://www.leconomiste.com/", headers=HDR, **R)
        soup = BeautifulSoup(r.text,"html.parser")
        for el in soup.select("h2,h3,.article-title,article h2,.titre")[:8]:
            t = el.get_text(strip=True)
            if len(t)>15: items.append(t[:180])
    except: pass
    items += scrape_rss("https://www.leconomiste.com/rss.xml", 4)
    if not items: items += gnews("L Economiste Maroc entreprises finance 2026", 4)
    return dedup_news(items)[:5]

def scrape_boursenews_full():
    items = []
    try:
        from bs4 import BeautifulSoup
        r = requests.get("https://www.boursenews.ma/", headers=HDR, **R)
        soup = BeautifulSoup(r.text,"html.parser")
        for el in soup.select("article h2, article h3, .entry-title")[:10]:
            t = el.get_text(strip=True)
            if len(t)>20: items.append(t[:200])
        items += scrape_rss("https://www.boursenews.ma/feed/", 4)
    except: pass
    return dedup_news(list(dict.fromkeys(items)))[:6]

def get_all_media_news():
    news = {}; print("[MEDIA] Collecte sources...")
    news["trump"]       = get_trump_signals()
    news["bfm"]         = scrape_bfm()
    news["reuters_bb"]  = scrape_reuters_bloomberg()
    news["alphabourse"] = scrape_alphabourse()
    news["boursenews"]  = scrape_boursenews_full()
    news["lavieeco"]    = scrape_lavieeco()
    news["leconomiste"] = scrape_leconomiste()
    total = sum(len(v) if isinstance(v,list) else 0 for v in news.values())
    print(f"[MEDIA] {total} articles collectes")
    return news

# ─── SCORING ──────────────────────────────────────────────────────────────────
def tech_score(d, info, macro=None):
    if not d or not d.get("close"): return 0
    s = 50
    close=d.get("close",0); rsi=d.get("rsi",50); macd=d.get("macd",0); macd_s=d.get("macd_s",0)
    ema20=d.get("ema20",0); ema50=d.get("ema50",0); ema200=d.get("ema200",0)
    vol=d.get("volume",0); avg=d.get("avg_vol",1) or 1; adx=d.get("adx",0); stoch=d.get("stoch",50)
    bb_up=d.get("bb_upper",0); bb_lo=d.get("bb_lower",0); sect=info.get("s",""); mc=info.get("mc","small")
    if rsi<20: s+=25
    elif rsi<30: s+=18
    elif rsi<40: s+=8
    elif rsi>80: s-=25
    elif rsi>70: s-=15
    elif rsi>60: s-=5
    if macd>macd_s: s += 15 if macd_s<0 else 8
    else:           s -= 12 if macd_s>0 else 6
    if close>ema20>ema50>ema200: s+=20
    elif close>ema20>ema50: s+=12
    elif close>ema20: s+=5
    elif close<ema20<ema50<ema200: s-=20
    elif close<ema20<ema50: s-=12
    elif close<ema20: s-=5
    vr = vol/avg
    if vr>5: s+=20
    elif vr>3: s+=14
    elif vr>2: s+=8
    elif vr>1.5: s+=4
    elif vr<0.4: s-=5
    if adx>35: s+=8
    elif adx>20: s+=4
    if stoch<20: s+=5
    elif stoch>80: s-=5
    if bb_lo>0 and close<=bb_lo*1.01: s+=7
    elif bb_up>0 and close>=bb_up*0.99: s-=7
    if mc=="large": s+=5
    elif mc=="mid": s+=2
    if macro:
        cac_c=macro.get("cac40",{}).get("c",0); brent_c=macro.get("brent",{}).get("c",0)
        gold_c=macro.get("gold",{}).get("c",0); silver_c=macro.get("silver",{}).get("c",0)
        phos_c=macro.get("phosphate",{}).get("c",0); sp_c=macro.get("sp500",{}).get("c",0)
        usd_mad=macro.get("usd_mad",10.0); spread=macro.get("yield_spread",0)
        rec=macro.get("recession_risk",False); vix_p=macro.get("vix",{}).get("p",20)
        if cac_c>1: s+=8
        elif cac_c>0.3: s+=4
        elif cac_c<-1: s-=7
        elif cac_c<-0.3: s-=3
        if vix_p<15: s+=5
        elif vix_p>30: s-=10
        if sect in ["Energie","Transport","Agro","Distribution"]:
            if brent_c>3: s-=12
            elif brent_c>1: s-=5
            elif brent_c<-3: s+=10
            elif brent_c<-1: s+=4
        if sect=="Mines":
            s += 14 if gold_c>1 else (8 if gold_c>0.5 else (-12 if gold_c<-1 else 0))
            s += 8 if silver_c>1 else (-8 if silver_c<-1 else 0)
        if sect in ["Chimie","Mines"]:
            s += 10 if phos_c>2 else (5 if phos_c>1 else (-7 if phos_c<-2 else 0))
        if usd_mad>10.3:
            if sect=="Chimie": s+=10
            if sect in ["Agro","Distribution","Pharma"]: s-=7
        elif usd_mad<9.7:
            if sect=="Chimie": s-=6
            if sect in ["Agro","Distribution"]: s+=5
        if sect=="Banque":
            s += 8 if spread>1 else (-12 if spread<0 else 0)
            if rec: s-=8
        if sect=="Assurance": s += 5 if spread>0.5 else (-5 if spread<0 else 0)
        if sect=="Immobilier":
            if spread<0 or rec: s-=10
            elif spread>1: s+=5
        if sect=="Telecom" and vix_p>25: s+=6
    return max(0,min(100,int(s)))

def get_direction(d, rsi_val, macro_context=""):
    rsi=rsi_val; macd=d.get("macd",0); macd_s=d.get("macd_s",0)
    close=d.get("close",0); ema20=d.get("ema20",0)
    if rsi < 28: return True, "REBOND RSI survente"
    if rsi > 72: return False, "RSI surachat sortir"
    if macd > macd_s and ema20 > 0 and close > ema20: return True, "MACD + EMA20 haussier"
    if macd < macd_s and ema20 > 0 and close < ema20: return False, "MACD + EMA20 baissier"
    return macd > macd_s, "MACD direction"

def make_reco(bvc_data, macro, ammc_pubs, timeframe, exclude=None):
    if exclude is None: exclude = set()
    scored = []
    for t, d in bvc_data.items():
        if t in exclude: continue
        info = BVC.get(t,{}); close = d.get("close",0)
        if not close: continue
        vol=d.get("volume",0); avg=d.get("avg_vol",1) or 1; rsi=d.get("rsi",50)
        chg=d.get("change",0); adx=d.get("adx",0); ema200=d.get("ema200",0); vr=vol/avg
        if vr < 0.4: continue
        if abs(chg) > 7: continue
        if at_limit(chg): continue
        sc = tech_score(d, info, macro)
        if timeframe=="day" and sc < 55: continue
        if timeframe=="week" and sc < 60: continue
        if timeframe=="quarter" and sc < 65: continue
        if timeframe=="week" and adx < 15: continue
        if timeframe=="quarter" and ema200>0 and close < ema200*0.97: continue
        scored.append({"t":t,"sc":sc,"d":d,"i":info})
    scored.sort(key=lambda x: -x["sc"])
    mults = {"day":(0.03,0.015),"week":(0.06,0.025),"quarter":(0.12,0.04)}
    m, sm = mults.get(timeframe,(0.05,0.02))
    recs = []
    for item in scored[:3]:
        t=item["t"]; d=item["d"]; i=item["i"]; sc=item["sc"]
        close=d.get("close",0); rsi=d.get("rsi",50)
        is_buy, reason = get_direction(d, rsi)
        tgt  = round(close*(1+m if is_buy else 1-m), 2)
        stop = round(close*(1-sm if is_buy else 1+sm), 2)
        if timeframe == "day":
            chg_today = d.get("change",0)
            room_up = max(0.5, BVC_DAILY_CAP - chg_today); room_dn = max(0.5, BVC_DAILY_CAP + chg_today)
            if is_buy: tgt = round(close*(1 + min(m, room_up/100)), 2)
            else:      tgt = round(close*(1 - min(m, room_dn/100)), 2)
        rr = round(abs(tgt-close)/max(abs(close-stop),0.01), 2)
        vr = round(d.get("volume",0)/(d.get("avg_vol",1) or 1), 1)
        ammc_t = [p for p in ammc_pubs if p.get("ticker")==t][:2]
        recs.append({"t":t,"sc":sc,"d":d,"i":i,"close":close,"is_buy":is_buy,"reason":reason,"target":tgt,"stop":stop,"rr":rr,"vr":vr,"ammc":ammc_t,"timeframe":timeframe})
    return recs

def exceptional_moves(bvc_data):
    alerts = []
    for t, d in bvc_data.items():
        chg=d.get("change",0); close=d.get("close",0); rsi=d.get("rsi",50)
        vol=d.get("volume",0); avg=d.get("avg_vol",1) or 1
        if abs(chg) >= 5:
            vr = round(vol/avg,1) if avg>0 else 0
            note = ""
            if chg < -7 and rsi < 40: note = f"RSI={rsi:.0f} survente — potentiel rebond technique"
            elif chg > 7 and rsi > 65: note = f"RSI={rsi:.0f} surachat — attention resistance"
            elif chg < -5: note = "Verifier news/AMMC — cause de la baisse?"
            elif chg > 5: note = "Catalyst? Verifier annonce AMMC"
            alerts.append({"t":t,"n":BVC.get(t,{}).get("n",t),"s":BVC.get(t,{}).get("s",""),"chg":chg,"close":close,"rsi":rsi,"vr":vr,"note":note})
    return sorted(alerts, key=lambda x:-abs(x["chg"]))

def smart_money(bvc_data):
    sm=[]
    for t,d in bvc_data.items():
        avg=d.get("avg_vol",1) or 1; vol=d.get("volume",0)
        if avg>0 and vol/avg>=2.5:
            sm.append({"t":t,"n":BVC.get(t,{}).get("n",""),"s":BVC.get(t,{}).get("s",""),"vr":round(vol/avg,1),"c":d.get("close",0),"chg":d.get("change",0),"rsi":d.get("rsi",50),"avg_vol":round(avg)})
    return sorted(sm,key=lambda x:-x["vr"])

def render_reco(rec, macro):
    t=rec["t"]; d=rec["d"]; i=rec["i"]; sc=rec["sc"]; close=rec["close"]
    is_buy=rec["is_buy"]; reason=rec["reason"]; tgt=rec["target"]; stop=rec["stop"]; rr=rec["rr"]; vr=rec["vr"]
    ammc_t=rec["ammc"]; tf=rec["timeframe"]; col="#00C87A" if is_buy else "#FF4560"; label="ACHAT" if is_buy else "VENTE"
    rsi=d.get("rsi",50); chg=d.get("change",0); ema20=d.get("ema20",0); ema200=d.get("ema200",0)
    macd_h="Haussier" if d.get("macd",0)>d.get("macd_s",0) else "Baissier"
    macd_c="#00C87A" if d.get("macd",0)>d.get("macd_s",0) else "#FF4560"
    tf_labels={"day":"INTRADAY","week":"SEMAINE","quarter":"3 MOIS"}
    tf_colors={"day":"#60A5FA","week":"#C9A84C","quarter":"#00C87A"}
    tgt_pct=round((tgt-close)/close*100,1); stp_pct=round(abs(close-stop)/close*100,1)
    cn = gnews(f"{i.get('n',t)} bourse Casablanca 2026", 2)
    sect=i.get("s",""); mc_ctx=""
    if macro:
        if sect=="Mines": mc_ctx=f"Or {macro.get('gold',{}).get('c',0):+.1f}%, Argent {macro.get('silver',{}).get('c',0):+.1f}%"
        elif sect in ["Energie","Transport"]: mc_ctx=f"Brent {macro.get('brent',{}).get('c',0):+.1f}%"
        elif sect=="Chimie": mc_ctx=f"Phosphate {macro.get('phosphate',{}).get('c',0):+.1f}%, USD/MAD={macro.get('usd_mad',10)}"
        elif sect=="Banque": mc_ctx=f"CAC40 {macro.get('cac40',{}).get('c',0):+.1f}%, Spread={macro.get('yield_spread',0):+.2f}%"
        else: mc_ctx=f"CAC40 {macro.get('cac40',{}).get('c',0):+.1f}%, VIX={macro.get('vix',{}).get('p',20):.0f}"
    ammc_ctx=" | ".join([a["title"][:70] for a in ammc_t]) if ammc_t else "Aucune AMMC recente"
    news_ctx=" | ".join(cn[:2]) if cn else "Aucune news specifique"
    prompt = f"""{t} | {sect} | Score {sc}/100 | Horizon {tf_labels.get(tf,"")}
RSI={rsi:.0f} | MACD={macd_h} | Vol x{vr} | Chg {chg:+.1f}%
Cours {close:.2f} MAD | EMA20 {ema20:.2f} | EMA200 {">" if close>ema200>0 else "<"} {ema200:.2f}
Macro: {mc_ctx} | AMMC: {ammc_ctx} | News: {news_ctx}
Signal: {label} ({reason})
Exactement 2 bullets:
• [ENTRER] raison precise + condition exacte (prix/volume/trigger)
• [RISQUE] risque principal + niveau sortie si negatif
Chiffres precis. 1 ligne chacun."""
    analyse = groq_call(prompt, 200) or f"• [ENTRER] Score {sc}/100, {reason}, RSI={rsi:.0f}\n• [RISQUE] Surveiller EMA20={ema20:.2f}"
    ammc_h = "".join(f'<div style="font-size:10px;color:{ammc_badge(a["type"])[0]};padding:1px 0">{ammc_badge(a["type"])[1]} {a["title"][:90]}</div>' for a in ammc_t)
    news_h = "".join(f'<div style="font-size:10px;color:#9CA3AF;padding:1px 0">📰 {n[:100]}</div>' for n in cn[:2])
    return (
        f'<div class="card" style="border-left:4px solid {col}">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">'
        f'<div><div style="font-size:20px;font-weight:900;color:{col};font-family:monospace">{t}</div>'
        f'<div style="font-size:10px;color:#6B7280">{i.get("n","")} — {sect}</div></div>'
        f'<div style="text-align:right"><div style="font-size:16px;font-weight:900;color:#E8E4D6">{close:.2f} MAD</div>'
        f'<div style="font-size:10px;color:{"#00C87A" if chg>=0 else "#FF4560"}">{chg:+.1f}% | Vol x{vr}</div>'
        f'<span style="background:{col}18;color:{col};border:1px solid {col}40;font-size:9px;padding:2px 8px;border-radius:3px">{label} {sc}/100</span>'
        f'<div style="color:{tf_colors.get(tf,"#C9A84C")};font-size:8px;margin-top:2px">{tf_labels.get(tf,"")}</div></div></div>'
        f'<div class="lv"><div style="font-size:8px;color:#C9A84C;margin-bottom:5px;letter-spacing:2px">NIVEAUX</div>'
        f'<div class="lr"><span style="color:#6B7280">Entree</span><strong style="color:#E8E4D6">{close:.2f} MAD</strong></div>'
        f'<div class="lr"><span style="color:#6B7280">Cible</span><strong style="color:#00C87A">{tgt:.2f} MAD ({sg(tgt_pct)}{tgt_pct}%)</strong></div>'
        f'<div class="lr"><span style="color:#6B7280">Stop</span><strong style="color:#FF4560">{stop:.2f} MAD (-{stp_pct}%)</strong></div>'
        f'<div class="lr"><span style="color:#6B7280">R/R</span><strong style="color:#C9A84C">{rr}</strong></div></div>'
        f'<table style="width:100%;font-size:10px;border-collapse:collapse;margin:5px 0">'
        f'<tr><td style="color:#6B7280">RSI</td><td style="color:{"#00C87A" if rsi<35 else "#FF4560" if rsi>70 else "#C9A84C"};font-weight:700">{rsi:.0f}</td>'
        f'<td style="color:#6B7280">MACD</td><td style="color:{macd_c}">{macd_h}</td>'
        f'<td style="color:#6B7280">ADX</td><td style="color:#9CA3AF">{d.get("adx",0):.0f}</td></tr>'
        f'<tr><td style="color:#6B7280">EMA20</td><td style="color:{"#00C87A" if close>ema20>0 else "#FF4560"}">{ema20:.2f}</td>'
        f'<td style="color:#6B7280">EMA200</td><td style="color:{"#00C87A" if close>ema200>0 else "#FF4560"}">{">" if close>ema200>0 else "<"}{ema200:.0f}</td>'
        f'<td style="color:#6B7280">BB</td><td style="color:#9CA3AF">{"Basse" if d.get("bb_lower",0)>0 and close<=d.get("bb_lower",0)*1.01 else "Mid"}</td></tr></table>'
        + (f'<div style="margin-top:5px">{ammc_h}</div>' if ammc_h else "")
        + (f'<div style="margin-top:3px">{news_h}</div>' if news_h else "")
        + f'<div style="font-size:11px;color:#B0B8C8;margin-top:7px;background:rgba(0,0,0,.2);padding:8px;border-radius:5px;line-height:1.8;white-space:pre-line">{analyse}</div>'
        + f'<div style="margin-top:6px"><div class="sb"><div class="sf" style="width:{sc}%"></div></div></div></div>'
    )

# ─── PRE-COLLECT 05h00 UTC ────────────────────────────────────────────────────
def pre_collect():
    print("[BARAKA] === PRE-COLLECTE 05h00 ===")
    try:
        global _NEWS_SEEN
        _NEWS_SEEN = set()
        macro  = get_macro()
        ammc   = get_ammc()
        geo    = get_geo()
        bn     = get_boursenews()
        social = get_social()
        crisis = detect_crisis(macro)
        media  = get_all_media_news()
        media["cac40_pm"] = get_cac40_premarket(macro)
        cac_pm = media["cac40_pm"]
        trump  = media.get("trump",[])

        # ── [v7.2] Pose la référence du jour pour alertes mines ±1% ──────────
        _ag_ref = macro.get("silver",{}).get("p",0)
        _au_ref = macro.get("gold",{}).get("p",0)
        if _ag_ref > 0 and _au_ref > 0:
            set_daily_reference(_ag_ref, _au_ref)
        # ─────────────────────────────────────────────────────────────────────

        sp_c=macro.get("sp500",{}).get("c",0); cac_c=macro.get("cac40",{}).get("c",0)
        brent_c=macro.get("brent",{}).get("c",0); gold_c=macro.get("gold",{}).get("c",0)
        silver_c=macro.get("silver",{}).get("c",0); phos_c=macro.get("phosphate",{}).get("c",0)
        mad=macro.get("usd_mad",10.0); eur_mad=macro.get("eur_mad",10.9)
        vix_p=macro.get("vix",{}).get("p",20); spread=macro.get("yield_spread",0)
        fed=macro.get("fed_rate",5.25); t10=macro.get("us10y",0)

        prompt = f"""BVC Casablanca - Brief 05h00.
ALERTES CRISE: {crisis if crisis else "Aucune"}
SP500 {sp_c:+.1f}% | CAC40 {cac_c:+.1f}% | VIX={vix_p:.0f}
Brent {brent_c:+.1f}% | Or {gold_c:+.1f}% | Argent {silver_c:+.1f}%
USD/MAD={mad} | US10Y={t10}% Spread={spread:+.2f}%
Geo Iran/USA: {geo.get("iran_usa",[])} | Fed: {geo.get("fed",[])}
AMMC: {[(p["type"].upper()+":"+p["title"][:60]) for p in ammc[:6]]}
CAC40 pre-market: {cac_pm.get("impact","")}
Trump: {trump}
BULLETS UNIQUEMENT (max 9):
• [CAC40] comment ouvert + implication BVC
• [GEO] evenement du jour + impact BVC chiffre
• [OR/MINES] si or/argent >1%: impact Managem/SMI
• [BRENT] impact petrole Maroc sectoriel
• [MAD] USD/MAD impact importateurs vs exportateurs
• [AMMC] si warning ou resultats importants
• [SECTEURS] 2-3 secteurs prioritaires"""
        deep_analysis = groq_call(prompt, 600)

        sector_prompt = f"""BVC rotation sectorielle.
CAC40={cac_c:+.1f}% Brent={brent_c:+.1f}% Or={gold_c:+.1f}% USD/MAD={mad}
Chaque secteur: ACHETER/NEUTRE/EVITER + raison 5 mots:
Banque|Assurance|Telecom|Chimie|Mines|Immobilier|Energie|Transport|Agro|Sante|Construction"""
        sector_analysis = groq_call(sector_prompt, 300)

        cache_set("pre_collect",{
            "macro":macro,"ammc":ammc,"geo":geo,"boursenews":bn,"social":social,
            "crisis":crisis,"media":media,"deep_analysis":deep_analysis,
            "sector_analysis":sector_analysis,"timestamp":datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        })
        print(f"[PRE-COLLECTE] OK | Réf mines: Ag ${_ag_ref:.2f} Au ${_au_ref:.0f}")
    except Exception as e:
        print(f"[PRE-COLLECTE] {e}")
        import traceback; traceback.print_exc()

# ─── EMAIL 1: BRIEF OUVERTURE 07h30 UTC ──────────────────────────────────────
def brief_ouverture():
    print("[BARAKA] === BRIEF OUVERTURE 07h30 ===")
    try:
        now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        cached = cache_get("pre_collect", max_min=180)
        if cached:
            macro=cached["macro"]; ammc=cached["ammc"]; geo=cached["geo"]
            bn=cached["boursenews"]; social=cached["social"]; crisis=cached["crisis"]
            media=cached.get("media",{}); deep_analysis=cached.get("deep_analysis","")
            sector_analysis=cached.get("sector_analysis",""); cached_time=cached.get("timestamp","")
        else:
            macro=get_macro(); ammc=get_ammc(); geo=get_geo(); bn=get_boursenews()
            social=get_social(); crisis=detect_crisis(macro); media=get_all_media_news()
            media["cac40_pm"]=get_cac40_premarket(macro); deep_analysis=""; sector_analysis=""; cached_time=""

        sp_c=macro.get("sp500",{}).get("c",0); sp_p=macro.get("sp500",{}).get("p",0)
        cac_c=macro.get("cac40",{}).get("c",0); dax_c=macro.get("dax",{}).get("c",0)
        nik_c=macro.get("nikkei",{}).get("c",0); sha_c=macro.get("shanghai",{}).get("c",0)
        brent_c=macro.get("brent",{}).get("c",0); brent_p=macro.get("brent",{}).get("p",0)
        gold_c=macro.get("gold",{}).get("c",0); gold_p=macro.get("gold",{}).get("p",0)
        silver_c=macro.get("silver",{}).get("c",0); phos_c=macro.get("phosphate",{}).get("c",0)
        copper_c=macro.get("copper",{}).get("c",0)
        mad=macro.get("usd_mad",10.0); eur_mad=macro.get("eur_mad",10.9)
        vix_p=macro.get("vix",{}).get("p",20); t10=macro.get("us10y",0)
        fed=macro.get("fed_rate",5.25); spread=macro.get("yield_spread",0)
        rec=macro.get("recession_risk",False); dxy_d=macro.get("dxy",{})
        dxy_c=dxy_d.get("c",0) if isinstance(dxy_d,dict) else 0

        # ── [v7.2] Bloc élasticité mines (BVC fermé → FV seule) ──────────────
        _elast_brief = render_elasticity_block(None, macro)
        # ─────────────────────────────────────────────────────────────────────

        if not deep_analysis:
            prompt=f"""BVC - Brief 07h30 - BVC ouvre dans 1h.
Alertes: {crisis} | SP500 {sp_c:+.1f}% | CAC40 {cac_c:+.1f}% | Brent {brent_c:+.1f}% | Or {gold_c:+.1f}%
Geo: {geo.get("iran_usa",[][:2])} {geo.get("fed",[][:1])}
AMMC: {[p["title"][:60] for p in ammc[:4]]}
BULLETS (max 6):
• [GEO] evenement + impact BVC
• [MARCHES] mouvement nuit + ouverture
• [COMMODITES] or/brent/argent + impact mines/OCP
• [MAD] impact importateurs vs exportateurs
• [AMMC] alerte si warning
• [SECTEURS] 2 secteurs prioritaires"""
            deep_analysis = groq_call(prompt, 500) or "Analyse indisponible"

        crisis_html = ("".join(f'<div class="imp"><span style="color:#FF4560;font-weight:900">⚠ {a}</span></div>' for a in crisis)) if crisis else ""

        def ni_geo(items, src):
            return "".join(f'<div class="ni"><span class="src" style="background:rgba(239,68,68,.15);color:#EF4444">{src}</span>{n}</div>' for n in items[:2]) if items else ""

        geo_html = ""
        if geo.get("iran_usa"):  geo_html += ni_geo(geo["iran_usa"],"Iran/USA")
        if geo.get("israel"):    geo_html += ni_geo(geo["israel"],"Israel")
        if geo.get("ukraine"):   geo_html += ni_geo(geo["ukraine"],"Ukraine")
        if geo.get("fed"):       geo_html += ni_geo(geo["fed"],"Fed")
        if geo.get("petrole"):   geo_html += ni_geo(geo["petrole"],"Petrole")
        if not geo_html: geo_html = '<div class="ni" style="color:#4B5563">Aucun evenement majeur</div>'

        ammc_html=""
        for a in ammc[:8]:
            badge_col, badge_txt = ammc_badge(a["type"])
            ammc_html+=(f'<div class="ni"><span class="src" style="background:{badge_col}18;color:{badge_col}">{"AMMC" if not badge_txt else badge_txt}</span>'
                       f'{a["title"][:110]}' + (f' <strong style="color:#C9A84C">[{a["ticker"]}]</strong>' if a.get("ticker") else "") + '</div>')
        if not ammc_html: ammc_html='<div class="ni" style="color:#4B5563">Aucune publication</div>'

        sec_html=""
        if sector_analysis:
            for line in sector_analysis.split("\n"):
                if ":"in line and len(line)>5:
                    parts=line.split(":",1); name=parts[0].strip(); rest=parts[1].strip() if len(parts)>1 else ""
                    col_s="#00C87A" if "ACHETER" in rest.upper() else ("#FF4560" if "EVITER" in rest.upper() else "#C9A84C")
                    sec_html+=f'<div class="ni"><span style="color:{col_s};font-weight:700;min-width:90px;display:inline-block">{name}</span>{rest}</div>'

        soc_html="".join(f'<div class="ni"><span class="src" style="background:rgba(139,92,246,.12);color:#8B5CF6">{s["src"]}</span>{s["t"][:120]}</div>' for s in social[:5]) or '<div class="ni" style="color:#4B5563">Aucun buzz</div>'
        bn_html ="".join(f'<div class="ni"><span class="src g">BN</span>{n}</div>' for n in bn[:4]) or '<div class="ni" style="color:#4B5563">Aucune news</div>'
        vix_col="#00C87A" if vix_p<20 else ("#C9A84C" if vix_p<30 else "#FF4560")
        vix_lab="RISK ON" if vix_p<20 else ("NEUTRE" if vix_p<30 else "RISK OFF")

        cac_pm = media.get("cac40_pm",{}) if isinstance(media,dict) else {}
        cac_sig = cac_pm.get("signal","NEUTRE")
        cac_col = "#00C87A" if cac_sig=="HAUSSIER" else ("#FF4560" if cac_sig=="BAISSIER" else "#C9A84C")
        cac_box = (f'<div class="sec" style="border-color:{cac_col}40"><div class="st" style="color:{cac_col}">CAC40 PRE-MARKET — OUVRE 1H AVANT BVC</div>'
                   f'<div style="font-size:13px;color:{cac_col};font-weight:700;margin-bottom:4px">{cac_sig}</div>'
                   f'<div style="font-size:12px;color:#E8E4D6">{cac_pm.get("impact","Donnees CAC40 indisponibles")}</div>'
                   + ("".join(f'<div class="ni"><span class="src b">CAC</span>{n}</div>' for n in cac_pm.get("news_cac",[])[:2]))
                   + '</div>') if cac_pm else ""

        trump = media.get("trump",[]) if isinstance(media,dict) else []
        trump_box = ('<div class="geo" style="border-color:rgba(245,158,11,.4)"><div class="geot" style="color:#F59E0B">TRUMP — MARKET MOVERS</div>'
                     + "".join(f'<div class="ni"><span class="src" style="background:rgba(245,158,11,.15);color:#F59E0B">TRUMP</span>{n}</div>' for n in trump[:5])
                     + '</div>') if trump else ""

        def media_block(items, src, col):
            if not items: return ""
            return "".join(f'<div class="ni"><span class="src" style="background:{col}18;color:{col}">{src}</span>{n}</div>' for n in items[:4])

        geo_intl_html = media_block(media.get("bfm",[]) if isinstance(media,dict) else [], "BFM", "#60A5FA")
        geo_intl_html += media_block(media.get("reuters_bb",[]) if isinstance(media,dict) else [], "R/BB", "#EF4444")
        geo_intl_box = ('<div class="sec"><div class="st">GEOPOLITIQUE INTL — BFM / REUTERS / BLOOMBERG</div>' + geo_intl_html + '</div>') if geo_intl_html else ""

        press_html = media_block(media.get("alphabourse",[]) if isinstance(media,dict) else [], "ALPHA", "#8B5CF6")
        press_html += media_block(media.get("leconomiste",[]) if isinstance(media,dict) else [], "ECONO", "#00C87A")
        press_html += media_block(media.get("lavieeco",[]) if isinstance(media,dict) else [], "VIEECO", "#C9A84C")
        press_box = ('<div class="sec"><div class="st">PRESSE MAROC — ALPHABOURSE / ECONOMISTE / VIE ECO</div>' + press_html + '</div>') if press_html else ""

        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="w">
<div class="hdr"><div class="logo">BARAKA</div><div class="sub">BRIEF OUVERTURE — {now}</div>
<span class="bdg g" style="border-color:rgba(0,200,122,.4);background:rgba(0,200,122,.08)">BVC OUVRE DANS 1H</span>
{f'<div style="font-size:9px;color:#4B5563;margin-top:4px">Analyse {cached_time}</div>' if cached_time else ""}</div>

{f'<div class="geo"><div class="geot">ALERTES CRISE MARCHES</div>{crisis_html}</div>' if crisis_html else ""}

{cac_box}
{trump_box}

<div class="geo"><div class="geot">RADAR GEOPOLITIQUE — IMPACT BVC</div>{geo_html}</div>
{geo_intl_box}
{press_box}

<div class="sy"><div class="syt">ANALYSE BARAKA</div><div class="sytx">{deep_analysis}</div></div>

{_elast_brief}

<div class="sec"><div class="st">MARCHES MONDIAUX — NUIT</div>
  <div class="mg" style="margin-bottom:8px">
    <div class="mb"><div class="ml">USD/MAD</div><div class="mv b">{mad}</div></div>
    <div class="mb"><div class="ml">EUR/MAD</div><div class="mv b">{eur_mad}</div></div>
    <div class="mb"><div class="ml">DXY</div><div class="mv {cv(dxy_c)}">{pv(dxy_c)}</div></div>
  </div>
  <div class="mg" style="margin-bottom:8px">
    <div class="mb"><div class="ml">S&P500</div><div class="mv {cv(sp_c)}">{sp_p:.0f}<br><span style="font-size:9px">{pv(sp_c)}</span></div></div>
    <div class="mb"><div class="ml">CAC40</div><div class="mv {cv(cac_c)}">{pv(cac_c)}</div></div>
    <div class="mb"><div class="ml">DAX</div><div class="mv {cv(dax_c)}">{pv(dax_c)}</div></div>
    <div class="mb"><div class="ml">NIKKEI</div><div class="mv {cv(nik_c)}">{pv(nik_c)}</div></div>
  </div>
  <div class="mg" style="margin-bottom:8px">
    <div class="mb"><div class="ml">OR/oz</div><div class="mv {cv(gold_c)}">{gold_p:.0f}$<br><span style="font-size:9px">{pv(gold_c)}</span></div></div>
    <div class="mb"><div class="ml">ARGENT</div><div class="mv {cv(silver_c)}">{pv(silver_c)}</div></div>
    <div class="mb"><div class="ml">BRENT</div><div class="mv {cv(brent_c)}">{brent_p:.1f}$<br><span style="font-size:9px">{pv(brent_c)}</span></div></div>
    <div class="mb"><div class="ml">CUIVRE</div><div class="mv {cv(copper_c)}">{pv(copper_c)}</div></div>
  </div>
  <div class="mg">
    <div class="mb"><div class="ml">US 10Y</div><div class="mv b">{t10:.2f}%</div></div>
    <div class="mb"><div class="ml">SPREAD</div><div class="mv {'r' if spread<0 else 'g'}">{spread:+.3f}%</div></div>
    <div class="mb"><div class="ml">FED</div><div class="mv go">{fed:.2f}%</div></div>
    <div class="mb"><div class="ml">VIX</div><div class="mv" style="color:{vix_col}">{vix_p:.1f}<br><span style="font-size:8px">{vix_lab}</span></div></div>
  </div>
</div>

{f'<div class="sec"><div class="st">ROTATION SECTORIELLE</div>{sec_html}</div>' if sec_html else ""}
<div class="sec"><div class="st">PUBLICATIONS AMMC</div>{ammc_html}</div>
<div class="sec"><div class="st">NEWS BVC — BOURSENEWS</div>{bn_html}</div>
<div class="sec"><div class="st">INTELLIGENCE SOCIALE</div>{soc_html}</div>

<div class="ft">Prochain: 12h00 — Analyse + Recommandations<br><strong class="go">BARAKA v7.2</strong></div>
</div></body></html>"""

        send_email("BARAKA — BRIEF OUVERTURE BVC 07h30", html)
    except Exception as e:
        print(f"[BRIEF] {e}")
        import traceback; traceback.print_exc()
        send_email("BARAKA — BRIEF OUVERTURE 07h30",
            f"<div style='background:#080C14;color:#E8E4D6;padding:20px;font-family:monospace'><h2 style='color:#C9A84C'>BRIEF {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</h2><p style='color:#FF4560'>{str(e)[:400]}</p></div>")

# ─── EMAIL 2: ANALYSE + RECOMMANDATIONS 11h00 UTC ────────────────────────────
def analyse_entrees():
    print("[BARAKA] === ANALYSE + ENTREES 11h00 ===")
    try:
        bvc_data=get_bvc_data(); macro=get_macro(); ammc_pubs=get_ammc()
        geo=get_geo(); now=datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        crisis=detect_crisis(macro)

        if not bvc_data:
            send_email("BARAKA — ANALYSE 11h00",
                "<div style='background:#080C14;color:#E8E4D6;padding:20px;font-family:monospace'><h2 style='color:#C9A84C'>TV Scanner indisponible</h2></div>")
            return

        exc_moves = exceptional_moves(bvc_data); used_tickers = set(e["t"] for e in exc_moves)
        sm = smart_money(bvc_data)
        mining_data = mining_intelligence(bvc_data, macro)

        geo_all = []
        for v in (geo.values() if isinstance(geo,dict) else []):
            if isinstance(v,list): geo_all += v
        geo_event = detect_geo_event(geo_all)

        global _FUNDAMENTALS
        _FUNDAMENTALS = get_fundamentals()
        trans_signals = bvc_transmission_scan(bvc_data, macro)

        reco_day  = make_reco(bvc_data, macro, ammc_pubs, "day")
        used_d    = {r["t"] for r in reco_day}
        reco_week = make_reco(bvc_data, macro, ammc_pubs, "week", exclude=used_d)
        used_w    = used_d | {r["t"] for r in reco_week}
        reco_qtr  = make_reco(bvc_data, macro, ammc_pubs, "quarter", exclude=used_w)

        update_scorecard(bvc_data); log_recos(reco_day + reco_week + reco_qtr)
        sc_stats = scorecard_stats()

        # ── [v7.2] Bloc élasticité mines (avec cours BVC réels) ──────────────
        _elast_full = render_elasticity_block(bvc_data, macro)
        # ─────────────────────────────────────────────────────────────────────

        sect_sc={}; sect_cnt={}
        for t,d in bvc_data.items():
            info=BVC.get(t,{}); sc=tech_score(d,info,macro); s=info.get("s","")
            if s not in sect_sc: sect_sc[s]=0; sect_cnt[s]=0
            sect_sc[s]+=sc; sect_cnt[s]+=1
        sect_rank=sorted([(s,round(sect_sc[s]/sect_cnt[s],1)) for s in sect_sc if sect_cnt[s]>0],key=lambda x:-x[1])

        vip_html=""
        for vt in VIP:
            vd=bvc_data.get(vt)
            if not vd: continue
            vi=BVC.get(vt,{}); vc=vd.get("close",0); vchg=vd.get("change",0)
            vrsi=vd.get("rsi",50); vsc=tech_score(vd,vi,macro)
            vvr=round(vd.get("volume",0)/max(vd.get("avg_vol",1),1),1)
            vcol="#00C87A" if vsc>=65 else ("#FF4560" if vsc<=35 else "#C9A84C")
            vip_html+=(f'<div class="vip" style="border-left:3px solid {vcol}"><div style="display:flex;justify-content:space-between">'
                       f'<span style="color:{vcol};font-weight:900;font-family:monospace;font-size:15px">{vt}</span>'
                       f'<span style="color:#9CA3AF;font-size:10px">{vi.get("n","")} | {vi.get("s","")}</span>'
                       f'<div style="text-align:right"><span style="color:#E8E4D6;font-weight:700">{vc:.2f} MAD</span>'
                       f' <span style="color:{"#00C87A" if vchg>=0 else "#FF4560"};font-size:10px">{vchg:+.1f}%</span>'
                       f'<div style="color:#9CA3AF;font-size:10px">RSI {vrsi:.0f} | Vol x{vvr} | Score {vsc}/100</div></div></div></div>')

        crisis_banner = ("".join(f'<div class="imp"><span style="color:#FF4560;font-weight:900">⚠ {a}</span></div>' for a in crisis)) if crisis else ""

        exc_html=""
        if exc_moves:
            exc_html='<div class="sec"><div class="st">MOUVEMENTS EXCEPTIONNELS (> 5%)</div>'
            for e in exc_moves[:5]:
                dc="#00C87A" if e["chg"]>0 else "#FF4560"
                exc_html+=(f'<div class="exc"><span style="color:{dc};font-weight:900;font-family:monospace">{e["t"]}</span> {e["n"]} | {e["s"]}<br>'
                           f'<span style="color:{dc};font-size:13px;font-weight:700">{e["chg"]:+.1f}% ({e["close"]:.2f} MAD)</span>'
                           f' | RSI {e["rsi"]:.0f} | Vol x{e["vr"]}<br>'
                           f'<span style="color:#C9A84C;font-size:11px">{e["note"]}</span></div>')
            exc_html+='</div>'

        sm_html=""
        if sm:
            sm_rows="".join(
                f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:11px">'
                f'<span style="color:#F59E0B;font-weight:700;font-family:monospace;min-width:70px">{s["t"]}</span>'
                f'<span style="color:#9CA3AF;flex:1">{s["n"][:20]}</span>'
                f'<span style="color:#F59E0B;font-weight:700">x{s["vr"]}</span>'
                f'<span style="color:{"#00C87A" if s["chg"]>=0 else "#FF4560"};margin-left:8px">{s["chg"]:+.1f}%</span>'
                f'<span style="color:#6B7280;margin-left:8px;font-size:10px">RSI {s["rsi"]:.0f}</span></div>'
                for s in sm[:6])
            sm_html=f'<div class="sec"><div class="st">SMART MONEY — VOL > 2.5x MOY.90J</div>{sm_rows}</div>'

        def reco_section(recs, title, icon):
            if not recs: return f'<div class="sec"><div class="st">{icon} {title}</div><div style="color:#6B7280;padding:10px">Aucun signal qualifie ce timeframe</div></div>'
            cards="".join(render_reco(rec,macro) for rec in recs)
            return f'<div class="sec"><div class="st">{icon} {title}</div>{cards}</div>'

        sect_html="".join(
            f'<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0">'
            f'<span style="color:{"#00C87A" if i<3 else "#C9A84C" if i<6 else "#6B7280"};font-size:11px">{"🟢" if i<3 else "🟡" if i<6 else "⚪"} {sn}</span>'
            f'<div style="flex:1;margin:0 8px;background:#080C14;border-radius:2px;height:4px"><div style="height:100%;border-radius:2px;width:{min(100,int(ss))}%;background:{"#00C87A" if i<3 else "#C9A84C" if i<6 else "#4B5563"}"></div></div>'
            f'<span style="color:#6B7280;font-size:10px">{ss:.0f}</span></div>'
            for i,(sn,ss) in enumerate(sect_rank[:8]))

        sp_c=macro.get("sp500",{}).get("c",0); mad=macro.get("usd_mad",10.0)

        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="w">
<div class="hdr"><div class="logo">BARAKA</div><div class="sub">ANALYSE + RECOMMANDATIONS — {now}</div>
<span class="bdg go" style="border-color:rgba(201,168,76,.4);background:rgba(201,168,76,.08)">{len(bvc_data)} TITRES — 3 HORIZONS</span></div>

<div style="display:flex;gap:8px;margin-bottom:10px">
  <div class="mb" style="flex:1"><div class="ml">S&P500</div><div class="mv {cv(sp_c)}">{pv(sp_c)}</div></div>
  <div class="mb" style="flex:1"><div class="ml">USD/MAD</div><div class="mv b">{mad}</div></div>
  <div class="mb" style="flex:1"><div class="ml">Titres actifs</div><div class="mv go">{len(bvc_data)}</div></div>
</div>

{f'<div class="geo"><div class="geot">ALERTES CRISE</div>{crisis_banner}</div>' if crisis_banner else ""}

{render_mining_block(mining_data, macro)}

{_elast_full}

{render_transmission_block(trans_signals, macro, geo_event)}

{render_fundamentals_block(_FUNDAMENTALS)}

{render_scorecard_block(sc_stats)}

{exc_html}
{sm_html}

{reco_section(reco_day,"TRADES INTRADAY — AUJOURD'HUI","⚡")}
{reco_section(reco_week,"POSITIONS SEMAINE — 7 JOURS","📅")}
{reco_section(reco_qtr,"INVESTISSEMENTS 3 MOIS","📈")}

<div class="sec"><div class="st">MOMENTUM SECTORIEL BVC</div>{sect_html}</div>

<div class="sec"><div class="st">ZOOM VIP</div>
<div style="font-size:9px;color:#F59E0B;margin-bottom:8px">Alliances • TGCC • Addoha • SGTM • Dar Saada • Akdital • Managem • SMI • CMT</div>
{vip_html or '<div style="color:#6B7280">Titres VIP non disponibles</div>'}
</div>

<div class="ft">Triggers actifs /10min | Alertes mines ±{THRESHOLD_PCT:.0f}% temps réel<br>
Prochain: 15h30 — Post-Cloture Smart Money<br><strong class="go">BARAKA v7.2</strong></div>
</div></body></html>"""

        send_email("BARAKA — ANALYSE + RECOMMANDATIONS 11h00", html)
        watchlist_clear()
        for rec in reco_day[:3]:
            watchlist_add(rec["t"],rec["close"],rec["stop"],rec["target"],"BUY" if rec["is_buy"] else "SELL")
        print(f"[WATCHLIST] {min(3,len(reco_day))} titres")
    except Exception as e:
        print(f"[ANALYSE] {e}")
        import traceback; traceback.print_exc()
        send_email("BARAKA — ANALYSE 11h00",
            f"<div style='background:#080C14;color:#E8E4D6;padding:20px;font-family:monospace'><h2 style='color:#C9A84C'>ANALYSE {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</h2><p style='color:#FF4560'>{str(e)[:400]}</p></div>")

# ─── EMAIL 3: POST-CLOTURE 14h30 UTC ─────────────────────────────────────────
def post_cloture():
    print("[BARAKA] === POST-CLOTURE 14h30 ===")
    try:
        bvc_data=get_bvc_data(); macro=get_macro(); ammc_pubs=get_ammc()
        geo=get_geo(); now=datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        sm=smart_money(bvc_data); exc=exceptional_moves(bvc_data)

        # ── [v7.2] Bloc élasticité mines (clôture de séance) ─────────────────
        _elast_close = render_elasticity_block(bvc_data, macro)
        # ─────────────────────────────────────────────────────────────────────

        top=sorted([{"t":t,"sc":tech_score(d,BVC.get(t,{}),macro),"d":d}
                    for t,d in bvc_data.items() if d.get("close") and
                    (d.get("volume",0)/(d.get("avg_vol",1) or 1))>=0.4],
                   key=lambda x:-x["sc"])[:5]

        sm_ctx="\n".join([f"{s['t']}: vol x{s['vr']}, {s['chg']:+.1f}%, RSI={s['rsi']:.0f}" for s in sm[:5]])
        exc_ctx="\n".join([f"{e['t']}: {e['chg']:+.1f}% ({e['note']})" for e in exc[:3]])
        brent_c=macro.get("brent",{}).get("c",0); gold_c=macro.get("gold",{}).get("c",0)
        silver_c=macro.get("silver",{}).get("c",0); cac_c=macro.get("cac40",{}).get("c",0)
        mad=macro.get("usd_mad",10)

        prompt=(f"Post-cloture BVC {datetime.date.today().strftime('%d/%m/%Y')}\n"
                f"SMART MONEY:\n{sm_ctx or 'Aucun mouvement anormal'}\n"
                f"MOUVEMENTS EXCEPTIONNELS:\n{exc_ctx or 'Aucun'}\n"
                f"MACRO: CAC40={cac_c:+.1f}% Brent={brent_c:+.1f}% Or={gold_c:+.1f}% Argent={silver_c:+.1f}% USD/MAD={mad}\n"
                f"TOP DEMAIN: {[x['t'] for x in top[:3]]}\n\n"
                "BULLETS UNIQUEMENT:\n"
                "• [SM] ou est alle le smart money + raison (lien macro/geo)\n"
                "• [GEO] evenement qui driveera la BVC demain matin\n"
                "• [MINES] si argent/or a bouge: SMI/MNG attendu demain (chiffre)\n"
                "• [TRADE1] ticker A: entree X MAD, cible Y MAD, stop Z MAD\n"
                "• [TRADE2] ticker B: entree X MAD, cible Y MAD, stop Z MAD\n"
                "• [RISQUE] si [scenario X] demain = ne pas entrer\n"
                "Chiffres precis. 1 ligne par bullet.")
        synth = groq_call(prompt, 500) or "Analyse en cours..."

        sm_cards=""
        for s in sm[:5]:
            t=s["t"]; info=BVC.get(t,{})
            ammc_t=[a for a in ammc_pubs if a.get("ticker")==t][:1]
            ammc_l=f'<div style="font-size:10px;color:#60A5FA">{ammc_badge(ammc_t[0]["type"])[1]} {ammc_t[0]["title"][:90]}</div>' if ammc_t else ""
            sm_cards+=(f'<div style="background:#13192A;border-radius:8px;padding:11px;margin-bottom:7px;border-left:3px solid #F59E0B">'
                       f'<div style="display:flex;justify-content:space-between"><span style="color:#F59E0B;font-weight:900;font-family:monospace;font-size:15px">{t}</span>'
                       f'<span style="color:#F59E0B;font-weight:700">VOLUME x{s["vr"]}</span></div>'
                       f'<div style="color:#9CA3AF;font-size:11px">{info.get("n","")} — {info.get("s","")}</div>'
                       f'<div style="font-size:11px;margin-top:5px;display:flex;gap:12px;flex-wrap:wrap">'
                       f'<span style="color:#6B7280">Cloture <strong style="color:#E8E4D6">{s["c"]:.2f} MAD</strong></span>'
                       f'<span style="color:{"#00C87A" if s["chg"]>=0 else "#FF4560"};font-weight:700">{s["chg"]:+.1f}%</span>'
                       f'<span style="color:#9CA3AF">RSI {s["rsi"]:.0f}</span></div>'
                       + ammc_l + '</div>')

        exc_html2=""
        if exc:
            exc_html2='<div class="sec"><div class="st">MOUVEMENTS DU JOUR > 5%</div>'
            for e in exc[:4]:
                dc="#00C87A" if e["chg"]>0 else "#FF4560"
                exc_html2+=f'<div class="exc"><span style="color:{dc};font-weight:900">{e["t"]} {e["chg"]:+.1f}%</span> — {e["n"]} | {e["note"]}</div>'
            exc_html2+='</div>'

        paris_html=""
        for item in top[:3]:
            t=item["t"]; d=item["d"]; info=BVC.get(t,{})
            close=d.get("close",0); sc=item["sc"]
            is_buy_p=d.get("macd",0)>d.get("macd_s",0) and d.get("rsi",50)<65
            col_p="#00C87A" if is_buy_p else "#FF4560"
            tgt_p=round(close*(1.05 if is_buy_p else 0.95),2); stp_p=round(close*(0.97 if is_buy_p else 1.03),2)
            vr_p=round(d.get("volume",0)/max(d.get("avg_vol",1),1),1)
            paris_html+=(f'<div style="background:#13192A;border-radius:8px;padding:9px;margin-bottom:7px;border-left:3px solid {col_p}">'
                         f'<div style="display:flex;justify-content:space-between;align-items:center">'
                         f'<span style="color:{col_p};font-weight:900;font-family:monospace">{t}</span>'
                         f'<span style="color:#9CA3AF;font-size:10px">{info.get("n","")} | Score {sc}/100 | Vol x{vr_p}</span></div>'
                         f'<div style="font-size:11px;color:#6B7280;margin-top:4px">'
                         f'Entree: <strong style="color:#E8E4D6">{close:.2f}</strong> — '
                         f'Cible: <strong style="color:#00C87A">{tgt_p:.2f}</strong> — '
                         f'Stop: <strong style="color:#FF4560">{stp_p:.2f}</strong></div></div>')

        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="w">
<div class="hdr"><div class="logo">BARAKA</div><div class="sub">POST-CLOTURE — {now}</div>
<span class="bdg or" style="border-color:rgba(245,158,11,.4);background:rgba(245,158,11,.08)">{len(sm)} SMART MONEY | {len(exc)} MOUVEMENTS EXCEPTIONNELS</span></div>

<div class="sy"><div class="syt">ANALYSE POST-CLOTURE</div><div class="sytx">{synth}</div></div>

{_elast_close}

<div class="sec"><div class="st">SMART MONEY — OU EST PARTI L'ARGENT</div>
{sm_cards or '<div style="color:#6B7280;padding:8px">Aucun mouvement institutionnel anormal</div>'}</div>

{exc_html2}

<div class="sec"><div class="st">PARIS POUR DEMAIN — NIVEAUX D'ENTREE</div>{paris_html}</div>

<div class="ft">Prochain: demain 05h00 — Pre-collecte | 07h30 — Brief<br>
<strong class="go">Baraka surveille pendant que tu dors</strong></div>
</div></body></html>"""

        send_email("BARAKA — POST-CLOTURE + SMART MONEY 14h30", html)
    except Exception as e:
        print(f"[CLOTURE] {e}")
        import traceback; traceback.print_exc()
        send_email("BARAKA — POST-CLOTURE 14h30",
            f"<div style='background:#080C14;color:#E8E4D6;padding:20px;font-family:monospace'><h2 style='color:#C9A84C'>POST-CLOTURE {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</h2><p style='color:#FF4560'>{str(e)[:400]}</p></div>")


# ─── SURVEILLANCE TRIGGERS ────────────────────────────────────────────────────
def monitor_triggers():
    if not _WATCHLIST: return
    try:
        bvc = get_bvc_data(); macro = get_macro()
        for ticker, wl in list(_WATCHLIST.items()):
            d=bvc.get(ticker)
            if not d: continue
            close=d.get("close",0); vol=d.get("volume",0)
            rsi=d.get("rsi",50); avg=d.get("avg_vol",1); ema20=d.get("ema20",0)
            triggered=[]

            if wl["side"]=="BUY":
                if close>=wl["target"]*0.998 and f"tgt_{ticker}" not in wl["fired"]:
                    wl["fired"].append(f"tgt_{ticker}")
                    triggered.append({"msg":f"CIBLE {wl['target']:.2f} ATTEINTE — PRENDRE PROFIT","urg":"CRITICAL"})
                if close<=wl["stop"]*1.002 and f"stp_{ticker}" not in wl["fired"]:
                    wl["fired"].append(f"stp_{ticker}")
                    triggered.append({"msg":f"STOP {wl['stop']:.2f} TOUCHE — SORTIR IMMEDIATEMENT","urg":"CRITICAL"})
                if avg>0 and vol/avg>3 and f"vol_{ticker}" not in wl["fired"]:
                    wl["fired"].append(f"vol_{ticker}")
                    triggered.append({"msg":f"Volume institutionnel x{vol/avg:.1f} detecte","urg":"HIGH"})

            if triggered:
                is_stop  = any("STOP" in t["msg"] for t in triggered)
                is_target= any("CIBLE" in t["msg"] for t in triggered)
                urg_col  = "#FF4560" if any(t["urg"]=="CRITICAL" for t in triggered) else "#F59E0B"
                prefix   = "STOP" if is_stop else ("CIBLE" if is_target else "TRIGGER")
                action   = ("SORTIR IMMEDIATEMENT" if is_stop else
                           f"PRENDRE PROFIT +{round((close-wl['entry'])/wl['entry']*100,1)}%" if is_target else
                           f"CONDITIONS ENTREE REUNIES {ticker}")
                cond_h   = "".join(
                    f'<div style="background:{urg_col}12;border-left:3px solid {urg_col};'
                    f'padding:10px;margin-bottom:5px;border-radius:4px">'
                    f'<span style="color:#E8E4D6;font-weight:700">{t["msg"]}</span></div>'
                    for t in triggered
                )
                html=(
                    f'<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head><body><div class="w">'
                    f'<div class="hdr" style="border-color:{urg_col}60"><div class="logo">BARAKA</div>'
                    f'<div class="sub">ALERTE {prefix} — {datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}</div></div>'
                    f'<div style="background:#13192A;border-radius:10px;padding:14px;margin-bottom:10px">'
                    f'<div style="font-size:20px;font-weight:900;color:{urg_col};font-family:monospace">{ticker}</div>'
                    f'<div style="color:#E8E4D6;font-size:18px;font-weight:900;margin-top:5px">{close:.2f} MAD | RSI {rsi:.0f}</div>'
                    f'<div style="color:#6B7280;font-size:11px">Entree: {wl["entry"]:.2f} | Stop: {wl["stop"]:.2f} | Cible: {wl["target"]:.2f}</div>'
                    f'</div>{cond_h}'
                    f'<div style="background:{urg_col}15;border:2px solid {urg_col};border-radius:8px;'
                    f'padding:14px;text-align:center;margin:10px 0">'
                    f'<div style="font-size:16px;font-weight:900;color:{urg_col}">{action}</div></div>'
                    f'<div class="ft"><strong class="go">BARAKA v7.2</strong></div></div></body></html>'
                )
                send_email(f"BARAKA — {prefix} {ticker}", html)
    except Exception as e:
        print(f"[TRIGGER] {e}")


# ─── SURVEILLANCE MARCHES + ALERTES MINES ─────────────────────────────────────
def monitor_markets():
    """
    Alerte si marché franchit seuil ±0.2 / 0.5 / 1 / 2%.
    [v7.2] Intègre aussi les alertes palier ±1% XAG/XAU → SMI/MNG théorique.
    """
    global _MKT_PREV
    try:
        macro = get_macro()
        markets = {
            "SP500": macro.get("sp500",{}),
            "Brent": macro.get("brent",{}),
            "Or":    macro.get("gold",{}),
            "VIX":   macro.get("vix",{}),
        }
        thresholds = [0.2, 0.5, 1.0, 2.0]
        alerts = []

        for name, d in markets.items():
            if not d or d.get("c") == 0: continue
            chg  = d.get("c", 0)
            prev = _MKT_PREV.get(name, chg)
            for th in thresholds:
                if chg <= -th and prev > -th:
                    alerts.append({"name":name,"chg":chg,"th":-th,"col":"#FF4560",
                                   "msg":f"{name} {chg:.2f}% sous -{th}%","critical":th>=1})
                    break
                elif chg >= th and prev < th:
                    alerts.append({"name":name,"chg":chg,"th":th,"col":"#00C87A",
                                   "msg":f"{name} +{chg:.2f}% depasse +{th}%","critical":name=="Brent" and th>=2})
                    break
                elif chg > -th*0.3 and prev <= -th:
                    alerts.append({"name":name,"chg":chg,"th":0,"col":"#F59E0B",
                                   "msg":f"{name} rebond {chg:.2f}% (etait {prev:.2f}%)","critical":False})
                    break
            _MKT_PREV[name] = chg

        # ── [v7.3] ALERTES MINES — palier ±1% XAG/XAU (séance BVC uniquement) ─
        # Session BVC : 9h00–15h30 Casa = 8h00–14h30 UTC
        _now_utc   = datetime.datetime.utcnow()
        _h, _m     = _now_utc.hour, _now_utc.minute
        _in_session = (8 <= _h < 14) or (_h == 14 and _m < 30)
        try:
            ag_now  = macro.get("silver",{}).get("p",0) if isinstance(macro.get("silver",{}),dict) else 0
            au_now  = macro.get("gold",{}).get("p",0)   if isinstance(macro.get("gold",{}),dict)   else 0
            cu_now  = macro.get("copper",{}).get("p",0) if isinstance(macro.get("copper",{}),dict) else 0
            zn_now  = macro.get("zinc",{}).get("p",0)   if isinstance(macro.get("zinc",{}),dict)   else 0
            if _in_session and (ag_now > 0 or au_now > 0):
                mine_alerts = check_alerts(ag_now, au_now,
                                           copper_now=cu_now, zinc_now=zn_now)
                if mine_alerts:
                    m_subj, m_body = format_alert(mine_alerts)
                    m_html = (
                        f'<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>'
                        f'<body><div class="w">'
                        f'<div class="hdr" style="border-color:rgba(56,189,248,.5)">'
                        f'<div class="logo">BARAKA</div>'
                        f'<div class="sub">ALERTE MINES — {datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}</div>'
                        f'<span class="bdg" style="color:#38bdf8;border-color:#38bdf840">PALIER ±1% METAUX</span>'
                        f'</div>'
                        f'<pre style="background:#0F1520;color:#E8E4D6;padding:16px;'
                        f'border-radius:10px;font-family:monospace;font-size:12px;'
                        f'line-height:1.8;white-space:pre-wrap">{m_body}</pre>'
                        f'<div class="ft"><strong class="go">BARAKA v7.2 — Alerte Mines Temps Réel</strong></div>'
                        f'</div></body></html>'
                    )
                    send_email(m_subj, m_html)
                    print(f"[MINES ALERT] {m_subj}")
        except Exception as me:
            print(f"[MINES ALERT] {me}")
        # ─────────────────────────────────────────────────────────────────────

        if alerts:
            impacts = []
            brent_c = macro.get("brent",{}).get("c",0)
            gold_c  = macro.get("gold",{}).get("c",0)
            sp_c    = macro.get("sp500",{}).get("c",0)
            vix_p   = macro.get("vix",{}).get("p",20)
            if brent_c > 2:  impacts.append(f"Brent +{brent_c:.1f}% → inflation Maroc → CTM/TMA/Agro sous pression")
            if brent_c < -2: impacts.append(f"Brent {brent_c:.1f}% → soulagement inflation → positif distribution")
            if gold_c < -1.5:impacts.append(f"Or {gold_c:.1f}% → deleveraging → Managem/SMI en baisse")
            if gold_c > 2:   impacts.append(f"Or +{gold_c:.1f}% → refuge → Managem/SMI en hausse")
            if sp_c < -1:    impacts.append(f"SP500 {sp_c:.1f}% → risk off → BVC ouverture negative, correlation 0.7")
            if vix_p > 25:   impacts.append(f"VIX={vix_p:.0f} → panique → flux vers BDT Maroc")

            ah = "".join(
                f'<div class="imp"><span style="color:{a["col"]};font-weight:900">'
                f'{"!" if a["critical"] else ""} {a["msg"]}</span></div>'
                for a in alerts
            )
            ih = "".join(f'<div style="font-size:11px;color:#9CA3AF;padding:2px 0">• {i}</div>' for i in impacts)
            sp_p = macro.get("sp500",{}).get("p",0)
            br_p = macro.get("brent",{}).get("p",0)
            go_p = macro.get("gold",{}).get("p",0)
            mad  = macro.get("usd_mad",10)
            has_crit = any(a["critical"] for a in alerts)
            urg_col  = "#FF4560" if has_crit else "#F59E0B"

            html = (
                f'<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head><body><div class="w">'
                f'<div class="hdr" style="border-color:{urg_col}60"><div class="logo">BARAKA</div>'
                f'<div class="sub">ALERTE MARCHE — {datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}</div>'
                f'<span class="bdg" style="color:{urg_col};border-color:{urg_col}50">{"CRITIQUE" if has_crit else "SIGNAL"}</span></div>'
                f'<div class="geo" style="border-color:{urg_col}40"><div class="geot">MOUVEMENTS DETECTES</div>{ah}</div>'
                f'<div class="sec"><div class="st">NIVEAUX TEMPS REEL</div><div class="mg">'
                f'<div class="mb"><div class="ml">SP500</div><div class="mv {cv(sp_c)}">{sp_p:.0f}<br><span style="font-size:9px">{pv(sp_c)}</span></div></div>'
                f'<div class="mb"><div class="ml">BRENT</div><div class="mv {cv(brent_c)}">{br_p:.1f}$<br><span style="font-size:9px">{pv(brent_c)}</span></div></div>'
                f'<div class="mb"><div class="ml">OR</div><div class="mv {cv(gold_c)}">{go_p:.0f}$<br><span style="font-size:9px">{pv(gold_c)}</span></div></div>'
                f'<div class="mb"><div class="ml">USD/MAD</div><div class="mv b">{mad}</div></div>'
                f'</div></div>'
                + (f'<div class="sec"><div class="st">IMPACT SUR LA BVC</div>{ih}</div>' if ih else "")
                + f'<div class="ft"><strong class="go">BARAKA v7.2 — Alerte Temps Réel</strong></div>'
                f'</div></body></html>'
            )
            names = ", ".join(a["name"] for a in alerts[:2])
            send_email(f"BARAKA — {'CRITIQUE' if has_crit else 'SIGNAL'} MARCHE: {names}", html)
            print(f"[MKT ALERT] {[a['msg'] for a in alerts]}")

    except Exception as e:
        print(f"[MKT MONITOR] {e}")


# ─── FLASK ────────────────────────────────────────────────────────────────────
def start_flask():
    try:
        from flask import Flask
        app = Flask(__name__)
        JOBS = {
            "brief":      brief_ouverture,
            "analyse":    analyse_entrees,
            "cloture":    post_cloture,
            "precollect": pre_collect,
        }

        @app.route("/")
        def idx():
            return f"BARAKA v7.2 ACTIVE {datetime.datetime.now().strftime('%H:%M:%S')}", 200

        @app.route("/ping")
        def ping():
            return "OK", 200

        @app.route("/trigger/<name>")
        def trigger(name):
            if name not in JOBS: return f"Options: {list(JOBS.keys())}", 400
            threading.Thread(target=JOBS[name], daemon=True).start()
            return f"'{name}' declenche", 200

        @app.route("/watchlist")
        def wl():
            if not _WATCHLIST: return "Watchlist vide", 200
            out = [f"BARAKA WATCHLIST {datetime.datetime.now().strftime('%H:%M')}\n"]
            for tk, w in _WATCHLIST.items():
                out.append(f"{tk}: {w['entry']:.2f} stop={w['stop']:.2f} cible={w['target']:.2f}\n")
            return "".join(out), 200, {"Content-Type": "text/plain"}

        @app.route("/check")
        def check():
            threading.Thread(target=monitor_triggers, daemon=True).start()
            return "Verification triggers", 200

        @app.route("/market")
        def mkt():
            threading.Thread(target=monitor_markets, daemon=True).start()
            return "Verification marches", 200

        @app.route("/mines")
        def mines():
            """Force un check alerte mines maintenant."""
            threading.Thread(target=monitor_markets, daemon=True).start()
            return "Check mines + marches lance", 200

        port = int(os.environ.get("PORT", 8080))
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"[FLASK] {e}")


# ─── SCHEDULER ────────────────────────────────────────────────────────────────
def run_scheduler():
    print("""
+===================================================+
|  BARAKA v7.2 - BVC HEDGE FUND INTELLIGENCE        |
+===================================================+
|  05:00 UTC (06:00 Casa) → Pre-collecte profonde   |
|  07:30 UTC (08:30 Casa) → Brief Ouverture         |
|  11:00 UTC (12:00 Casa) → Analyse + Recos         |
|  14:30 UTC (15:30 Casa) → Post-Cloture            |
|  /5 min  (6h-23h UTC)  → Alertes marches + MINES |
|  /10 min (9h-15h UTC)  → Triggers positions      |
+===================================================+
|  NOUVEAU v7.2: Élasticité SMI/MNG dans chaque     |
|  email. Alertes ±1% XAG/XAU en temps réel.        |
+===================================================+
    """)
    threading.Thread(target=start_flask, daemon=True).start()
    fired = {}

    while True:
        try:
            now   = datetime.datetime.utcnow()
            today = str(now.date())
            h, m, wd = now.hour, now.minute, now.weekday()

            # Reset quotidien minuit UTC
            if h == 0 and m == 0:
                fired = {}
                watchlist_clear()

            if wd < 5:  # Lun-Ven uniquement
                if h == 5 and 0 <= m < 15 and f"pre_{today}" not in fired:
                    fired[f"pre_{today}"] = True
                    threading.Thread(target=pre_collect, daemon=True).start()

                elif h == 7 and 30 <= m < 45 and f"brief_{today}" not in fired:
                    fired[f"brief_{today}"] = True
                    threading.Thread(target=brief_ouverture, daemon=True).start()

                elif h == 11 and 0 <= m < 15 and f"analyse_{today}" not in fired:
                    fired[f"analyse_{today}"] = True
                    threading.Thread(target=analyse_entrees, daemon=True).start()

                elif h == 14 and 30 <= m < 45 and f"cloture_{today}" not in fired:
                    fired[f"cloture_{today}"] = True
                    threading.Thread(target=post_cloture, daemon=True).start()

                # Triggers positions: toutes les 10 min, session BVC (9h-15h UTC)
                if 9 <= h < 15 and m % 10 == 0 and _WATCHLIST:
                    tk = f"trig_{today}_{h}_{m}"
                    if tk not in fired:
                        fired[tk] = True
                        threading.Thread(target=monitor_triggers, daemon=True).start()

            # Alertes marchés + mines: toutes les 5 min, 6h-23h UTC (y compris weekend pour metaux)
            if 6 <= h < 23 and m % 5 == 0:
                mk = f"mkt_{today}_{h}_{m}"
                if mk not in fired:
                    fired[mk] = True
                    threading.Thread(target=monitor_markets, daemon=True).start()

        except Exception as e:
            print(f"[SCHEDULER] {e}")

        time.sleep(30)


if __name__ == "__main__":
    run_scheduler()
