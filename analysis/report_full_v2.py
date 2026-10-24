import argparse
import html
import json
from datetime import datetime
from pathlib import Path

from analysis.confidence_v2 import clasificar_v2


BASE = Path("data")
MATCHES = BASE / "matches"
PARTIDOS = BASE / "partidos.json"

OUT_JSON = BASE / "report_full_v2.json"
OUT_HTML = BASE / "report_full_v2.html"


def cargar(path):
    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return None


def normalizar_partidos(datos):
    if isinstance(datos, list):
        return datos

    if not isinstance(datos, dict):
        return []

    for clave in (
        "partidos",
        "matches",
        "eventos",
        "events",
    ):
        if isinstance(datos.get(clave), list):
            return datos[clave]

    # por si partidos.json usa secciones
    salida = []

    for sec in datos.get("secciones", []):
        for p in sec.get("partidos", []):
            x = dict(p)

            if not x.get("competicion"):
                x["competicion"] = (
                    sec.get("titulo")
                    or sec.get("competicion")
                )

            salida.append(x)

    return salida


def match_id(p):
    return (
        p.get("match_id")
        or p.get("id")
        or p.get("flashscore_id")
    )


def fecha_iso(p):
    valor = str(
        p.get("fecha")
        or p.get("date")
        or ""
    ).strip()

    for fmt in (
        "%Y-%m-%d",
        "%d.%m.%y",
        "%d.%m.%Y",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(
                valor,
                fmt,
            ).strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def prob(v):
    if v is None:
        return None

    if isinstance(v, str):
        v = v.strip()

        try:
            if v.endswith("%"):
                return float(v[:-1]) / 100
            v = float(v)
        except ValueError:
            return None

    try:
        v = float(v)
    except Exception:
        return None

    if 1 < v <= 100:
        v /= 100

    return v


def pct(v):
    v = prob(v)

    if v is None:
        return "N/D"

    return f"{v:.1%}"


def dec(v):
    v = num(v)

    if v is None:
        return "N/D"

    return f"{v:.2f}"


def primer_valor(d, *claves):
    if not isinstance(d, dict):
        return None

    for k in claves:
        if d.get(k) is not None:
            return d.get(k)

    return None


def extraer_resultado(mid):
    p = MATCHES / mid / "result.json"
    d = cargar(p)

    if not d:
        return None

    # Intento directo
    fuente = d

    # Algunos result.json guardan varios modelos
    for clave in (
        "J_base",
        "BT0",
        "base",
        "resultado",
    ):
        if isinstance(d.get(clave), dict):
            fuente = d[clave]
            break

    lh = primer_valor(
        fuente,
        "lambda_local",
        "local",
        "lambda_home",
    )

    la = primer_valor(
        fuente,
        "lambda_visitante",
        "visitante",
        "lambda_away",
    )

    lt = primer_valor(
        fuente,
        "lambda_total",
        "total",
        "total_lambda",
    )

    # Si no estaban arriba, buscar estructuras anidadas
    if lh is None or la is None:
        lam = fuente.get("lambda")

        if isinstance(lam, dict):
            lh = (
                lh
                if lh is not None
                else primer_valor(
                    lam,
                    "local",
                    "home",
                )
            )

            la = (
                la
                if la is not None
                else primer_valor(
                    lam,
                    "visitante",
                    "away",
                )
            )

    if lt is None:
        a = num(lh)
        b = num(la)

        if a is not None and b is not None:
            lt = a + b

    probs = {}

    candidatos = [
        fuente,
        fuente.get("probabilidades", {}),
        fuente.get("probabilities", {}),
        fuente.get("mercados", {}),
    ]

    aliases = {
        "+1.5": (
            "+1.5",
            "over_1_5",
            "p_over_1_5",
            "2+",
        ),
        "+2.5": (
            "+2.5",
            "over_2_5",
            "p_over_2_5",
            "3+",
        ),
        "+3.5": (
            "+3.5",
            "over_3_5",
            "p_over_3_5",
            "4+",
        ),
        "+4.5": (
            "+4.5",
            "over_4_5",
            "p_over_4_5",
            "5+",
        ),
        "BTTS": (
            "BTTS",
            "btts",
            "p_btts",
        ),
    }

    for destino, nombres in aliases.items():
        valor = None

        for c in candidatos:
            if not isinstance(c, dict):
                continue

            for nombre in nombres:
                if c.get(nombre) is not None:
                    valor = c.get(nombre)
                    break

            if valor is not None:
                break

        probs[destino] = prob(valor)

    return {
        "lambda_local": num(lh),
        "lambda_visitante": num(la),
        "lambda_total": num(lt),
        **probs,
    }


def es_no_convencional(p):
    texto = " ".join(
        str(p.get(k) or "")
        for k in (
            "competicion",
            "liga",
            "local",
            "visitante",
        )
    ).casefold()

    claves = (
        "kings league",
        "kings world",
        "queens league",
        "club de cuervos",
        "raniza",
        "galacticos del caribe",
        "los chamos",
    )

    return any(
        x in texto
        for x in claves
    )


def enriquecer(p):
    x = dict(p)

    mid = match_id(x)

    x["match_id"] = mid

    if not mid:
        x["analizado"] = False
        return x

    resultado = extraer_resultado(mid)

    if resultado:
        x.update(resultado)
        x["analizado"] = True
    else:
        x["analizado"] = False

    if es_no_convencional(x):
        x["fuera_modelo"] = True
        x["calidad_datos"] = "FUERA_MODELO"
        x["confianza_btts"] = "FUERA_MODELO"
        x["alertas"] = [
            "Formato/competición no convencional; "
            "no comparable con fútbol 11."
        ]
        return x

    x["fuera_modelo"] = False

    if x["analizado"]:
        try:
            c = clasificar_v2(mid)

            x["calidad_datos"] = (
                c.get(
                    "calidad_datos_global",
                    "N/D",
                )
            )

            btts = (
                c.get("mercados", {})
                .get("BTTS", {})
            )

            x["confianza_btts"] = (
                btts.get(
                    "confianza_predictiva",
                    "N/D",
                )
            )

            detalle = c.get(
                "detalle_v1",
                {},
            )

            x["score_calidad"] = (
                detalle.get("score")
            )

            x["razones"] = (
                detalle.get(
                    "razones",
                    [],
                )
            )

            x["alertas"] = (
                detalle.get(
                    "alertas",
                    [],
                )
            )

            x["muestras"] = (
                detalle.get(
                    "muestras",
                    {},
                )
            )

            x["xg_bilateral"] = (
                detalle.get(
                    "xg_bilateral"
                )
            )

            x["dispersion_lambda"] = (
                detalle.get(
                    "dispersion_lambda_senales"
                )
            )

        except Exception as e:
            x["calidad_datos"] = "N/D"
            x["confianza_btts"] = "N/D"
            x["alertas"] = [
                f"Confidence V2: {e!r}"
            ]

    else:
        x["calidad_datos"] = "SIN_ANALIZAR"
        x["confianza_btts"] = "SIN_ANALIZAR"
        x["alertas"] = [
            "No existe result.json para este partido."
        ]

    return x


def clave_ranking(p):
    if p.get("fuera_modelo"):
        grupo = 2
    elif not p.get("analizado"):
        grupo = 1
    else:
        grupo = 0

    p25 = prob(
        p.get("+2.5")
    )

    if p25 is None:
        p25 = -1

    return (
        grupo,
        -p25,
        str(p.get("hora") or ""),
    )


def generar_html(partidos, fecha):
    resumen_rows = []
    detalles = []

    for i, p in enumerate(partidos, 1):
        local = html.escape(
            str(p.get("local") or "")
        )

        visitante = html.escape(
            str(p.get("visitante") or "")
        )

        hora = html.escape(
            str(p.get("hora") or "")
        )

        comp = html.escape(
            str(
                p.get("competicion")
                or p.get("liga")
                or ""
            )
        )

        alertas = "; ".join(
            p.get("alertas", [])
        )

        resumen_rows.append(
            f"""
<tr>
<td>{i}</td>
<td>
<strong>{local}</strong> vs <strong>{visitante}</strong>
<br><small>{hora} · {comp}</small>
</td>
<td>{dec(p.get('lambda_local'))}</td>
<td>{dec(p.get('lambda_visitante'))}</td>
<td>{dec(p.get('lambda_total'))}</td>
<td>{pct(p.get('+1.5'))}</td>
<td><strong>{pct(p.get('+2.5'))}</strong></td>
<td>{pct(p.get('+3.5'))}</td>
<td>{pct(p.get('+4.5'))}</td>
<td>{pct(p.get('BTTS'))}</td>
<td>{html.escape(str(p.get('calidad_datos','N/D')))}</td>
<td>{html.escape(str(p.get('confianza_btts','N/D')))}</td>
</tr>
"""
        )

        razones = p.get(
            "razones",
            []
        )

        muestras = p.get(
            "muestras",
            {}
        )

        razones_html = (
            "<ul>"
            + "".join(
                f"<li>{html.escape(str(r))}</li>"
                for r in razones
            )
            + "</ul>"
            if razones
            else "<p>N/D</p>"
        )

        alertas_html = (
            "<ul>"
            + "".join(
                f"<li>{html.escape(str(a))}</li>"
                for a in p.get(
                    "alertas",
                    [],
                )
            )
            + "</ul>"
            if p.get("alertas")
            else "<p>Sin alertas relevantes.</p>"
        )

        detalles.append(
            f"""
<section class="card">
<h2>{i}. {local} vs {visitante}</h2>

<div class="meta">
{hora} · {comp}
</div>

<div class="grid">
<div>
<h3>Expectativa</h3>
<p>λ local: <strong>{dec(p.get('lambda_local'))}</strong></p>
<p>λ visitante: <strong>{dec(p.get('lambda_visitante'))}</strong></p>
<p>λ total: <strong>{dec(p.get('lambda_total'))}</strong></p>
</div>

<div>
<h3>Probabilidades</h3>
<p>2+ goles: <strong>{pct(p.get('+1.5'))}</strong></p>
<p>3+ goles: <strong>{pct(p.get('+2.5'))}</strong></p>
<p>4+ goles: <strong>{pct(p.get('+3.5'))}</strong></p>
<p>5+ goles: <strong>{pct(p.get('+4.5'))}</strong></p>
<p>BTTS: <strong>{pct(p.get('BTTS'))}</strong></p>
</div>

<div>
<h3>Calidad</h3>
<p>Calidad datos:
<strong>{html.escape(str(p.get('calidad_datos','N/D')))}</strong>
</p>
<p>Confianza BTTS:
<strong>{html.escape(str(p.get('confianza_btts','N/D')))}</strong>
</p>
<p>Score:
<strong>{html.escape(str(p.get('score_calidad','N/D')))}</strong>
</p>
<p>xG bilateral:
<strong>{html.escape(str(p.get('xg_bilateral','N/D')))}</strong>
</p>
</div>

<div>
<h3>Muestras</h3>
<p>Forma local: {muestras.get('forma_local','N/D')}</p>
<p>Forma visitante: {muestras.get('forma_visitante','N/D')}</p>
<p>Casa local: {muestras.get('casa_local','N/D')}</p>
<p>Fuera visitante: {muestras.get('fuera_visitante','N/D')}</p>
</div>
</div>

<h3>Razones</h3>
{razones_html}

<h3>Alertas</h3>
{alertas_html}
</section>
"""
        )

    documento = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Match Goals AI — Reporte completo {fecha}</title>

<style>
body {{
    font-family: Arial, sans-serif;
    background: #f4f4f4;
    margin: 24px;
    color: #111;
}}

h1 {{
    margin-bottom: 5px;
}}

.notice {{
    background: white;
    border: 1px solid #ddd;
    padding: 15px;
    margin: 15px 0 25px 0;
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
    position: sticky;
    top: 0;
}}

td:nth-child(2) {{
    text-align: left;
}}

.card {{
    background: white;
    border: 1px solid #ddd;
    margin: 22px 0;
    padding: 18px;
}}

.grid {{
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(210px, 1fr));
    gap: 15px;
}}

