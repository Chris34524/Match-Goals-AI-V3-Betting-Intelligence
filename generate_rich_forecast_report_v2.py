#!/usr/bin/env python3

import argparse
import html
import json
import math
import shutil
from pathlib import Path


# ============================================================
# CONFIG
# ============================================================

MARKET_LABELS = {
    "Over1.5": "Más de 1.5",
    "Over2.5": "Más de 2.5",
    "Over3.5": "Más de 3.5",
    "BTTS": "Ambos anotan",
    "HomeWin": "Gana local",
    "Draw": "Empate",
    "AwayWin": "Gana visitante",
    "1X": "Doble oportunidad 1X",
    "X2": "Doble oportunidad X2",
    "12": "Sin empate",
}

NON_STANDARD_HINTS = (
    "kings",
    "baller",
    "6x6",
    "5x5",
    "esoccer",
    "e-soccer",
    "cyber",
    "virtual",
)

REQUIRED_ARTIFACTS = (
    "history.json",
    "standings.json",
    "xg_history.json",
    "enriched.json",
    "h2h_analysis.json",
    "lambda_comparison.json",
    "result.json",
)


# ============================================================
# BASIC HELPERS
# ============================================================

def load_json(path, default=None):
    if default is None:
        default = {}

    try:
        return json.loads(
            Path(path).read_text(encoding="utf-8")
        )
    except Exception:
        return default


def esc(value):
    if value is None:
        return "—"

    return html.escape(str(value))


def num(value, decimals=2):
    try:
        return f"{float(value):.{decimals}f}"
    except Exception:
        return "—"


def probability_pct(value):
    """
    Probability expected in [0, 1].
    """
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "—"


def percent_any(value):
    """
    Supports either:
      0.72 -> 72.0%
      72.0 -> 72.0%
    """
    try:
        value = float(value)

        if -1 <= value <= 1:
            value *= 100

        return f"{value:.1f}%"
    except Exception:
        return "—"


def fair_odds(probability):
    try:
        probability = float(probability)

        if probability <= 0:
            return "—"

        return f"{1 / probability:.2f}"
    except Exception:
        return "—"


def safe_div(a, b):
    try:
        a = float(a)
        b = float(b)

        if not b:
            return None

        return a / b
    except Exception:
        return None


def artifact_state(path):
    return "AVAILABLE" if Path(path).is_file() else "MISSING"


# ============================================================
# SOURCE NORMALIZATION
# ============================================================

