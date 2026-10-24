import json
import html
from pathlib import Path
from datetime import datetime


BASE = Path("data/matches")
DAY = Path("data/day_predictions.json")
SALIDA = Path("data/reporte_jornada.html")


def cargar(ruta, defecto=None):
    if defecto is None:
        defecto = {}

    if not ruta.exists():
        return defecto

    try:
        with ruta.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return defecto


def esc(valor):
    if valor is None:
        return "-"
    return html.escape(str(valor))


def num(valor, dec=2):
    if valor is None:
        return "-"

    try:
        return f"{float(valor):.{dec}f}"
    except (TypeError, ValueError):
        return "-"


def porcentaje_fraccion(valor):
    if valor is None:
        return "-"

    try:
        return f"{float(valor) * 100:.1f}%"
    except (TypeError, ValueError):
        return "-"


def calidad_clase(valor):
    valor = str(valor or "").upper()

    if valor == "FUERTE":
        return "quality strong"

    if valor == "MEDIA":
        return "quality medium"

    return "quality weak"


def obtener_forma(bloque, ventana):
    v = bloque.get(ventana, {})

    over = (
        v.get("over_2_5", {})
        .get("porcentaje")
    )

    btts = (
        v.get("btts", {})
        .get("porcentaje")
    )

    return {
        "pj": v.get("pj"),
        "gf": v.get("promedio_gf"),
        "gc": v.get("promedio_gc"),
        "tg": v.get(
            "promedio_total_goles"
        ),
        "over25": over,
        "btts": btts,
    }


def tabla_forma(nombre, bloque):
    filas = []

    for ventana in ("l5", "l10", "l20"):
        v = obtener_forma(
            bloque,
            ventana,
        )

        filas.append(
            f"""
            <tr>
                <td>{ventana.upper()}</td>
                <td>{esc(v['pj'])}</td>
                <td>{num(v['gf'])}</td>
                <td>{num(v['gc'])}</td>
                <td>{num(v['tg'])}</td>
                <td>{porcentaje_fraccion(v['over25'])}</td>
                <td>{porcentaje_fraccion(v['btts'])}</td>
            </tr>
            """
        )

    return f"""
    <div class="team">
        <h4>{esc(nombre)}</h4>

        <div class="table-wrap">
        <table>
            <thead>
                <tr>
                    <th>Ventana</th>
                    <th>PJ</th>
                    <th>GF/PJ</th>
                    <th>GC/PJ</th>
                    <th>TG/PJ</th>
                    <th>O2.5</th>
                    <th>BTTS</th>
                </tr>
            </thead>
            <tbody>
                {''.join(filas)}
            </tbody>
        </table>
        </div>
    </div>
    """


def tabla_xg(xg):
    filas = []

    for lado, etiqueta in (
        ("local", "Local"),
        ("visitante", "Visitante"),
    ):
        equipo = xg.get(lado, {})

        for ventana in ("l5", "l10"):
            v = equipo.get(
                ventana,
                {},
            )

            filas.append(
                f"""
                <tr>
                    <td>{etiqueta}</td>
                    <td>{ventana.upper()}</td>
                    <td>
                        {esc(v.get('partidos_con_xg'))}
                        /
                        {esc(v.get('partidos_considerados'))}
                    </td>
                    <td>{porcentaje_fraccion(v.get('cobertura_xg'))}</td>
                    <td>{num(v.get('xgf_promedio'), 3)}</td>
                    <td>{num(v.get('xga_promedio'), 3)}</td>
                </tr>
                """
            )

    return f"""
    <div class="table-wrap">
    <table>
        <thead>
            <tr>
                <th>Equipo</th>
                <th>Ventana</th>
                <th>xG disp.</th>
                <th>Cobertura</th>
                <th>xGF</th>
                <th>xGA</th>
            </tr>
        </thead>
        <tbody>
            {''.join(filas)}
        </tbody>
    </table>
    </div>
    """


