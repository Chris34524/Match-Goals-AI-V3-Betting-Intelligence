"""Standalone escaped HTML and immutable JSON/HTML bundles in an isolated root."""
import html
import os
from pathlib import Path
import shutil
import tempfile
import re

from v3.flashscore.contract import dumps

ROOT = Path('v3_data/selected_analysis')


def esc(value):
    if type(value) is bool:
        value = 'Sí' if value else 'No'
    return html.escape(str(value if value is not None else 'N/D'), quote=True)


def number(value):
    return f'{value:.3f}' if type(value) in (int, float) else 'N/D'


def reason(value):
    if value is None:
        return 'N/D'
    messages = {
        'stable_team_competition_season_ids_required': 'Faltan IDs estables de equipos, competición o temporada.',
        'explicit_verified_card_counting_policy_required': 'Falta una política explícita de conteo de tarjetas verificada.',
        'incompatible_card_semantics': 'Las categorías o reglas de tarjetas son incompatibles.',
        'insufficient_history': 'Historial insuficiente: se requieren al menos cinco partidos válidos.',
        'missing_operand': 'Falta una estadística histórica necesaria.',
        'temporal_ineligible': 'La publicación o revisión no está acreditada antes del corte.',
        'acquisition_not_verified': 'La autorización de adquisición no está verificada.',
        'minimum_5_vetted_scores_per_team_required': 'Se requieren al menos cinco resultados válidos por equipo.',
        'cached_predictions_not_accredited_for_requested_cutoff': 'El caché no acredita el corte solicitado.',
        'same_vetted_inputs_no_promotion': 'Mismos datos filtrados; comparación descriptiva sin promoción.'}
    return messages.get(value, value)


def table(headers, rows):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+(
        '</tr></thead><tbody>')+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in rows)+(
        '</tbody></table></div>')


