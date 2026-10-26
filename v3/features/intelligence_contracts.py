"""Evaluated candidates for Phases 2.8 onward; no extraction or model inputs.

A contract is not an implemented sporting value. Candidate counts are semantic
signals, unlike sided/window-expanded columns of the base 2.1 catalog.
"""
from dataclasses import asdict, dataclass
import json

VERSION = '2.12.0'


@dataclass(frozen=True)
class IntelligenceContract:
    name: str
    phase: str
    family: str
    definition: str
    prerequisites: str
    markets: tuple[str, ...]
    status: str = 'blocked'
    blocked_reason: str = 'No permitted provider and no stable-identity, timestamped historical observations in local archive.'
    unknown_policy: str = 'null with explicit reason; never zero-fill or retrospective backfill'
    provenance_requirement: str = 'provider/permission evidence; entity, team, fixture and competition IDs; source artifact/URL + digest; publication/revision timestamp; decision cutoff; oriented field evidence'
    temporal_requirement: str = 'Strictly pre-cutoff publication/revision and pre-target completed match; exclude target, same-day, future; final scores/labels/model outputs forbidden'

    def __post_init__(self):
        if self.status not in ('blocked','partial','planned') or not self.blocked_reason:
            raise ValueError('Unevidenced candidates cannot become available')


TEAM_STATS = ('shots', 'shots_on_target', 'shots_off_target', 'blocked_shots',
              'big_chances', 'big_chances_missed', 'possession', 'corners',
              'passes', 'passes_completed', 'pass_accuracy', 'tackles', 'duels',
              'duels_won', 'fouls', 'xgot', 'xa', 'offsides', 'touches_in_opposition_box')
KEEPER_STATS = ('saves', 'shots_faced', 'xgot_faced', 'goals_prevented', 'save_percentage')


PLAYER_DEFINITIONS = {
    'stable_player_ids': 'Provider persistent player ID reconciled across team transfers; shirt number/name is insufficient.',
    'official_starting_xi': 'Official announced eleven player IDs and separately versioned publication snapshot.',
    'predicted_xi': 'Provider predicted eleven IDs; never substitute official XI or merge their histories.',
    'bench': 'Official named substitutes in a pre-cutoff snapshot.',
    'formation': 'Official or predicted formation with explicit snapshot kind, never infer official from prediction.',
    'minutes': 'Historical regulation playing minutes with provider substitution/stoppage convention.',
    'recent_minutes_load': 'Sum accredited minutes in [cutoff-14 days, cutoff); requires complete all-competition ledger.',
    'starts': 'Count official starts over last 10 complete eligible appearances/fixtures; denominator explicit.',
    'sub_appearances': 'Count appearances from bench over last 10 eligible team fixtures; unused bench excluded.',
    'player_rating': 'Provider match rating, definition/version and historical publication; competition average is distinct.',
    'player_goals': 'Prior match regulation goals attributed to stable player ID with own-goal rules.',
    'player_assists': 'Prior match official assists with provider definition and correction lineage.',
    'player_shots': 'Prior match regulation shots attributed to stable player ID.',
    'availability': 'Explicit dated availability status; unknown is not available.',
    'injury': 'Explicit confirmed injury report with player ID and effective date.',
    'illness': 'Explicit confirmed illness report, distinct from injury and unknown absence.',
    'suspension': 'Effective competition-specific sanction with served-match ledger and appeal updates.',
    'not_in_squad': 'Explicit published squad omission; no inferred cause.',
    'return_from_injury': 'Confirmed return following recorded injury, not silence or retrospective appearance.',
    'lineup_continuity': 'Intersection of current official XI and previous eligible official XI divided by 11.',
    'rotation': '11 minus official XI intersection size; full official XIs required.',
    'bench_strength': 'Sum bench players prior per-90 production under predeclared metric/minute threshold; no post-target rating.',
    'key_player_availability': 'Status of players selected by top-3 share of prior 10 fixture minutes; complete historical minutes and as-of status required.',
}


