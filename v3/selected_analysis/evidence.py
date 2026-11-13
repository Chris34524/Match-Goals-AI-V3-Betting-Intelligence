"""Read-only legacy form and strict FS capability history adapters."""
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

from analysis.enrich_match import calcular_ventanas_equipo
from v3.data.builder import reject_constant, unique_object
from v3.features.history_adapter import target_metadata, team_history
from v3.features.h2h import materialize as h2h_features
from v3.flashscore.contract import Capability, Fixture, State, dumps, timestamp
from v3.flashscore.observation_index import ObservationIndex, operand_key, provenance
from v3.data.validation import day

ROOT = Path(__file__).resolve().parents[2]


def read_json(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlink_evidence_forbidden')
    raw = path.read_bytes()
    credential = os.environ.get('API_FOOTBALL_KEY')
    if credential and (credential.encode() in raw or credential in str(path)):
        raise ValueError('credential_in_evidence_forbidden')
    value = json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique_object)
    return value, dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), captured_at=None)


def cutoff_for(fixture, cutoff=None):
    if cutoff is None:
        # A conservative calendar boundary is a feature cutoff, never an inferred kickoff.
        cutoff = datetime.fromisoformat(fixture['date']).replace(
            tzinfo=ZoneInfo(fixture['timezone'])).isoformat()
        if fixture['kickoff'] and timestamp(cutoff) >= timestamp(fixture['kickoff']):
            cutoff = (timestamp(fixture['kickoff'])-timedelta(microseconds=1)).isoformat()
    limit = timestamp(cutoff)
    if limit.astimezone(ZoneInfo(fixture['timezone'])).date().isoformat() > fixture['date']:
        raise ValueError('cutoff_after_target_date')
    if fixture['kickoff'] and limit >= timestamp(fixture['kickoff']):
        raise ValueError('cutoff_must_precede_kickoff')
    return limit.isoformat()


def legacy(fixture, root, cutoff):
    sources, warnings, samples, exclusions, observed = [], [], {}, {}, {}
    if fixture['provider'] != 'flashscore':
        return dict(samples={}, exclusions={}, observed={}, h2h=None, sources=[],
                    warnings=['Legacy Flashscore history cannot be assigned to another provider.'])
    path = Path(root)/fixture['provider_fixture_id']/'history.json'
    if not path.exists():
        return dict(samples={}, exclusions={}, observed={}, h2h=None, sources=[], warnings=['missing_history'])
    history, source = read_json(path)
    metadata, error = target_metadata(history, fixture['provider_fixture_id'])
    if error or any(metadata[s] != fixture[s]['name'] for s in ('home', 'away')) or metadata['date'] != fixture['date']:
        raise ValueError('legacy_fixture_identity_conflict')
    sources.append(source)
    cutoff_day = timestamp(cutoff).astimezone(ZoneInfo(fixture['timezone'])).date().isoformat()
    metadata = dict(metadata, date=min(metadata['date'], cutoff_day))
    for side, label, venue in (('home', 'local', 'local'), ('away', 'visitante', 'visitante')):
        valid, excluded, section_error = team_history(history, fixture['provider_fixture_id'], metadata, side)
        samples[side], exclusions[side] = valid[:20], excluded
        if section_error:
            warnings.append(side+':'+section_error)
        prepared = [dict(s, gc=s['ga'], total_goles=s['gf']+s['ga'],
                         condicion='local' if s['venue'] == 'home' else 'visitante') for s in valid[:20]]
        observed[side] = dict(equipo=fixture[side]['name'], **calcular_ventanas_equipo(prepared, venue))
        for key, stats in observed[side].items():
            if isinstance(stats, dict):
                stats['requested_n'] = int(key[1:]) if key.startswith('l') else None
                stats['partial_sample'] = key.startswith('l') and stats['pj'] < int(key[1:])
                if stats['pj'] == 0:
                    for k in ('gf', 'gc', 'victorias', 'empates', 'derrotas'):
                        stats[k] = None
    # Existing H2H grammar and duplicate gates, with the same conservative cutoff.
    bounded = dict(history, partido=dict(history['partido'], fecha=metadata['date']))
    h2h = h2h_features(bounded, fixture['provider_fixture_id'])
    warnings.append('Date-filtered legacy scores have no independently verified publication/revision lineage; OOS excluded.')
    return dict(samples=samples, exclusions=exclusions, observed=observed, h2h=h2h,
                sources=sources, warnings=warnings)


