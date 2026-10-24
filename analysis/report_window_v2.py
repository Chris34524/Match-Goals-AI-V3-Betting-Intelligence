import html
import json
from pathlib import Path


SRC = Path("data/day_predictions_v2.json")
OUT = Path("data/report_window_v2.html")


def cargar(path):
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def pct(v):
    if v is None:
        return "N/D"

    try:
        v = float(v)
    except:
        return "N/D"

    if 1 < v <= 100:
        v /= 100

    return f"{v:.1%}"


def dec(v):
    try:
        return f"{float(v):.2f}"
    except:
        return "N/D"


def valor(p, *claves):
    for k in claves:
        if p.get(k) is not None:
            return p.get(k)
    return None


def main():
    if not SRC.exists():
        raise SystemExit(
            "No existe data/day_predictions_v2.json"
        )

    d = cargar(SRC)

    partidos = d.get(
        "partidos",
        []
    )

    if not partidos:
        raise SystemExit(
            "No hay partidos en day_predictions_v2.json"
        )

    resumen = []
    detalles = []

    for i, p in enumerate(
        partidos,
        1,
    ):
        local = html.escape(
            str(
                p.get("local")
                or p.get("equipo_local")
                or ""
            )
        )

        visitante = html.escape(
            str(
                p.get("visitante")
                or p.get("equipo_visitante")
                or ""
            )
        )

        hora = html.escape(
            str(
                p.get("hora")
                or p.get("time")
                or ""
            )
        )

        competicion = html.escape(
            str(
                p.get("competicion")
                or p.get("liga")
                or ""
            )
        )

        lh = valor(
            p,
            "lambda_local",
            "lambda_home",
        )

        la = valor(
            p,
            "lambda_visitante",
            "lambda_away",
        )

        lt = valor(
            p,
            "lambda_total",
            "total_lambda",
        )

        p15 = valor(
            p,
            "+1.5",
            "over_1_5",
        )

        p25 = valor(
            p,
            "+2.5",
            "over_2_5",
        )

        p35 = valor(
            p,
            "+3.5",
            "over_3_5",
        )

        p45 = valor(
            p,
            "+4.5",
            "over_4_5",
        )

        btts = valor(
            p,
            "btts",
            "BTTS",
            "p_btts",
        )

        calidad = p.get(
            "calidad_datos",
            "N/D",
        )

        conf_btts = p.get(
            "confianza_btts",
            "N/D",
        )

        score = p.get(
            "score_calidad",
            "N/D",
        )

        alertas = p.get(
            "alertas_calidad",
            [],
        )

        conf = p.get(
            "confidence_v2",
            {}
        )

        detalle_v1 = conf.get(
            "detalle_v1",
            {}
        )

        razones = detalle_v1.get(
            "razones",
            [],
        )

        muestras = detalle_v1.get(
            "muestras",
            {},
        )

        xg = detalle_v1.get(
            "xg_bilateral",
            "N/D",
        )

        dispersion = detalle_v1.get(
            "dispersion_lambda_senales",
            "N/D",
        )

        resumen.append(
            f"""
<tr>
<td>{i}</td>
<td>
<strong>{local}</strong> vs <strong>{visitante}</strong>
<br>
<small>{hora} · {competicion}</small>
</td>
<td>{dec(lh)}</td>
<td>{dec(la)}</td>
<td>{dec(lt)}</td>
<td>{pct(p15)}</td>
<td><strong>{pct(p25)}</strong></td>
<td>{pct(p35)}</td>
<td>{pct(p45)}</td>
<td>{pct(btts)}</td>
<td>{html.escape(str(calidad))}</td>
<td>{html.escape(str(conf_btts))}</td>
</tr>
"""
        )

        razones_html = (
            "<ul>"
            + "".join(
                f"<li>{html.escape(str(x))}</li>"
                for x in razones
            )
            + "</ul>"
            if razones
            else "<p>N/D</p>"
        )

        alertas_html = (
            "<ul>"
            + "".join(
                f"<li>{html.escape(str(x))}</li>"
                for x in alertas
            )
            + "</ul>"
            if alertas
            else "<p>Sin alertas relevantes.</p>"
        )

        detalles.append(
            f"""
<section class="card">
<h2>{i}. {local} vs {visitante}</h2>

<p class="meta">
{hora} · {competicion}
</p>

<div class="grid">

<div>
<h3>Expectativa de goles</h3>
<p>λ local: <strong>{dec(lh)}</strong></p>
<p>λ visitante: <strong>{dec(la)}</strong></p>
<p>λ total: <strong>{dec(lt)}</strong></p>
</div>

<div>
<h3>Probabilidades</h3>
<p>2+ goles: <strong>{pct(p15)}</strong></p>
<p>3+ goles: <strong>{pct(p25)}</strong></p>
<p>4+ goles: <strong>{pct(p35)}</strong></p>
<p>5+ goles: <strong>{pct(p45)}</strong></p>
<p>BTTS: <strong>{pct(btts)}</strong></p>
</div>

<div>
<h3>Calidad</h3>
<p>Calidad datos:
<strong>{html.escape(str(calidad))}</strong></p>

<p>Confianza BTTS:
<strong>{html.escape(str(conf_btts))}</strong></p>

<p>Score:
<strong>{html.escape(str(score))}</strong></p>

<p>xG bilateral:
<strong>{html.escape(str(xg))}</strong></p>

<p>Dispersión señales:
<strong>{html.escape(str(dispersion))}</strong></p>
</div>

<div>
<h3>Muestras</h3>
<p>Forma local:
<strong>{muestras.get('forma_local','N/D')}</strong></p>

<p>Forma visitante:
<strong>{muestras.get('forma_visitante','N/D')}</strong></p>

<p>Casa local:
<strong>{muestras.get('casa_local','N/D')}</strong></p>

<p>Fuera visitante:
<strong>{muestras.get('fuera_visitante','N/D')}</strong></p>
</div>

</div>

<h3>Razones</h3>
{razones_html}

<h3>Alertas</h3>
{alertas_html}

</section>
"""
        )

    documento = f"""
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">

<title>
Match Goals AI — Ventana analizada V2
</title>

<style>
body {{
    font-family: Arial, sans-serif;
    margin: 24px;
    background: #f5f5f5;
    color: #111;
}}

.notice {{
    background: white;
    border: 1px solid #ddd;
    padding: 15px;
    margin-bottom: 24px;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    background: white;
}}

th, td {{
    border: 1px solid #ddd;
    padding: 9px;
    text-align: center;
}}

th {{
    background: #eee;
}}

td:nth-child(2) {{
    text-align: left;
}}

.card {{
    background: white;
    border: 1px solid #ddd;
    padding: 18px;
    margin: 22px 0;
}}

.grid {{
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(220px, 1fr));
    gap: 15px;
}}

.grid > div {{
    border: 1px solid #eee;
    padding: 12px;
}}

.meta {{
    color: #666;
}}

small {{
    color: #666;
}}
</style>
</head>

<body>

<h1>
Match Goals AI — Ventana analizada V2
</h1>

<div class="notice">
<strong>
Sólo incluye los partidos que fueron procesados
por la ventana de 4 horas.
</strong>
<br><br>

Modelo: J_BT_sin_temporada / BT0.<br>
Ranking: probabilidad estimada de 3+ goles.<br>
ALTA/MEDIA/BAJA = calidad de datos.<br>
FUERTE/MEDIA/DÉBIL en BTTS =
confianza predictiva validada.
</div>

<h2>Ranking de la ventana</h2>

<table>

<thead>
<tr>
<th>#</th>
<th>Partido</th>
<th>λ L</th>
<th>λ V</th>
<th>λ Total</th>
<th>2+</th>
<th>3+</th>
<th>4+</th>
<th>5+</th>
<th>BTTS</th>
<th>Calidad</th>
<th>Conf. BTTS</th>
</tr>
</thead>

<tbody>
{''.join(resumen)}
</tbody>

</table>

<h1>
Detalle partido por partido
</h1>

{''.join(detalles)}

</body>
</html>
"""

    OUT.write_text(
        documento,
        encoding="utf-8",
    )

    print("=" * 78)
    print("REPORTE COMPLETO — VENTANA 4H")
    print("=" * 78)
    print("Partidos:", len(partidos))
    print("HTML:", OUT)
    print("=" * 78)


if __name__ == "__main__":
    main()
