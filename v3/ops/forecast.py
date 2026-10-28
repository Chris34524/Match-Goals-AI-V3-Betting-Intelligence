"""Offline predictive lane. PICKS DO NOT DEPEND ON ODDS.

Evidence adapters replay independent, content-addressed records; serialized flags
alone never accredit predictions or outcomes. No betting ledger writes occur here.
"""
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from analysis.poisson import analizar
from v3.odds.provider import utc
from . import runtime
from .target_discovery import validate_kickoff_lineage

ROOT = Path('v3_data/ops/forecast')
CHAMPION = 'J_BT_sin_temporada'
IDENTITY = ('internal_match_id', 'home', 'away', 'competition')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def load(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def evidence(row, kind):
    """Read sealed evidence, reject self-reference, symlinks and ambiguous identity."""
    lineage = row[kind + '_lineage']
    path = Path(lineage['source_path'])
    resolved = path.resolve()
    roots = [Path('data').resolve(), Path('v3_data/ops/evidence').resolve()]
    if not any(resolved.is_relative_to(r) for r in roots):
        raise ValueError('evidence_outside_root')
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('evidence_symlink')
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != lineage['source_sha256'] or (resolved.is_relative_to(roots[1]) and path.name != sha + '.json'):
        raise ValueError('evidence_digest')
    document = json.loads(raw)
    records = [r for r in document['records'] if r.get('source_record_id') == lineage['source_record_id']]
    if len(records) != 1 or document.get('synthetic_test_only') is not False:
        raise ValueError('evidence_ambiguous_or_synthetic')
    record = records[0]
    if record.get('synthetic_test_only') is not False or any(k in record for k in ('prediction_lineage', 'settlement_lineage', 'kickoff_lineage')):
        raise ValueError('evidence_self_reference_or_synthetic')
    if record['identity'] != {k: row[k] for k in IDENTITY}:
        raise ValueError('evidence_identity')
    return record, sha


def accredited(row, now):
    try:
        if row.get('synthetic_test_only') is not False or row.get('model') != CHAMPION:
            return False
        identity = {k: row[k] for k in IDENTITY}
        if not all(identity.values()) or row['home'] == row['away']:
            return False
        validate_kickoff_lineage(row, ROOT/'prospective.json', identity, now)
        record, _ = evidence(row, 'prediction')
        fields = ('generated_at', 'kickoff_at', 'model', 'model_lineage', 'probabilities', 'feature_cutoff_at')
        if any(record.get(k) != row.get(k) for k in fields) or not row.get('model_lineage'):
            return False
        return utc(row['feature_cutoff_at']) <= utc(row['generated_at']) < utc(row['kickoff_at']) and utc(row['generated_at']) <= utc(now)
    except (KeyError, TypeError, ValueError, OSError):
        return False


def probabilities(lh, la):
    r = analizar(lh, la)
    return {'Over1.5': r['goles']['2_mas'], 'Over2.5': r['goles']['3_mas'],
            'Over3.5': r['goles']['4_mas'], 'BTTS': r['btts']['si'],
            'HomeWin': r['resultado']['victoria_local'], 'Draw': r['resultado']['empate'],
            'AwayWin': r['resultado']['victoria_visitante'], **r['doble_oportunidad']}


def candidates(row, now):
    good = accredited(row, now)
    probs = row.get('probabilities', {})
    if not good:
        lh, la = row.get('lambda_home'), row.get('lambda_away')
        if lh is not None and la is not None:
            if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x >= 0 for x in (lh, la)):
                return []
            probs = probabilities(lh, la)
    out = []
    for market, p in probs.items():
        if market not in {'Over1.5','Over2.5','Over3.5','BTTS','HomeWin','Draw','AwayWin','1X','X2','12'}:
            continue
        if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1:
            continue
        item = {k: row.get(k) for k in (*IDENTITY, 'kickoff_at', 'generated_at', 'lambda_home', 'lambda_away', 'lambda_total', 'data_quality')}
        item.update(model=CHAMPION, market=market, selection=market, model_probability=p,
                    calibrated_probability=None, probability=p, fair_odds=1/p if p > 0 else None,
                    minimum_acceptable_odds=None, forecast_status='FORECAST_PASS',
                    accreditation_status='ACCREDITED_FORECAST' if good else 'OPERATIONAL_LEGACY_FORECAST',
                    oos_eligible=good, odds_status='UNAVAILABLE', value_status='NOT_EVALUATED',
                    provenance=row, source_digest=(row['prediction_lineage']['source_sha256'] if good else row.get('source_digest')),
                    market_odds=None, market_probability=None, edge=None, ev=None, clv=None, PickScore=None)
        # Phase 4 defaults are explicitly synthetic, so not a real minimum-price policy.
        item['forecast_id'] = digest({k:item[k] for k in ('internal_match_id','model','market','generated_at','source_digest')})
        out.append(item)
    quality = {'ALTA': 0, 'FUERTE': 0, 'MEDIA': 1, 'BAJA': 2, 'DEBIL': 2, 'REVISAR': 3}
    out.sort(key=lambda x: (-int(x['oos_eligible']), quality.get(x['data_quality'], 4), -x['probability'], x['market']))
    for rank, item in enumerate(out, 1):
        item['forecast_rank'] = rank
    return out


