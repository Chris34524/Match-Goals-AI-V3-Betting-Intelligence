import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

from analysis.poisson import analizar
from analysis.rank_day import calidad, pct
import analysis.report_day as report_day


BASE = Path("data/matches")
SALIDA_DATOS = Path("data/all_predictions.json")
SALIDA_HTML = Path("data/reporte_todo_analizado.html")


def argumentos():
    p = argparse.ArgumentParser(
        description=(
            "Genera un reporte acumulado de todos "
            "los partidos ya analizados."
        )
    )

    p.add_argument(
        "--date",
        default=datetime.now().strftime(
            "%Y-%m-%d"
        ),
        help=(
            "Fecha YYYY-MM-DD. "
            "Por defecto usa hoy."
        ),
    )

    p.add_argument(
        "--all-dates",
        action="store_true",
        help=(
            "Incluye todas las fechas existentes "
            "en data/matches."
        ),
    )

    p.add_argument(
        "--open",
        action="store_true",
        help="Abre el HTML al terminar.",
    )

    return p.parse_args()


def cargar(ruta):
    try:
        with ruta.open(
            encoding="utf-8"
        ) as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    args = argumentos()

    filas = []
    errores = []

    for carpeta in sorted(BASE.iterdir()):
        if not carpeta.is_dir():
            continue

        mid = carpeta.name

        ruta_lambda = (
            carpeta
            / "lambda_comparison.json"
        )

        if not ruta_lambda.exists():
            continue

        comp = cargar(ruta_lambda)

        partido = comp.get(
            "partido",
            {},
        )

        fecha = partido.get("fecha")

        if (
            not args.all_dates
            and fecha != args.date
        ):
            continue

        metodo = (
            comp.get(
                "metodos",
                {},
            ).get(
                "J_BT_sin_temporada"
            )
        )

        if not metodo:
            errores.append(
                {
                    "match_id": mid,
                    "motivo": "sin_modelo_base",
                }
            )
            continue

        ruta_result = (
            carpeta / "result.json"
        )

        result = (
            cargar(ruta_result)
            if ruta_result.exists()
            else {}
        )

        try:
            r = analizar(
                metodo["local"],
                metodo["visitante"],
            )
        except Exception as exc:
            errores.append(
                {
                    "match_id": mid,
                    "motivo": (
                        f"poisson_error: {exc}"
                    ),
                }
            )
            continue

        fila = {
            "match_id": mid,

            "fecha": fecha,
            "hora": partido.get("hora"),
            "pais": partido.get("pais"),
            "competicion": (
                partido.get("competicion")
            ),

            "local": partido.get("local"),
            "visitante": (
                partido.get("visitante")
            ),

            "lambda_local": round(
                metodo["local"],
                3,
            ),

            "lambda_visitante": round(
                metodo["visitante"],
                3,
            ),

            "lambda_total": round(
                metodo["total"],
                3,
            ),

            "+1.5": pct(
                r["goles"]["2_mas"]
            ),

            "+2.5": pct(
                r["goles"]["3_mas"]
            ),

            "+3.5": pct(
                r["goles"]["4_mas"]
            ),

            "+4.5": pct(
                r["over_4_0"]["gana"]
            ),

            "btts": pct(
                r["btts"]["si"]
            ),

            "victoria_local": pct(
                r["resultado"][
                    "victoria_local"
                ]
            ),

            "empate": pct(
                r["resultado"]["empate"]
            ),

            "victoria_visitante": pct(
                r["resultado"][
                    "victoria_visitante"
                ]
            ),

            "1X": pct(
                r["doble_oportunidad"]["1X"]
            ),

            "X2": pct(
                r["doble_oportunidad"]["X2"]
            ),

            "12": pct(
                r["doble_oportunidad"]["12"]
            ),

            "calidad": calidad(result),
        }

        filas.append(fila)

    # Orden cronológico.
    filas.sort(
        key=lambda x: (
            str(x.get("fecha") or ""),
            str(x.get("hora") or "99:99"),
            str(x.get("competicion") or ""),
        )
    )

    salida = {
        "fecha": (
            "TODAS"
            if args.all_dates
            else args.date
        ),
        "numero_partidos": len(filas),
        "modelo_principal": (
            "J_BT_sin_temporada"
        ),
        "partidos": filas,
        "errores": errores,
    }

    with SALIDA_DATOS.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            salida,
            f,
            ensure_ascii=False,
            indent=2,
        )

    # Reutilizamos exactamente el mismo
    # generador HTML detallado que ya tienes.
    report_day.DAY = SALIDA_DATOS
    report_day.SALIDA = SALIDA_HTML

    report_day.main()

    print()
    print("=" * 78)
    print("REPORTE ACUMULADO")
    print("=" * 78)

    print(
        "Fecha:",
        salida["fecha"],
    )

    print(
        "Partidos analizados:",
        len(filas),
    )

    print(
        "Con error/revisión:",
        len(errores),
    )

    print()
    print(
        "HTML:",
        SALIDA_HTML,
    )

    if args.open:
        try:
            ruta_windows = (
                subprocess.check_output(
                    [
                        "wslpath",
                        "-w",
                        str(
                            SALIDA_HTML.resolve()
                        ),
                    ],
                    text=True,
                )
                .strip()
            )

            subprocess.run(
                [
                    "explorer.exe",
                    ruta_windows,
                ],
                check=False,
            )

        except Exception as exc:
            print(
                "No se pudo abrir:",
                exc,
            )


if __name__ == "__main__":
    main()
