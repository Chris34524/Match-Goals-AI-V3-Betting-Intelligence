import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


LISTA = Path("data/matches_manana.txt")
MATCHES = Path("data/matches")
LOGS = Path("data/tomorrow_logs")
ERRORES = Path("data/tomorrow_errors.txt")


def cargar_json(ruta):
    try:
        with ruta.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def completo(mid):
    carpeta = MATCHES / mid

    result = cargar_json(
        carpeta / "result.json"
    )

    lambdas = cargar_json(
        carpeta / "lambda_comparison.json"
    )

    if not result or not lambdas:
        return False

    integridad = (
        result
        .get("integridad_temporal", {})
        .get("estado")
    )

    modelo = (
        lambdas
        .get("metodos", {})
        .get("J_BT_sin_temporada")
    )

    return (
        integridad == "OK"
        and modelo is not None
    )


def main():
    if not LISTA.exists():
        raise SystemExit(
            "ERROR: no existe "
            "data/matches_manana.txt"
        )

    ids = [
        x.strip()
        for x in LISTA.read_text(
            encoding="utf-8"
        ).splitlines()
        if x.strip()
    ]

    if not ids:
        raise SystemExit(
            "ERROR: data/matches_manana.txt "
            "está vacío"
        )

    LOGS.mkdir(
        parents=True,
        exist_ok=True,
    )

    completados = [
        mid
        for mid in ids
        if completo(mid)
    ]

    pendientes = [
        mid
        for mid in ids
        if not completo(mid)
    ]

    print("=" * 72)
    print("MATCH GOALS AI | PROCESO REANUDABLE")
    print("=" * 72)
    print("TOTAL       :", len(ids))
    print("COMPLETADOS :", len(completados))
    print("PENDIENTES  :", len(pendientes))

    if ids:
        print(
            "AVANCE      :",
            f"{len(completados) / len(ids) * 100:.1f}%"
        )

    print("=" * 72)

    if not pendientes:
        print("TODO COMPLETADO")
        return

    errores = []

    for numero, mid in enumerate(
        pendientes,
        start=1,
    ):
        print()
        print(
            f"[{numero}/{len(pendientes)}] "
            f"{mid}"
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
                start_new_session=True,
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
                print()
                print("=" * 72)
                print("PROCESO PAUSADO")
                print(
                    "El partido actual puede quedar "
                    "incompleto."
                )
                print(
                    "Los partidos terminados NO "
                    "se volverán a procesar."
                )
                print("=" * 72)

                try:
                    os.killpg(
                        os.getpgid(proceso.pid),
                        signal.SIGTERM,
                    )
                    proceso.wait(timeout=10)

                except Exception:
                    try:
                        os.killpg(
                            os.getpgid(proceso.pid),
                            signal.SIGKILL,
                        )
                    except Exception:
                        pass

                return

        if (
            codigo == 0
            and completo(mid)
        ):
            print(
                ">>> COMPLETADO:",
                mid,
            )

        else:
            print(
                ">>> ERROR/PENDIENTE:",
                mid,
            )
            errores.append(mid)

        completados_actuales = sum(
            completo(x)
            for x in ids
        )

        print(
            ">>> AVANCE:",
            f"{completados_actuales}/{len(ids)}",
            f"({completados_actuales / len(ids) * 100:.1f}%)"
        )

        time.sleep(5)

    ERRORES.write_text(
        "".join(
            f"{mid}\n"
            for mid in errores
        ),
        encoding="utf-8",
    )

    total_ok = sum(
        completo(mid)
        for mid in ids
    )

    print()
    print("=" * 72)
    print("RESUMEN FINAL")
    print("=" * 72)
    print(
        "COMPLETADOS:",
        total_ok,
        "/",
        len(ids),
    )
    print(
        "PENDIENTES :",
        len(ids) - total_ok,
    )
    print(
        "ERRORES    :",
        len(errores),
    )


if __name__ == "__main__":
    main()
