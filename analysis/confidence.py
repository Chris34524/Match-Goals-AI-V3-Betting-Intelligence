import argparse
import json
import re
from pathlib import Path

from analysis.temporal import filtrar_prepartido


BASE = Path("data/matches")


def cargar(path):
    if not path.exists():
        return None

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return None


def normalizar(nombre):
    nombre = str(nombre or "").strip()

    nombre = re.sub(
        r"\s+\([^)]*\)$",
        "",
        nombre,
    )

    return " ".join(
        nombre.split()
    ).casefold()


def buscar_seccion(
    history,
    tipo,
    equipo,
):
    secciones = history.get(
        "secciones",
        [],
    )

    # 1. Etiqueta normal
    for s in secciones:
        if s.get("tipo_estimado") == tipo:
            return s

    # 2. Fallback por título
    objetivo = normalizar(equipo)

    candidatos = []

    for s in secciones:
        if s.get("tipo_estimado") == "h2h":
            continue

        titulo = str(
            s.get("titulo") or ""
        )

        titulo = re.sub(
            r"^ÚLTIMOS PARTIDOS:\s*",
            "",
            titulo,
            flags=re.I,
        )

        if normalizar(titulo) == objetivo:
            candidatos.append(s)

    if len(candidatos) == 1:
        return candidatos[0]

    return None


def obtener_metodos(datos):
    if not isinstance(datos, dict):
        return {}

    for clave in (
        "metodos",
        "methods",
    ):
        if isinstance(
            datos.get(clave),
            dict,
        ):
            return datos[clave]

    return datos


def metodo(metodos, nombre):
    d = metodos.get(nombre)

    if not isinstance(d, dict):
        return None

    try:
        local = float(d.get("local"))
        visitante = float(
            d.get("visitante")
        )
    except (TypeError, ValueError):
        return None

    return {
        "local": local,
        "visitante": visitante,
        "total": local + visitante,
    }


def limitar_nivel(nivel, maximo):
    orden = {
        "DEBIL": 0,
        "MEDIA": 1,
        "FUERTE": 2,
    }

    if orden[nivel] <= orden[maximo]:
        return nivel

    return maximo


