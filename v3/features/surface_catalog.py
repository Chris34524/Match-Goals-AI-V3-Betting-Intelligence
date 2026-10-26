"""Roadmap 2.1A: declarative signal surface, separate from extraction permission.

No I/O on import, no acquisition code, and no changes to the 2.1 feature API.
One entry is a named signal candidate, not a generated model column. Base 2.1
columns retain their granularity; expanded rows are unsided signal definitions.
"""
from collections import Counter
from dataclasses import asdict, dataclass, replace
import json

from .catalog import CATALOG, MISSING, TEMPORAL
from .context_catalog import CONTEXT_ROWS

VERSION = '2.1A'
LEVELS = ('team', 'player', 'match', 'lineup', 'discipline', 'context', 'news')
PRIORITIES = ('P0', 'P1', 'P2', 'P3')
AVAILABILITY = ('observed_local', 'visible_public', 'competition_dependent', 'unknown')
CAPTURE_POLICIES = ('existing_local', 'manual_or_permitted_source', 'requires_authorization', 'blocked')
STATUSES = ('available', 'planned', 'blocked')
MARKETS = ('BTTS', 'OVER_1_5', 'OVER_2_5', 'OVER_3_5', '1X2', 'CORNERS_FUTURE',
           'CARDS_FUTURE', 'PLAYER_PROPS_FUTURE')
GOALS = MARKETS[:5]
HISTORY = ('data/matches/<id>/history.json',)

# Primary product documentation only; these are references, never request targets.
PUBLIC_SOURCES = {
    'terms': 'https://www.flashscore.com/terms-of-use/',
    'team': 'https://www.flashscore.com/news/more-data-to-help-you-read-the-game-flashscore-s-football-stats-get-a-facelift/42Kj2YYI/',
    'team_expansion': 'https://www.flashscore.com/news/football-even-more-in-depth-flashscore-expands-match-statistics/6yne1Z8e/',
    'player': 'https://www.flashscoreusa.com/news/players-under-the-magnifying-glass-a-look-at-players-detailed-statistics/8pvZSJ6U/',
    'lineup': 'https://www.flashscore.com/news/soccer-premier-league-pre-match-football-content-boost-flashscore-introduces-predicted-lineups/fw2Jv6j5/',
    'ratings': 'https://www.flashscore.in/faq/data/',
    'scope': 'https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/11',
}
HISTORICAL = (
    'Historical completed matches only, strictly before target cutoff. Reconcile '
    'match/player/team/competition IDs, regulation/extra-time scope and timezone. '
    'Require publication and revision available_at <= decision cutoff, not mtime '
    'or event date alone for stats/ratings. Reject target, same-day without verified '
    'timestamp, future and unknown inputs. Retain sample provenance and exclusions.'
)
SNAPSHOT = (
    'Require source-published snapshot and revision timestamp <= decision cutoff, '
    'verified fixture/player/team IDs and timezone. Never backfill from final XI, '
    'post-match profile, current table, later injury update or closing odds. '
    'Official and predicted lineups must remain distinct and versioned.'
)
AUTH = ('New automated Flashscore acquisition requires express authorization or a '
        'documented permitted/licensed alternative, then coverage and as-of validation. '
        'Public visibility and local possession do not grant acquisition rights.')


@dataclass(frozen=True)
class SignalSpec:
    name: str
    family: str
    level: str
    description: str
    markets: tuple[str, ...]
    surface_availability: str
    capture_policy: str
    source_artifacts: tuple[str, ...]
    public_references: tuple[str, ...]
    temporal_requirement: str
    missing_policy: str
    leakage_risk: str
    status: str
    priority: str
    enablement_requirement: str
    observable_basis: str
    automatable: bool = False

    def __post_init__(self):
        for value, allowed in ((self.level, LEVELS), (self.priority, PRIORITIES),
                               (self.surface_availability, AVAILABILITY),
                               (self.capture_policy, CAPTURE_POLICIES), (self.status, STATUSES)):
            if value not in allowed:
                raise ValueError(f'Invalid signal vocabulary: {value}')
        if not self.markets or not set(self.markets) <= set(MARKETS):
            raise ValueError('Invalid markets')
        if self.automatable and (self.capture_policy in ('requires_authorization', 'blocked')
                                 or self.status != 'available'):
            raise ValueError('Unapproved or blocked signal cannot be automatable')
        forbidden = ('labels', 'backtest', 'champion', 'lambda_comparison', 'confidence', 'result.json')
        if any(word in path.casefold() for path in self.source_artifacts for word in forbidden):
            raise ValueError('Evaluation/model outputs cannot be feature sources')
        if self.priority == 'P0' and (not self.source_artifacts or
                self.surface_availability != 'observed_local' or self.capture_policy != 'existing_local'):
            raise ValueError('P0 requires existing local raw evidence')