def tabla_h2h(h2h):
    filas = []

    for clave in (
        "h5",
        "h10",
        "h20",
    ):
        v = h2h.get(clave)

        if not v:
            continue

        filas.append(
            f"""
            <tr>
                <td>{clave.upper()}</td>
                <td>{esc(v.get('n'))}</td>
                <td>{num(v.get('total_promedio'))}</td>
                <td>{porcentaje_fraccion(v.get('p_2_mas'))}</td>
                <td>{porcentaje_fraccion(v.get('p_3_mas'))}</td>
                <td>{porcentaje_fraccion(v.get('p_4_mas'))}</td>
                <td>{porcentaje_fraccion(v.get('btts'))}</td>
            </tr>
            """
        )

    if not filas:
        return '<p class="muted">Sin H2H disponible.</p>'

    return f"""
    <div class="table-wrap">
    <table>
        <thead>
            <tr>
                <th>H2H</th>
                <th>N</th>
                <th>Goles/PJ</th>
                <th>2+</th>
                <th>3+</th>
                <th>4+</th>
                <th>BTTS</th>
            </tr>
        </thead>
        <tbody>
            {''.join(filas)}
        </tbody>
    </table>
    </div>
    """



def marcador_historial(partido):
    gl = partido.get("goles_local")
    gv = partido.get("goles_visitante")

    if gl is None or gv is None:
        return "-"

    marcador = f"{gl} - {gv}"

    pl = partido.get("penales_local")
    pv = partido.get("penales_visitante")

    if pl is not None and pv is not None:
        marcador += f" (pen. {pl}-{pv})"

    return marcador


def tabla_partidos_historial(
    history,
    tipo,
    match_id_objetivo,
):
    seccion = next(
        (
            s
            for s in history.get(
                "secciones",
                [],
            )
            if s.get("tipo_estimado") == tipo
        ),
        None,
    )

    if seccion is None:
        return (
            '<p class="muted">'
            'Sección no disponible.'
            '</p>'
        )

    partidos = [
        partido
        for partido in seccion.get(
            "partidos",
            [],
        )
        if partido.get("match_id")
        != match_id_objetivo
    ]

    if not partidos:
        return (
            '<p class="muted">'
            'No hay partidos históricos disponibles.'
            '</p>'
        )

    filas = []

    for i, partido in enumerate(
        partidos,
        start=1,
    ):
        competicion = (
            partido.get("competicion")
            or partido.get(
                "competicion_codigo"
            )
            or "-"
        )

        filas.append(
            f"""
            <tr>
                <td>{i}</td>
                <td>{esc(partido.get('fecha'))}</td>
                <td>{esc(competicion)}</td>
                <td>{esc(partido.get('local'))}</td>
                <td class="score">
                    {esc(marcador_historial(partido))}
                </td>
                <td>{esc(partido.get('visitante'))}</td>
            </tr>
            """
        )

    titulo = seccion.get("titulo") or tipo

    return f"""
    <div class="history-header">
        <b>{esc(titulo)}</b>
        <span class="history-count">
            {len(partidos)} partidos
        </span>
    </div>

    <div class="table-wrap">
        <table class="history-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Fecha</th>
                    <th>Competición</th>
                    <th>Local</th>
                    <th>Marcador</th>
                    <th>Visitante</th>
                </tr>
            </thead>

            <tbody>
                {''.join(filas)}
            </tbody>
        </table>
    </div>
    """

def bloque_temporada(enriched):
    t = (
        enriched.get(
            "datos_observados",
            {},
        ).get(
            "temporada",
            {},
        )
    )

    if (
        not t
        or t.get("estado")
        != "ok"
    ):
        return (
            '<p class="muted">'
            'Clasificación no disponible '
            'o no utilizada en el modelo principal.'
            '</p>'
        )

    local = t.get("local") or {}
    visitante = t.get(
        "visitante"
    ) or {}

    return f"""
    <div class="season-grid">
        <div>
            <b>Local</b><br>
            Posición: {esc(local.get('posicion'))}<br>
            PJ: {esc(local.get('pj'))}<br>
            GF: {esc(local.get('gf'))} |
            GC: {esc(local.get('gc'))}<br>
            Pts: {esc(local.get('puntos'))}
        </div>

        <div>
            <b>Visitante</b><br>
            Posición: {esc(visitante.get('posicion'))}<br>
            PJ: {esc(visitante.get('pj'))}<br>
            GF: {esc(visitante.get('gf'))} |
            GC: {esc(visitante.get('gc'))}<br>
            Pts: {esc(visitante.get('puntos'))}
        </div>
    </div>
    """


