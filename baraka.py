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

# ─── CACHE SYSTÈME ─────────────────────────────────────────────────────────────
_CACHE = {}  # Cache en mémoire (persiste dans le processus)

def cache_set(key, value):
    _CACHE[key] = {"data": value, "ts": datetime.datetime.utcnow()}

def cache_get(key, max_age_min=120):
    """Recupere du cache si pas trop vieux"""
    if key not in _CACHE: return None
    age = (datetime.datetime.utcnow() - _CACHE[key]["ts"]).total_seconds() / 60
    return _CACHE[key]["data"] if age < max_age_min else None

# ─── WATCHLIST & TRIGGER MONITORING ──────────────────────────────────────────

_WATCHLIST = {}  # {ticker: {condition, entry, stop, target, fired, side}}

def watchlist_add(ticker, conditions, entry, stop, target, side="BUY"):
    """Ajoute un titre à surveiller avec ses conditions de trigger"""
    _WATCHLIST[ticker] = {
        "conditions": conditions,   # liste de conditions à surveiller
        "entry": entry,
        "stop": stop,
        "target": target,
        "side": side,
        "fired": [],                # conditions déjà déclenchées
        "added_at": datetime.datetime.utcnow().isoformat(),
        "name": BVC.get(ticker, {}).get("n", ticker),
        "sector": BVC.get(ticker, {}).get("s", ""),
    }
    print(f"[WATCHLIST] {ticker} ajouté — {len(conditions)} conditions")

def watchlist_clear():
    """Efface la watchlist (appelé chaque matin)"""
    _WATCHLIST.clear()
    print("[WATCHLIST] Réinitialisé")

def _check_single_trigger(ticker, wl, d):
    """
    Vérifie les conditions de trigger pour un titre.
    Retourne la liste des conditions déclenchées (nouvelles seulement).
    """
    if not d or not d.get("close"): return []
    triggered = []
    close  = d.get("close", 0)
    vol    = d.get("volume", 0)
    rsi    = d.get("rsi", 50)
    macd   = d.get("macd", 0)
    macd_s = d.get("macd_s", 0)
    ema20  = d.get("ema20", 0)
    ema50  = d.get("ema50", 0)
    avg    = d.get("avg90", 0) or d.get("avg30", 0) or BVC.get(ticker, {}).get("v", 1)

    entry  = wl["entry"]
    stop   = wl["stop"]
    target = wl["target"]
    side   = wl["side"]

    cond_key_base = lambda c: f"{ticker}_{c}"

    # ── CONDITIONS DE DÉCLENCHEMENT ──────────────────────────────
    if side == "BUY":
        # 1. Cassure au-dessus de l'EMA20
        if ema20 > 0 and close > ema20 * 1.001:
            ck = cond_key_base("above_ema20")
            if ck not in wl["fired"]:
                triggered.append({"key":ck, "msg":f"✅ Cours ({close:.2f}) au-dessus EMA20 ({ema20:.2f})", "urgency":"HIGH"})

        # 2. RSI en zone de rebond
        if rsi < 32:
            ck = cond_key_base("rsi_oversold")
            if ck not in wl["fired"]:
                triggered.append({"key":ck, "msg":f"📉 RSI={rsi:.0f} — zone de survente extrême, rebond probable", "urgency":"HIGH"})

        # 3. Volume institutionnel
        if avg > 0 and vol > avg * 2.5:
            ck = cond_key_base("vol_spike")
            if ck not in wl["fired"]:
                triggered.append({"key":ck, "msg":f"🏦 Volume institutionnel x{vol/avg:.1f} — accumulation détectée", "urgency":"HIGH"})

        # 4. MACD croisement haussier
        if macd > macd_s and macd > 0:
            ck = cond_key_base("macd_cross_bull")
            if ck not in wl["fired"]:
                triggered.append({"key":ck, "msg":f"⚡ MACD croise à la hausse en territoire positif", "urgency":"MEDIUM"})

        # 5. Stop touché (sortir!)
        if close <= stop * 1.002:
            ck = cond_key_base("stop_hit")
            if ck not in wl["fired"]:
                triggered.append({"key":ck, "msg":f"🛑 STOP TOUCHÉ! Cours={close:.2f} ≤ Stop={stop:.2f} — SORTIR IMMÉDIATEMENT", "urgency":"CRITICAL"})

        # 6. Cible atteinte
        if close >= target * 0.998:
            ck = cond_key_base("target_hit")
            if ck not in wl["fired"]:
                triggered.append({"key":ck, "msg":f"🎯 CIBLE ATTEINTE! Cours={close:.2f} ≥ Cible={target:.2f} — PRENDRE PROFIT", "urgency":"CRITICAL"})

    else:  # SELL
        if close >= stop * 0.998:
            ck = cond_key_base("stop_hit_short")
            if ck not in wl["fired"]:
                triggered.append({"key":ck, "msg":f"🛑 STOP COURT TOUCHÉ! Couvrir la position", "urgency":"CRITICAL"})
        if close <= target * 1.002:
            ck = cond_key_base("target_hit_short")
            if ck not in wl["fired"]:
                triggered.append({"key":ck, "msg":f"🎯 CIBLE COURT ATTEINTE — Racheter et prendre profit", "urgency":"CRITICAL"})

    return triggered


