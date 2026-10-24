import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SRC = ROOT / "data" / "day_predictions_v2.json"

OUT_JSON = ROOT / "data" / "selected_window_matches.json"
OUT_TXT = ROOT / "data" / "selected_window_matches.txt"


def cargar(path):
    return json.loads(
        path.read_text(encoding="utf-8")
    )


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
        or "Local"
    )


def visitante(p):
    return (
        p.get("visitante")
        or p.get("equipo_visitante")
        or "Visitante"
    )


def pct(v):
    try:
        v = float(v)

        if 1 < v <= 100:
            v /= 100

        return f"{v:.1%}"

    except Exception:
        return "N/D"


def valor(p, *claves):
    for k in claves:
        if p.get(k) is not None:
            return p.get(k)

    return None


def parsear_seleccion(texto, n):
    texto = (
        texto.strip()
        .lower()
        .replace(" ", "")
    )

    if texto in (
        "todos",
        "todo",
        "all",
        "*",
    ):
        return list(range(1, n + 1))

    elegidos = set()

    for bloque in texto.split(","):
        if not bloque:
            continue

        if "-" in bloque:
            partes = bloque.split("-", 1)

            if len(partes) != 2:
                raise ValueError(
                    f"Rango inválido: {bloque}"
                )

            a = int(partes[0])
            b = int(partes[1])

            if a > b:
                a, b = b, a

            for x in range(a, b + 1):
                if 1 <= x <= n:
                    elegidos.add(x)

        else:
            x = int(bloque)

            if 1 <= x <= n:
                elegidos.add(x)

    if not elegidos:
        raise ValueError(
            "No seleccionaste partidos válidos."
        )

    return sorted(elegidos)


def ejecutar(modulo, match_id, extra=None):
    cmd = [
        sys.executable,
        "-u",
        "-m",
        modulo,
        "--match-id",
        match_id,
    ]

    if extra:
        cmd.extend(extra)

    print()
    print("=" * 92)
    print("EJECUTANDO:")
    print(" ".join(cmd))
    print("=" * 92)

    r = subprocess.run(
        cmd,
        cwd=ROOT,
    )

    return r.returncode


