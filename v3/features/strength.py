"""2.5: explicit strength candidates, blocked until opponent lineage is accredited.

Rolling own points is form, not an opponent adjustment. Capped histories from
unrelated target captures cannot establish a complete opponent schedule or
resolve team aliases across competitions. No values are emitted by this audit.
"""
VERSION = '2.5.0'
DEFINITIONS = {
    'opponent_results_strength': 'mean((3*wins + draws)/n) for each opponent, using its own N prior fixtures before the evaluated fixture; N=10',
    'opponent_adjusted_form': 'mean(points_earned - (3 - opponent_prior_ppg)) over last 10; requires validated opponent_prior_ppg for every fixture',
    'schedule_strength': 'mean(opponent_prior_ppg) over last 10 eligible fixtures',
    'opponent_scoring_strength': 'mean(opponent_prior_GF/n) over last 10 eligible fixtures; n=10 for each opponent',
    'opponent_conceding_strength': 'mean(opponent_prior_GA/n) over last 10 eligible fixtures; n=10 for each opponent',
    'standing_position': 'rank in accredited pre-target competition/season table',
    'standing_points_per_game': 'pre-target competition points / played; played > 0',
}
BLOCK_REASON = (
    'No accredited opponent identity registry and independently dated opponent '
    'fixture lineage before each evaluated historical fixture; capped target '
    'histories are not a reliable opponent schedule. Current standings lack '
    'historical publication snapshots and constituent results. Own rolling '
    'points would duplicate form without measuring rival quality.'
)


def assessment():
    return {f'{side}_{name}': dict(status='blocked', value=None, formula=formula,
            reason=BLOCK_REASON, min_sample=10 if not name.startswith('standing_') else 1,
            null_policy='null with reason; never current-table fallback or zero fill',
            provenance_requirement='stable opponent/competition/season IDs; constituent match IDs, dates, scores and independent pre-cutoff availability')
            for side in ('home', 'away') for name, formula in DEFINITIONS.items()}
