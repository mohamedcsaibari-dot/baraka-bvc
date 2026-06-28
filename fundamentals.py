"""
fundamentals.py — Modèle Élasticité Prix SMI, Managem & CMT
Baraka BVC v7.3 — Mining Intelligence Module

══ SMI (pure argent — mine Imiter/Zgounder) ══════════════════════════════
Anchors confirmés (enrichir après chaque séance clé):
  Ag $35  → SMI  2 237 MAD  (52S low)
  Ag $58  → SMI  5 700 MAD  (clôture 24 juin 2026)
  Ag $73  → SMI  9 220 MAD  (pic avr 2026)
  Ag $84  → SMI 12 899 MAD  (ATH 52S)

══ MANAGEM (or dominant + cuivre en montée) ══════════════════════════════
CA 2025 ~9.8 MMDH: or ~48% (Tri-K Guinée, Boto Sénégal, Soudan)
                   cuivre ~25% (Pumpi RDC, Tizert Maroc en prod.)
                   argent ~15% (mines polymétalliques Maroc)
                   cobalt ~7%  (prod. volontairement réduite, prix déprimé)
                   divers ~5%
Modèle: base or (beta calibré empiriquement) + ajustement cuivre (déviation vs ref)

══ CMT (Minière Touissit — mine Tighza, plomb-zinc argentifère) ══════════
CA 2025 ~691 MDH: argent 65% (concentrés Pb-Ag + Zn-Ag, teneur 95 g/t)
                  zinc   20% (concentré zinc argentifère)
                  plomb  15% (proxié par zinc, très corrélés sur Tighza)
Production: ~1 000 T/j minerai → 23 000 T/an concentré Pb-Ag + 3 600 T/an Zn
Calibration: Ag=$58 + Zn=$3 000/T → CMT=4 900 MAD (06/2026)
"""
import os

# ══ SMI ═══════════════════════════════════════════════════════════════════════
SMI_ANCHORS = [
    (35,   2_237),
    (58,   5_700),
    (73,   9_220),
    (84,  12_899),
]

# ══ Managem ═══════════════════════════════════════════════════════════════════
MNG_BETA_OR   = float(os.getenv("MNG_BETA_OR",    "3.43"))   # MAD/$/oz or
MNG_ALPHA_OR  = float(os.getenv("MNG_ALPHA",      "-285"))   # constante calibrée
MNG_FLOOR     = 2_000.0
MNG_CU_REF    = float(os.getenv("MNG_CU_REF",    "9200"))    # $/T cuivre référence
MNG_CU_WEIGHT = float(os.getenv("MNG_CU_WEIGHT", "0.25"))    # poids cuivre CA (25%)

# ══ CMT ═══════════════════════════════════════════════════════════════════════
CMT_PRICE_REF = float(os.getenv("CMT_PRICE_REF", "4900"))    # MAD point calibration
CMT_AG_REF    = float(os.getenv("CMT_AG_REF",    "58.0"))    # $/oz argent référence
CMT_ZN_REF    = float(os.getenv("CMT_ZN_REF",    "3000"))    # $/T zinc référence (LME)
CMT_AG_WEIGHT = float(os.getenv("CMT_AG_WEIGHT", "0.65"))    # argent 65% valeur conc.
CMT_ZN_WEIGHT = float(os.getenv("CMT_ZN_WEIGHT", "0.35"))    # zinc+plomb proxy 35%
CMT_FLOOR     = 500.0

BVC_CAP_PCT   = 0.10


# ══ SMI ═══════════════════════════════════════════════════════════════════════

def _anchors():
    return sorted(SMI_ANCHORS, key=lambda x: x[0])

def smi_fair_value(silver_usd: float) -> float:
    pts = _anchors()
    if silver_usd <= pts[0][0]: return float(pts[0][1])
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]; x1, y1 = pts[i+1]
        if x0 <= silver_usd <= x1:
            return y0 + (silver_usd - x0) / (x1 - x0) * (y1 - y0)
    x0, y0 = pts[-2]; x1, y1 = pts[-1]
    return max(float(y1), y1 + (y1-y0)/(x1-x0) * (silver_usd - x1))

