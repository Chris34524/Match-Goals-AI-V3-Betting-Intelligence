import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "report_day_v2.html"


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
    print()

    subprocess.run(
        cmd,
        cwd=ROOT,
        check=True,
    )


def abrir_reporte():
    if not REPORT.exists():
        print(
            "No existe:",
            REPORT,
        )
        return

    try:
        r = subprocess.run(
            [
                "wslpath",
                "-w",
                str(REPORT),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        ruta_win = r.stdout.strip()

        subprocess.Popen(
            [
                "explorer.exe",
                ruta_win,
            ]
        )

        print(
            "Reporte abierto:",
            REPORT,
        )

    except Exception as e:
        print(
            "No pude abrir automáticamente "
            "el HTML:",
            repr(e),
        )

        print(
            "Ruta:",
            REPORT,
        )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Pipeline diario Match Goals AI V2"
        )
    )

    parser.add_argument(
        "--days",
        type=int,
        default=2,
    )

    parser.add_argument(
        "--hours",
        type=int,
        default=4,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=30,
    )

    parser.add_argument(
        "--max-per-competition",
        type=int,
        default=0,
    )

    parser.add_argument(
        "--grace-minutes",
        type=int,
        default=0,
    )

    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help=(
            "No vuelve a ejecutar "
            "scraper.flashscore."
        ),
    )

    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help=(
            "No vuelve a ejecutar run_day; "
            "sólo genera reporte V2."
        ),
    )

    parser.add_argument(
        "--open",
        action="store_true",
        help="Abre el HTML al terminar.",
    )

    args = parser.parse_args()

    print("=" * 100)
    print("MATCH GOALS AI — DAILY V2")
    print("=" * 100)

    if not args.skip_scrape:
        ejecutar(
            "scraper.flashscore",
            [
                "--days",
                str(args.days),
            ],
        )

        ejecutar(
            "scraper.filter_matches",
            [
                "--grace-minutes",
                str(args.grace_minutes),
            ],
        )

    if not args.skip_analysis:
        ejecutar(
            "analysis.run_day",
            [
                "--hours",
                str(args.hours),
                "--limit",
                str(args.limit),
                "--max-per-competition",
                str(
                    args.max_per_competition
                ),
                "--skip-slate-refresh",
            ],
        )

    ejecutar(
        "analysis.report_day_v2"
    )

    print()
    print("=" * 100)
    print("DAILY V2 COMPLETADO")
    print("=" * 100)

    print(
        "JSON :",
        ROOT
        / "data"
        / "day_predictions_v2.json",
    )

    print(
        "HTML :",
        REPORT,
    )

    if args.open:
        abrir_reporte()


if __name__ == "__main__":
    main()