def normalize_source(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in (
            "partidos",
            "matches",
            "fixtures",
            "data",
        ):
            value = data.get(key)

            if isinstance(value, list):
                return value

    return []


def source_match_id(row):
    return str(
        row.get("id")
        or row.get("match_id")
        or row.get("fixture_id")
        or ""
    )


# ============================================================
# FORECAST
# ============================================================

def forecast_map(forecast):
    result = {}

    for group in forecast.get("matches", []):
        mid = str(group.get("internal_match_id") or "")

        if not mid:
            picks = group.get(
                "ranked_forecast_candidates",
                [],
            )

            if picks:
                mid = str(
                    picks[0].get("internal_match_id")
                    or ""
                )

        if mid:
            result[mid] = group

    return result


def picks_by_market(group):
    result = {}

    for pick in group.get(
        "ranked_forecast_candidates",
        [],
    ):
        market = pick.get("market")

        if market:
            result[str(market)] = pick

    return result


def probability_of(markets, market):
    pick = markets.get(market) or {}

    value = pick.get("probability")

    if value is None:
        value = pick.get("model_probability")

    try:
        return float(value)
    except Exception:
        return None


# ============================================================
# ARTIFACT ANALYSIS
# ============================================================

def champion_lambda(lambdas, group):
    methods = (
        lambdas.get("metodos", {})
        if isinstance(lambdas, dict)
        else {}
    )

    champion = (
        methods.get("J_BT_sin_temporada")
        or {}
    )

    local = (
        champion.get("local")
        if champion.get("local") is not None
        else champion.get("lambda_local")
    )

    away = (
        champion.get("visitante")
        if champion.get("visitante") is not None
        else champion.get("lambda_visitante")
    )

    total = champion.get("total")

    if total is None:
        total = champion.get("lambda_total")

    # Forecast fallback.
    picks = group.get(
        "ranked_forecast_candidates",
        [],
    )

    first = picks[0] if picks else {}

    if local is None:
        local = first.get("lambda_home")

    if away is None:
        away = first.get("lambda_away")

    if total is None:
        total = first.get("lambda_total")

    return local, away, total


def quality_information(result, lambdas):
    calidad = (
        result.get("calidad_datos", {})
        if isinstance(result, dict)
        else {}
    )

    forma = calidad.get("forma") or {}
    xg = calidad.get("xg") or {}
    h2h = calidad.get("h2h") or {}
    standings = calidad.get("standings") or {}

    fl = (forma.get("local") or {}).get("n") or 0
    fa = (forma.get("visitante") or {}).get("n") or 0

    xgl = (xg.get("local") or {}).get("cobertura") or 0
    xga = (xg.get("visitante") or {}).get("cobertura") or 0

    h2hn = h2h.get("n") or 0

    standings_ok = (
        standings.get("estado") == "ok"
    )

    champion = (
        (lambdas.get("metodos") or {})
        .get("J_BT_sin_temporada")
        if isinstance(lambdas, dict)
        else None
    )

    temporal_ok = (
        (result.get("integridad_temporal") or {})
        .get("estado")
        == "OK"
        if isinstance(result, dict)
        else False
    )

    score = 0.0

    score += min(float(fl) / 20, 1) * 15
    score += min(float(fa) / 20, 1) * 15

    score += min(float(xgl), 1) * 12.5
    score += min(float(xga), 1) * 12.5

    score += min(float(h2hn) / 10, 1) * 15

    if standings_ok:
        score += 10

    if champion:
        score += 10

    if temporal_ok:
        score += 10

    if score >= 75:
        label = "ALTA"
    elif score >= 50:
        label = "MEDIA"
    else:
        label = "BAJA"

    return {
        "score": round(score, 1),
        "label": label,
        "forma_local": fl,
        "forma_visitante": fa,
        "xg_local": xgl,
        "xg_visitante": xga,
        "h2h": h2hn,
        "standings": standings_ok,
        "lambda": bool(champion),
        "temporal": temporal_ok,
    }


# ============================================================
# HTML TABLES
# ============================================================

def standings_html(standings):
    if (
        not isinstance(standings, dict)
        or standings.get("estado") != "ok"
    ):
        return (
            '<p class="muted">'
            'Clasificación no disponible.'
            '</p>'
        )

    rows = []

    for side, label in (
        ("local", "LOCAL"),
        ("visitante", "VISITANTE"),
    ):
        d = standings.get(side) or {}

        pj = d.get("pj")
        pts = d.get("puntos")
        gf = d.get("gf")
        gc = d.get("gc")

        rows.append(
            f"""
            <tr>
              <td><span class="side">{label}</span></td>
              <td><strong>{esc(d.get("equipo"))}</strong></td>
              <td>{esc(d.get("posicion"))}</td>
              <td>{esc(pj)}</td>
              <td>{esc(pts)}</td>
              <td>{num(safe_div(pts, pj))}</td>
              <td>{esc(gf)}</td>
              <td>{esc(gc)}</td>
              <td>{esc(d.get("dg"))}</td>
              <td>{num(safe_div(gf, pj))}</td>
              <td>{num(safe_div(gc, pj))}</td>
            </tr>
            """
        )

    return f"""
    <div class="table-wrap">
      <table class="detail-table">
        <thead>
          <tr>
            <th></th>
            <th>Equipo</th>
            <th>Pos.</th>
            <th>PJ</th>
            <th>Pts</th>
            <th>Pts/PJ</th>
            <th>GF</th>
            <th>GC</th>
            <th>DG</th>
            <th>GF/PJ</th>
            <th>GC/PJ</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </div>
    """


def form_team_html(team_name, data, venue_key):
    rows = []

    for window, label in (
        ("l5", "L5"),
        ("l10", "L10"),
        ("l20", "L20"),
        (venue_key, "LOCAL" if venue_key == "como_local" else "VISITANTE"),
    ):
        d = (
            data.get(window)
            if isinstance(data, dict)
            else None
        )

        if not isinstance(d, dict):
            continue

        def stat(name):
            value = d.get(name)

            if isinstance(value, dict):
                return value.get("porcentaje")

            return None

        rows.append(
            f"""
            <tr>
              <td><strong>{label}</strong></td>
              <td>{esc(d.get("pj"))}</td>
              <td>{num(d.get("promedio_gf"))}</td>
              <td>{num(d.get("promedio_gc"))}</td>
              <td>{num(d.get("promedio_total_goles"))}</td>
              <td>{percent_any(stat("over_1_5"))}</td>
              <td>{percent_any(stat("over_2_5"))}</td>
              <td>{percent_any(stat("over_3_5"))}</td>
              <td>{percent_any(stat("btts"))}</td>
              <td>{esc(d.get("victorias"))}</td>
              <td>{esc(d.get("empates"))}</td>
              <td>{esc(d.get("derrotas"))}</td>
            </tr>
            """
        )

    if not rows:
        return (
            '<p class="muted">'
            'Forma no disponible.'
            '</p>'
        )

    return f"""
    <h4>{esc(team_name)}</h4>

    <div class="table-wrap">
      <table class="detail-table">
        <thead>
          <tr>
            <th>Ventana</th>
            <th>PJ</th>
            <th>GF/PJ</th>
            <th>GC/PJ</th>
            <th>TG/PJ</th>
            <th>O1.5</th>
            <th>O2.5</th>
            <th>O3.5</th>
            <th>BTTS</th>
            <th>G</th>
            <th>E</th>
            <th>P</th>
          </tr>
        </thead>

        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </div>
    """


def xg_summary_html(xg, home, away):
    cards = []

    for side, name in (
        ("local", home),
        ("visitante", away),
    ):
        team = (
            xg.get(side, {})
            if isinstance(xg, dict)
            else {}
        )

        windows = []

        for window in ("l5", "l10"):
            d = team.get(window) or {}

            windows.append(
                f"""
                <div class="xg-window">
                  <strong>{window.upper()}</strong>

                  <div>
                    <small>Cobertura</small>
                    <b>
                      {esc(d.get("partidos_con_xg"))}
                      /
                      {esc(d.get("partidos_considerados"))}
                    </b>
                  </div>

                  <div>
                    <small>% cobertura</small>
                    <b>{percent_any(d.get("cobertura_xg"))}</b>
                  </div>

                  <div>
                    <small>xGF/PJ</small>
                    <b>{num(d.get("xgf_promedio"), 3)}</b>
                  </div>

                  <div>
                    <small>xGA/PJ</small>
                    <b>{num(d.get("xga_promedio"), 3)}</b>
                  </div>
                </div>
                """
            )

        cards.append(
            f"""
            <div class="sub-card">
              <h4>{esc(name)}</h4>
              {''.join(windows)}
            </div>
            """
        )

    return (
        '<div class="two-cols">'
        + "".join(cards)
        + "</div>"
    )


def xg_history_html(xg):
    blocks = []

    for side, label in (
        ("local", "LOCAL"),
        ("visitante", "VISITANTE"),
    ):
        team = (
            xg.get(side, {})
            if isinstance(xg, dict)
            else {}
        )

        matches = team.get("partidos") or []

        rows = []

        for p in matches[:10]:
            if p.get("xg_disponible"):
                xg_score = (
                    f"{num(p.get('xg_local'))}"
                    " - "
                    f"{num(p.get('xg_visitante'))}"
                )
                state = "OK"
            else:
                xg_score = "No disponible"
                state = "SIN xG"

            score = (
                f"{esc(p.get('goles_local'))}"
                " - "
                f"{esc(p.get('goles_visitante'))}"
            )

            rows.append(
                f"""
                <tr>
                  <td>{esc(p.get("fecha"))}</td>
                  <td>{esc(p.get("local"))}</td>
                  <td class="score">{score}</td>
                  <td>{esc(p.get("visitante"))}</td>
                  <td>{xg_score}</td>
                  <td>{state}</td>
                </tr>
                """
            )

        if rows:
            blocks.append(
                f"""
                <h4>{label}: {esc(team.get("equipo"))}</h4>

                <div class="table-wrap">
                  <table class="detail-table">
                    <thead>
                      <tr>
                        <th>Fecha</th>
                        <th>Local</th>
                        <th>Marcador</th>
                        <th>Visitante</th>
                        <th>xG local - visitante</th>
                        <th>Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {''.join(rows)}
                    </tbody>
                  </table>
                </div>
                """
            )

    if not blocks:
        return (
            '<p class="muted">'
            'Historial xG no disponible.'
            '</p>'
        )

    return "".join(blocks)


def h2h_html(h2h):
    if not isinstance(h2h, dict):
        return '<p class="muted">H2H no disponible.</p>'

    rows = []

    for key, label in (
        ("h5", "H5"),
        ("h10", "H10"),
        ("h20", "H20"),
        ("ponderado_recencia", "PONDERADO"),
    ):
        d = h2h.get(key)

        if not isinstance(d, dict):
            continue

        if not d.get("n"):
            continue

        rows.append(
            f"""
            <tr>
              <td><strong>{label}</strong></td>
              <td>{esc(d.get("n"))}</td>
              <td>{num(d.get("gf_local_promedio"))}</td>
              <td>{num(d.get("gf_visitante_promedio"))}</td>
              <td>{num(d.get("total_promedio"))}</td>
              <td>{percent_any(d.get("p_2_mas"))}</td>
              <td>{percent_any(d.get("p_3_mas"))}</td>
              <td>{percent_any(d.get("p_4_mas"))}</td>
              <td>{percent_any(d.get("p_menos_2"))}</td>
              <td>{percent_any(d.get("p_menos_3"))}</td>
              <td>{percent_any(d.get("p_menos_4"))}</td>
              <td>{percent_any(d.get("btts"))}</td>
              <td>{percent_any(d.get("victoria_local"))}</td>
              <td>{percent_any(d.get("empate"))}</td>
              <td>{percent_any(d.get("victoria_visitante"))}</td>
            </tr>
            """
        )

    if not rows:
        return (
            '<p class="muted">'
            'Sin enfrentamientos directos válidos.'
            '</p>'
        )

    return f"""
    <div class="table-wrap">
      <table class="detail-table wide">
        <thead>
          <tr>
            <th>Ventana</th>
            <th>N</th>
            <th>GF local</th>
            <th>GF visita</th>
            <th>TG/PJ</th>
            <th>O1.5</th>
            <th>O2.5</th>
            <th>O3.5</th>
            <th>U1.5</th>
            <th>U2.5</th>
            <th>U3.5</th>
            <th>BTTS</th>
            <th>1</th>
            <th>X</th>
            <th>2</th>
          </tr>
        </thead>

        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </div>
    """


def h2h_matches_html(h2h):
    matches = (
        h2h.get("partidos", [])
        if isinstance(h2h, dict)
        else []
    )

    if not matches:
        return (
            '<p class="muted">'
            'Sin partidos H2H disponibles.'
            '</p>'
        )

    rows = []

    for p in matches[:20]:
        rows.append(
            f"""
            <tr>
              <td>{esc(p.get("fecha"))}</td>
              <td>{esc(p.get("competicion"))}</td>
              <td>{esc(p.get("orientacion"))}</td>
              <td>{esc(p.get("goles_equipo_local"))}</td>
              <td>{esc(p.get("goles_equipo_visitante"))}</td>
              <td>{esc(p.get("total_goles"))}</td>
              <td>{"Sí" if p.get("btts") else "No"}</td>
            </tr>
            """
        )

    return f"""
    <div class="table-wrap">
      <table class="detail-table">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Competición</th>
            <th>Orientación</th>
            <th>GF local</th>
            <th>GF visita</th>
            <th>Total</th>
            <th>BTTS</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </div>
    """


def lambda_html(lambdas):
    methods = (
        lambdas.get("metodos", {})
        if isinstance(lambdas, dict)
        else {}
    )

    if not methods:
        return (
            '<p class="muted">'
            'Comparador λ no disponible.'
            '</p>'
        )

    rows = []

    for method, d in methods.items():
        if not isinstance(d, dict):
            continue

        local = (
            d.get("local")
            if d.get("local") is not None
            else d.get("lambda_local")
        )

        away = (
            d.get("visitante")
            if d.get("visitante") is not None
            else d.get("lambda_visitante")
        )

        total = (
            d.get("total")
            if d.get("total") is not None
            else d.get("lambda_total")
        )

        champion = (
            method == "J_BT_sin_temporada"
        )

        css = " champion-row" if champion else ""

        badge = (
            '<span class="champion-badge">CHAMPION</span>'
            if champion
            else ""
        )

        rows.append(
            f"""
            <tr class="{css.strip()}">
              <td>
                <strong>{esc(method)}</strong>
                {badge}
              </td>
              <td>{num(local, 3)}</td>
              <td>{num(away, 3)}</td>
              <td>{num(total, 3)}</td>
            </tr>
            """
        )

    return f"""
    <div class="table-wrap">
      <table class="detail-table lambda-table">
        <thead>
          <tr>
            <th>Método</th>
            <th>λ local</th>
            <th>λ visita</th>
            <th>λ total</th>
          </tr>
        </thead>

        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </div>
    """


def scenarios_html(result):
    scenarios = (
        result.get("escenarios", {})
        if isinstance(result, dict)
        else {}
    )

    if not scenarios:
        return (
            '<p class="muted">'
            'Escenarios experimentales no disponibles.'
            '</p>'
        )

    rows = []

    for name in (
        "J_base",
        "P_H2H10",
        "Q_H2H15",
        "R_H2H20",
    ):
        d = scenarios.get(name)

        if not isinstance(d, dict):
            continue

        lam = d.get("lambda") or {}
        one = d.get("resultado_1x2") or {}
        goals = d.get("goles_medio") or {}
        btts = d.get("btts") or {}

        rows.append(
            f"""
            <tr>
              <td><strong>{esc(name)}</strong></td>
              <td>{num(lam.get("total"), 3)}</td>
              <td>{percent_any(one.get("1"))}</td>
              <td>{percent_any(one.get("X"))}</td>
              <td>{percent_any(one.get("2"))}</td>
              <td>{percent_any(goals.get("+1.5"))}</td>
              <td>{percent_any(goals.get("+2.5"))}</td>
              <td>{percent_any(goals.get("+3.5"))}</td>
              <td>{percent_any(goals.get("+4.5"))}</td>
              <td>{percent_any(btts.get("si"))}</td>
            </tr>
            """
        )

    if not rows:
        return (
            '<p class="muted">'
            'Escenarios experimentales no disponibles.'
            '</p>'
        )

    return f"""
    <div class="table-wrap">
      <table class="detail-table">
        <thead>
          <tr>
            <th>Escenario</th>
            <th>λ total</th>
            <th>1</th>
            <th>X</th>
            <th>2</th>
            <th>O1.5</th>
            <th>O2.5</th>
            <th>O3.5</th>
            <th>O4.5</th>
            <th>BTTS</th>
          </tr>
        </thead>

        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </div>

    <p class="muted small">
      Diagnóstico experimental.
      El Champion vigente sigue siendo
      BT0 / J_BT_sin_temporada.
    </p>
    """


def likely_scores_html(result):
    scenarios = (
        result.get("escenarios", {})
        if isinstance(result, dict)
        else {}
    )

    base = scenarios.get("J_base") or {}

    scores = base.get("marcadores_probables") or []

    if not scores:
        return (
            '<p class="muted">'
            'Marcadores probables no disponibles.'
            '</p>'
        )

    cards = []

    for item in scores[:5]:
        cards.append(
            f"""
            <div class="score-card">
              <strong>{esc(item.get("marcador"))}</strong>
              <span>{probability_pct(item.get("probabilidad"))}</span>
            </div>
            """
        )

    return (
        '<div class="score-grid">'
        + "".join(cards)
        + "</div>"
    )


# ============================================================
# PICK SELECTION
# ============================================================

def is_standard_competition(target):
    text = " ".join(
        str(target.get(k) or "")
        for k in (
            "pais",
            "competicion",
            "local",
            "visitante",
        )
    ).lower()

    return not any(
        hint in text
        for hint in NON_STANDARD_HINTS
    )


def choose_primary_pick(markets, quality):
    candidates = []

    config = {
        "Over2.5": (0.58, 1.10),
        "BTTS": (0.58, 1.08),
        "Over1.5": (0.78, 0.94),
        "HomeWin": (0.50, 1.00),
        "AwayWin": (0.50, 1.00),
        "Over3.5": (0.45, 1.00),
        "1X": (0.66, 0.88),
        "X2": (0.66, 0.88),
        "12": (0.70, 0.86),
    }

    q_factor = {
        "ALTA": 1.0,
        "MEDIA": 0.92,
        "BAJA": 0.76,
    }.get(quality["label"], 0.76)

    for market, (minimum, weight) in config.items():
        p = probability_of(markets, market)

        if p is None or p < minimum:
            continue

        score = p * weight * q_factor

        candidates.append(
            (
                score,
                market,
                p,
            )
        )

    if not candidates:
        return {
            "market": None,
            "probability": None,
            "score": 0,
        }

    candidates.sort(reverse=True)

    score, market, p = candidates[0]

    return {
        "market": market,
        "probability": p,
        "score": score,
    }


# ============================================================
# CSS / JS
# ============================================================

CSS = r"""
:root {
  --bg:#08101f;
  --panel:#101a2e;
  --panel2:#141f36;
  --line:#273756;
  --text:#f1f5ff;
  --muted:#8ea5cb;
  --blue:#73adff;
  --green:#56d9a4;
  --yellow:#f2c46e;
  --red:#ff7d86;
  --purple:#b69cff;
}

* {
  box-sizing:border-box;
}

html {
  scroll-behavior:smooth;
}

body {
  margin:0;
  background:
    linear-gradient(
      180deg,
      #07101e,
      #0a1020
    );
  color:var(--text);
  font-family:
    Inter,
    "Segoe UI",
    Arial,
    sans-serif;
}

.container {
  max-width:1580px;
  margin:auto;
  padding:28px;
}

a {
  color:var(--blue);
  text-decoration:none;
}

h1 {
  margin:0 0 6px;
  font-size:32px;
}

h2 {
  margin-top:36px;
  margin-bottom:14px;
}

h3 {
  margin-top:24px;
}

h4 {
  margin:0 0 12px;
}

.muted {
  color:var(--muted);
}

.small {
  font-size:12px;
}

.nav {
  display:flex;
  flex-wrap:wrap;
  gap:9px;
  margin:16px 0 22px;
}

.button {
  padding:9px 13px;
  background:var(--panel);
  border:1px solid var(--line);
  border-radius:9px;
}

.hero {
  padding:22px;
  border:1px solid var(--line);
  background:var(--panel);
  border-radius:17px;
}

.grid {
  display:grid;
  grid-template-columns:
    repeat(
      auto-fit,
      minmax(190px,1fr)
    );
  gap:12px;
}

.two-cols {
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:14px;
}

.card,
.sub-card {
  padding:15px;
  background:var(--panel);
  border:1px solid var(--line);
  border-radius:14px;
}

.sub-card {
  background:var(--panel2);
}

.metric-title {
  color:var(--muted);
  font-size:13px;
}

.metric-value {
  margin-top:5px;
  font-size:26px;
  font-weight:800;
}

.fair {
  color:var(--muted);
  font-size:12px;
  margin-top:4px;
}

.note {
  padding:14px;
  background:#0d172b;
  border:1px solid var(--line);
  border-left:4px solid var(--blue);
  border-radius:10px;
}

.quality-high {
  color:var(--green);
}

.quality-medium {
  color:var(--yellow);
}

.quality-low {
  color:var(--red);
}

.table-wrap {
  width:100%;
  overflow-x:auto;
  margin-top:10px;
  border:1px solid var(--line);
  border-radius:11px;
}

table {
  width:100%;
  border-collapse:collapse;
  background:var(--panel);
}

th,
td {
  padding:10px 11px;
  border-bottom:1px solid var(--line);
  text-align:left;
  vertical-align:middle;
  white-space:nowrap;
  font-size:13px;
}

/*
IMPORTANT:
NO global sticky rule.
*/
th {
  color:#d7e4ff;
  background:#17223b;
}

/*
Only GLOBAL may use sticky TH.
*/
.global-scroll {
  max-height:78vh;
  overflow:auto;
  border:1px solid var(--line);
  border-radius:12px;
}

.global-table thead th {
  position:sticky;
  top:0;
  z-index:2;
}

/*
ALL DETAIL TABLES ARE STATIC.
*/
.detail-table thead th,
.lambda-table thead th {
  position:static;
  top:auto;
}

.detail-table {
  min-width:760px;
}

.wide {
  min-width:1200px;
}

.lambda-table {
  min-width:720px;
}

.lambda-table td:first-child {
  min-width:280px;
}

.champion-row {
  background:
    rgba(
      86,
      217,
      164,
      .10
    );
}

.champion-badge {
  display:inline-block;
  margin-left:8px;
  padding:3px 7px;
  border-radius:999px;
  background:var(--green);
  color:#07110d;
  font-size:10px;
  font-weight:900;
}

.side {
  color:var(--blue);
  font-size:11px;
  font-weight:800;
}

.score {
  font-weight:800;
  text-align:center;
}

.xg-window {
  display:grid;
  grid-template-columns:
    60px repeat(4,1fr);
  gap:8px;
  padding:10px 0;
  border-top:1px solid var(--line);
}

.xg-window small {
  display:block;
  color:var(--muted);
  margin-bottom:3px;
}

.score-grid {
  display:grid;
  grid-template-columns:
    repeat(
      auto-fit,
      minmax(120px,1fr)
    );
  gap:10px;
}

.score-card {
  padding:12px;
  border:1px solid var(--line);
  background:var(--panel2);
  border-radius:10px;
}

.score-card strong {
  display:block;
  font-size:22px;
}

.score-card span {
  color:var(--muted);
}

.pick-card {
  padding:15px;
  background:var(--panel);
  border:1px solid var(--line);
  border-radius:14px;
}

.pick-market {
  color:var(--green);
  font-size:22px;
  font-weight:800;
}

.filters {
  display:flex;
  flex-wrap:wrap;
  gap:10px;
  margin:18px 0;
}

.filters input,
.filters select {
  padding:10px;
  background:#0d1729;
  color:var(--text);
  border:1px solid var(--line);
  border-radius:8px;
}

.status-ok {
  color:var(--green);
}

.status-bad {
  color:var(--red);
}

.artifact-available {
  color:var(--green);
}

.artifact-missing {
  color:var(--red);
}

footer {
  margin:35px 0;
  color:var(--muted);
  font-size:12px;
}

@media (max-width:900px) {
  .two-cols {
    grid-template-columns:1fr;
  }

  .container {
    padding:14px;
  }

  .xg-window {
    grid-template-columns:1fr 1fr;
  }
}
"""


JS = r"""
function filterGlobal() {
  const q =
    (document.getElementById("search")?.value || "")
    .toLowerCase();

  const country =
    document.getElementById("country")?.value || "";

  const quality =
    document.getElementById("quality")?.value || "";

  const status =
    document.getElementById("status")?.value || "";

  document
    .querySelectorAll("#global-body tr")
    .forEach(row => {
      const text =
        row.innerText.toLowerCase();

      const visible =
        (!q || text.includes(q))
        &&
        (!country || row.dataset.country === country)
        &&
        (!quality || row.dataset.quality === quality)
        &&
        (!status || row.dataset.status === status);

      row.style.display =
        visible ? "" : "none";
    });
}
"""


# ============================================================
# REPORT
# ============================================================

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        required=True,
    )

    parser.add_argument(
        "--source",
        required=True,
    )

    parser.add_argument(
        "--forecast",
        required=True,
    )

    parser.add_argument(
        "--output",
        required=True,
    )

    args = parser.parse_args()

    root = Path(".")
    matches_root = root / "data" / "matches"

    source = normalize_source(
        load_json(args.source, [])
    )

    forecast = load_json(args.forecast, {})

    forecast_groups = forecast_map(forecast)

    output = Path(args.output)
    details_dir = output / "details"
    assets_dir = output / "assets"

    if output.exists():
        shutil.rmtree(output)

    details_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    assets_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (assets_dir / "report.css").write_text(
        CSS,
        encoding="utf-8",
    )

    (assets_dir / "report.js").write_text(
        JS,
        encoding="utf-8",
    )

    records = []

    for index, target in enumerate(source, 1):
        mid = source_match_id(target)

        folder = matches_root / mid

        group = forecast_groups.get(mid, {})

        markets = picks_by_market(group)

        enriched = load_json(
            folder / "enriched.json",
            {},
        )

        standings = load_json(
            folder / "standings.json",
            {},
        )

        xg = load_json(
            folder / "xg_history.json",
            {},
        )

        h2h = load_json(
            folder / "h2h_analysis.json",
            {},
        )

        history = load_json(
            folder / "history.json",
            {},
        )

        lambdas = load_json(
            folder / "lambda_comparison.json",
            {},
        )

        result = load_json(
            folder / "result.json",
            {},
        )

        observed = (
            enriched.get("datos_observados", {})
            if isinstance(enriched, dict)
            else {}
        )

        local_form = observed.get("local") or {}
        away_form = observed.get("visitante") or {}

        lh, la, lt = champion_lambda(
            lambdas,
            group,
        )

        quality = quality_information(
            result,
            lambdas,
        )

        result_exists = (
            (folder / "result.json").is_file()
        )

        champion_exists = (
            (
                lambdas.get("metodos", {})
                if isinstance(lambdas, dict)
                else {}
            ).get("J_BT_sin_temporada")
            is not None
        )

        if result_exists and champion_exists:
            status = "OK"
        elif any(
            (folder / f).is_file()
            for f in REQUIRED_ARTIFACTS
        ):
            status = "INCOMPLETE"
        else:
            status = "FAILED"

        primary = choose_primary_pick(
            markets,
            quality,
        )

        artifacts = {
            f: artifact_state(folder / f)
            for f in REQUIRED_ARTIFACTS
        }

        record = {
            "index": index,
            "mid": mid,
            "target": target,
            "group": group,
            "markets": markets,
            "enriched": enriched,
            "standings": standings,
            "xg": xg,
            "h2h": h2h,
            "history": history,
            "lambdas": lambdas,
            "result": result,
            "local_form": local_form,
            "away_form": away_form,
            "lambda_home": lh,
            "lambda_away": la,
            "lambda_total": lt,
            "quality": quality,
            "status": status,
            "primary": primary,
            "artifacts": artifacts,
        }

        detail_file = (
            f"{index:03d}_{mid}.html"
        )

        record["detail_file"] = (
            f"details/{detail_file}"
        )

        records.append(record)

    # --------------------------------------------------------
    # DETAILS
    # --------------------------------------------------------

    for record in records:
        target = record["target"]
        markets = record["markets"]

        home = (
            target.get("local")
            or "?"
        )

        away = (
            target.get("visitante")
            or "?"
        )

        def metric_card(
            title,
            value,
            probability=None,
        ):
            fair = (
                fair_odds(probability)
                if probability is not None
                else "—"
            )

            fair_html = (
                f'<div class="fair">'
                f'Fair odds: {fair}'
                f'</div>'
                if probability is not None
                else ""
            )

            return f"""
            <div class="card">
              <div class="metric-title">
                {esc(title)}
              </div>
              <div class="metric-value">
                {esc(value)}
              </div>
              {fair_html}
            </div>
            """

        o15 = probability_of(
            markets,
            "Over1.5",
        )

        o25 = probability_of(
            markets,
            "Over2.5",
        )

        o35 = probability_of(
            markets,
            "Over3.5",
        )

        btts = probability_of(
            markets,
            "BTTS",
        )

        p1 = probability_of(
            markets,
            "HomeWin",
        )

        px = probability_of(
            markets,
            "Draw",
        )

        p2 = probability_of(
            markets,
            "AwayWin",
        )

        p1x = probability_of(
            markets,
            "1X",
        )

        px2 = probability_of(
            markets,
            "X2",
        )

        p12 = probability_of(
            markets,
            "12",
        )

        primary = record["primary"]

        if primary["market"]:
            primary_text = (
                f"{MARKET_LABELS.get(primary['market'], primary['market'])}"
                f" — "
                f"{probability_pct(primary['probability'])}"
            )
        else:
            primary_text = "REVISIÓN / NO BET"

        quality_class = {
            "ALTA": "quality-high",
            "MEDIA": "quality-medium",
            "BAJA": "quality-low",
        }.get(
            record["quality"]["label"],
            "quality-low",
        )

        artifact_rows = []

        for filename, state in (
            record["artifacts"].items()
        ):
            css = (
                "artifact-available"
                if state == "AVAILABLE"
                else "artifact-missing"
            )

            artifact_rows.append(
                f"""
                <tr>
                  <td>
                    data/matches/{esc(record["mid"])}/{esc(filename)}
                  </td>
                  <td class="{css}">
                    {state}
                  </td>
                </tr>
                """
            )

        q = record["quality"]

        detail = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta
  name="viewport"
  content="width=device-width,initial-scale=1"
