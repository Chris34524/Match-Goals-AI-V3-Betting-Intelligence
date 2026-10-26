"""Allowlisted history evidence; no operational results or model inputs."""
from collections import Counter
import json

from v3.data.builder import reject_constant, unique_object
from v3.data.temporal import sample_reasons
from v3.data.validation import day


def read_history(folder):
    path = folder / 'history.json'
    try:
        if folder.is_symlink() or path.is_symlink():
            raise ValueError('symlink source')
        raw = path.read_bytes()
        obj = json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique_object)
        if not isinstance(obj, dict):
            raise ValueError('expected object')
        return obj, raw, None
    except (OSError, ValueError, UnicodeError):
        return {}, None, 'missing_or_invalid_history'


def target_metadata(history, target_id):
    target = history.get('partido')
    if not isinstance(target, dict):
        return {}, 'invalid_target'
    identities = [history.get('match_id'), target.get('id'), target.get('match_id')]
    teams = [target.get(k) for k in ('local', 'visitante')]
    if (any(i is not None and i != target_id for i in identities)
            or not day(target.get('fecha'))
            or not all(isinstance(t, str) and t.strip() for t in teams)
            or teams[0] == teams[1]):
        return {}, 'invalid_target'
    return dict(date=day(target['fecha']).isoformat(), home=teams[0], away=teams[1]), None


def regulation_evidence(sample):
    """Accept explicit regulation scope or exact ordinary Flashscore row grammar.

    The legacy parser alone is insufficient: it also parses shootouts and can
    skip extra-time markers. Unknown/annotated row shapes fail closed.
    """
    if (sample.get('decidido_penales') not in (None, False)
            or any(sample.get(k) is not None for k in ('penales_local', 'penales_visitante'))):
        return None
    scope = sample.get('score_scope')
    if scope is not None:
        return 'explicit_REGULATION' if scope == 'REGULATION' else None
    lines = sample.get('lineas_raw')
    expected = [sample.get('fecha'), sample.get('competicion_codigo'),
                sample.get('local'), sample.get('visitante'),
                str(sample.get('goles_local')), str(sample.get('goles_visitante'))]
    if (isinstance(lines, list) and len(lines) == 7 and lines[:6] == expected
            and all(isinstance(x, str) and x for x in expected)
            and lines[6] in ('G', 'E', 'P')):
        return 'flashscore_ordinary_row_v1'
    return None


def team_history(history, target_id, metadata, side):
    sections = history.get('secciones')
    if not isinstance(sections, list):
        return [], [], 'invalid_history_sections'
    matched = [s for s in sections if isinstance(s, dict)
               and isinstance(s.get('titulo'), str)
               and s['titulo'].casefold() == 'últimos partidos: ' + metadata[side].casefold()]
    if len(matched) != 1 or not isinstance(matched[0].get('partidos'), list):
        return [], [], 'missing_or_ambiguous_team_section'
    samples = matched[0]['partidos']
    ids = Counter(s.get('match_id') for s in samples if isinstance(s, dict)
                  and isinstance(s.get('match_id'), str))
    valid, excluded = [], []
    for s in samples:
        if not isinstance(s, dict):
            excluded.append(dict(match_id=None, date=None, reasons=['invalid_sample']))
            continue
        sid = s.get('match_id')
        reasons = sample_reasons(target_id, metadata['date'], sid, s.get('fecha'))
        if isinstance(sid, str) and ids[sid] > 1:
            reasons.append('duplicate_match_id')  # Exclude ALL copies, including conflicts.
        teams = (s.get('local'), s.get('visitante'))
        if (not all(isinstance(t, str) and t.strip() for t in teams)
                or teams[0] == teams[1] or metadata[side] not in teams):
            reasons.append('team_conflict')
        if s.get('resultado_parseado') is not True or not all(
                type(s.get(k)) is int and s[k] >= 0 for k in ('goles_local', 'goles_visitante')):
            reasons.append('invalid_score')
        scope = regulation_evidence(s)
        if scope is None:
            reasons.append('unverified_regulation_scope')
        if reasons:
            excluded.append(dict(match_id=sid if isinstance(sid, str) else None,
                                 date=day(s.get('fecha')).isoformat() if day(s.get('fecha')) else None,
                                 reasons=sorted(set(reasons))))
            continue
        home = s['local'] == metadata[side]
        valid.append(dict(match_id=sid, date=day(s['fecha']).isoformat(),
                          venue='home' if home else 'away',
                          gf=s['goles_local' if home else 'goles_visitante'],
                          ga=s['goles_visitante' if home else 'goles_local'],
                          score_evidence=scope))
    valid.sort(key=lambda s: (-day(s['date']).toordinal(), s['match_id']))
    excluded.sort(key=lambda s: json.dumps(s, sort_keys=True))
    return valid, excluded, None
