import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PARTIDOS_JSON = ROOT / "data" / "partidos.json"
WINDOW_JSON = ROOT / "data" / "day_predictions_v2.json"


# ============================================================
# UTILIDADES
# ============================================================

def cargar(path):
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def ejecutar(modulo, extra=None):
    cmd = [
        sys.executable,
        "-u",
        "-m",
        modulo,
    ]

    if extra:
        cmd.extend(extra)

    print()
    print("=" * 100)
    print("EJECUTANDO:")
    print(" ".join(cmd))
    print("=" * 100)

    return subprocess.run(
        cmd,
        cwd=ROOT,
    ).returncode


def mid(p):
    return (
        p.get("match_id")
        or p.get("id")
        or p.get("flashscore_id")
    )


def local(p):
    return (
        p.get("local")
        or p.get("equipo_local")
        or p.get("home")
        or "Local"
    )


def visitante(p):
    return (
        p.get("visitante")
        or p.get("equipo_visitante")
        or p.get("away")
        or "Visitante"
    )


def competicion(p):
    return (
        p.get("competicion")
        or p.get("liga")
        or p.get("tournament")
        or ""
    )


def hora(p):
    return (
        p.get("hora")
        or p.get("time")
        or ""
    )


def normalizar(s):
    return " ".join(
        str(s or "")
        .strip()
        .casefold()
        .split()
    )


# ============================================================
# FECHAS
# ============================================================

def resolver_fecha(valor):
    hoy = date.today()

    valor = str(valor).strip().lower()

    if valor in (
        "today",
        "hoy",
    ):
        return hoy

    if valor in (
        "tomorrow",
        "mañana",
        "manana",
    ):
        return hoy + timedelta(days=1)

    return datetime.strptime(
        valor,
        "%Y-%m-%d",
    ).date()


