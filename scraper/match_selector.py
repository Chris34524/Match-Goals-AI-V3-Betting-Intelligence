import json
from pathlib import Path


ARCHIVO_PARTIDOS = Path(
    "data/partidos.json"
)

ARCHIVO_BACKTEST = Path(
    "data/backtest_pool.json"
)


def cargar_json(path):
    if not path.exists():
        return None

    with path.open(
        encoding="utf-8"
    ) as archivo:
        return json.load(archivo)


def cargar_partidos():
    datos = cargar_json(
        ARCHIVO_PARTIDOS
    )

    if datos is None:
        return []

    if isinstance(datos, list):
        return datos

    if isinstance(datos, dict):
        return datos.get(
            "partidos",
            [],
        )

    return []


def cargar_backtest():
    datos = cargar_json(
        ARCHIVO_BACKTEST
    )

    if not isinstance(datos, dict):
        return []

    return datos.get(
        "partidos",
        [],
    )


def obtener_id(partido):
    return str(
        partido.get("id")
        or partido.get("match_id")
        or partido.get("flashscore_id")
        or ""
    )


def normalizar_partido(partido):
    p = dict(partido)

    mid = obtener_id(p)

    if mid:
        p["id"] = mid
        p["match_id"] = mid

    return p


def buscar_por_id(match_id):
    match_id = str(match_id)

    # 1. Jornada actual / futura
    for partido in cargar_partidos():
        if obtener_id(partido) == match_id:
            return normalizar_partido(
                partido
            )

    # 2. Pool histórico de backtest
    for partido in cargar_backtest():
        if obtener_id(partido) == match_id:
            p = normalizar_partido(
                partido
            )

            if not p.get("url"):
                raise RuntimeError(
                    "Target histórico encontrado, "
                    "pero no tiene URL: "
                    f"{match_id}"
                )

            return p

    raise RuntimeError(
        "No encontramos partido "
        f"con ID {match_id} ni en "
        "partidos.json ni en "
        "backtest_pool.json"
    )


def buscar_por_equipos(
    local,
    visitante,
):
    local = local.lower().strip()
    visitante = visitante.lower().strip()

    candidatos = (
        cargar_partidos()
        + cargar_backtest()
    )

    for partido in candidatos:
        nombre_local = str(
            partido.get("local")
            or ""
        ).lower().strip()

        nombre_visitante = str(
            partido.get("visitante")
            or ""
        ).lower().strip()

        if (
            local in nombre_local
            and visitante in nombre_visitante
        ):
            return normalizar_partido(
                partido
            )

    raise RuntimeError(
        "No encontramos "
        f"{local} vs {visitante}"
    )
