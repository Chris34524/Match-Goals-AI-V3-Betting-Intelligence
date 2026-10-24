import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "data" / "Match_Goals_AI_Seleccion_Actual.html"


def main():
    if not HTML.exists():
        raise SystemExit(
            f"No existe: {HTML}"
        )

    r = subprocess.run(
        [
            "wslpath",
            "-w",
            str(HTML),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    winfile = r.stdout.strip()

    subprocess.Popen(
        [
            "cmd.exe",
            "/C",
            "start",
            "",
            winfile,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print("Reporte abierto:")
    print(HTML)


if __name__ == "__main__":
    main()