def smi_local_beta(silver_usd: float) -> float:
    """β local SMI: MAD par $/oz argent (non-constant, croît avec prix)."""
    pts = _anchors()
    if silver_usd <= pts[0][0]: return (pts[1][1]-pts[0][1])/(pts[1][0]-pts[0][0])
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]; x1, y1 = pts[i+1]
        if x0 <= silver_usd <= x1: return (y1-y0)/(x1-x0)
    x0, y0 = pts[-2]; x1, y1 = pts[-1]
    return (y1-y0)/(x1-x0)

def smi_elasticity(silver_usd: float, smi_price: float) -> float:
    if smi_price <= 0: return 0.0
    return round(smi_local_beta(silver_usd) * silver_usd / smi_price, 2)


# ══ MANAGEM ═══════════════════════════════════════════════════════════════════

def mng_fair_value(gold_usd: float, copper_usd: float = 0.0) -> float:
    """
    Juste valeur Managem — modèle bi-facteur or + cuivre.
    Base: beta or linéaire calibré empiriquement.
    Ajustement cuivre: déviation % vs référence × poids CA cuivre (25%).
    Ex: cuivre +10% vs ref → +2.5% sur la FV or-seule.
    """
    base = max(MNG_FLOOR, MNG_ALPHA_OR + MNG_BETA_OR * gold_usd)
    if copper_usd > 0 and MNG_CU_REF > 0:
        cu_dev = (copper_usd - MNG_CU_REF) / MNG_CU_REF
        base   = max(MNG_FLOOR, base * (1.0 + MNG_CU_WEIGHT * cu_dev))
    return base

def mng_elasticity(gold_usd: float, mng_price: float, copper_usd: float = 0.0) -> float:
    """Élasticité MNG vs or (+1% or → X% MNG). Cuivre traité séparément."""
    if mng_price <= 0: return 0.0
    return round(MNG_BETA_OR * gold_usd / mng_price, 2)

def mng_copper_sens(copper_usd: float, mng_fv: float) -> float:
    """+1% cuivre → X% Managem (linéaire via poids CA)."""
    return MNG_CU_WEIGHT  # 0.25 constant

def mng_copper_delta(copper_usd: float) -> float:
    """Impact MAD sur FV si cuivre dévie de sa référence."""
    if MNG_CU_REF <= 0: return 0.0
    cu_dev = (copper_usd - MNG_CU_REF) / MNG_CU_REF
    base_ref = max(MNG_FLOOR, MNG_ALPHA_OR + MNG_BETA_OR * 4000)  # ref or $4000
    return round(base_ref * MNG_CU_WEIGHT * cu_dev)


# ══ CMT ═══════════════════════════════════════════════════════════════════════

def cmt_fair_value(silver_usd: float, zinc_usd: float = 0.0) -> float:
    """
    Juste valeur CMT (Minière de Touissit — mine Tighza).
    Modèle composite: argent 65% + zinc+plomb 35% (plomb proxié par zinc).
    Si zinc indisponible: ratio zinc = 1.0 (stable à référence).
    Calibration: Ag=$58 + Zn=$3000/T → CMT=4900 MAD (06/2026).
    """
    ag_ratio = silver_usd / CMT_AG_REF if CMT_AG_REF > 0 else 1.0
    zn_ratio = (zinc_usd / CMT_ZN_REF
                if (zinc_usd > 0 and CMT_ZN_REF > 0) else 1.0)
    composite = CMT_AG_WEIGHT * ag_ratio + CMT_ZN_WEIGHT * zn_ratio
    return max(CMT_FLOOR, CMT_PRICE_REF * composite)

def cmt_local_beta_ag(silver_usd: float = 0.0, cmt_price: float = 0.0) -> float:
    """β argent de CMT (MAD par $/oz)."""
    return round(CMT_AG_WEIGHT * CMT_PRICE_REF / CMT_AG_REF, 1)

def cmt_elasticity(silver_usd: float, cmt_price: float, zinc_usd: float = 0.0) -> float:
    """Élasticité CMT vs argent (+1% argent → X% CMT)."""
    if cmt_price <= 0: return 0.0
    beta = CMT_AG_WEIGHT * CMT_PRICE_REF / CMT_AG_REF  # MAD/$/oz
    return round(beta * silver_usd / cmt_price, 2)