def partido_html(p, posicion):
    mid = p["match_id"]
    carpeta = BASE / mid

    enriched = cargar(
        carpeta / "enriched.json"
    )

    history = cargar(
        carpeta / "history.json"
    )

    xg = cargar(
        carpeta / "xg_history.json"
    )

    h2h = cargar(
        carpeta / "h2h_analysis.json"
    )

    result = cargar(
        carpeta / "result.json"
    )

    observados = enriched.get(
        "datos_observados",
        {},
    )

    local = observados.get(
        "local",
        {},
    )

    visitante = observados.get(
        "visitante",
        {},
    )

    integridad = result.get(
        "integridad_temporal",
        {},
    ).get(
        "estado",
        "N/D",
    )

    return f"""
    <article
        class="match-card"
        data-quality="{esc(p.get('calidad'))}"
        data-search="{esc(
            (p.get('local') or '')
            + ' '
            + (p.get('visitante') or '')
            + ' '
            + (p.get('competicion') or '')
        ).lower()}"
    >
        <div class="match-head">
            <div>
                <div class="rank">#{posicion}</div>
                <h2>
                    {esc(p.get('local'))}
                    <span>vs</span>
                    {esc(p.get('visitante'))}
                </h2>

                <p class="muted">
                    {esc(p.get('pais'))}
                    ·
                    {esc(p.get('competicion'))}
                    ·
                    {esc(p.get('fecha'))}
                    {esc(p.get('hora'))}
                    · ID {esc(mid)}
                </p>
            </div>

            <div class="{calidad_clase(p.get('calidad'))}">
                {esc(p.get('calidad'))}
            </div>
        </div>

        <div class="prob-grid">
            <div class="metric primary">
                <small>λ total</small>
                <strong>{num(p.get('lambda_total'))}</strong>
            </div>

            <div class="metric">
                <small>+1.5</small>
                <strong>{num(p.get('+1.5'), 1)}%</strong>
            </div>

            <div class="metric">
                <small>+2.5</small>
                <strong>{num(p.get('+2.5'), 1)}%</strong>
            </div>

            <div class="metric">
                <small>+3.5</small>
                <strong>{num(p.get('+3.5'), 1)}%</strong>
            </div>

            <div class="metric">
                <small>+4.5</small>
                <strong>{num(p.get('+4.5'), 1)}%</strong>
            </div>

            <div class="metric">
                <small>BTTS</small>
                <strong>{num(p.get('btts'), 1)}%</strong>
            </div>
        </div>

        <div class="section-label">
            Resultado del partido
        </div>

        <div class="prob-grid result-grid">
            <div class="metric result-metric">
                <small>Victoria local (1)</small>
                <strong>{num(p.get('victoria_local'), 1)}%</strong>
            </div>

            <div class="metric result-metric">
                <small>Empate (X)</small>
                <strong>{num(p.get('empate'), 1)}%</strong>
            </div>

            <div class="metric result-metric">
                <small>Victoria visitante (2)</small>
                <strong>{num(p.get('victoria_visitante'), 1)}%</strong>
            </div>
        </div>

        <div class="section-label">
            Doble oportunidad
        </div>

        <div class="prob-grid double-grid">
            <div class="metric">
                <small>Local o empate (1X)</small>
                <strong>{num(p.get('1X'), 1)}%</strong>
            </div>

            <div class="metric">
                <small>Empate o visitante (X2)</small>
                <strong>{num(p.get('X2'), 1)}%</strong>
            </div>

            <div class="metric">
                <small>Sin empate (12)</small>
                <strong>{num(p.get('12'), 1)}%</strong>
            </div>
        </div>

        <details open>
            <summary>Forma reciente L5 / L10 / L20</summary>

            <div class="two-cols">
                {tabla_forma(
                    local.get(
                        "equipo",
                        p.get("local")
                    ),
                    local,
                )}

                {tabla_forma(
                    visitante.get(
                        "equipo",
                        p.get("visitante")
                    ),
                    visitante,
                )}
            </div>
        </details>

        <details>
            <summary>xG reciente</summary>
            {tabla_xg(xg)}
        </details>

        <details>
            <summary>Enfrentamientos directos H2H</summary>
            {tabla_h2h(h2h)}
        </details>

        <details>
            <summary>Clasificación / temporada</summary>
            {bloque_temporada(enriched)}
        </details>

        <details>
            <summary>
                Todos los partidos scrapeados · {esc(p.get('local'))}
            </summary>

            {tabla_partidos_historial(
                history,
                "equipo_local",
                mid,
            )}
        </details>

        <details>
            <summary>
                Todos los partidos scrapeados · {esc(p.get('visitante'))}
            </summary>

            {tabla_partidos_historial(
                history,
                "equipo_visitante",
                mid,
            )}
        </details>

        <details>
            <summary>
                Todos los enfrentamientos directos H2H
            </summary>

            {tabla_partidos_historial(
                history,
                "h2h",
                mid,
            )}
        </details>

        <div class="integrity">
            Integridad temporal:
            <b>{esc(integridad)}</b>
        </div>
    </article>
    """