>
<title>
{esc(home)} vs {esc(away)}
</title>
<link
  rel="stylesheet"
  href="../assets/report.css"
>
</head>

<body>
<div class="container">

<div class="nav">
  <a
    class="button"
    href="../forecast_best_{args.date}.html"
  >
    ← Mejores pronósticos
  </a>

  <a
    class="button"
    href="../forecast_global_{args.date}.html"
  >
    ← Reporte global
  </a>
</div>

<section class="hero">
  <h1>
    {esc(home)}
    vs
    {esc(away)}
  </h1>

  <p class="muted">
    #{record["index"]}
    · {esc(target.get("pais"))}
    · {esc(target.get("competicion"))}
    · {esc(target.get("hora"))}
    · ID {esc(record["mid"])}
    · Pipeline:
    <strong>
      {esc(record["status"])}
    </strong>
  </p>
</section>

<h2>Resumen Champion BT0</h2>

<div class="grid">

{metric_card(
    "λ BT0",
    (
        f"{num(record['lambda_home'],3)}"
        " + "
        f"{num(record['lambda_away'],3)}"
        " = "
        f"{num(record['lambda_total'],3)}"
    ),
)}

{metric_card(
    "Over 1.5",
    probability_pct(o15),
    o15,
)}

{metric_card(
    "Over 2.5",
    probability_pct(o25),
    o25,
)}

