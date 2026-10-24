import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


CANDIDATOS = Path("data/partidos_candidatos.json")
SALIDA = Path("data/manual_selected.json")
ERRORES = Path("data/manual_errors.txt")
LOGS = Path("data/manual_logs")


def cargar(ruta):
    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def obtener_lista(datos):
    if isinstance(datos, list):
        return datos

    return (
        datos.get("candidatos")
        or datos.get("partidos")
        or []
    )


def obtener_id(p):
    return (
        p.get("match_id")
        or p.get("id")
        or p.get("flashscore_id")
    )


def parsear_fecha_hora(p):
    valor = p.get("fecha_hora_local")

    if valor:
        texto = str(valor).strip()

        try:
            return datetime.fromisoformat(
                texto.replace("Z", "+00:00")
            )
        except ValueError:
            pass

    fecha = p.get("fecha")
    hora = p.get("hora")

    if fecha and hora:
        for formato in (
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                return datetime.strptime(
                    f"{fecha} {hora}",
                    formato,
                )
            except ValueError:
                continue

    return None


def minutos_hasta(dt):
    if dt is None:
        return None

    if dt.tzinfo is not None:
        ahora = datetime.now(dt.tzinfo)
    else:
        ahora = datetime.now()

    return (
        dt - ahora
    ).total_seconds() / 60


def seleccionar_ventana(partidos, horas):
    salida = []
    vistos = set()

    for p in partidos:
        mid = obtener_id(p)

        if not mid or mid in vistos:
            continue

        vistos.add(mid)

        dt = parsear_fecha_hora(p)
        minutos = minutos_hasta(dt)

        if minutos is None:
            continue

        if minutos < 0:
            continue

        if minutos > horas * 60:
            continue

        q = dict(p)
        q["match_id"] = mid
        q["minutos_hasta_inicio"] = round(
            minutos,
            1,
        )

        salida.append(q)

    salida.sort(
        key=lambda x: x[
            "minutos_hasta_inicio"
        ]
    )

    return salida


def mostrar(partidos, horas):
    print()
    print("=" * 110)
    print(
        f"PARTIDOS EN LAS PRÓXIMAS "
        f"{horas:g} HORAS"
    )
    print("=" * 110)

    print(
        f"{'#':>3} "
        f"{'MIN':>6} "
        f"{'HORA':<7} "
        f"{'PAÍS':<16} "
        f"{'COMPETICIÓN':<28} "
        f"PARTIDO"
    )

    print("-" * 110)

    for i, p in enumerate(
        partidos,
        start=1,
    ):
        local = p.get("local") or "?"
        visitante = p.get("visitante") or "?"

        pais = str(
            p.get("pais") or "-"
        )[:16]

        competicion = str(
            p.get("competicion") or "-"
        )[:28]

        hora = str(
            p.get("hora") or "-"
        )

        minutos = round(
            p["minutos_hasta_inicio"]
        )

        print(
            f"{i:>3} "
            f"{minutos:>6} "
            f"{hora:<7} "
            f"{pais:<16} "
            f"{competicion:<28} "
            f"{local} - {visitante}"
        )

    print("=" * 110)
    print(
        "Puedes elegir: 3  |  3,7,12  |  3-8  |  q para salir"
    )
    print()


def interpretar(texto, total):
    texto = texto.strip().lower()

    if texto in ("q", "quit", "salir"):
        return []

    numeros = set()

    for bloque in texto.split(","):
        bloque = bloque.strip()

        if not bloque:
            continue

        if "-" in bloque:
            partes = bloque.split("-", 1)

            try:
                inicio = int(partes[0])
                fin = int(partes[1])
            except ValueError:
                raise ValueError(
                    f"Selección inválida: {bloque}"
                )

            if inicio > fin:
                inicio, fin = fin, inicio

            for n in range(
                inicio,
                fin + 1,
            ):
                numeros.add(n)

        else:
            try:
                numeros.add(int(bloque))
            except ValueError:
                raise ValueError(
                    f"Selección inválida: {bloque}"
                )

    fuera = [
        n
        for n in numeros
        if n < 1 or n > total
    ]

    if fuera:
        raise ValueError(
            "Fuera de rango: "
            + ", ".join(map(str, fuera))
        )

    return sorted(numeros)


def guardar_seleccion(partidos):
    datos = {
        "generado": datetime.now().isoformat(
            timespec="seconds"
        ),
        "numero_partidos": len(partidos),
        "partidos": partidos,
    }

    SALIDA.write_text(
        json.dumps(
            datos,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def analizar(partidos, pausa):
    LOGS.mkdir(
        parents=True,
        exist_ok=True,
    )

    errores = []

    print()
    print("=" * 80)
    print("ANÁLISIS DE PARTIDOS SELECCIONADOS")
    print("=" * 80)

    for i, p in enumerate(
        partidos,
        start=1,
    ):
        mid = p["match_id"]

        nombre = (
            f"{p.get('local')} - "
            f"{p.get('visitante')}"
        )

        print()
        print(
            f"[{i}/{len(partidos)}] "
            f"{nombre}"
        )
        print(
            f"ID: {mid}"
        )

        log_path = LOGS / f"{mid}.log"

        comando = [
            sys.executable,
            "-u",
            "-m",
            "analysis.run_match",
            "--match-id",
            mid,
            "--prepare",
        ]

        with log_path.open(
            "w",
            encoding="utf-8",
        ) as log:

            proceso = subprocess.Popen(
                comando,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            try:
                for linea in proceso.stdout:
                    print(
                        linea,
                        end="",
                        flush=True,
                    )

                    log.write(linea)
                    log.flush()

                codigo = proceso.wait()

            except KeyboardInterrupt:
                proceso.terminate()

                print()
                print(
                    "Proceso detenido por el usuario."
                )
                print(
                    "Los análisis ya terminados "
                    "permanecen guardados."
                )
                return

        if codigo == 0:
            print(
                f">>> OK: {mid}"
            )
        else:
            errores.append(mid)

            print(
                f">>> ERROR: {mid}"
            )
            print(
                f">>> LOG: {log_path}"
            )

        if (
            i < len(partidos)
            and pausa > 0
        ):
            time.sleep(pausa)

    ERRORES.write_text(
        "".join(
            f"{mid}\n"
            for mid in errores
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 80)
    print("FINALIZADO")
    print("=" * 80)
    print(
        "Seleccionados:",
        len(partidos),
    )
    print(
        "Errores:",
        len(errores),
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Muestra los partidos de una ventana "
            "horaria y permite elegir manualmente "
            "cuáles analizar."
        )
    )

    parser.add_argument(
        "--hours",
        type=float,
        default=4,
        help="Próximas N horas.",
    )

    parser.add_argument(
        "--pause",
        type=float,
        default=5,
        help=(
            "Pausa entre partidos seleccionados."
        ),
    )

    args = parser.parse_args()

    if args.hours <= 0:
        parser.error(
            "--hours debe ser mayor que 0"
        )

    if not CANDIDATOS.exists():
        raise SystemExit(
            "No existe "
            "data/partidos_candidatos.json\n"
            "Ejecuta primero:\n"
            "python -m scraper.filter_matches "
            "--grace-minutes 0"
        )

    datos = cargar(CANDIDATOS)
    partidos = obtener_lista(datos)

    ventana = seleccionar_ventana(
        partidos,
        args.hours,
    )

    if not ventana:
        print(
            "No hay partidos futuros dentro "
            "de esa ventana."
        )
        return

    mostrar(
        ventana,
        args.hours,
    )

    while True:
        texto = input(
            "Selecciona partido(s): "
        )

        try:
            indices = interpretar(
                texto,
                len(ventana),
            )
            break

        except ValueError as exc:
            print(
                "ERROR:",
                exc,
            )

    if not indices:
        print(
            "Sin selección. No se analiza nada."
        )
        return

    seleccionados = [
        ventana[i - 1]
        for i in indices
    ]

    print()
    print("SELECCIONADOS:")

    for i, p in enumerate(
        seleccionados,
        start=1,
    ):
        print(
            f"{i}. "
            f"{p.get('local')} - "
            f"{p.get('visitante')} "
            f"[{p['match_id']}]"
        )

    guardar_seleccion(
        seleccionados
    )

    confirmar = input(
        "\n¿Analizar ahora? [S/n]: "
    ).strip().lower()

    if confirmar in (
        "",
        "s",
        "si",
        "sí",
        "y",
        "yes",
    ):
        analizar(
            seleccionados,
            args.pause,
        )
    else:
        print()
        print(
            "Selección guardada en:",
            SALIDA,
        )


if __name__ == "__main__":
    main()
