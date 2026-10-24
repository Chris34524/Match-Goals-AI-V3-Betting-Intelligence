import argparse
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def esc(v):
    return html.escape(
        str(v or "")
    )


def pct(v):
    try:
        return (
            f"{float(v)*100:.1f}%"
        )
    except Exception:
        return "N/D"


def dec(v, n=4):
    try:
        return f"{float(v):.{n}f}"
    except Exception:
        return "N/D"


def diagnostico_html(c):
    if not c:
        return "—"

    d = c.get(
        "diagnostico",
        {}
    )

    sesgo = d.get(
        "sesgo_calibracion"
    )

    sesgo_txt = (
        f"{sesgo*100:+.1f} pp"
        if sesgo is not None
        else "N/D"
    )

    return f"""
    <div class="bb-diagnostic">

      <div>
        <strong>Prob. BT0:</strong>
        {pct(c.get('probabilidad'))}
      </div>

      <div>
        <strong>Score decisión:</strong>
        {pct(c.get('score_decision'))}
      </div>

      <div>
        <strong>Brier:</strong>
        {dec(d.get('brier'))}
        vs
        {dec(d.get('brier_referencia'))}
      </div>

      <div>
        <strong>Sesgo calibración:</strong>
        {sesgo_txt}
      </div>

      <div>
        <strong>Muestra:</strong>
        N={d.get('n', 0)}
      </div>

      <div>
        <strong>Fuente:</strong>
        {esc(c.get('fuente_calibracion'))}
      </div>

      <div>
        <strong>Segmento:</strong>
        {esc(c.get('segmento'))}
      </div>

      <div>
        <strong>Datos:</strong>
        {esc(c.get('calidad_datos'))}
      </div>

    </div>
    """


def pick_html(c):
    if not c:
        return "—"

    return f"""
    <div class="bb-pick">
      <div class="bb-market">
        {esc(c.get('mercado'))}
      </div>

      <div class="bb-prob">
        {pct(c.get('probabilidad'))}
      </div>

      <div class="bb-level">
        {esc(c.get('nivel'))}
      </div>
    </div>
    """


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--html",
        default=(
            "data/"
            "report_window_pro.html"
        ),
    )

    ap.add_argument(
        "--data",
        default=(
            "data/"
            "selected_predictions_v2.json"
        ),
    )

    args = ap.parse_args()

    hp = ROOT / args.html
    dp = ROOT / args.data

    doc = hp.read_text(
        encoding="utf-8"
    )

    data = json.loads(
        dp.read_text(
            encoding="utf-8"
        )
    )

    rows = []

    for p in data.get(
        "partidos",
        []
    ):

        b = p.get(
            "mejores_apuestas",
            {}
        )

        principal = b.get(
            "principal"
        )

        alternativas = b.get(
            "alternativas",
            []
        )

        r = b.get(
            "resultado_1x2"
        )

        dc = b.get(
            "doble_oportunidad"
        )

        rows.append(
            f"""
            <tr>

              <td class="bb-match">
                <strong>
                  {esc(p.get('local'))}
                  vs
                  {esc(p.get('visitante'))}
                </strong>

                <div class="bb-small">
                  {esc(
                      p.get('competicion')
                      or p.get('league')
                  )}
                </div>

                <div class="bb-small">
                  {esc(b.get('segmento'))}
                </div>
              </td>

              <td>
                {pick_html(principal)}
              </td>

              <td class="bb-why">
                {
                    diagnostico_html(
                        principal
                    )
                }
              </td>

              <td>
                {
                    pick_html(
                        alternativas[0]
                    )
                    if len(alternativas) > 0
                    else "—"
                }
              </td>

              <td>
                {
                    pick_html(
                        alternativas[1]
                    )
                    if len(alternativas) > 1
                    else "—"
                }
              </td>

              <td>
                {
                    (
                        f"<strong>"
                        f"{esc(r.get('resultado'))}"
                        f"</strong><br>"
                        f"{pct(r.get('probabilidad'))}"
                    )
                    if r
                    else "—"
                }
              </td>

              <td>
                {
                    (
                        f"<strong>"
                        f"{esc(dc.get('mercado'))}"
                        f"</strong><br>"
                        f"{pct(dc.get('probabilidad'))}"
                    )
                    if dc
                    else "—"
                }
              </td>

              <td>
                <strong>
                  {esc(b.get('accion'))}
                </strong>
              </td>

            </tr>
            """
        )

    panel = f"""
<style>

.bb-panel {{
    margin: 25px auto;
    max-width: 98%;
    padding: 22px;
    border-radius: 15px;
    background: #151d29;
    color: #f2f5f8;
}}

.bb-wrap {{
    overflow-x: auto;
}}

.bb-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}}

.bb-table th,
.bb-table td {{
    padding: 11px 9px;
    border-bottom:
        1px solid #334052;
    text-align: center;
    vertical-align: middle;
}}

.bb-table th {{
    background: #243044;
}}

.bb-match {{
    text-align: left !important;
    min-width: 230px;
}}

.bb-why {{
    min-width: 220px;
    text-align: left !important;
}}

.bb-pick {{
    min-width: 90px;
}}

.bb-market {{
    font-weight: bold;
    font-size: 15px;
}}

.bb-prob {{
    font-size: 17px;
    margin: 3px 0;
}}

.bb-level {{
    font-size: 11px;
    opacity: .78;
}}

.bb-diagnostic {{
    line-height: 1.55;
    font-size: 11px;
}}

.bb-small {{
    opacity: .67;
    font-size: 11px;
    margin-top: 3px;
}}

.bb-note {{
    opacity: .78;
    margin-bottom: 15px;
    font-size: 12px;
    line-height: 1.5;
}}

</style>

<section class="bb-panel">

<h2>
Mejores opciones estadísticas por partido
</h2>

<div class="bb-note">

<strong>Prob. BT0</strong> es la
probabilidad matemática del modelo.

<strong>Score decisión</strong>
NO es una probabilidad ni una cuota:
combina probabilidad, Brier,
calibración, tamaño de muestra y
calidad de datos para ordenar señales.

Si existe muestra suficiente del tipo
de competición se utiliza ese segmento;
de lo contrario se utiliza la
calibración global acumulada.

Sin cuotas disponibles no podemos
calcular edge ni valor esperado (EV).

</div>

<div class="bb-wrap">

<table class="bb-table">

<thead>
<tr>
<th>Partido</th>
<th>Principal</th>
<th>¿Por qué?</th>
<th>Alternativa 1</th>
<th>Alternativa 2</th>
<th>1X2 probable</th>
<th>Doble oportunidad</th>
<th>Decisión</th>
</tr>
</thead>

<tbody>
{''.join(rows)}
</tbody>

</table>

</div>
</section>
"""

    body = doc.lower().find(
        "<body"
    )

    if body == -1:
        raise SystemExit(
            "No encontré BODY."
        )

    pos = doc.find(
        ">",
        body,
    )

    if pos == -1:
        raise SystemExit(
            "BODY inválido."
        )

    pos += 1

    doc = (
        doc[:pos]
        + panel
        + doc[pos:]
    )

    hp.write_text(
        doc,
        encoding="utf-8",
    )

    print(
        "Panel explicable generado:",
        len(rows),
        "partidos"
    )


if __name__ == "__main__":
    main()