DISCIPLINE_DEFINITIONS = {
    'yellow_cards': 'Observable yellow events excluding provider duplicate representations; retain whether a caution is second-yellow.',
    'red_cards': 'Dismissals = direct-red dismissals plus second-yellow dismissals, each dismissal ID once; market settlement may use different weights.',
    'second_yellow_red': 'One dismissal linked to its triggering second caution; provider synthetic red row is not another dismissal.',
    'discipline_fouls': 'Recorded regulation fouls with provider definition; no inference about emotional aggression.',
    'cards_per_match': 'Sum disjoint card events over n complete prior matches; n and yellow/red components explicit.',
    'disciplinary_streaks': 'Consecutive eligible fixtures with at least one defined card event; cap/sample/censoring retained; complete ledger required.',
    'player_cards': 'Disjoint dated card events attributed to stable player ID, with team stint and rescissions.',
    'team_cards': 'Disjoint dated card events attributed to team ID; staff/bench scope explicit.',
    'event_chronology': 'Ordered period, elapsed minute, added time, sequence and event IDs; corrections and rescinded events retained.',
}
CARD_LEDGER_CONTRACT = {
    'required_identity': ('event_id', 'dismissal_id_when_red', 'fixture_id', 'team_id', 'player_or_staff_id', 'competition_id', 'season_id'),
    'required_time': ('period', 'minute', 'added_time', 'sequence', 'publication_timestamp', 'revision_timestamp', 'decision_cutoff'),
    'completeness': 'Independent provider evidence of all pages/events, completed fixture scope and revision/correction history; boolean complete=true alone is insufficient.',
    'second_yellow_policy': 'Link triggering caution and synthetic red to one dismissal_id. Never add a second-yellow dismissal and its synthetic red as two reds. Preserve caution ledger separately.',
    'rules': 'Versioned competition suspension/carryover/amnesty/appeal rules; market settlement rules are separate and not implemented.',
    'future_market': 'CARDS_FUTURE',
    'unknown_policy': 'No complete ledger => null + blocked; absence of card rows is not zero cards.',
}


CONTEXT_DEFINITIONS = {
    'derby_rivalry': ('Membership of unordered stable team-ID pair in dated curated rivalry registry.', 'Published registry effective before cutoff; no sentiment or geographical guess.'),
    'knockout': ('Scheduled match belongs to knockout stage under competition rules.', 'Official dated stage/fixture identity and season rules before cutoff.'),
    'final': ('Official scheduled competition stage equals final.', 'Official pre-cutoff fixture stage; never infer from outcome or title winner.'),
    'two_leg_tie_context': ('Official leg index, aggregate score from completed prior leg and current season tie rules.', 'Tie/leg IDs, regulation scope, accredited earlier leg result and rules (including away-goals rule where applicable).'),
    'title_race': ('Title outcome remains mathematically affected by target result under season rules.', 'Historical pre-cutoff table, remaining fixtures and tiebreaks; current standings forbidden.'),
    'relegation_stakes': ('Relegation outcome remains mathematically affected by target result.', 'Historical pre-cutoff table, remaining fixtures, deductions and competition rules.'),
    'qualification_stakes': ('Qualification outcome remains mathematically affected by target result.', 'Historical pre-cutoff table, remaining fixtures, qualification places and tiebreaks.'),
    'manager_changed_14d': ('True iff independently confirmed appointment effective time lies in [cutoff-14 days, cutoff); false only with complete appointment coverage.', 'Official dated appointment, stable manager/team IDs, publication before cutoff and full interval coverage.'),
    'manager_first_n_matches': ('Count complete eligible team fixtures since confirmed appointment; indicator count < N with N declared before modeling.', 'Appointment evidence plus complete all-competition fixture ledger through cutoff.'),
    'key_player_absence': ('Confirmed unavailable member of top-3 players by prior-10-fixture minute share.', 'Predeclared key-player rule, complete minutes and timestamped confirmed availability.'),
    'key_player_return': ('Confirmed return of predeclared key player after recorded absence sequence.', 'Stable IDs, dated availability sequence and complete minutes for key-player rule.'),
    'rotation_intensity': ('11 minus intersection size of current and previous official starting XI.', 'Two complete official XIs with publication before respective cutoffs; never predicted as official.'),
    'lineup_surprise': ('Symmetric difference size between official XI and latest strictly earlier predicted XI.', 'Separately versioned predicted and official snapshots, both published before decision cutoff.'),
    'fixture_importance': ('Vector of accredited final/knockout/title/relegation/qualification flags; no subjective scalar.', 'Each constituent proxy individually accredited; missing constituents stay unknown, not false.'),
}