def render(report):
    fixture = report['fixture']
    title = fixture['home']['name']+' vs '+fixture['away']['name']
    sections = []
    if report.get('pilot'):
        frozen = report['pilot']
        sections.append('<section><h2>Corte prepartido congelado</h2>'+table(
            ('Corte de información','Generación','Kickoff programado','Evidencia de horario'),
            [(report['cutoff'],report['generated_at'],fixture['kickoff'],frozen['schedule_status'])])+
            '<p>Los bytes de entrada se conservaron con hashes antes del kickoff. '
            'La corroboración del horario y este registro local no acreditan OOS, '
            'calibración ni publicaciones históricas desconocidas.</p></section>')
    if report.get('market_matrix'):
        sections.append('<section><h2>Estado real por mercado</h2>'+table(
            ('Mercado','Estado','Fuente','n predictivo por equipo','Cobertura','Acreditación temporal','Método','Motivo'),
            [(r['market'],r['status'],
              fixture['provider']+' · '+', '.join(Path(s).name for s in r['source']) if r['source'] else 'Sin evidencia',
              str(r['sample_size']),f"{r['coverage']:.0%}" if isinstance(r['coverage'],(float,int)) else 'N/D',
              'Fechas históricas; OOS excluido' if r['temporal_accreditation']=='HISTORICAL_SCORE_DATE_POLICY'
                  else 'Linaje específico requerido; OOS excluido',
              r['method'],reason(r['reason'])) for r in report['market_matrix']])+'</section>')
    form_rows = []
    for side in ('home', 'away'):
        for key, value in report['form']['observed'].get(side, {}).items():
            if isinstance(value, dict):
                window = {'como_local':'Como local','como_visitante':'Como visitante'}.get(key,key.upper())
                form_rows.append((fixture[side]['name'], window, value['pj'], value.get('requested_n'),
                    number(value['promedio_gf']), number(value['promedio_gc']),
                    value.get('partial_sample', False)))
    sections.append('<section><h2>Rendimiento reciente y localía</h2>'+table(
        ('Equipo', 'Ventana', 'n observado', 'n solicitado', 'GF / partido', 'GC / partido', 'Muestra parcial'), form_rows)+
        '<p>Las ventanas L5/L10/L20 se solapan. Sus tamaños no se suman como muestras independientes.</p></section>')
    reference = report.get('flashscore_reference',{})
    reference_rows = reference.get('observations',[])
    xg_rows = [r for r in reference_rows if r['field'] in ('xg','xga')]
    if xg_rows:
        sections.append('<section><h2>Flashscore México · xG/xGA del archivo existente</h2>'+table(
            ('Campo','Equipo','Ventana','Media observada','n','Cobertura','Uso predictivo'),
            [({'xg':'xG','xga':'xGA'}[r['field']],fixture[r['side']]['name'],r['window'],number(r['value']),r['sample_size'],
              f"{r['coverage']:.0%}" if r['coverage'] is not None else 'N/D',r['predictive_status']) for r in xg_rows])+
            '<p>Son observaciones archivadas. El scraper legado no registró el periodo seleccionado ni la fecha de captura '
            'de cada valor; tampoco se acredita su publicación histórica. Estos valores quedan excluidos de los modelos.</p></section>')
    standings = {(r['side'],r['field']):r['value'] for r in reference_rows if r['field'].startswith('standings_')}
    if standings:
        fields = ('posicion','pj','ganados','empatados','perdidos','gf','gc','dg','puntos','forma')
        sections.append('<section><h2>Flashscore México · clasificación archivada</h2>'+table(
            ('Equipo','Pos.','PJ','G','E','P','GF','GC','DG','Puntos','Forma'),
            [(fixture[side]['name'],*(standings.get((side,'standings_'+field)) for field in fields)) for side in ('home','away')])+
            '<p>Snapshot de referencia con captura/publicación no acreditadas. No representa una clasificación '
            'prepartido verificada y no participa en el Champion.</p></section>')
    metric_names = dict(xg='xG',xga='xGA',shots='Remates totales',shots_on_target='Remates a puerta',
                        possession='Posesión',yellow_cards='Amarillas observadas',red_cards='Rojas observadas',fouls='Faltas')
    observed_rows = [(metric_names[metric], fixture[side]['name'], number(values['mean']), values['n'], values['status'], reason(values['reason']))
                     for metric, teams in report['observed_statistics'].items() for side, values in teams.items()]
    sections.append('<section><h2>Estadísticas observadas · xG y rendimiento</h2>'+table(
        ('Métrica', 'Equipo', 'Media observada', 'n', 'Estado', 'Limitación'), observed_rows)+
        '<p>xG observado y xGA describen ocasiones históricas; λ es una expectativa del modelo. Los null no son ceros.</p></section>')
    for group in report['markets']:
        rows = [(m['market'], f"{m['probability']:.2%}" if m['probability'] is not None else 'N/D',
                 m['status'], m['model'], str(m['sample_size']), number(m['coverage']), reason(m['reason'])) for m in group['markets']]
        components = ''
        if group['family'] == 'cards':
            components = '<p>Conteo según política explícita: '+esc((group.get('counting_policy') or {}).get('version'))+'</p>'
            components += table(('Equipo', 'Amarillas', 'Rojas directas', 'Expulsión por segunda amarilla'),
                [(fixture[side]['name'], *(number(values[k]) for k in ('yellow', 'direct_red', 'second_yellow_dismissals')))
                 for side, values in group.get('observed_components', {}).items()])
        sections.append('<section class="market-group" data-status="'+esc(group['status'])+'"><h2>'+esc(
            {'goals': 'Goles', 'corners': 'Córners', 'cards': 'Tarjetas'}[group['family']]+' · '+group['period'])+
            '</h2><span class="badge">'+esc(group['status'])+'</span><div class="metrics">'+
            ''.join('<div><small>'+esc(label)+'</small><strong>'+number(group[key])+'</strong></div>'
                    for label, key in (('Expectativa local', 'expected_home'), ('Expectativa visitante', 'expected_away'),
                                       ('Expectativa total', 'expected_total')))+
            '</div>'+components+table(('Mercado', 'Probabilidad', 'Estado', 'Modelo', 'n por serie', 'Cobertura', 'Causa'), rows)+
            '<p>'+esc(group['metadata']['accreditation'])+' · Calibración: no acreditada · OOS: excluido</p>'+
            '<p>'+esc('; '.join(group['metadata']['limitations']))+'</p>'+(
                '<details><summary>Modelo, validación y trazabilidad de las muestras</summary><pre>'+esc(dumps(
                    {k: v for k, v in group.items() if k not in ('markets',)}))+'</pre></details>')+'</section>')
    first = report['markets'][0]
    sections.append('<section><h2>Marcadores más probables</h2>'+table(('Marcador', 'Probabilidad'),
        [(s['marcador'], f"{s['probabilidad']:.2%}") for s in first['likely_scores']])+ '</section>')
    sections.append('<section><h2>Producción por mitades</h2>'+table(('1H total', '2H total', '2H − 1H'),
        [[number(report['half_comparison'][k]) for k in ('first_half', 'second_half', 'second_minus_first')]])+'</section>')
    sections.append('<section><h2>Comparación de modelos</h2>'+table(('Modelo', 'λ local', 'λ visitante', 'λ total', 'Estado', 'Causa'),
        [(r['model'], number((r['values'] or {}).get('local')), number((r['values'] or {}).get('visitante')),
          number((r['values'] or {}).get('total')), r['status'], reason(r['reason'])) for r in report['model_comparison']])+
        '<p>Comparación descriptiva de expectativas. No acredita calibración, rendimiento OOS ni promoción.</p></section>')
    sections.append('<section><h2>Enfrentamientos directos</h2><pre>'+esc(dumps(report['form']['h2h']))+'</pre></section>')
    sections.append('<section><h2>Calidad de información y mercados pendientes</h2><ul>'+''.join(
        '<li>'+esc(w)+'</li>' for w in report['quality']['warnings'])+'</ul>'+table(('Variable', 'Estado'),
        report['additional_variables'].items())+'</section>')
    sections.append('<section><h2>Fuentes y trazabilidad</h2>'+table(('Archivo', 'SHA-256', 'Captura'),
        [(s['path'], s['sha256'], s['captured_at']) for s in report['sources']])+ '<p>Corte: '+esc(report['cutoff'])+
        '</p><p>Generado: '+esc(report['generated_at'])+'</p><p>ID: '+esc(report['analysis_id'])+'</p></section>')
    sections.append('<section><h2>Conclusiones analíticas</h2><ul>'+''.join('<li>'+esc(c)+'</li>' for c in report['conclusions'])+
        '</ul><p>NO_BET. Las probabilidades estimadas conservan incertidumbre y no acreditan rentabilidad.</p></section>')
    return '''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>'''+esc(title)+''' · Match Goals AI</title><style>
:root{color-scheme:dark;--bg:#0c1421;--panel:#142235;--ink:#eaf2ff;--muted:#a8bcd5;--line:#304158;--accent:#5ae1bd}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,sans-serif;overflow-wrap:anywhere}
main{max-width:1220px;margin:auto;padding:32px 22px}header{padding:30px 0}h1{font-size:clamp(28px,4vw,48px);line-height:1.15;margin:12px 0}
h2{font-size:21px;margin:0 0 16px}small,.muted,p{color:var(--muted)}.brand{letter-spacing:.15em;color:var(--accent);font-size:12px}
section{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:24px;margin:18px 0}.badge{display:inline-block;border:1px solid var(--accent);border-radius:30px;padding:3px 12px;color:var(--accent)}
.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:20px 0}.metrics strong{display:block;font-size:28px}.scroll{overflow:auto}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{text-align:left;border-bottom:1px solid var(--line);padding:12px 10px;vertical-align:top;white-space:nowrap}th{color:var(--muted)}
td:last-child{white-space:normal;min-width:130px;max-width:360px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;max-height:440px;overflow:auto}select{background:var(--panel);color:var(--ink);padding:9px;border:1px solid var(--line);border-radius:8px}
details{margin-top:16px}summary{cursor:pointer;color:var(--accent)}li{margin:8px 0}footer{padding:24px;color:var(--muted)}
@media(max-width:620px){main{padding:15px}section{padding:17px}.metrics{grid-template-columns:1fr}.metrics strong{font-size:24px}}
@media print{body{background:white;color:#132238}section{background:white;break-inside:avoid}p,small,th{color:#384d60}select,details{display:none}}
</style></head><body><main><header><div class="brand">MATCH GOALS AI · V3</div><h1>'''+esc(title)+'''</h1><p>'''+esc(
        fixture['competition'])+' · '+esc(fixture['date'])+' · '+esc(fixture['display_time'])+' · '+esc(fixture['timezone'])+(
        '</p><p>Referencia principal: Flashscore México · Fuente activa: '+esc(fixture['provider'])+
        ' · Complementos por selección explícita</p><span class="badge">NO_BET · ANÁLISIS OPERATIVO · OOS EXCLUIDO</span>')+(
        '<p>SYNTHETIC_TEST_ONLY</p>' if report['synthetic_test_only'] else '')+'''</header>
<label for="state">Mostrar mercados: </label><select id="state"><option value="all">Todos</option><option>IMPLEMENTED</option><option>EXPERIMENTAL</option><option>INSUFFICIENT_DATA</option><option>BLOCKED</option><option>NOT_COVERED</option></select>
'''+''.join(sections)+'''<footer>Reporte autónomo · Sin recursos externos · Datos faltantes visibles</footer></main>
<script>document.getElementById('state').addEventListener('change',function(){document.querySelectorAll('.market-group').forEach(s=>{s.hidden=this.value!=='all'&&s.dataset.status!==this.value})})</script></body></html>'''


def destination(root):
    root = Path(root).absolute()
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('symlink_report_path')
    if not (root.resolve().is_relative_to(ROOT.resolve()) or root.resolve().is_relative_to(Path('/tmp'))):
        raise ValueError('outside_isolated_selected_analysis_root')
    return root


def write(report, root=ROOT):
    fixture = report['fixture']
    if (not re.fullmatch(r'[a-z_]+', fixture['provider'])
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', fixture['provider_fixture_id'])
            or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', fixture['date'])
            or not re.fullmatch(r'[0-9a-f]{64}', report['analysis_id'])):
        raise ValueError('invalid_report_identity')
    parent = destination(Path(root)/fixture['date']/(fixture['provider']+'_'+fixture['provider_fixture_id']))
    final = destination(parent/report['analysis_id'])
    payloads = {'report.json': dumps(report)+'\n', 'report.html': render(report)}
    if final.exists():
        if any((final/name).is_symlink() or (final/name).read_text(encoding='utf-8') != text for name, text in payloads.items()):
            raise ValueError('immutable_report_conflict')
        return final
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.analysis-', dir=parent))
    try:
        for name, text in payloads.items():
            with (temporary/name).open('x', encoding='utf-8') as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
        temporary.rename(final)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return final
