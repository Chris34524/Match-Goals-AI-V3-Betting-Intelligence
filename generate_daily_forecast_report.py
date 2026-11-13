import json
import html
from pathlib import Path

FORECAST = Path("v3_data/ops/forecast/latest.json")
TARGETS = Path("data/partidos_manana.json")
OUTDIR = Path("v3_data/ops/forecast")

LABELS = {
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

def esc(v):
    return html.escape("" if v is None else str(v))

def pct(v):
    return f"{v * 100:.1f}%" if isinstance(v, (int, float)) else "-"

def odd(v):
    return f"{v:.2f}" if isinstance(v, (int, float)) else "-"

if not FORECAST.exists():
    raise SystemExit(f"ERROR: no existe {FORECAST}")

if not TARGETS.exists():
    raise SystemExit(f"ERROR: no existe {TARGETS}")

forecast = json.loads(FORECAST.read_text(encoding="utf-8"))
targets = json.loads(TARGETS.read_text(encoding="utf-8"))

fecha = targets.get("fecha_objetivo")

if not fecha:
    raise SystemExit("ERROR: partidos_manana.json no contiene fecha_objetivo")

expected = targets.get("total_partidos", 0)
actual = forecast.get("forecast_matches", 0)

print("=" * 72)
print("VALIDACIÓN DE JORNADA")
print("=" * 72)
print("Fecha objetivo :", fecha)
print("Targets        :", expected)
print("Forecast       :", actual)

if actual == 0:
    raise SystemExit("ERROR: forecast vacío")

if actual > expected:
    raise SystemExit(
        f"ERROR: forecast tiene {actual} partidos "
        f"pero el universo actual sólo tiene {expected}"
    )

output = OUTDIR / f"forecast_report_{fecha}.html"

matches = forecast.get("matches", [])

top = []

for group in matches:
    picks = group.get("ranked_forecast_candidates", [])
    if picks:
        top.append(picks[0])

top.sort(
    key=lambda x: (
        x.get("probability")
        if isinstance(x.get("probability"), (int, float))
        else -1
    ),
    reverse=True,
)

cards = []

for i, p in enumerate(top[:30], 1):
    probability = p.get("probability", 0)

    cards.append(f"""
    <article class="card">
      <div class="topline">
        <span class="rank">#{i}</span>
        <span class="quality">{esc(p.get("data_quality") or "N/D")}</span>
      </div>

      <h3>
        {esc(p.get("home"))}
        <span>vs</span>
        {esc(p.get("away"))}
      </h3>

      <div class="competition">
        {esc(p.get("competition") or "Competición no disponible")}
      </div>

      <div class="market">
        {esc(LABELS.get(p.get("market"), p.get("market")))}
      </div>

      <div class="metrics">
        <div>
          <small>Probabilidad</small>
          <strong>{pct(probability)}</strong>
        </div>
        <div>
          <small>Fair odds</small>
          <strong>{odd(p.get("fair_odds"))}</strong>
        </div>
      </div>

      <div class="bar">
        <span style="width:{probability * 100:.1f}%"></span>
      </div>
    </article>
    """)

rows = []

for group in matches:
    for p in group.get("ranked_forecast_candidates", []):
        probability = p.get("probability", 0)

        rows.append(f"""
        <tr
          data-team="{esc((p.get('home') or '') + ' ' + (p.get('away') or ''))}"
          data-market="{esc(p.get('market') or '')}"
          data-prob="{probability}"
        >
          <td>
            <strong>{esc(p.get("home"))}</strong><br>
            <span class="muted">vs {esc(p.get("away"))}</span>
          </td>
          <td>{esc(p.get("competition") or "-")}</td>
          <td>
            <span class="badge">
              {esc(LABELS.get(p.get("market"), p.get("market")))}
            </span>
          </td>
          <td class="num"><strong>{pct(probability)}</strong></td>
          <td class="num">{odd(p.get("fair_odds"))}</td>
          <td class="num">{esc(p.get("forecast_rank"))}</td>
          <td>{esc(p.get("data_quality") or "N/D")}</td>
        </tr>
        """)

display_date = "/".join(reversed(fecha.split("-")))

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
 font-family:Inter,Segoe UI,Arial,sans-serif;
 background:linear-gradient(180deg,#08101d,#0b1020);
 color:var(--text);
}}

