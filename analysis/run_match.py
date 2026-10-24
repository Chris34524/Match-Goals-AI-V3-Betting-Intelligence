import argparse
import json
import subprocess
import sys
from pathlib import Path

from analysis.poisson import analizar
from analysis.temporal import filtrar_prepartido


BASE = Path("data/matches")


def argumentos():
    parser = argparse.ArgumentParser(
        description=(
            "Ejecuta el pipeline moderno "
            "de análisis para un partido."
        )
    )

    parser.add_argument(
        "--match-id",
        required=True,
    )

    parser.add_argument(
        "--skip-xg",
        action="store_true",
        help=(
            "No vuelve a ejecutar extract_xg; "
            "usa xg_history.json existente."
        ),
    )

    parser.add_argument(
        "--prepare",
        action="store_true",
        help=(
            "Prepara automáticamente history.json "
            "y standings.json si no existen."
        ),
    )

    parser.add_argument(
        "--refresh",
        action="store_true",
        help=(
            "Con --prepare, vuelve a extraer "
            "history y standings aunque existan."
        ),
    )

    return parser.parse_args()


def ejecutar(modulo, match_id, extra=None):
    comando = [
        sys.executable,
        "-m",
        modulo,
        "--match-id",
        match_id,
    ]

    if extra:
        comando.extend(extra)

    print()
    print("-" * 78)
    print("EJECUTANDO:", " ".join(comando))
    print("-" * 78)

    resultado = subprocess.run(
        comando,
        check=False,
    )

    if resultado.returncode != 0:
        raise RuntimeError(
            f"{modulo} terminó con "
            f"código {resultado.returncode}"
        )


def pct(valor):
    return round(
        valor * 100,
        2,
    )


def construir_resultado_poisson(
    nombre,
    lambdas,
):
    lambda_local = lambdas["local"]
    lambda_visitante = lambdas["visitante"]

    r = analizar(
        lambda_local,
        lambda_visitante,
    )

    goles = r["goles"]

    # Líneas .5:
    #
    # +1.5 = total >= 2 = 2+
    # +2.5 = total >= 3 = 3+
    # +3.5 = total >= 4 = 4+
    #
    # Para +0.5/+4.5 calculamos desde
    # probabilidades exactas del total.

    dist_total = r.get(
        "distribucion_total",
        {},
    )

    # Nuestro poisson.py actual ya ofrece
    # 2+, 3+ y 4+. Para 4.5 necesitamos
    # P(total >= 5), que equivale a la
    # probabilidad de ganar Over 4.0.
    over_4 = r["over_4_0"]

    mas_15 = goles["2_mas"]
    mas_25 = goles["3_mas"]
    mas_35 = goles["4_mas"]
    mas_45 = over_4["gana"]

    menos_15 = goles["menos_2"]
    menos_25 = goles["menos_3"]
    menos_35 = goles["menos_4"]

    # Under 4.5 = complemento de Over 4.5.
    menos_45 = 1.0 - mas_45

    salida = {
        "escenario": nombre,

        "lambda": {
            "local": lambda_local,
            "visitante": lambda_visitante,
            "total": (
                lambda_local
                + lambda_visitante
            ),
        },

        "resultado_1x2": {
            "1": pct(
                r["resultado"][
                    "victoria_local"
                ]
            ),
            "X": pct(
                r["resultado"]["empate"]
            ),
            "2": pct(
                r["resultado"][
                    "victoria_visitante"
                ]
            ),
        },

        "doble_oportunidad": {
            "1X": pct(
                r["doble_oportunidad"]["1X"]
            ),
            "X2": pct(
                r["doble_oportunidad"]["X2"]
            ),
            "12": pct(
                r["doble_oportunidad"]["12"]
            ),
        },

        "goles_medio": {
            "+1.5": pct(mas_15),
            "+2.5": pct(mas_25),
            "+3.5": pct(mas_35),
            "+4.5": pct(mas_45),

            "-1.5": pct(menos_15),
            "-2.5": pct(menos_25),
            "-3.5": pct(menos_35),
            "-4.5": pct(menos_45),
        },

        "btts": {
            "si": pct(r["btts"]["si"]),
            "no": pct(r["btts"]["no"]),
        },

        "asiaticas": {},
    }

    for linea in ("2_0", "3_0", "4_0"):
        etiqueta = linea.replace(
            "_",
            ".",
        )

        over = r[f"over_{linea}"]
        under = r[f"under_{linea}"]

        salida["asiaticas"][
            f"over_{etiqueta}"
        ] = {
            "gana": pct(over["gana"]),
            "push": pct(over["push"]),
            "pierde": pct(over["pierde"]),
        }

        salida["asiaticas"][
            f"under_{etiqueta}"
        ] = {
            "gana": pct(under["gana"]),
            "push": pct(under["push"]),
            "pierde": pct(under["pierde"]),
        }

    salida["marcadores_probables"] = (
        r.get(
            "marcadores_probables",
            [],
        )[:10]
    )

    return salida


