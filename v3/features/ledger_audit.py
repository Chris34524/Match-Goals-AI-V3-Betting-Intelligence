"""Read-only local ledger candidates, never authorization to enable features.

python -m v3.features.ledger_audit --source-root data > /tmp/ledger-audit.json
Completeness cannot be inferred from row counts, coverage keys or raw page presence.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from v3.data.builder import dumps, reject_constant, unique_object
from v3.data.validation import day
from v3.features.temporal_context import BLOCKED

RAW_NAMES = frozenset((
    'history.json', 'history_raw.json', 'xg_history.json', 'standings.json',
    'partidos.json', 'partidos_hoy.json', 'partidos_manana.json', 'partidos_candidatos.json',
    'match_detail.txt', 'match_detail.html', 'h2h_page.txt', 'h2h_page.html',
    'flashscore_home.html', 'flashscore_rendered.html', 'date_navigation_inspect.txt',
    'inspect_matches.txt', 'standings_page.txt', 'standings_page.html',
    'standings_rows.txt', 'matches_manana.txt', 'day_selected.json',
))
EVIDENCE_KEY = re.compile(r'ledger|complete|complet|coverage|cobertura|pagination|exhaust|has_more|cursor|team_id|season_id', re.I)


def audit_ledger(source_root):
    root = Path(source_root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('source-root must be a real directory')
    groups, digest = {}, hashlib.sha256()
    objectives, lengths, parsing = Counter(), Counter(), Counter()

    def walk(directory):
        for p in sorted(directory.iterdir()):
            if p.is_symlink():
                continue
            if p.is_dir():
                yield from walk(p)
            elif p.is_file():
                yield p

    for p in walk(root):
        parts = p.relative_to(root).parts
        if not (p.name in RAW_NAMES or parts[0] == 'xg_cache' or p.name.startswith('selected_matches_')):
            continue
        relative = p.relative_to(root).as_posix()
        raw = p.read_bytes()
        digest.update(relative.encode() + b'\0')
        digest.update(hashlib.sha256(raw).digest())
        group = (parts[0] + '/<id>/' + p.name if len(parts) > 2 else
                 'xg_cache/*.json' if parts[0] == 'xg_cache' else
                 'selected_matches_*' + p.suffix if p.name.startswith('selected_matches_') else relative)
        stats = groups.setdefault(group, dict(files=0, bytes=0, invalid_json=0, top_keys=Counter(),
            dated_samples=0, date_min=None, date_max=None, completeness_key_paths=Counter()))
        stats['files'] += 1
        stats['bytes'] += len(raw)
        if p.suffix != '.json':
            text = raw.decode('utf-8', errors='replace')
            stats['pagination_marker_files'] = stats.get('pagination_marker_files', 0) + bool(re.search(r'Mostrar más|Mostrar m|Show more', text, re.I))
            stats['calendar_marker_files'] = stats.get('calendar_marker_files', 0) + bool(re.search(r'calendar|event__match|h2h__row', text, re.I))
            continue
        try:
            obj = json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique_object)
        except (ValueError, UnicodeError):
            stats['invalid_json'] += 1
            continue
        if isinstance(obj, dict):
            stats['top_keys'].update(obj.keys())

        def inspect(obj, path='$'):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if EVIDENCE_KEY.search(key):
                        stats['completeness_key_paths'][path + '/' + key] += 1
                    date = day(value) if key == 'fecha' and isinstance(value, str) else None
                    if date:
                        date = date.isoformat()
                        stats['dated_samples'] += 1
                        stats['date_min'] = min(stats['date_min'] or date, date)
                        stats['date_max'] = max(stats['date_max'] or date, date)
                    inspect(value, path + '/' + key)
            elif isinstance(obj, list):
                for item in obj:
                    inspect(item, path + '/[]')

        inspect(obj)
        if p.name == 'history.json' and parts[0] == 'matches' and isinstance(obj, dict):
            objectives[str(obj.get('objetivo_partidos'))] += 1
            sections = obj.get('secciones')
            for section in sections if isinstance(sections, list) else []:
                if not isinstance(section, dict) or not str(section.get('titulo', '')).casefold().startswith('últimos partidos: '):
                    continue
                samples = section.get('partidos')
                if isinstance(samples, list):
                    lengths[str(len(samples))] += 1
                    parsing['team_sections'] += 1
                    parsing['rows'] += len(samples)
                    parsing['sections_with_unparsed_rows'] += any(not isinstance(s, dict) or s.get('resultado_parseado') is not True for s in samples)
    return dict(audit_version='2.4.0', candidate_files=sum(g['files'] for g in groups.values()),
        candidate_sha256=digest.hexdigest(), groups=groups,
        history_objectives=dict(objectives), history_section_lengths=dict(lengths), history_parsing=dict(parsing),
        decisions={name: dict(status='blocked', reason=reason) for name, reason in BLOCKED.items()},
        limitations=[
            'Only raw candidate files are read; operational outputs are excluded.',
            'Key paths and date ranges are discovery evidence, not accredited completeness.',
            'Raw HTML/text markers do not prove pagination exhaustion or all-competition coverage.',
            'Dates use the shared day parser, including its two-digit-year interpretation; ranges are not certified coverage.',
            'No local completeness attestation or validated fixture-ledger adapter exists; arbitrary complete flags do not enable features.',
        ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', default='data')
    args = parser.parse_args()
    print(dumps(audit_ledger(args.source_root)))


if __name__ == '__main__':
    main()