.container {{
 max-width:1500px;
 margin:auto;
 padding:30px;
}}

header {{
 display:flex;
 justify-content:space-between;
 gap:20px;
 padding:26px;
 background:var(--panel);
 border:1px solid var(--line);
 border-radius:18px;
}}

h1 {{ margin:0 0 8px }}

.subtitle {{
 color:var(--muted);
 line-height:1.6;
}}

.date {{
 color:var(--green);
 font-size:22px;
 font-weight:800;
}}

.kpis {{
 display:grid;
 grid-template-columns:repeat(6,1fr);
 gap:14px;
 margin:18px 0;
}}

.kpi {{
 padding:18px;
 background:var(--panel);
 border:1px solid var(--line);
 border-radius:15px;
}}

.kpi small {{
 display:block;
 color:var(--muted);
 margin-bottom:8px;
}}

.kpi strong {{ font-size:24px }}

.notice {{
 padding:16px;
 border:1px solid #554b2d;
 background:rgba(255,209,102,.06);
 border-radius:12px;
 color:#e8d797;
}}

section {{ margin-top:30px }}

.cards {{
 display:grid;
 grid-template-columns:repeat(4,1fr);
 gap:14px;
}}

.card {{
 padding:17px;
 background:var(--panel);
 border:1px solid var(--line);
 border-radius:16px;
}}

.topline {{
 display:flex;
 justify-content:space-between;
}}

.rank {{
 color:var(--blue);
 font-weight:800;
}}

.quality {{
 color:var(--muted);
 font-size:12px;
}}

.card h3 {{
 font-size:15px;
 margin:12px 0 5px;
}}

.card h3 span {{
 color:var(--muted);
 font-weight:400;
}}

.competition {{
 min-height:28px;
 color:var(--muted);
 font-size:12px;
}}

.market {{
 margin:14px 0;
 color:var(--green);
 font-weight:700;
}}

.metrics {{
 display:grid;
 grid-template-columns:1fr 1fr;
}}

.metrics small {{
 display:block;
 color:var(--muted);
}}

.metrics strong {{
 font-size:19px;
}}

.bar {{
 height:5px;
 margin-top:14px;
 background:#202c43;
 border-radius:20px;
 overflow:hidden;
}}

.bar span {{
 display:block;
 height:100%;
 background:linear-gradient(90deg,var(--blue),var(--green));
}}

.controls {{
 display:flex;
 flex-wrap:wrap;
 gap:10px;
 margin-bottom:14px;
}}

input,select {{
 padding:10px 12px;
 color:var(--text);
 background:var(--panel2);
 border:1px solid var(--line);
 border-radius:10px;
}}

input {{ min-width:300px }}

.table-wrap {{
 overflow:auto;
 border:1px solid var(--line);
 border-radius:16px;
}}

table {{
 width:100%;
 min-width:1000px;
 border-collapse:collapse;
 background:var(--panel);
}}

th,td {{
 padding:12px 14px;
 border-bottom:1px solid var(--line);
 text-align:left;
 font-size:13px;
}}

th {{
 position:sticky;
 top:0;
 background:#121d31;
}}

.num {{ text-align:right }}
.muted {{ color:var(--muted) }}

.badge {{
 display:inline-block;
 padding:4px 8px;
 border:1px solid #35435f;
 border-radius:999px;
 color:var(--green);
}}

footer {{
 margin-top:28px;
 color:var(--muted);
 font-size:12px;
 line-height:1.6;
}}

@media(max-width:1100px) {{
 .kpis {{ grid-template-columns:repeat(3,1fr) }}
 .cards {{ grid-template-columns:repeat(2,1fr) }}
}}

@media(max-width:700px) {{
 .container {{ padding:14px }}
 header {{ flex-direction:column }}
 .kpis {{ grid-template-columns:repeat(2,1fr) }}
 .cards {{ grid-template-columns:1fr }}
}}
</style>
</head>

<body>
<div class="container">

