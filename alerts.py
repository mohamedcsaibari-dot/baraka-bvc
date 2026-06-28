"""
alerts.py — Alertes palier ±1% XAG/XAU → cours théorique SMI / MNG / CMT
Baraka BVC Trading Intelligence Agent v7.3

Logique:
  · Référence = clôture veille (posée chaque matin au job 05h00 UTC)
  · Déclenchement: seuil franchi OU inversion de direction
  · Cooldown 20 min anti-spam (configurable ALERT_COOLDOWN_MIN)
  · État persisté sur Railway Volume /data/commodity_refs.json
  · XAG → impacte SMI (pure argent) + CMT (argent 65% du CA)
  · XAU → impacte MNG (or 48% + cuivre 25%)
"""

import json
import os
import time
from pathlib import Path
from fundamentals import (
    smi_fair_value, mng_fair_value, cmt_fair_value,
    smi_local_beta, smi_elasticity,
    mng_elasticity,
    cmt_local_beta_ag, cmt_elasticity,
    MNG_CU_REF,
)

# ══ Config ════════════════════════════════════════════════════════════════════
DATA_DIR      = Path(os.getenv("DATA_DIR", "/tmp"))
STATE_FILE    = DATA_DIR / "commodity_refs.json"
THRESHOLD_PCT = float(os.getenv("ALERT_THRESHOLD_PCT", "1.0"))
COOLDOWN_MIN  = float(os.getenv("ALERT_COOLDOWN_MIN",  "20"))


# ── State ─────────────────────────────────────────────────────────────────────

def _load() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {
            "silver_ref": 0.0, "gold_ref": 0.0,
            "last_ts": 0.0,
            "last_ag_dir": None,   # direction argent → SMI
            "last_ag_dir_cmt": None,  # direction argent → CMT (tracker séparé)
            "last_au_dir": None,   # direction or    → MNG
        }

