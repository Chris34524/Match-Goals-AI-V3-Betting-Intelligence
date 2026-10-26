"""Declarative V3 candidates; no extraction, training or source I/O on import."""
from dataclasses import asdict, dataclass
import json

CATALOG_VERSION = '2.1.0'
MARKETS = ('BTTS', 'OVER_1_5', 'OVER_2_5', 'OVER_3_5', '1X2_EXPERIMENTAL')
STATUSES = ('available', 'planned', 'blocked')
WINDOWS = ('L5', 'L10', 'home_L5', 'home_L10', 'away_L5', 'away_L10',
           'H5', 'H10', 'D14', 'previous', 'as_of_target', None)
HISTORY = ('data/matches/<id>/history.json',)
TEMPORAL = (
    'Require verified target identity/date and eligible V3 row. For each input use '
    'v3.data.temporal.sample_reasons: unique non-target match_id, known date strictly '
    'before target local date; reject same-day inputs even with raw hora, future and '
    'unknown dates. Require parsed nonnegative integer scores and matching team(s). '
    'Historical sample date is evidence under V3 day-resolution policy, not file '
    'mtime/capture time. Exclude penalties; ambiguous regulation scope yields null. '
    'Retain input IDs/dates and exclusion reasons in future extraction provenance.'
)
RISK = 'Historical ordering/identity or score-scope ambiguity; never use target result.'
MISSING = 'Return null with reason and observed sample count; no zero-fill, imputation or cross-source fallback.'
XG_BLOCK = (
    'Raw per-match xG exists partially, but no accredited as-of revision/availability '
    'lineage for xG values or validated bilateral adapter. To enable: reconcile '
    'IDs/dates/teams with history, validate finite nonnegative paired xG/xGA and '
    'orientation, document provider publication/revision availability before cutoff, '
    'and audit every contributing sample. Aggregate l5/l10 alone is insufficient.'
)
STRENGTH_BLOCK = (
    'Current standings have no accredited as-of timestamp or constituent match '
    'lineage. Require season/competition identity, pre-target table availability '
    'and dated contributing matches excluding target/same-day/future results.'
)


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    group: str
    description: str
    dtype: str
    side: str
    window: str | None
    source_artifacts: tuple[str, ...]
    temporal_requirement: str
    missing_policy: str
    min_sample: int | None
    markets: tuple[str, ...]
    leakage_risk: str
    status: str
    blocked_reason: str | None = None


