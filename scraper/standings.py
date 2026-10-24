import argparse
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

from scraper.match_selector import (
    buscar_por_id,
)


def leer_argumentos():
    parser = argparse.ArgumentParser(
        description=(
            "Extrae clasificación "
            "del partido."
        )
    )

    parser.add_argument(
        "--match-id",
        required=True,
        help="ID de Flashscore",
    )

    return parser.parse_args()


def limpiar_nombre(nombre):
    return re.sub(
        r"\s+\([^)]*\)$",
        "",
        nombre,
    ).strip()


def convertir_entero(texto):
    texto = texto.strip().replace(".", "")

    try:
        return int(texto)
    except ValueError:
        return None


def extraer_forma(fila):
    iconos = fila.locator(
        ".tableCellFormIcon"
    )

    forma = []

    for i in range(iconos.count()):
        texto = (
            iconos
            .nth(i)
            .inner_text()
            .strip()
        )

        if texto in {
            "G",
            "E",
            "P",
        }:
            forma.append(texto)

    return forma


def extraer_fila(fila):
    participante = fila.locator(
        ".tableCellParticipant__name"
    )

    if participante.count() == 0:
        return None

    equipo = (
        participante
        .first
        .inner_text()
        .strip()
    )

    rango = fila.locator(
        ".tableCellRank"
    )

    if rango.count() == 0:
        return None

    posicion = convertir_entero(
        rango.first.inner_text()
    )

    valores = fila.locator(
        ".table__cell--value"
    )

    if valores.count() < 7:
        return None

    textos = [
        valores
        .nth(i)
        .inner_text()
        .strip()
        for i in range(
            valores.count()
        )
    ]

    pj = convertir_entero(
        textos[0]
    )

    ganados = convertir_entero(
        textos[1]
    )

    empatados = convertir_entero(
        textos[2]
    )

    perdidos = convertir_entero(
        textos[3]
    )

    marcador_locator = fila.locator(
        ".table__cell--score"
    )

    if marcador_locator.count() == 0:
        return None

    marcador = (
        marcador_locator
        .first
        .inner_text()
        .strip()
    )

    if ":" not in marcador:
        return None

    gf_texto, gc_texto = (
        marcador.split(
            ":",
            maxsplit=1,
        )
    )

    gf = convertir_entero(
        gf_texto
    )

    gc = convertir_entero(
        gc_texto
    )

    dg_locator = fila.locator(
        ".table__cell--goalsForAgainstDiff"
    )

    puntos_locator = fila.locator(
        ".table__cell--points"
    )

    dg = None
    puntos = None

    if dg_locator.count():
        dg = convertir_entero(
            dg_locator
            .first
            .inner_text()
        )

    if puntos_locator.count():
        puntos = convertir_entero(
            puntos_locator
            .first
            .inner_text()
        )

    promedio_gf = None
    promedio_gc = None

    if (
        pj is not None
        and pj > 0
        and gf is not None
        and gc is not None
    ):
        promedio_gf = gf / pj
        promedio_gc = gc / pj

    return {
        "posicion": posicion,
        "equipo": equipo,
        "pj": pj,
        "ganados": ganados,
        "empatados": empatados,
        "perdidos": perdidos,
        "gf": gf,
        "gc": gc,
        "goles": marcador,
        "dg": dg,
        "puntos": puntos,
        "promedio_gf": promedio_gf,
        "promedio_gc": promedio_gc,
        "forma": extraer_forma(
            fila
        ),
    }


def extraer_tabla(tabla):
    filas = tabla.locator(
        ".ui-table__row"
    )

    resultado = []

    for i in range(filas.count()):
        try:
            datos = extraer_fila(
                filas.nth(i)
            )

            if datos:
                resultado.append(
                    datos
                )

        except Exception as error:
            print(
                f"Fila {i + 1}: "
                f"{error}"
            )

    return resultado


def buscar_equipo(
    clasificacion,
    nombre,
):
    objetivo = (
        limpiar_nombre(nombre)
        .lower()
    )

    for fila in clasificacion:
        equipo = (
            limpiar_nombre(
                fila["equipo"]
            )
            .lower()
        )

        if equipo == objetivo:
            return fila

    return None


def encontrar_tabla_relevante(
    page,
    local,
    visitante,
):
    tablas = page.locator(
        ".ui-table"
    )

    print(
        f"Tablas encontradas: "
        f"{tablas.count()}"
    )

    for i in range(tablas.count()):
        tabla = tablas.nth(i)

        clasificacion = (
            extraer_tabla(
                tabla
            )
        )

        if not clasificacion:
            continue

        local_encontrado = (
            buscar_equipo(
                clasificacion,
                local,
            )
        )

        visitante_encontrado = (
            buscar_equipo(
                clasificacion,
                visitante,
            )
        )

        if (
            local_encontrado
            and visitante_encontrado
        ):
            print(
                "Tabla relevante "
                f"encontrada: {i + 1}"
            )

            return clasificacion

    return []


def main():
    args = leer_argumentos()

    partido = buscar_por_id(
        args.match_id
    )

    directorio = (
        Path("data/matches")
        / partido["id"]
    )

    directorio.mkdir(
        parents=True,
        exist_ok=True,
    )

    archivo_salida = (
        directorio
        / "standings.json"
    )

    partido = {
        **partido,
        "local": limpiar_nombre(
            partido["local"]
        ),
        "visitante": limpiar_nombre(
            partido["visitante"]
        ),
    }

    print("=" * 70)
    print(
        "MATCH GOALS AI - "
        "CLASIFICACIÓN"
    )
    print("=" * 70)

    print(
        f"\n{partido['local']} "
        f"vs {partido['visitante']}"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1920,
                "height": 1080,
            },
            locale="es-MX",
        )

        print("\nAbriendo partido...")

        response = page.goto(
            partido["url"],
            wait_until="domcontentloaded",
            timeout=60_000,
        )

        if response:
            print(
                f"HTTP: {response.status}"
            )

        page.wait_for_timeout(
            5000
        )

        clasificacion = (
            encontrar_tabla_relevante(
                page,
                partido["local"],
                partido["visitante"],
            )
        )

        local = buscar_equipo(
            clasificacion,
            partido["local"],
        )

        visitante = buscar_equipo(
            clasificacion,
            partido["visitante"],
        )

        if (
            local is None
            or visitante is None
        ):
            print(
                "\nNo existe una "
                "clasificación común "
                "para ambos equipos."
            )

            print(
                "Puede tratarse de copa, "
                "eliminatoria, amistoso "
                "o competición sin tabla."
            )

            estado = (
                "sin_clasificacion_comun"
            )

        else:
            estado = "ok"

            print(
                f"\n{local['posicion']}°. "
                f"{local['equipo']} | "
                f"{local['goles']} | "
                f"{local['puntos']} pts"
            )

            print(
                f"{visitante['posicion']}°. "
                f"{visitante['equipo']} | "
                f"{visitante['goles']} | "
                f"{visitante['puntos']} pts"
            )

        salida = {
            "partido": {
                "local": (
                    partido["local"]
                ),
                "visitante": (
                    partido[
                        "visitante"
                    ]
                ),
                "id": partido.get("id"),
            },
            "estado": estado,
            "local": local,
            "visitante": visitante,
            "clasificacion": (
                clasificacion
            ),
        }

        archivo_salida.write_text(
            json.dumps(
                salida,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            f"\nGuardado en: "
            f"{archivo_salida}"
        )

        browser.close()


if __name__ == "__main__":
    main()
