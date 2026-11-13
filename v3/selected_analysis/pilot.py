"""Two-fixture offline pilot with real-clock input sealing and deterministic replay.

This is a separate operational record, never an OOS journal or acquisition grant.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sys

from v3.flashscore.contract import dumps, timestamp
from v3.flashscore.market_contract import CardSettlementPolicy
from . import fixtures
from .engine import analyze
from .evidence import ROOT, read_json, observations
from .market_matrix import build as market_matrix
from .report import destination, esc, table, write, reason as human_reason

VERSION = 'selected-two-fixture-pilot-1'
DEFAULT_ROOT = Path('v3_data/selected_analysis/pilots')


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(dumps(value).encode()).hexdigest()


def immutable(path, content):
    path = destination(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    raw = content.encode('utf-8') if isinstance(content,str) else content
    if path.exists():
        if path.is_symlink() or path.read_bytes()!=raw:
            raise ValueError('immutable_pilot_conflict')
    else:
        with path.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            import os
            os.fsync(stream.fileno())
    return path


def scheduled(fixture, document, as_of):
    """A reviewed schedule corroborates time; it does not accredit OOS lineage."""
    if not isinstance(document,dict) or document.get('schema_version')!='pilot-schedule-review-1' or type(document.get('synthetic_test_only')) is not bool:
        raise ValueError('schedule_review_contract_required')
    records = document.get('records',[])
    matches = [r for r in records if isinstance(r,dict) and r.get('provider')==fixture['provider']
               and r.get('provider_fixture_id')==fixture['provider_fixture_id']]
    if len(matches)!=1:
        raise ValueError('unique_schedule_review_required')
    record = matches[0]
    identity = dict(home=fixture['home']['name'],away=fixture['away']['name'],
                    date=fixture['date'],competition=fixture['competition'])
    if record.get('identity')!=identity or record.get('timezone')!=fixture['timezone']:
        raise ValueError('schedule_identity_conflict')
    kickoff,reviewed = timestamp(record['kickoff_at']),timestamp(record['reviewed_at'])
    if record.get('timezone_basis') not in ('explicit_central_mexico','venue_local_time_review','explicit_utc_offset'):
        raise ValueError('schedule_timezone_evidence_required')
    from zoneinfo import ZoneInfo
    local = kickoff.astimezone(ZoneInfo(fixture['timezone']))
    if local.date().isoformat()!=fixture['date'] or reviewed>timestamp(as_of) or reviewed>=kickoff:
        raise ValueError('schedule_review_temporal_conflict')
    if fixture.get('kickoff') and timestamp(fixture['kickoff'])!=kickoff:
        raise ValueError('schedule_kickoff_conflict')
    if fixture.get('display_time') and fixture['display_time']!=local.strftime('%H:%M'):
        raise ValueError('schedule_display_time_conflict')
    supports = record.get('supporting_sources')
    if not isinstance(supports,list) or not supports or any(
            not isinstance(s,dict) or not isinstance(s.get('url'),str) or not s['url'].startswith('https://')
            or not s.get('claim') or not s.get('evidence_method') for s in supports):
        raise ValueError('independent_schedule_sources_required')
    lifecycle = fixture.get('source_lifecycle')
    if lifecycle not in (None,'NS','TBD','scheduled','Programado','No comenzado'):
        raise ValueError('pilot_requires_scheduled_fixture')
    if kickoff<=timestamp(as_of):
        raise ValueError('pilot_requires_future_fixture')
    result = dict(fixture,kickoff=record['kickoff_at'],display_time=local.strftime('%H:%M'),
                  schedule_status='PUBLIC_SCHEDULE_CORROBORATED_NOT_OOS')
    return result,record


def _materialize_report(manifest, directory, fixture):
    paths = [directory/p for p in manifest['capability_paths']]
    index,_ = observations(paths)
    if any(timestamp(c.evidence.observed_at)>timestamp(manifest['cutoff'])
           for group in index.by_key.values() for c in group):
        raise ValueError('pilot_observation_after_freeze')
    policy_path = manifest.get('card_policy_path')
    card_policy = CardSettlementPolicy(**read_json(directory/policy_path)[0]) if policy_path else None
    report = analyze(fixture,history_root=directory/'inputs/matches',
        capability_paths=paths,
        cutoff=manifest['cutoff'],generated_at=manifest['generated_at'],card_policy=card_policy)
    if report['synthetic_test_only'] and not manifest['synthetic_test_only']:
        raise ValueError('synthetic_input_in_real_pilot')
    report['pilot'] = dict(pilot_id=manifest['pilot_id'],sealed_at=manifest['sealed_at'],
        input_manifest_sha256=manifest['input_manifest_sha256'],
        schedule_status=fixture['schedule_status'],schedule_evidence_path=str(directory/'inputs/schedule.json'),
        local_integrity_only=True,oos_eligible=False)
    report['analysis_mode'] = 'OPERATIONAL_PREMATCH_FROZEN_NOT_OOS'
    report['market_matrix'] = market_matrix(report)
    for row in report['market_matrix']:
        row['input_availability'] = 'LOCAL_BYTES_SEALED_BEFORE_KICKOFF'
    report['analysis_id'] = digest({k:v for k,v in report.items() if k!='analysis_id'})
    return report


def run(source, schedule, *, date, ids=(), indices=None, provider='flashscore',
        history_root=ROOT/'data/matches', capability_paths=(), output=DEFAULT_ROOT,
        timezone_name=fixtures.TIMEZONE, clock=None, synthetic_test_only=False, card_policy_path=None):
    if clock is not None and not synthetic_test_only:
        raise ValueError('test_clock_requires_synthetic_test_only')
    clock = clock or now
    started = clock()
    buffers,snapshot,missing = {},{},[]

    def collect(relative, original):
        value,receipt = read_json(original)
        raw = Path(original).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=receipt['sha256']:
            raise ValueError('source_changed_during_freeze')
        buffers[relative] = raw
        snapshot[relative] = dict(original_path=str(Path(original).absolute()),sha256=receipt['sha256'],
                                  bytes=len(raw),locally_read_at=clock(),source_captured_at=None)
        return value

    universe = collect('inputs/fixture_universe.json',source)
    schedule_document = collect('inputs/schedule.json',schedule)
    if not isinstance(schedule_document,dict) or schedule_document.get('synthetic_test_only') is not synthetic_test_only:
        raise ValueError('pilot_schedule_origin_mismatch')
    excluded = []
    rows = fixtures.universe(fixtures.rows_from_document(universe),provider,timezone_name,exclusions=excluded)
    rows = fixtures.filtered(rows,fixtures.resolve_date(date,timezone_name))
    if not indices and not ids:
        if not sys.stdin.isatty():
            raise ValueError('explicit_two_fixture_selection_required')
        for i,row in enumerate(rows,1):
            print(f"{i:02}. {row['home']['name']} vs {row['away']['name']} | {row['provider_fixture_id']}")
        indices = input('Selecciona exactamente dos partidos: ')
    selected = fixtures.choose(rows,indices,ids,limit=2)
    if len(selected)!=2:
        raise ValueError('pilot_requires_exactly_two_unique_fixtures')
    if any(f.get('synthetic_test_only') is True for f in selected) and not synthetic_test_only:
        raise ValueError('synthetic_input_in_real_pilot')
    selected = [scheduled(f,schedule_document,clock())[0] for f in selected]
    cache_ids = set()
    for fixture in selected:
        mid = fixture['provider_fixture_id']
        if provider=='flashscore':
            for name in ('history.json','xg_history.json','standings.json','lambda_comparison.json'):
                original = Path(history_root)/mid/name
                if original.exists():
                    value = collect(f'inputs/matches/{mid}/{name}',original)
                    if name=='xg_history.json':
                        for side in ('local','visitante'):
                            block = value.get(side,{}) if isinstance(value,dict) else {}
                            for row in block.get('partidos',[]) if isinstance(block,dict) else []:
                                sid = row.get('match_id') if isinstance(row,dict) else None
                                if isinstance(sid,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}',sid):
                                    cache_ids.add(sid)
                else:
                    missing.append(f'inputs/matches/{mid}/{name}')
    for sid in sorted(cache_ids):
        original = Path(history_root).parent/'xg_cache'/(sid+'.json')
        if original.exists():
            collect(f'inputs/xg_cache/{sid}.json',original)
        else:
            missing.append(f'inputs/xg_cache/{sid}.json')
    cap_paths = []
    for i,path in enumerate(capability_paths):
        relative = f'inputs/capabilities/{i:03}.json'
        collect(relative,path)
        cap_paths.append(relative)
    policy_path = None
    if card_policy_path is not None:
        policy_path = 'inputs/card_policy.json'
        CardSettlementPolicy(**collect(policy_path,card_policy_path))
    pilot_id = digest(dict(started_at=started,files=snapshot,fixtures=selected,synthetic_test_only=synthetic_test_only))
    directory = destination(Path(output)/pilot_id)
    if directory.exists():
        raise ValueError('pilot_directory_already_exists')
    directory.mkdir(parents=True)
    for relative,raw in buffers.items():
        immutable(directory/relative,raw)
    sealed = clock()
    if timestamp(sealed)<timestamp(started) or any(timestamp(s['locally_read_at'])>timestamp(sealed) for s in snapshot.values()):
        raise ValueError('pilot_clock_not_monotonic')
    if any(timestamp(sealed)>=timestamp(f['kickoff']) for f in selected):
        raise ValueError('pilot_seal_not_prematch')
    manifest = dict(schema_version=VERSION,pilot_id=pilot_id,synthetic_test_only=synthetic_test_only,
        started_at=started,sealed_at=sealed,cutoff=sealed,generated_at=clock(),
        fixtures=selected,snapshot_files=snapshot,missing_sources=missing,
        capability_paths=cap_paths,card_policy_path=policy_path,excluded_fixture_conflicts=excluded,
        decision='NO_BET',oos_eligible=False,network_requests=0,
        limitations=['Local input integrity is not independent OOS accreditation.',
                     'Legacy xG period/publication/revision lineage stays unverified.',
                     'No automatic provider fallback or cross-provider name matching.'])
    if timestamp(manifest['generated_at'])<timestamp(sealed):
        raise ValueError('pilot_clock_not_monotonic')
    manifest['input_manifest_sha256'] = digest(dict(files=snapshot,sealed_at=sealed,fixtures=selected))
    immutable(directory/'input-manifest.json',dumps(manifest)+'\n')
    reports = []
    for fixture in selected:
        report = _materialize_report(manifest,directory,fixture)
        path = write(report,directory/'reports')
        reports.append(dict(provider=fixture['provider'],match_id=fixture['provider_fixture_id'],
            json=str((path/'report.json').relative_to(directory)),
            html=str((path/'report.html').relative_to(directory)),
            json_sha256=hashlib.sha256((path/'report.json').read_bytes()).hexdigest(),
            html_sha256=hashlib.sha256((path/'report.html').read_bytes()).hexdigest(),
            implementation_sha256=report['implementation_sha256'],market_matrix=report['market_matrix']))
    finished = clock()
    if timestamp(finished)<timestamp(manifest['generated_at']) or any(
            timestamp(finished)>=timestamp(f['kickoff']) for f in selected):
        raise ValueError('pilot_generation_not_prematch')
    result = dict(manifest,finished_at=finished,status='SYNTHETIC_TEST_ONLY' if synthetic_test_only else 'PREMATCH_FROZEN_OPERATIONAL',
                  reports=reports)
    immutable(directory/'pilot.json',dumps(result)+'\n')
    immutable(directory/'index.html',index_html(result))
    return directory,result


def replay(directory):
    directory = destination(directory)
    manifest,_ = read_json(directory/'pilot.json')
    initial,_ = read_json(directory/'input-manifest.json')
    if manifest.get('schema_version')!=VERSION or any(manifest.get(k)!=v for k,v in initial.items()):
        raise ValueError('pilot_manifest_conflict')
    if len(manifest['fixtures'])!=2 or not (timestamp(manifest['sealed_at'])==timestamp(manifest['cutoff'])
            <=timestamp(manifest['generated_at'])<=timestamp(manifest['finished_at'])) or any(
            timestamp(manifest['finished_at'])>=timestamp(f['kickoff']) for f in manifest['fixtures']):
        raise ValueError('pilot_timing_invalid')
    if digest(dict(files=manifest['snapshot_files'],sealed_at=manifest['sealed_at'],fixtures=manifest['fixtures']))!=manifest['input_manifest_sha256']:
        raise ValueError('pilot_input_manifest_digest')
    actual = {str(p.relative_to(directory)) for p in (directory/'inputs').rglob('*') if p.is_file()}
    if actual!=set(manifest['snapshot_files']):
        raise ValueError('pilot_snapshot_inventory_changed')
    for relative,record in manifest['snapshot_files'].items():
        path = destination(directory/relative)
        if not path.resolve().is_relative_to((directory/'inputs').resolve()):
            raise ValueError('pilot_snapshot_path_escape')
        _,receipt = read_json(path)
        if receipt['sha256']!=record['sha256']:
            raise ValueError('pilot_snapshot_digest_mismatch')
    expected = {(r['provider'],r['match_id']):r for r in manifest['reports']}
    for fixture in manifest['fixtures']:
        saved = expected[(fixture['provider'],fixture['provider_fixture_id'])]
        report = _materialize_report(initial,directory,fixture)
        if report['implementation_sha256']!=saved['implementation_sha256']:
            raise ValueError('pilot_implementation_changed')
        raw = (dumps(report)+'\n').encode()
        if hashlib.sha256(raw).hexdigest()!=saved['json_sha256']:
            raise ValueError('pilot_replay_prediction_mismatch')
        for kind in ('json','html'):
            path = destination(directory/saved[kind])
            if not path.resolve().is_relative_to(directory.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=saved[kind+'_sha256']:
                raise ValueError('pilot_report_digest_mismatch')
    return dict(status='REPLAY_PASS',pilot_id=manifest['pilot_id'],matches=len(manifest['fixtures']),
                original_cutoff=manifest['cutoff'],network_requests=0,oos_eligible=False)


def index_html(manifest):
    rows = []
    for fixture,report in zip(manifest['fixtures'],manifest['reports']):
        for row in report['market_matrix']:
            rows.append((fixture['home']['name']+' vs '+fixture['away']['name'],row['market'],row['status'],
                         str(row['sample_size']),f"{row['coverage']:.0%}" if isinstance(row['coverage'],(float,int)) else 'N/D',
                         human_reason(row['reason'])))
    links = ''.join('<li><a href="'+esc(r['html'])+'">'+esc(f['home']['name']+' vs '+f['away']['name'])+'</a></li>'
                    for f,r in zip(manifest['fixtures'],manifest['reports']))
    return '<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+(
        '<title>Piloto multimercado · Match Goals AI</title><style>body{background:#0c1421;color:#eaf2ff;font:16px/1.5 system-ui;max-width:1250px;margin:auto;padding:24px;overflow-wrap:anywhere}a{color:#5ae1bd}.scroll{overflow:auto}table{border-collapse:collapse;width:100%}td,th{padding:12px;text-align:left;border-bottom:1px solid #304158;min-width:100px}td:nth-child(3),th:nth-child(3){white-space:nowrap;min-width:150px}h1{font-size:30px}p{color:#b2c6df}</style>')+(
        '<h1>Piloto de dos partidos · NO_BET</h1><p>Flashscore México como referencia principal. Registro operacional prepartido; OOS excluido.</p>')+(
        '<p>Corte congelado: '+esc(manifest['cutoff'])+'</p><ul>')+links+'</ul>'+table(
            ('Partido','Mercado','Estado','n por equipo','Cobertura','Motivo'),rows)+'</html>'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    p = sub.add_parser('run')
    p.add_argument('--source',type=Path,default=ROOT/'data/partidos.json')
    p.add_argument('--schedule',type=Path,required=True)
    p.add_argument('--date',default='today')
    p.add_argument('--match-id',action='append',default=[])
    p.add_argument('--indices')
    p.add_argument('--provider',choices=('flashscore','api_football'),default='flashscore')
    p.add_argument('--history-root',type=Path,default=ROOT/'data/matches')
    p.add_argument('--capabilities',type=Path,action='append',default=[])
    p.add_argument('--card-policy',type=Path)
    p.add_argument('--output',type=Path,default=DEFAULT_ROOT)
    p = sub.add_parser('replay')
    p.add_argument('directory',type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command=='replay':
            print(dumps(replay(args.directory)))
        else:
            directory,result = run(args.source,args.schedule,date=args.date,ids=args.match_id,
                indices=args.indices,provider=args.provider,history_root=args.history_root,
                capability_paths=args.capabilities,card_policy_path=args.card_policy,output=args.output)
            print(dumps(dict(status=result['status'],pilot=str(directory/'pilot.json'),
                             index=str(directory/'index.html'),cutoff=result['cutoff'],reports=result['reports'])))
        return 0
    except (ValueError,KeyError,TypeError,OSError):
        print(dumps(dict(status='BLOCKED_INVALID_PILOT_CONFIGURATION_OR_EVIDENCE',network_requests=0)))
        return 2


if __name__=='__main__':
    raise SystemExit(main())
