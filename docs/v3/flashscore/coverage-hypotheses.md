# FS-0 hypotheses for the future FS-3 audit

These are hypotheses, not measured coverage, forecasts of profitability, or acquisition permission. The 21-sample purposive ledger is too small and index-dependent to estimate coverage. No percentages are fabricated. Field visible in one league != universal coverage; availability != authorization.

| Hypothesis | Motivation | Falsifier / required audit |
|---|---|---|
| Corners may be CORE | Labeled paired team corner counts in several indexed overall tables | Insufficient bilateral counts, regulation ambiguity, competition/season gaps, half failures |
| Cards may be CORE for some supported competitions | Player card columns and timeline foul annotations suggest a discipline surface | Team yellow/red counts and types are still UNKNOWN here; validate colors, second yellow, bench/staff and periods before any classification |
| Basic 1H/2H stats may have high coverage where overall stats exist | Period navigation plus half URLs with indexed rows | No active selected-half state was verified; non-additivity, empty halves or wrong cached period falsify |
| Team shots and SOT may be CORE in covered competition strata | Explicit paired team counts across several examples, including lower-coverage candidate | Audit all prespecified fixtures, not just those showing Stats tabs |
| xG is competition/season/provider conditional | Visible in selected major leagues and indexed Liga Expansión preview | Measure across competition tiers and archive ages; cannot classify by league reputation |
| xGOT/xA may be more limited than basic stats | Advanced labeled rows observed; no universal evidence | Compare joint and per-field denominators, FT versus halves, early versus recent seasons |
| Player stats may be CONDITIONAL/EXPERIMENTAL | General/top-stat rows seen in Liga Expansión and Argentina | Numeric completeness, IDs, keeper rows, participation/minutes, category and historical-depth gaps |
| Lower-tier coverage may be mixed rather than uniformly absent | Ghana candidate has basic shot stats; Liga Expansión has richer indexed content | Verify league identity; inspect full stats and multiple fixtures before interpreting preview omissions |
| Historical tables/H2H may be visible but unusable as prematch inputs | Current H2H includes target; live table lacks historical publication lineage | Find permitted historical snapshots with publication/revision evidence; measure usable coverage separately |

## Proposed thresholds — NOT VALIDATED

For a prespecified eligible stratum and required operand set:

- **PROPOSED CORE: >= 80%**.
- **PROPOSED CONDITIONAL: 50–79%** (for unrounded rates, 50% <= rate < 80%).
- **PROPOSED EXPERIMENTAL: < 50%**.

These are proposed FS-3 classification thresholds, not current measured findings or production gates. Never classify an uninspected or entirely blocked stratum as EXPERIMENTAL just because no observations were obtained; report UNKNOWN/BLOCKED and an unassessed tier. A high pooled rate cannot enable a poorly covered competition or period.

## Future audit design

1. Freeze a manifest of fixtures independently of Stats-tab visibility. Stratify by competition, season/stage, competition tier, archive age and lifecycle (scheduled/live/finished). Include Premier League, LaLiga, Serie A, Bundesliga, Liga MX, MLS, Liga Expansión, Brazil, Argentina, Champions/Europa and a verified lower-coverage league. Verify competition IDs and fixture dates rather than trusting FS-0 inferred attribution. Define minimum sample size and sampling seed before inspection; do not choose a target sample size based on observed success.
2. Obtain an authorized route or permitted/licensed source first. Budget conservative inspection limits with a stop-on-denial/error policy; no bypass or automatic retry loop. A reviewer can finish FS-0 browser confirmation through ordinary permitted navigation without authorizing a collector. Do not integrate collection into production.
3. Inspect summary, events, Overall, active 1H, active 2H, lineups, H2H, standings and player categories separately. Log every attempted surface, including missing tabs, unavailable fields, unresolved periods and blocked access. Record a selected-period indicator rather than trusting a URL. Reconcile FT/HT/2H regulation goals; test counts and never subtract percentages. Include extra time, shootouts, own goals, cancelled goals, second yellow, bench cards and keeper substitutions as semantic checks.
4. Unit for team metrics: unique fixture × field × period × side. Require both sides for totals/most/handicap markets. Unit for player props: unique participating player-fixture × field with explicit eligibility/position/minutes rules; nonparticipants and keepers use separate denominators. Deduplicate fixture IDs, URL aliases, revisits and player rows. A revisited observation is not another fixture.
5. Report AVAILABLE/MISSING/NOT_COVERED/BLOCKED/UNKNOWN counts and reasons for every stratum. Primary operational completeness denominator is **all prespecified eligible fixture/operand units**, including blocked and unknown units; numerator is usable, validated required operands. Report successful-inspection conditional availability separately, with the denominator explicitly stated. Show technical visibility, numeric completeness, settlement-compatible availability and prematch-temporal usability separately; no conflation.
6. Report uncertainty intervals and sample sizes alongside rates; account for clustering by fixture/competition/player. Track inspection failures separately from confirmed non-coverage. Prespecify whether the proposed tier applies to point estimate or conservative interval bound before calculating results. Preserve raw unrounded rates and do not average league percentages without weights/denominators.
7. Assess joint market readiness: FT/HT goals for HT/FT; two team counts for corners; typed cards and settlement rules; resolved player counts and participation for props. A single available input is insufficient. Compare missingness by match status/date/team and league; do not select only high-profile matches or only players with ratings.
8. Keep observation time, provider publication time, event time, revisions and target cutoff distinct. Post-match discovery fields can be settlement operands or eligible prior-match history only. Exclude target/future/unverified same-day inputs and preserve the existing policies; no fabricated as-of timestamps. Current standings and player pages cannot reconstruct old snapshots.
9. Store permitted metadata/provenance, null reasons and capability revisions in a separate audit artifact. Do not mutate existing match data, tune models, alter thresholds or generate OOS/production-improvement claims. Coverage results do not authorize acquisition or market release.

## FS-0 follow-up dependencies

Direct opens in this environment frequently yielded shells; therefore verified browser-rendered tabs, selected-half contents, team-card types/counts and most player categories remain open. Competition/stage attribution and the Ghana date conflict need reconciliation. The official player article's initial league list is product context, not the FS-3 sampling frame. No full FS-0 rendered-surface acceptance or quantitative FS-3 completion is asserted.