def champion(fixture, form, xg=None):
    """Run the unchanged legacy formula in an ephemeral isolated working directory.

    No scraper, standing table, cached prediction or result is executed/consumed.
    Only vetted summaries and independently eligible optional xG are supplied.
    """
    if not form['observed']:
        return {}, None
    enriched = dict(match_id=fixture['provider_fixture_id'],
        partido=dict(id=fixture['provider_fixture_id'], fecha=fixture['date'],
                     local=fixture['home']['name'], visitante=fixture['away']['name']),
        datos_observados=dict(local=form['observed']['home'], visitante=form['observed']['away'],
                             temporada=dict(local=None, visitante=None)))
    xg = xg or dict(local=dict(partidos=[]), visitante=dict(partidos=[]))
    with tempfile.TemporaryDirectory(prefix='selected-champion-') as temporary:
        directory = Path(temporary)/'data/matches'/fixture['provider_fixture_id']
        directory.mkdir(parents=True)
        for name, value in (('enriched', enriched), ('xg_history', xg), ('h2h_analysis', {})):
            (directory/(name+'.json')).write_text(dumps(value), encoding='utf-8')
        env = dict(os.environ, PYTHONPATH=str(ROOT)+os.pathsep+os.environ.get('PYTHONPATH', ''))
        run = subprocess.run([sys.executable, '-W', 'error', '-m', 'analysis.compare_lambda',
                              '--match-id', fixture['provider_fixture_id']],
                             cwd=temporary, env=env, capture_output=True, text=True, timeout=30)
        if run.returncode:
            raise ValueError('isolated_champion_comparison_failed')
        comparison = json.loads((directory/'lambda_comparison.json').read_text(encoding='utf-8'))
    return comparison['metodos'], hashlib.sha256((ROOT/'analysis/compare_lambda.py').read_bytes()).hexdigest()


def target_fixture(fixture):
    if not all(fixture[s]['id'] for s in ('home', 'away')) or not fixture['competition_id'] or not fixture['season']:
        return None
    return Fixture(fixture['provider'], fixture['provider_fixture_id'], fixture['competition_id'],
                   fixture['season'], 'selected', 'scheduled', fixture['home']['id'], fixture['away']['id'],
                   fixture['date'])


def observations(paths):
    result, sources = [], []
    for path in paths:
        value, source = read_json(path)
        if isinstance(value, dict) and value.get('schema_version') == 'fs-replay-batch-1':
            from v3.flashscore.replay import replay_document
            result.extend(replay_document(value))
        elif isinstance(value, list):
            result.extend(Capability.from_dict(item) for item in value)
        else:
            raise ValueError('capabilities_array_or_structured_replay_required')
        sources.append(source)
    return ObservationIndex(result), sources


def series(index, target, cutoff, side, metric, period, *, against=False, window=20,
           scope='overall', card_policy=None):
    """Never skip missing recent operands to backfill older complete fixtures."""
    if target is None:
        return dict(status='BLOCKED', reason='stable_team_competition_season_ids_required', values=[],
                    provenance=[], dates=[], n_selected=0, coverage=None, scope=scope)
    team = getattr(target, side+'_id')
    boundary = min(day(target.match_date), timestamp(cutoff).date())
    history = [f for f in index.by_team.get((target.provider, team), ())
               if day(f.match_date) and day(f.match_date) < boundary and f.match_id != target.match_id
               and f.lifecycle == 'finished' and (scope == 'overall' or getattr(f, scope+'_id') == team)]
    history.sort(key=lambda f: (-day(f.match_date).toordinal(), f.match_id))
    selected = history[:window]
    values, sources, dates, failures, components, used = [], [], [], [], [], []
    for f in selected:
        source_side = 'home' if f.home_id == team else 'away'
        if against:
            source_side = 'away' if source_side == 'home' else 'home'
        c, reason = index.select(operand_key(f, metric, period, source_side), cutoff)
        if c is None:
            failures.append(reason)
            continue
        sources.append(provenance(c))
        if c.state != State.AVAILABLE:
            failures.append(c.state.value)
        elif c.evidence.acquisition_authorization != 'verified':
            failures.append('acquisition_not_verified')
        elif not c.prematch_usable(target.match_id, target.match_date, cutoff):
            failures.append('temporal_ineligible')
        elif metric == 'cards' and (card_policy is None or not card_policy.compatible(c)):
            failures.append('incompatible_card_semantics')
        else:
            values.append(card_policy.count(c.evidence.value) if metric == 'cards' else c.evidence.value)
            components.append(c.evidence.value)
            dates.append(f.match_date)
            used.append(dict(match_id=f.match_id, date=f.match_date, value=values[-1],
                             venue='home' if f.home_id == team else 'away',
                             entity_id=c.request.entity_id))
    n = len(selected)
    reason = ','.join(sorted(set(failures))) or ('insufficient_history' if n < 5 else None)
    state = ('BLOCKED' if any(r in ('incompatible_card_semantics', 'acquisition_not_verified',
                                  'temporal_ineligible', 'BLOCKED', 'conflicting_latest_observations')
                                for r in failures) else 'NOT_COVERED' if 'NOT_COVERED' in failures
             else 'INSUFFICIENT_DATA' if reason else 'EXPERIMENTAL')
    return dict(status=state, reason=reason, values=values, components=components, samples=used, provenance=sources,
                dates=dates, n_selected=n, coverage=len(values)/n if n else None, scope=scope,
                excluded_target=True, window=window, partial_sample=n < window)