def _build():
    rows = []
    for feature in CATALOG:
        markets = tuple('1X2' if m == '1X2_EXPERIMENTAL' else m for m in feature.markets)
        level = ('match' if feature.side in ('h2h', 'match') else
                 'context' if feature.group == 'temporal_context' else 'team')
        rows.append(SignalSpec(feature.name, 'base_' + feature.group, level,
            feature.description, markets, 'observed_local', 'existing_local',
            feature.source_artifacts + (('data/xg_cache/<id>.json',) if feature.group == 'xg' else ()), (), feature.temporal_requirement,
            feature.missing_policy, feature.leakage_risk, feature.status,
            'P2' if feature.group == 'h2h_auxiliary' else
            'P0' if feature.status == 'available' else
            'P2' if feature.group == 'temporal_context' else 'P1',
            feature.blocked_reason or 'Future extractor must preserve the 2.1 temporal/sample contract.',
            'Verified dated historical scores' if feature.source_artifacts == HISTORY
            else 'Local raw candidate; lineage not accredited'))

    def add(name, family, level, description, markets=GOALS, priority='P1',
            availability='competition_dependent', policy='requires_authorization',
            sources=(), refs=('scope',), temporal=HISTORICAL, requirement=AUTH,
            basis='Documented public sports observation; coverage varies by competition.',
            status='planned'):
        rows.append(SignalSpec(name, family, level, description, tuple(markets),
            availability, policy, tuple(sources), tuple(PUBLIC_SOURCES[r] for r in refs),
            temporal, MISSING + ' Distinguish absent, unsupported, unpublished and invalid; no implicit zero for omitted cards.',
            'Target/post-cutoff contamination, retrospective corrections, identity and coverage selection bias.',
            status, priority, requirement, basis))

    for metric, desc in (
        ('identity', 'Verified match identifier and bilateral team identity'),
        ('competition', 'Scheduled competition, season and stage identity'),
        ('scheduled_date', 'Scheduled match date; date is not a verified kickoff timestamp'),
        ('scheduled_time', 'Scheduled local time; unknown offset must remain unknown'),
        ('venue_side', 'Home and away team orientation'),
        ('fixture_status', 'Observed scheduled/live/finished status as of snapshot')):
        add('match_' + metric, 'fixture_metadata', 'match', desc,
            priority='P1' if metric == 'fixture_status' else 'P0',
            availability='observed_local', policy='existing_local',
            sources=HISTORY + ('data/partidos.json',), refs=(), temporal=SNAPSHOT,
            requirement='Validate identity against dated raw history; status/schedule need as-of snapshot. No automatic eligibility from file presence.')
    for metric in ('played', 'wins', 'draws', 'losses', 'goals_for', 'goals_against',
                   'goal_difference', 'points', 'form'):
        add('team_table_' + metric, 'standings_snapshot', 'team',
            'Raw standings ' + metric.replace('_', ' ') + '; not an as-of-accredited feature.',
            availability='observed_local', policy='existing_local',
            sources=('data/matches/<id>/standings.json', 'data/standings.json'),
            refs=(), temporal=SNAPSHOT, status='blocked',
            requirement='Require pre-cutoff publication snapshot, season/stage identity and constituent fixture lineage; current table is insufficient.')

    team_metrics = '''shots|Total shots
shots_on_target|Shots on target
shots_off_target|Shots off target
shots_blocked|Blocked shots
shots_inside_box|Shots inside penalty area
shots_outside_box|Shots outside penalty area
woodwork|Attempts hitting woodwork
big_chances|Big chances created
big_chances_scored|Big chances converted
big_chances_missed|Big chances missed
xgot|Expected goals on target
xa|Expected assists
touches_opposition_box|Touches in opposition box
corners|Corner kicks
possession|Possession share
passes|Attempted passes
accurate_passes|Completed passes and completion denominator
long_passes|Attempted and completed long passes
final_third_passes|Attempted and completed final-third passes
crosses|Attempted and accurate crosses
offsides|Offsides
fouls|Fouls committed
free_kicks|Free kicks awarded
tackles|Attempted and successful tackles
duels_won|Ground and aerial duels won
clearances|Defensive clearances
interceptions|Interceptions
errors_leading_shot|Errors leading to a shot
errors_leading_goal|Errors leading to a goal
saves|Goalkeeper saves
xgot_faced|Expected goals on target faced
goals_prevented|Goalkeeper goals prevented excluding own goals
headed_goals|Headed goals
average_rating|Mean team rating using documented participating-player denominator'''
    for line in team_metrics.splitlines():
        metric, desc = line.split('|')
        markets = (GOALS + ('CORNERS_FUTURE',) if metric in ('corners', 'crosses', 'shots', 'shots_blocked')
                   else GOALS + ('CARDS_FUTURE',) if metric in ('fouls', 'tackles', 'duels_won') else GOALS)
        add('team_' + metric, 'team_match_stats', 'team', desc, markets,
            refs=('team', 'team_expansion', 'ratings') if metric == 'average_rating'
            else ('team', 'team_expansion', 'scope'))

    player_metrics = '''identity|Stable player ID, display name and position, with identity resolution
minutes|Played minutes with stoppage/extra-time convention
rating|Individual match rating with provider scale/version
rolling_rating|Rolling rating on identical eligible historical samples
goals|Goals excluding own goals and shootouts
assists|Credited assists with provider convention
shots|Total player shots
shots_on_target|Player shots on target
xg|Individual expected goals
xgot|Individual expected goals on target
xa|Individual expected assists
passes|Attempted and completed passes
key_passes|Key passes
crosses|Attempted and accurate crosses
dribbles|Attempted and successful dribbles
duels|Ground and aerial duels attempted/won
tackles|Attempted and successful tackles
interceptions|Interceptions
clearances|Clearances
fouls_committed|Fouls committed
fouls_suffered|Fouls suffered
errors_leading_shot|Errors leading to shots
errors_leading_goal|Errors leading to goals
saves|Goalkeeper saves
xgot_faced|Goalkeeper xGOT faced
goals_prevented|Goalkeeper goals prevented
clean_sheets|Goalkeeper clean sheets with minutes eligibility
penalty_saves|Goalkeeper penalties saved excluding shootouts
player_of_match|Provider player of the match distinction
age|Age at cutoff, never current age backfilled
position|Position at cutoff
market_value|Provider market value estimate, currency and valuation date
contract_expiry|Public contract expiry with version date
current_club|Club membership at cutoff
loan_status|Dated loan status
transfer_history|Dated completed transfers
injury_history|Publicly reported injury spells with publication/revision dates
season_average_rating|Season average rating available at cutoff, never end-season backfill
recent_minutes|Minutes in fixed preceding window with complete fixtures
recent_starts|Starts in fixed preceding window with complete fixtures
recent_goal_contribution|Prior goals plus assists on eligible historical appearances
minutes_load|Sum minutes and appearance intervals, observable exposure not inferred fatigue'''
    snapshot_metrics = {'age', 'position', 'market_value', 'contract_expiry', 'current_club',
                        'loan_status', 'transfer_history', 'injury_history', 'season_average_rating'}
    for line in player_metrics.splitlines():
        metric, desc = line.split('|')
        uncertain = metric in {'contract_expiry', 'loan_status', 'penalty_saves', 'clean_sheets'}
        add('player_' + metric, 'player_profile' if metric in snapshot_metrics else 'player_performance',
            'player', desc, GOALS + ('PLAYER_PROPS_FUTURE',),
            priority='P3' if metric in {'market_value', 'contract_expiry', 'loan_status'} else 'P1',
            availability='unknown' if uncertain else 'competition_dependent',
            refs=('player', 'ratings', 'scope'), temporal=SNAPSHOT if metric in snapshot_metrics else HISTORICAL,
            requirement=AUTH + (' Verify exact field visibility; Issue scope is not field-level public evidence.' if uncertain else ''))

    lineup_metrics = '''official_xi|Official starting XI, kept separate from predictions
predicted_xi|Predicted XI with prediction version and confidence if published
formation|Official/predicted formation labelled by source type
starter_status|Official starter status
substitute_status|Used substitute status and substitution event time
bench_status|Named unused bench status
not_in_squad|Explicitly reported not-in-squad status, never inferred from missing entry
continuity|Overlap of official XIs in eligible history
starters_repeated_l3|Repeated starters across last three eligible matches
starters_repeated_l5|Repeated starters across last five eligible matches
changes_previous_match|Changes against previous verified official XI
key_player_availability|Public availability weighted by predeclared prior-minutes rule
bench_strength|Prior contribution of named bench, with denominator and null handling
injury|Publicly reported injury-related absence
illness|Publicly reported illness-related absence; no diagnosis inference
suspension|Confirmed suspension with competition and effective fixtures
card_absence|Card-related unavailability, confirmed separately from threshold risk
return_from_injury|Explicit return status with earlier public absence record
transfer_out|Confirmed departure removing player from eligible squad'''
    derived_lineup = {'continuity', 'starters_repeated_l3', 'starters_repeated_l5', 'changes_previous_match', 'bench_strength'}
    for line in lineup_metrics.splitlines():
        metric, desc = line.split('|')
        add('lineup_' + metric, 'availability_lineup', 'lineup', desc,
            GOALS + ('CARDS_FUTURE', 'PLAYER_PROPS_FUTURE'),
            refs=('lineup', 'player', 'scope'), temporal=SNAPSHOT,
            requirement=AUTH + (' Require complete historical XIs and stable IDs; derived candidate, not a public scalar.' if metric in derived_lineup else ''))

    discipline_metrics = '''team_yellow_cards|Team yellow cards, including explicit second-yellow convention
team_red_cards|Team direct and second-yellow red cards without double counting
team_card_rates|Team historical yellow/red cards per match
player_yellow_cards|Player yellow cards
player_red_cards|Player direct and second-yellow red cards
player_card_rates|Player cards per 90 and per appearance with minutes denominator
fouls|Team/player committed and suffered fouls
late_cards|Cards after a predefined minute threshold with added-time convention
cards_under_score_pressure|Cards while trailing or within a predefined close-score state; no emotion inference
suspension_risk|Cards remaining to a rule-based threshold, not a confirmed suspension
red_card_history|Dated dismissal history
cards_by_match_state|Cards joined to strictly preceding score state'''
    for line in discipline_metrics.splitlines():
        metric, desc = line.split('|')
        add('discipline_' + metric, 'discipline', 'discipline', desc,
            ('CARDS_FUTURE', '1X2', 'PLAYER_PROPS_FUTURE'),
            priority='P2' if metric in ('late_cards', 'cards_under_score_pressure', 'cards_by_match_state') else 'P1',
            refs=('team', 'player', 'lineup', 'scope'),
            requirement=AUTH + (' Complete ordered card/goal events and corrections are mandatory for state/time joins.'
                if metric in ('late_cards', 'cards_under_score_pressure', 'cards_by_match_state')
                else ' Suspension thresholds require season/competition rules, resets, appeals and served-match ledger.'))

    for name, desc, prerequisites in CONTEXT_ROWS:
        sources = HISTORY if name in ('winning_streak', 'winless_streak', 'scoring_streak') else ()
        add('context_' + name, 'observable_context', 'context', desc,
            GOALS + ('CARDS_FUTURE', 'CORNERS_FUTURE'), priority='P2',
            availability='observed_local' if sources else 'unknown',
            policy='existing_local' if sources else 'manual_or_permitted_source',
            sources=sources, refs=('scope',), temporal=TEMPORAL if sources else SNAPSHOT,
            requirement=prerequisites + (' Local derivation only; no new capture.' if sources else
                ' No source authorization is established; secure a permitted structured source before automation. Flashscore acquisition requires authorization.'),
            basis=desc + ': ' + prerequisites)

    for name, level, family, description in (
        ('player_display_name', 'player', 'player_profile', 'Displayed player name; not a stable player ID'),
        ('player_shirt_number', 'player', 'player_profile', 'Displayed shirt number; never a globally unique ID'),
        ('match_venue', 'match', 'fixture_metadata', 'Displayed venue and city'),
        ('match_venue_capacity', 'match', 'fixture_metadata', 'Displayed venue capacity, not observed attendance'),
        ('match_coach_names', 'match', 'fixture_metadata', 'Displayed coach names, not appointment/change dates')):
        add(name, family, level, description, priority='P1',
            availability='observed_local', policy='existing_local',
            sources=('data/match_detail.txt', 'data/standings_page.txt'), refs=(),
            temporal=SNAPSHOT, requirement='Unparsed historical page snapshot only; require verified fixture identity, stable entities and accredited available_at before extraction.')

    for market in ('1x2', 'totals', 'btts', 'corners', 'cards', 'player_props'):
        add('odds_' + market, 'odds_market', 'match',
            'Quoted bookmaker odds for ' + market + '; preserve bookmaker, line, side, currency/format and timestamp.',
            MARKETS, availability='unknown' if market == 'player_props' else 'competition_dependent',
            priority='P3' if market == 'player_props' else 'P1', refs=('terms', 'scope'), temporal=SNAPSHOT)
    for metric in ('opening_snapshot', 'current_snapshot', 'closing_snapshot', 'bookmaker_consensus', 'bookmaker_dispersion'):
        add('odds_' + metric, 'odds_market', 'match', metric.replace('_', ' ') +
            '; compare identical market/line/time, remove margin only with documented method.', MARKETS,
            priority='P3' if metric == 'closing_snapshot' else 'P1',
            availability='unknown', refs=('terms', 'scope'), temporal=SNAPSHOT,
            requirement=AUTH + ' Historical snapshots must be legally available; closing quotes after cutoff are forbidden prematch inputs.')
    for metric in ('previews', 'match_reports', 'commentary', 'context_sentiment'):
        add('news_' + metric, 'news_context', 'news',
            'Future structured, attributed ' + metric.replace('_', ' ') +
            ' metadata; sentiment describes permitted text only, never a player mental state.',
            GOALS, priority='P3', availability='unknown' if metric == 'context_sentiment' else 'visible_public',
            policy='requires_authorization', refs=('scope', 'terms'), temporal=SNAPSHOT,
            requirement=AUTH + ' No bulk copied articles/commentary corpus; post-match reports cannot explain their own target prematch.',
            basis='Public reporting metadata and attributed factual events only.')
    # Read-only inspection found actual values in old page snapshots, not merely UI tabs.
    # Player ratings there are competition averages, NOT target-match performance ratings.
    text_evidence = {
        'lineup_predicted_xi': ('data/match_detail.txt', 'data/standings_page.txt'),
        'lineup_injury': ('data/match_detail.txt', 'data/standings_page.txt'),
        'lineup_card_absence': ('data/match_detail.txt',),
        'player_season_average_rating': ('data/match_detail.txt', 'data/standings_page.txt'),
        'team_average_rating': ('data/match_detail.txt', 'data/standings_page.txt'),
        'odds_1x2': ('data/match_detail.txt', 'data/standings_page.txt'),
        'context_referee_assignment': ('data/match_detail.txt', 'data/standings_page.txt'),
    }
    rows = [replace(row, surface_availability='observed_local', capture_policy='existing_local',
        source_artifacts=text_evidence[row.name],
        observable_basis=row.observable_basis + ' Actual displayed values in local text snapshots; partial unparsed evidence only.',
        enablement_requirement='No new capture authorized. Validate page/fixture identity, field semantics, '
            'publication/revision available_at and a bilateral adapter. Snapshot capture time is unaccredited; '
            'ratings are displayed competition averages, card absence is not a served-suspension ledger. '
            'Future Flashscore acquisition still requires authorization.')
        if row.name in text_evidence else row for row in rows]
    return tuple(sorted(rows, key=lambda row: row.name))


SURFACE_CATALOG = _build()


def get_surface_catalog(*, level=None, status=None, priority=None, market=None):
    filters = ((level, LEVELS, 'level'), (status, STATUSES, 'status'),
               (priority, PRIORITIES, 'priority'), (market, MARKETS, 'market'))
    for value, allowed, label in filters:
        if value is not None and value not in allowed:
            raise ValueError(f'Unknown {label}: {value}')
    return tuple(row for row in SURFACE_CATALOG if
        (level is None or row.level == level) and (status is None or row.status == status)
        and (priority is None or row.priority == priority) and (market is None or market in row.markets))


def surface_catalog_json(**filters):
    return json.dumps({'catalog_version': VERSION,
                       'signals': [asdict(row) for row in get_surface_catalog(**filters)]},
                      ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':')) + '\n'


def surface_summary():
    return {'signals': len(SURFACE_CATALOG), 'families': len({s.family for s in SURFACE_CATALOG}),
            **{key: dict(sorted(Counter(getattr(s, key) for s in SURFACE_CATALOG).items()))
               for key in ('priority', 'level', 'family', 'surface_availability', 'capture_policy', 'status')}}


if __name__ == '__main__':
    print(surface_catalog_json(), end='')
