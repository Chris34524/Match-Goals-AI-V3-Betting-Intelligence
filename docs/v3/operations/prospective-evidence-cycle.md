# V3 Prospective Evidence Cycle

## Purpose

Move V3 from software-complete / real-release-BLOCKED to evidence-backed operation without changing the stable Champion or fabricating retrospective evidence.

This is an operational evidence cycle, not a new software phase.

## Entry state

- Roadmap phases 1–9: implementation complete.
- Champion: `BT0 / J_BT_sin_temporada`.
- Real OOS counter: `0 / 200`.
- Real release: `BLOCKED`.
- Real Daily Picks: `BLOCKED`.
- Closing / CLV: `BLOCKED`.
- Automated real betting: `false`.
- Human confirmation: required.

## Operating sequence

1. **O-01 — Accredited odds source**
   - Configure a permitted provider and credentials outside Git.
   - Keep live ingestion fail-closed until authorization and credentials are real.

2. **O-02 — Prospective temporal evidence**
   - Capture observations before kickoff / decision cutoff.
   - Preserve independent `observed_at` and provider timestamps.
   - No retrospective backfill for missed decision snapshots.

3. **O-03 — Real paper-betting journal**
   - Register eligible picks before kickoff.
   - Settle only after event completion.
   - Fixed simulated stake: 1u.
   - Synthetic fixtures never count toward real OOS.

4. **O-04 — Accredited closing / CLV**
   - Closing requires explicit evidence.
   - Never infer closing from the last pre-kickoff capture.
   - CLV is ex-post evaluation only.

5. **O-05 — OOS checkpoints**
   - 50 real unique settled matches: integrity / distribution review.
   - 100: preliminary stability and calibration review.
   - 200: formal gate becomes eligible for Champion/Challenger evaluation.

6. **O-06 — Champion/Challenger decision**
   - Compare only equivalent populations and windows.
   - No automatic promotion.
   - Decision states: `PROMOTE | KEEP_CHAMPION | BLOCKED`.

## Non-negotiable controls

- No future/result leakage.
- No fabricated kickoff/cutoff/prediction/closing/OOS evidence.
- No runtime artifacts under `v3_data/` committed to Git.
- No new Flashscore automation.
- No paid historical reconstruction required for the prospective cycle.
- No Kelly, martingale, adaptive stake, sportsbook order API or automatic real betting.
- Existing stable paths remain protected: `data/`, `scraper/`, `analysis/`, `analysis_backup_*`, `main.py`.
- Champion remains unchanged until the audited promotion gate explicitly allows a human decision.

## Current provider target

Initial target: The Odds API current/live endpoints already supported by the V3 odds layer. Provider terms and project credentials must be treated as separate controls: public technical availability does not itself activate project authorization.

## GitHub tracking

- O-01: Issue #54
- O-02: Issue #55
- O-03: Issue #56
- O-04: Issue #57
- O-05: Issue #58
- O-06: Issue #59

Branch: `ops/prospective-evidence-cycle`
