import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path


CANDIDATOS = Path("data/partidos_candidatos.json")
SELECCION = Path("data/day_selected.json")
ERRORES = Path("data/day_errors.txt")
LOGS = Path("data/day_logs")
MATCHES = Path("data/matches")
IDS_TMP = Path("/tmp/matches_hoy.txt")
REPORTE = Path("data/reporte_jornada.html")


def argumentos():
    p = argparse.ArgumentParser(
        description=(
            "Ejecuta la jornada completa de Match Goals AI."
        )
    )

    p.add_argument(
        "--hours",
        type=float,
        default=4,
        help=(
            "Ventana de próximos partidos en horas. "
            "Ejemplo: 4 = próximos 240 minutos."
        ),
    )

    p.add_argument(
        "--limit",
        type=int,
        default=15,
        help=(
            "Cantidad máxima de partidos. "
            "Permitido: 1 a 30."
        ),
    )

    p.add_argument(
        "--max-per-competition",
        type=int,
        default=3,
        help=(
            "Preferencia de máximo por competición "
            "en la primera pasada. 0 = sin límite."
        ),
    )

    p.add_argument(
        "--pause",
        type=float,
        default=5.0,
        help="Pausa entre partidos nuevos.",
    )

    p.add_argument(
        "--days",
        type=int,
        default=2,
        help="Días solicitados a flashscore.py.",
    )

    p.add_argument(
        "--country",
        default=None,
        help="Filtro opcional por país.",
    )

    p.add_argument(
        "--competition",
        default=None,
        help="Filtro opcional por competición.",
    )

    p.add_argument(
        "--refresh-existing",
        action="store_true",
        help=(
            "Recalcula también partidos que ya "
            "tienen result.json válido."
        ),
    )

    p.add_argument(
        "--skip-slate-refresh",
        action="store_true",
        help=(
            "No vuelve a ejecutar flashscore/filter; "
            "reutiliza partidos_candidatos.json."
        ),
    )

    p.add_argument(
        "--open",
        action="store_true",
        help="Abre el reporte HTML al terminar.",
    )

    args = p.parse_args()

    if not 1 <= args.limit <= 30:
        p.error(
            "--limit debe estar entre 1 y 30."
        )

    if args.hours <= 0 or args.hours > 48:
        p.error(
            "--hours debe ser mayor que 0 "
            "y máximo 48."
        )

    if args.pause < 0:
        p.error("--pause no puede ser negativo.")

    if args.days < 1:
        p.error("--days debe ser >= 1.")

    if args.max_per_competition < 0:
        p.error(
            "--max-per-competition debe ser >= 0."
        )

    return args


def cargar_json(ruta, defecto=None):
    if defecto is None:
        defecto = {}

    if not ruta.exists():
        return defecto

    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def guardar_json(ruta, datos):
    ruta.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with ruta.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            datos,
            f,
            ensure_ascii=False,
            indent=2,
        )


def ejecutar_modulo(
    modulo,
    extras,
    log_name,
):
    LOGS.mkdir(
        parents=True,
        exist_ok=True,
    )

    ruta_log = LOGS / log_name

    comando = [
        sys.executable,
        "-m",
        modulo,
        *extras,
    ]

    print(
        f"Ejecutando {modulo}..."
    )

    with ruta_log.open(
        "w",
        encoding="utf-8",
    ) as log:
        resultado = subprocess.run(
            comando,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
        )

    if resultado.returncode == 0:
        print(
            f"  OK -> {ruta_log}"
        )
    else:
        print(
            f"  ERROR ({resultado.returncode}) "
            f"-> {ruta_log}"
        )

    return resultado.returncode


def parsear_fecha_hora(partido):
    valor = partido.get(
        "fecha_hora_local"
    )

    if valor:
        texto = str(valor).strip()

        try:
            texto_iso = texto.replace(
                "Z",
                "+00:00",
            )

            return datetime.fromisoformat(
                texto_iso
            )
        except ValueError:
            pass

        formatos = (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
        )

        for formato in formatos:
            try:
                return datetime.strptime(
                    texto,
                    formato,
                )
            except ValueError:
                continue

    fecha = partido.get("fecha")
    hora = partido.get("hora")

    if fecha and hora:
        texto = f"{fecha} {hora}"

        try:
            return datetime.strptime(
                texto,
                "%Y-%m-%d %H:%M",
            )
        except ValueError:
            pass

    return None


def minutos_hasta(fecha_hora):
    if fecha_hora is None:
        return None

    if fecha_hora.tzinfo is not None:
        ahora = datetime.now(
            fecha_hora.tzinfo
        )
    else:
        ahora = datetime.now()

    return (
        fecha_hora - ahora
    ).total_seconds() / 60.0


def contiene(valor, filtro):
    if not filtro:
        return True

    return (
        filtro.casefold()
        in str(valor or "").casefold()
    )


