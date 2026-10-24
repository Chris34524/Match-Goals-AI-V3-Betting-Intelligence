import argparse
import json
import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "data" / "evaluation"

CUMULATIVE = (
    EVAL / "effectiveness_cumulative.json"
)

BASELINE = {
    "+1.5": 0.1752,
    "-1.5": 0.1752,

    "+2.5": 0.2425,
    "-2.5": 0.2425,

    "+3.5": 0.2193,
    "-3.5": 0.2193,

    "BTTS": 0.2575,
}


def num(v):
    try:
        x = float(v)

        if math.isfinite(x):
            return x

    except Exception:
        pass

    return None


def clamp(x, lo, hi):
    return max(
        lo,
        min(hi, x),
    )


def segmento(
    competicion,
    local="",
    visitante="",
):
    texto = " ".join(
        [
            str(competicion or ""),
            str(local or ""),
            str(visitante or ""),
        ]
    ).lower()

    juvenil = bool(
        re.search(
            r"\bsub[- ]?\d+\b"
            r"|\bu[- ]?\d+\b"
            r"|under[- ]?\d+",
            texto,
        )
    )

    femenil = any(
        x in texto
        for x in (
            "femenil",
            "femenina",
            "women",
            " wfc",
            " femenino",
        )
    )

    if juvenil and femenil:
        return "JUVENIL_FEMENIL"

    if juvenil:
        return "JUVENIL"

    if femenil:
        return "FEMENIL"

    if any(
        x in texto
        for x in (
            "kings league",
            "queens league",
        )
    ):
        return "NO_CONVENCIONAL"

    if any(
        x in texto
        for x in (
            "amistoso",
            "friendly",
        )
    ):
        return "AMISTOSO"

    if any(
        x in texto
        for x in (
            "(am)",
            " amateur",
            "reserva",
            "reserve",
            "reserves",
        )
    ):
        return "RESERVA_AMATEUR"

    return "SENIOR_CONVENCIONAL"


def cargar_evaluacion():
    if not CUMULATIVE.exists():
        return {}

    try:
        return json.loads(
            CUMULATIVE.read_text(
                encoding="utf-8"
            )
        )

    except Exception:
        return {}


def clave_metrica(mercado):
    if mercado in (
        "BTTS_SI",
        "BTTS_NO",
    ):
        return "BTTS"

    return mercado


def fallback_metrica(mercado):
    equivalencias = {
        "-1.5": "+1.5",
        "-2.5": "+2.5",
        "-3.5": "+3.5",
    }

    return equivalencias.get(
        mercado
    )


def buscar_metrica(
    metricas,
    mercado,
):
    k = clave_metrica(
        mercado
    )

    m = metricas.get(k)

    if isinstance(m, dict):
        return m

    fb = fallback_metrica(k)

    if fb:
        m = metricas.get(fb)

        if isinstance(m, dict):
            return m

    return {}


def seleccionar_metrica(
    evaluacion,
    seg,
    mercado,
):
    # --------------------------------------------------------
    # Preferimos el segmento sólo si tiene suficiente muestra.
    # Si no, usamos la evaluación global acumulada.
    # --------------------------------------------------------

    segmentos = evaluacion.get(
        "segmentos",
        {}
    )

    bloque_seg = segmentos.get(
        seg,
        {}
    )

    metrica_seg = buscar_metrica(
        bloque_seg.get(
            "metricas",
            {},
        ),
        mercado,
    )

    n_seg = int(
        metrica_seg.get("n", 0)
        or 0
    )

    if n_seg >= 50:
        return (
            metrica_seg,
            f"SEGMENTO:{seg}",
        )

    globales = evaluacion.get(
        "metricas",
        {}
    )

    metrica_global = buscar_metrica(
        globales,
        mercado,
    )

    if metrica_global:
        return (
            metrica_global,
            "GLOBAL_ACUMULADO",
        )

    return (
        {},
        "SIN_HISTORIAL",
    )


def calidad_factor(calidad):
    q = str(
        calidad or ""
    ).upper()

    if q == "ALTA":
        return 1.00

    if q == "MEDIA":
        return 0.97

    if q == "BAJA":
        return 0.90

    return 0.93


