from datetime import datetime


def parsear_fecha_objetivo(valor):
    if not valor:
        return None

    try:
        return datetime.strptime(
            valor,
            "%Y-%m-%d",
        ).date()
    except (TypeError, ValueError):
        return None


def parsear_fecha_historica(valor):
    if not valor:
        return None

    try:
        return datetime.strptime(
            valor,
            "%d.%m.%y",
        ).date()
    except (TypeError, ValueError):
        return None


def filtrar_prepartido(
    partidos,
    match_id_objetivo,
    fecha_objetivo,
):
    """
    Conserva únicamente partidos estrictamente
    anteriores al partido objetivo.

    Reglas:
      1. excluye el propio match_id objetivo;
      2. excluye mismo día;
      3. excluye partidos futuros;
      4. excluye fechas no interpretables.

    Devuelve:
      (partidos_validos, control)
    """

    fecha_obj = parsear_fecha_objetivo(
        fecha_objetivo
    )

    if fecha_obj is None:
        raise ValueError(
            "Fecha objetivo inválida o ausente: "
            f"{fecha_objetivo!r}"
        )

    validos = []

    control = {
        "entrada": len(partidos),
        "validos": 0,
        "objetivo_excluido": 0,
        "mismo_dia_excluidos": 0,
        "futuros_excluidos": 0,
        "sin_fecha_excluidos": 0,
    }

    for partido in partidos:
        if (
            partido.get("match_id")
            == match_id_objetivo
        ):
            control[
                "objetivo_excluido"
            ] += 1
            continue

        fecha = parsear_fecha_historica(
            partido.get("fecha")
        )

        if fecha is None:
            control[
                "sin_fecha_excluidos"
            ] += 1
            continue

        if fecha == fecha_obj:
            control[
                "mismo_dia_excluidos"
            ] += 1
            continue

        if fecha > fecha_obj:
            control[
                "futuros_excluidos"
            ] += 1
            continue

        validos.append(partido)

    control["validos"] = len(validos)

    return validos, control