def fecha_partido(p):
    raw = (
        p.get("fecha")
        or p.get("date")
    )

    if not raw:
        return None

    raw = str(raw).strip()

    for fmt in (
        "%Y-%m-%d",
        "%d.%m.%y",
        "%d.%m.%Y",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(
                raw,
                fmt,
            ).date()
        except ValueError:
            pass

    return None


# ============================================================
# NORMALIZAR partidos.json
# ============================================================

def extraer_partidos(datos):
    if isinstance(datos, list):
        return datos

    if not isinstance(datos, dict):
        return []

    for key in (
        "partidos",
        "matches",
        "events",
    ):
        if isinstance(
            datos.get(key),
            list,
        ):
            return datos[key]

    salida = []

    for seccion in datos.get(
        "secciones",
        [],
    ):
        for partido in seccion.get(
            "partidos",
            [],
        ):
            x = dict(partido)

            if not x.get("competicion"):
                x["competicion"] = (
                    seccion.get("titulo")
                    or seccion.get(
                        "competicion"
                    )
                    or ""
                )

            salida.append(x)

    return salida


# ============================================================
# SELECCIÓN
# ============================================================

def parsear_indices(texto, total):
    texto = (
        str(texto)
        .strip()
        .replace(" ", "")
        .lower()
    )

    if texto in (
        "todos",
        "todo",
        "all",
        "*",
    ):
        return list(
            range(1, total + 1)
        )

    encontrados = set()

    for bloque in texto.split(","):
        if not bloque:
            continue

        if "-" in bloque:
            a, b = bloque.split(
                "-",
                1,
            )

            a = int(a)
            b = int(b)

            if a > b:
                a, b = b, a

            for n in range(
                a,
                b + 1,
            ):
                if 1 <= n <= total:
                    encontrados.add(n)

        else:
            n = int(bloque)

            if 1 <= n <= total:
                encontrados.add(n)

    return sorted(encontrados)


def seleccionar_por_mid(
    partidos,
    mids,
):
    buscados = {
        str(x).strip()
        for x in mids
        if str(x).strip()
    }

    salida = []

    for p in partidos:
        if mid(p) in buscados:
            salida.append(p)

    faltan = (
        buscados
        - {
            mid(p)
            for p in salida
        }
    )

    return salida, faltan


def seleccionar_exactamente(
    partidos,
    texto,
):
    """
    Permite:
       Local vs Visitante
    """

    patron = re.split(
        r"\s+vs\.?\s+",
        texto.strip(),
        flags=re.I,
    )

    if len(patron) != 2:
        return []

    l_obj = normalizar(
        patron[0]
    )

    v_obj = normalizar(
        patron[1]
    )

    return [
        p
        for p in partidos
        if (
            normalizar(local(p))
            == l_obj
            and normalizar(
                visitante(p)
            )
            == v_obj
        )
    ]


# ============================================================
# MOSTRAR
# ============================================================

def mostrar(partidos, titulo):
    print()
    print("=" * 118)
    print(titulo)
    print("=" * 118)

    for i, p in enumerate(
        partidos,
        1,
    ):
        print(
            f"{i:03d}. "
            f"{hora(p):5s} | "
            f"{local(p)} vs "
            f"{visitante(p)}"
        )

        print(
            f"     {competicion(p)}"
        )

        print(
            f"     MATCH ID: "
            f"{mid(p) or 'SIN_ID'}"
        )

    print("=" * 118)
    print(
        f"TOTAL: {len(partidos)}"
    )
    print("=" * 118)


# ============================================================
# GUARDAR
# ============================================================

def guardar(
    seleccionados,
    target_date,
):
    fecha_txt = (
        target_date.isoformat()
        if target_date
        else "window"
    )

    out_json = (
        ROOT
        / "data"
        / f"selected_matches_{fecha_txt}.json"
    )

    out_txt = (
        ROOT
        / "data"
        / f"selected_matches_{fecha_txt}.txt"
    )

    out_json.write_text(
        json.dumps(
            {
                "fecha": fecha_txt,
                "total": len(
                    seleccionados
                ),
                "partidos": seleccionados,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    out_txt.write_text(
        "\n".join(
            mid(p)
            for p in seleccionados
            if mid(p)
        )
        + "\n",
        encoding="utf-8",
    )

    return out_json, out_txt


# ============================================================
# ANALIZAR SELECCIONADOS
# ============================================================

def analizar(
    seleccionados,
    refresh=False,
):
    ok = []
    errores = []

    for i, p in enumerate(
        seleccionados,
        1,
    ):
        partido_id = mid(p)

        print()
        print("#" * 100)

        print(
            f"[{i}/{len(seleccionados)}] "
            f"{local(p)} vs "
            f"{visitante(p)}"
        )

        print(
            "MATCH ID:",
            partido_id,
        )

        print("#" * 100)

        if not partido_id:
            errores.append(
                (
                    "SIN_ID",
                    local(p),
                    visitante(p),
                )
            )
            continue

        extra = [
            "--match-id",
            partido_id,
            "--prepare",
        ]

        if refresh:
            extra.append(
                "--refresh"
            )

        rc = ejecutar(
            "analysis.run_match",
            extra,
        )

        if rc != 0:
            errores.append(
                (
                    partido_id,
                    "run_match",
                )
            )
            continue

        rc = ejecutar(
            "analysis.confidence_v2",
            [
                "--match-id",
                partido_id,
            ],
        )

        if rc != 0:
            errores.append(
                (
                    partido_id,
                    "confidence_v2",
                )
            )
            continue

        ok.append(
            partido_id
        )

    return ok, errores


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Selector exacto de partidos "
            "Match Goals AI"
        )
    )

    parser.add_argument(
        "--source",
        choices=(
            "day",
            "window",
        ),
        default="day",
        help=(
            "day = partidos.json por fecha; "
            "window = ventana ya analizada."
        ),
    )

    parser.add_argument(
        "--date",
        default="tomorrow",
        help=(
            "today, tomorrow o YYYY-MM-DD. "
            "Sólo aplica con --source day."
        ),
    )

    parser.add_argument(
        "--refresh-list",
        action="store_true",
        help=(
            "Actualiza primero partidos.json "
            "con scraper.flashscore --days 2."
        ),
    )

    parser.add_argument(
        "--select",
        help=(
            'Índices: "1,3,7-9" '
            'o "todos".'
        ),
    )

    parser.add_argument(
        "--match-id",
        action="append",
        default=[],
        help=(
            "Selecciona exactamente por "
            "Match ID. Puede repetirse."
        ),
    )

    parser.add_argument(
        "--exact",
        action="append",
        default=[],
        help=(
            'Selección exacta por nombres: '
            '"Local vs Visitante". '
            "Puede repetirse."
        ),
    )

    parser.add_argument(
        "--run",
        action="store_true",
        help=(
            "Scrapea y analiza inmediatamente "
            "los partidos elegidos."
        ),
    )

    parser.add_argument(
        "--refresh-data",
        action="store_true",
        help=(
            "Fuerza refresh de datos "
            "durante run_match."
        ),
    )

    args = parser.parse_args()

    target_date = None

    # --------------------------------------------------------
    # REFRESH FIXTURES
    # --------------------------------------------------------

    if (
        args.source == "day"
        and args.refresh_list
    ):
        rc = ejecutar(
            "scraper.flashscore",
            [
                "--days",
                "2",
            ],
        )

        if rc != 0:
            raise SystemExit(
                "Falló actualización "
                "de partidos."
            )

    # --------------------------------------------------------
    # CARGAR FUENTE
    # --------------------------------------------------------

    if args.source == "window":
        if not WINDOW_JSON.exists():
            raise SystemExit(
                "No existe "
                "data/day_predictions_v2.json"
            )

        datos = cargar(
            WINDOW_JSON
        )

        partidos = datos.get(
            "partidos",
            [],
        )

        titulo = (
            "PARTIDOS DE LA VENTANA "
            "YA ANALIZADA"
        )

    else:
        if not PARTIDOS_JSON.exists():
            raise SystemExit(
                "No existe data/partidos.json.\n"
                "Ejecuta con --refresh-list."
            )

        target_date = resolver_fecha(
            args.date
        )

        todos = extraer_partidos(
            cargar(
                PARTIDOS_JSON
            )
        )

        partidos = [
            p
            for p in todos
            if fecha_partido(p)
            == target_date
        ]

        partidos.sort(
            key=lambda p: (
                hora(p),
                competicion(p),
                local(p),
            )
        )

        titulo = (
            "PARTIDOS DEL "
            + target_date.isoformat()
        )

    if not partidos:
        raise SystemExit(
            "No encontré partidos "
            "para esa selección."
        )

    mostrar(
        partidos,
        titulo,
    )

    # --------------------------------------------------------
    # ELEGIR
    # --------------------------------------------------------

    seleccionados = []
    usados = set()

    def agregar(p):
        partido_id = mid(p)

        clave = (
            partido_id
            or (
                normalizar(local(p)),
                normalizar(
                    visitante(p)
                ),
                hora(p),
            )
        )

        if clave not in usados:
            usados.add(clave)
            seleccionados.append(p)

    # Por Match ID exacto
    if args.match_id:
        encontrados, faltan = (
            seleccionar_por_mid(
                partidos,
                args.match_id,
            )
        )

        for p in encontrados:
            agregar(p)

        if faltan:
            print()
            print(
                "MATCH IDs no encontrados:"
            )

            for x in sorted(faltan):
                print(
                    "  ",
                    x,
                )

    # Por nombres exactos
    for texto in args.exact:
        encontrados = (
            seleccionar_exactamente(
                partidos,
                texto,
            )
        )

        if not encontrados:
            print(
                "No encontré exactamente:",
                texto,
            )

        for p in encontrados:
            agregar(p)

    # Por índices
    if args.select:
        indices = parsear_indices(
            args.select,
            len(partidos),
        )

        for n in indices:
            agregar(
                partidos[n - 1]
            )

    # Interactivo
    if not seleccionados:
        print()
        print(
            "Puedes seleccionar:"
        )

        print(
            "  3           -> partido #3"
        )

        print(
            "  1,4,8       -> varios"
        )

        print(
            "  2-6         -> rango"
        )

        print(
            "  todos       -> todos"
        )

        texto = input(
            "\nSelección: "
        )

        indices = parsear_indices(
            texto,
            len(partidos),
        )

        for n in indices:
            agregar(
                partidos[n - 1]
            )

    if not seleccionados:
        raise SystemExit(
            "No quedó ningún partido "
            "seleccionado."
        )

    # --------------------------------------------------------
    # CONFIRMACIÓN
    # --------------------------------------------------------

    print()
    print("=" * 118)
    print("SELECCIÓN EXACTA FINAL")
    print("=" * 118)

    for i, p in enumerate(
        seleccionados,
        1,
    ):
        print(
            f"{i:02d}. "
            f"{hora(p)} | "
            f"{local(p)} vs "
            f"{visitante(p)}"
        )

        print(
            f"    {competicion(p)}"
        )

        print(
            f"    MATCH ID: "
            f"{mid(p)}"
        )

    print("=" * 118)

    out_json, out_txt = guardar(
        seleccionados,
        target_date,
    )

    print()
    print(
        "JSON:",
        out_json,
    )

    print(
        "TXT :",
        out_txt,
    )

    # --------------------------------------------------------
    # RUN
    # --------------------------------------------------------

    if not args.run:
        print()
        print(
            "Selección guardada."
        )

        print(
            "Añade --run para ejecutar "
            "scrapeo + análisis."
        )

        return

    ok, errores = analizar(
        seleccionados,
        refresh=args.refresh_data,
    )

    print()
    print("=" * 100)
    print("RESULTADO FINAL")
    print("=" * 100)

    print(
        "Completados:",
        len(ok),
        "/",
        len(seleccionados),
    )

    if errores:
        print()
        print("Pendientes:")

        for e in errores:
            print(
                "  ",
                " | ".join(
                    str(x)
                    for x in e
                )
            )

    print("=" * 100)


if __name__ == "__main__":
    main()