{metric_card(
    "Over 3.5",
    probability_pct(o35),
    o35,
)}

{metric_card(
    "BTTS Sí",
    probability_pct(btts),
    btts,
)}

{metric_card(
    "1 / X / 2",
    (
        f"{probability_pct(p1)}"
        " / "
        f"{probability_pct(px)}"
        " / "
        f"{probability_pct(p2)}"
    ),
)}

{metric_card(
    "1X / X2 / 12",
    (
        f"{probability_pct(p1x)}"
        " / "
        f"{probability_pct(px2)}"
        " / "
        f"{probability_pct(p12)}"
    ),
)}

<div class="card">
  <div class="metric-title">
    Calidad de datos
  </div>

  <div
    class="metric-value {quality_class}"
  >
    {esc(q["label"])}
  </div>

  <div class="fair">
    Coverage score:
    {esc(q["score"])}
    / 100
  </div>
</div>

</div>

<h2>Lectura operativa</h2>

<div class="note">
  <strong>
    {esc(primary_text)}
  </strong>

  <br><br>

  Forecast basado en
  <strong>
    BT0 / J_BT_sin_temporada
  </strong>.

  Sin odds reales no se etiqueta
  como Value.
</div>

<h2>Calidad y cobertura de datos</h2>

<div class="grid">

