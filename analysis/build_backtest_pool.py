import argparse
import json
import random
from collections import Counter
from datetime import datetime
from pathlib import Path


MATCHES_DIR = Path("data/matches")
OUTPUT = Path("data/backtest_pool.json")
OUTPUT_IDS = Path("data/backtest_pool.txt")


def cargar_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_fecha(valor):
    if not valor:
        return None

    texto = str(valor).strip()

    formatos = (
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d.%m.%y",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y-%m-%d %H:%M",
        "%d.%m.%Y %H:%M",
        "%d.%m.%y %H:%M",
    )

    for formato in formatos:
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(
            texto.replace("Z", "+00:00")
        ).replace(tzinfo=None)
    except Exception:
        return None


def filas_history(history):
    for seccion in history.get("secciones", []):
        tipo = (
            seccion.get("tipo_estimado")
            or seccion.get("tipo")
            or "desconocida"
        )

        for p in seccion.get("partidos", []):
            yield tipo, p


def normalizar(tipo, p, origen):
    mid = (
        p.get("match_id")
        or p.get("id")
        or p.get("flashscore_id")
    )

    if not mid:
        return None

    url = p.get("url")

    # El pipeline histórico necesita poder abrir
    # directamente la página del partido.
    if not url:
        return None

    fecha = parse_fecha(
        p.get("fecha") or p.get("date")
    )

    if not fecha:
        return None

    gl = p.get("goles_local")
    gv = p.get("goles_visitante")

    try:
        gl = int(gl)
        gv = int(gv)
    except Exception:
        return None

    return {
        "id": str(mid),
        "match_id": str(mid),
        "url": url,
        "fecha": fecha.strftime("%Y-%m-%d"),
        "timestamp": fecha.timestamp(),
        "local": p.get("local"),
        "visitante": p.get("visitante"),
        "goles_local": gl,
        "goles_visitante": gv,
        "competicion": (
            p.get("competicion")
            or "DESCONOCIDA"
        ),
        "codigo_competicion": (
            p.get("competicion_codigo")
            or p.get("codigo_competicion")
        ),
        "tipo_origen": tipo,
        "origen": origen,
    }


def recolectar(min_fecha=None, max_fecha=None):
    candidatos = {}

    for history_path in MATCHES_DIR.glob("*/history.json"):
        history = cargar_json(history_path)

        if not history:
            continue

        origen = (
            history.get("match_id")
            or history_path.parent.name
        )

        for tipo, p in filas_history(history):
            item = normalizar(
                tipo,
                p,
                origen,
            )

            if not item:
                continue

            fecha = datetime.strptime(
                item["fecha"],
                "%Y-%m-%d",
            ).date()

            if min_fecha and fecha < min_fecha:
                continue

            if max_fecha and fecha > max_fecha:
                continue

            mid = item["match_id"]

            if mid not in candidatos:
                candidatos[mid] = item

    return list(candidatos.values())


def seleccionar(
    candidatos,
    target,
    seed,
    max_comp,
):
    rng = random.Random(seed)

    candidatos = candidatos[:]
    rng.shuffle(candidatos)

    seleccion = []
    usados = set()
    por_comp = Counter()

    # Primera pasada respetando máximo por competición.
    for p in candidatos:
        if len(seleccion) >= target:
            break

        mid = p["match_id"]

        if mid in usados:
            continue

        comp = p["competicion"]

        if (
            max_comp > 0
            and por_comp[comp] >= max_comp
        ):
            continue

        seleccion.append(p)
        usados.add(mid)
        por_comp[comp] += 1

    # Si el límite impide completar el target,
    # rellenamos con candidatos restantes.
    if len(seleccion) < target:
        for p in candidatos:
            if len(seleccion) >= target:
                break

            mid = p["match_id"]

            if mid in usados:
                continue

            seleccion.append(p)
            usados.add(mid)

    seleccion.sort(
        key=lambda x: x["timestamp"]
    )

    return seleccion


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--target",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=20261009,
    )

    parser.add_argument(
        "--max-per-competition",
        type=int,
        default=10,
    )

    parser.add_argument(
        "--min-date",
        default=None,
        help="Fecha mínima YYYY-MM-DD",
    )

    parser.add_argument(
        "--max-date",
        default=None,
        help="Fecha máxima YYYY-MM-DD",
    )

    args = parser.parse_args()

    if args.target < 1:
        parser.error("--target debe ser >= 1")

    min_fecha = (
        datetime.strptime(
            args.min_date,
            "%Y-%m-%d",
        ).date()
        if args.min_date
        else None
    )

    max_fecha = (
        datetime.strptime(
            args.max_date,
            "%Y-%m-%d",
        ).date()
        if args.max_date
        else None
    )

    candidatos = recolectar(
        min_fecha=min_fecha,
        max_fecha=max_fecha,
    )

    print("=" * 72)
    print("BACKTEST HISTORICAL POOL")
    print("=" * 72)

    print(
        "RANGO:",
        args.min_date or "sin mínimo",
        "→",
        args.max_date or "sin máximo",
    )

    print(
        "CANDIDATOS ÚNICOS:",
        len(candidatos),
    )

    if not candidatos:
        raise SystemExit(
            "No hay candidatos para ese rango."
        )

    seleccion = seleccionar(
        candidatos,
        args.target,
        args.seed,
        args.max_per_competition,
    )

    salida = {
        "generado": datetime.now().isoformat(
            timespec="seconds"
        ),
        "seed": args.seed,
        "min_date": args.min_date,
        "max_date": args.max_date,
        "target": args.target,
        "candidatos_disponibles": len(candidatos),
        "numero_seleccionados": len(seleccion),
        "partidos": seleccion,
    }

    OUTPUT.write_text(
        json.dumps(
            salida,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    OUTPUT_IDS.write_text(
        "".join(
            f"{p['match_id']}\n"
            for p in seleccion
        ),
        encoding="utf-8",
    )

    por_comp = Counter(
        p["competicion"]
        for p in seleccion
    )

    print(
        "SELECCIONADOS:",
        len(seleccion),
    )

    print()
    print("TOP COMPETICIONES:")

    for comp, n in por_comp.most_common(20):
        print(
            f"{n:>4}  {comp}"
        )

    print()
    print("ARCHIVO:", OUTPUT)
    print("IDS    :", OUTPUT_IDS)


if __name__ == "__main__":
    main()
