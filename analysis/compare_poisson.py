import argparse

from analysis.poisson import analizar


def pct(valor):
    return f"{valor * 100:6.2f}%"


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--local",
        required=True,
    )

    parser.add_argument(
        "--visitante",
        required=True,
    )

    parser.add_argument(
        "--escenario",
        action="append",
        nargs=3,
        metavar=(
            "NOMBRE",
            "LAMBDA_LOCAL",
            "LAMBDA_VISITANTE",
        ),
        required=True,
    )

    args = parser.parse_args()

    resultados = []

    for (
        nombre,
        lambda_local,
        lambda_visitante,
    ) in args.escenario:

        ll = float(lambda_local)
        lv = float(lambda_visitante)

        r = analizar(
            ll,
            lv,
        )

        resultados.append(
            (
                nombre,
                ll,
                lv,
                r,
            )
        )

    print("=" * 105)
    print("SENSIBILIDAD POISSON")
    print("=" * 105)

    print(
        args.local,
        "vs",
        args.visitante,
    )

    print()

    encabezado = (
        f"{'ESCENARIO':<15}"
        f"{'λL':>7}"
        f"{'λV':>7}"
        f"{'TOTAL':>8}"
        f"{'1':>9}"
        f"{'X':>9}"
        f"{'2':>9}"
        f"{'2+':>9}"
        f"{'3+':>9}"
        f"{'4+':>9}"
        f"{'BTTS':>9}"
    )

    print(encabezado)
    print("-" * len(encabezado))

    for (
        nombre,
        ll,
        lv,
        r,
    ) in resultados:

        print(
            f"{nombre:<15}"
            f"{ll:>7.3f}"
            f"{lv:>7.3f}"
            f"{ll + lv:>8.3f}"
            f"{pct(r['resultado']['victoria_local']):>9}"
            f"{pct(r['resultado']['empate']):>9}"
            f"{pct(r['resultado']['victoria_visitante']):>9}"
            f"{pct(r['goles']['2_mas']):>9}"
            f"{pct(r['goles']['3_mas']):>9}"
            f"{pct(r['goles']['4_mas']):>9}"
            f"{pct(r['btts']['si']):>9}"
        )

    print()
    print("=" * 105)
    print("DOBLE OPORTUNIDAD")
    print("=" * 105)

    print(
        f"{'ESCENARIO':<15}"
        f"{'1X':>12}"
        f"{'X2':>12}"
        f"{'12':>12}"
    )

    print("-" * 51)

    for nombre, _, _, r in resultados:
        d = r["doble_oportunidad"]

        print(
            f"{nombre:<15}"
            f"{pct(d['1X']):>12}"
            f"{pct(d['X2']):>12}"
            f"{pct(d['12']):>12}"
        )

    print()
    print("=" * 105)
    print("MENOS DE N GOLES")
    print("=" * 105)

    print(
        f"{'ESCENARIO':<15}"
        f"{'-2':>12}"
        f"{'-3':>12}"
        f"{'-4':>12}"
    )

    print("-" * 51)

    for nombre, _, _, r in resultados:
        g = r["goles"]

        print(
            f"{nombre:<15}"
            f"{pct(g['menos_2']):>12}"
            f"{pct(g['menos_3']):>12}"
            f"{pct(g['menos_4']):>12}"
        )

    print()
    print("=" * 105)
    print("LINEAS ASIATICAS")
    print("=" * 105)

    for nombre, _, _, r in resultados:

        print()
        print(nombre)

        for linea in (
            "2.0",
            "3.0",
            "4.0",
        ):
            clave_linea = linea.replace(
                ".",
                "_",
            )

            over = r[
                f"over_{clave_linea}"
            ]

            under = r[
                f"under_{clave_linea}"
            ]

            print(
                f"  O{linea} "
                f"W {pct(over['gana'])} "
                f"P {pct(over['push'])} "
                f"L {pct(over['pierde'])}"
            )

            print(
                f"  U{linea} "
                f"W {pct(under['gana'])} "
                f"P {pct(under['push'])} "
                f"L {pct(under['pierde'])}"
            )


if __name__ == "__main__":
    main()
