import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


CANDIDATOS = Path("data/backtest_candidates.json")
ESTADO = Path("data/backtest_dataset_progress.json")
MATCHES = Path("data/matches")


def cargar_json(ruta, defecto=None):
    if not ruta.exists():
        return defecto

    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def guardar_json(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)

    with ruta.open("w", encoding="utf-8") as f:
        json.dump(
            datos,
            f,
            ensure_ascii=False,
            indent=2,
        )


def ahora():
    return datetime.now().isoformat(
        timespec="seconds"
    )


def ejecutar(cmd):
    print()
    print("$", " ".join(cmd))
    print()

    r = subprocess.run(cmd)

    return r.returncode


def comprobar_resultado(mid):
    ruta = MATCHES / mid / "result.json"

    if not ruta.exists():
        return False, "sin_result.json"

    try:
        d = cargar_json(ruta, {})
    except Exception as exc:
        return False, f"result_json_error: {exc}"

    integridad = d.get(
        "integridad_temporal",
        {},
    )

    if integridad.get("estado") != "OK":
        return (
            False,
            "integridad_temporal_no_ok",
        )

    return True, "OK"


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Máximo de candidatos a intentar.",
    )

    parser.add_argument(
        "--pause",
        type=float,
        default=5.0,
        help="Pausa entre candidatos.",
    )

    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Permite reintentar candidatos ERROR.",
    )

    args = parser.parse_args()

    datos = cargar_json(CANDIDATOS)

    if not datos:
        raise SystemExit(
            "No existe data/backtest_candidates.json"
        )

    candidatos = datos.get("partidos", [])

    progreso = cargar_json(
        ESTADO,
        {
            "creado": ahora(),
            "actualizado": ahora(),
            "partidos": {},
        },
    )

    estados = progreso.setdefault(
        "partidos",
        {},
    )

    intentados = 0

    for candidato in candidatos:
        if intentados >= args.limit:
            break

        mid = candidato["match_id"]

        anterior = estados.get(mid, {})
        estado_anterior = anterior.get("estado")

        if estado_anterior == "OK":
            print(
                f"[SKIP] {mid} ya está OK"
            )
            continue

        if (
            estado_anterior == "ERROR"
            and not args.retry_errors
        ):
            print(
                f"[SKIP] {mid} está ERROR "
                f"(usa --retry-errors)"
            )
            continue

        intentados += 1

        print()
        print("=" * 78)
        print(
            f"[{intentados}/{args.limit}] "
            f"{mid} | "
            f"{candidato.get('local')} - "
            f"{candidato.get('visitante')}"
        )
        print("=" * 78)

        estados[mid] = {
            **candidato,
            "estado": "PROCESANDO",
            "inicio": ahora(),
        }

        progreso["actualizado"] = ahora()
        guardar_json(ESTADO, progreso)

        cmd = [
            sys.executable,
            "-m",
            "analysis.run_match",
            "--match-id",
            mid,
            "--prepare",
        ]

        codigo = ejecutar(cmd)

        if codigo != 0:
            estados[mid].update({
                "estado": "ERROR",
                "fin": ahora(),
                "motivo": (
                    f"run_match_returncode_{codigo}"
                ),
            })

            progreso["actualizado"] = ahora()
            guardar_json(ESTADO, progreso)

            print(
                f"[ERROR] {mid}: "
                f"run_match terminó con {codigo}"
            )

        else:
            ok, motivo = comprobar_resultado(mid)

            if ok:
                estados[mid].update({
                    "estado": "OK",
                    "fin": ahora(),
                    "motivo": "OK",
                })

                print(
                    f"[OK] {mid}: "
                    "integridad temporal validada"
                )

            else:
                estados[mid].update({
                    "estado": "DESCARTADO",
                    "fin": ahora(),
                    "motivo": motivo,
                })

                print(
                    f"[DESCARTADO] {mid}: "
                    f"{motivo}"
                )

            progreso["actualizado"] = ahora()
            guardar_json(ESTADO, progreso)

        if intentados < args.limit:
            print(
                f"Pausa conservadora: "
                f"{args.pause:.1f}s"
            )
            time.sleep(args.pause)

    conteo = {}

    for x in estados.values():
        e = x.get("estado", "DESCONOCIDO")
        conteo[e] = conteo.get(e, 0) + 1

    print()
    print("=" * 78)
    print("RESUMEN")
    print("=" * 78)

    for estado, n in sorted(conteo.items()):
        print(f"{estado:<12}: {n}")

    print()
    print("Progreso:", ESTADO)


if __name__ == "__main__":
    main()
