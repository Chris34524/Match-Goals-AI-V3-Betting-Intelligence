import json
import html
import shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(".")
FORECAST = Path("v3_data/ops/forecast/latest.json")
TARGETS = Path("data/partidos_hoy.json")
MATCHES = Path("data/matches")
OUTDIR = Path("v3_data/ops/forecast")
ARCHIVE = OUTDIR / "archive"

MARKETS = {
    "Over1.5": "Más de 1.5 goles",
    "Over2.5": "Más de 2.5 goles",
    "Over3.5": "Más de 3.5 goles",
    "BTTS": "Ambos anotan",
    "HomeWin": "Gana local",
    "Draw": "Empate",
    "AwayWin": "Gana visitante",
    "1X": "Doble oportunidad 1X",
    "X2": "Doble oportunidad X2",
    "12": "Doble oportunidad 12",
}

def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def esc(v):
    return html.escape("-" if v is None else str(v))

def num(v, dec=2):
    try:
        return f"{float(v):.{dec}f}"
    except Exception:
        return "-"

def pct(v):
    try:
        x = float(v)
        if 0 <= x <= 1:
            x *= 100
        return f"{x:.1f}%"
    except Exception:
        return "-"

if not FORECAST.exists():
    raise SystemExit(f"ERROR: no existe {FORECAST}")

if not TARGETS.exists():
    raise SystemExit(f"ERROR: no existe {TARGETS}")

forecast = load(FORECAST)
targets = load(TARGETS)

fecha = targets.get("fecha_objetivo")
if not fecha:
    raise SystemExit(
        "ERROR: partidos_hoy.json no contiene fecha_objetivo"
    )

display_date = "/".join(reversed(fecha.split("-")))

target_rows = targets.get("partidos", [])
target_map = {
    str(p.get("id")): p
    for p in target_rows
    if p.get("id")
}
allowed_ids = set(target_map)

# -------------------------------------------------------
# Filtrar latest.json estrictamente contra universo del 31
# -------------------------------------------------------

valid_groups = []

for group in forecast.get("matches", []):
    picks = group.get("ranked_forecast_candidates", [])

    if not picks:
        continue

    first = picks[0]

    mid = str(
        first.get("internal_match_id")
        or group.get("internal_match_id")
        or ""
    )

    if mid not in allowed_ids:
        continue

    valid_groups.append((mid, group))

# -------------------------------------------------------
# Snapshot del forecast actual para futura evaluación
# -------------------------------------------------------

OUTDIR.mkdir(parents=True, exist_ok=True)
ARCHIVE.mkdir(parents=True, exist_ok=True)

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

snapshot_path = (
    ARCHIVE
    / f"forecast_{fecha}_{stamp}.json"
)

shutil.copy2(
    FORECAST,
    snapshot_path,
)

# -------------------------------------------------------
# Helpers técnicos
# -------------------------------------------------------

def forma_table(nombre, bloque):
    rows = []

    for window in ("l5", "l10", "l20"):
        d = bloque.get(window, {}) if isinstance(bloque, dict) else {}

        over = (
            d.get("over_2_5", {})
            .get("porcentaje")
            if isinstance(d.get("over_2_5"), dict)
            else None
        )

        btts = (
            d.get("btts", {})
            .get("porcentaje")
            if isinstance(d.get("btts"), dict)
            else None
        )

        rows.append(
            f"""
            <tr>
              <td>{window.upper()}</td>
              <td>{esc(d.get("pj"))}</td>
              <td>{num(d.get("promedio_gf"))}</td>
              <td>{num(d.get("promedio_gc"))}</td>
              <td>{num(d.get("promedio_total_goles"))}</td>
              <td>{pct(over)}</td>
              <td>{pct(btts)}</td>
            </tr>
            """
        )

    return f"""
    <div class="team-block">
      <h4>{esc(nombre)}</h4>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Ventana</th>
              <th>PJ</th>
              <th>GF/PJ</th>
              <th>GC/PJ</th>
              <th>TG/PJ</th>
              <th>O2.5</th>
              <th>BTTS</th>
            </tr>
          </thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    </div>
    """


def market_probability_map(picks):
    result = {}

    for p in picks:
        market = p.get("market")
        probability = p.get("probability")

        if market and probability is not None:
            result[str(market)] = probability

    return result