def _save(state: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ── API ───────────────────────────────────────────────────────────────────────

def set_daily_reference(silver_close: float, gold_close: float):
    """
    Appeler au job 05h00 UTC.
    Pose la référence du jour et remet le cooldown + directions à zéro.
    """
    state = _load()
    state.update({
        "silver_ref":      float(silver_close),
        "gold_ref":        float(gold_close),
        "last_ts":         0.0,
        "last_ag_dir":     None,
        "last_ag_dir_cmt": None,
        "last_au_dir":     None,
    })
    _save(state)
    print(f"[ALERTS] Référence posée — Ag ${silver_close:.2f}  Au ${gold_close:.0f}")


def check_alerts(
    silver_now  : float,
    gold_now    : float,
    smi_price   : float = 0.0,
    mng_price   : float = 0.0,
    cmt_price   : float = 0.0,
    copper_now  : float = 0.0,
    zinc_now    : float = 0.0,
) -> list:
    """
    Vérifie si ±THRESHOLD_PCT est franchi depuis la référence.
    XAG → SMI + CMT (deux alertes distinctes)
    XAU → MNG (avec cuivre en contexte)
    Retourne liste d'alertes (vide = cooldown actif ou rien à signaler).
    """
    state = _load()
    now   = time.time()

    # Cooldown global
    if now - state.get("last_ts", 0.0) < COOLDOWN_MIN * 60:
        return []

    alerts  = []
    changed = False
    ag_ref  = state.get("silver_ref", 0.0)
    au_ref  = state.get("gold_ref",   0.0)

    # ── ARGENT → SMI ─────────────────────────────────────────────────────────
    if ag_ref > 0 and silver_now > 0:
        ag_move = (silver_now - ag_ref) / ag_ref * 100
        ag_dir  = "up" if ag_move > 0 else "down"
        if abs(ag_move) >= THRESHOLD_PCT and ag_dir != state.get("last_ag_dir"):
            smi_fv  = smi_fair_value(silver_now)
            smi_gap = (smi_fv - smi_price) / smi_price * 100 if smi_price > 0 else None
            alerts.append({
                "commodity":   "ARGENT",
                "symbol":      "XAG",
                "stock":       "SMI",
                "move_pct":    round(ag_move, 2),
                "price_now":   silver_now,
                "price_ref":   ag_ref,
                "fv_mad":      round(smi_fv),
                "bvc_mad":     round(smi_price) if smi_price > 0 else None,
                "gap_pct":     round(smi_gap, 1) if smi_gap is not None else None,
                "beta":        round(smi_local_beta(silver_now)),
                "elasticity":  smi_elasticity(silver_now, smi_price or smi_fv),
                "direction":   ag_dir,
                "note":        f"SMI pure argent · β={round(smi_local_beta(silver_now))} MAD/$/oz",
            })
            state["last_ag_dir"] = ag_dir
            changed = True

    # ── ARGENT → CMT ─────────────────────────────────────────────────────────
    if ag_ref > 0 and silver_now > 0:
        ag_move = (silver_now - ag_ref) / ag_ref * 100
        ag_dir  = "up" if ag_move > 0 else "down"
        if abs(ag_move) >= THRESHOLD_PCT and ag_dir != state.get("last_ag_dir_cmt"):
            cmt_fv   = cmt_fair_value(silver_now, zinc_now)
            cmt_gap  = (cmt_fv - cmt_price) / cmt_price * 100 if cmt_price > 0 else None
            cmt_bet  = cmt_local_beta_ag(silver_now, cmt_price or cmt_fv)
            cmt_el   = cmt_elasticity(silver_now, cmt_price or cmt_fv, zinc_now)
            zn_ctx   = (f" · Zn ${zinc_now:,.0f}/T" if zinc_now > 0 else " · Zn n.d.")
            alerts.append({
                "commodity":   "ARGENT→CMT",
                "symbol":      "XAG",
                "stock":       "CMT",
                "move_pct":    round(ag_move, 2),
                "price_now":   silver_now,
                "price_ref":   ag_ref,
                "fv_mad":      round(cmt_fv),
                "bvc_mad":     round(cmt_price) if cmt_price > 0 else None,
                "gap_pct":     round(cmt_gap, 1) if cmt_gap is not None else None,
                "beta":        cmt_bet,
                "elasticity":  cmt_el,
                "direction":   ag_dir,
                "note":        f"CMT Tighza 95g/t Ag · Ag 65%+Zn+Pb 35%{zn_ctx}",
            })
            state["last_ag_dir_cmt"] = ag_dir
            changed = True

    # ── OR → MANAGEM ─────────────────────────────────────────────────────────
    if au_ref > 0 and gold_now > 0:
        au_move = (gold_now - au_ref) / au_ref * 100
        au_dir  = "up" if au_move > 0 else "down"
        if abs(au_move) >= THRESHOLD_PCT and au_dir != state.get("last_au_dir"):
            mng_fv  = mng_fair_value(gold_now, copper_now)
            mng_gap = (mng_fv - mng_price) / mng_price * 100 if mng_price > 0 else None
            cu_ctx  = (f" · Cu ${copper_now:,.0f}/T {(copper_now-MNG_CU_REF)/MNG_CU_REF*100:+.1f}% vs réf"
                       if copper_now > 0 else " · Cu n.d.")
            alerts.append({
                "commodity":   "OR",
                "symbol":      "XAU",
                "stock":       "MNG",
                "move_pct":    round(au_move, 2),
                "price_now":   gold_now,
                "price_ref":   au_ref,
                "fv_mad":      round(mng_fv),
                "bvc_mad":     round(mng_price) if mng_price > 0 else None,
                "gap_pct":     round(mng_gap, 1) if mng_gap is not None else None,
                "beta":        3.43,
                "elasticity":  mng_elasticity(gold_now, mng_price or mng_fv, copper_now),
                "direction":   au_dir,
                "note":        f"MNG: or 48%+cuivre 25%{cu_ctx}",
            })
            state["last_au_dir"] = au_dir
            changed = True

    if changed:
        state["last_ts"] = now
        _save(state)

    return alerts


def format_alert(alerts: list) -> tuple:
    """Retourne (subject, html_body) prêt pour Resend."""
    # Subject basé sur la première alerte
    a0    = alerts[0]
    arrow = "▲" if a0["move_pct"] > 0 else "▼"
    stocks_str = " / ".join(a["stock"] for a in alerts)
    fv_str     = " / ".join(str(a["fv_mad"]) for a in alerts)
    subject    = (
        f"BARAKA ALERT -- {a0['commodity']} "
        f"{arrow}{abs(a0['move_pct']):.1f}% -- "
        f"{stocks_str} theo {fv_str} MAD"
    )

    lines = [
        f"⚡ BARAKA — ALERTE PALIER ±{THRESHOLD_PCT:.0f}%",
        "─" * 50, "",
    ]
    for a in alerts:
        arr  = "▲" if a["move_pct"] > 0 else "▼"
        verb = "HAUSSE" if a["move_pct"] > 0 else "BAISSE"
        el   = a["elasticity"]
        fv   = a["fv_mad"]
        th   = THRESHOLD_PCT

        lines += [
            f"  {arr} {a['commodity']} ({a['symbol']}) → {a['stock']}   {a['move_pct']:+.2f}%",
            f"  Cours actuel : ${a['price_now']:.2f}/oz",
            f"  Référence    : ${a['price_ref']:.2f}/oz",
            f"  β / él.      : {a['beta']} MAD/$  ·  {el:.2f}×",
            f"  Note         : {a.get('note','')}",
            "",
            f"  {a['stock']} THÉORIQUE  :  {fv:,} MAD",
        ]
        if a["bvc_mad"] and a["gap_pct"] is not None:
            gap_lbl = ("← retard BVC" if (a["gap_pct"] or 0) > 3 else
                       "← BVC en avance" if (a["gap_pct"] or 0) < -3 else "← aligné")
            lines += [
                f"  {a['stock']} BVC actuel :  {a['bvc_mad']:,} MAD",
                f"  Gap BVC/théo :  {a['gap_pct']:+.1f}%  {gap_lbl}",
            ]
        lines += [
            "",
            f"  Si {a['commodity'].split('→')[0].strip()} continue {verb} +{th:.0f}%/step :",
            f"    +{th:.0f}%  →  {round(fv * (1 + el * th/100)):,} MAD",
            f"    −{th:.0f}%  →  {round(fv * (1 - el * th/100)):,} MAD",
            "", "─" * 50, "",
        ]

    lines.append("→ Vérifier cours BVC et ajuster si nécessaire.")
    return subject, "\n".join(lines)
