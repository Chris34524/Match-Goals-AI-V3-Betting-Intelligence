import argparse
import json
from pathlib import Path

from analysis.confidence import clasificar


BASE = Path("data/matches")


def mapear_calidad(nivel):
    return {
        "FUERTE": "ALTA",
        "MEDIA": "MEDIA",
        "DEBIL": "BAJA",
    }.get(nivel, "BAJA")


def clasificar_v2(match_id):
    v1 = clasificar(match_id)

    nivel_global = v1.get(
        "nivel",
        "DEBIL",
    )

    mercados_v1 = v1.get(
        "mercados",
        {},
    )

    # --------------------------------------------------
    # BTTS
    # Único mercado donde la categoría FUERTE mostró
    # separación favorable global y mantuvo la dirección
    # en validación temporal.
    # --------------------------------------------------

    btts = mercados_v1.get(
        "BTTS",
        "DEBIL",
    )

    # --------------------------------------------------
    # GOLES
    # No llamamos "confianza predictiva" a V1.
    # Conservamos únicamente calidad de los datos.
    # --------------------------------------------------

    calidad_goles = mapear_calidad(
        mercados_v1.get(
            "goles",
            nivel_global,
        )
    )

    salida = {
        "version": "confidence_v2",
        "match_id": match_id,

        "modelo": "J_BT_sin_temporada",

        "calidad_datos_global": (
            mapear_calidad(
                nivel_global
            )
        ),

        "mercados": {
            "+1.5": {
                "calidad_datos": calidad_goles,
                "confianza_predictiva": (
                    "NO_VALIDADA"
                ),
            },

            "+2.5": {
                "calidad_datos": calidad_goles,
                "confianza_predictiva": (
                    "NO_VALIDADA"
                ),
            },

            "+3.5": {
                "calidad_datos": calidad_goles,
                "confianza_predictiva": (
                    "NO_VALIDADA"
                ),
                "nota": (
                    "La ventaja de V1 no "
                    "sobrevivió validación temporal."
                ),
            },

            "+4.5": {
                "calidad_datos": calidad_goles,
                "confianza_predictiva": (
                    "NO_VALIDADA"
                ),
            },

            "BTTS": {
                "calidad_datos": (
                    mapear_calidad(btts)
                ),
                "confianza_predictiva": btts,
                "validacion": (
                    "V2_BACKTEST_485"
                ),
            },

            "1X2": {
                "calidad_datos": (
                    mapear_calidad(
                        mercados_v1.get(
                            "1X2",
                            "DEBIL",
                        )
                    )
                ),
                "confianza_predictiva": (
                    "NO_VALIDADA"
                ),
            },
        },

        "evidencia": {
            "BTTS": {
                "n_total": 485,
                "n_fuerte": 178,
                "brier_fuerte": 0.24480,
                "brier_resto": 0.26485,
                "delta": -0.02005,
                "ic95": [
                    -0.03976,
                    -0.00049,
                ],
                "test_temporal_delta": (
                    -0.03352
                ),
                "test_temporal_n_fuerte": 52,
                "interpretacion": (
                    "Ventaja favorable y "
                    "direccionalmente estable. "
                    "El TEST temporal individual "
                    "aún tiene incertidumbre."
                ),
            },

            "+3.5": {
                "estado": "NO_VALIDADA",
                "motivo": (
                    "Delta favorable en TRAIN "
                    "pero desfavorable en TEST."
                ),
            },
        },

        "detalle_v1": v1,
    }

    ruta = (
        BASE
        / match_id
        / "confidence_v2.json"
    )

    ruta.write_text(
        json.dumps(
            salida,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return salida


def ids_pool():
    p = Path(
        "data/backtest_pool.txt"
    )

    return [
        x.strip()
        for x in p.read_text(
            encoding="utf-8"
        ).splitlines()
        if x.strip()
    ]


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--match-id"
    )

    parser.add_argument(
        "--pool",
        action="store_true",
    )

    args = parser.parse_args()

    if args.match_id:
        d = clasificar_v2(
            args.match_id
        )

        print(
            json.dumps(
                d,
                ensure_ascii=False,
                indent=2,
            )
        )

        return

    if args.pool:
        conteo = {
            "FUERTE": 0,
            "MEDIA": 0,
            "DEBIL": 0,
        }

        procesados = 0

        for mid in ids_pool():
            try:
                d = clasificar_v2(
                    mid
                )
            except Exception as e:
                print(
                    "ERROR:",
                    mid,
                    repr(e),
                )
                continue

            nivel = (
                d["mercados"]
                ["BTTS"]
                ["confianza_predictiva"]
            )

            conteo[nivel] += 1
            procesados += 1

        print()
        print("=" * 72)
        print("CONFIDENCE V2")
        print("=" * 72)

        print(
            "Procesados:",
            procesados,
        )

        print()
        print("BTTS")

        for nivel in (
            "FUERTE",
            "MEDIA",
            "DEBIL",
        ):
            print(
                f"{nivel:8s}:",
                conteo[nivel],
            )

        return

    raise SystemExit(
        "Usa --match-id MID o --pool"
    )


if __name__ == "__main__":
    main()
