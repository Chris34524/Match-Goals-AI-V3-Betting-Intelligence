import argparse
import json
from pathlib import Path


ENTRADA = Path("data/partidos.json")
SALIDA = Path("data/backtest_candidates.json")

LIGAS = [
    ("ALEMANIA", "Bundesliga"),
    ("ESPAÑA", "LaLiga EA Sports"),
    ("FRANCIA", "Ligue 1"),
    ("INGLATERRA", "Premier League"),
    ("ITALIA", "Serie A"),
    ("ESTADOS UNIDOS", "MLS"),
    ("INGLATERRA", "Championship"),
    ("JAPÓN", "J1 League"),
    ("PAÍSES BAJOS", "Eredivisie"),
    ("PORTUGAL", "Liga Portugal"),
]


def terminado(p):
    try:
        int(p.get("gol_local"))
        int(p.get("gol_visitante"))
        return True
    except (TypeError, ValueError):
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--por-liga", type=int, default=2)
    parser.add_argument("--fecha", default="2026-09-19")
    args = parser.parse_args()

    with ENTRADA.open(encoding="utf-8") as f:
        datos = json.load(f)

    partidos = (
        datos.get("partidos", [])
        if isinstance(datos, dict)
        else datos
    )

    seleccion = []

    for pais, competicion in LIGAS:
        candidatos = [
            p for p in partidos
            if p.get("fecha") == args.fecha
            and p.get("pais") == pais
            and p.get("competicion") == competicion
            and terminado(p)
            and p.get("id")
        ]

        # Tomamos los primeros N dentro de cada liga.
        # No utilizamos el marcador para ordenar o seleccionar.
        elegidos = candidatos[:args.por_liga]

        for p in elegidos:
            seleccion.append({
                "match_id": p["id"],
                "fecha": p["fecha"],
                "pais": p.get("pais"),
                "competicion": p.get("competicion"),
                "local": p.get("local"),
                "visitante": p.get("visitante"),
                "gol_local": int(p["gol_local"]),
                "gol_visitante": int(p["gol_visitante"]),
                "url": p.get("url"),
            })

    salida = {
        "fecha": args.fecha,
        "por_liga": args.por_liga,
        "seleccionados": len(seleccion),
        "partidos": seleccion,
    }

    with SALIDA.open("w", encoding="utf-8") as f:
        json.dump(
            salida,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Seleccionados: {len(seleccion)}")
    print()

    for i, p in enumerate(seleccion, 1):
        print(
            f"{i:>2}. {p['match_id']} | "
            f"{p['pais']} | "
            f"{p['competicion']} | "
            f"{p['local']} - {p['visitante']}"
        )

    print()
    print("Guardado:", SALIDA)


if __name__ == "__main__":
    main()
