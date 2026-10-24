import argparse
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path


ENTRADA = Path(
    "data/partidos.json"
)

SALIDA = Path(
    "data/partidos_candidatos.json"
)


ESTADOS_FINALIZADOS = {
    "finalizado",
    "finalizado pen.",
    "finalizado prórroga",
    "aplazado",
    "cancelado",
    "walkover",
}


def argumentos():
    parser = argparse.ArgumentParser(
        description=(
            "Selecciona partidos futuros "
            "para Match Goals AI."
        )
    )

    parser.add_argument(
        "--grace-minutes",
        type=int,
        default=0,
        help=(
            "Margen en minutos. "
            "0 = solamente partidos "
            "que aún no alcanzan su hora."
        ),
    )

    return parser.parse_args()


def normalizar(texto):
    if texto is None:
        return ""

    return (
        str(texto)
        .strip()
        .lower()
    )


def cargar():
    if not ENTRADA.exists():
        raise FileNotFoundError(
            f"No existe {ENTRADA}"
        )

    with ENTRADA.open(
        encoding="utf-8"
    ) as archivo:
        datos = json.load(
            archivo
        )

    if isinstance(datos, dict):
        return (
            datos,
            datos.get(
                "partidos",
                [],
            ),
        )

    if isinstance(datos, list):
        return (
            {},
            datos,
        )

    raise RuntimeError(
        "Formato desconocido "
        "en partidos.json"
    )


def clasificar_estado(partido):
    estado = normalizar(
        partido.get("estado")
    )

    hora = partido.get(
        "hora"
    )

    goles_local = partido.get(
        "gol_local"
    )

    goles_visitante = partido.get(
        "gol_visitante"
    )

    if estado in ESTADOS_FINALIZADOS:
        return "finalizado"

    if "finalizado" in estado:
        return "finalizado"

    if "cancelado" in estado:
        return "descartado"

    if "aplazado" in estado:
        return "descartado"

    if (
        goles_local is not None
        and goles_visitante is not None
        and not hora
    ):
        return "marcador_sin_hora"

    if hora:
        return "programado"

    return "desconocido"


def obtener_datetime_partido(
    partido,
):
    fecha = partido.get(
        "fecha"
    )

    hora = partido.get(
        "hora"
    )

    if not fecha or not hora:
        return None

    try:
        return datetime.strptime(
            f"{fecha} {hora}",
            "%Y-%m-%d %H:%M",
        )

    except ValueError:
        return None


def clasificar_tiempo(
    partido,
    ahora,
    grace_minutes,
):
    fecha_hora = (
        obtener_datetime_partido(
            partido
        )
    )

    if fecha_hora is None:
        return (
            "hora_invalida",
            None,
        )

    limite = (
        ahora
        - timedelta(
            minutes=grace_minutes
        )
    )

    if fecha_hora > limite:
        return (
            "futuro",
            fecha_hora,
        )

    return (
        "pasado_por_hora",
        fecha_hora,
    )


def main():
    args = argumentos()

    metadata, partidos = cargar()

    # Hora local del sistema WSL.
    ahora = datetime.now()

    candidatos = []

    contador_estado = Counter()
    contador_tiempo = Counter()
    descartes = Counter()

    for partido in partidos:
        categoria_estado = (
            clasificar_estado(
                partido
            )
        )

        contador_estado[
            categoria_estado
        ] += 1

        if categoria_estado != "programado":
            descartes[
                categoria_estado
            ] += 1
            continue

        categoria_tiempo, fecha_hora = (
            clasificar_tiempo(
                partido,
                ahora,
                args.grace_minutes,
            )
        )

        contador_tiempo[
            categoria_tiempo
        ] += 1

        if categoria_tiempo != "futuro":
            descartes[
                categoria_tiempo
            ] += 1
            continue

        registro = dict(
            partido
        )

        registro[
            "categoria_estado"
        ] = categoria_estado

        registro[
            "categoria_tiempo"
        ] = categoria_tiempo

        registro[
            "fecha_hora_local"
        ] = fecha_hora.strftime(
            "%Y-%m-%d %H:%M"
        )

        candidatos.append(
            registro
        )

    salida = {
        "generado_en": (
            ahora.isoformat(
                timespec="seconds"
            )
        ),
        "origen": str(
            ENTRADA
        ),
        "grace_minutes": (
            args.grace_minutes
        ),
        "total_origen": len(
            partidos
        ),
        "total_candidatos": len(
            candidatos
        ),
        "conteo_estado": dict(
            contador_estado
        ),
        "conteo_tiempo_programados": dict(
            contador_tiempo
        ),
        "descartes": dict(
            descartes
        ),
        "candidatos": candidatos,
    }

    SALIDA.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    SALIDA.write_text(
        json.dumps(
            salida,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 70)
    print("FILTRO TEMPORAL DE PARTIDOS")
    print("=" * 70)

    print(
        "Hora local del sistema:",
        ahora.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )

    print(
        f"Margen: "
        f"{args.grace_minutes} minutos"
    )

    print(
        f"Partidos originales: "
        f"{len(partidos)}"
    )

    print()

    print("ESTADO FLASHSCORE")

    for categoria, cantidad in sorted(
        contador_estado.items()
    ):
        print(
            f"{categoria:<24}"
            f"{cantidad}"
        )

    print()

    print(
        "TIEMPO DE LOS PROGRAMADOS"
    )

    for categoria, cantidad in sorted(
        contador_tiempo.items()
    ):
        print(
            f"{categoria:<24}"
            f"{cantidad}"
        )

    print()

    print(
        f"CANDIDATOS FUTUROS: "
        f"{len(candidatos)}"
    )

    print(
        f"Guardado en: "
        f"{SALIDA}"
    )

    print()

    por_fecha = Counter(
        p["fecha"]
        for p in candidatos
    )

    print("CANDIDATOS POR FECHA")

    for fecha, cantidad in sorted(
        por_fecha.items()
    ):
        print(
            f"{fecha}: "
            f"{cantidad}"
        )


if __name__ == "__main__":
    main()