def mostrar(partidos):
    print()
    print("=" * 110)
    print("SELECCIÓN DE PARTIDOS — VENTANA ANALIZADA")
    print("=" * 110)

    for i, p in enumerate(
        partidos,
        1,
    ):
        p25 = valor(
            p,
            "+2.5",
            "over_2_5",
        )

        btts = valor(
            p,
            "BTTS",
            "btts",
            "p_btts",
        )

        hora = (
            p.get("hora")
            or p.get("time")
            or ""
        )

        comp = (
            p.get("competicion")
            or p.get("liga")
            or ""
        )

        calidad = p.get(
            "calidad_datos",
            "N/D",
        )

        conf = p.get(
            "confianza_btts",
            "N/D",
        )

        fuera = (
            calidad == "FUERA_MODELO"
        )

        marca = (
            " [FUERA MODELO]"
            if fuera
            else ""
        )

        print(
            f"{i:02d}. "
            f"{local(p)} vs {visitante(p)}"
            f"{marca}"
        )

        print(
            f"    {hora} | {comp}"
        )

        print(
            "    2.5+: "
            f"{pct(p25)}"
            " | BTTS: "
            f"{pct(btts)}"
            " | Calidad: "
            f"{calidad}"
            " | Conf.BTTS: "
            f"{conf}"
        )

    print()
    print("=" * 110)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--select",
        help=(
            'Ej.: "1,3,5-7" o "todos". '
            "Si se omite, pregunta interactivamente."
        ),
    )

    parser.add_argument(
        "--run",
        action="store_true",
        help=(
            "Ejecuta scrapeo/análisis completo "
            "sobre los seleccionados."
        ),
    )

    parser.add_argument(
        "--refresh",
        action="store_true",
        help=(
            "Con --run fuerza refresh de "
            "history/standings donde corresponda."
        ),
    )

    parser.add_argument(
        "--include-outside-model",
        action="store_true",
        help=(
            "Permite seleccionar competiciones "
            "marcadas FUERA_MODELO."
        ),
    )

    args = parser.parse_args()

    if not SRC.exists():
        raise SystemExit(
            "No existe data/day_predictions_v2.json.\n"
            "Ejecuta primero la ventana diaria V2."
        )

    datos = cargar(SRC)

    partidos = datos.get(
        "partidos",
        []
    )

    if not partidos:
        raise SystemExit(
            "No hay partidos en la ventana."
        )

    mostrar(partidos)

    seleccion_txt = args.select

    if not seleccion_txt:
        seleccion_txt = input(
            "Selecciona partidos "
            "(ej. 1,3,5-7 / todos): "
        )

    indices = parsear_seleccion(
        seleccion_txt,
        len(partidos),
    )

    seleccionados = []

    omitidos = []

    for idx in indices:
        p = partidos[idx - 1]

        if (
            p.get("calidad_datos")
            == "FUERA_MODELO"
            and not args.include_outside_model
        ):
            omitidos.append(
                (
                    idx,
                    local(p),
                    visitante(p),
                )
            )
            continue

        seleccionados.append(
            dict(p)
        )

    if not seleccionados:
        raise SystemExit(
            "No quedaron partidos seleccionables."
        )

    OUT_JSON.write_text(
        json.dumps(
            {
                "total": len(seleccionados),
                "partidos": seleccionados,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    OUT_TXT.write_text(
        "\n".join(
            mid(p)
            for p in seleccionados
            if mid(p)
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 92)
    print("SELECCIÓN FINAL")
    print("=" * 92)

    for i, p in enumerate(
        seleccionados,
        1,
    ):
        print(
            f"{i:02d}. "
            f"{local(p)} vs {visitante(p)}"
            f" | ID={mid(p)}"
        )

    if omitidos:
        print()
        print("Omitidos por FUERA_MODELO:")

        for idx, l, v in omitidos:
            print(
                f"  {idx:02d}. {l} vs {v}"
            )

    print()
    print(
        "JSON:",
        OUT_JSON,
    )

    print(
        "TXT :",
        OUT_TXT,
    )

    if not args.run:
        print()
        print(
            "Selección guardada. "
            "Usa --run para procesarla."
        )
        return

    print()
    print("=" * 92)
    print("SCRAPEO + ANÁLISIS DE SELECCIONADOS")
    print("=" * 92)

    ok = []
    errores = []

    for n, p in enumerate(
        seleccionados,
        1,
    ):
        partido_id = mid(p)

        if not partido_id:
            errores.append(
                ("SIN_ID", local(p), visitante(p))
            )
            continue

        print()
        print(
            f"[{n}/{len(seleccionados)}] "
            f"{local(p)} vs {visitante(p)}"
        )

        extra = [
            "--prepare",
        ]

        if args.refresh:
            extra.append(
                "--refresh"
            )

        rc = ejecutar(
            "analysis.run_match",
            partido_id,
            extra,
        )

        if rc == 0:
            # Generar Confidence V2 una vez
            # terminado el análisis.
            rc_conf = ejecutar(
                "analysis.confidence_v2",
                partido_id,
            )

            if rc_conf == 0:
                ok.append(partido_id)
            else:
                errores.append(
                    (
                        partido_id,
                        "confidence_v2",
                    )
                )

        else:
            errores.append(
                (
                    partido_id,
                    "run_match",
                )
            )

    print()
    print("=" * 92)
    print("RESULTADO")
    print("=" * 92)
    print(
        "Completados:",
        len(ok),
        "/",
        len(seleccionados),
    )

    if errores:
        print()
        print("Pendientes / errores:")

        for e in errores:
            print(
                "  ",
                " | ".join(
                    str(x)
                    for x in e
                )
            )

    print("=" * 92)


if __name__ == "__main__":
    main()