def clave_competicion(partido):
    return (
        str(partido.get("pais") or ""),
        str(
            partido.get(
                "competicion"
            ) or ""
        ),
    )


def preparar_candidatos(
    datos,
    args,
):
    if isinstance(datos, list):
        candidatos = datos
    else:
        candidatos = (
            datos.get("candidatos")
            or datos.get("partidos")
            or []
        )

    elegibles = []
    vistos = set()

    for partido in candidatos:
        mid = (
            partido.get("id")
            or partido.get("match_id")
        )

        if not mid or mid in vistos:
            continue

        vistos.add(mid)

        if not contiene(
            partido.get("pais"),
            args.country,
        ):
            continue

        if not contiene(
            partido.get("competicion"),
            args.competition,
        ):
            continue

        fecha_hora = parsear_fecha_hora(
            partido
        )

        minutos = minutos_hasta(
            fecha_hora
        )

        if minutos is None:
            continue

        # Sólo futuro.
        if minutos < 0:
            continue

        # Ventana móvil.
        if minutos > (
            args.hours * 60
        ):
            continue

        copia = dict(partido)
        copia["match_id"] = mid
        copia[
            "minutos_hasta_inicio"
        ] = round(minutos, 1)

        elegibles.append(
            copia
        )

    elegibles.sort(
        key=lambda p: (
            p[
                "minutos_hasta_inicio"
            ],
            str(
                p.get(
                    "competicion",
                    "",
                )
            ),
        )
    )

    return elegibles


def seleccionar_diverso(
    elegibles,
    limite,
    max_por_competicion,
):
    if max_por_competicion == 0:
        return elegibles[:limite]

    seleccion = []
    seleccionados = set()
    contador = Counter()

    # Primera pasada:
    # prioriza diversidad.
    for partido in elegibles:
        clave = clave_competicion(
            partido
        )

        if contador[clave] >= (
            max_por_competicion
        ):
            continue

        seleccion.append(partido)
        seleccionados.add(
            partido["match_id"]
        )
        contador[clave] += 1

        if len(seleccion) >= limite:
            return seleccion

    # Segunda pasada:
    # si no alcanzamos el límite,
    # rellenamos con los siguientes,
    # aunque superen el máximo preferente.
    for partido in elegibles:
        if (
            partido["match_id"]
            in seleccionados
        ):
            continue

        seleccion.append(partido)
        seleccionados.add(
            partido["match_id"]
        )

        if len(seleccion) >= limite:
            break

    return seleccion


def resultado_reutilizable(mid):
    carpeta = MATCHES / mid

    result = cargar_json(
        carpeta / "result.json",
        {},
    )

    lambdas = cargar_json(
        carpeta
        / "lambda_comparison.json",
        {},
    )

    if not result or not lambdas:
        return False

    integridad = result.get(
        "integridad_temporal",
        {},
    )

    if integridad.get(
        "estado"
    ) != "OK":
        return False

    metodos = lambdas.get(
        "metodos",
        {},
    )

    return (
        "J_BT_sin_temporada"
        in metodos
    )


def escribir_ids(seleccion):
    contenido = "\n".join(
        p["match_id"]
        for p in seleccion
    )

    if contenido:
        contenido += "\n"

    IDS_TMP.write_text(
        contenido,
        encoding="utf-8",
    )


def abrir_reporte():
    if not REPORTE.exists():
        print(
            "No existe reporte para abrir."
        )
        return

    try:
        ruta_windows = (
            subprocess.check_output(
                [
                    "wslpath",
                    "-w",
                    str(REPORTE.resolve()),
                ],
                text=True,
            )
            .strip()
        )

        subprocess.run(
            [
                "explorer.exe",
                ruta_windows,
            ],
            check=False,
        )

    except Exception as exc:
        print(
            "No pude abrir automáticamente:",
            exc,
        )


