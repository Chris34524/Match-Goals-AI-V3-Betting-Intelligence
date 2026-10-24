import argparse
import html
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

OUT_JSON = EVAL / "effectiveness_cumulative.json"
OUT_HTML = EVAL / "effectiveness_cumulative.html"


BASELINE = {
    "+1.5": 0.1752,
    "-1.5": 0.1752,
    "+2.5": 0.2425,
    "-2.5": 0.2425,
    "+3.5": 0.2193,
    "-3.5": 0.2193,
    "BTTS": 0.2575,
    "1X2": 0.6077,
}


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def esc(v):
    return html.escape(str(v or ""))


def cargar_snapshots():
    """
    Recupera el PRIMER snapshot de cada partido y fecha.
    Sirve además para recuperar competición en evaluaciones
    antiguas donde todavía no se guardaba en settled.
    """
    out = {}

    if not ARCHIVE.exists():
        return out

    with ARCHIVE.open(
        encoding="utf-8"
    ) as f:
        for line in f:
            try:
                x = json.loads(line)
            except Exception:
                continue

            fecha = str(x.get("date") or "")
            mid = str(x.get("match_id") or "")

            if not fecha or not mid:
                continue

            key = (fecha, mid)

            if key not in out:
                out[key] = x

    return out


def segmento(competicion, local="", visitante=""):
    texto = " ".join(
        [
            str(competicion or ""),
            str(local or ""),
            str(visitante or ""),
        ]
    ).lower()

    juvenil = bool(
        re.search(
            r"\bsub[- ]?\d+\b|\bu[- ]?\d+\b|under[- ]?\d+",
            texto,
        )
    )

    femenil = any(
        x in texto
        for x in (
            "femenil",
            "femenina",
            "women",
            " wfc",
            " femenino",
        )
    )

    if juvenil and femenil:
        return "JUVENIL_FEMENIL"

    if juvenil:
        return "JUVENIL"

    if femenil:
        return "FEMENIL"

    if any(
        x in texto
        for x in (
            "kings league",
            "queens league",
        )
    ):
        return "NO_CONVENCIONAL"

    if any(
        x in texto
        for x in (
            "amistoso",
            "friendly",
        )
    ):
        return "AMISTOSO"

    if any(
        x in texto
        for x in (
            "(am)",
            " amateur",
            "reserva",
            "reserves",
            "reserve",
        )
    ):
        return "RESERVA_AMATEUR"

    return "SENIOR_CONVENCIONAL"


def nuevo_acum():
    return defaultdict(
        lambda: {
            "n": 0,
            "brier_sum": 0.0,
            "p_sum": 0.0,
            "y_sum": 0.0,
            "hits": 0,
            "binario": True,
        }
    )


def agregar_binario(acum, mercado, info):
    p = num(info.get("p"))
    y = num(info.get("real"))
    br = num(info.get("brier"))

    if p is None or y is None:
        return

    if br is None:
        br = (p - y) ** 2

    hit = info.get("acierto_50")

    if hit is None:
        hit = int(
            (p >= 0.5)
            == bool(y)
        )

    a = acum[mercado]

    a["n"] += 1
    a["brier_sum"] += br
    a["p_sum"] += p
    a["y_sum"] += y
    a["hits"] += int(hit)
    a["binario"] = True


def agregar_1x2(acum, info):
    br = num(info.get("brier"))

    if br is None:
        return

    a = acum["1X2"]

    a["n"] += 1
    a["brier_sum"] += br
    a["hits"] += int(
        info.get("acierto", 0)
    )
    a["binario"] = False


def confianza_mercado(nombre, r):
    n = r.get("n", 0)

    if n < 50:
        return "INSUFICIENTE"

    brier = num(r.get("brier"))
    baseline = BASELINE.get(nombre)

    if nombre == "1X2":
        if (
            brier is not None
            and baseline is not None
            and brier <= baseline
        ):
            return "MEDIA"

        return "BAJA"

    gap = abs(
        num(r.get("prob_media")) -
        num(r.get("frecuencia_real"))
    )

    if (
        brier is not None
        and baseline is not None
        and brier <= baseline
        and gap <= 0.03
    ):
        return "ALTA"

    if (
        brier is not None
        and baseline is not None
        and brier <= baseline * 1.05
        and gap <= 0.06
    ):
        return "MEDIA"

    return "BAJA"