def probabilities_panel(picks):
    probs = market_probability_map(picks)

    markets = [
        ("Over1.5", "Más de 1.5"),
        ("Over2.5", "Más de 2.5"),
        ("Over3.5", "Más de 3.5"),
        ("BTTS", "Ambos anotan"),
        ("HomeWin", "Victoria local"),
        ("Draw", "Empate"),
        ("AwayWin", "Victoria visitante"),
        ("1X", "Local o empate"),
        ("X2", "Empate o visitante"),
        ("12", "Sin empate"),
    ]

    cards = []

    for key, label in markets:
        value = probs.get(key)

        cards.append(
            f"""
            <div class="prob-card">
              <small>{esc(label)}</small>
              <strong>{pct(value)}</strong>
            </div>
            """
        )

    return f"""
    <div class="probability-grid">
      {''.join(cards)}
    </div>
    """


def season_block(enriched, home, away):
    temporada = (
        enriched
        .get("datos_observados", {})
        .get("temporada", {})
    )

    if (
        not isinstance(temporada, dict)
        or temporada.get("estado") != "ok"
    ):
        return (
            '<p class="muted">'
            'Clasificación / datos de temporada no disponibles.'
            '</p>'
        )

    local = temporada.get("local") or {}
    visitante = temporada.get("visitante") or {}

    def team_card(label, name, d):
        try:
            pj = float(d.get("pj"))
        except Exception:
            pj = None

        try:
            gf = float(d.get("gf"))
        except Exception:
            gf = None

        try:
            gc = float(d.get("gc"))
        except Exception:
            gc = None

        try:
            pts = float(d.get("puntos"))
        except Exception:
            pts = None

        gf_pj = (
            gf / pj
            if gf is not None and pj
            else None
        )

        gc_pj = (
            gc / pj
            if gc is not None and pj
            else None
        )

        pts_pj = (
            pts / pj
            if pts is not None and pj
            else None
        )

        return f"""
        <div class="season-card">
          <div class="season-side">{esc(label)}</div>

          <h4>{esc(name)}</h4>

          <div class="season-stats">

            <div>
              <small>Posición</small>
              <strong>{esc(d.get("posicion"))}</strong>
            </div>

            <div>
              <small>PJ</small>
              <strong>{esc(d.get("pj"))}</strong>
            </div>

            <div>
              <small>Puntos</small>
              <strong>{esc(d.get("puntos"))}</strong>
            </div>

            <div>
              <small>Pts/PJ</small>
              <strong>{num(pts_pj)}</strong>
            </div>

            <div>
              <small>GF</small>
              <strong>{esc(d.get("gf"))}</strong>
            </div>

            <div>
              <small>GC</small>
              <strong>{esc(d.get("gc"))}</strong>
            </div>

            <div>
              <small>GF/PJ</small>
              <strong>{num(gf_pj)}</strong>
            </div>

            <div>
              <small>GC/PJ</small>
              <strong>{num(gc_pj)}</strong>
            </div>

          </div>
        </div>
        """

    return f"""
    <div class="season-grid">
      {team_card("LOCAL", home, local)}
      {team_card("VISITANTE", away, visitante)}
    </div>
    """


def xg_summary(xg, home, away):
    blocks = []

    for side, name in (
        ("local", home),
        ("visitante", away),
    ):
        team = (
            xg.get(side, {})
            if isinstance(xg, dict)
            else {}
        )

        rows = []

        for window in ("l5", "l10"):
            d = (
                team.get(window, {})
                if isinstance(team, dict)
                else {}
            )

            rows.append(
                f"""
                <div class="xg-window">

                  <div class="window-name">
                    {window.upper()}
                  </div>

                  <div>
                    <small>xGF</small>
                    <strong>
                      {num(d.get("xgf_promedio"), 3)}
                    </strong>
                  </div>

                  <div>
                    <small>xGA</small>
                    <strong>
                      {num(d.get("xga_promedio"), 3)}
                    </strong>
                  </div>

                  <div>
                    <small>Cobertura xG</small>
                    <strong>
                      {pct(d.get("cobertura_xg"))}
                    </strong>
                  </div>

                  <div>
                    <small>Partidos xG</small>
                    <strong>
                      {esc(d.get("partidos_con_xg"))}
                      /
                      {esc(d.get("partidos_considerados"))}
                    </strong>
                  </div>

                </div>
                """
            )

        blocks.append(
            f"""
            <div class="xg-team-card">
              <h4>{esc(name)}</h4>
              {''.join(rows)}
            </div>
            """
        )

    return f"""
    <div class="xg-summary-grid">
      {''.join(blocks)}
    </div>
    """



