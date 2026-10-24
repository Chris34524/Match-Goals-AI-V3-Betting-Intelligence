import json
from pathlib import Path


def extraer_target(history, match_id=None):
    principal = history.get("partido", {})

    objetivo = (
        match_id
        or principal.get("id")
        or history.get("match_id")
    )

    encontrados = []

    for seccion in history.get("secciones", []):
        for partido in seccion.get("partidos", []):
            if partido.get("match_id") != objetivo:
                continue

            if not partido.get("resultado_parseado"):
                continue

            gl = partido.get("goles_local")
            gv = partido.get("goles_visitante")

            if gl is None or gv is None:
                continue

            encontrados.append(
                {
                    "match_id": objetivo,
                    "fecha": partido.get("fecha"),
                    "local": partido.get("local"),
                    "visitante": partido.get("visitante"),
                    "goles_local": int(gl),
                    "goles_visitante": int(gv),
                }
            )

    if not encontrados:
        return None

    primero = encontrados[0]

    for otro in encontrados[1:]:
        campos = (
            "goles_local",
            "goles_visitante",
            "local",
            "visitante",
        )

        for campo in campos:
            if otro.get(campo) != primero.get(campo):
                raise ValueError(
                    "Copias inconsistentes del target "
                    f"{objetivo}: campo {campo}"
                )

    gl = primero["goles_local"]
    gv = primero["goles_visitante"]
    total = gl + gv

    primero["total_goles"] = total
    primero["btts"] = (
        gl > 0 and gv > 0
    )

    primero["resultado_1x2"] = (
        "1"
        if gl > gv
        else "2"
        if gv > gl
        else "X"
    )

    primero["targets_goles"] = {
        "+1.5": total >= 2,
        "+2.5": total >= 3,
        "+3.5": total >= 4,
        "+4.5": total >= 5,
    }

    primero["copias_encontradas"] = len(
        encontrados
    )

    return primero


def cargar_target(carpeta):
    carpeta = Path(carpeta)

    with (
        carpeta / "history.json"
    ).open(encoding="utf-8") as f:
        history = json.load(f)

    return extraer_target(history)
