import argparse
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATCHES = ROOT / "data" / "matches"


def cargar(path):
    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return None


def mid(p):
    return (
        p.get("match_id")
        or p.get("id")
        or p.get("flashscore_id")
    )


def buscar_clave_recursiva(obj, clave):
    if isinstance(obj, dict):
        if clave in obj:
            return obj[clave]

        for v in obj.values():
            r = buscar_clave_recursiva(
                v,
                clave,
            )

            if r is not None:
                return r

    elif isinstance(obj, list):
        for v in obj:
            r = buscar_clave_recursiva(
                v,
                clave,
            )

            if r is not None:
                return r

    return None


def numero(v):
    try:
        v = float(v)

        if math.isfinite(v):
            return v

    except Exception:
        pass

    return None


def extraer_lambda_bt0(carpeta):
    # --------------------------------------------------------
    # FUENTE PRINCIPAL:
    # lambda_comparison.json / J_BT_sin_temporada
    # --------------------------------------------------------

    comp = cargar(
        carpeta / "lambda_comparison.json"
    )

    if comp:
        metodo = buscar_clave_recursiva(
            comp,
            "J_BT_sin_temporada",
        )

        if isinstance(metodo, dict):
            lh = numero(
                metodo.get("local")
            )

            la = numero(
                metodo.get("visitante")
            )

            if lh is not None and la is not None:
                return (
                    lh,
                    la,
                    "lambda_comparison:J_BT_sin_temporada",
                )

    # --------------------------------------------------------
    # FALLBACK:
    # confidence_v2 -> detalle_v1 -> lambda_base
    # Este lambda_base también corresponde al BT0.
    # --------------------------------------------------------

    conf = cargar(
        carpeta / "confidence_v2.json"
    )

    if conf:
        base = (
            conf.get("detalle_v1", {})
            .get("lambda_base", {})
        )

        lh = numero(
            base.get("local")
        )

        la = numero(
            base.get("visitante")
        )

        if lh is not None and la is not None:
            return (
                lh,
                la,
                "confidence_v2:lambda_base",
            )

    return None, None, None


def poisson_total(lam):
    p0 = math.exp(-lam)
    p1 = p0 * lam
    p2 = p1 * lam / 2
    p3 = p2 * lam / 3

    return {
        "+1.5": (
            1 - (p0 + p1)
        ),
        "+2.5": (
            1 - (p0 + p1 + p2)
        ),
        "+3.5": (
            1 - (
                p0 + p1 + p2 + p3
            )
        ),
    }


def prob_1x2(lh, la):
    max_goles = 35

    def dist(lam):
        p = [
            math.exp(-lam)
        ]

        for k in range(
            1,
            max_goles + 1,
        ):
            p.append(
                p[-1]
                * lam
                / k
            )

        return p

    home = dist(lh)
    away = dist(la)

    p1 = 0.0
    px = 0.0
    p2 = 0.0

    for i, pi in enumerate(home):
        for j, pj in enumerate(away):
            q = pi * pj

            if i > j:
                p1 += q

            elif i == j:
                px += q

            else:
                p2 += q

    total = p1 + px + p2

    return (
        p1 / total,
        px / total,
        p2 / total,
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--file",
        required=True,
    )

    parser.add_argument(
        "--output",
        default=(
            "data/"
            "selected_predictions_v2.json"
        ),
    )

    args = parser.parse_args()

    source = ROOT / args.file
    output = ROOT / args.output

    datos = cargar(source)

    if not datos:
        raise SystemExit(
            f"No pude leer {source}"
        )

    partidos = datos.get(
        "partidos",
        [],
    )

    salida = []

    print("=" * 92)
    print("CONSTRUYENDO DATASET BT0 SELECCIONADO")
    print("=" * 92)

    for p in partidos:
        x = dict(p)

        partido_id = mid(x)

        if not partido_id:
            continue

        carpeta = (
            MATCHES / partido_id
        )

        conf = cargar(
            carpeta
            / "confidence_v2.json"
        )

        lh, la, fuente = (
            extraer_lambda_bt0(
                carpeta
            )
        )

        print()
        print(
            partido_id,
            "|",
            x.get("local"),
            "vs",
            x.get("visitante"),
        )

        if lh is None or la is None:
            print(
                "  ERROR: BT0 λ no disponible"
            )

            x["lambda_local"] = None
            x["lambda_visitante"] = None
            x["lambda_total"] = None

            x["+1.5"] = None
            x["+2.5"] = None
            x["+3.5"] = None
            x["BTTS"] = None

        else:
            lt = lh + la

            overs = poisson_total(
                lt
            )

            btts = (
                (1 - math.exp(-lh))
                * (1 - math.exp(-la))
            )

            p1, px, p2 = prob_1x2(
                lh,
                la,
            )

            x["lambda_local"] = lh
            x["lambda_visitante"] = la
            x["lambda_total"] = lt

            x["+1.5"] = (
                overs["+1.5"]
            )

            x["+2.5"] = (
                overs["+2.5"]
            )

            x["+3.5"] = (
                overs["+3.5"]
            )

            x["BTTS"] = btts

            x["prob_1"] = p1
            x["prob_X"] = px
            x["prob_2"] = p2

            x["modelo_lambda"] = (
                "J_BT_sin_temporada"
            )

            x["fuente_lambda"] = (
                fuente
            )

            print(
                "  λ:",
                f"{lh:.3f}",
                "+",
                f"{la:.3f}",
                "=",
                f"{lt:.3f}",
            )

            print(
                "  1.5+:",
                f"{overs['+1.5']:.1%}",
                "| 2.5+:",
                f"{overs['+2.5']:.1%}",
                "| 3.5+:",
                f"{overs['+3.5']:.1%}",
            )

            print(
                "  BTTS:",
                f"{btts:.1%}",
            )

            print(
                "  1/X/2:",
                f"{p1:.1%}",
                "/",
                f"{px:.1%}",
                "/",
                f"{p2:.1%}",
            )

            print(
                "  Fuente:",
                fuente,
            )

        if conf:
            x["confidence_v2"] = conf

            x["calidad_datos"] = (
                conf.get(
                    "calidad_datos_global",
                    "N/D",
                )
            )

            x["confianza_btts"] = (
                conf
                .get(
                    "mercados",
                    {},
                )
                .get(
                    "BTTS",
                    {},
                )
                .get(
                    "confianza_predictiva",
                    "N/D",
                )
            )

            detalle = conf.get(
                "detalle_v1",
                {},
            )

            x["score_calidad"] = (
                detalle.get("score")
            )

            x["alertas_calidad"] = (
                detalle.get(
                    "alertas",
                    [],
                )
            )

        salida.append(x)

    output.write_text(
        json.dumps(
            {
                "source": str(source),
                "modelo": (
                    "J_BT_sin_temporada"
                ),
                "total": len(salida),
                "partidos": salida,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 92)
    print(
        "PARTIDOS:",
        len(salida),
    )
    print(
        "SALIDA:",
        output,
    )
    print("=" * 92)


if __name__ == "__main__":
    main()