def xg_table(xg):
    rows = []

    for side, label in (
        ("local", "Local"),
        ("visitante", "Visitante"),
    ):
        team = xg.get(side, {}) if isinstance(xg, dict) else {}

        for window in ("l5", "l10"):
            d = team.get(window, {}) if isinstance(team, dict) else {}

            rows.append(
                f"""
                <tr>
                  <td>{label}</td>
                  <td>{window.upper()}</td>
                  <td>
                    {esc(d.get("partidos_con_xg"))}
                    /
                    {esc(d.get("partidos_considerados"))}
                  </td>
                  <td>{pct(d.get("cobertura_xg"))}</td>
                  <td>{num(d.get("xgf_promedio"), 3)}</td>
                  <td>{num(d.get("xga_promedio"), 3)}</td>
                </tr>
                """
            )

    return f"""
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Equipo</th>
            <th>Ventana</th>
            <th>xG disponibles</th>
            <th>Cobertura</th>
            <th>xGF</th>
            <th>xGA</th>
          </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """

def h2h_table(h2h):
    rows = []

    for window in ("h5", "h10", "h20"):
        d = h2h.get(window) if isinstance(h2h, dict) else None

        if not isinstance(d, dict):
            continue

        rows.append(
            f"""
            <tr>
              <td>{window.upper()}</td>
              <td>{esc(d.get("n"))}</td>
              <td>{num(d.get("total_promedio"))}</td>
              <td>{pct(d.get("p_2_mas"))}</td>
              <td>{pct(d.get("p_3_mas"))}</td>
              <td>{pct(d.get("p_4_mas"))}</td>
              <td>{pct(d.get("btts"))}</td>
            </tr>
            """
        )

    if not rows:
        return '<p class="muted">Sin H2H disponible.</p>'

    return f"""
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>H2H</th>
            <th>N</th>
            <th>Goles/PJ</th>
            <th>2+</th>
            <th>3+</th>
            <th>4+</th>
            <th>BTTS</th>
          </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """

def history_table(history, match_id):
    sections = (
        history.get("secciones", [])
        if isinstance(history, dict)
        else []
    )

    blocks = []

    for section in sections[:3]:
        partidos = [
            p
            for p in section.get("partidos", [])
            if str(p.get("match_id")) != str(match_id)
        ][:10]

        if not partidos:
            continue

        rows = []

        for p in partidos:
            gl = p.get("goles_local")
            gv = p.get("goles_visitante")

            score = (
                f"{gl} - {gv}"
                if gl is not None and gv is not None
                else "-"
            )

            rows.append(
                f"""
                <tr>
                  <td>{esc(p.get("fecha"))}</td>
                  <td>{esc(p.get("local"))}</td>
                  <td class="score">{esc(score)}</td>
                  <td>{esc(p.get("visitante"))}</td>
                </tr>
                """
            )

        blocks.append(
            f"""
            <h4>{esc(section.get("titulo") or section.get("tipo_estimado"))}</h4>

            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Local</th>
                    <th>Marcador</th>
                    <th>Visitante</th>
                  </tr>
                </thead>
                <tbody>{''.join(rows)}</tbody>
              </table>
            </div>
            """
        )

    return (
        "".join(blocks)
        if blocks
        else '<p class="muted">Sin historial disponible.</p>'
    )

# -------------------------------------------------------
# Cards resumen
# -------------------------------------------------------

top = []

for mid, group in valid_groups:
    picks = group.get("ranked_forecast_candidates", [])

    if picks:
        top.append(picks[0])

top.sort(
    key=lambda p: (
        p.get("probability")
        if isinstance(p.get("probability"), (int, float))
        else -1
    ),
    reverse=True,
)

top_cards = []