def diagnostico_confiabilidad(
    mercado,
    metrica,
):
    n = int(
        metrica.get("n", 0)
        or 0
    )

    brier = num(
        metrica.get("brier")
    )

    pm = num(
        metrica.get(
            "prob_media"
        )
    )

    real = num(
        metrica.get(
            "frecuencia_real"
        )
    )

    k = clave_metrica(
        mercado
    )

    referencia = (
        num(
            metrica.get(
                "baseline_brier"
            )
        )
        or BASELINE.get(k)
        or BASELINE.get(
            fallback_metrica(k)
            or ""
        )
    )

    # --------------------------------------------------------
    # 1) Calidad Brier
    #
    # referencia / brier_actual
    #
    # Si actual < referencia => factor > 1
    # Si actual > referencia => factor < 1
    # Limitamos el efecto para evitar sobreajuste.
    # --------------------------------------------------------

    if (
        brier is not None
        and referencia is not None
        and brier > 0
    ):
        factor_brier = clamp(
            referencia / brier,
            0.85,
            1.10,
        )
    else:
        factor_brier = 0.95

    # --------------------------------------------------------
    # 2) Calibración
    #
    # sesgo = P_media - frecuencia_real
    #
    # Cuanto más cerca de cero, mejor.
    # --------------------------------------------------------

    if (
        pm is not None
        and real is not None
    ):
        sesgo = pm - real
        gap = abs(sesgo)

        factor_cal = clamp(
            1 - 1.5 * gap,
            0.85,
            1.00,
        )

    else:
        sesgo = None
        gap = None
        factor_cal = 0.95

    # --------------------------------------------------------
    # 3) Tamaño de muestra
    #
    # N=0    -> 0.90
    # N=100  -> 0.95
    # N>=200 -> 1.00
    # --------------------------------------------------------

    factor_muestra = (
        0.90
        + 0.10
        * min(
            1.0,
            n / 200.0,
        )
    )

    # --------------------------------------------------------
    # Confiabilidad total
    # --------------------------------------------------------

    confiabilidad = clamp(
        factor_brier
        * factor_cal
        * factor_muestra,
        0.80,
        1.10,
    )

    return {
        "n": n,
        "brier": brier,
        "brier_referencia": referencia,
        "factor_brier": factor_brier,

        "prob_media_historica": pm,
        "frecuencia_real": real,

        "sesgo_calibracion": sesgo,
        "gap_calibracion": gap,
        "factor_calibracion": factor_cal,

        "factor_muestra": factor_muestra,

        "confiabilidad": confiabilidad,
    }


def nivel(
    prob,
    score,
    diagnostico,
    calidad,
):
    n = diagnostico["n"]

    rel = diagnostico[
        "confiabilidad"
    ]

    qf = calidad_factor(
        calidad
    )

    # --------------------------------------------------------
    # FUERTE:
    # - probabilidad alta
    # - score ajustado alto
    # - historial suficiente
    # - datos altos/medios
    # --------------------------------------------------------

    if (
        prob >= 0.70
        and score >= 0.66
        and rel >= 0.95
        and qf >= 0.97
        and n >= 50
    ):
        return "FUERTE"

    if (
        prob >= 0.62
        and score >= 0.57
        and rel >= 0.90
        and n >= 30
    ):
        return "MEDIA"

    if (
        prob >= 0.55
        and score >= 0.50
    ):
        return "DÉBIL"

    return "SIN SEÑAL"