def sources():
    """Accredited adapter first, then exact BT0 lambdas, then legacy outputs."""
    selected = {}
    for row in load(ROOT/'prospective.json', []) or []:
        if accredited(row, datetime.now(timezone.utc).isoformat()):
            selected[row['internal_match_id']] = row
    for path in sorted(Path('data/matches').glob('*/lambda_comparison.json')):
        comp = load(path, {})
        method = comp.get('metodos', {}).get(CHAMPION)
        if not method:
            continue
        mid = path.parent.name
        conf = load(path.parent/'confidence_v2.json', {})
        p = comp.get('partido', {})
        selected.setdefault(mid, dict(internal_match_id=mid, home=p.get('local'), away=p.get('visitante'),
            competition=p.get('competicion'), lambda_home=method.get('local'), lambda_away=method.get('visitante'),
            lambda_total=method.get('total'), data_quality=conf.get('calidad_datos_global'),
            source_path=str(path), source_digest=hashlib.sha256(path.read_bytes()).hexdigest(),
            legacy_date=p.get('fecha'), legacy_time=p.get('hora')))
    for path in sorted(Path('data/matches').glob('*/confidence_v2.json')):
        conf = load(path, {})
        if conf.get('modelo') != CHAMPION:
            continue
        base = (conf.get('detalle_v1') or {}).get('lambda_base') or {}
        p = (conf.get('detalle_v1') or {}).get('partido') or {}
        if base.get('local') is None or base.get('visitante') is None:
            continue
        mid = path.parent.name
        selected.setdefault(mid, dict(internal_match_id=mid, home=p.get('local'), away=p.get('visitante'),
            competition=p.get('competicion'), lambda_home=base['local'], lambda_away=base['visitante'],
            lambda_total=base.get('total'), data_quality=conf.get('calidad_datos_global'),
            source_path=str(path), source_digest=hashlib.sha256(path.read_bytes()).hexdigest(),
            legacy_date=p.get('fecha'), legacy_time=p.get('hora')))
    for path in map(Path, ('data/day_predictions_v2.json','data/day_predictions.json','data/all_predictions.json')):
        document = load(path, {})
        if document.get('modelo_principal') != CHAMPION:
            continue
        for p in document.get('partidos', []):
            mid = p.get('match_id')
            if not mid or mid in selected:
                continue
            confpath = Path('data/matches')/mid/'confidence_v2.json'
            conf = load(confpath, {})
            base = (conf.get('detalle_v1') or {}).get('lambda_base') or {}
            selected[mid] = dict(internal_match_id=mid, home=p.get('local'), away=p.get('visitante'), competition=p.get('competicion'),
                lambda_home=base.get('local', p.get('lambda_local')), lambda_away=base.get('visitante', p.get('lambda_visitante')),
                lambda_total=base.get('total', p.get('lambda_total')), data_quality=p.get('calidad'),
                source_path=str(path), source_digest=hashlib.sha256(path.read_bytes()).hexdigest(), legacy_date=p.get('fecha'), legacy_time=p.get('hora'))
    return [selected[k] for k in sorted(selected)]