{metric_card(
    "Forma local",
    f'{q["forma_local"]}/20',
)}

{metric_card(
    "Forma visitante",
    f'{q["forma_visitante"]}/20',
)}

{metric_card(
    "xG local",
    percent_any(q["xg_local"]),
)}

{metric_card(
    "xG visitante",
    percent_any(q["xg_visitante"]),
)}

{metric_card(
    "H2H",
    f'{q["h2h"]} partidos',
)}

{metric_card(
    "Standings",
    "Disponible" if q["standings"] else "No disponible",
)}

{metric_card(
    "Integridad temporal",
    "OK" if q["temporal"] else "Revisar",
)}

</div>

<h2>Clasificación</h2>

{standings_html(record["standings"])}

<h2>Forma reciente — {esc(home)}</h2>

{form_team_html(
    home,
    record["local_form"],
    "como_local",
)}

<h2>Forma reciente — {esc(away)}</h2>

{form_team_html(
    away,
    record["away_form"],
    "como_visitante",
)}

<h2>Goles esperados — xG / xGA</h2>

{xg_summary_html(
    record["xg"],
    home,
    away,
)}

<h3>Partidos revisados para xG</h3>

{xg_history_html(record["xg"])}

<h2>Enfrentamientos directos</h2>

{h2h_html(record["h2h"])}