def _build():
    specs = []

    def add(name, group, description, side, window, minimum, markets,
            status='available', sources=HISTORY, dtype='float', reason=None,
            temporal=TEMPORAL):
        specs.append(FeatureSpec(name, group, description, dtype, side, window,
                                 sources, temporal, MISSING, minimum,
                                 tuple(m for m in MARKETS if m in markets),
                                 RISK, status, reason))

    goals = MARKETS
    metrics = (
        ('gf_mean', 'sum(team regulation goals) / n', goals),
        ('ga_mean', 'sum(opponent regulation goals) / n', goals),
        ('btts_rate', 'count(GF > 0 and GA > 0) / n', ('BTTS',)),
        ('over_1_5_rate', 'count(GF + GA >= 2) / n', ('OVER_1_5',)),
        ('over_2_5_rate', 'count(GF + GA >= 3) / n', ('OVER_2_5',)),
        ('over_3_5_rate', 'count(GF + GA >= 4) / n', ('OVER_3_5',)),
        ('clean_sheet_rate', 'count(GA == 0) / n', ('BTTS', '1X2_EXPERIMENTAL')),
        ('failed_to_score_rate', 'count(GF == 0) / n', ('BTTS', '1X2_EXPERIMENTAL')),
    )
    for side in ('home', 'away'):
        for venue in (False, True):
            for n in (5, 10):
                window = f'{side}_L{n}' if venue else f'L{n}'
                prefix = f'{side}_{"venue_" if venue else ""}'
                for metric, formula, markets in metrics:
                    add(f'{prefix}{metric}_l{n}', 'venue_form' if venue else 'recent_form',
                        f'{formula}; exactly last {n} eligible matches of target {side} team'
                        + (f' playing {side} only.' if venue else ' across venues.'),
                        side, window, n, markets)
                add(f'{prefix}sample_count_l{n}', 'sample_quality',
                    f'Number of eligible matches in {window}, capped at {n}; zero only for verified empty section.',
                    side, window, 0, goals, dtype='int')
        for n in (5, 10):
            for metric, formula, dtype in (
                ('xg_mean', 'mean team xG', 'float'),
                ('xga_mean', 'mean opponent xG', 'float'),
                ('xg_sample_count', 'number of valid paired xG samples, capped at window', 'int'),
                ('goals_per_xg', 'sum(GF) / sum(xG) on identical paired samples; null if denominator <= 0', 'float'),
            ):
                add(f'{side}_{metric}_l{n}', 'xg', formula + '; latest window matches, never backfill missing xG from older matches.',
                    side, f'L{n}', 0 if dtype == 'int' else n, goals, 'blocked',
                    ('data/matches/<id>/xg_history.json',) + HISTORY,
                    dtype, XG_BLOCK)
        add(f'{side}_days_rest', 'temporal_context',
            'Calendar days between target and immediately preceding finished match; not elapsed hours.',
            side, 'previous', 1, ('1X2_EXPERIMENTAL',), 'blocked', reason=
            'Truncated history does not certify latest-match completeness. Require complete dated fixture ledger through cutoff, including intervening fixtures.')
        add(f'{side}_matches_last_14_days', 'temporal_context',
            'Count finished team matches in [target date - 14 days, target date); all competitions.',
            side, 'D14', 0, ('1X2_EXPERIMENTAL',), 'blocked', reason=
            'History cap and unparsed/missing fixtures cannot certify 14-day completeness. Require complete fixture ledger for interval, including zero-match evidence.')
        for metric, predicate, markets in (
            ('scoring_streak', 'GF > 0', ('BTTS', 'OVER_1_5')),
            ('btts_streak', 'GF > 0 and GA > 0', ('BTTS',)),
            ('clean_sheet_streak', 'GA == 0', ('BTTS', '1X2_EXPERIMENTAL')),
        ):
            add(f'{side}_{metric}_capped_l10', 'temporal_context',
                f'Consecutive prefix satisfying {predicate} in latest 10 eligible observed matches; '
                'capped at 10 and at observed sample length, not an uncensored true streak.',
                side, 'L10', 1, markets, 'available', dtype='int')
        for metric, formula in (('standing_position', 'pre-target league rank'),
                                ('standing_points_per_game', 'pre-target points / played; null if played <= 0')):
            add(f'{side}_{metric}', 'strength', formula, side, 'as_of_target', 1,
                ('1X2_EXPERIMENTAL',), 'blocked', ('data/matches/<id>/standings.json',),
                'int' if metric.endswith('position') else 'float', STRENGTH_BLOCK)
    for n in (5, 10):
        add(f'bilateral_xg_available_l{n}', 'xg',
            f'True only if both teams have all {n} paired eligible xG/xGA samples; false only on verified absence, otherwise null.',
            'match', f'L{n}', 0, goals, 'blocked',
            ('data/matches/<id>/xg_history.json',) + HISTORY, 'bool', XG_BLOCK)
        for metric, formula, markets in (
            ('sample_count', 'eligible pair meetings, capped at window; zero only for verified empty H2H section', goals),
            ('btts_rate', 'count(both score) / n', ('BTTS',)),
            ('over_1_5_rate', 'count(total >= 2) / n', ('OVER_1_5',)),
            ('over_2_5_rate', 'count(total >= 3) / n', ('OVER_2_5',)),
            ('over_3_5_rate', 'count(total >= 4) / n', ('OVER_3_5',)),
            ('home_gf_mean', 'mean goals scored by current home team, independent of historical venue', goals),
            ('home_ga_mean', 'mean goals conceded by current home team (= current away team GF)', goals),
        ):
            add(f'h2h_{metric}_h{n}', 'h2h_auxiliary', formula + '; auxiliary only, never mixed with core form.',
                'h2h', f'H{n}', 0 if metric == 'sample_count' else 3,
                markets, dtype='int' if metric == 'sample_count' else 'float')
    return tuple(sorted(specs, key=lambda f: f.name))


CATALOG = _build()


def get_catalog(*, market=None, group=None, status=None):
    """Return immutable specs, in canonical name order; filters are conjunctive."""
    for value, allowed, label in ((market, MARKETS, 'market'),
                                  (status, STATUSES, 'status'),
                                  (group, {f.group for f in CATALOG}, 'group')):
        if value is not None and value not in allowed:
            raise ValueError(f'Unknown {label}: {value}')
    return tuple(f for f in CATALOG if
                 (market is None or market in f.markets) and
                 (group is None or group == f.group) and
                 (status is None or status == f.status))


def catalog_json(*, market=None, group=None, status=None):
    """Canonical UTF-8-compatible JSON, stable keys/order, no clock or local paths."""
    return json.dumps({'catalog_version': CATALOG_VERSION,
                       'features': [asdict(f) for f in get_catalog(
                           market=market, group=group, status=status)]},
                      ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(',', ':')) + '\n'