def oos_report(rows, settlements=(), now=None):
    now = now or datetime.now(timezone.utc).isoformat()
    unique = {}
    results = {}
    for s in settlements:
        try:
            record, _ = evidence(s, 'settlement')
            if record['home_goals'] != s['home_goals'] or record['away_goals'] != s['away_goals']:
                continue
            if not all(type(s[k]) is int and s[k] >= 0 for k in ('home_goals','away_goals')):
                continue
            if not utc(s['kickoff_at']) < utc(record['settled_at']) <= utc(now):
                continue
            results.setdefault(s['internal_match_id'], []).append(s)
        except (KeyError, ValueError, TypeError, OSError):
            continue
    for row in rows:
        source = row.get('provenance', {})
        if not accredited(source, now):
            continue
        expected = {r['forecast_id']:r for r in candidates(source, now)}
        if row != expected.get(row.get('forecast_id')):
            continue
        settlements_for_match = results.get(row['internal_match_id'], [])
        if len(settlements_for_match) != 1:
            continue
        s = settlements_for_match[0]
        if any(s.get(k) != row.get(k) for k in (*IDENTITY, 'kickoff_at')):
            continue
        h,a = s['home_goals'], s['away_goals']
        labels = {'Over1.5':h+a>=2,'Over2.5':h+a>=3,'Over3.5':h+a>=4,'BTTS':h>0 and a>0,
                  'HomeWin':h>a,'Draw':h==a,'AwayWin':h<a,'1X':h>=a,'X2':a>=h,'12':h!=a}
        # One prediction per match/model/market; repeated revisions never inflate OOS.
        key = (row['internal_match_id'],row['market'])
        unique.setdefault(key, (row, int(labels[row['market']])))
    by_market = {}
    for market in sorted({k[1] for k in unique}):
        pairs = [(r['probability'],y) for (_,m),(r,y) in unique.items() if m == market]
        n = len(pairs)
        by_market[market] = dict(n=n, brier=sum((p-y)**2 for p,y in pairs)/n,
            log_loss=sum(-math.log(max(1e-15, min(1-1e-15,p)) if y else max(1e-15,1-min(1-1e-15,p))) for p,y in pairs)/n,
            hit_rate=sum((p>=.5)==bool(y) for p,y in pairs)/n)
    matches = len({k[0] for k in unique})
    return dict(forecast_oos_count=matches, forecast_oos_matches=matches, forecast_oos_predictions=len(unique),
                forecast_oos_status='COLLECTING' if unique else 'NO_ACCREDITED_SETTLED_FORECASTS', by_market=by_market)


def generate():
    now = datetime.now(timezone.utc).isoformat()
    groups = []
    for row in sources():
        ranked = candidates(row, now)
        if ranked:
            groups.append(dict(internal_match_id=row['internal_match_id'], ranked_forecast_candidates=ranked))
    flat = [r for g in groups for r in g['ranked_forecast_candidates']]
    with runtime.locked('forecast/journal'):
        path = runtime.safe_path(ROOT/'journal.jsonl')
        existing = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        ids = {r['forecast_id'] for r in existing}
        fresh = [r for r in flat if r['oos_eligible'] and utc(r['kickoff_at']) > utc(now) and r['forecast_id'] not in ids]
        runtime.ensure_safe(fresh)
        with path.open('a') as stream:
            for r in fresh:
                stream.write(json.dumps(r, sort_keys=True, allow_nan=False)+'\n')
            stream.flush()
            os.fsync(stream.fileno())
        stats = oos_report(existing+fresh, load(ROOT/'settlements.json', []), now)
    from .oos import report as betting_report
    betting = betting_report()['real_oos_count']
    result = dict(forecast_generation_status='AVAILABLE' if flat else 'NO_FORECAST_SOURCES',
        matches=groups, forecast_matches=len(groups), forecast_candidates=len(flat),
        accredited_forecasts=sum(r['oos_eligible'] for r in flat), legacy_operational_forecasts=sum(not r['oos_eligible'] for r in flat),
        champion='BT0 / '+CHAMPION, odds_required_for_forecast=False, value_evaluated=False,
        betting_oos_matches=betting, network_calls=0, **stats)
    return runtime.write(ROOT/'latest.json', result)