def evaluar_calidad_datos(carpeta):
    def cargar(nombre):
        ruta = carpeta / nombre

        if not ruta.exists():
            return None

        with ruta.open(
            encoding="utf-8",
        ) as f:
            return json.load(f)

    history = cargar("history.json")
    xg = cargar("xg_history.json")
    standings = cargar("standings.json")
    h2h = cargar("h2h_analysis.json")

    calidad = {
        "forma": {},
        "xg": {},
        "h2h": {},
        "standings": {},
    }

    # -----------------------------------------
    # FORMA
    # -----------------------------------------

    if history:
        secciones = {
            s.get("tipo_estimado"): s
            for s in history.get(
                "secciones",
                [],
            )
        }

        for lado, tipo in (
            ("local", "equipo_local"),
            ("visitante", "equipo_visitante"),
        ):
            partidos = secciones.get(
                tipo,
                {},
            ).get(
                "partidos",
                [],
            )

            objetivo = (
                history.get("partido", {}).get("id")
                or history.get("match_id")
            )

            fecha_objetivo = (
                history.get("partido", {}).get("fecha")
            )

            validos, _ = filtrar_prepartido(
                partidos,
                objetivo,
                fecha_objetivo,
            )

            n = min(
                len(validos),
                20,
            )

            if n >= 20:
                nivel = "completa"
            elif n >= 10:
                nivel = "parcial"
            else:
                nivel = "debil"

            calidad["forma"][lado] = {
                "n": n,
                "objetivo": 20,
                "nivel": nivel,
            }

    # -----------------------------------------
    # xG
    # -----------------------------------------

    if xg:
        for lado in (
            "local",
            "visitante",
        ):
            bloque = (
                xg.get(lado, {})
                .get("l10", {})
            )

            disponibles = bloque.get(
                "partidos_con_xg",
                0,
            )

            considerados = bloque.get(
                "partidos_considerados",
                0,
            )

            cobertura = bloque.get(
                "cobertura_xg",
                0,
            )

            if cobertura >= 1.0:
                nivel = "completa"
            elif cobertura >= 0.8:
                nivel = "buena"
            elif cobertura >= 0.5:
                nivel = "parcial"
            else:
                nivel = "debil"

            calidad["xg"][lado] = {
                "con_xg": disponibles,
                "considerados": considerados,
                "objetivo": 10,
                "cobertura": cobertura,
                "nivel": nivel,
            }

    # -----------------------------------------
    # H2H
    # -----------------------------------------

    if h2h:
        n = (
            h2h.get(
                "h20",
                {},
            ).get(
                "n",
                0,
            )
        )

        if n >= 20:
            nivel = "completa"
        elif n >= 10:
            nivel = "buena"
        elif n >= 5:
            nivel = "parcial"
        else:
            nivel = "debil"

        calidad["h2h"] = {
            "n": n,
            "objetivo": 20,
            "nivel": nivel,
        }

    # -----------------------------------------
    # STANDINGS
    # -----------------------------------------

    if standings:
        estado = standings.get(
            "estado"
        )

        if estado == "ok":
            nivel = "disponible"
        elif estado == (
            "sin_clasificacion_comun"
        ):
            nivel = "no_disponible"
        else:
            nivel = "revisar"

        calidad["standings"] = {
            "estado": estado,
            "nivel": nivel,
        }

    return calidad



