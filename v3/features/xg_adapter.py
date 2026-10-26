"""Fail-closed raw xG reconciliation, independent of the form engine.

Availability attestations are supplied by a trusted caller, never inferred from
raw presence, kickoff, mtime or an unverified timestamp embedded in a record.
The local build has no accredited publication/revision source and supplies none.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import math

from v3.data.builder import dumps
from v3.data.temporal import sample_reasons
from v3.data.validation import day
from v3.features.history_adapter import target_metadata


def numeric(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def identity(row):
    return (row.get('match_id'), day(row.get('fecha')), row.get('local'), row.get('visitante'))


def value_digest(row):
    """Bind an independently verified capture to the exact identity and pair."""
    return hashlib.sha256(dumps(dict(zip(
        ('match_id', 'date', 'home', 'away', 'xg_home', 'xg_away'),
        (row.get('match_id'), day(row.get('fecha')).isoformat() if day(row.get('fecha')) else None,
         row.get('local'), row.get('visitante'), row.get('xg_local'), row.get('xg_visitante'))))).encode()).hexdigest()


def accredited(row, metadata, attestations):
    try:
        attestation = attestations.get(row.get('match_id'), {})
        observed = datetime.fromisoformat(attestation['observed_at'].replace('Z', '+00:00'))
        cutoff = datetime.fromisoformat(metadata['date']).replace(tzinfo=timezone.utc)
        # Require an earlier calendar day as well; target timezone is unverified.
        return (observed.tzinfo is not None and observed.date() < day(metadata['date'])
                and observed < cutoff and observed.date() >= day(row.get('fecha'))
                and attestation['value_sha256'] == value_digest(row)
                and isinstance(attestation['source_artifact'], str)
                and bool(attestation['source_artifact'].strip()))
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def reconcile(history, xg, cache, target_id, *, attestations=None):
    """Return both sides with exclusions; cache is keyed by file stem.

    Exact cross-source copies collapse; repeated IDs within a section and any
    identity/value disagreement poison the ID. Missing pairs remain evidence.
    """
    metadata, target_error = target_metadata(history, target_id)
    results = {}
    sections = history.get('secciones', [])
    ledger = defaultdict(list)
    for section in sections if isinstance(sections, list) else []:
        if isinstance(section, dict) and isinstance(section.get('partidos'), list):
            for row in section['partidos']:
                if isinstance(row, dict) and isinstance(row.get('match_id'), str):
                    ledger[row['match_id']].append(row)
    xg_peers = defaultdict(list)
    for key in ('local', 'visitante'):
        section = xg.get(key, {}) if isinstance(xg, dict) else {}
        rows = section.get('partidos', []) if isinstance(section, dict) else []
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict) and isinstance(row.get('match_id'), str):
                xg_peers[row['match_id']].append(row)
    for side, raw_side in (('home', 'local'), ('away', 'visitante')):
        section = xg.get(raw_side, {}) if isinstance(xg, dict) else {}
        rows = section.get('partidos') if isinstance(section, dict) else None
        error = target_error
        if not isinstance(rows, list):
            error = error or 'missing_or_invalid_xg_section'
            rows = []
        if not error and (xg.get('match_id') != target_id
                         or section.get('equipo') != metadata[side]
                         or not isinstance(xg.get('partido'), dict)
                         or any(xg.get('partido', {}).get(k) != metadata[v]
                                for k, v in (('local', 'home'), ('visitante', 'away')))):
            error = 'target_identity_conflict'
        counts = Counter(r.get('match_id') for r in rows if isinstance(r, dict) and isinstance(r.get('match_id'), str))
        accepted, exclusions = [], []
        for row in rows:
            if not isinstance(row, dict):
                exclusions.append(dict(match_id=None, reasons=['invalid_sample'], source_artifact=f'matches/{target_id}/xg_history.json'))
                continue
            sid = row.get('match_id')
            reasons = sample_reasons(target_id, metadata.get('date'), sid, row.get('fecha'))
            sources = [f'matches/{target_id}/xg_history.json']
            if error:
                reasons.append(error)
            if isinstance(sid, str) and counts[sid] > 1:
                reasons.append('duplicate_match_id')
            peers = ledger.get(sid, []) if isinstance(sid, str) else []
            if not peers or any(identity(r) != identity(row) for r in peers):
                reasons.append('unreconciled_history_identity')
            if isinstance(sid, str) and any(
                    identity(p) != identity(row) or any(p.get(k) != row.get(k)
                    for k in ('xg_local', 'xg_visitante')) for p in xg_peers[sid]):
                reasons.append('conflicting_xg_identity_or_value')
            teams = (row.get('local'), row.get('visitante'))
            team = metadata.get(side)
            home = teams[0] == team
            if (not all(isinstance(t, str) and t.strip() for t in teams)
                    or teams[0] == teams[1] or team not in teams
                    or row.get('equipo') != team
                    or row.get('condicion_equipo') != ('local' if home else 'visitante')):
                reasons.append('team_orientation_conflict')
            pair = (row.get('xg_local'), row.get('xg_visitante'))
            if not all(numeric(v) for v in pair):
                reasons.append('invalid_or_incomplete_bilateral_xg')
            else:
                if (row.get('xgf') != pair[0 if home else 1]
                        or row.get('xga') != pair[1 if home else 0]
                        or not numeric(row.get('xgf')) or not numeric(row.get('xga'))):
                    reasons.append('oriented_value_conflict')
            cached = cache.get(sid) if isinstance(sid, str) else None
            if cached is not None:
                sources.append(f'xg_cache/{sid}.json')
                if (not isinstance(cached, dict) or identity(cached) != identity(row)
                        or any(type(cached.get(k)) is bool or cached.get(k) != row.get(k)
                               for k in ('xg_local', 'xg_visitante'))):
                    reasons.append('cache_identity_or_value_conflict')
            if not accredited(row, metadata, attestations or {}):
                reasons.append('unverified_pre_target_xg_lineage')
            evidence = dict(match_id=sid if isinstance(sid, str) else None,
                            date=day(row.get('fecha')).isoformat() if day(row.get('fecha')) else None,
                            source_artifacts=sources, orientation='home' if home else 'away',
                            bilateral_available=all(numeric(v) for v in pair))
            if reasons:
                exclusions.append(dict(evidence, reasons=sorted(set(reasons))))
            else:
                accepted.append(dict(evidence, xgf=row['xgf'], xga=row['xga'],
                                     availability=attestations[sid], quality_flags=[]))
        accepted.sort(key=lambda r: (-day(r['date']).toordinal(), r['match_id']))
        exclusions.sort(key=dumps)
        results[side] = dict(samples=accepted, exclusions=exclusions, reason=error)
    return metadata, results
