import argparse
import json
from pathlib import Path

from analysis.backtest_target import cargar_target
from analysis.poisson import analizar


BASE = Path("data/matches")

METODOS = {
    "BT0": "J_BT_sin_temporada",
    "BT10": "BT_H2H_10pct",
    "BT15": "BT_H2H_15pct",
    "BT20": "BT_H2H_20pct",
}


def argumentos():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--match-id",
        required=True,
    )
    return parser.parse_args()


def brier(probabilidad, ocurrido):
    y = 1.0 if ocurrido else 0.0
    return (probabilidad - y) ** 2


def cargar_target_pool(match_id):
    """
    Recupera el resultado real del target desde el pool de backtest.

    Se usa únicamente para evaluación retrospectiva.
    No participa en el cálculo de lambda ni en las probabilidades.
    """
    ruta = Path("data/backtest_pool.json")

    if not ruta.exists():
        return None

    try:
        datos = json.loads(
            ruta.read_text(encoding="utf-8")
        )
    except Exception:
        return None

    if isinstance(datos, list):
        partidos = datos
    elif isinstance(datos, dict):
        partidos = (
            datos.get("partidos")
            or datos.get("matches")
            or datos.get("pool")
            or datos.get("seleccionados")
            or []
        )
    else:
        return None

    for partido in partidos:
        mid = (
            partido.get("match_id")
            or partido.get("id")
        )

        if mid != match_id:
            continue

        gl = partido.get("goles_local")
        gv = partido.get("goles_visitante")

        if gl is None or gv is None:
            return None

        try:
            gl = int(gl)
            gv = int(gv)
        except (TypeError, ValueError):
            return None

        total = gl + gv

        if gl > gv:
            resultado_1x2 = "1"
        elif gl < gv:
            resultado_1x2 = "2"
        else:
            resultado_1x2 = "X"

        return {
            "match_id": match_id,
            "fecha": partido.get("fecha"),
            "local": partido.get("local"),
            "visitante": partido.get("visitante"),
            "goles_local": gl,
            "goles_visitante": gv,
            "total_goles": total,
            "btts": gl > 0 and gv > 0,
            "resultado_1x2": resultado_1x2,
            "targets_goles": {
                "+1.5": total >= 2,
                "+2.5": total >= 3,
                "+3.5": total >= 4,
                "+4.5": total >= 5,
            },
            "copias_encontradas": 1,
            "fuente_resultado": "backtest_pool.json",
        }

    return None


def probabilidades(lambdas):
    r = analizar(
        lambdas["local"],
        lambdas["visitante"],
    )

    goles = r["goles"]

    return {
        "+1.5": goles["2_mas"],
        "+2.5": goles["3_mas"],
        "+3.5": goles["4_mas"],
        "+4.5": r["over_4_0"]["gana"],
        "btts": r["btts"]["si"],
        "1": r["resultado"]["victoria_local"],
        "X": r["resultado"]["empate"],
        "2": r["resultado"]["victoria_visitante"],
    }


def main():
    args = argumentos()
    carpeta = BASE / args.match_id

    ruta_lambda = (
        carpeta / "lambda_comparison.json"
    )

    if not ruta_lambda.exists():
        raise FileNotFoundError(
            f"No existe {ruta_lambda}"
        )

    with ruta_lambda.open(
        encoding="utf-8"
    ) as f:
        comparacion = json.load(f)

    target = cargar_target(carpeta)

    if target is None:
        target = cargar_target_pool(
            args.match_id
        )

        if target is not None:
            print(
                ">>> Resultado real recuperado "
                "desde backtest_pool.json"
            )

    if target is None:
        raise RuntimeError(
            "No se encontró resultado real "
            "para el partido objetivo."
        )

    metodos_disponibles = comparacion[
        "metodos"
    ]

    evaluaciones = {}

    for etiqueta, clave in METODOS.items():
        if clave not in metodos_disponibles:
            continue

        lambdas = metodos_disponibles[clave]
        probs = probabilidades(lambdas)

        errores_goles = {}

        for linea in (
            "+1.5",
            "+2.5",
            "+3.5",
            "+4.5",
        ):
            ocurrido = target[
                "targets_goles"
            ][linea]

            errores_goles[linea] = {
                "probabilidad": round(
                    probs[linea],
                    6,
                ),
                "ocurrio": ocurrido,
                "brier": round(
                    brier(
                        probs[linea],
                        ocurrido,
                    ),
                    6,
                ),
            }

        errores_btts = {
            "probabilidad": round(
                probs["btts"],
                6,
            ),
            "ocurrio": target["btts"],
            "brier": round(
                brier(
                    probs["btts"],
                    target["btts"],
                ),
                6,
            ),
        }

        real_1x2 = target[
            "resultado_1x2"
        ]

        brier_1x2 = sum(
            (
                probs[resultado]
                - (
                    1.0
                    if resultado == real_1x2
                    else 0.0
                )
            ) ** 2
            for resultado in ("1", "X", "2")
        )

        evaluaciones[etiqueta] = {
            "metodo": clave,
            "lambda": lambdas,
            "probabilidades": {
                k: round(v, 6)
                for k, v in probs.items()
            },
            "brier_goles": errores_goles,
            "brier_btts": errores_btts,
            "brier_1x2": round(
                brier_1x2,
                6,
            ),
        }

    salida = {
        "match_id": args.match_id,
        "target": target,
        "modelos": evaluaciones,
        "nota": (
            "Evaluación retrospectiva. "
            "El target real se usa únicamente "
            "después de generar las probabilidades."
        ),
    }

    ruta_salida = (
        carpeta / "backtest.json"
    )

    with ruta_salida.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            salida,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("=" * 72)
    print("BACKTEST:", args.match_id)
    print(
        target["local"],
        target["goles_local"],
        "-",
        target["goles_visitante"],
        target["visitante"],
    )
    print("=" * 72)

    for nombre, datos in evaluaciones.items():
        print()
        print(nombre)

        for linea in (
            "+1.5",
            "+2.5",
            "+3.5",
            "+4.5",
        ):
            d = datos[
                "brier_goles"
            ][linea]

            print(
                f"  {linea}: "
                f"P={d['probabilidad']:.3f} "
                f"real={int(d['ocurrio'])} "
                f"Brier={d['brier']:.4f}"
            )

        d = datos["brier_btts"]

        print(
            f"  BTTS: "
            f"P={d['probabilidad']:.3f} "
            f"real={int(d['ocurrio'])} "
            f"Brier={d['brier']:.4f}"
        )

        print(
            "  Brier 1X2:",
            f"{datos['brier_1x2']:.4f}",
        )

    print()
    print("Guardado:", ruta_salida)


if __name__ == "__main__":
    main()