def evaluar_integridad_temporal(carpeta):
    ruta_history = carpeta / "history.json"

    if not ruta_history.exists():
        return {
            "estado": "ERROR",
            "motivo": "history.json no disponible",
        }

    with ruta_history.open(
        encoding="utf-8",
    ) as f:
        history = json.load(f)

    principal = history.get(
        "partido",
        {},
    )

    match_id_objetivo = (
        principal.get("id")
        or history.get("match_id")
    )

    fecha_objetivo = principal.get(
        "fecha"
    )

    salida = {
        "match_id_objetivo": match_id_objetivo,
        "fecha_objetivo": fecha_objetivo,
        "forma_local": None,
        "forma_visitante": None,
        "h2h": None,
        "xg_local": None,
        "xg_visitante": None,
        "estado": "OK",
    }

    secciones = {
        s.get("tipo_estimado"): s
        for s in history.get(
            "secciones",
            [],
        )
    }

    mapa = {
        "forma_local": "equipo_local",
        "forma_visitante": "equipo_visitante",
        "h2h": "h2h",
    }

    for nombre, tipo in mapa.items():
        partidos = (
            secciones.get(
                tipo,
                {},
            ).get(
                "partidos",
                [],
            )
        )

        _, control = filtrar_prepartido(
            partidos,
            match_id_objetivo,
            fecha_objetivo,
        )

        salida[nombre] = control

    ruta_xg = carpeta / "xg_history.json"

    if ruta_xg.exists():
        with ruta_xg.open(
            encoding="utf-8",
        ) as f:
            xg = json.load(f)

        for lado in ("local", "visitante"):
            partidos = (
                xg.get(
                    lado,
                    {},
                ).get(
                    "partidos",
                    [],
                )
            )

            _, control = filtrar_prepartido(
                partidos,
                match_id_objetivo,
                fecha_objetivo,
            )

            salida[f"xg_{lado}"] = control

    # Verificación sobre las muestras realmente
    # almacenadas en xg_history.json.
    for clave in (
        "xg_local",
        "xg_visitante",
    ):
        control = salida.get(clave)

        if control is None:
            salida["estado"] = "REVISAR"
            continue

        if (
            control.get(
                "objetivo_excluido",
                0,
            ) > 0
            or control.get(
                "mismo_dia_excluidos",
                0,
            ) > 0
            or control.get(
                "futuros_excluidos",
                0,
            ) > 0
            or control.get(
                "sin_fecha_excluidos",
                0,
            ) > 0
        ):
            salida["estado"] = "ERROR"

    return salida