def main():
    if not DAY.exists():
        raise SystemExit(
            "No existe data/day_predictions.json"
        )

    day = cargar(DAY)

    partidos = day.get(
        "partidos",
        [],
    )

    errores = day.get(
        "errores",
        [],
    )

    cards = [
        partido_html(p, i)
        for i, p in enumerate(
            partidos,
            start=1,
        )
    ]

    errores_html = ""

    if errores:
        filas = "".join(
            f"""
            <tr>
                <td>{esc(e.get('match_id'))}</td>
                <td>{esc(e.get('motivo'))}</td>
            </tr>
            """
            for e in errores
        )

        errores_html = f"""
        <section class="errors">
            <h2>No analizados</h2>
            <table>
                <thead>
                    <tr>
                        <th>Match ID</th>
                        <th>Motivo</th>
                    </tr>
                </thead>
                <tbody>
                    {filas}
                </tbody>
            </table>
        </section>
        """

    generado = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    documento = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta
    name="viewport"
    content="width=device-width,initial-scale=1"
>
<title>Match Goals AI - Jornada</title>

<style>
:root {{
    color-scheme: dark;
    --bg: #0d1117;
    --panel: #161b22;
    --panel2: #21262d;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #8b949e;
    --good: #3fb950;
    --mid: #d29922;
    --bad: #f85149;
    --accent: #58a6ff;
}}

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    font-family:
        Inter,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
    background: var(--bg);
    color: var(--text);
}}

main {{
    width: min(1500px, 96%);
    margin: 0 auto;
    padding: 28px 0 60px;
}}

.top {{
    display: flex;
    justify-content: space-between;
    gap: 20px;
    align-items: flex-start;
    flex-wrap: wrap;
    margin-bottom: 24px;
}}

h1 {{
    margin: 0 0 6px;
}}

h2 {{
    margin: 0;
}}

h2 span {{
    color: var(--muted);
    font-weight: 400;
}}

.muted {{
    color: var(--muted);
}}

.controls {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}}

input,
select {{
    background: var(--panel);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 16px;
}}

.summary {{
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin: 16px 0 26px;
}}

.summary-box {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 18px;
}}

.match-card {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 22px;
}}

.match-head {{
    display: flex;
    justify-content: space-between;
    gap: 14px;
    align-items: flex-start;
}}

.rank {{
    color: var(--accent);
    font-weight: 700;
    margin-bottom: 5px;
}}

.quality {{
    padding: 8px 12px;
    border-radius: 999px;
    font-weight: 700;
}}

.strong {{
    color: var(--good);
    border: 1px solid var(--good);
}}

.medium {{
    color: var(--mid);
    border: 1px solid var(--mid);
}}

.weak {{
    color: var(--bad);
    border: 1px solid var(--bad);
}}

.prob-grid {{
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(110px, 1fr));
    gap: 10px;
    margin: 20px 0;
}}

