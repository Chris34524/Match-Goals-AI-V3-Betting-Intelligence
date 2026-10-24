import argparse
import json
import math
import re
import subprocess
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EVAL = DATA / "evaluation"
ARCHIVE = EVAL / "predictions_archive.jsonl"


BASELINE = {
    "+1.5": 0.1752,
    "+2.5": 0.2425,
    "+3.5": 0.2193,
    "BTTS": 0.2575,
    "1X2": 0.6077,
}


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def match_id(obj):
    if not isinstance(obj, dict):
        return None

    return (
        obj.get("match_id")
        or obj.get("flashscore_id")
        or obj.get("id")
        or obj.get("mid")
    )


def status_final(obj):
    if not isinstance(obj, dict):
        return False

    status = str(
        obj.get("status")
        or obj.get("estado")
        or obj.get("state")
        or ""
    ).lower()

    if not status:
        return True

    finales = (
        "finished",
        "final",
        "terminado",
        "finalizado",
        "after penalties",
        "after extra time",
        "ft",
    )

    return any(
        x in status
        for x in finales
    )


def extraer_score(obj):
    if not isinstance(obj, dict):
        return None

    pares = (
        ("gol_local", "gol_visitante"),
        ("goles_local", "goles_visitante"),
        ("home_score", "away_score"),
        ("score_home", "score_away"),
        ("local_score", "visitante_score"),
        ("homeScore", "awayScore"),
        ("scoreHome", "scoreAway"),
        ("home", "away"),
    )

    for a, b in pares:
        if a in obj and b in obj:
            x = num(obj.get(a))
            y = num(obj.get(b))

            if (
                x is not None
                and y is not None
                and status_final(obj)
            ):
                return int(x), int(y)

    score = obj.get("score")

    if isinstance(score, dict):
        for a, b in (
            ("home", "away"),
            ("local", "visitante"),
            ("homeScore", "awayScore"),
        ):
            x = num(score.get(a))
            y = num(score.get(b))

            if (
                x is not None
                and y is not None
                and status_final(obj)
            ):
                return int(x), int(y)

    for k in (
        "resultado",
        "result",
        "score",
        "marcador",
    ):
        v = obj.get(k)

        if isinstance(v, str):
            m = re.search(
                r"(\d+)\s*[-:]\s*(\d+)",
                v,
            )

            if m and status_final(obj):
                return (
                    int(m.group(1)),
                    int(m.group(2)),
                )

    return None


def buscar_objeto_por_id(obj, objetivo):
    hallados = []

    if isinstance(obj, dict):
        if str(
            match_id(obj) or ""
        ) == str(objetivo):
            hallados.append(obj)

        for v in obj.values():
            hallados.extend(
                buscar_objeto_por_id(
                    v,
                    objetivo,
                )
            )

    elif isinstance(obj, list):
        for v in obj:
            hallados.extend(
                buscar_objeto_por_id(
                    v,
                    objetivo,
                )
            )

    return hallados


def cargar_json(path):
    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return None


def score_desde_fuente(path, objetivo):
    data = cargar_json(path)

    if data is None:
        return None

    for obj in buscar_objeto_por_id(
        data,
        objetivo,
    ):
        sc = extraer_score(obj)

        if sc is not None:
            return sc

    return None


def buscar_score(mid, resultados_extra=None):
    if resultados_extra:
        sc = score_desde_fuente(
            resultados_extra,
            mid,
        )

        if sc:
            return sc, str(resultados_extra)

    partidos = DATA / "partidos.json"

    if partidos.exists():
        sc = score_desde_fuente(
            partidos,
            mid,
        )

        if sc:
            return sc, str(partidos)

    carpeta = DATA / "matches" / str(mid)

    if carpeta.exists():
        candidatos = [
            carpeta / "match.json",
            carpeta / "history.json",
            carpeta / "enriched.json",
            carpeta / "standings.json",
        ]

        candidatos.extend(
            sorted(
                carpeta.glob("*.json")
            )
        )

        vistos = set()

        for p in candidatos:
            if p in vistos:
                continue

            vistos.add(p)

            if not p.exists():
                continue

            if p.name in (
                "result.json",
                "lambda_comparison.json",
                "confidence.json",
                "confidence_v2.json",
            ):
                continue

            sc = score_desde_fuente(
                p,
                mid,
            )

            if sc:
                return sc, str(p)

    return None, None


