import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def ejecutar(modulo, args):
    cmd = [
        sys.executable,
        "-u",
        "-m",
        modulo,
        *args,
    ]

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


def nombre(p):
    local = (
        p.get("local")
        or p.get("equipo_local")
        or "Local"
    )

    visitante = (
        p.get("visitante")
        or p.get("equipo_visitante")
        or "Visitante"
    )

    return f"{local} vs {visitante}"


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--file",
        required=True,
        help="JSON generado por select_day_matches",
    )

    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Fuerza refresh de history/standings",
    )

    args = parser.parse_args()

    ruta = ROOT / args.file

    if not ruta.exists():
        raise SystemExit(
            f"No existe: {ruta}"
        )

    datos = json.loads(
        ruta.read_text(encoding="utf-8")
    )

    partidos = datos.get(
        "partidos",
        []
    )

    if not partidos:
        raise SystemExit(
            "El archivo no contiene partidos."
        )

    print("=" * 100)
    print("ANÁLISIS DE SELECCIÓN GUARDADA")
    print("=" * 100)
    print("Archivo:", ruta)
    print("Partidos:", len(partidos))

    ok = []
    errores = []

    for i, p in enumerate(
        partidos,
        1,
    ):
        partido_id = mid(p)

        print()
        print("#" * 100)
        print(
            f"[{i}/{len(partidos)}] "
            f"{nombre(p)}"
        )
        print("MATCH ID:", partido_id)
        print("#" * 100)

        if not partido_id:
            errores.append(
                (nombre(p), "SIN_ID")
            )
            continue

        extra = [
            "--match-id",
            partido_id,
            "--prepare",
        ]

        if args.refresh:
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

        ok.append(partido_id)

    print()
    print("=" * 100)
    print("RESULTADO FINAL")
    print("=" * 100)
    print(
        "Completados:",
        len(ok),
        "/",
        len(partidos),
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

    print("=" * 100)


if __name__ == "__main__":
    main()
