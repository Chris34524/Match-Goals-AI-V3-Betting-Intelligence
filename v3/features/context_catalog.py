"""Observable context definitions; no private psychological state inference.

Rows: name, operational definition, prerequisites. These are candidates, not
claims that Flashscore publishes a dedicated field or that an extractor exists.
"""
CONTEXT_ROWS = (
    ('derby_rivalry', 'Documented rivalry flag', 'Dated curated rivalry registry; no inference from sentiment.'),
    ('knockout_stage', 'Knockout stage flag', 'Verified competition rules and pre-match stage identity.'),
    ('final_stage', 'Final stage flag', 'Verified scheduled stage; never infer from final score.'),
    ('relegation_stakes', 'Mathematically possible relegation stakes', 'As-of table, remaining fixtures and season-specific rules.'),
    ('qualification_stakes', 'Mathematically possible qualification stakes', 'As-of table, tiebreaks and qualification rules.'),
    ('title_stakes', 'Mathematically possible title stakes', 'As-of table, remaining fixtures and tiebreak rules.'),
    ('points_to_threshold', 'Points distance to a documented standings threshold', 'Timestamped pre-target table and explicit threshold definition.'),
    ('winning_streak', 'Consecutive wins in capped observed historical sample', 'Eligible dated scores; report cap and sample size.'),
    ('winless_streak', 'Consecutive non-wins in capped observed historical sample', 'Eligible dated scores; report cap and sample size.'),
    ('scoring_streak', 'Consecutive scoring games in capped observed historical sample', 'Eligible dated scores; report cap and sample size.'),
    ('comeback_frequency', 'Historical wins/draws after trailing', 'Complete ordered goal events, disallowed-goal corrections and regulation scope.'),
    ('collapse_frequency', 'Historical losses/draws after leading', 'Complete ordered goal events and regulation scope; no psychological interpretation.'),
    ('recent_red_card_burden', 'Prior red cards per eligible historical match', 'Complete dated card events with second-yellow deduplication.'),
    ('manager_change', 'Publicly confirmed appointment date', 'Dated official appointment source and club identity.'),
    ('first_matches_new_coach', 'Count matches since confirmed appointment', 'Complete fixture ledger and accredited appointment date.'),
    ('key_player_absence', 'Absence weighted by prior minutes contribution', 'Predeclared key-player rule, as-of availability and historical minutes.'),
    ('key_player_return', 'Confirmed return after recorded absence', 'As-of availability sequence; no assumed recovery from silence.'),
    ('lineup_surprise', 'Official XI symmetric difference from latest earlier predicted XI', 'Two separately timestamped snapshots before decision cutoff.'),
    ('rotation_intensity', 'Starter changes relative to previous eligible match', 'Player IDs, complete official XI and dated previous fixture.'),
    ('transfer_negotiations', 'Publicly confirmed ongoing negotiations flag', 'Structured attributed report, timestamp and confirmation status; exclude rumours.'),
    ('transfer_disruption', 'Count confirmed squad departures in a defined window', 'Dated completed transfers and roster; no inferred turmoil or emotions.'),
    ('rest_days', 'Days since last completed fixture', 'Complete fixture ledger through cutoff; capped history is insufficient.'),
    ('fixture_congestion', 'Fixtures in preceding 14 days', 'Complete all-competition ledger with explicit empty-window evidence.'),
    ('travel_distance', 'Distance between documented fixture venues', 'Licensed venue coordinates and complete schedule; no inferred fatigue.'),
    ('venue_home_advantage', 'Home/away or documented neutral venue', 'Verified scheduled venue and as-of neutral-ground flag.'),
    ('weather_conditions', 'Observed forecast issued before cutoff', 'Permitted weather provider, venue and forecast issue timestamp.'),
    ('referee_assignment', 'Officially announced referee identity', 'Timestamped assignment; historical referee rates need complete dated events.'),
    ('match_momentum', 'Provider-defined historical minute-level pressure series', 'Permitted source, documented methodology and complete events; never target live data for prematch.'),
    ('attendance_capacity', 'Historical verified attendance relative to venue capacity', 'Dated attendance and capacity; target attendance unavailable prematch.'),
)