<h3>Partidos H2H utilizados</h3>

{h2h_matches_html(record["h2h"])}

<h2>Comparador completo de λ</h2>

{lambda_html(record["lambdas"])}

<h2>Escenarios experimentales</h2>

{scenarios_html(record["result"])}

<h3>Marcadores probables — J_base</h3>

{likely_scores_html(record["result"])}

<h2>Artefactos del análisis</h2>

<div class="table-wrap">
<table class="detail-table">
<thead>
<tr>
  <th>Archivo</th>
  <th>Estado</th>
</tr>
</thead>

<tbody>
{''.join(artifact_rows)}
</tbody>
</table>
</div>

<div class="nav">
  <a
    class="button"
    href="../forecast_best_{args.date}.html"
  >
    ← Mejores pronósticos
  </a>

  <a
    class="button"
    href="../forecast_global_{args.date}.html"
  >
    ← Reporte global
  </a>
</div>

<footer>
Match Goals AI
· {esc(args.date)}
· Champion BT0 / J_BT_sin_temporada
</footer>

</div>
</body>
</html>
"""

        (
            details_dir
            / Path(record["detail_file"]).name
        ).write_text(
            detail,
            encoding="utf-8",
        )

    # --------------------------------------------------------
    # BEST PICKS
    # --------------------------------------------------------

    standard_records = [
        r
        for r in records
        if (
            r["status"] == "OK"
            and r["primary"]["market"]
            and is_standard_competition(
                r["target"]
            )
        )
    ]

    standard_records.sort(
        key=lambda r: (
            r["primary"]["score"],
            r["quality"]["score"],
            r["lambda_total"]
            if isinstance(
                r["lambda_total"],
                (int, float),
            )
            else -1,
        ),
        reverse=True,
    )

    best_records = standard_records[:12]

    best_cards = []

    for rank, r in enumerate(
        best_records,
        1,
    ):
        target = r["target"]
        primary = r["primary"]

        market = primary["market"]
        probability = primary["probability"]

        best_cards.append(
            f"""
            <article class="pick-card">

              <div class="muted">
                #{rank}
                · {esc(target.get("hora"))}
                · {esc(target.get("pais"))}
              </div>

              <h3>
                {esc(target.get("local"))}
                vs
                {esc(target.get("visitante"))}
              </h3>

              <div class="pick-market">
                {esc(
                    MARKET_LABELS.get(
                        market,
                        market,
                    )
                )}
              </div>

              <div class="grid">

                <div>
                  <small>Probabilidad</small>
                  <strong>
                    {probability_pct(probability)}
                  </strong>
                </div>

                <div>
                  <small>Fair odds</small>
                  <strong>
                    {fair_odds(probability)}
                  </strong>
                </div>

                <div>
                  <small>λ total</small>
                  <strong>
                    {num(r["lambda_total"],3)}
                  </strong>
                </div>

                <div>
                  <small>Calidad</small>
                  <strong>
                    {esc(r["quality"]["label"])}
                  </strong>
                </div>

              </div>

              <p class="muted small">
                {esc(target.get("competicion"))}
              </p>

              <a
                class="button"
                href="{esc(r['detail_file'])}"
              >
                Ver ficha completa →
              </a>

            </article>
            """
        )

    best_page = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta
  name="viewport"
  content="width=device-width,initial-scale=1"
>
<title>
Mejores pronósticos {esc(args.date)}
</title>
<link
  rel="stylesheet"
  href="assets/report.css"
>
</head>

<body>
<div class="container">

<section class="hero">

<h1>
Mejores pronósticos
· {esc(args.date)}
</h1>

<p class="muted">
Champion:
{esc(forecast.get("champion"))}
· Universo:
{len(records)} partidos
</p>

</section>

<div class="nav">

<a
  class="button"
  href="forecast_global_{args.date}.html"
>
  Ver reporte global →
</a>

</div>

<div class="note">
Estos son Forecast Picks.
No son Value Bets porque
no se evaluaron odds reales.
El ranking combina probabilidad
del BT0 con cobertura y calidad
de datos.
</div>

<h2>
Mejores candidatos de fútbol estándar
</h2>

<div class="grid">
{''.join(best_cards)}
</div>

<footer>
Partidos estándar excluyen
formatos virtuales / Kings /
Baller del ranking principal.
</footer>

</div>
</body>
</html>
"""

    (
        output
        / f"forecast_best_{args.date}.html"
    ).write_text(
        best_page,
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # GLOBAL
    # --------------------------------------------------------

    countries = sorted(
        {
            str(
                r["target"].get("pais")
                or ""
            )
            for r in records
            if r["target"].get("pais")
        }
    )

    country_options = "".join(
        f'<option value="{esc(c)}">{esc(c)}</option>'
        for c in countries
    )

    global_rows = []

    for r in records:
        target = r["target"]
        markets = r["markets"]

        o15 = probability_of(
            markets,
            "Over1.5",
        )

        o25 = probability_of(
            markets,
            "Over2.5",
        )

        o35 = probability_of(
            markets,
            "Over3.5",
        )

        btts = probability_of(
            markets,
            "BTTS",
        )

        p1 = probability_of(
            markets,
            "HomeWin",
        )

        px = probability_of(
            markets,
            "Draw",
        )

        p2 = probability_of(
            markets,
            "AwayWin",
        )

        primary = r["primary"]

        primary_label = (
            MARKET_LABELS.get(
                primary["market"],
                primary["market"],
            )
            if primary["market"]
            else "REVISIÓN / NO BET"
        )

        status_class = (
            "status-ok"
            if r["status"] == "OK"
            else "status-bad"
        )

        global_rows.append(
            f"""
            <tr
              data-country="{esc(target.get("pais"))}"
              data-quality="{esc(r["quality"]["label"])}"
              data-status="{esc(r["status"])}"
            >
              <td>{r["index"]}</td>
              <td>{esc(target.get("hora"))}</td>
              <td>{esc(target.get("pais"))}</td>
              <td>{esc(target.get("competicion"))}</td>
              <td>
                <strong>
                  {esc(target.get("local"))}
                </strong>
                <br>
                <span class="muted">
                  vs
                  {esc(target.get("visitante"))}
                </span>
              </td>
              <td>{num(r["lambda_total"],3)}</td>
              <td>{probability_pct(o15)}</td>
              <td>{probability_pct(o25)}</td>
              <td>{probability_pct(o35)}</td>
              <td>{probability_pct(btts)}</td>
              <td>
                {probability_pct(p1)}
                /
                {probability_pct(px)}
                /
                {probability_pct(p2)}
              </td>
              <td>
                {esc(r["quality"]["label"])}
                <br>
                <span class="muted small">
                  {r["quality"]["score"]}/100
                </span>
              </td>
              <td>
                {esc(primary_label)}
              </td>
              <td class="{status_class}">
                {esc(r["status"])}
              </td>
              <td>
                <a
                  href="{esc(r["detail_file"])}"
                >
                  Ficha completa →
                </a>
              </td>
            </tr>
            """
        )

    global_page = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta
  name="viewport"
  content="width=device-width,initial-scale=1"
>
<title>
Reporte global {esc(args.date)}
</title>
<link
  rel="stylesheet"
  href="assets/report.css"
>
<script
  defer
  src="assets/report.js"
></script>
</head>

<body>
<div class="container">

<section class="hero">
<h1>
Reporte global
· {esc(args.date)}
</h1>

<p class="muted">
{len(records)}
partidos scrapeados
· Champion:
{esc(forecast.get("champion"))}
</p>
</section>

<div class="nav">
<a
  class="button"
  href="forecast_best_{args.date}.html"
>
  ← Mejores pronósticos
</a>
</div>

<div class="filters">

<input
  id="search"
  placeholder="Buscar equipo o competición..."
  oninput="filterGlobal()"
>

<select
  id="country"
  onchange="filterGlobal()"
>
<option value="">
Todos los países
</option>
{country_options}
</select>

<select
  id="quality"
  onchange="filterGlobal()"
>
<option value="">
Todas las calidades
</option>
<option>ALTA</option>
<option>MEDIA</option>
<option>BAJA</option>
</select>

<select
  id="status"
  onchange="filterGlobal()"
>
<option value="">
Todos los estados
</option>
<option>OK</option>
<option>INCOMPLETE</option>
<option>FAILED</option>
</select>

</div>

<div class="global-scroll">

<table class="global-table">

<thead>
<tr>
  <th>#</th>
  <th>Hora</th>
  <th>País</th>
  <th>Competición</th>
  <th>Partido</th>
  <th>λ</th>
  <th>O1.5</th>
  <th>O2.5</th>
  <th>O3.5</th>
  <th>BTTS</th>
  <th>1 / X / 2</th>
  <th>Datos</th>
  <th>Forecast</th>
  <th>Estado</th>
  <th></th>
</tr>
</thead>

<tbody id="global-body">
{''.join(global_rows)}
</tbody>

</table>

</div>

<footer>
Cada partido tiene una ficha individual
con clasificación, forma, xG,
H2H, λ y escenarios.
</footer>

</div>
</body>
</html>
"""

    (
        output
        / f"forecast_global_{args.date}.html"
    ).write_text(
        global_page,
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # MANIFEST
    # --------------------------------------------------------

    manifest = {
        "date": args.date,
        "champion": forecast.get("champion"),
        "global_match_count": len(records),
        "detail_count": len(records),
        "best_pick_count": len(best_records),
        "ok_count": sum(
            r["status"] == "OK"
            for r in records
        ),
        "incomplete_count": sum(
            r["status"] == "INCOMPLETE"
            for r in records
        ),
        "failed_count": sum(
            r["status"] == "FAILED"
            for r in records
        ),
        "source": str(args.source),
        "forecast": str(args.forecast),
    }

    (
        output / "manifest.json"
    ).write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    (
        output / "README.txt"
    ).write_text(
        (
            "MATCH GOALS AI RICH REPORT\n\n"
            f"DATE={args.date}\n"
            f"MATCHES={len(records)}\n"
            f"DETAILS={len(records)}\n"
            f"BEST={len(best_records)}\n\n"
            f"Open first:\n"
            f"forecast_best_{args.date}.html\n"
            f"forecast_global_{args.date}.html\n"
        ),
        encoding="utf-8",
    )

    print("=" * 72)
    print("RICH REPORT V2")
    print("=" * 72)
    print("DATE              =", args.date)
    print("GLOBAL_MATCH_COUNT=", len(records))
    print("DETAIL_COUNT      =", len(records))
    print("BEST_PICK_COUNT   =", len(best_records))
    print(
        "OK_COUNT          =",
        manifest["ok_count"],
    )
    print(
        "INCOMPLETE_COUNT  =",
        manifest["incomplete_count"],
    )
    print(
        "FAILED_COUNT      =",
        manifest["failed_count"],
    )
    print("OUTPUT_PATH       =", output.resolve())
    print("=" * 72)


if __name__ == "__main__":
    main()
