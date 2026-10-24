import argparse
import html
import json
from pathlib import Path

from analysis.confidence_v2 import clasificar_v2


DAY = Path("data/day_predictions.json")
OUT_JSON = Path("data/day_predictions_v2.json")
OUT_HTML = Path("data/report_day_v2.html")


def cargar(path):
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def prob_num(v):
    if v is None:
        return None

    if isinstance(v, str):
        s = v.strip()

        try:
            if s.endswith("%"):
                return float(s[:-1]) / 100
            return float(s)
        except ValueError:
            return None

    try:
        v = float(v)
    except (TypeError, ValueError):
        return None

    # Si accidentalmente viene 65 en vez de .65
    if 1 < v <= 100:
        v /= 100

    return v


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def pct(v):
    v = prob_num(v)

    if v is None:
        return "N/D"

    return f"{v:.1%}"


def dec(v):
    v = num(v)

    if v is None:
        return "N/D"

    return f"{v:.2f}"


def campo_prob(p, *claves):
    for k in claves:
        if k in p:
            v = prob_num(p.get(k))
            if v is not None:
                return v

    return None


def campo_num(p, *claves):
    for k in claves:
        if k in p:
            v = num(p.get(k))
            if v is not None:
                return v

    return None


def es_no_convencional(p):
    texto = " ".join(
        str(p.get(k) or "")
        for k in (
            "competicion",
            "liga",
            "pais",
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
        clave in texto
        for clave in claves
    )


def aplicar_confianza(partido):
    p = dict(partido)

    if es_no_convencional(p):
        p["fuera_modelo_convencional"] = True
        p["calidad_datos"] = "FUERA_MODELO"
        p["calidad_goles"] = "FUERA_MODELO"
        p["confianza_btts"] = "FUERA_MODELO"
        p["alertas_calidad"] = [
            "Formato/competición no convencional; "
            "no comparable con el backtest de fútbol 11."
        ]
        return p

    p["fuera_modelo_convencional"] = False

    mid = (
        p.get("match_id")
        or p.get("id")
        or p.get("flashscore_id")
    )

    if not mid:
        p["confidence_v2_error"] = (
            "Partido sin match_id"
        )
        return p

    try:
        c = clasificar_v2(mid)
    except Exception as e:
        p["confidence_v2_error"] = repr(e)
        return p

    p["confidence_v2"] = c

    p["calidad_datos"] = (
        c.get(
            "calidad_datos_global",
            "BAJA",
        )
    )

    mercados = c.get(
        "mercados",
        {},
    )

    p["confianza_btts"] = (
        mercados.get(
            "BTTS",
            {},
        ).get(
            "confianza_predictiva",
            "NO_VALIDADA",
        )
    )

    p["calidad_btts"] = (
        mercados.get(
            "BTTS",
            {},
        ).get(
            "calidad_datos",
            "BAJA",
        )
    )

    p["calidad_goles"] = (
        mercados.get(
            "+2.5",
            {},
        ).get(
            "calidad_datos",
            p["calidad_datos"],
        )
    )

    detalle = c.get(
        "detalle_v1",
        {},
    )

    p["score_calidad"] = detalle.get(
        "score"
    )

    p["alertas_calidad"] = detalle.get(
        "alertas",
        [],
    )

    return p


def ordenar(partido):
    # Ranking principal:
    # probabilidad de 3+ goles (+2.5)
    p25 = campo_prob(
        partido,
        "+2.5",
        "over_2_5",
        "p_over_2_5",
    )

    lt = campo_num(
        partido,
        "lambda_total",
        "total_lambda",
    )

    return (
        p25 if p25 is not None else -1,
        lt if lt is not None else -1,
    )


def render_console(partidos):
    print("=" * 118)
    print("MATCH GOALS AI — JORNADA V2")
    print("=" * 118)

    for i, p in enumerate(
        partidos,
        1,
    ):
        local = (
            p.get("local")
            or p.get("equipo_local")
            or "Local"
        )

        visitante = (
            p.get("visitante")
            or p.get("equipo_visitante")
            or "Visitante"
        )

        hora = (
            p.get("hora")
            or p.get("time")
            or ""
        )

        lh = campo_num(
            p,
            "lambda_local",
            "lambda_home",
        )

        la = campo_num(
            p,
            "lambda_visitante",
            "lambda_away",
        )

        lt = campo_num(
            p,
            "lambda_total",
            "total_lambda",
        )

        p15 = campo_prob(
            p,
            "+1.5",
            "over_1_5",
        )

        p25 = campo_prob(
            p,
            "+2.5",
            "over_2_5",
        )

        p35 = campo_prob(
            p,
            "+3.5",
            "over_3_5",
        )

        p45 = campo_prob(
            p,
            "+4.5",
            "over_4_5",
        )

        btts = campo_prob(
            p,
            "btts",
            "BTTS",
            "p_btts",
        )

        print()
        print(
            f"{i:02d}. "
            f"{local} vs {visitante}"
            + (
                f" | {hora}"
                if hora
                else ""
            )
        )

        print(
            "    λ: "
            f"{dec(lh)} + {dec(la)}"
            f" = {dec(lt)}"
        )

        print(
            "    2+ "
            f"{pct(p15):>7s}"
            " | 3+ "
            f"{pct(p25):>7s}"
            " | 4+ "
            f"{pct(p35):>7s}"
            " | 5+ "
            f"{pct(p45):>7s}"
            " | BTTS "
            f"{pct(btts):>7s}"
        )

        print(
            "    Calidad datos: "
            f"{p.get('calidad_datos', 'N/D')}"
            " | Calidad goles: "
            f"{p.get('calidad_goles', 'N/D')}"
            " | Confianza BTTS: "
            f"{p.get('confianza_btts', 'N/D')}"
        )

        alertas = p.get(
            "alertas_calidad",
            [],
        )

        if alertas:
            print(
                "    Alertas: "
                + "; ".join(alertas)
            )


def generar_html(partidos):
    filas = []

    for i, p in enumerate(
        partidos,
        1,
    ):
        local = html.escape(
            str(
                p.get("local")
                or p.get("equipo_local")
                or "Local"
            )
        )

        visitante = html.escape(
            str(
                p.get("visitante")
                or p.get("equipo_visitante")
                or "Visitante"
            )
        )

        hora = html.escape(
            str(
                p.get("hora")
                or p.get("time")
                or ""
            )
        )

        lt = campo_num(
            p,
            "lambda_total",
            "total_lambda",
        )

        p15 = campo_prob(
            p,
            "+1.5",
            "over_1_5",
        )

        p25 = campo_prob(
            p,
            "+2.5",
            "over_2_5",
        )

        p35 = campo_prob(
            p,
            "+3.5",
            "over_3_5",
        )

        p45 = campo_prob(
            p,
            "+4.5",
            "over_4_5",
        )

        btts = campo_prob(
            p,
            "btts",
            "BTTS",
            "p_btts",
        )

        alertas = html.escape(
            "; ".join(
                p.get(
                    "alertas_calidad",
                    [],
                )
            )
        )

        filas.append(
            f"""
            <tr>
              <td>{i}</td>
              <td>
                <strong>{local}</strong>
                vs
                <strong>{visitante}</strong>
                <br>
                <small>{hora}</small>
              </td>
              <td>{dec(lt)}</td>
              <td>{pct(p15)}</td>
              <td><strong>{pct(p25)}</strong></td>
              <td>{pct(p35)}</td>
              <td>{pct(p45)}</td>
              <td>{pct(btts)}</td>
              <td>{html.escape(str(p.get('calidad_datos', 'N/D')))}</td>
              <td>{html.escape(str(p.get('confianza_btts', 'N/D')))}</td>
              <td><small>{alertas}</small></td>
            </tr>
            """
        )

    documento = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Match Goals AI — Jornada V2</title>
<style>
body {{
    font-family: Arial, sans-serif;
    margin: 24px;
    background: #f7f7f7;
}}
h1 {{
    margin-bottom: 4px;
}}
.notice {{
    margin-bottom: 20px;
    padding: 12px;
    background: white;
    border: 1px solid #ddd;
}}
table {{
    border-collapse: collapse;
    width: 100%;
    background: white;
}}
th, td {{
    border: 1px solid #ddd;
    padding: 9px;
    text-align: center;
}}
th {{
    position: sticky;
    top: 0;
    background: #eee;
}}
td:nth-child(2) {{
    text-align: left;
}}
small {{
    opacity: .75;
}}
</style>
</head>
<body>

<h1>Match Goals AI — Jornada V2</h1>

<div class="notice">
<strong>Modelo:</strong> J_BT_sin_temporada (BT0)<br>
<strong>Ranking:</strong> probabilidad estimada de 3+ goles.<br>
<strong>Importante:</strong>
ALTA/MEDIA/BAJA en goles representa calidad de datos,
no confianza predictiva validada.
BTTS sí dispone de clasificación predictiva
FUERTE/MEDIA/DÉBIL.
</div>

<table>
<thead>
<tr>
<th>#</th>
<th>Partido</th>
<th>λ total</th>
<th>2+</th>
<th>3+</th>
<th>4+</th>
<th>5+</th>
<th>BTTS</th>
<th>Calidad</th>
<th>Conf. BTTS</th>
<th>Alertas</th>
</tr>
</thead>
<tbody>
{''.join(filas)}
</tbody>
</table>

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
        "--input",
        default=str(DAY),
    )

    args = parser.parse_args()

    entrada = Path(args.input)

    if not entrada.exists():
        raise SystemExit(
            f"No existe {entrada}. "
            "Ejecuta primero analysis.run_day."
        )

    day = cargar(entrada)

    originales = day.get(
        "partidos",
        []
    )

    enriquecidos = [
        aplicar_confianza(p)
        for p in originales
    ]

    convencionales = [
        p for p in enriquecidos
        if not p.get(
            "fuera_modelo_convencional",
            False,
        )
    ]

    no_convencionales = [
        p for p in enriquecidos
        if p.get(
            "fuera_modelo_convencional",
            False,
        )
    ]

    convencionales.sort(
        key=ordenar,
        reverse=True,
    )

    no_convencionales.sort(
        key=ordenar,
        reverse=True,
    )

    enriquecidos = (
        convencionales
        + no_convencionales
    )

    salida = dict(day)
    salida["partidos"] = enriquecidos
    salida["confidence_version"] = (
        "confidence_v2"
    )

    OUT_JSON.write_text(
        json.dumps(
            salida,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    generar_html(
        enriquecidos
    )

    render_console(
        enriquecidos
    )

    print()
    print("=" * 118)
    print(
        "JSON:",
        OUT_JSON,
    )
    print(
        "HTML:",
        OUT_HTML,
    )
    print("=" * 118)


if __name__ == "__main__":
    main()
