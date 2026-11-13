"""Report actual market readiness independently of observed archive coverage."""
from . import CHAMPION

NAMES = ('GOLES', '1X2', 'DOBLE OPORTUNIDAD', 'xG', 'PRIMERA MITAD',
         'SEGUNDA MITAD', 'CÓRNERS', 'TARJETAS')


def build(report):
    groups = {(g['family'],g['period']):g for g in report['markets']}
    rows = []
    for name in NAMES:
        if name == 'xG':
            native = [report['observed_statistics']['xg'][s] for s in ('home','away')]
            raw = [next((r for r in report['flashscore_reference']['observations']
                         if r['field']=='xg' and r['side']==side and r['window']=='L10'),{})
                   for side in ('home','away')]
            usable = all(r['status']=='EXPERIMENTAL' and r['n']>=5 for r in native)
            source = sorted({p['evidence']['source_url'] for r in native for p in r.get('provenance',[])})
            source += sorted({r['source']['path'] for r in raw if r.get('source')})
            row = dict(market=name,status='IMPLEMENTED' if usable else 'BLOCKED',
                method='Paired historical observed xG/xGA means; not model lambda',
                sample_size=[r['n'] for r in native],
                observed_sample_size=[r.get('sample_size') for r in raw],
                coverage=[r['coverage'] for r in native] if usable else None,
                observed_coverage=[r.get('coverage') for r in raw],
                source=source, probabilities={},
                reason=None if usable else 'unverified_xg_period_capture_publication_or_identity',
                value_kind='OBSERVED_INPUT_NOT_PREDICTION')
        else:
            family,period = {'PRIMERA MITAD':('goals','1H'),'SEGUNDA MITAD':('goals','2H'),
                'CÓRNERS':('corners','FT'),'TARJETAS':('cards','FT')}.get(name,('goals','FT'))
            group = groups[(family,period)]
            selected = group['markets']
            if name == '1X2':
                selected = [m for m in selected if m['market'] in ('1','X','2')]
            elif name == 'DOBLE OPORTUNIDAD':
                selected = [m for m in selected if m['market'] in ('1X','X2','12')]
            elif name == 'GOLES':
                selected = [m for m in selected if m['market'].startswith(('OVER_','UNDER_','BTTS'))]
            meta = group['metadata']
            row = dict(market=name,status=group['status'],method=meta['model'],
                sample_size=meta['sample_size'][:2],input_sample_sizes=meta['sample_size'],
                coverage=meta['coverage'],source=meta['source'],
                probabilities={m['market']:m['probability'] for m in selected},
                reason=group['reason'],value_kind='MODEL_ESTIMATE',
                temporal_window=meta['temporal_window'])
        row.update(prematch_cutoff=report['cutoff'],
            temporal_accreditation='HISTORICAL_SCORE_DATE_POLICY' if name in ('GOLES','1X2','DOBLE OPORTUNIDAD')
                else 'VERIFIED_CAPABILITY_LINEAGE_REQUIRED',
            calibration='NOT_ACCREDITED',validated_oos=False,oos_eligible=False,
            frozen_inputs=bool(report.get('pilot')),decision='NO_BET')
        rows.append(row)
    return rows