def main():
    args = argumentos()

    print("=" * 78)
    print("MATCH GOALS AI | RUN DAY")
    print("=" * 78)

    print(
        f"Ventana       : próximas {args.hours:g} h"
    )
    print(
        f"Límite        : {args.limit}"
    )
    print(
        "Máx/torneo    :",
        args.max_per_competition,
    )

    # -----------------------------------------
    # 1. Actualizar jornada
    # -----------------------------------------

    if not args.skip_slate_refresh:
        codigo = ejecutar_modulo(
            "scraper.flashscore",
            [
                "--days",
                str(args.days),
            ],
            "flashscore.log",
        )

        if codigo != 0:
            raise SystemExit(
                "Falló scraper.flashscore. "
                "Revisa data/day_logs/flashscore.log"
            )

        codigo = ejecutar_modulo(
            "scraper.filter_matches",
            [
                "--grace-minutes",
                "0",
            ],
            "filter_matches.log",
        )

        if codigo != 0:
            raise SystemExit(
                "Falló scraper.filter_matches. "
                "Revisa data/day_logs/filter_matches.log"
            )

    if not CANDIDATOS.exists():
        raise SystemExit(
            "No existe "
            "data/partidos_candidatos.json"
        )

    # -----------------------------------------
    # 2. Selección por ventana horaria
    # -----------------------------------------

    datos = cargar_json(
        CANDIDATOS,
        {},
    )

    elegibles = preparar_candidatos(
        datos,
        args,
    )

    seleccion = seleccionar_diverso(
        elegibles,
        args.limit,
        args.max_per_competition,
    )

    print()
    print(
        "Elegibles en ventana:",
        len(elegibles),
    )

    print(
        "Seleccionados:",
        len(seleccion),
    )

    if not seleccion:
        print(
            "No hay partidos en la ventana."
        )
        return

    salida_seleccion = {
        "generado": (
            datetime.now().isoformat(
                timespec="seconds"
            )
        ),
        "hours": args.hours,
        "limit": args.limit,
        "max_per_competition": (
            args.max_per_competition
        ),
        "partidos": seleccion,
    }

    guardar_json(
        SELECCION,
        salida_seleccion,
    )

    escribir_ids(seleccion)

    print()
    print(
        f"{'#':>2} "
        f"{'MIN':>6} "
        f"{'COMPETICION':<26} "
        f"PARTIDO"
    )
    print("-" * 100)

    for i, p in enumerate(
        seleccion,
        1,
    ):
        partido = (
            f"{p.get('local')} - "
            f"{p.get('visitante')}"
        )

        print(
            f"{i:>2} "
            f"{p['minutos_hasta_inicio']:>6.0f} "
            f"{str(p.get('competicion') or '')[:26]:<26} "
            f"{partido}"
        )

    # -----------------------------------------
    # 3. Analizar partidos
    # -----------------------------------------

    errores = []
    nuevos = 0
    reutilizados = 0

    print()
    print("=" * 78)
    print("ANALISIS")
    print("=" * 78)

    total = len(seleccion)

    for indice, partido in enumerate(
        seleccion,
        1,
    ):
        mid = partido["match_id"]

        nombre = (
            f"{partido.get('local')} - "
            f"{partido.get('visitante')}"
        )

        print()
        print(
            f"[{indice}/{total}] "
            f"{mid} | {nombre}"
        )

        reutilizar = (
            not args.refresh_existing
            and resultado_reutilizable(
                mid
            )
        )

        if reutilizar:
            reutilizados += 1
            print(
                "  REUTILIZADO: análisis válido existente"
            )
            continue

        codigo = ejecutar_modulo(
            "analysis.run_match",
            [
                "--match-id",
                mid,
                "--prepare",
            ],
            f"{mid}.log",
        )

        if codigo == 0:
            nuevos += 1
            print(
                "  ANALIZADO: OK"
            )
        else:
            errores.append(mid)
            print(
                "  ANALIZADO: ERROR"
            )

        if (
            indice < total
            and args.pause > 0
        ):
            time.sleep(args.pause)

    ERRORES.write_text(
        "".join(
            f"{mid}\n"
            for mid in errores
        ),
        encoding="utf-8",
    )

    # -----------------------------------------
    # 4. Ranking
    # -----------------------------------------

    codigo_rank = ejecutar_modulo(
        "analysis.rank_day",
        [],
        "rank_day.log",
    )

    if codigo_rank != 0:
        raise SystemExit(
            "Falló analysis.rank_day. "
            "Revisa data/day_logs/rank_day.log"
        )

    # -----------------------------------------
    # 5. HTML
    # -----------------------------------------

    codigo_report = ejecutar_modulo(
        "analysis.report_day",
        [],
        "report_day.log",
    )

    if codigo_report != 0:
        raise SystemExit(
            "Falló analysis.report_day. "
            "Revisa data/day_logs/report_day.log"
        )

    # -----------------------------------------
    # 6. Resumen
    # -----------------------------------------

    print()
    print("=" * 78)
    print("JORNADA COMPLETADA")
    print("=" * 78)

    print(
        "Seleccionados :",
        len(seleccion),
    )
    print(
        "Nuevos OK     :",
        nuevos,
    )
    print(
        "Reutilizados  :",
        reutilizados,
    )
    print(
        "Errores       :",
        len(errores),
    )

    if errores:
        print()
        print("IDs con error:")

        for mid in errores:
            print(
                " ",
                mid,
                "->",
                LOGS / f"{mid}.log",
            )

    print()
    print(
        "Predicciones  : data/day_predictions.json"
    )
    print(
        "Reporte HTML  : data/reporte_jornada.html"
    )
    print(
        "Selección     : data/day_selected.json"
    )
    print(
        "Logs          : data/day_logs/"
    )

    if args.open:
        abrir_reporte()


if __name__ == "__main__":
    main()
