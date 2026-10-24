import argparse
import html
import json
import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def pct(v):
    v = num(v)
    if v is None:
        return "N/D"
    return f"{100*v:.1f}%"


def dec(v):
    v = num(v)
    if v is None:
        return "N/D"
    return f"{v:.2f}"


def esc(x):
    return html.escape(
        str(x or "")
    )


def nivel(p):
    p = num(p)

    if p is None:
        return ""

    if p >= 0.70:
        return "FUERTE"

    if p >= 0.62:
        return "MEDIA"

    if p >= 0.55:
        return "DÉBIL"

    return ""


def celda(p):
    n = nivel(p)

    extra = (
        f'<div class="mg-level">{n}</div>'
        if n
        else ""
    )

    return (
        f"<td>{pct(p)}{extra}</td>"
    )


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--html",
        default="data/report_window_pro.html",
    )

    ap.add_argument(
        "--data",
        default="data/selected_predictions_v2.json",
    )

    args = ap.parse_args()

    html_path = ROOT / args.html
    data_path = ROOT / args.data

    doc = html_path.read_text(
        encoding="utf-8"
    )

    data = json.loads(
        data_path.read_text(
            encoding="utf-8"
        )
    )

    filas = []

    for p in data.get(
        "partidos",
        [],
    ):
        o15 = num(p.get("+1.5"))
        o25 = num(p.get("+2.5"))
        o35 = num(p.get("+3.5"))
        u35 = (
            None
            if o35 is None
            else 1 - o35
        )

        btts = num(p.get("BTTS"))
        p1 = num(p.get("prob_1"))
        px = num(p.get("prob_X"))
        p2 = num(p.get("prob_2"))

        vals = {
            "1": p1,
            "X": px,
            "2": p2,
        }

        validos = {
            k: v
            for k, v in vals.items()
            if v is not None
        }

        if validos:
            favor = max(
                validos,
                key=validos.get,
            )

            favor_txt = (
                f"{favor} "
                f"{pct(validos[favor])}"
            )
        else:
            favor_txt = "N/D"

        filas.append(
            f"""
            <tr>
              <td class="mg-match">
                <strong>
                  {esc(p.get("local"))}
                  vs
                  {esc(p.get("visitante"))}
                </strong>
                <div class="mg-small">
                  {esc(p.get("competicion") or p.get("league"))}
                </div>
              </td>

              <td>{dec(p.get("lambda_local"))}</td>
              <td>{dec(p.get("lambda_visitante"))}</td>
              <td><strong>{dec(p.get("lambda_total"))}</strong></td>

              {celda(o15)}
              {celda(o25)}
              {celda(o35)}
              {celda(u35)}
              {celda(btts)}

              <td>{pct(p1)}</td>
              <td>{pct(px)}</td>
              <td>{pct(p2)}</td>

              <td>
                <strong>{favor_txt}</strong>
                <div class="mg-small">
                  1X2 sin confianza validada
                </div>
              </td>

              <td>
                {esc(p.get("calidad_datos") or "N/D")}
              </td>

              <td>
                {esc(p.get("confianza_btts") or "N/D")}
              </td>
            </tr>
            """
        )

    panel = f"""
    <style>
      .mg-pred-panel {{
        margin: 24px auto;
        max-width: 98%;
        padding: 20px;
        border-radius: 14px;
        background: rgba(20,25,35,.96);
        color: #f4f6f8;
        box-shadow: 0 8px 30px rgba(0,0,0,.25);
      }}

      .mg-pred-panel h2 {{
        margin-top: 0;
      }}

      .mg-pred-wrap {{
        overflow-x: auto;
      }}

      .mg-pred-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
      }}

      .mg-pred-table th,
      .mg-pred-table td {{
        border-bottom: 1px solid rgba(255,255,255,.13);
        padding: 9px 8px;
        text-align: center;
        white-space: nowrap;
      }}

      .mg-pred-table th {{
        position: sticky;
        top: 0;
        background: #202735;
      }}

      .mg-match {{
        text-align: left !important;
      }}

      .mg-small {{
        opacity: .68;
        font-size: 11px;
        margin-top: 3px;
      }}

      .mg-level {{
        font-size: 10px;
        opacity: .75;
        margin-top: 2px;
      }}

      .mg-note {{
        opacity: .75;
        font-size: 12px;
        margin-bottom: 14px;
      }}
    </style>

    <section class="mg-pred-panel">
      <h2>
        Predicción prematch — modelo BT0
      </h2>

      <div class="mg-note">
        λ y probabilidades son estimaciones del modelo.
        Los datos históricos, xG, forma, clasificación y H2H
        permanecen en los dossiers detallados debajo.
        FUERTE ≥70%, MEDIA 62–69.9%, DÉBIL 55–61.9%.
        La clasificación 1X2 se muestra sin confianza predictiva
        validada.
      </div>

      <div class="mg-pred-wrap">
        <table class="mg-pred-table">
          <thead>
            <tr>
              <th>Partido</th>
              <th>λL</th>
              <th>λV</th>
              <th>λTotal</th>
              <th>+1.5</th>
              <th>+2.5</th>
              <th>+3.5</th>
              <th>-3.5</th>
              <th>BTTS Sí</th>
              <th>1</th>
              <th>X</th>
              <th>2</th>
              <th>Favor 1X2</th>
              <th>Calidad</th>
              <th>Conf. BTTS</th>
            </tr>
          </thead>

          <tbody>
            {''.join(filas)}
          </tbody>
        </table>
      </div>
    </section>
    """

    m = re.search(
        r"<body[^>]*>",
        doc,
        flags=re.I,
    )

    if not m:
        raise SystemExit(
            "No encontré <body> en el HTML"
        )

    doc = (
        doc[:m.end()]
        + panel
        + doc[m.end():]
    )

    html_path.write_text(
        doc,
        encoding="utf-8",
    )

    print(
        "Panel prematch insertado:",
        len(filas),
        "partidos"
    )


if __name__ == "__main__":
    main()