def candidato(
    nombre,
    prob,
    evaluacion,
    seg,
    calidad,
):
    if prob is None:
        return None

    metrica, fuente = (
        seleccionar_metrica(
            evaluacion,
            seg,
            nombre,
        )
    )

    diag = diagnostico_confiabilidad(
        nombre,
        metrica,
    )

    qf = calidad_factor(
        calidad
    )

    # --------------------------------------------------------
    # SCORE DE DECISIÓN
    #
    # Probabilidad pura
    # x confiabilidad histórica
    # x calidad de datos del partido
    #
    # IMPORTANTE:
    # NO es una probabilidad.
    # NO es EV.
    # Sólo sirve para ordenar opciones.
    # --------------------------------------------------------

    score = clamp(
        prob
        * diag["confiabilidad"]
        * qf,
        0.0,
        1.0,
    )

    niv = nivel(
        prob,
        score,
        diag,
        calidad,
    )

    return {
        "mercado": nombre,
        "probabilidad": prob,

        "nivel": niv,

        "score_decision": score,

        "segmento": seg,

        "fuente_calibracion": fuente,

        "calidad_datos": calidad,

        "diagnostico": diag,
    }


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--input",
        default=(
            "data/"
            "selected_predictions_v2.json"
        ),
    )

    args = ap.parse_args()

    src = ROOT / args.input

    data = json.loads(
        src.read_text(
            encoding="utf-8"
        )
    )

    evaluacion = cargar_evaluacion()

    partidos = data.get(
        "partidos",
        []
    )

    for p in partidos:

        o15 = num(
            p.get("+1.5")
        )

        o25 = num(
            p.get("+2.5")
        )

        o35 = num(
            p.get("+3.5")
        )

        btts = num(
            p.get("BTTS")
        )

        mercados = [
            (
                "+1.5",
                o15,
            ),
            (
                "+2.5",
                o25,
            ),
            (
                "+3.5",
                o35,
            ),
            (
                "-1.5",
                None
                if o15 is None
                else 1 - o15,
            ),
            (
                "-2.5",
                None
                if o25 is None
                else 1 - o25,
            ),
            (
                "-3.5",
                None
                if o35 is None
                else 1 - o35,
            ),
            (
                "BTTS_SI",
                btts,
            ),
            (
                "BTTS_NO",
                None
                if btts is None
                else 1 - btts,
            ),
        ]

        calidad = p.get(
            "calidad_datos",
            "N/D",
        )

        seg = segmento(
            p.get(
                "competicion"
                or p.get("league")
            ),
            p.get("local"),
            p.get("visitante"),
        )

        candidatos = []

        for nombre, prob in mercados:

            if (
                prob is None
                or prob < 0.55
            ):
                continue

            c = candidato(
                nombre,
                prob,
                evaluacion,
                seg,
                calidad,
            )

            if c:
                candidatos.append(c)

        candidatos.sort(
            key=lambda x: (
                x["score_decision"],
                x["probabilidad"],
            ),
            reverse=True,
        )

        principal = (
            candidatos[0]
            if candidatos
            else None
        )

        if principal is None:
            accion = "NO APUESTA"

        elif (
            principal["nivel"]
            == "FUERTE"
        ):
            accion = "SEÑAL FUERTE"

        elif (
            principal["nivel"]
            == "MEDIA"
        ):
            accion = "SEÑAL MEDIA"

        elif (
            principal["nivel"]
            == "DÉBIL"
        ):
            accion = "OBSERVAR"

        else:
            accion = "NO APUESTA"

        # ----------------------------------------------------
        # 1X2 permanece exploratorio
        # ----------------------------------------------------

        p1 = num(
            p.get("prob_1")
        )

        px = num(
            p.get("prob_X")
        )

        p2 = num(
            p.get("prob_2")
        )

        resultado = None
        doble = None

        if (
            p1 is not None
            and px is not None
            and p2 is not None
        ):
            uno_x_dos = {
                "1": p1,
                "X": px,
                "2": p2,
            }

            k = max(
                uno_x_dos,
                key=uno_x_dos.get,
            )

            resultado = {
                "resultado": k,
                "probabilidad": (
                    uno_x_dos[k]
                ),
                "confianza": (
                    "NO_VALIDADA"
                ),
            }

            dobles = {
                "1X": p1 + px,
                "X2": px + p2,
                "12": p1 + p2,
            }

            dk = max(
                dobles,
                key=dobles.get,
            )

            doble = {
                "mercado": dk,
                "probabilidad": (
                    dobles[dk]
                ),
                "confianza": (
                    "EXPLORATORIA"
                ),
            }

        p["mejores_apuestas"] = {
            "accion": accion,

            "segmento": seg,

            "principal": principal,

            "alternativas": (
                candidatos[1:3]
            ),

            "resultado_1x2": resultado,

            "doble_oportunidad": doble,

            "nota": (
                "Selección estadística sin "
                "cuotas. Score_decision no es "
                "probabilidad ni EV."
            ),
        }

    data[
        "best_bets_model"
    ] = (
        "BT0 + calibración acumulada "
        "+ segmento + calidad"
    )

    src.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 100)
    print("MEJORES OPCIONES EXPLICABLES")
    print("=" * 100)

    for p in partidos:

        b = p.get(
            "mejores_apuestas",
            {}
        )

        c = b.get(
            "principal"
        )

        print()
        print(
            p.get("local"),
            "vs",
            p.get("visitante"),
        )

        if not c:
            print(
                "  NO APUESTA"
            )
            continue

        d = c["diagnostico"]

        print(
            "  Principal:",
            c["mercado"],
            f"{c['probabilidad']:.1%}",
            c["nivel"],
        )

        print(
            "  Score:",
            f"{c['score_decision']:.1%}",
        )

        print(
            "  Brier:",
            d["brier"],
            "| Ref:",
            d["brier_referencia"],
        )

        print(
            "  N:",
            d["n"],
            "| Fuente:",
            c["fuente_calibracion"],
        )

        print(
            "  Calidad:",
            c["calidad_datos"],
        )


if __name__ == "__main__":
    main()