def main():
    args = argumentos()

    carpeta = BASE / args.match_id

    history = carpeta / "history.json"
    standings = carpeta / "standings.json"
    xg = carpeta / "xg_history.json"
    lambda_json = (
        carpeta
        / "lambda_comparison.json"
    )
    salida_json = (
        carpeta
        / "result.json"
    )

    print("=" * 78)
    print("PIPELINE DE ANALISIS POR PARTIDO")
    print("=" * 78)
    print("Match ID:", args.match_id)

    # -------------------------------------------------
    # 0. Preparación de datos base
    # -------------------------------------------------

    if args.prepare:
        if args.refresh or not history.exists():
            ejecutar(
                "scraper.extract_history",
                args.match_id,
                [
                    "--target",
                    "21",
                ],
            )
        else:
            print()
            print(
                "Historial: reutilizando "
                "history.json existente"
            )

        if args.refresh or not standings.exists():
            ejecutar(
                "scraper.standings",
                args.match_id,
            )
        else:
            print(
                "Clasificación: reutilizando "
                "standings.json existente"
            )

    if not history.exists():
        raise FileNotFoundError(
            f"No existe {history}. "
            "Usa --prepare para extraerlo."
        )

    if not standings.exists():
        raise FileNotFoundError(
            f"No existe {standings}. "
            "Usa --prepare para extraerlo."
        )

    # -------------------------------------------------
    # 1. xG
    # -------------------------------------------------

    if args.skip_xg:
        if not xg.exists():
            raise FileNotFoundError(
                "--skip-xg fue indicado, "
                f"pero no existe {xg}"
            )

        print()
        print(
            "xG: reutilizando archivo existente"
        )

    else:
        ejecutar(
            "scraper.extract_xg",
            args.match_id,
            [
                "--target",
                "10",
            ],
        )

    # -------------------------------------------------
    # 2. Enriquecimiento anti-leak
    # -------------------------------------------------

    ejecutar(
        "analysis.enrich_match",
        args.match_id,
    )

    # -------------------------------------------------
    # 3. H2H
    # -------------------------------------------------

    ejecutar(
        "analysis.h2h",
        args.match_id,
    )

    # -------------------------------------------------
    # 4. Lambdas
    # -------------------------------------------------

    ejecutar(
        "analysis.compare_lambda",
        args.match_id,
    )

    if not lambda_json.exists():
        raise RuntimeError(
            "compare_lambda no generó "
            f"{lambda_json}"
        )

    with lambda_json.open(
        encoding="utf-8",
    ) as f:
        comparacion = json.load(f)

    metodos = comparacion["metodos"]

    escenarios_deseados = {
        "J_base": (
            "J_hibrido_experimental"
        ),
        "P_H2H10": (
            "P_base_H2H_10pct"
        ),
        "Q_H2H15": (
            "Q_base_H2H_15pct"
        ),
        "R_H2H20": (
            "R_base_H2H_20pct"
        ),
    }

    escenarios = {}

    for etiqueta, clave in (
        escenarios_deseados.items()
    ):
        if clave not in metodos:
            continue

        escenarios[etiqueta] = (
            construir_resultado_poisson(
                etiqueta,
                metodos[clave],
            )
        )

    if not escenarios:
        raise RuntimeError(
            "No se encontraron escenarios "
            "Poisson utilizables."
        )

    partido = comparacion.get(
        "partido",
        {},
    )

    salida = {
        "match_id": args.match_id,

        "partido": partido,

        "calidad_datos": (
            evaluar_calidad_datos(
                carpeta
            )
        ),

        "integridad_temporal": (
            evaluar_integridad_temporal(
                carpeta
            )
        ),

        "estado_modelo": (
            "experimental"
        ),

        "modelo": {
            "base": (
                "J_hibrido_experimental"
            ),
            "h2h": (
                "sensibilidad 10/15/20%"
            ),
            "seleccion_definitiva": None,
        },

        "escenarios": escenarios,

        "notas": [
            (
                "Las probabilidades proceden "
                "de Poisson a partir de los "
                "lambda estimados."
            ),
            (
                "Los pesos del modelo todavía "
                "requieren backtesting."
            ),
            (
                "No se selecciona todavía un "
                "peso H2H definitivo."
            ),
        ],
    }

    with salida_json.open(
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
    print("=" * 78)
    print("RESULTADO FINAL")
    print("=" * 78)

    print(
        partido.get("local"),
        "vs",
        partido.get("visitante"),
    )

    for nombre, resultado in (
        escenarios.items()
    ):
        print()
        print(nombre)

        l = resultado["lambda"]
        g = resultado["goles_medio"]
        rx = resultado["resultado_1x2"]
        b = resultado["btts"]

        print(
            "  lambda:",
            f"{l['local']:.3f}",
            "+",
            f"{l['visitante']:.3f}",
            "=",
            f"{l['total']:.3f}",
        )

        print(
            "  1/X/2:",
            f"{rx['1']:.2f}% /",
            f"{rx['X']:.2f}% /",
            f"{rx['2']:.2f}%",
        )

        print(
            "  +1.5:",
            f"{g['+1.5']:.2f}%",
            "| +2.5:",
            f"{g['+2.5']:.2f}%",
            "| +3.5:",
            f"{g['+3.5']:.2f}%",
            "| +4.5:",
            f"{g['+4.5']:.2f}%",
        )

        print(
            "  BTTS:",
            f"{b['si']:.2f}%",
        )

    print()
    print(
        "Guardado:",
        salida_json,
    )


if __name__ == "__main__":
    main()