def clasificar(match_id):
    carpeta = BASE / match_id

    history = cargar(
        carpeta / "history.json"
    )

    lambdas = cargar(
        carpeta / "lambda_comparison.json"
    )

    if not history:
        return {
            "match_id": match_id,
            "nivel": "DEBIL",
            "score": 0,
            "alertas": [
                "Sin history.json usable"
            ],
        }

    partido = history.get(
        "partido",
        {},
    )

    local = partido.get("local")
    visitante = partido.get(
        "visitante"
    )

    competicion = str(
        partido.get("competicion")
        or ""
    )

    target_id = (
        partido.get("id")
        or match_id
    )

    fecha = partido.get("fecha")

    sec_local = buscar_seccion(
        history,
        "equipo_local",
        local,
    )

    sec_visitante = buscar_seccion(
        history,
        "equipo_visitante",
        visitante,
    )

    alertas = []
    razones = []

    validos_local = []
    validos_visitante = []

    control_local = {}
    control_visitante = {}

    if sec_local:
        (
            validos_local,
            control_local,
        ) = filtrar_prepartido(
            sec_local.get(
                "partidos",
                [],
            ),
            target_id,
            fecha,
        )
    else:
        alertas.append(
            "No se identificó historial local"
        )

    if sec_visitante:
        (
            validos_visitante,
            control_visitante,
        ) = filtrar_prepartido(
            sec_visitante.get(
                "partidos",
                [],
            ),
            target_id,
            fecha,
        )
    else:
        alertas.append(
            "No se identificó historial visitante"
        )

    n_form_local = min(
        len(validos_local),
        10,
    )

    n_form_visitante = min(
        len(validos_visitante),
        10,
    )

    local_norm = normalizar(local)
    visitante_norm = normalizar(
        visitante
    )

    n_casa = sum(
        normalizar(
            p.get("local")
        ) == local_norm
        for p in validos_local
    )

    n_fuera = sum(
        normalizar(
            p.get("visitante")
        ) == visitante_norm
        for p in validos_visitante
    )

    metodos = obtener_metodos(
        lambdas or {}
    )

    base = (
        metodo(
            metodos,
            "J_BT_sin_temporada",
        )
        or metodo(
            metodos,
            "J_hibrido_experimental",
        )
    )

    forma = metodo(
        metodos,
        "H_forma_goles_5_10_20",
    )

    casa = metodo(
        metodos,
        "F_casa_visitante",
    )

    xg = metodo(
        metodos,
        "I_forma_xG_5_10",
    )

    # ------------------------------------------------
    # SCORE V1
    # ------------------------------------------------

    score = 0

    # Forma reciente: 0-2 puntos
    if (
        n_form_local >= 10
        and n_form_visitante >= 10
    ):
        score += 2
        razones.append(
            "L10 completo en ambos equipos"
        )

    elif (
        n_form_local >= 5
        and n_form_visitante >= 5
    ):
        score += 1
        razones.append(
            "Forma reciente suficiente, "
            "pero L10 incompleto"
        )

    else:
        alertas.append(
            "Muestra de forma pequeña"
        )

    # Casa / visitante: 0-2 puntos
    if (
        n_casa >= 8
        and n_fuera >= 8
    ):
        score += 2
        razones.append(
            "Muestra casa/visitante >=8 "
            "en ambos"
        )

    elif (
        n_casa >= 5
        and n_fuera >= 5
    ):
        score += 1
        razones.append(
            "Muestra casa/visitante "
            "moderada"
        )

    else:
        alertas.append(
            "Muestra casa/visitante pequeña"
        )

    # xG: 0-2 puntos
    xg_disponible = xg is not None

    if xg_disponible:
        score += 2
        razones.append(
            "Señal xG utilizable "
            "en ambos equipos"
        )
    else:
        alertas.append(
            "Sin señal xG bilateral usable"
        )

    # Coherencia entre señales: 0-2 puntos
    totales = []

    for senal in (
        forma,
        casa,
        xg,
    ):
        if senal is not None:
            totales.append(
                senal["total"]
            )

    dispersion = None

    if len(totales) >= 2:
        dispersion = (
            max(totales)
            - min(totales)
        )

        if dispersion <= 0.75:
            score += 2
            razones.append(
                "Señales muy coherentes"
            )

        elif dispersion <= 1.25:
            score += 1
            razones.append(
                "Señales con dispersión moderada"
            )

        else:
            alertas.append(
                "Alta dispersión entre señales"
            )

    else:
        alertas.append(
            "Pocas señales independientes "
            "para contrastar"
        )

    # Base calculable: 0-1
    if base is not None:
        score += 1
    else:
        alertas.append(
            "BT0 no disponible"
        )

    # Tipo de competición: 0-1
    comp = competicion.casefold()

    especial = any(
        x in comp
        for x in (
            "amistoso",
            "friendly",
            "kings league",
        )
    )

    if not especial:
        score += 1
    else:
        alertas.append(
            "Competición no convencional/"
            "amistosa"
        )

    # ------------------------------------------------
    # NIVEL GLOBAL
    # ------------------------------------------------

    if (
        score >= 8
        and n_form_local >= 10
        and n_form_visitante >= 10
        and n_casa >= 8
        and n_fuera >= 8
        and (
            dispersion is None
            or dispersion <= 1.25
        )
        and not especial
        and base is not None
    ):
        nivel = "FUERTE"

    elif (
        score >= 5
        and n_form_local >= 5
        and n_form_visitante >= 5
        and base is not None
        and not especial
    ):
        nivel = "MEDIA"

    else:
        nivel = "DEBIL"

    # Amistosos/Kings nunca superan DÉBIL
    if especial:
        nivel = "DEBIL"

    # Mercados específicos
    nivel_goles = nivel

    # BTTS: el único mercado donde la ablación
    # mostró beneficio estadísticamente detectable
    # del xG. Sin xG no permitimos FUERTE.
    nivel_btts = nivel

    if not xg_disponible:
        nivel_btts = limitar_nivel(
            nivel_btts,
            "MEDIA",
        )

    # 1X2 todavía no tiene evidencia suficiente
    # para una categoría FUERTE.
    nivel_1x2 = limitar_nivel(
        nivel,
        "MEDIA",
    )

    salida = {
        "match_id": match_id,
        "partido": {
            "fecha": fecha,
            "competicion": competicion,
            "local": local,
            "visitante": visitante,
        },
        "modelo": (
            "J_BT_sin_temporada"
        ),
        "score": score,
        "nivel": nivel,
        "mercados": {
            "goles": nivel_goles,
            "BTTS": nivel_btts,
            "1X2": nivel_1x2,
        },
        "muestras": {
            "forma_local": n_form_local,
            "forma_visitante": (
                n_form_visitante
            ),
            "casa_local": n_casa,
            "fuera_visitante": n_fuera,
        },
        "xg_bilateral": xg_disponible,
        "dispersion_lambda_senales": (
            dispersion
        ),
        "lambda_base": base,
        "razones": razones,
        "alertas": alertas,
        "control_temporal": {
            "local": control_local,
            "visitante": control_visitante,
        },
    }

    ruta = (
        carpeta
        / "confidence.json"
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

    if not p.exists():
        return []

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
        d = clasificar(
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
                d = clasificar(mid)
            except Exception as e:
                print(
                    "ERROR",
                    mid,
                    repr(e),
                )
                continue

            conteo[
                d["nivel"]
            ] += 1

            procesados += 1

        print()
        print("=" * 72)
        print("CONFIANZA V1")
        print("=" * 72)
        print(
            "Procesados:",
            procesados,
        )

        for k in (
            "FUERTE",
            "MEDIA",
            "DEBIL",
        ):
            print(
                f"{k:8s}:",
                conteo[k],
            )

        return

    raise SystemExit(
        "Usa --match-id MID o --pool"
    )


if __name__ == "__main__":
    main()
