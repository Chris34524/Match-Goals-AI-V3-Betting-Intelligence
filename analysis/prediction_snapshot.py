import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "data" / "evaluation"
ARCHIVE = EVAL / "predictions_archive.jsonl"


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def mid(p):
    return (
        p.get("match_id")
        or p.get("id")
        or p.get("flashscore_id")
    )


def prob(p, *keys):
    for k in keys:
        if k in p:
            x = num(p.get(k))
            if x is not None:
                return x
    return None


def fuerza(p):
    if p is None:
        return "N/D"

    if p >= 0.70:
        return "FUERTE"

    if p >= 0.62:
        return "MEDIA"

    if p >= 0.55:
        return "DÉBIL"

    return "SIN SEÑAL"


def pct(p):
    if p is None:
        return None
    return round(p, 8)


def enriquecer(p):
    q = dict(p)

    o15 = prob(q, "+1.5", "over_1_5")
    o25 = prob(q, "+2.5", "over_2_5")
    o35 = prob(q, "+3.5", "over_3_5")
    btts = prob(q, "BTTS", "btts")

    p1 = prob(q, "prob_1", "1")
    px = prob(q, "prob_X", "X")
    p2 = prob(q, "prob_2", "2")

    u15 = None if o15 is None else 1 - o15
    u25 = None if o25 is None else 1 - o25
    u35 = None if o35 is None else 1 - o35
    btts_no = None if btts is None else 1 - btts

    q["-1.5"] = pct(u15)
    q["-2.5"] = pct(u25)
    q["-3.5"] = pct(u35)
    q["BTTS_NO"] = pct(btts_no)

    if p1 is not None and px is not None and p2 is not None:
        q["prob_1X"] = pct(p1 + px)
        q["prob_X2"] = pct(px + p2)
        q["prob_12"] = pct(p1 + p2)

        ganador = max(
            [
                ("1", p1),
                ("X", px),
                ("2", p2),
            ],
            key=lambda x: x[1],
        )

        q["favor_1x2"] = {
            "resultado": ganador[0],
            "probabilidad": pct(ganador[1]),
            "confianza_predictiva": "NO_VALIDADA",
        }

    mercados = {}

    for nombre, valor in (
        ("+1.5", o15),
        ("+2.5", o25),
        ("+3.5", o35),
        ("-1.5", u15),
        ("-2.5", u25),
        ("-3.5", u35),
        ("BTTS_SI", btts),
        ("BTTS_NO", btts_no),
    ):
        mercados[nombre] = {
            "probabilidad": pct(valor),
            "nivel": fuerza(valor),
        }

    q["prediccion_operativa"] = mercados

    return q


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--input",
        default="data/selected_predictions_v2.json",
    )

    ap.add_argument(
        "--date",
        required=True,
    )

    args = ap.parse_args()

    src = ROOT / args.input

    data = json.loads(
        src.read_text(encoding="utf-8")
    )

    partidos = data.get("partidos", [])

    ahora = datetime.now(
        timezone.utc
    ).isoformat()

    nuevos = []

    EVAL.mkdir(
        parents=True,
        exist_ok=True,
    )

    snapshot_dir = (
        EVAL
        / "snapshots"
        / args.date
    )

    snapshot_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for p in partidos:
        q = enriquecer(p)
        nuevos.append(q)

        registro = {
            "snapshot_at": ahora,
            "date": args.date,
            "match_id": mid(q),
            "local": q.get("local"),
            "visitante": q.get("visitante"),
            "competicion": (
                q.get("competicion")
                or q.get("league")
            ),
            "hora": q.get("hora"),
            "modelo": (
                q.get("modelo_lambda")
                or "J_BT_sin_temporada"
            ),
            "lambda_local": num(
                q.get("lambda_local")
            ),
            "lambda_visitante": num(
                q.get("lambda_visitante")
            ),
            "lambda_total": num(
                q.get("lambda_total")
            ),
            "+1.5": prob(q, "+1.5"),
            "+2.5": prob(q, "+2.5"),
            "+3.5": prob(q, "+3.5"),
            "-1.5": prob(q, "-1.5"),
            "-2.5": prob(q, "-2.5"),
            "-3.5": prob(q, "-3.5"),
            "BTTS": prob(q, "BTTS"),
            "BTTS_NO": prob(q, "BTTS_NO"),
            "prob_1": prob(q, "prob_1"),
            "prob_X": prob(q, "prob_X"),
            "prob_2": prob(q, "prob_2"),
            "prob_1X": prob(q, "prob_1X"),
            "prob_X2": prob(q, "prob_X2"),
            "prob_12": prob(q, "prob_12"),
            "calidad_datos": q.get(
                "calidad_datos"
            ),
            "confianza_btts": q.get(
                "confianza_btts"
            ),
            "prediccion_operativa": q.get(
                "prediccion_operativa"
            ),
            "mejores_apuestas": q.get(
                "mejores_apuestas"
            ),
        }

        with ARCHIVE.open(
            "a",
            encoding="utf-8",
        ) as f:
            f.write(
                json.dumps(
                    registro,
                    ensure_ascii=False,
                )
                + "\n"
            )

    data["partidos"] = nuevos
    data["snapshot_at"] = ahora
    data["snapshot_date"] = args.date

    src.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    stamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    snapfile = (
        snapshot_dir
        / f"predicciones_{stamp}.json"
    )

    snapfile.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 90)
    print("SNAPSHOT PREMATCH GUARDADO")
    print("=" * 90)
    print("Fecha:", args.date)
    print("Partidos:", len(nuevos))
    print("Archivo:", snapfile)
    print("Histórico:", ARCHIVE)


if __name__ == "__main__":
    main()