for i, p in enumerate(top[:30], 1):
    top_cards.append(
        f"""
        <article class="pick-card">
          <span class="rank">#{i}</span>

          <h3>
            {esc(p.get("home"))}
            <span>vs</span>
            {esc(p.get("away"))}
          </h3>

          <div class="market">
            {esc(MARKETS.get(p.get("market"), p.get("market")))}
          </div>

          <div class="metrics">
            <div>
              <small>Probabilidad</small>
              <strong>{pct(p.get("probability"))}</strong>
            </div>

            <div>
              <small>Fair odds</small>
              <strong>{num(p.get("fair_odds"))}</strong>
            </div>
          </div>
        </article>
        """
    )

# -------------------------------------------------------
# Detalle partido por partido
# -------------------------------------------------------

match_blocks = []

for index, (mid, group) in enumerate(valid_groups, 1):
    picks = group.get("ranked_forecast_candidates", [])

    if not picks:
        continue

    first = picks[0]
    target = target_map.get(mid, {})

    folder = MATCHES / mid

    enriched = load(folder / "enriched.json")
    xg = load(folder / "xg_history.json")
    h2h = load(folder / "h2h_analysis.json")
    history = load(folder / "history.json")
    result = load(folder / "result.json")
    lambdas = load(folder / "lambda_comparison.json")
    confidence = load(folder / "confidence_v2.json")

    observed = enriched.get("datos_observados", {})

    local_form = observed.get("local", {})
    away_form = observed.get("visitante", {})

    champion = (
        lambdas
        .get("metodos", {})
        .get("J_BT_sin_temporada", {})
    )

    lambda_home = (
        first.get("lambda_home")
        or champion.get("lambda_local")
        or champion.get("home")
    )

    lambda_away = (
        first.get("lambda_away")
        or champion.get("lambda_visitante")
        or champion.get("away")
    )

    lambda_total = (
        first.get("lambda_total")
        or champion.get("lambda_total")
    )

    integrity = (
        result
        .get("integridad_temporal", {})
        .get("estado", "N/D")
    )

    picks_rows = []

    for p in picks[:10]:
        picks_rows.append(
            f"""
            <tr>
              <td>{esc(p.get("forecast_rank"))}</td>
              <td>{esc(MARKETS.get(p.get("market"), p.get("market")))}</td>
              <td><strong>{pct(p.get("probability"))}</strong></td>
              <td>{num(p.get("fair_odds"))}</td>
              <td>{esc(p.get("data_quality") or "-")}</td>
            </tr>
            """
        )

    match_blocks.append(
        f"""
        <article class="match-card">

          <div class="match-header">
            <div>
              <span class="rank">#{index}</span>

              <h2>
                {esc(first.get("home"))}
                <span>vs</span>
                {esc(first.get("away"))}
              </h2>

              <p class="muted">
                {esc(target.get("pais"))}
                · {esc(target.get("competicion"))}
                · {esc(target.get("hora"))}
                · ID {esc(mid)}
              </p>
            </div>

            <div class="integrity">
              Integridad: {esc(integrity)}
            </div>
          </div>

          <div class="lambda-grid">
            <div>
              <small>λ local</small>
              <strong>{num(lambda_home)}</strong>
            </div>

            <div>
              <small>λ visitante</small>
              <strong>{num(lambda_away)}</strong>
            </div>

            <div>
              <small>λ total</small>
              <strong>{num(lambda_total)}</strong>
            </div>

            <div>
              <small>Confianza</small>
              <strong>{esc(confidence.get("calidad") or first.get("data_quality") or "-")}</strong>
            </div>
          </div>

          <h3>Información general de temporada</h3>

          {season_block(
              enriched,
              first.get("home"),
              first.get("away"),
          )}

          <h3>Probabilidades generales del modelo</h3>

          {probabilities_panel(picks)}

          <h3>Resumen xG</h3>

          {xg_summary(
              xg,
              first.get("home"),
              first.get("away"),
          )}

          <h3>Pronósticos ordenados</h3>

          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Mercado</th>
                  <th>Probabilidad</th>
                  <th>Fair odds</th>
                  <th>Calidad</th>
                </tr>
              </thead>
              <tbody>
                {''.join(picks_rows)}
              </tbody>
            </table>
          </div>

          <details>
            <summary>Forma reciente L5 / L10 / L20</summary>

            <div class="two-cols">
              {forma_table(first.get("home"), local_form)}
              {forma_table(first.get("away"), away_form)}
            </div>
          </details>

          <details>
            <summary>xG / xGA y cobertura</summary>
            {xg_table(xg)}
          </details>

          <details>
            <summary>Head to Head</summary>
            {h2h_table(h2h)}
          </details>

          <details>
            <summary>Partidos utilizados en el análisis</summary>
            {history_table(history, mid)}
          </details>

        </article>
        """
    )