# ══ Utilitaires communs ═══════════════════════════════════════════════════════

def valuation_signal(actual: float, fair_value: float) -> tuple:
    gap = (fair_value - actual) / actual * 100 if actual > 0 else 0.0
    if   gap >  12: s = f"FORT POTENTIEL +{gap:.1f}%"
    elif gap >   5: s = f"SOUS-ÉVALUÉ +{gap:.1f}%"
    elif gap >  -5: s = f"JUSTE VALEUR {gap:+.1f}%"
    elif gap > -12: s = f"SUR-ÉVALUÉ {gap:.1f}%"
    else:           s = f"FORT PREMIUM {gap:.1f}%"
    return s, round(gap, 1)

def bvc_limits(open_price: float) -> tuple:
    return round(open_price * (1+BVC_CAP_PCT)), round(open_price * (1-BVC_CAP_PCT))

def _sig_col(gap):
    return "#00C87A" if gap > 5 else ("#FF4560" if gap < -5 else "#C9A84C")


# ══ Bloc HTML ════════════════════════════════════════════════════════════════

def mines_html_block(
    smi_price:  float,
    mng_price:  float,
    silver_usd: float,
    gold_usd:   float,
    smi_open:   float = 0.0,
    mng_open:   float = 0.0,
    compact:    bool  = False,
    cmt_price:  float = 0.0,
    copper_usd: float = 0.0,
    zinc_usd:   float = 0.0,
    cmt_open:   float = 0.0,
) -> str:
    """
    Bloc HTML pour emails Baraka.
    compact=True  → brief 07h30 (4+1 boîtes, format condensé)
    compact=False → analyse 11h / post-clôture (grille 3 colonnes)
    xxx_price=0   → BVC fermé, affiche valeur théorique seule
    """
    smi_fv  = smi_fair_value(silver_usd)
    mng_fv  = mng_fair_value(gold_usd, copper_usd)
    cmt_fv  = cmt_fair_value(silver_usd, zinc_usd)
    smi_bet = smi_local_beta(silver_usd)
    smi_el  = smi_elasticity(silver_usd, smi_price or smi_fv)
    mng_el  = mng_elasticity(gold_usd, mng_price or mng_fv, copper_usd)
    cmt_bet = cmt_local_beta_ag(silver_usd, cmt_price or cmt_fv)
    cmt_el  = cmt_elasticity(silver_usd, cmt_price or cmt_fv, zinc_usd)

    ag1_smi = smi_bet * silver_usd * 0.01    # +1% Ag → MAD SMI
    au1_mng = MNG_BETA_OR * gold_usd  * 0.01 # +1% Au → MAD MNG
    ag1_cmt = cmt_bet * silver_usd * 0.01    # +1% Ag → MAD CMT

    # Valuation signals
    def _vrow(bvc, fv, drv_sym, drv_price):
        if bvc > 0:
            _, gap = valuation_signal(bvc, fv)
            gc = "#00C87A" if gap > 0 else "#FF4560"
            arrow = "↑ sous-évalué" if gap > 5 else ("↓ sur-évalué" if gap < -5 else "≈ juste valeur")
            return (
                f'<div class="lr"><span style="color:#6B7280">BVC</span>'
                f'<strong style="color:#E8E4D6">{bvc:,.0f} MAD</strong></div>'
                f'<div class="lr"><span style="color:#6B7280">Théorique</span>'
                f'<strong style="color:#C9A84C">{fv:,.0f} MAD</strong></div>'
                f'<div class="lr"><span style="color:#6B7280">Gap</span>'
                f'<strong style="color:{gc}">{gap:+.1f}% {arrow}</strong></div>'
            ), gap
        else:
            return (
                f'<div class="lr"><span style="color:#6B7280">FV ({drv_sym}${drv_price:.1f})</span>'
                f'<strong style="color:#60A5FA">{fv:,.0f} MAD</strong></div>'
                f'<div style="font-size:9px;color:#4B5563">BVC fermé</div>'
            ), 0

    smi_vrow, smi_gap = _vrow(smi_price, smi_fv, "Ag", silver_usd)
    mng_vrow, mng_gap = _vrow(mng_price, mng_fv, "Au", gold_usd)
    cmt_vrow, cmt_gap = _vrow(cmt_price, cmt_fv, "Ag", silver_usd)

    # Limites BVC ±10%
    def _lim(open_p):
        if open_p <= 0: return ""
        h, b = bvc_limits(open_p)
        return f'<div class="lr"><span style="color:#6B7280">±10%</span><span style="color:#9CA3AF">▲{h:,} / ▼{b:,}</span></div>'

    cu_note = (f" | Cu ${copper_usd:,.0f}/T {'+' if copper_usd > MNG_CU_REF else ''}{(copper_usd-MNG_CU_REF)/MNG_CU_REF*100:.1f}% vs ref"
               if copper_usd > 0 else "")
    zn_note = (f" | Zn ${zinc_usd:,.0f}/T" if zinc_usd > 0 else " | Zn: non dispo")

    # ── MODE COMPACT ──────────────────────────────────────────────────────────
    if compact:
        def _mb(ticker, fv, bvc, gap, drv, drv_p, plus1, el, border_col):
            lbl = f"BVC:{bvc:,.0f}" if bvc > 0 else "BVC fermé"
            gc  = "#00C87A" if gap > 0 else ("#FF4560" if gap < 0 else "#C9A84C")
            return (
                f'<div class="mb" style="border-left:2px solid {border_col}">'
                f'<div class="ml">{ticker} ({drv}${drv_p:.1f})</div>'
                f'<div class="mv" style="color:{border_col}">{fv:,.0f}</div>'
                f'<div style="font-size:9px;color:#6B7280">{lbl}</div>'
                f'<div style="font-size:10px;color:{gc}">{gap:+.1f}%</div></div>'
            )
        return (
            '<div class="sec" style="border-color:rgba(201,168,76,.3)">'
            '<div class="st" style="color:#C9A84C">MINES — SIGNAL ÉLASTICITÉ PRIX</div>'
            '<div class="mg">'
            + _mb("SMI", smi_fv, smi_price, smi_gap, "Ag", silver_usd, ag1_smi, smi_el, "#38bdf8")
            + _mb("MNG", mng_fv, mng_price, mng_gap, "Au", gold_usd,   au1_mng, mng_el, "#fbbf24")
            + _mb("CMT", cmt_fv, cmt_price, cmt_gap, "Ag", silver_usd, ag1_cmt, cmt_el, "#a78bfa")
            + f'<div class="mb"><div class="ml">+1% Ag → SMI/CMT</div>'
            + f'<div class="mv go">+{ag1_smi:,.0f}/<br>+{ag1_cmt:,.0f}</div>'
            + f'<div style="font-size:9px;color:#6B7280">MAD</div></div>'
            + '</div>'
            + f'<div style="font-size:9px;color:#4B5563;margin-top:4px">'
            + f'β_smi={smi_bet:.0f} · β_mng={MNG_BETA_OR} · β_cmt={cmt_bet:.0f} MAD/$/oz'
            + cu_note + zn_note + '</div></div>'
        )

    # ── MODE FULL (3 colonnes) ─────────────────────────────────────────────────
    def _col(ticker, color, driver_line, fv, el, beta, plus1, vrow, lim_o, note=""):
        return (
            f'<div>'
            f'<div style="font-size:11px;color:{color};font-weight:700;margin-bottom:6px;font-family:monospace">{ticker}</div>'
            f'<div style="font-size:9px;color:#6B7280;margin-bottom:6px">{driver_line}</div>'
            '<div class="mg" style="margin-bottom:6px">'
            f'<div class="mb"><div class="ml">Théorique</div><div class="mv" style="color:{color}">{fv:,.0f}</div><div style="font-size:9px;color:#6B7280">MAD</div></div>'
            f'<div class="mb"><div class="ml">β local</div><div class="mv go">{beta:.0f}</div><div style="font-size:9px;color:#6B7280">MAD/$</div></div>'
            f'<div class="mb"><div class="ml">Él.</div><div class="mv b">{el:.2f}×</div><div style="font-size:9px;color:#6B7280">+1%</div></div>'
            '</div>'
            f'<div class="lv" style="border-color:{color}30">'
            + vrow + _lim(lim_o) +
            '</div>'
            f'<div style="font-size:10px;color:#6B7280;margin-top:4px">'
            f'+1%→<span style="color:#00C87A">+{plus1:,.0f}MAD</span> · '
            f'+5%→<span style="color:#00C87A">+{plus1*5:,.0f}MAD</span> · '
            f'-5%→<span style="color:#FF4560">{-plus1*5:,.0f}MAD</span></div>'
            + (f'<div style="font-size:9px;color:#4B5563;margin-top:3px">{note}</div>' if note else '')
            + '</div>'
        )

    return (
        '<div class="sec" style="border-color:rgba(201,168,76,.3)">'
        '<div class="st" style="color:#C9A84C">MINES — ÉLASTICITÉ PRIX & VALORISATION FONDAMENTALE</div>'
        f'<div style="font-size:9px;color:#6B7280;margin-bottom:10px">'
        f'SMI: pure argent · MNG: or 48%+cuivre 25%{cu_note} · CMT: argent 65%+zinc/Pb 35%{zn_note}</div>'
        '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">'
        + _col("SMI / IMITER",  "#38bdf8", f"Ag ${silver_usd:.2f}/oz — pure argent",
               smi_fv, smi_el, smi_bet, ag1_smi, smi_vrow, smi_open,
               f"Anchors: $35→2237 · $58→5700 · $73→9220 · $84→12899")
        + _col("MANAGEM",       "#fbbf24", f"Au ${gold_usd:,.0f} + Cu ${copper_usd:,.0f}/T",
               mng_fv, mng_el, MNG_BETA_OR, au1_mng, mng_vrow, mng_open,
               f"Cu déviation: {(copper_usd-MNG_CU_REF)/MNG_CU_REF*100:+.1f}% → FV {'+' if copper_usd>MNG_CU_REF else ''}{mng_copper_delta(copper_usd):+,.0f}MAD" if copper_usd > 0 else "β or calibré · ajust. cuivre +0.25% par 1% Cu")
        + _col("CMT / TIGHZA",  "#a78bfa", f"Ag ${silver_usd:.2f}/oz + Zn ${zinc_usd:,.0f}/T",
               cmt_fv, cmt_el, cmt_bet, ag1_cmt, cmt_vrow, cmt_open,
               f"95g/t Ag · 6.11% Pb · 1.11% Zn · CA Ag~65%, Zn+Pb~35%")
        + '</div>'
        + f'<div style="font-size:9px;color:#4B5563;margin-top:8px">'
        + f'Calibration CMT: Ag$58+Zn$3000→4900 MAD · MNG: or β={MNG_BETA_OR} + Cu poids {MNG_CU_WEIGHT:.0%}'
        + '</div></div>'
    )