def contracts(phase=None):
    rows = []
    for family, names in (('advanced_team_stats', TEAM_STATS), ('goalkeeper', KEEPER_STATS)):
        for name in names:
            rows.append(IntelligenceContract(name, '2.8', family,
                f'Provider-defined regulation {name} per completed match; rolling mean only over 5/10 fully accredited recent fixtures; preserve units and denominator.',
                'Permitted source, stable IDs, pre-cutoff publication/revision, correct home/away and keeper-team stint orientation. '
                'Percentages require documented denominators; goals_prevented requires provider definition (e.g. xGOT faced minus goals conceded), never mix xG and xGOT.',
                ('CORNERS_FUTURE',) if name == 'corners' else ('BTTS','OVER_2_5','1X2_EXPERIMENTAL')))
    for name, definition in PLAYER_DEFINITIONS.items():
        rows.append(IntelligenceContract(name, '2.9', 'players_lineups', definition,
            'Permitted provider; stable player/team/match IDs; historical minutes and fixture completeness where relevant; separately timestamped official versus predicted snapshots before decision cutoff.',
            ('BTTS','OVER_2_5','1X2_EXPERIMENTAL'),
            blocked_reason='Local TXT has expected XI, shirt numbers, competition-average ratings and absences, but no accredited publication timestamp, stable player IDs, official XI or historical minutes ledger.',
            temporal_requirement='Historical performance uses strictly earlier completed fixtures (target/same-day/future excluded). Target prematch official/predicted/availability snapshots require independently accredited publication/revision strictly before decision cutoff; never backfill later official XI.'))
    for name, definition in DISCIPLINE_DEFINITIONS.items():
        rows.append(IntelligenceContract(name, '2.10', 'discipline', definition,
            'Permitted source, complete event ledger and correction history; stable event/dismissal/player/team IDs; second-yellow linked without duplicate reds; competition rules when deriving sanctions.',
            ('CARDS_FUTURE',), blocked_reason='No complete dated card/foul event ledger, stable player/event IDs or accredited publications. A red-card absence mention is not chronology, sanction duration or served-match evidence.'))
    for name, (definition, prerequisites) in CONTEXT_DEFINITIONS.items():
        rows.append(IntelligenceContract(name, '2.11', 'objective_context', definition,
            'Permitted source; independently published/versioned evidence before decision cutoff. ' + prerequisites,
            ('BTTS','OVER_2_5','1X2_EXPERIMENTAL'),
            blocked_reason='No accredited historical stage/rivalry/appointment/table/availability/XI snapshots with stable IDs and pre-cutoff publications for this proxy. Raw headings, current coach names or current standings do not establish historical context.',
            temporal_requirement='Each context snapshot must be independently published/revised before decision cutoff; historical fixture operands use strictly earlier eligible dates. Target scheduled stage and prematch XI are admissible only as independently accredited prematch snapshots, never inferred from outcomes.'))
    from v3.features.news_contract import EVENT_TYPES
    for name in EVENT_TYPES:
        rows.append(IntelligenceContract('news_' + name, '2.12', 'news_context_p3',
            'Structured attributed ' + name + ' event; no psychological sentiment or private-state inference.',
            'Permitted ingestion source and independent publication/revision evidence; bounded source excerpt, stable entity ID, versioned extraction and confidence; schema validity alone is not permission or timestamp accreditation.',
            ('BTTS','OVER_2_5','1X2_EXPERIMENTAL'),
            blocked_reason='No permitted news provider or independently timestamped local corpus. Existing preview snapshot lacks publication/revision accreditation; no retrospective backfill or mass acquisition.',
            temporal_requirement='Independently accredited publication/revision strictly before decision cutoff with timezone. Same-day news needs verified publication timing; schema timestamp strings alone grant no availability. No target outcome, later revision or retrospective backfill.'))
    return tuple(sorted((r for r in rows if phase is None or r.phase == phase), key=lambda r:r.name))


def contracts_json(phase=None):
    return json.dumps(dict(version=VERSION, contracts=[asdict(r) for r in contracts(phase)]),
                      ensure_ascii=False, sort_keys=True, indent=2)+'\n'


if __name__ == '__main__':
    print(contracts_json(), end='')