def _send_trigger_alert(ticker, wl, triggered_conditions, d, macro):
    """Envoie un email d'alerte immédiat pour un trigger déclenché"""
    now  = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    name = wl.get("name", ticker)
    sect = wl.get("sector", "")
    close = d.get("close", 0)
    rsi   = d.get("rsi", 50)
    vol   = d.get("volume", 0)
    avg   = d.get("avg90", 0) or BVC.get(ticker, {}).get("v", 1)

    # Niveau d'urgence max
    urgencies = [c.get("urgency","MEDIUM") for c in triggered_conditions]
    max_urg   = "CRITICAL" if "CRITICAL" in urgencies else ("HIGH" if "HIGH" in urgencies else "MEDIUM")
    urg_color = "#FF4560" if max_urg=="CRITICAL" else ("#F59E0B" if max_urg=="HIGH" else "#C9A84C")

    cond_html = "".join(
        f'<div style="background:{("#FF4560" if c["urgency"]=="CRITICAL" else "#F59E0B")}15;border-left:3px solid {("#FF4560" if c["urgency"]=="CRITICAL" else "#F59E0B")};border-radius:4px;padding:10px;margin-bottom:6px;">'
        f'<div style="font-size:13px;color:#E8E4D6;font-weight:700">{c["msg"]}</div>'
        f'</div>'
        for c in triggered_conditions
    )

    # Action à prendre
    is_stop    = any("STOP" in c["msg"] for c in triggered_conditions)
    is_target  = any("CIBLE" in c["msg"] for c in triggered_conditions)
    is_entry   = any(c.get("urgency")=="HIGH" for c in triggered_conditions) and not is_stop

    if is_stop:
        action_html = f'<div style="background:rgba(255,69,96,.15);border:2px solid #FF4560;border-radius:8px;padding:14px;margin:10px 0;text-align:center;"><div style="font-size:16px;font-weight:900;color:#FF4560">⛔ ACTION IMMÉDIATE</div><div style="font-size:14px;color:#FF4560;margin-top:6px">VENDRE {ticker} AU MARCHÉ — STOP DÉCLENCHÉ</div></div>'
    elif is_target:
        action_html = f'<div style="background:rgba(0,200,122,.1);border:2px solid #00C87A;border-radius:8px;padding:14px;margin:10px 0;text-align:center;"><div style="font-size:16px;font-weight:900;color:#00C87A">🎯 PRENDRE PROFIT</div><div style="font-size:14px;color:#00C87A;margin-top:6px">VENDRE {ticker} — CIBLE ATTEINTE +{round((close-wl["entry"])/wl["entry"]*100,1)}%</div></div>'
    else:
        action_html = f'<div style="background:rgba(245,158,11,.1);border:2px solid #F59E0B;border-radius:8px;padding:14px;margin:10px 0;text-align:center;"><div style="font-size:16px;font-weight:900;color:#F59E0B">🔔 CONDITIONS REMPLIES</div><div style="font-size:14px;color:#F59E0B;margin-top:6px">ENTRER sur {ticker} à {close:.2f} MAD — Confirmer</div></div>'

    sp_c = macro.get("sp500", {}).get("c", 0)
    cac_c = macro.get("cac40", {}).get("c", 0)

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>body{{background:#0A0D14;color:#E8E4D6;font-family:Courier New,monospace;margin:0;padding:0}}.w{{max-width:640px;margin:0 auto;padding:16px}}</style>
</head><body><div class="w">

<div style="background:#111520;border:2px solid {urg_color};border-radius:12px;padding:18px;text-align:center;margin-bottom:14px">
  <div style="font-size:24px;font-weight:900;color:#C9A84C;letter-spacing:6px">BARAKA</div>
  <div style="font-size:10px;color:#6B7280;margin-top:3px">ALERTE TRIGGER — {now}</div>
  <div style="display:inline-block;background:{urg_color}15;border:1px solid {urg_color};color:{urg_color};padding:4px 14px;border-radius:20px;font-size:11px;margin-top:8px">
    {'🚨 CRITIQUE' if max_urg=='CRITICAL' else ('⚡ HAUTE PRIORITÉ' if max_urg=='HIGH' else '🔔 SIGNAL')}
  </div>
</div>

<div style="background:#171C2C;border-radius:10px;padding:14px;margin-bottom:12px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
    <div>
      <div style="font-size:22px;font-weight:900;color:{urg_color};font-family:monospace">{ticker}</div>
      <div style="font-size:11px;color:#9CA3AF">{name} — {sect}</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:20px;font-weight:900;color:#E8E4D6">{close:.2f} MAD</div>
      <div style="font-size:11px;color:#9CA3AF">RSI {rsi:.0f} | Vol x{round(vol/avg,1) if avg>0 else 'N/A'}</div>
    </div>
  </div>

  <div style="display:flex;gap:8px;font-size:11px;margin-bottom:8px">
    <span style="color:#6B7280">Entrée: <strong style="color:#E8E4D6">{wl['entry']:.2f}</strong></span>
    <span style="color:#6B7280">Stop: <strong style="color:#FF4560">{wl['stop']:.2f}</strong></span>
    <span style="color:#6B7280">Cible: <strong style="color:#00C87A">{wl['target']:.2f}</strong></span>
  </div>
</div>

<div style="margin-bottom:12px">
  <div style="font-size:10px;color:{urg_color};letter-spacing:3px;text-transform:uppercase;margin-bottom:8px">CONDITIONS DÉCLENCHÉES</div>
  {cond_html}
</div>

{action_html}

<div style="background:#111520;border:1px solid rgba(201,168,76,.2);border-radius:8px;padding:10px;margin-bottom:12px">
  <div style="font-size:9px;color:#6B7280;margin-bottom:5px">CONTEXTE MARCHÉ</div>
  <div style="font-size:11px;color:#9CA3AF">
    S&P500: <span style="color:{'#00C87A' if sp_c>=0 else '#FF4560'}">{sp_c:+.2f}%</span> | 
    CAC40: <span style="color:{'#00C87A' if cac_c>=0 else '#FF4560'}">{cac_c:+.2f}%</span>
  </div>
</div>

<div style="text-align:center;font-size:10px;color:#4B5563;margin-top:12px">
  Baraka surveille en continu — Alerte en temps réel<br>
  <strong style="color:#C9A84C">Confirmez toujours avant d'agir</strong>
</div>

</div></body></html>"""

    subj_prefix = "🚨 STOP DÉCLENCHÉ" if is_stop else ("🎯 CIBLE ATTEINTE" if is_target else "⚡ TRIGGER ACTIF")
    send_email(f"BARAKA — {subj_prefix} — {ticker}", html)
    print(f"[WATCHLIST] Alerte envoyée: {ticker} — {[c['msg'][:40] for c in triggered_conditions]}")


def monitor_triggers():
    """
    Surveillance des triggers toutes les 10 minutes.
    Appelé pendant les heures de marché (08:00-15:30 UTC = 09:00-16:30 Casa).
    """
    if not _WATCHLIST:
        return  # Rien à surveiller

    print(f"[WATCHLIST] Vérification {len(_WATCHLIST)} titre(s)...")
    try:
        bvc_data = get_bvc_data()
        macro    = get_macro()

        for ticker, wl in list(_WATCHLIST.items()):
            d = bvc_data.get(ticker)
            if not d: continue

            triggered = _check_single_trigger(ticker, wl, d)
            if triggered:
                # Marquer comme déclenchés
                for t in triggered:
                    wl["fired"].append(t["key"])
                # Envoyer alerte
                _send_trigger_alert(ticker, wl, triggered, d, macro)

    except Exception as e:
        print(f"[WATCHLIST] Erreur: {e}")


# ─── ELITE ANALYTICS ENGINE ───────────────────────────────────────────────────

def extract_pdf_financials(url, title):
    """
    Lit un PDF AMMC et extrait les chiffres financiers clés.
    Retourne : CA, Résultat Net, variation, EPS, dividende.
    """
    try:
        import pdfplumber
        r = requests.get(url, headers=HEADERS, **R)
        if r.status_code != 200: return {}
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            text = ""
            for page in pdf.pages[:8]:
                t = page.extract_text()
                if t: text += t + "\n"
        if len(text) < 100: return {}

        # Groq lit le PDF et extrait les chiffres
        prompt = f"""Analyse ce document financier marocain et extrait les données clés.
Document: {title}
Contenu (premiers 3000 chars):
{text[:3000]}

Réponds UNIQUEMENT en JSON valide:
{{"type": "rapport_annuel|semestriel|trimestriel|autre",
  "periode": "S1 2026|T1 2026|annuel 2025|...",
  "ca_mdh": 0.0,
  "ca_variation_pct": 0.0,
  "resultat_net_mdh": 0.0,
  "resultat_variation_pct": 0.0,
  "marge_nette_pct": 0.0,
  "eps_mad": 0.0,
  "dividende_mad": 0.0,
  "vs_previsions": "conforme|au_dessus|en_dessous|inconnu",
  "signal": "ACHAT_FORT|ACHAT|NEUTRE|VENTE|VENTE_FORTE",
  "resume": "une phrase maximum",
  "catalyseur": "point positif principal",
  "risque": "point negatif principal"}}
Si une valeur est inconnue, mets 0 ou null."""

        raw = groq_call(prompt, 500)
        clean = raw.replace("```json","").replace("```","").strip()
        start = clean.find("{")
        end   = clean.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(clean[start:end])
    except Exception as e:
        print(f"[PDF] {e}")
    return {}


def calculate_sector_momentum(bvc_data, macro):
    """
    Calcule le momentum de chaque secteur BVC.
    Score sectoriel = moyenne des scores des titres du secteur + bonus macro.
    Retourne le ranking des secteurs.
    """
    sector_scores = {}
    sector_counts = {}

    for t, d in bvc_data.items():
        info = BVC.get(t, {})
        sect = info.get("s","")
        sc   = score(d, info, macro)
        if sect not in sector_scores:
            sector_scores[sect] = 0
            sector_counts[sect] = 0
        sector_scores[sect] += sc
        sector_counts[sect] += 1

    # Moyenne par secteur
    sector_avg = {
        s: round(sector_scores[s]/sector_counts[s], 1)
        for s in sector_scores if sector_counts[s] > 0
    }

    # Ranking
    ranked = sorted(sector_avg.items(), key=lambda x: -x[1])
    return ranked


def detect_technical_pattern(d, info):
    """
    Détecte les patterns techniques clés.
    Retourne une liste de patterns détectés.
    """
    patterns = []
    close  = d.get("close", 0)
    ema20  = d.get("ema20", 0)
    ema50  = d.get("ema50", 0)
    ema200 = d.get("ema200", 0)
    rsi    = d.get("rsi", 50)
    macd   = d.get("macd", 0)
    macd_s = d.get("macd_s", 0)
    adx    = d.get("adx", 0)
    high   = d.get("high", 0)
    low    = d.get("low", 0)
    vol    = d.get("volume", 0)
    avg    = d.get("avg90", 0) or d.get("avg30", 0) or info.get("v", 1)

    # Golden Cross
    if ema20 > ema50 and close > ema20: patterns.append("🟡 Golden Cross EMA20/50")
    # Death Cross
    if ema20 < ema50 and close < ema20: patterns.append("💀 Death Cross EMA20/50")
    # Breakout EMA200
    if ema200 > 0 and close > ema200 and close < ema200 * 1.02:
        patterns.append("🚀 Breakout au-dessus EMA200")
    # Survente RSI
    if rsi < 30: patterns.append(f"📉 Survente RSI={rsi:.0f} — zone rebond")
    if rsi < 25: patterns.append(f"🔥 Survente EXTRÊME RSI={rsi:.0f}")
    # Surachat RSI
    if rsi > 70: patterns.append(f"📈 Surachat RSI={rsi:.0f} — attention")
    # MACD croisement haussier
    if macd > macd_s and macd_s < 0: patterns.append("⚡ MACD croisement haussier (zone négative)")
    # Tendance forte ADX
    if adx > 35: patterns.append(f"💪 Tendance forte ADX={adx:.0f}")
    # Volume institutionnel
    if avg > 0 and vol/avg > 3: patterns.append(f"🏦 Volume institutionnel x{vol/avg:.1f}")
    # Near support EMA50
    if ema50 > 0 and abs(close-ema50)/ema50 < 0.01:
        patterns.append("🎯 Cours sur support EMA50")

    return patterns[:4]  # Max 4 patterns


def kelly_position_size(win_rate, rr_ratio, portfolio_pct=True):
    """
    Kelly Criterion : taille optimale de position.
    f* = (p * (b+1) - 1) / b
    p = win_rate, b = R/R ratio
    Retourne le % recommandé du capital (max 20% par trade).
    """
    if rr_ratio <= 0 or win_rate <= 0: return 2.0
    p = win_rate / 100  # Convertir en décimal
    b = rr_ratio
    kelly = (p * (b + 1) - 1) / b
    # Demi-Kelly pour prudence, cap à 20%
    half_kelly = max(0, min(kelly / 2 * 100, 20))
    return round(half_kelly, 1)


def generate_trigger_conditions(d, info, macro, is_buy):
    """
    Génère des conditions d'entrée précises et actionnables.
    Exemple: "Entre si ATW casse 487 MAD avec volume > 50K titres"
    """
    close  = d.get("close", 0)
    high   = d.get("high", close)
    low    = d.get("low", close)
    ema20  = d.get("ema20", 0)
    ema50  = d.get("ema50", 0)
    rsi    = d.get("rsi", 50)
    avg    = d.get("avg90", 0) or info.get("v", 1)
    vol_trigger = int(avg * 1.5)

    triggers = []
    alarms   = []

    if is_buy:
        # Trigger d'entrée
        if close > ema20:
            triggers.append(f"Prix au-dessus EMA20 ({ema20:.2f}) — entrer maintenant au marché")
        else:
            triggers.append(f"Attendre cassure de EMA20 ({ema20:.2f} MAD) en clôture")

        if avg > 0:
            triggers.append(f"Confirmer avec volume > {vol_trigger:,} titres")

        if rsi > 45:
            triggers.append(f"RSI={rsi:.0f} — entrer maintenant (momentum positif)")
        else:
            triggers.append(f"RSI={rsi:.0f} en zone de retournement — entrée progressive")

        # Conditions d'alarme (= ne pas entrer)
        alarms.append(f"Si cours casse sous {low:.2f} MAD (plus bas du jour) = sortir")
        alarms.append(f"Si RSI dépasse 72 avant entrée = attendre consolidation")
        if macro.get("cac40",{}).get("c",0) < -1.5:
            alarms.append("Si CAC40 baisse > 1.5% = reporter l'entrée")

    else:  # Vente
        triggers.append(f"Vendre sous EMA20 ({ema20:.2f} MAD)")
        triggers.append(f"Confirmer avec volume > {vol_trigger:,} titres")
        alarms.append(f"Si rebond au-dessus {high:.2f} MAD = couvrir les ventes")

    return triggers[:3], alarms[:3]


def bull_base_bear_scenarios(close, is_buy, sc, macro):
    """
    3 scénarios probabilisés pour chaque recommandation.
    Basé sur le score et le contexte macro.
    """
    # Probabilités basées sur le score
    if sc >= 80:
        p_bull, p_base, p_bear = 45, 40, 15
    elif sc >= 65:
        p_bull, p_base, p_bear = 30, 45, 25
    else:
        p_bull, p_base, p_bear = 20, 45, 35

    # Ajustement macro
    cac_c = macro.get("cac40", {}).get("c", 0)
    if cac_c > 1: p_bull += 5; p_bear -= 5
    if cac_c < -1: p_bull -= 5; p_bear += 5

    mult = 1 if is_buy else -1

    return {
        "bull":  {"pct": p_bull,  "target": round(close * (1 + mult*0.08), 2), "label": "Scénario haussier"},
        "base":  {"pct": p_base,  "target": round(close * (1 + mult*0.05), 2), "label": "Scénario de base"},
        "bear":  {"pct": p_bear,  "target": round(close * (1 - mult*0.03), 2), "label": "Scénario baissier"},
    }


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
    # ── ZOOM VIP QUOTIDIEN ─────────────────────────────────────────────────────
    "ALLIANCES":{"n":"Alliances Developpement", "s":"Immobilier",  "v":8000,  "mc":"mid"},
    "TGCC":     {"n":"TGCC",                    "s":"Construction","v":5000,  "mc":"mid"},
    "SGTM":     {"n":"SGTM",                    "s":"Construction","v":3000,  "mc":"small"},
    "DAR":      {"n":"Res. Dar Saada",          "s":"Immobilier",  "v":4000,  "mc":"small"},
    "AKDITAL":  {"n":"Akdital",                 "s":"Sante",       "v":4500,  "mc":"mid"},
    # ── MINES & MÉTAUX PRÉCIEUX ───────────────────────────────────────────────
    "MANAGEM":  {"n":"Managem",                 "s":"Mines",       "v":12000, "mc":"mid"},
    "SMI":      {"n":"SMI (Argent)",            "s":"Mines",       "v":8000,  "mc":"small"},
    "CMT":      {"n":"CMT (Zinc/Plomb)",        "s":"Mines",       "v":5000,  "mc":"small"},
}

# Titres VIP — zoom quotidien approfondi
VIP_TICKERS = ["ALLIANCES","ALM","TGCC","ADH","SGTM","DAR","AKDITAL","MANAGEM","SMI","CMT"]
# Alias TV scanner → BVC key
TV_ALIASES  = {"ALM":"ALLIANCES","ADH":"ADDOHA"}

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

# ─── PRÉ-COLLECTE 06h00 ──────────────────────────────────────────────────────
def pre_collect():
    """
    Collecte et analyse profonde a 06h00 pendant que tu dors.
    Groq analyse avec 2x plus de temps et de tokens.
    Brief de 08h30 part en 5 secondes avec analyse deja mûrie.
    """
    print("[BARAKA] === PRÉ-COLLECTE 06h00 ===")
    try:
        macro   = get_macro()
        ammc    = get_ammc_pubs()
        bn      = boursenews()
        tg      = telegram_bvc()
        bkam    = bkam_news()
        correl  = get_correlations_context(macro)
        # Commodites et ODC dans la pre-collecte
        comm_pre = get_commodities_maroc()
        odc_pre  = get_office_changes()
        n_bvc   = gnews("Bourse Casablanca 2026", 5)
        n_mac   = gnews("taux Fed BCE Banque centrale mondiale 2026", 4)
        n_geo   = gnews("guerre conflit geopolitique mondial impact economie 2026", 4)
        n_usa   = gnews("Federal Reserve inflation USA economie 2026", 4)
        n_eur   = gnews("BCE Europe taux recession 2026", 3)
        n_china = gnews("Chine economie commerce mondial 2026", 3)
        n_maroc = gnews("Maroc economie inflation BAM BDT 2026", 4)
        n_intl  = gnews("BFM Reuters Bloomberg marche mondial 2026", 4)

        # Groq deep analysis — plus de tokens, plus de contexte
        sp_c  = macro.get("sp500",{}).get("c",0)
        cac_c = macro.get("cac40",{}).get("c",0)
        nas_c = macro.get("nasdaq",{}).get("c",0)
        dax_c = macro.get("dax",{}).get("c",0)
        nik_c = macro.get("nikkei",{}).get("c",0)
        sha_c = macro.get("shanghai",{}).get("c",0)
        br_c  = macro.get("brent",{}).get("c",0)
        go_c  = macro.get("gold",{}).get("c",0)
        ph_c  = macro.get("phosphate_idx",{}).get("c",0)
        mad   = macro.get("usd_mad",10.0)
        eur_mad = macro.get("eur_mad",10.9)
        spread = macro.get("yield_spread",0)
        rec   = macro.get("recession_risk",False)
        t10   = macro.get("us10y",0)
        fed   = macro.get("fed_rate",5.25)

        deep_prompt = f"""Tu es Baraka, analyste BVC Wall Street niveau. Il est 06h00 Casablanca.
Analyse profonde pour preparer le brief de 08h30.

=== MARCHÉS NUIT ===
Amerique: S&P500 {sp_c:+.2f}% | Nasdaq {nas_c:+.2f}%
Europe: CAC40 {cac_c:+.2f}% | DAX {dax_c:+.2f}%
Asie: Nikkei {nik_c:+.2f}% | Shanghai {sha_c:+.2f}%
MP: Or {go_c:+.2f}% | Brent {br_c:+.2f}% | Phosphate {ph_c:+.2f}%
Change: USD/MAD={mad} EUR/MAD={eur_mad}
Taux: US10Y={t10}% Spread={spread:+.3f}% {'⚠️ INVERSION COURBE' if rec else ''}
Fed={fed}%

=== CORRÉLATIONS DIRECTES AVEC LA BVC ===
{chr(10).join(correl)}

=== NEWS GÉOPOLITIQUE MONDIALE ===
Monde: {n_geo[:3]}
USA/Fed: {n_usa[:3]}
Europe: {n_eur[:2]}
Chine: {n_china[:2]}
Maroc: {n_maroc[:3]}
BVC: {n_bvc[:4]}

=== AMMC PUBLICATIONS ===
{[p['title'][:80] + (' → ' + p['ticker'] if p.get('ticker') else '') for p in ammc[:6]]}

=== BAM / BDT / INFLATION ===
BAM: {bkam.get('bam_news',[])}
Inflation Maroc: {bkam.get('inflation_news',[])}
BDT: {bkam.get('bdt_news',[])}

=== MACRO GLOBALE → IMPACT MAROC QUANTIFIÉ ===
France/CAC40: 1er partenaire commercial Maroc (30% export) — corrélation BVC ~0.7
Brent: impact direct sur inflation Maroc (60% energie importée)
Phosphate: OCP = 50% des exportations marocaines
USD/MAD: chaque +0.5 MAD = hausse importations ~3% → inflation

Réponds en 6 sections SANS markdown:
1. AMBIANCE MARCHÉS: Résumé des marchés mondiaux cette nuit et impact direct BVC aujourd'hui
2. ÉVÉNEMENT CLEF: L'événement géopolitique/économique mondial le plus important pour le Maroc aujourd'hui
3. INFLATION ET POUVOIR D'ACHAT: Impact USD/MAD + Brent sur l'économie réelle marocaine
4. ARBITRAGE BDT VS ACTIONS: Où vont les salles de marché ce matin? Bons du Trésor ou actions?
5. AMMC + FONDAMENTAUX: Publications du jour et impact sur les titres concernés
6. SECTEURS PRIORITAIRES: Quels secteurs surveiller à l'ouverture et pourquoi précisément
Style: trader professionnel, chiffres précis, liens causaux explicites. Français."""

        deep_analysis = groq_call(deep_prompt, 900)

        # Analyse rotation sectorielle
        sector_prompt = f"""Analyse rapide de rotation sectorielle pour la BVC aujourd'hui.
CAC40: {cac_c:+.2f}% | Brent: {br_c:+.2f}% | Or: {go_c:+.2f}% | Phosphate: {ph_c:+.2f}%
USD/MAD: {mad} | Spread 10Y-2Y: {spread:+.3f}%

Pour chaque secteur BVC, dis si c'est ACHETER / ÉVITER / NEUTRE et en 5 mots max pourquoi:
Banque | Assurance | Telecom | Chimie/OCP | Mines | Immobilier | Energie | Transport | Agro | Distribution
Format: SECTEUR: SIGNAL — raison courte
Français. Direct."""

        sector_analysis = groq_call(sector_prompt, 400)

        # Stocker en cache
        cache_set("pre_collect", {
            "macro": macro, "ammc": ammc, "boursenews": bn,
            "telegram": tg, "bkam": bkam, "correlations": correl,
            "news": {"bvc":n_bvc,"mac":n_mac,"geo":n_geo,"usa":n_usa,
                     "eur":n_eur,"china":n_china,"maroc":n_maroc,"intl":n_intl},
            "deep_analysis": deep_analysis,
            "sector_analysis": sector_analysis,
            "commodities": comm_pre,
            "odc": odc_pre,
            "timestamp": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        })
        print(f"[BARAKA] Pré-collecte OK — analyse Groq: {len(deep_analysis)} chars")

    except Exception as e:
        print(f"[PRÉ-COLLECTE] Erreur: {e}")


def confidence_score(d, sc, ammc_pubs_count, macro):
    """
    Score de confiance 0-5 basé sur le nombre de confirmations independantes.
    Chaque signal confirme = +1 etoile.
    """
    conf = 0
    # 1. Technique fort (score > 70)
    if sc >= 70: conf += 1
    # 2. Volume institutionnel (> 2x moy 90j)
    avg = d.get("avg90",0) or d.get("avg30",0) or 1
    if avg > 0 and d.get("volume",0)/avg > 2: conf += 1
    # 3. AMMC fondamentaux disponibles
    if ammc_pubs_count > 0: conf += 1
    # 4. Macro sectoriel aligné (score > 75 = technique + macro)
    if sc >= 75: conf += 1
    # 5. Momentum: MACD haussier ET RSI pas suracheté
    rsi = d.get("rsi",50)
    macd, macd_s = d.get("macd",0), d.get("macd_s",0)
    if macd > macd_s and rsi < 65: conf += 1
    return conf

def stars(n):
    return "★" * n + "☆" * (5-n)


# ─── EMAIL 1 : BRIEF OUVERTURE 08h30 ─────────────────────────────────────────
def brief_ouverture():
    print("[BARAKA] === BRIEF OUVERTURE 08h30 ===")
    try:
        now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        # Utiliser le cache de pré-collecte si disponible (max 3h)
        cached = cache_get("pre_collect", max_age_min=180)
        if cached:
            print("[BRIEF] Cache pré-collecte disponible ✓")
            macro  = cached["macro"]
            ammc   = cached["ammc"]
            bn     = cached["boursenews"]
            tg     = cached["telegram"]
            bkam   = cached["bkam"]
            correl = cached["correlations"]
            n_bvc  = cached["news"]["bvc"]
            n_mac  = cached["news"]["mac"]
            n_geo  = cached["news"]["geo"]
            n_usa  = cached["news"]["usa"]
            n_eur  = cached["news"]["eur"]
            n_china= cached["news"]["china"]
            n_maroc= cached["news"]["maroc"]
            n_intl = cached["news"]["intl"]
            pre_analysis    = cached.get("deep_analysis","")
            sector_analysis = cached.get("sector_analysis","")
            cached_time     = cached.get("timestamp","")
        else:
            print("[BRIEF] Collecte en direct (pas de cache)")
            macro  = get_macro()
            ammc   = get_ammc_pubs()
            bn     = boursenews()
            tg     = telegram_bvc()
            bkam   = bkam_news()
            correl = get_correlations_context(macro)
            n_bvc  = gnews("Bourse Casablanca 2026", 4)
            n_mac  = gnews("taux banque centrale Fed Reserve BCE 2026", 3)
            n_geo  = gnews("guerre conflit geopolitique mondial impact economie 2026", 3)
            n_usa  = gnews("Federal Reserve inflation USA economie 2026", 3)
            n_eur  = gnews("BCE Europe taux inflation recession 2026", 3)
            n_china= gnews("Chine economie commerce mondial 2026", 2)
            n_maroc= gnews("Maroc economie inflation BAM BDT 2026", 3)
            n_intl = gnews("BFM Business Reuters Bloomberg marche mondial 2026", 3)
            pre_analysis    = ""
            sector_analysis = ""
            cached_time     = ""

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
        f"=== MATIERES PREMIERES MAROC ===\n"
        f"Or/oz: {comm_pre.get('gold_oz',{}).get('p',0):.0f}$ ({comm_pre.get('gold_oz',{}).get('c',0):+.2f}%) -> Managem/SMI\n"
        f"Argent/oz: {comm_pre.get('silver_oz',{}).get('p',0):.2f}$ ({comm_pre.get('silver_oz',{}).get('c',0):+.2f}%) -> SMI Bou Azzer\n"
        f"Cuivre: {comm_pre.get('copper',{}).get('c',0):+.2f}% | Phosphate: {comm_pre.get('phosphate',{}).get('c',0):+.2f}% -> OCP\n"
        f"News mines Maroc: {comm_pre.get('news_or',[])}\n"
        f"Office des Changes: {odc_pre.get('news',[])}\n"
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
        # Utiliser l'analyse profonde de pré-collecte si disponible
        if pre_analysis:
            synth = pre_analysis
            print("[BRIEF] Analyse pré-collecte utilisée ✓")
        else:
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

        _dxy  = macro.get("dxy", {})
        dxy_c = _dxy.get("c", 0) if isinstance(_dxy, dict) else 0

        macro_html = f"""
        <div style="margin-bottom:8px;font-size:9px;color:#6B7280;letter-spacing:2px">CHANGE</div>
        <div class="mg" style="margin-bottom:10px">
          <div class="mb"><div class="ml">USD/MAD</div><div class="mv b">{mad}</div></div>
          <div class="mb"><div class="ml">EUR/MAD</div><div class="mv b">{eur_mad2}</div></div>
          <div class="mb"><div class="ml">DXY</div><div class="mv {col(dxy_c)}">{pct(dxy_c)}</div></div>
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

{'<div class="sec"><div class="t">🔄 ROTATION SECTORIELLE — OÙ ALLER CE MATIN</div>' + "".join(f'<div class="ni"><span class="src go">→</span>{line}</div>' for line in sector_analysis.split(chr(10)) if line.strip()) + "</div>" if sector_analysis else ""}

{'<div style="font-size:9px;color:#4B5563;text-align:right;margin-bottom:8px">Analyse pré-collectée à ' + cached_time + " — 6 sections Groq</div>" if cached_time else ""}

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

# ─── COMMODITES MAROC & METAUX PRECIEUX ──────────────────────────────────────
def get_commodities_maroc():
    """Prix matieres premieres liees a la production marocaine"""
    c = {}
    symbols = {
        "gold_oz":"xauusd","silver_oz":"xagusd","zinc":"zs.f",
        "lead":"pb.f","copper":"hg.f","phosphate":"mos.us",
    }
    for name, sym in symbols.items():
        c[name] = _stooq(sym)
        time.sleep(0.2)
    c["news_or"]    = gnews("or gold prix production mines Maroc Managem 2026", 3)
    c["news_argent"]= gnews("argent silver SMI Bou Azzer Maroc 2026", 2)
    c["news_phos"]  = gnews("phosphate OCP Maroc prix export 2026", 3)
    return c

def get_office_changes():
    """Veille Office des Changes Maroc reserves transferts IDE"""
    data = {"pubs":[], "news":[]}
    try:
        from bs4 import BeautifulSoup
        r = requests.get("https://www.officedeschnages.ma/fr/statistiques",
                         headers=HEADERS, **R)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text,"html.parser")
            for link in soup.find_all("a", href=True)[:20]:
                t = link.get_text(strip=True)
                h = link["href"]
                if len(t)>10 and any(k in t.lower() for k in ["reserve","transfert","ide","balance","exportation"]):
                    data["pubs"].append({"title":t[:150],"url":h})
    except: pass
    data["news"] = gnews("Office des Changes Maroc reserves devises 2026", 3)
    data["bkam_reserves"] = gnews("BAM Bank Al Maghrib reserves devises changes 2026", 2)
    return data

def get_historical_poc(ticker, bvc_info):
    """
    Point of Control (POC) : cours ou est passe le plus de volume sur 1 mois.
    Utilise stooq historique BVC si disponible. Fallback VWAP estime.
    """
    poc = {"price": 0, "method": "estimation", "note": ""}
    try:
        d1 = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y%m%d")
        d2 = datetime.date.today().strftime("%Y%m%d")
        r = requests.get(
            f"https://stooq.com/q/d/l/?s={ticker.lower()}.ma&i=d&d1={d1}&d2={d2}",
            headers=HEADERS, **R
        )
        if r.status_code == 200 and len(r.text) > 100:
            lines = r.text.strip().splitlines()[1:]
            if len(lines) >= 5:
                prices, volumes = [], []
                for line in lines:
                    parts = line.split(",")
                    if len(parts) >= 6:
                        try:
                            cl = float(parts[4])
                            vl = float(parts[5]) if parts[5] else 0
                            if cl > 0: prices.append(cl); volumes.append(vl)
                        except: pass
                if prices and sum(volumes) > 0:
                    poc_price = sum(p*v for p,v in zip(prices,volumes)) / sum(volumes)
                    poc["price"]  = round(poc_price, 2)
                    poc["method"] = "VWAP 30j"
                    poc["high"]   = round(max(prices),2)
                    poc["low"]    = round(min(prices),2)
                    poc["note"]   = f"Sur {len(prices)} seances"
                    return poc
    except: pass
    poc["note"] = "stooq indisponible"
    return poc

def detect_intraday_patterns(d, info):
    """
    Patterns intraday pour trades buy/sell dans la journee.
    Retourne patterns detectes + strategies concretes.
    """
    patterns, strategies = [], []
    close = d.get("close",0); open_ = d.get("open",0)
    high  = d.get("high",0);  low   = d.get("low",0)
    rsi   = d.get("rsi",50);  ema20 = d.get("ema20",0)
    vol   = d.get("volume",0)
    avg   = d.get("avg90",0) or info.get("v",1)

    if not close or not open_: return patterns, strategies

    range_day = high - low if high > low else 0.001
    body      = abs(close - open_)
    body_pct  = body / range_day
    wick_low  = min(open_,close) - low
    wick_high = high - max(open_,close)
    mid       = (high + low) / 2

    # Patterns bougies japonaises
    if wick_low/range_day > 0.6 and body_pct < 0.3:
        patterns.append("Marteau - Signal ACHAT")
        strategies.append(f"Entree > {close:.2f} | Stop < {low:.2f} | Cible {round(close+(high-low),2):.2f}")

    if wick_high/range_day > 0.6 and body_pct < 0.3:
        patterns.append("Etoile filante - Signal VENTE")
        strategies.append(f"Vente < {close:.2f} | Stop > {high:.2f} | Cible {round(close-(high-low),2):.2f}")

    if body_pct < 0.1:
        patterns.append("Doji - Indecision, attendre confirmation")

    if close > open_ and body_pct > 0.8:
        patterns.append("Marubozu haussier - Momentum fort ACHAT")
        strategies.append(f"Hold/Renforcer si maintient > {open_:.2f}")

    if close < open_ and body_pct > 0.8:
        patterns.append("Marubozu baissier - Momentum fort VENTE")
        strategies.append(f"Sortir/Vendre si casse < {close:.2f}")

    # Opening Range Breakout
    if close > mid and rsi < 65 and vol > avg*1.2:
        strategies.append(f"ORB Haussier: achat si depasse {high:.2f} vol>{int(avg*1.3):,}")
    elif close < mid and rsi > 35 and vol > avg*1.2:
        strategies.append(f"ORB Baissier: vente si casse {low:.2f} vol>{int(avg*1.3):,}")

    # Pullback EMA20
    if ema20>0 and abs(close-ema20)/ema20 < 0.006:
        strategies.append(f"Pullback EMA20 ({ema20:.2f}) - Zone entree precise")

    return patterns[:3], strategies[:3]

def get_vip_fundamental(ticker, ammc_pubs):
    """Analyse fondamentale pour les titres VIP"""
    return {
        "ammc": ammc_for(ticker, ammc_pubs),
        "news": gnews(f"{BVC.get(ticker,{}).get('n',ticker)} Maroc resultats 2026", 3),
        "news_secteur": gnews(f"{BVC.get(ticker,{}).get('s','')} Maroc 2026", 2),
    }

def build_vip_zoom_html(ticker, d, macro, ammc_pubs, commodities=None):
    """Bloc HTML zoom approfondi pour un titre VIP"""
    if not d or not d.get("close"):
        return f'<div style="background:#171C2C;border-radius:8px;padding:10px;margin-bottom:8px;border-left:3px solid #4B5563"><span style="color:#6B7280">{ticker} - donnees indisponibles</span></div>'

    info  = BVC.get(ticker, {})
    close = d.get("close",0);  rsi   = d.get("rsi",50)
    vol   = d.get("volume",0); avg   = d.get("avg90",0) or d.get("avg30",0) or info.get("v",1)
    chg   = d.get("change",0); ema20 = d.get("ema20",0)
    ema200= d.get("ema200",0); high  = d.get("high",0);  low = d.get("low",0)
    vr    = round(vol/avg,1) if avg>0 else 0
    sc    = score(d, info, macro)

    patterns, strategies = detect_intraday_patterns(d, info)
    poc   = get_historical_poc(ticker, info)
    fund  = get_vip_fundamental(ticker, ammc_pubs)

    sig_col = "#00C87A" if sc>=70 else ("#FF4560" if sc<=35 else "#C9A84C")
    sig_txt = "ACHAT" if sc>=70 else ("VENTE" if sc<=35 else "NEUTRE")
    chg_col = "#00C87A" if chg>=0 else "#FF4560"

    # POC section
    poc_html = ""
    if poc.get("price",0) > 0:
        dist = round((close-poc["price"])/poc["price"]*100,1)
        dist_col = "#00C87A" if dist>=0 else "#FF4560"
        poc_html = (
            f'<div style="background:rgba(139,92,246,.08);border:1px solid rgba(139,92,246,.2);border-radius:6px;padding:8px;margin:6px 0">'
            f'<div style="font-size:9px;color:#8B5CF6;margin-bottom:4px;letter-spacing:2px">POC - COURS LE PLUS TRADE (30j)</div>'
            f'<div style="font-size:13px;color:#E8E4D6;font-weight:700">{poc["price"]:.2f} MAD '
            f'<span style="font-size:10px;color:{dist_col}">({dist:+.1f}% vs POC)</span></div>'
            f'<div style="font-size:9px;color:#6B7280;margin-top:2px">{poc.get("note","")} | {poc.get("low",0):.2f} - {poc.get("high",0):.2f}</div>'
            f'</div>'
        )

    # Patterns
    pat_html = "".join(f'<div style="font-size:11px;color:#F59E0B;padding:2px 0">{p}</div>' for p in patterns)
    if pat_html:
        pat_html = f'<div style="margin:4px 0">{pat_html}</div>'

    # Strategies intraday
    strat_html = ""
    if strategies:
        strat_html = (
            f'<div style="background:rgba(245,158,11,.06);border-radius:5px;padding:7px;margin:5px 0">'
            f'<div style="font-size:9px;color:#F59E0B;margin-bottom:4px;letter-spacing:2px">TRADES INTRADAY</div>'
            + "".join(f'<div style="font-size:11px;color:#9CA3AF;padding:1px 0">. {s}</div>' for s in strategies)
            + f'</div>'
        )

    # Commodites
    comm_html = ""
    if commodities and info.get("s") == "Mines":
        if ticker in ["MANAGEM","CMT"]:
            go  = commodities.get("gold_oz",{})
            cop = commodities.get("copper",{})
            go_col  = "#00C87A" if go.get("c",0)>=0 else "#FF4560"
            cop_col = "#00C87A" if cop.get("c",0)>=0 else "#FF4560"
            comm_html = (f'<div style="font-size:10px;color:#6B7280;padding:3px 0">'
                        f'Or: <span style="color:{go_col};font-weight:700">{go.get("p",0):.0f}$ ({go.get("c",0):+.2f}%)</span> | '
                        f'Cuivre: <span style="color:{cop_col}">{cop.get("c",0):+.2f}%</span></div>')
        elif ticker == "SMI":
            ag  = commodities.get("silver_oz",{})
            ag_col = "#00C87A" if ag.get("c",0)>=0 else "#FF4560"
            comm_html = (f'<div style="font-size:10px;color:#6B7280;padding:3px 0">'
                        f'Argent: <span style="color:{ag_col};font-weight:700">{ag.get("p",0):.2f}$ ({ag.get("c",0):+.2f}%)</span></div>')

    # News + AMMC
    news_html = "".join(
        f'<div style="font-size:10px;color:#9CA3AF;padding:2px 0;border-bottom:1px solid rgba(255,255,255,.04)">. {n[:100]}</div>'
        for n in fund["news"][:2]
    )
    ammc_html2 = "".join(
        f'<div style="font-size:10px;color:#60A5FA;padding:2px 0">. {p["title"][:90]}</div>'
        for p in fund["ammc"][:2]
    )

    macd_col = "#00C87A" if d.get("macd",0)>d.get("macd_s",0) else "#FF4560"
    macd_dir = "Haussier" if d.get("macd",0)>d.get("macd_s",0) else "Baissier"
    ema200_col = "#00C87A" if close>ema200>0 else "#FF4560"

    return (
        f'<div style="background:#171C2C;border-radius:10px;padding:14px;margin-bottom:10px;border-left:4px solid {sig_col}">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">'
        f'<div><div style="font-size:18px;font-weight:900;color:{sig_col};font-family:monospace">{ticker}</div>'
        f'<div style="font-size:10px;color:#6B7280">{info.get("n","")} - {info.get("s","")}</div></div>'
        f'<div style="text-align:right">'
        f'<div style="font-size:16px;font-weight:900;color:#E8E4D6">{close:.2f} MAD</div>'
        f'<div style="font-size:11px;color:{chg_col}">{chg:+.2f}% | Vol x{vr}</div>'
        f'<div style="background:{sig_col}20;color:{sig_col};border:1px solid {sig_col}40;font-size:9px;padding:2px 8px;border-radius:4px;margin-top:2px">{sig_txt} {sc}/100</div>'
        f'</div></div>'
        f'<div style="display:flex;gap:10px;font-size:10px;flex-wrap:wrap;margin-bottom:6px">'
        f'<span style="color:#6B7280">RSI <strong style="color:{"#00C87A" if rsi<35 else "#FF4560" if rsi>70 else "#C9A84C"}">{rsi:.0f}</strong></span>'
        f'<span style="color:#6B7280">MACD <strong style="color:{macd_col}">{macd_dir}</strong></span>'
        f'<span style="color:#6B7280">EMA20 <strong style="color:{"#00C87A" if close>ema20>0 else "#FF4560"}">{ema20:.2f}</strong></span>'
        f'<span style="color:#6B7280">EMA200 <strong style="color:{ema200_col}">{">" if close>ema200>0 else "<"}</strong></span>'
        f'<span style="color:#6B7280">H:{high:.2f} B:{low:.2f}</span></div>'
        f'{comm_html}{poc_html}{pat_html}{strat_html}'
        + (f'<div style="font-size:9px;color:#60A5FA;margin-bottom:3px;letter-spacing:2px">AMMC</div>{ammc_html2}' if ammc_html2 else "")
        + (f'<div style="font-size:9px;color:#6B7280;margin-top:4px;letter-spacing:2px">NEWS</div>{news_html}' if news_html else "")
        + f'</div>'
    )


def _render_pdf_financials(pf):
    """Render AMMC financial data HTML"""
    if not pf: return ""
    ca  = pf.get("ca_mdh","N/A")
    ca_v= pf.get("ca_variation_pct","")
    rn  = pf.get("resultat_net_mdh","N/A")
    rn_v= pf.get("resultat_variation_pct","")
    eps = pf.get("eps_mad","N/A")
    div = pf.get("dividende_mad","N/A")
    resume = pf.get("resume","")
    signal = pf.get("signal","")
    sig_col = "#00C87A" if "ACHAT" in str(signal) else ("#FF4560" if "VENTE" in str(signal) else "#C9A84C")
    return (
        f'<div style="margin-top:8px;padding:8px;background:rgba(0,100,255,.06);border-radius:6px">' +
        f'<div style="font-size:9px;color:#60A5FA;margin-bottom:5px;letter-spacing:2px">📊 DONNÉES FINANCIÈRES AMMC EXTRAITES</div>' +
        f'<div style="display:flex;gap:8px;font-size:11px;flex-wrap:wrap">' +
        f'<span style="color:#6B7280">CA: <strong style="color:#E8E4D6">{ca} MDH</strong> {("+"+str(ca_v)+"%" if ca_v else "")}</span>' +
        f'<span style="color:#6B7280">RN: <strong style="color:#E8E4D6">{rn} MDH</strong> {("+"+str(rn_v)+"%" if rn_v else "")}</span>' +
        f'<span style="color:#6B7280">EPS: <strong style="color:#E8E4D6">{eps} MAD</strong></span>' +
        f'<span style="color:#6B7280">Div: <strong style="color:#C9A84C">{div} MAD</strong></span>' +
        f'</div>' +
        (f'<div style="font-size:10px;color:{sig_col};margin-top:4px">{signal} — {resume}</div>' if resume else "") +
        f'</div>'
    )


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

            rr   = round(abs(target-close)/abs(close-stop),2) if abs(close-stop)>0 else 0
            avg  = d.get("avg90",0) or d.get("avg30",0) or info.get("v",1)
            vr   = round(d.get("volume",0)/avg,1) if avg>0 else 0

            # Score de confiance (0-5 étoiles)
            conf = confidence_score(d, sc, len(ammc_t), macro)

            # Multi-horizon targets
            t_day  = round(close * (1.03 if is_buy else 0.97), 2)   # T+1 jour
            t_week = round(close * (1.06 if is_buy else 0.94), 2)   # T+1 semaine
            t_month= round(close * (1.12 if is_buy else 0.88), 2)   # T+1 mois

            # Groq par ticker
            ammc_ctx = " | ".join([p["title"][:80] for p in ammc_t]) if ammc_t else "Aucune publication AMMC récente"
            # Patterns techniques
            patterns = detect_technical_pattern(d, info)
            
            # Scenarios bull/base/bear
            scenarios = bull_base_bear_scenarios(close, is_buy, sc, macro)
            
            # Kelly position sizing (win_rate estimé à 55-70% selon score)
            win_rate_est = 45 + sc * 0.25  # 45% à 70% selon score
            kelly_pct = kelly_position_size(win_rate_est, rr, True)
            
            # Trigger conditions
            triggers, alarms = generate_trigger_conditions(d, info, macro, is_buy)

            # Analyse PDF AMMC si disponible
            pdf_financials = {}
            if ammc_t:
                print(f"[ANALYSE] Extraction PDF {t}...")
                pdf_financials = extract_pdf_financials(ammc_t[0]["url"], ammc_t[0]["title"])

            # Contexte macro sectoriel
            sect    = info.get("s","")
            cac_c   = macro.get("cac40",{}).get("c",0)
            brent_c = macro.get("brent",{}).get("c",0)
            gold_c  = macro.get("gold",{}).get("c",0)
            phos_c  = macro.get("phosphate_idx",{}).get("c",0)
            usd_mad = macro.get("usd_mad",10.0)
            spread  = macro.get("yield_spread",0)

            # === CHAIN-OF-THOUGHT GROQ (3 étapes) ===
            cot_prompt = f"""Tu es Baraka, analyste BVC Wall Street Elite. Analyse en 3 étapes.

TITRE: {t} — {info.get('n','')} ({sect}) — Score: {sc}/100

ÉTAPE 1 — CONTEXTE MACRO SECTORIEL:
CAC40(France/1er partenaire Maroc): {cac_c:+.2f}%
Brent: {brent_c:+.2f}% | Or: {gold_c:+.2f}% | Phosphate: {phos_c:+.2f}%
USD/MAD: {usd_mad} | Spread 10Y-2Y: {spread:+.3f}%
Impact sectoriel sur {sect}: analyse l'impact direct

ÉTAPE 2 — SETUP TECHNIQUE:
RSI={rsi:.0f} | MACD={'HAUSSIER' if d.get('macd',0)>d.get('macd_s',0) else 'BAISSIER'}
Cours={close:.2f} vs EMA20={d.get('ema20',0):.2f} | EMA50={d.get('ema50',0):.2f} | EMA200={d.get('ema200',0):.2f}
Volume: {d.get('volume',0):,} vs moy.90j {int(avg):,} (x{vr})
Patterns: {patterns if patterns else 'Aucun pattern majeur'}
Signal technique: {'ACHAT' if is_buy else 'VENTE'} avec confiance {conf}/5

ÉTAPE 3 — FONDAMENTAUX AMMC:
Publications récentes: {ammc_ctx}
{f"Données financières extraites: CA={pdf_financials.get('ca_mdh','N/A')} MDH ({pdf_financials.get('ca_variation_pct','N/A')}%), RN={pdf_financials.get('resultat_net_mdh','N/A')} MDH ({pdf_financials.get('resultat_variation_pct','N/A')}%), EPS={pdf_financials.get('eps_mad','N/A')} MAD" if pdf_financials else "PDF non encore analysé"}
Signal fondamental: {pdf_financials.get('signal','N/A') if pdf_financials else 'Basé sur news'}

VERDICT FINAL (3 phrases sans markdown):
1. Verdict technique + macro alignés OUI/NON et pourquoi précisément
2. Catalyseur fondamental (AMMC/résultats/secteur) qui confirme ou infirme
3. Condition d'entrée PRÉCISE: à quel prix, avec quel volume, dans quel délai
Français. Style trader hedge fund."""

            analyse = groq_call(cot_prompt, 400) or "Signaux techniques alignés — confirmation AMMC disponible."

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
    <div style="display:flex;justify-content:space-between;margin-bottom:8px;align-items:center">
      <div style="font-size:9px;color:#C9A84C;letter-spacing:2px">NIVEAUX DE TRADING</div>
      <div style="font-size:14px;color:#F59E0B" title="Confiance {conf}/5">{stars(conf)} <span style="font-size:9px;color:#6B7280">{conf}/5</span></div>
    </div>
    <div class="lr"><span style="color:#6B7280">💰 Entrée</span><strong style="color:#E8E4D6">{close:.2f} MAD</strong></div>
    <div class="lr"><span style="color:#6B7280">🛑 Stop</span><strong style="color:#FF4560">{stop:.2f} MAD (-{stp_pct}%)</strong></div>
    <div style="margin:6px 0;padding:6px;background:rgba(0,0,0,.2);border-radius:5px">
      <div style="font-size:9px;color:#6B7280;margin-bottom:4px">CIBLES PROGRESSIVES</div>
      <div class="lr"><span style="color:#9CA3AF;font-size:11px">T+1 jour</span><strong style="color:#4ADE80">{t_day:.2f} MAD ({sg(round((t_day-close)/close*100,1))}{round((t_day-close)/close*100,1)}%)</strong></div>
      <div class="lr"><span style="color:#9CA3AF;font-size:11px">T+1 semaine</span><strong style="color:#00C87A">{t_week:.2f} MAD ({sg(round((t_week-close)/close*100,1))}{round((t_week-close)/close*100,1)}%)</strong></div>
      <div class="lr"><span style="color:#9CA3AF;font-size:11px">T+1 mois</span><strong style="color:#C9A84C">{t_month:.2f} MAD ({sg(round((t_month-close)/close*100,1))}{round((t_month-close)/close*100,1)}%)</strong></div>
    </div>
    <div class="lr"><span style="color:#6B7280">R/R (jour)</span><strong style="color:#C9A84C">{rr}</strong></div>
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
      <span style="color:#6B7280">Score Baraka</span>
      <span style="color:#C9A84C;font-weight:700">{sc}/100</span>
    </div>
    <div class="sb"><div class="sf" style="width:{sc}%"></div></div>
  </div>

  {"" if not patterns else f'<div style="margin-top:8px;padding:8px;background:rgba(201,168,76,.06);border-radius:6px"><div style="font-size:9px;color:#C9A84C;margin-bottom:4px;letter-spacing:2px">PATTERNS DÉTECTÉS</div>' + "".join(f'<div style="font-size:11px;color:#9CA3AF;padding:1px 0">{p}</div>' for p in patterns) + "</div>"}

  <div style="margin-top:8px;padding:8px;background:rgba(0,0,0,.3);border-radius:6px">
    <div style="font-size:9px;color:#C9A84C;margin-bottom:6px;letter-spacing:2px">TRIGGERS D'ENTRÉE</div>
    {"".join(f'<div style="font-size:11px;color:#9CA3AF;padding:2px 0">✅ {trig}</div>' for trig in triggers)}
    <div style="height:1px;background:rgba(255,69,96,.2);margin:5px 0"></div>
    {"".join(f'<div style="font-size:11px;color:#FF4560;padding:2px 0">⛔ {alarm}</div>' for alarm in alarms)}
  </div>

  <div style="margin-top:8px">
    <div style="font-size:9px;color:#C9A84C;margin-bottom:6px;letter-spacing:2px">3 SCÉNARIOS</div>
    <div style="display:flex;gap:4px">
      <div style="flex:1;background:rgba(0,200,122,.08);border:1px solid rgba(0,200,122,.2);border-radius:5px;padding:6px;text-align:center">
        <div style="font-size:9px;color:#00C87A">BULL</div>
        <div style="font-size:11px;color:#00C87A;font-weight:700">{scenarios['bull']['target']:.2f}</div>
        <div style="font-size:9px;color:#6B7280">{scenarios['bull']['pct']}%</div>
      </div>
      <div style="flex:1;background:rgba(201,168,76,.08);border:1px solid rgba(201,168,76,.2);border-radius:5px;padding:6px;text-align:center">
        <div style="font-size:9px;color:#C9A84C">BASE</div>
        <div style="font-size:11px;color:#C9A84C;font-weight:700">{scenarios['base']['target']:.2f}</div>
        <div style="font-size:9px;color:#6B7280">{scenarios['base']['pct']}%</div>
      </div>
      <div style="flex:1;background:rgba(255,69,96,.08);border:1px solid rgba(255,69,96,.2);border-radius:5px;padding:6px;text-align:center">
        <div style="font-size:9px;color:#FF4560">BEAR</div>
        <div style="font-size:11px;color:#FF4560;font-weight:700">{scenarios['bear']['target']:.2f}</div>
        <div style="font-size:9px;color:#6B7280">{scenarios['bear']['pct']}%</div>
      </div>
    </div>
  </div>

  {_render_pdf_financials(pdf_financials)}

  <div style="margin-top:8px;padding:7px;background:rgba(201,168,76,.05);border-radius:6px;display:flex;justify-content:space-between;align-items:center">
    <div style="font-size:10px;color:#6B7280">Kelly Criterion</div>
    <div style="font-size:13px;color:#C9A84C;font-weight:700">{kelly_pct}% du capital</div>
  </div>

</div>"""

        if not cards:
            cards = '<div style="text-align:center;padding:20px;color:#6B7280">Aucun signal qualifié ce matin — attendre confirmation.</div>'

        # Momentum sectoriel
        sector_momentum = calculate_sector_momentum(bvc_data, macro)

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

        </div>

        <div class="sec">
          <div class="t">📊 MOMENTUM SECTORIEL BVC</div>
          {"".join(
            f'<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:11px">' +
            f'<span style="color:{"#00C87A" if i<3 else ("#C9A84C" if i<5 else "#6B7280")};min-width:120px">{"🟢" if i<3 else ("🟡" if i<5 else "⚪")} {sect_name}</span>' +
            f'<div style="flex:1;margin:0 8px;background:#0A0D14;border-radius:2px;height:4px"><div style="height:100%;border-radius:2px;width:{min(100,int(sect_sc))}%;background:{"#00C87A" if i<3 else ("#C9A84C" if i<5 else "#6B7280")}"></div></div>' +
            f'<span style="color:#6B7280">{sect_sc:.0f}/100</span></div>'
            for i,(sect_name,sect_sc) in enumerate(sector_momentum[:8])
          )}
        </div>

        <div class="ft">Prochaine analyse : 15h30 — Smart Money & Paris Demain<br>
<strong class="go">Max 3 trades/jour — Kelly Criterion — Confirmez manuellement</strong></div>
</div></body></html>"""

        # ══════════════════════════════════════════════════════════════════
        # ZOOM VIP QUOTIDIEN — Analyse approfondie des titres suivis
        # ══════════════════════════════════════════════════════════════════
        print("[BARAKA] Zoom VIP quotidien en cours...")
        commodities = get_commodities_maroc()
        odc         = get_office_changes()

        vip_cards_html = ""
        for vip_t in VIP_TICKERS:
            vip_d = bvc.get(vip_t)
            if vip_d:
                vip_cards_html += build_vip_zoom_html(vip_t, vip_d, macro, ammc, commodities)

        # Section commodites Maroc
        go   = commodities.get("gold_oz",{})
        ag   = commodities.get("silver_oz",{})
        zn   = commodities.get("zinc",{})
        cu   = commodities.get("copper",{})
        ph   = commodities.get("phosphate",{})
        go_c  = go.get("c",0);  ag_c = ag.get("c",0)
        zn_c  = zn.get("c",0);  cu_c = cu.get("c",0)

        def cc(v): return "#00C87A" if v>=0 else "#FF4560"

        comm_section = f"""
        <div class="sec" style="border-color:rgba(245,158,11,.3)">
          <div class="t" style="color:#F59E0B">MATIERES PREMIERES MAROC</div>
          <div style="display:flex;gap:6px;flex-wrap:wrap">
            <div class="mb"><div class="ml">OR/oz</div><div class="mv" style="color:{cc(go_c)}">{go.get("p",0):.0f}$<br><span style="font-size:10px">{go_c:+.2f}%</span></div></div>
            <div class="mb"><div class="ml">ARGENT/oz</div><div class="mv" style="color:{cc(ag_c)}">{ag.get("p",0):.2f}$<br><span style="font-size:10px">{ag_c:+.2f}%</span></div></div>
            <div class="mb"><div class="ml">ZINC</div><div class="mv" style="color:{cc(zn_c)}">{zn_c:+.2f}%</div></div>
            <div class="mb"><div class="ml">CUIVRE</div><div class="mv" style="color:{cc(cu_c)}">{cu_c:+.2f}%</div></div>
            <div class="mb"><div class="ml">PHOSPHATE</div><div class="mv" style="color:{cc(ph.get("c",0))}">{ph.get("c",0):+.2f}%</div></div>
          </div>
          {"".join(f'<div class="ni"><span class="src" style="color:#F59E0B">MINES</span>{n}</div>' for n in (commodities.get("news_or",[]) + commodities.get("news_argent",[]))[:3])}
          {"".join(f'<div class="ni"><span class="src" style="color:#C9A84C">PHOS</span>{n}</div>' for n in commodities.get("news_phos",[])[:2])}
        </div>"""

        odc_html = ""
        if odc.get("pubs") or odc.get("news"):
            odc_html = (
                '<div class="sec"><div class="t">OFFICE DES CHANGES MAROC</div>'
                + "".join(f'<div class="ni"><span class="src b">ODC</span>{p["title"]}</div>' for p in odc.get("pubs",[])[:3])
                + "".join(f'<div class="ni"><span class="src b">ODC</span>{n}</div>' for n in odc.get("news",[])[:2])
                + "".join(f'<div class="ni"><span class="src go">BAM</span>{n}</div>' for n in odc.get("bkam_reserves",[])[:2])
                + "</div>"
            )

        # Email ZOOM VIP séparé
        zoom_html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="w">
<div class="hdr">
  <div class="logo">BARAKA</div>
  <div class="sub">ZOOM VIP QUOTIDIEN - {now}</div>
  <span class="bdg" style="color:#F59E0B;border-color:rgba(245,158,11,.3);background:rgba(245,158,11,.1)">
    {len([t for t in VIP_TICKERS if bvc.get(t)])} TITRES SUIVIS EN PROFONDEUR
  </span>
</div>
{comm_section}
{odc_html}
<div style="font-size:10px;color:#C9A84C;letter-spacing:3px;text-transform:uppercase;margin-bottom:10px">ANALYSE APPROFONDIE - TECHNIQUE + INTRADAY + POC + AMMC</div>
{vip_cards_html if vip_cards_html else '<div style="color:#6B7280;padding:20px">Donnees TV indisponibles pour les titres VIP</div>'}
<div class="ft">Zoom VIP quotidien - Baraka Elite Max<br>
<strong class="go">POC = cours le plus trade sur 30j - Reference Smart Money</strong></div>
</div></body></html>"""

        send_email("BARAKA - ZOOM VIP QUOTIDIEN 12h00", zoom_html)

        send_email("BARAKA — ANALYSE + ENTRÉES 12h00", html)

        # ── PEUPLER LA WATCHLIST pour surveillance en temps réel ──
        watchlist_clear()
        for item in scored:
            t    = item["t"]
            d    = item["d"]
            info = item["i"]
            close_p = d.get("close",0)
            rsi_p   = d.get("rsi",50)
            ema20_p = d.get("ema20",0)
            avg_p   = d.get("avg90",0) or info.get("v",1)
            is_buy_p = d.get("macd",0) > d.get("macd_s",0) and rsi_p < 65
            tgt_p   = round(close_p*(1.06 if is_buy_p else 0.94),2)
            stp_p   = round(close_p*(0.97 if is_buy_p else 1.02),2)
            conditions_p = [
                f"Cours > EMA20 ({ema20_p:.2f})",
                f"Volume > {int(avg_p*1.5):,} titres",
                f"RSI < 32 (survente)",
                f"MACD croisement haussier",
            ]
            watchlist_add(t, conditions_p, close_p, stp_p, tgt_p, "BUY" if is_buy_p else "SELL")

        print(f"[WATCHLIST] {len(scored)} titre(s) en surveillance active")

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


        @app.route("/watchlist")
        def watchlist_view():
            if not _WATCHLIST:
                return "Watchlist vide — en attente analyse 12h00", 200
            out = [f"BARAKA WATCHLIST {datetime.datetime.now().strftime('%H:%M')}\n"]
            for tk, wl in _WATCHLIST.items():
                out.append(f"{tk}: entree={wl['entry']:.2f} stop={wl['stop']:.2f} cible={wl['target']:.2f} triggers_fired={len(wl['fired'])}\n")
            return "".join(out), 200, {"Content-Type":"text/plain"}

        @app.route("/check")
        def force_check():
            threading.Thread(target=monitor_triggers, daemon=True).start()
            return f"Verification {len(_WATCHLIST)} titres — alerte email si trigger actif", 200

        port = int(os.environ.get("PORT", 8080))
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"[FLASK] {e}")

# ─── SCHEDULER SIMPLE UTC ────────────────────────────────────────────────────
def run_scheduler():
    print("""
╔═════════════════════════════════════════════════════╗
║  BARAKA v6.0 ELITE MAX — BVC — Analyse Wall Street       ║
╠═════════════════════════════════════════════════════╣
║  05:00 UTC → 06:00 Casa — PRÉ-COLLECTE PROFONDE     ║
║  07:30 UTC → 08:30 Casa — BRIEF OUVERTURE            ║
║  11:00 UTC → 12:00 Casa — ANALYSE + ENTRÉES           ║
║  14:30 UTC → 15:30 Casa — POST-CLÔTURE SMART MONEY  ║
╚═════════════════════════════════════════════════════╝
    """)

    threading.Thread(target=start_flask, daemon=True).start()
    fired = {}

    while True:
        try:
            now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            today = str(now.date())
            h, m, wd = now.hour, now.minute, now.weekday()

            if h == 0 and m == 0:
                fired = {}

            if wd < 5:  # Lundi-Vendredi seulement
                # 05:00 UTC = 06:00 Casa → PRÉ-COLLECTE PROFONDE
                if h==5 and 0<=m<15 and f"precollect_{today}" not in fired:
                    fired[f"precollect_{today}"] = True
                    print("[SCHEDULER] → pre_collect")
                    threading.Thread(target=pre_collect, daemon=True).start()

                # 07:30 UTC = 08:30 Casa → BRIEF OUVERTURE
                elif h==7 and 30<=m<45 and f"brief_{today}" not in fired:
                    fired[f"brief_{today}"] = True
                    print("[SCHEDULER] → brief_ouverture")
                    threading.Thread(target=brief_ouverture, daemon=True).start()

                # 11:00 UTC = 12:00 Casa → ANALYSE + ENTRÉES
                elif h==11 and 0<=m<15 and f"analyse_{today}" not in fired:
                    fired[f"analyse_{today}"] = True
                    print("[SCHEDULER] → analyse_entrees")
                    threading.Thread(target=analyse_entrees, daemon=True).start()

                # 14:30 UTC = 15:30 Casa → POST-CLÔTURE
                elif h==14 and 30<=m<45 and f"cloture_{today}" not in fired:
                    fired[f"cloture_{today}"] = True
                    print("[SCHEDULER] → post_cloture")
                    threading.Thread(target=post_cloture, daemon=True).start()

                # SURVEILLANCE TRIGGERS toutes les 10 min (09:00-15:30 UTC = 10:00-16:30 Casa)
                # Tire à chaque :00 et :10 et :20 et :30 et :40 et :50
                if 9 <= h < 15 and m % 10 == 0:
                    trigger_key = f"trigger_{today}_{h}_{m}"
                    if trigger_key not in fired and _WATCHLIST:
                        fired[trigger_key] = True
                        threading.Thread(target=monitor_triggers, daemon=True).start()

                # Reset watchlist à minuit
                if h == 0 and m == 0:
                    watchlist_clear()

        except Exception as e:
            print(f"[SCHEDULER] {e}")

        time.sleep(30)


if __name__ == "__main__":
    run_scheduler()
