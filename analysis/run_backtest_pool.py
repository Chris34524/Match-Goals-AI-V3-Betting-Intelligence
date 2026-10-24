import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


LISTA = Path("data/backtest_pool.txt")
MATCHES = Path("data/matches")
LOGS = Path("data/backtest_pool_logs")
ERRORES = Path("data/backtest_pool_errors.txt")


def cargar_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def analisis_valido(mid):
    carpeta = MATCHES / mid

    result = cargar_json(carpeta / "result.json")
    lambdas = cargar_json(carpeta / "lambda_comparison.json")

    if not result or not lambdas:
        return False

    integridad = (
        result
        .get("integridad_temporal", {})
        .get("estado")
    )

    metodos = lambdas.get("metodos", lambdas)

    return (
        integridad == "OK"
        and "J_BT_sin_temporada" in metodos
    )


def backtest_valido(mid):
    path = MATCHES / mid / "backtest.json"

    if not path.exists():
        return False

    d = cargar_json(path)

    return bool(d)


def ejecutar(comando, log):
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
            print(linea, end="", flush=True)
            log.write(linea)
            log.flush()

        return proceso.wait()

    except KeyboardInterrupt:
        print()
        print("DETENIENDO PROCESO ACTUAL...")

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

        raise


def procesar(mid, log):
    if not analisis_valido(mid):
        print()
        print(">>> PREPARANDO TARGET HISTÓRICO")

        codigo = ejecutar(
            [
                sys.executable,
                "-u",
                "-m",
                "analysis.run_match",
                "--match-id",
                mid,
                "--prepare",
            ],
            log,
        )

        if codigo != 0:
            return False

        if not analisis_valido(mid):
            print(
                ">>> El análisis terminó pero "
                "no pasó validación temporal."
            )
            return False

    else:
        print(
            ">>> Análisis existente y válido; "
            "se reutiliza."
        )

    if backtest_valido(mid):
        print(
            ">>> Backtest existente; "
            "se reutiliza."
        )
        return True

    print()
    print(">>> CALCULANDO BACKTEST")

    codigo = ejecutar(
        [
            sys.executable,
            "-u",
            "-m",
            "analysis.backtest",
            "--match-id",
            mid,
        ],
        log,
    )

    return (
        codigo == 0
        and backtest_valido(mid)
    )


def main():
    if not LISTA.exists():
        raise SystemExit(
            "No existe data/backtest_pool.txt"
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
            "data/backtest_pool.txt está vacío"
        )

    LOGS.mkdir(
        parents=True,
        exist_ok=True,
    )

    completados = [
        mid
        for mid in ids
        if backtest_valido(mid)
    ]

    pendientes = [
        mid
        for mid in ids
        if not backtest_valido(mid)
    ]

    print("=" * 72)
    print("BACKTEST POOL REANUDABLE")
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

    errores = []

    try:
        for numero, mid in enumerate(
            pendientes,
            start=1,
        ):
            print()
            print("=" * 72)
            print(
                f"[{numero}/{len(pendientes)}] "
                f"{mid}"
            )
            print("=" * 72)

            log_path = LOGS / f"{mid}.log"

            with log_path.open(
                "a",
                encoding="utf-8",
            ) as log:

                ok = procesar(
                    mid,
                    log,
                )

            if ok:
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

            ok_total = sum(
                backtest_valido(x)
                for x in ids
            )

            print(
                ">>> AVANCE:",
                f"{ok_total}/{len(ids)}",
                f"({ok_total / len(ids) * 100:.1f}%)"
            )

            time.sleep(5)

    except KeyboardInterrupt:
        print()
        print("=" * 72)
        print("BACKTEST PAUSADO")
        print(
            "Puedes ejecutar el mismo comando "
            "para continuar."
        )
        print("=" * 72)

    finally:
        ERRORES.write_text(
            "".join(
                f"{mid}\n"
                for mid in errores
            ),
            encoding="utf-8",
        )

        ok_total = sum(
            backtest_valido(x)
            for x in ids
        )

        print()
        print("=" * 72)
        print("ESTADO")
        print("=" * 72)
        print(
            "COMPLETADOS:",
            ok_total,
            "/",
            len(ids),
        )
        print(
            "PENDIENTES :",
            len(ids) - ok_total,
        )


if __name__ == "__main__":
    main()