def intraday_target(open_price, silver_open, silver_now, ticker="SMI", current_price=0.0):
    """Cible intraday pour brief 05h00 — argent a bougé la nuit."""
    ag_move = (silver_now - silver_open) / silver_open * 100 if silver_open > 0 else 0
    if ticker == "SMI":
        el = smi_elasticity(silver_now, open_price)
    elif ticker == "CMT":
        el = cmt_elasticity(silver_now, open_price)
    else:
        el = mng_elasticity(silver_now, open_price)
    expected_pct = ag_move * el
    target = round(open_price * (1 + expected_pct / 100))
    lim_h, lim_b = bvc_limits(open_price)
    capped   = min(lim_h, max(lim_b, target))
    cap_note = " ⚠️ cappé ±10% BVC" if capped != target else ""
    lines = [
        f"  {ticker} — Cible intraday",
        f"  Ag open/now : ${silver_open:.2f} / ${silver_now:.2f}  ({ag_move:+.2f}%)",
        f"  Élasticité  : {el:.2f}×  →  move attendu {expected_pct:+.2f}%",
        f"  Cible BVC   : {capped:,} MAD{cap_note}",
        f"  Limites     : ▲ {lim_h:,} / ▼ {lim_b:,} MAD",
    ]
    if current_price > 0:
        lines.append(f"  Cours actuel: {current_price:,} MAD  (gap {(current_price-capped)/capped*100:+.1f}%)")
    return "\n".join(lines)