.grid > div {{
    border: 1px solid #eee;
    padding: 12px;
}}

.meta {{
    color: #666;
    margin-bottom: 15px;
}}

small {{
    color: #666;
}}
</style>
</head>

<body>

<h1>Match Goals AI — Reporte completo V2</h1>

<div class="notice">
<strong>Fecha:</strong> {fecha}<br>
<strong>Modelo:</strong> J_BT_sin_temporada / BT0<br>
<strong>Ranking:</strong> 3+ goles, sólo fútbol convencional.<br>
<strong>Nota:</strong>
ALTA/MEDIA/BAJA representa calidad de datos.
Sólo BTTS FUERTE/MEDIA/DÉBIL tiene validación predictiva específica.
</div>

<h2>Ranking general</h2>

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
{''.join(resumen_rows)}
</tbody>
</table>

<h1>Detalle partido por partido</h1>

{''.join(detalles)}

</body>
</html>
"""

    OUT_HTML.write_text(
        documento,
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        required=True,
        help="YYYY-MM-DD",
    )

    args = parser.parse_args()

    datos = cargar(PARTIDOS)

    if datos is None:
        raise SystemExit(
            "No pude leer data/partidos.json"
        )

    todos = normalizar_partidos(datos)

    seleccionados = [
        p
        for p in todos
        if fecha_iso(p) == args.date
    ]

    if not seleccionados:
        raise SystemExit(
            f"No encontré partidos para {args.date}"
        )

    completos = [
        enriquecer(p)
        for p in seleccionados
    ]

    completos.sort(
        key=clave_ranking
    )

    OUT_JSON.write_text(
        json.dumps(
            {
                "fecha": args.date,
                "total": len(completos),
                "partidos": completos,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    generar_html(
        completos,
        args.date,
    )

    analizados = sum(
        1
        for p in completos
        if p.get("analizado")
    )

    fuera = sum(
        1
        for p in completos
        if p.get("fuera_modelo")
    )

    print("=" * 78)
    print("REPORTE COMPLETO V2")
    print("=" * 78)
    print("Fecha       :", args.date)
    print("Total día   :", len(completos))
    print("Analizados  :", analizados)
    print(
        "Sin analizar:",
        len(completos) - analizados,
    )
    print("Fuera modelo:", fuera)
    print()
    print("JSON:", OUT_JSON)
    print("HTML:", OUT_HTML)
    print("=" * 78)


if __name__ == "__main__":
    main()