def resumir(acum):
    out = {}

    for mercado, a in acum.items():
        n = a["n"]

        if not n:
            continue

        r = {
            "n": n,
            "brier": (
                a["brier_sum"] / n
            ),
            "accuracy": (
                a["hits"] / n
            ),
        }

        baseline = BASELINE.get(
            mercado
        )

        if baseline is not None:
            r["baseline_brier"] = baseline
            r["delta_vs_baseline"] = (
                r["brier"] - baseline
            )

        if a["binario"]:
            r["prob_media"] = (
                a["p_sum"] / n
            )

            r["frecuencia_real"] = (
                a["y_sum"] / n
            )

            r["error_calibracion_pp"] = (
                100
                * (
                    r["prob_media"]
                    - r["frecuencia_real"]
                )
            )

        r["confianza_mercado"] = (
            confianza_mercado(
                mercado,
                r,
            )
        )

        out[mercado] = r

    return out


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--open",
        action="store_true",
    )

    args = ap.parse_args()

    snapshots = cargar_snapshots()

    global_acum = nuevo_acum()
    segment_acum = defaultdict(
        nuevo_acum
    )

    partidos_segmento = defaultdict(set)

    vistos = set()
    fechas = set()

    archivos = sorted(
        EVAL.glob(
            "effectiveness_????-??-??.json"
        )
    )

    for path in archivos:
        try:
            d = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            continue

        fecha = str(
            d.get("date")
            or path.stem.replace(
                "effectiveness_",
                "",
            )
        )

        fechas.add(fecha)

        for p in d.get(
            "partidos",
            []
        ):
            mid = str(
                p.get("match_id")
                or ""
            )

            if not mid:
                continue

            key = (
                fecha,
                mid,
            )

            # Evitar duplicados.
            if key in vistos:
                continue

            vistos.add(key)

            snap = snapshots.get(
                key,
                {},
            )

            competicion = (
                p.get("competicion")
                or snap.get("competicion")
                or ""
            )

            seg = segmento(
                competicion,
                p.get("local"),
                p.get("visitante"),
            )

            partidos_segmento[
                seg
            ].add(key)

            for mercado, info in (
                p.get(
                    "mercados",
                    {}
                )
            ).items():

                agregar_binario(
                    global_acum,
                    mercado,
                    info,
                )

                agregar_binario(
                    segment_acum[seg],
                    mercado,
                    info,
                )

            if isinstance(
                p.get("1X2"),
                dict,
            ):
                agregar_1x2(
                    global_acum,
                    p["1X2"],
                )

                agregar_1x2(
                    segment_acum[seg],
                    p["1X2"],
                )

    metricas = resumir(
        global_acum
    )

    segmentos = {}

    for seg, acum in (
        segment_acum.items()
    ):
        segmentos[seg] = {
            "n_partidos": len(
                partidos_segmento[seg]
            ),
            "metricas": resumir(
                acum
            ),
        }

    n_total = len(vistos)

    if n_total < 200:
        decision = (
            "MANTENER BT0 — todavía no hay "
            "200 partidos acumulados fuera de muestra."
        )
    else:
        deteriorados = []

        for mercado in (
            "+1.5",
            "+2.5",
            "+3.5",
            "BTTS",
        ):
            r = metricas.get(
                mercado,
                {}
            )

            delta = num(
                r.get(
                    "delta_vs_baseline"
                )
            )

            if (
                delta is not None
                and delta > 0.02
            ):
                deteriorados.append(
                    mercado
                )

        if len(deteriorados) >= 2:
            decision = (
                "REVISAR CHALLENGERS — deterioro "
                "material acumulado en: "
                + ", ".join(deteriorados)
                + ". No modificar BT0 sin "
                  "backtest temporal y bootstrap."
            )
        else:
            decision = (
                "MANTENER BT0 — la evidencia "
                "acumulada no justifica cambiar pesos."
            )

    salida = {
        "fechas_incluidas": sorted(
            fechas
        ),
        "partidos_unicos": n_total,
        "metricas": metricas,
        "segmentos": segmentos,
        "decision_modelo": decision,
    }

    OUT_JSON.write_text(
        json.dumps(
            salida,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    filas = []

    for mercado, r in (
        metricas.items()
    ):
        pm = r.get("prob_media")
        real = r.get(
            "frecuencia_real"
        )

        filas.append(
            f"""
            <tr>
              <td><strong>{esc(mercado)}</strong></td>
              <td>{r['n']}</td>
              <td>{r['brier']:.4f}</td>
              <td>{
                  f"{r['baseline_brier']:.4f}"
                  if r.get('baseline_brier') is not None
                  else '—'
              }</td>
              <td>{r['accuracy']*100:.1f}%</td>
              <td>{
                  f"{pm*100:.1f}%"
                  if pm is not None
                  else '—'
              }</td>
              <td>{
                  f"{real*100:.1f}%"
                  if real is not None
                  else '—'
              }</td>
              <td>
                <strong>
                  {esc(r['confianza_mercado'])}
                </strong>
              </td>
            </tr>
            """
        )

    seg_html = []

    for seg, info in sorted(
        segmentos.items()
    ):
        rows = []

        for mercado, r in (
            info["metricas"].items()
        ):
            rows.append(
                f"""
                <tr>
                  <td>{esc(mercado)}</td>
                  <td>{r['n']}</td>
                  <td>{r['brier']:.4f}</td>
                  <td>
                    {esc(r['confianza_mercado'])}
                  </td>
                </tr>
                """
            )

        seg_html.append(
            f"""
            <div class="card">
              <h2>{esc(seg)}</h2>
              <p>
                Partidos:
                {info['n_partidos']}
              </p>
              <table>
                <thead>
                  <tr>
                    <th>Mercado</th>
                    <th>N</th>
                    <th>Brier</th>
                    <th>Confianza</th>
                  </tr>
                </thead>
                <tbody>
                  {''.join(rows)}
                </tbody>
              </table>
            </div>
            """
        )

    OUT_HTML.write_text(
        f"""
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Efectividad acumulada Match Goals AI</title>
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
  font-size: 19px;
  font-weight: bold;
}}
</style>
</head>

<body>

<div class="card">
<h1>Evaluación acumulada BT0</h1>

<p>
Fechas incluidas:
{len(fechas)}
</p>

<p>
Partidos únicos:
<strong>{n_total}</strong>
</p>

<p class="decision">
{esc(decision)}
</p>
</div>

<div class="card">
<h2>Métricas acumuladas</h2>

<table>
<thead>
<tr>
<th>Mercado</th>
<th>N</th>
<th>Brier</th>
<th>Referencia</th>
<th>Acierto</th>
<th>P media</th>
<th>Real</th>
<th>Confianza</th>
</tr>
</thead>

<tbody>
{''.join(filas)}
</tbody>
</table>
</div>

{''.join(seg_html)}

</body>
</html>
        """,
        encoding="utf-8",
    )

    print()
    print("=" * 90)
    print("EVALUACIÓN ACUMULADA BT0")
    print("=" * 90)
    print(
        "Fechas:",
        len(fechas),
    )
    print(
        "Partidos únicos:",
        n_total,
    )
    print()

    for mercado, r in (
        metricas.items()
    ):
        print(
            f"{mercado:8}",
            f"N={r['n']:4}",
            f"Brier={r['brier']:.4f}",
            f"Conf={r['confianza_mercado']}",
        )

    print()
    print(decision)
    print()
    print("JSON:", OUT_JSON)
    print("HTML:", OUT_HTML)

    if args.open:
        r = subprocess.run(
            [
                "wslpath",
                "-w",
                str(OUT_HTML),
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