<header>
<div>
<h1>Match Goals AI V3</h1>

<div class="subtitle">
Forecast Intelligence Report<br>
Champion: {esc(forecast.get("champion"))}<br>
Fuente: {esc(forecast.get("source"))}
</div>
</div>

<div class="date">{display_date}</div>
</header>

<div class="kpis">
<div class="kpi"><small>Partidos objetivo</small><strong>{expected}</strong></div>
<div class="kpi"><small>Partidos analizados</small><strong>{actual}</strong></div>
<div class="kpi"><small>Candidatos</small><strong>{forecast.get("forecast_candidates",0)}</strong></div>
<div class="kpi"><small>Forecast legacy</small><strong>{forecast.get("legacy_operational_forecasts",0)}</strong></div>
<div class="kpi"><small>Forecast OOS</small><strong>{forecast.get("forecast_oos_count",0)}</strong></div>
<div class="kpi"><small>Betting OOS</small><strong>{forecast.get("betting_oos_matches",0)}</strong></div>
</div>

<div class="notice">
Ranking basado en probabilidad predictiva.
Sin odds de mercado no se evalúan todavía
Value, Edge, EV ni CLV.
</div>

<section>
<h2>Top 30 picks — {display_date}</h2>
<div class="cards">
{''.join(cards)}
</div>
</section>

<section>
<h2>Detalle completo</h2>

<div class="controls">
<input id="search" type="search" placeholder="Buscar equipo...">

<select id="market">
<option value="">Todos los mercados</option>
<option value="Over1.5">Over 1.5</option>
<option value="Over2.5">Over 2.5</option>
<option value="Over3.5">Over 3.5</option>
<option value="BTTS">BTTS</option>
<option value="HomeWin">Gana local</option>
<option value="Draw">Empate</option>
<option value="AwayWin">Gana visitante</option>
<option value="1X">1X</option>
<option value="X2">X2</option>
<option value="12">12</option>
</select>

<select id="prob">
<option value="0">Todas las probabilidades</option>
<option value=".50">≥ 50%</option>
<option value=".60">≥ 60%</option>
<option value=".70">≥ 70%</option>
<option value=".80">≥ 80%</option>
<option value=".90">≥ 90%</option>
</select>
</div>

<div class="table-wrap">
<table>
<thead>
<tr>
<th>Partido</th>
<th>Competición</th>
<th>Mercado</th>
<th class="num">Probabilidad</th>
<th class="num">Fair odds</th>
<th class="num">Rank</th>
<th>Calidad</th>
</tr>
</thead>

<tbody id="rows">
{''.join(rows)}
</tbody>
</table>
</div>
</section>

<footer>
Match Goals AI V3 — Betting Intelligence<br>
Reporte: {display_date} ·
odds_required_for_forecast =
{str(forecast.get("odds_required_for_forecast")).lower()} ·
value_evaluated =
{str(forecast.get("value_evaluated")).lower()}
</footer>

</div>

<script>
const search=document.getElementById("search");
const market=document.getElementById("market");
const prob=document.getElementById("prob");
const rows=[...document.querySelectorAll("#rows tr")];

function filterRows(){{
 const term=search.value.toLowerCase().trim();
 const m=market.value;
 const p=Number(prob.value);

 rows.forEach(row=>{{
   const a=!term || row.dataset.team.toLowerCase().includes(term);
   const b=!m || row.dataset.market===m;
   const c=Number(row.dataset.prob)>=p;

   row.style.display=a&&b&&c ? "" : "none";
 }});
}}

search.addEventListener("input",filterRows);
market.addEventListener("change",filterRows);
prob.addEventListener("change",filterRows);
</script>

</body>
</html>
"""

OUTDIR.mkdir(parents=True, exist_ok=True)

output.write_text(
    document,
    encoding="utf-8",
)

print()
print("=" * 72)
print("REPORTE GENERADO CORRECTAMENTE")
print("=" * 72)
print("Fecha   :", fecha)
print("Targets :", expected)
print("Forecast:", actual)
print("Archivo :", output.resolve())
print()
print("Los reportes de jornadas anteriores NO fueron modificados.")
print("=" * 72)
