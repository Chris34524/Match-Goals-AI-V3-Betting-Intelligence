"""FS-3 bridge with additional team-SOT/HT-goal readiness, without changing FS-3."""
from v3.flashscore.audit import audit


def coverage(manifest, observations):
    report = audit(manifest, observations)
    units = report['units']
    for market, operands in {'TEAM_SOT': (('shots_on_target', 'FT'),),
                             'GOALS_HT': (('goals_first_half', '1H'),)}.items():
        identities = {(u['request']['fixture']['provider'], u['request']['fixture']['match_id']) for u in units}
        for provider, fixture_id in sorted(identities):
            pair = [u for u in units if u['key'][:2] == [provider, fixture_id]
                    and tuple(u['key'][2:4]) in operands and u['key'][4] == 'team']
            ready = len(pair) == 2 * len(operands) and all(u['settlement_compatible'] for u in pair)
            report['markets']['units'].append(dict(provider=provider, match_id=fixture_id,
                market=market, ready=ready, reason=None if ready else 'unavailable_or_unplanned_operands'))
        rows = [r for r in report['markets']['units'] if r['market'] == market]
        from v3.flashscore.coverage import rate
        report['markets']['totals'].append(dict(market=market,
            readiness=rate(sum(r['ready'] for r in rows), len(rows))))
    return report