# -------------------------------------------------------
# HTML
# -------------------------------------------------------

report_path = OUTDIR / f"forecast_report_{fecha}.html"

document = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">

<title>Match Goals AI V3 — {display_date}</title>

<style>
:root {{
 --bg:#08101d;
 --panel:#10192b;
 --panel2:#141f34;
 --line:#26334c;
 --text:#edf3ff;
 --muted:#8f9db5;
 --blue:#5aa7ff;
 --green:#67e0b4;
}}

* {{ box-sizing:border-box }}

body {{
 margin:0;
 background:linear-gradient(180deg,#08101d,#0b1020);
 color:var(--text);
 font-family:Inter,Segoe UI,Arial,sans-serif;
}}

.container {{
 max-width:1500px;
 margin:auto;
 padding:28px;
}}

header {{
 padding:25px;
 background:var(--panel);
 border:1px solid var(--line);
 border-radius:18px;
}}

h1,h2,h3,h4 {{ margin-top:0 }}

.muted {{ color:var(--muted) }}

.summary {{
 display:grid;
 grid-template-columns:repeat(4,1fr);
 gap:12px;
 margin:18px 0 30px;
}}

.summary div,
.lambda-grid div {{
 padding:15px;
 background:var(--panel);
 border:1px solid var(--line);
 border-radius:12px;
}}

.summary small,
.lambda-grid small,
.metrics small {{
 display:block;
 color:var(--muted);
}}

.summary strong,
.lambda-grid strong,
.metrics strong {{
 font-size:20px;
}}

.top-grid {{
 display:grid;
 grid-template-columns:repeat(4,1fr);
 gap:12px;
}}

.pick-card {{
 padding:15px;
 background:var(--panel);
 border:1px solid var(--line);
 border-radius:14px;
}}

.pick-card h3 {{
 margin:10px 0;
 font-size:15px;
}}

.pick-card h3 span,
.match-header h2 span {{
 color:var(--muted);
 font-weight:400;
}}

.rank {{
 color:var(--blue);
 font-weight:800;
}}

.market {{
 color:var(--green);
 font-weight:700;
 margin-bottom:12px;
}}

.metrics {{
 display:grid;
 grid-template-columns:1fr 1fr;
}}

.match-card {{
 margin-top:24px;
 padding:22px;
 background:var(--panel);
 border:1px solid var(--line);
 border-radius:16px;
}}

.match-header {{
 display:flex;
 justify-content:space-between;
 gap:20px;
}}

.integrity {{
 color:var(--green);
 font-weight:700;
}}

.lambda-grid {{
 display:grid;
 grid-template-columns:repeat(4,1fr);
 gap:10px;
 margin:18px 0;
}}

.probability-grid {{
 display:grid;
 grid-template-columns:repeat(5,1fr);
 gap:10px;
 margin:14px 0 22px;
}}

.prob-card {{
 padding:14px;
 border:1px solid var(--line);
 border-radius:12px;
 background:var(--panel2);
}}

.prob-card small {{
 display:block;
 color:var(--muted);
 margin-bottom:5px;
}}

.prob-card strong {{
 font-size:20px;
 color:var(--green);
}}

.season-grid {{
 display:grid;
 grid-template-columns:1fr 1fr;
 gap:14px;
 margin:14px 0 24px;
}}

.season-card {{
 padding:16px;
 border:1px solid var(--line);
 border-radius:14px;
 background:var(--panel2);
}}

.season-side {{
 color:var(--blue);
 font-size:11px;
 font-weight:800;
 margin-bottom:6px;
}}

.season-stats {{
 display:grid;
 grid-template-columns:repeat(4,1fr);
 gap:10px;
}}

.season-stats div {{
 padding:10px;
 border:1px solid var(--line);
 border-radius:10px;
}}

.season-stats small {{
 display:block;
 color:var(--muted);
 margin-bottom:4px;
}}

.season-stats strong {{
 font-size:17px;
}}

.xg-summary-grid {{
 display:grid;
 grid-template-columns:1fr 1fr;
 gap:14px;
 margin:14px 0 24px;
}}

.xg-team-card {{
 padding:16px;
 border:1px solid var(--line);
 border-radius:14px;
 background:var(--panel2);
}}

.xg-window {{
 display:grid;
 grid-template-columns:70px repeat(4,1fr);
 gap:8px;
 align-items:center;
 padding:10px 0;
 border-top:1px solid var(--line);
}}

.xg-window small {{
 display:block;
 color:var(--muted);
}}

.xg-window strong {{
 font-size:15px;
}}

.window-name {{
 color:var(--blue);
 font-weight:800;
}}

details {{
 margin-top:12px;
 padding:12px 14px;
 border:1px solid var(--line);
 border-radius:12px;
 background:var(--panel2);
}}

summary {{
 cursor:pointer;
 font-weight:700;
 color:var(--green);
}}

.two-cols {{
 display:grid;
 grid-template-columns:1fr 1fr;
 gap:14px;
 margin-top:14px;
}}

.team-block {{
 min-width:0;
}}

.table-wrap {{
 overflow:auto;
 margin-top:10px;
}}

table {{
 width:100%;
 border-collapse:collapse;
 min-width:650px;
}}

th,td {{
 padding:9px 10px;
 border-bottom:1px solid var(--line);
 font-size:12px;
 text-align:left;
}}

th {{
 color:#cfd8eb;
}}

.score {{
 font-weight:800;
 text-align:center;
}}

footer {{
 margin:30px 0;
 color:var(--muted);
 font-size:12px;
}}

@media(max-width:1000px) {{
 .summary,
 .top-grid,
 .lambda-grid {{
   grid-template-columns:repeat(2,1fr);
 }}

 .two-cols,
 .season-grid,
 .xg-summary-grid {{
   grid-template-columns:1fr;
 }}

 .probability-grid {{
   grid-template-columns:repeat(2,1fr);
 }}

 .season-stats {{
   grid-template-columns:repeat(2,1fr);
 }}

 .xg-window {{
   grid-template-columns:1fr 1fr;
 }}
}}

@media(max-width:650px) {{
 .container {{
   padding:12px;
 }}

 .summary,
 .top-grid,
 .lambda-grid {{
   grid-template-columns:1fr;
 }}

 .match-header {{
   flex-direction:column;
 }}
}}
</style>
</head>

<body>
<div class="container">

<header>
  <h1>Match Goals AI V3</h1>

  <p>
    Forecast Intelligence Report ·
    <strong>{display_date}</strong>
  </p>

  <p class="muted">
    Champion:
    {esc(forecast.get("champion"))}
    · Forecast incremental
  </p>
</header>

<section class="summary">
  <div>
    <small>Partidos universo</small>
    <strong>{len(allowed_ids)}</strong>
  </div>

  <div>
    <small>Partidos analizados ahora</small>
    <strong>{len(valid_groups)}</strong>
  </div>

  <div>
    <small>Candidatos actuales</small>
    <strong>{sum(len(g.get("ranked_forecast_candidates", [])) for _, g in valid_groups)}</strong>
  </div>

  <div>
    <small>Odds API</small>
    <strong>NO requerida</strong>
  </div>
</section>

<h2>Top 30 actuales</h2>

<div class="top-grid">
  {''.join(top_cards)}
</div>

<h2 style="margin-top:32px">
  Análisis completo por partido
</h2>

{''.join(match_blocks)}

<footer>
Snapshot guardado:
{esc(snapshot_path)}
<br>
El reporte sólo contiene IDs pertenecientes al universo del
{display_date}.
</footer>

</div>
</body>
</html>
"""

report_path.write_text(
    document,
    encoding="utf-8",
)

print("=" * 76)
print("REPORTE HTML GENERADO")
print("=" * 76)
print("Fecha               :", fecha)
print("Universo del día     :", len(allowed_ids))
print("Analizados ahora     :", len(valid_groups))
print(
    "Candidatos actuales :",
    sum(
        len(g.get("ranked_forecast_candidates", []))
        for _, g in valid_groups
    ),
)
print("Snapshot             :", snapshot_path)
print("HTML                 :", report_path.resolve())
print("=" * 76)
