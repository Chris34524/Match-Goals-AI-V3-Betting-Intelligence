import argparse
import math


def poisson(
    goles,
    lamb,
):
    return (
        math.exp(-lamb)
        * (lamb ** goles)
        / math.factorial(goles)
    )


def matriz_marcadores(
    lambda_local,
    lambda_visitante,
    max_goles=12,
):
    matriz = []

    for goles_local in range(
        max_goles + 1
    ):
        fila = []

        p_local = poisson(
            goles_local,
            lambda_local,
        )

        for goles_visitante in range(
            max_goles + 1
        ):
            p_visitante = poisson(
                goles_visitante,
                lambda_visitante,
            )

            fila.append(
                p_local
                * p_visitante
            )

        matriz.append(fila)

    return matriz


def sumar_condicion(
    matriz,
    condicion,
):
    total = 0.0

    for goles_local, fila in enumerate(
        matriz
    ):
        for goles_visitante, p in enumerate(
            fila
        ):
            if condicion(
                goles_local,
                goles_visitante,
            ):
                total += p

    return total


def prob_total_exacto(
    matriz,
    goles,
):
    return sumar_condicion(
        matriz,
        lambda gl, gv:
        gl + gv == goles,
    )


def prob_total_menor(
    matriz,
    goles,
):
    return sumar_condicion(
        matriz,
        lambda gl, gv:
        gl + gv < goles,
    )


def prob_total_mayor(
    matriz,
    goles,
):
    return sumar_condicion(
        matriz,
        lambda gl, gv:
        gl + gv > goles,
    )


def linea_asiatica_over(
    matriz,
    linea,
):
    exacto = int(linea)

    return {
        "gana": prob_total_mayor(
            matriz,
            exacto,
        ),
        "push": prob_total_exacto(
            matriz,
            exacto,
        ),
        "pierde": prob_total_menor(
            matriz,
            exacto,
        ),
    }


def linea_asiatica_under(
    matriz,
    linea,
):
    exacto = int(linea)

    return {
        "gana": prob_total_menor(
            matriz,
            exacto,
        ),
        "push": prob_total_exacto(
            matriz,
            exacto,
        ),
        "pierde": prob_total_mayor(
            matriz,
            exacto,
        ),
    }


def analizar(
    lambda_local,
    lambda_visitante,
    max_goles=12,
):
    matriz = matriz_marcadores(
        lambda_local,
        lambda_visitante,
        max_goles,
    )

    masa = sum(
        sum(fila)
        for fila in matriz
    )

    victoria_local = sumar_condicion(
        matriz,
        lambda gl, gv:
        gl > gv,
    )

    empate = sumar_condicion(
        matriz,
        lambda gl, gv:
        gl == gv,
    )

    victoria_visitante = (
        sumar_condicion(
            matriz,
            lambda gl, gv:
            gl < gv,
        )
    )

    # ---------------------------------
    # Totales
    # ---------------------------------

    p_2_mas = sumar_condicion(
        matriz,
        lambda gl, gv:
        gl + gv >= 2,
    )

    p_3_mas = sumar_condicion(
        matriz,
        lambda gl, gv:
        gl + gv >= 3,
    )

    p_4_mas = sumar_condicion(
        matriz,
        lambda gl, gv:
        gl + gv >= 4,
    )

    p_menos_2 = sumar_condicion(
        matriz,
        lambda gl, gv:
        gl + gv < 2,
    )

    p_menos_3 = sumar_condicion(
        matriz,
        lambda gl, gv:
        gl + gv < 3,
    )

    p_menos_4 = sumar_condicion(
        matriz,
        lambda gl, gv:
        gl + gv < 4,
    )

    # ---------------------------------
    # BTTS
    # ---------------------------------

    btts_si = sumar_condicion(
        matriz,
        lambda gl, gv:
        gl >= 1 and gv >= 1,
    )

    btts_no = masa - btts_si

    # ---------------------------------
    # Marcadores
    # ---------------------------------

    marcadores = []

    for gl, fila in enumerate(
        matriz
    ):
        for gv, p in enumerate(
            fila
        ):
            marcadores.append(
                {
                    "marcador": (
                        f"{gl}-{gv}"
                    ),
                    "probabilidad": p,
                }
            )

    marcadores.sort(
        key=lambda x:
        x["probabilidad"],
        reverse=True,
    )

    return {
        "masa_matriz": masa,

        "resultado": {
            "victoria_local": (
                victoria_local
            ),
            "empate": empate,
            "victoria_visitante": (
                victoria_visitante
            ),
        },

        "doble_oportunidad": {
            "1X": (
                victoria_local
                + empate
            ),
            "X2": (
                empate
                + victoria_visitante
            ),
            "12": (
                victoria_local
                + victoria_visitante
            ),
        },

        "goles": {
            "2_mas": p_2_mas,
            "3_mas": p_3_mas,
            "4_mas": p_4_mas,

            "menos_2": p_menos_2,
            "menos_3": p_menos_3,
            "menos_4": p_menos_4,
        },

        "btts": {
            "si": btts_si,
            "no": btts_no,
        },

        "over_2_0": (
            linea_asiatica_over(
                matriz,
                2,
            )
        ),

        "over_3_0": (
            linea_asiatica_over(
                matriz,
                3,
            )
        ),

        "over_4_0": (
            linea_asiatica_over(
                matriz,
                4,
            )
        ),

        "under_2_0": (
            linea_asiatica_under(
                matriz,
                2,
            )
        ),

        "under_3_0": (
            linea_asiatica_under(
                matriz,
                3,
            )
        ),

        "under_4_0": (
            linea_asiatica_under(
                matriz,
                4,
            )
        ),

        "marcadores_probables": (
            marcadores[:10]
        ),
    }