.metric {{
    background: var(--panel2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px;
}}

.metric small {{
    display: block;
    color: var(--muted);
    margin-bottom: 5px;
}}

.metric strong {{
    font-size: 1.35rem;
}}

.metric.primary {{
    border-color: var(--accent);
}}

.section-label {{
    margin-top: 18px;
    margin-bottom: 8px;
    color: var(--muted);
    font-size: .85rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .04em;
}}

.result-metric strong {{
    font-size: 1.25rem;
}}

details {{
    border-top: 1px solid var(--border);
    padding: 13px 0;
}}

summary {{
    cursor: pointer;
    font-weight: 700;
}}

.two-cols {{
    display: grid;
    grid-template-columns:
        repeat(2, minmax(0, 1fr));
    gap: 16px;
    margin-top: 14px;
}}

.team h4 {{
    margin: 5px 0 10px;
}}

.table-wrap {{
    overflow-x: auto;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 12px;
}}

th,
td {{
    text-align: right;
    padding: 9px 10px;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
}}

th:first-child,
td:first-child {{
    text-align: left;
}}

th {{
    color: var(--muted);
    font-weight: 600;
}}

.season-grid {{
    display: grid;
    grid-template-columns:
        repeat(2, minmax(0, 1fr));
    gap: 20px;
    margin-top: 14px;
}}

.history-header {{
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
    margin-top: 14px;
    margin-bottom: 6px;
}}

.history-count {{
    color: var(--muted);
    font-size: .9rem;
}}

.history-table .score {{
    text-align: center;
    font-weight: 700;
    color: var(--text);
}}

.history-table td:nth-child(1) {{
    color: var(--muted);
}}

.history-table td:nth-child(4),
.history-table td:nth-child(6) {{
    text-align: left;
}}

.integrity {{
    margin-top: 8px;
    font-size: .9rem;
    color: var(--muted);
}}

.integrity b {{
    color: var(--good);
}}

.errors {{
    background: var(--panel);
    border: 1px solid var(--bad);
    border-radius: 14px;
    padding: 20px;
    margin-top: 30px;
}}

.hidden {{
    display: none;
}}

@media (max-width: 800px) {{
    .two-cols,
    .season-grid {{
        grid-template-columns: 1fr;
    }}

    .match-head {{
        flex-direction: column;
    }}
}}
</style>
</head>

<body>
<main>

<div class="top">
    <div>
        <h1>Match Goals AI</h1>
        <div class="muted">
            Reporte completo de la jornada
        </div>
        <div class="muted">
            Generado: {generado}
        </div>
    </div>

    <div class="controls">
        <input
            id="search"
            type="search"
            placeholder="Buscar equipo o liga..."
        >

        <select id="quality">
            <option value="">Todas las calidades</option>
            <option value="FUERTE">FUERTE</option>
            <option value="MEDIA">MEDIA</option>
            <option value="DEBIL">DEBIL</option>
        </select>
    </div>
</div>

<div class="summary">
    <div class="summary-box">
        Analizados:
        <b>{len(partidos)}</b>
    </div>

    <div class="summary-box">
        No analizados:
        <b>{len(errores)}</b>
    </div>

    <div class="summary-box">
        Modelo:
        <b>Forma + xG + local/visitante</b>
    </div>
</div>

<section id="matches">
    {''.join(cards)}
</section>

{errores_html}

</main>

<script>
const search = document.getElementById("search");
const quality = document.getElementById("quality");
const cards = Array.from(
    document.querySelectorAll(".match-card")
);

function filtrar() {{
    const texto = search.value.trim().toLowerCase();
    const q = quality.value;

    cards.forEach(card => {{
        const coincideTexto =
            !texto ||
            card.dataset.search.includes(texto);

        const coincideCalidad =
            !q ||
            card.dataset.quality === q;

        card.classList.toggle(
            "hidden",
            !(coincideTexto && coincideCalidad)
        );
    }});
}}

search.addEventListener("input", filtrar);
quality.addEventListener("change", filtrar);
</script>

</body>
</html>
"""

    SALIDA.write_text(
        documento,
        encoding="utf-8",
    )

    print(
        "Reporte generado:",
        SALIDA,
    )

    print(
        "Partidos:",
        len(partidos),
    )

    print(
        "No analizados:",
        len(errores),
    )


if __name__ == "__main__":
    main()