def cargar_snapshots(fecha):
    mejores = {}

    if not ARCHIVE.exists():
        return mejores

    with ARCHIVE.open(
        encoding="utf-8"
    ) as f:
        for linea in f:
            try:
                x = json.loads(linea)
            except Exception:
                continue

            if str(
                x.get("date")
            ) != str(fecha):
                continue

            mid = str(
                x.get("match_id")
                or ""
            )

            if not mid:
                continue

            # Nos quedamos con el PRIMER snapshot:
            # el más conservador frente a reanálisis posteriores.
            if mid not in mejores:
                mejores[mid] = x

    return mejores


def brier(p, y):
    if p is None:
        return None

    return (
        float(p) - float(y)
    ) ** 2


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--date",
        required=True,
    )

    ap.add_argument(
        "--results",
        default=None,
        help=(
            "JSON opcional con resultados finales."
        ),
    )

    ap.add_argument(
        "--open",
        action="store_true",
    )

    args = ap.parse_args()

    snapshots = cargar_snapshots(
        args.date
    )

    if not snapshots:
        raise SystemExit(
            "No encontré snapshots prematch "
            f"para {args.date}"
        )

    results_path = (
        ROOT / args.results
        if args.results
        else None
    )

    métricas = defaultdict(
        lambda: {
            "n": 0,
            "brier_sum": 0.0,
            "p_sum": 0.0,
            "y_sum": 0.0,
            "hits": 0,
        }
    )

    settled = []

    mae_total = []
    mae_home = []
    mae_away = []

    for mid, pred in snapshots.items():
        sc, fuente = buscar_score(
            mid,
            results_path,
        )

        if sc is None:
            continue

        gh, ga = sc
        total = gh + ga

        fila = {
            "match_id": mid,
            "local": pred.get("local"),
            "visitante": pred.get("visitante"),
            "competicion": pred.get("competicion"),
            "goles_local": gh,
            "goles_visitante": ga,
            "total_goles": total,
            "fuente_resultado": fuente,
        }

        mercados = {
            "+1.5": (
                num(pred.get("+1.5")),
                int(total >= 2),
            ),
            "+2.5": (
                num(pred.get("+2.5")),
                int(total >= 3),
            ),
            "+3.5": (
                num(pred.get("+3.5")),
                int(total >= 4),
            ),
            "-1.5": (
                num(pred.get("-1.5")),
                int(total <= 1),
            ),
            "-2.5": (
                num(pred.get("-2.5")),
                int(total <= 2),
            ),
            "-3.5": (
                num(pred.get("-3.5")),
                int(total <= 3),
            ),
            "BTTS": (
                num(pred.get("BTTS")),
                int(
                    gh > 0
                    and ga > 0
                ),
            ),
        }

        fila["mercados"] = {}

        for nombre, (p, y) in mercados.items():
            if p is None:
                continue

            br = brier(p, y)
            hit = int(
                (p >= 0.5) == bool(y)
            )

            m = métricas[nombre]
            m["n"] += 1
            m["brier_sum"] += br
            m["p_sum"] += p
            m["y_sum"] += y
            m["hits"] += hit

            fila["mercados"][nombre] = {
                "p": p,
                "real": y,
                "brier": br,
                "acierto_50": hit,
            }

        p1 = num(pred.get("prob_1"))
        px = num(pred.get("prob_X"))
        p2 = num(pred.get("prob_2"))

        if (
            p1 is not None
            and px is not None
            and p2 is not None
        ):
            if gh > ga:
                real = "1"
                y = [1, 0, 0]
            elif gh == ga:
                real = "X"
                y = [0, 1, 0]
            else:
                real = "2"
                y = [0, 0, 1]

            probs = [p1, px, p2]

            br3 = sum(
                (p - yy) ** 2
                for p, yy in zip(
                    probs,
                    y,
                )
            )

            predicho = (
                ["1", "X", "2"][
                    max(
                        range(3),
                        key=lambda i: probs[i],
                    )
                ]
            )

            m = métricas["1X2"]
            m["n"] += 1
            m["brier_sum"] += br3
            m["hits"] += int(
                predicho == real
            )

            fila["1X2"] = {
                "p1": p1,
                "px": px,
                "p2": p2,
                "real": real,
                "predicho": predicho,
                "brier": br3,
                "acierto": int(
                    predicho == real
                ),
            }

        lh = num(
            pred.get("lambda_local")
        )
        la = num(
            pred.get("lambda_visitante")
        )
        lt = num(
            pred.get("lambda_total")
        )

        if lh is not None:
            mae_home.append(
                abs(lh - gh)
            )

        if la is not None:
            mae_away.append(
                abs(la - ga)
            )

        if lt is not None:
            mae_total.append(
                abs(lt - total)
            )

        settled.append(fila)

    resumen = {}

    for nombre, m in métricas.items():
        n = m["n"]

        if not n:
            continue

        r = {
            "n": n,
            "brier": (
                m["brier_sum"] / n
            ),
            "accuracy": (
                m["hits"] / n
            ),
        }

        if nombre != "1X2":
            r["prob_media"] = (
                m["p_sum"] / n
            )
            r["frecuencia_real"] = (
                m["y_sum"] / n
            )
            r["error_calibracion_pp"] = (
                100
                * (
                    r["prob_media"]
                    - r["frecuencia_real"]
                )
            )

        if nombre in BASELINE:
            r["baseline_brier"] = (
                BASELINE[nombre]
            )
            r["delta_vs_baseline"] = (
                r["brier"]
                - BASELINE[nombre]
            )

        resumen[nombre] = r

    n_partidos = len(settled)

    if n_partidos < 50:
        decisión = (
            "MANTENER BT0 — muestra nueva todavía "
            "demasiado pequeña para ajustar."
        )

    elif n_partidos < 200:
        decisión = (
            "MANTENER BT0 — revisar métricas, pero "
            "acumular al menos 200 partidos fuera "
            "de muestra antes de modificar pesos."
        )

    else:
        peores = 0

        for k in (
            "+1.5",
            "+2.5",
            "+3.5",
            "BTTS",
        ):
            r = resumen.get(k)

            if (
                r
                and r.get(
                    "delta_vs_baseline",
                    0,
                ) > 0.02
            ):
                peores += 1

        if peores >= 2:
            decisión = (
                "REVISAR CHALLENGERS — hay deterioro "
                "material en al menos dos mercados. "
                "No ajustar automáticamente: primero "
                "backtest temporal y bootstrap."
            )
        else:
            decisión = (
                "MANTENER BT0 — no hay evidencia "
                "suficiente para sustituir el modelo."
            )

    salida = {
        "date": args.date,
        "partidos_snapshot": len(
            snapshots
        ),
        "partidos_liquidados": n_partidos,
        "metricas": resumen,
        "lambda_mae": {
            "local": (
                sum(mae_home) / len(mae_home)
                if mae_home
                else None
            ),
            "visitante": (
                sum(mae_away) / len(mae_away)
                if mae_away
                else None
            ),
            "total": (
                sum(mae_total) / len(mae_total)
                if mae_total
                else None
            ),
        },
        "decision_modelo": decisión,
        "partidos": settled,
    }

    EVAL.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_out = (
        EVAL
        / f"effectiveness_{args.date}.json"
    )

    json_out.write_text(
        json.dumps(
            salida,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    filas = []

    for mercado, r in resumen.items():
        filas.append(
            f"""
            <tr>
              <td><strong>{mercado}</strong></td>
              <td>{r['n']}</td>
              <td>{r['brier']:.4f}</td>
              <td>
                {r.get('baseline_brier', float('nan')):.4f}
                {
                    ''
                    if 'baseline_brier' in r
                    else 'N/D'
                }
              </td>
              <td>
                {
                    f"{r['accuracy']*100:.1f}%"
                }
              </td>
              <td>
                {
                    f"{r.get('prob_media', 0)*100:.1f}%"
                    if 'prob_media' in r
                    else '—'
                }
              </td>
              <td>
                {
                    f"{r.get('frecuencia_real', 0)*100:.1f}%"
                    if 'frecuencia_real' in r
                    else '—'
                }
              </td>
            </tr>
            """
        )

    partidos_html = []

    for x in settled:
        partidos_html.append(
            f"""
            <tr>
              <td>
                {x.get('local','')}
                vs
                {x.get('visitante','')}
              </td>
              <td>
                {x['goles_local']}
                -
                {x['goles_visitante']}
              </td>
              <td>
                {x['total_goles']}
              </td>
            </tr>
            """
        )

    html_out = (
        EVAL
        / f"effectiveness_{args.date}.html"
    )

    html_out.write_text(
        f"""
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Efectividad Match Goals AI</title>
<style>
body {{
    font-family: Arial, sans-serif;
    background: #111722;
    color: #edf1f5;
    margin: 0;
    padding: 28px;
}}
.card {{
    background: #1a2230;
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 22px;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th,td {{
    padding: 9px;
    border-bottom: 1px solid #344052;
    text-align: center;
}}
th {{
    background: #252f40;
}}
.decision {{
    font-size: 20px;
    font-weight: bold;
}}
small {{
    opacity: .7;
}}
</style>
</head>
<body>

<div class="card">
<h1>Evaluación del modelo BT0</h1>
<p>Fecha: {args.date}</p>
<p>
Snapshots: {len(snapshots)}
|
Liquidados: {n_partidos}
</p>
<p class="decision">
{decisión}
</p>
</div>

<div class="card">
<h2>Métricas por mercado</h2>
<table>
<thead>
<tr>
<th>Mercado</th>
<th>N</th>
<th>Brier actual</th>
<th>Brier referencia</th>
<th>Acierto</th>
<th>P media</th>
<th>Real</th>
</tr>
</thead>
<tbody>
{''.join(filas)}
</tbody>
</table>
</div>

<div class="card">
<h2>Error de λ</h2>
<p>
MAE local:
{
    f"{salida['lambda_mae']['local']:.3f}"
    if salida['lambda_mae']['local'] is not None
    else 'N/D'
}
</p>
<p>
MAE visitante:
{
    f"{salida['lambda_mae']['visitante']:.3f}"
    if salida['lambda_mae']['visitante'] is not None
    else 'N/D'
}
</p>
<p>
MAE total:
{
    f"{salida['lambda_mae']['total']:.3f}"
    if salida['lambda_mae']['total'] is not None
    else 'N/D'
}
</p>
</div>

<div class="card">
<h2>Partidos liquidados</h2>
<table>
<thead>
<tr>
<th>Partido</th>
<th>Resultado</th>
<th>Goles</th>
</tr>
</thead>
<tbody>
{''.join(partidos_html)}
</tbody>
</table>
</div>

</body>
</html>
        """,
        encoding="utf-8",
    )

    print("=" * 90)
    print("EVALUACIÓN BT0")
    print("=" * 90)
    print("Fecha:", args.date)
    print(
        "Snapshots:",
        len(snapshots),
    )
    print(
        "Liquidados:",
        n_partidos,
    )
    print()
    print(decisión)
    print()
    print("JSON:", json_out)
    print("HTML:", html_out)

    if args.open:
        r = subprocess.run(
            [
                "wslpath",
                "-w",
                str(html_out),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        subprocess.Popen(
            [
                "cmd.exe",
                "/C",
                "start",
                "",
                r.stdout.strip(),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


if __name__ == "__main__":
    main()
