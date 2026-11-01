# FS-4 / FS-5 controlled batch

Implements [Issue #66](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/66) in isolated Lane B on `feature/fs-4-5-feature-target-engine`. HEAD and `origin/integration/flashscore-market-expansion` both equal expected base `e62851648b66786930d30c065aa241bc7e169699`. Initial working tree was clean. No commit, push, staging, PR, acquisition, model training, Forecast integration or production job was performed.

## Inspection and input boundaries

Before editing, inspected Issue #66; FS-0 discovery, observed-field/sample ledgers, coverage hypotheses and closeout; `fs-1-3-final.md`; all ten requested FS-1–FS-3 modules; the V3 temporal/data contracts; feature catalog, form/history and xG materialization; market schemas; test conventions and BT0/lambda operational context. No applicable AGENTS.md was found.

1. Eligible feature operands are FS `Capability` records for oriented canonical team metrics from finished, regulation, strictly earlier fixtures, with AVAILABLE state and independently verified publication/revision lineage strictly before the supplied cutoff. Source team identity, period and inspection proof are revalidated through the existing contract.
2. Target-fixture final metrics are settlement inputs only. Prior-fixture metrics without verified historical availability can be settlement evidence but cannot become historical feature values. Surface snapshots, current standings/profiles, target rows, future rows and same-day rows are excluded from historical feature calculation. Player features are outside this initial catalog.
3. Reuse `sample_reasons`, `Capability.prematch_usable`, timestamp parsing, canonical `dumps`, capability deserialization/validation and canonical units. Reuse the player surface validator for settlement participation. Production form/xG code supplies design conventions (select the window before checking missing operands), but its adapters and catalog are not changed or imported into the engine.
4. Both engines accept only runtime FS capabilities. Feature dictionaries, target dictionaries and scalar labels are rejected. The target engine has no feature-engine import. Historical target-fixture capabilities are excluded even if they claim an earlier publication date.

## FS-4 — feature engine

Created `v3/flashscore/feature_catalog.py`, `feature_materializer.py`, and shared `observation_index.py`. Catalog and materializer version: `fs-features-1`. The experimental catalog has 37 metric/orientation specifications and 82 window specifications per target side/scope (492 rows with both target sides and all three scopes).

Supported families:

- Goals for/against: FT, 1H, 2H, L5/L10/L20.
- Corners for/against: FT L5/L10/L20; 1H and 2H L5/L10.
- Cards and fouls for/against: L5/L10; cards require an explicit compatible counting policy.
- Shots and SOT for/against: L5/L10.
- xG, xGOT and big chances for/against: L5/L10.
- xA, box touches, goalkeeper saves, xGOT faced, goals prevented, tackles, interceptions and clearances: L5/L10.
- Cards per foul, shot accuracy and xG per shot: L5/L10. These are ratios of sums over the identical complete window. Any zero per-fixture denominator, missing operand or incompatible card policy blocks the feature. SOT greater than shots is incompatible.

Every metric supports `overall`, `home` and `away` history scopes, independently for each target team. Opponent values use the opposite side of each historical fixture; venue filtering applies to the focal team's actual historical orientation. Explicit 2H canonical operands are required for features; FS-5's optional goal subtraction is not imported into FS-4.

Feature records contain schema/materializer version, deterministic SHA-256 feature ID, target identity and match ID, focal team and target side, feature name, window, scope, cutoff and card policy, nullable value, explicit status, aggregation, required/eligible/available counts, total eligible history count, coverage rate and denominator, ordered source fixture IDs, selected observation hashes, full request/evidence provenance, per-fixture operand diagnostics and excluded fixtures. Hashes cover the complete canonical FS-1 observation. An ID identifies a feature contract/context; source hashes identify its materialized evidence and may change when source data is revised.

`FeatureStatus` distinguishes AVAILABLE, INSUFFICIENT_HISTORY, MISSING_OPERAND, BLOCKED_SOURCE, TEMPORAL_INELIGIBLE, UNASSESSED, NOT_COVERED and SEMANTIC_INCOMPATIBLE. No unsuccessful status has a numeric value. Observed zero is valid. If history is short, INSUFFICIENT_HISTORY is primary and operand failure reasons remain in diagnostics. Otherwise the documented code priority selects a primary status while retaining all per-fixture reasons. Excluded/ineligible observation diagnostics retain hashes and original capability states/reasons.

Temporal and revision behavior:

- Fixtures must predate both target day and cutoff day; all same-day fixtures remain excluded because this FS contract has no independently accredited kickoff field. This deliberately retains the conservative V3 policy even when raw timestamps look earlier.
- Publication and revision history must be verified. Publication must be no later than revision, and both must be strictly before cutoff. A discovery timestamp never substitutes for availability.
- Among as-of candidates, the greatest verified revision time (or publication time when no revision exists) wins. Conflicting full observations at equal effective time fail closed. A later post-cutoff revision does not replace an earlier accredited version. An after-cutoff discovery can document an earlier value only through the existing explicit verified publication/revision assertions.
- Select the most recent N eligible fixture dates before checking operands. Do not substitute an older xG value for a missing recent value. Equal fixture dates sort by stable match ID; no unverified intraday ordering is invented.
- Exact duplicate capabilities collapse; conflicting fixture identity/date/lifecycle/orientation raises an error. Duplicate visits cannot increase sample sizes.

Quality semantics: `n_required=N`; `n_eligible` is the number of selected fixture slots, capped at N; `n_available` is the number of selected fixtures with every required operand usable; `n_history_eligible` is the total fixture-date/lifecycle-eligible history in that scope. Coverage is explicitly `n_available/n_required`. AVAILABLE requires a complete N-fixture operand window; no partial means are emitted. These describe the supplied evidence set, not usefulness, calibration, source rights, complete population coverage or predictive quality.

The observation index is built once, with provider/team fixture indexes and capability-key observation buckets. Per target it scans only each focal team's indexed fixture history once, then performs bounded L5/L10/L20 dictionary lookups for specifications. It never scans all observations for every fixture. A 1,500-fixture regression exercises this path. Bulk all-target caching, complete historical fixture manifests and large revision-chain optimization remain future work.

FS-4 tests cover all 37 catalog paths, exact L5/L10/L20 selection, insufficient L10/L20, cutoff equality, target/future/same-day/unknown-date exclusions, home/away and opponent orientation, unrelated/wrong identities, missing versus observed zero, partial xG without backfill, all three ratios and zero denominators, blocked/noncovered evidence, duplicate/conflicting fixtures, revision selection, deterministic ordering/serialization, hashes and rejection of labels as feature inputs.

Limitations: windows are relative to the supplied capability fixture universe. This batch cannot establish that an external adapter supplied every historical fixture. Availability is not a model-readiness or completeness certification. Same-day accredited-time support, player features, historical standings reconstruction and production dataset adapters are deliberately absent.

## FS-5 — market target engine

Created `v3/flashscore/market_contract.py` and `targets.py`. Target schema: `fs-targets-1`. `MarketSpec` validates family/market/period/side/line/player combinations; corner handicaps and quarter lines are rejected. `research_markets()` declares 61 example specifications; callers can supply their own validated specs and configure team shots/SOT lines.

Supported markets:

- FT goals total O0.5/O1.5/O2.5/O3.5/O4.5; home/away O0.5/O1.5.
- FT/1H/2H BTTS; 1H and 2H O0.5/O1.5.
- HT and FT 1X2; HT/FT canonical HOME/DRAW/AWAY result strings (for example `DRAW/AWAY`).
- Regulation total corners O7.5/O8.5/O9.5/O10.5/O11.5; home/away O3.5/O4.5/O5.5; 1H O3.5/O4.5/O5.5; most corners HOME/DRAW/AWAY.
- Explicit-policy total cards O2.5/O3.5/O4.5/O5.5, home/away cards on those lines, explicit 1H total cards, red-card YES/NO. Additional explicit period/team specs use the same operand checks.
- Configurable team shots/SOT thresholds. Research examples: shots O8.5/O10.5, SOT O2.5/O3.5/O4.5.
- Explicitly requested FT player SOT thresholds with stable player identity, same-side/team participation evidence and a player-market policy.

Target records retain schema version, deterministic target key, provider/match, family/market/side/entity, period/line, full versioned settlement policy, explicit status/outcome/nullable binary label, all reasons, raw operand values and keys (including missing required keys), complete observation provenance and hashes, regulation scope, derivation version and nullable `settled_at`. No evidence field supplies a legitimate settlement timestamp here, so `settled_at` remains null. Publication/discovery times are preserved as provenance, never relabeled settlement times. Keys include fixture identity, specification, and complete policy, including derivation opt-in.

`TargetStatus`: SETTLED, UNSETTLED, MISSING_OPERAND, SETTLEMENT_INCOMPATIBLE, VOID, UNASSESSED, BLOCKED_SOURCE and NOT_COVERED. All unavailable labels are null. For overs and affirmative BTTS/red-card propositions, WIN/LOSS produces binary 1/0. Generic integer-line equality produces PUSH and a null binary label. Result markets use HOME/DRAW/AWAY strings rather than arbitrary binary coding.

Settlement policies:

- `research-regulation-settlement-v1`: finished fixtures require final compatible operands; cancelled fixtures are VOID; scheduled/live/postponed/abandoned remain UNSETTLED. These lifecycle decisions are explicit research rules, not a universal sportsbook policy.
- `CardSettlementPolicy` explicitly declares version, operand-rule reference, yellow/direct-red/second-yellow weights, exclusive-component interpretation, bench inclusion and staff inclusion. Staff inclusion requires bench inclusion in the supported scopes. Operand actor scope and rule reference must exactly match.
- `RESEARCH_CARDS` / `research-exclusive-cards-v1`: on-field players only; yellow, direct-red and second-yellow dismissal components each weight 1. Its `research-exclusive-components-v1` input rule requires yellow to exclude the dismissal caution and direct-red to exclude synthetic second-yellow red representations. A second-yellow dismissal therefore contributes once. It does not count as both a second-yellow dismissal and a direct red. Red YES means any direct-red or second-yellow dismissal under the matching scope. This rule is an assertion about certified typed inputs, not an event-to-card reconstruction adapter or bookmaker convention.
- Player policy explicitly names minimum participation minutes and allowed positions. Settlement requires a compatible numeric player SOT capability and a separately validated complete player surface whose unique row matches player/team/side and passes participation eligibility. No bench/roster assumption substitutes for this evidence.

All numeric settlement operands must be regulation-compatible; extra-time-only, shootout and ET-inclusive values never settle regulation markets. Even team lines require both team operands in this batch. Card sides must both comply with the same explicit policy. First-half cards require their own explicit typed period operands.

2H goals default to explicit canonical 2H operands. Optional `derive_second_half=True` enables separately tested `regulation-ft-minus-ht-v1`: both regulation FT and HT sides must exist and each FT score must be at least HT. A partially explicit 2H pair must agree with subtraction. Incompatible, conflicting, blocked or unknown explicit 2H observations cannot be bypassed through this fallback. HT/FT also rejects HT greater than FT. No ET-inclusive subtraction is allowed.

Settlement selects the latest observed capability per operand, including later failures; equal-time conflicts remain unresolved. It does not apply feature cutoffs because labels intentionally use target-fixture final evidence. Its result dictionaries cannot be passed into the feature engine.

FS-5 tests cover exact goal and corner thresholds, BTTS per period, HT/FT results and inconsistency, team totals, explicit/derived/invalid/ET-blocked 2H, missing bilateral evidence, most-corners draws, typed card weights and second-yellow behavior, bench/staff policies, red YES/NO, explicit half cards, shots/SOT, player identity/participation/position/minutes and malformed rosters, lifecycle handling, regulation scope, generic integer PUSH, latest failures/conflicts, stable keys and serialization.

Limitations: no sportsbook certification, odds, Value, handicap settlement, event-derived card reconstruction, player feature catalog, real coverage measurement, training or production promotion. Policy assertions and historical publication accreditation require a trusted permitted evidence adapter; this code does not independently certify them.

## Synthetic reproduction

Created `v3/flashscore/demo.py` and `examples/synthetic-fs-4-5.json`. Every identity, date, observation and sporting value in the demo is explicitly synthetic.

```bash
python -m v3.flashscore.demo
```

Demonstrates L5 goals overall/home/away; FT O2.5; HT O0.5; 2H O0.5; BTTS; corners O9.5 and most corners; cards under the named research policy; home SOT O4.5. The checked-in JSON is a concise projection of engine records, not a replacement for the full provenance-bearing schemas. A golden test verifies fresh output matches it. It makes no real coverage or prediction-quality claim.

## Validation and protected paths

Local validation only; no GitHub Actions CI is configured and no CI pass is claimed.

| Check | Result |
| --- | --- |
| `python -m pytest -q tests/v3/flashscore/test_feature_targets.py` | 158 passed |
| `python -m pytest -q tests/v3/flashscore` | 251 passed (93 existing + 158 new) |
| `python -m pytest -q tests/v3` | 1,602 passed |
| `python -m compileall -q` on all six new modules and new test module | Passed |
| `git diff --check` | Passed |
| Whitespace scan of all new files | Passed |
| `git diff --exit-code origin/integration/flashscore-market-expansion -- .` | Empty; all existing tracked files unchanged |
| Protected path comparison: `scraper/ analysis/ v3/ops/` against integration base | Empty |
| Fresh synthetic demo / golden-output test | Passed |

The unchanged-file comparison covers the production feature catalog, BT0 / J_BT_sin_temporada, lambda comparison, current Forecast and CLI, daily HTML, Value Engine, PickScore, calibration, paper betting and OOS gates. The full V3 tests pass. No live operational execution or network job was needed or performed. New imports stay within Lane B and the existing read-only validation/temporal helpers.

Exact files added (9); no existing file modified/deleted:

```text
docs/v3/flashscore/examples/synthetic-fs-4-5.json
docs/v3/flashscore/fs-4-5-final.md
tests/v3/flashscore/test_feature_targets.py
v3/flashscore/demo.py
v3/flashscore/feature_catalog.py
v3/flashscore/feature_materializer.py
v3/flashscore/market_contract.py
v3/flashscore/observation_index.py
v3/flashscore/targets.py
```

Final `git status --short`:

```text
?? docs/v3/flashscore/examples/synthetic-fs-4-5.json
?? docs/v3/flashscore/fs-4-5-final.md
?? tests/v3/flashscore/test_feature_targets.py
?? v3/flashscore/demo.py
?? v3/flashscore/feature_catalog.py
?? v3/flashscore/feature_materializer.py
?? v3/flashscore/market_contract.py
?? v3/flashscore/observation_index.py
?? v3/flashscore/targets.py
```

## Blockers, adapter boundary and FS-6–FS-8

No blocker to the isolated synthetic/replay implementation. Real-data/production prerequisites remain unresolved: permitted acquisition/reuse, a complete accredited historical fixture universe, verified publication/revision histories, real numeric cohorts and explicit bookmaker policies. No real history or timestamps were fabricated to close these gaps.

A future Lane A adapter would need to map these experimental feature/target schemas into a separately reviewed research dataset with source rights, complete fixture manifests, temporal eligibility and policy compatibility enforced. It must not import target records as X, change the production feature catalog or add markets to Forecast as part of this batch. That integration is left outside this workspace change.

Recommended follow-up scope, subject to the roadmap issues:

- FS-6: freeze an authorized research cohort and fixture universe; join X/y by stable identities with explicit cutoff and policy versions; audit leakage/missingness and establish chronological evaluation splits. Only then pursue the separately authorized model experiments. No model was trained here.
- FS-7: validate coverage and settlement semantics on accredited real observations, by market/period/competition and player eligibility; certify exact bookmaker policies before any odds mapping.
- FS-8: assess research evaluation/reproducibility and review isolated production adapters, operational compatibility and existing OOS promotion gates. No automatic Champion or market promotion follows from numeric feature availability.

Workspace changes are ready for manual review. Nothing is staged, committed, pushed or submitted as a PR.