def porcentaje(valor):
    return f"{valor:.2%}"


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--local",
        type=float,
        required=True,
        help="Lambda del equipo local",
    )

    parser.add_argument(
        "--visitante",
        type=float,
        required=True,
        help="Lambda del visitante",
    )

    args = parser.parse_args()

    r = analizar(
        args.local,
        args.visitante,
    )

    print("=" * 72)
    print("POISSON")
    print("=" * 72)

    print()
    print(
        "Lambda local     :",
        args.local,
    )

    print(
        "Lambda visitante :",
        args.visitante,
    )

    print(
        "Lambda total     :",
        round(
            args.local
            + args.visitante,
            3,
        ),
    )

    print(
        "Masa matriz      :",
        f"{r['masa_matriz']:.8f}",
    )

    print()
    print("RESULTADO")

    print(
        "Victoria local    :",
        porcentaje(
            r["resultado"][
                "victoria_local"
            ]
        ),
    )

    print(
        "Empate            :",
        porcentaje(
            r["resultado"][
                "empate"
            ]
        ),
    )

    print(
        "Victoria visitante:",
        porcentaje(
            r["resultado"][
                "victoria_visitante"
            ]
        ),
    )

    print()
    print("DOBLE OPORTUNIDAD")

    for clave in (
        "1X",
        "X2",
        "12",
    ):
        print(
            f"{clave:<3}:",
            porcentaje(
                r[
                    "doble_oportunidad"
                ][clave]
            ),
        )

    print()
    print("GOLES")

    print(
        "2+ :",
        porcentaje(
            r["goles"]["2_mas"]
        ),
    )

    print(
        "3+ :",
        porcentaje(
            r["goles"]["3_mas"]
        ),
    )

    print(
        "4+ :",
        porcentaje(
            r["goles"]["4_mas"]
        ),
    )

    print()

    print(
        "-2 :",
        porcentaje(
            r["goles"]["menos_2"]
        ),
    )

    print(
        "-3 :",
        porcentaje(
            r["goles"]["menos_3"]
        ),
    )

    print(
        "-4 :",
        porcentaje(
            r["goles"]["menos_4"]
        ),
    )

    print()
    print("BTTS")

    print(
        "Sí :",
        porcentaje(
            r["btts"]["si"]
        ),
    )

    print(
        "No :",
        porcentaje(
            r["btts"]["no"]
        ),
    )

    for nombre in (
        "over_2_0",
        "over_3_0",
        "over_4_0",
        "under_2_0",
        "under_3_0",
        "under_4_0",
    ):
        valores = r[nombre]

        print()
        print(
            nombre.upper()
        )

        print(
            " Gana  :",
            porcentaje(
                valores["gana"]
            ),
        )

        print(
            " Push  :",
            porcentaje(
                valores["push"]
            ),
        )

        print(
            " Pierde:",
            porcentaje(
                valores["pierde"]
            ),
        )

    print()
    print("MARCADORES MÁS PROBABLES")

    for item in (
        r["marcadores_probables"]
    ):
        print(
            f"{item['marcador']:>5}",
            porcentaje(
                item["probabilidad"]
            ),
        )


if __name__ == "__main__":
    main()
