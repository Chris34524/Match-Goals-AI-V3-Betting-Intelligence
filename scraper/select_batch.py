import argparse
import json
from collections import Counter
from pathlib import Path


ENTRADA = Path(
    "data/partidos_candidatos.json"
)

SALIDA = Path(
    "data/lote_analisis.json"
)


def argumentos():
    parser = argparse.ArgumentParser(
        description=(
            "Selecciona un lote controlado "
            "de partidos para enriquecimiento."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Cantidad máxima de partidos.",
    )

    parser.add_argument(
        "--offset-day",
        type=int,
        default=None,
        help=(
            "Filtra por offset de día. "
            "0=hoy, 1=mañana, etc."
        ),
    )

    parser.add_argument(
        "--country",
        type=str,
        default=None,
        help="Filtra por país.",
    )

    parser.add_argument(
        "--competition",
        type=str,
        default=None,
        help=(
            "Texto contenido en "
            "el nombre de competición."
        ),
    )

    args = parser.parse_args()

    if args.limit < 1:
        parser.error(
            "--limit debe ser >= 1"
        )

    return args


def normalizar(texto):
    return (
        str(texto or "")
        .strip()
        .casefold()
    )


def cargar():
    if not ENTRADA.exists():
        raise FileNotFoundError(
            f"No existe {ENTRADA}"
        )

    with ENTRADA.open(
        encoding="utf-8"
    ) as archivo:
        datos = json.load(
            archivo
        )

    candidatos = datos.get(
        "candidatos",
        [],
    )

    return datos, candidatos


def cumple_filtros(
    partido,
    args,
):
    if (
        args.offset_day is not None
        and partido.get("offset_dia")
        != args.offset_day
    ):
        return False

    if args.country:
        if (
            normalizar(
                partido.get("pais")
            )
            != normalizar(
                args.country
            )
        ):
            return False

    if args.competition:
        buscado = normalizar(
            args.competition
        )

        competicion = normalizar(
            partido.get(
                "competicion"
            )
        )

        if buscado not in competicion:
            return False

    return True


def main():
    args = argumentos()

    metadata, candidatos = cargar()

    filtrados = [
        partido
        for partido in candidatos
        if cumple_filtros(
            partido,
            args,
        )
    ]

    # Orden cronológico.
    filtrados.sort(
        key=lambda p: (
            p.get("fecha", ""),
            p.get("hora", ""),
            p.get("pais", ""),
            p.get("competicion", ""),
        )
    )

    lote = filtrados[
        :args.limit
    ]

    salida = {
        "origen": str(
            ENTRADA
        ),
        "filtros": {
            "limit": args.limit,
            "offset_day": (
                args.offset_day
            ),
            "country": (
                args.country
            ),
            "competition": (
                args.competition
            ),
        },
        "candidatos_disponibles": len(
            candidatos
        ),
        "coincidencias_filtro": len(
            filtrados
        ),
        "total_lote": len(
            lote
        ),
        "partidos": lote,
    }

    SALIDA.write_text(
        json.dumps(
            salida,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 70)
    print("LOTE DE ANÁLISIS")
    print("=" * 70)

    print(
        "Candidatos disponibles:",
        len(candidatos),
    )

    print(
        "Coincidencias:",
        len(filtrados),
    )

    print(
        "Seleccionados:",
        len(lote),
    )

    print()

    for numero, partido in enumerate(
        lote,
        start=1,
    ):
        print(
            f"{numero:>2}. "
            f"{partido.get('fecha')} "
            f"{partido.get('hora')} | "
            f"{partido.get('pais')} | "
            f"{partido.get('competicion')} | "
            f"{partido.get('local')} "
            f"vs "
            f"{partido.get('visitante')} | "
            f"{partido.get('id')}"
        )

    print()

    print(
        "Guardado en:",
        SALIDA,
    )

    print()

    conteo = Counter(
        p.get("pais")
        for p in lote
    )

    print(
        "Países del lote:",
        dict(conteo),
    )


if __name__ == "__main__":
    main()
