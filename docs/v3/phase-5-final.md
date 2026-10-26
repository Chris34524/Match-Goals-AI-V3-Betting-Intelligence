# Phase 5 final report

Branch: `feature/phase5-batch-5.1-5.6`. No staging, commit or push.

**Protocol/model implementation: validated. Real market experiments: BLOCKED.**
Implementation completion does not mean the five training/evaluation experiments ran.
No performance improvement, base-rate win, Champion win or promotion is claimed.

## Roadmap 5.1

Protocol PASS. Offline deterministic stdlib implementation; no dependencies added.
The Phase 1 JSONL/manifest are read-only and hash-verified. Existing regulation labels
were reused and checked for score/label consistency; no labels were rebuilt.
Target universe: 4,256. Labeled targets: 500 per market. Eligible rows: 0.
Kickoffs with accredited offsets: 0. The model matrix fails closed.

Features: available catalog 2.1.0 intersected with the signal surface and approved
Phase 2 recent-form/venue/sample-quality/streak/H2H extractors. Per-market sorted
feature lists, counts and versions are in each checkpoint JSON. Full source
artifact hashes and sample provenance are under ignored `v3_data/models/`.
Blocked xG/xGA, strength/schedule, advanced/GK, player/lineup, discipline, context,
news/NLP and odds/value families are excluded. Labels/scores are never features.

Exclusion reasons overlap: missing kickoff 4,256; missing target label 3,756;
canonical temporal ineligible 1,360; feature identity conflict 7; no feature evidence 7.
Target/future/same-day/duplicate/conflicting history exclusions remain in approved
Phase 2 materializers. Model matrix rejects duplicate target IDs, ambiguous joins,
blocked/unexpected features and invalid feature values.

Split policy `utc-distinct-dates-60-20-20-v1`: approximately 60/20/20 of sorted
distinct UTC kickoff dates, never rows; no date overlap. Phase 1.4 has snapshot
contracts but no reusable split policy. Real split sizes/dates/cutoffs/IDs: null,
because there are no eligible model rows. No artificial split was made.

Preprocessing: TRAIN-only median/mean/population std, all-missing fill 0 and
zero-variance scale 1; stable feature order, labels ignored. Real parameters: null.
TEST seal requires full feature/preprocessing/family/candidate/selection/model
commitment, permits one opening, and rejects repeat opening or recommitment.

Champion audit: 4,108 identified predictions among 4,256 targets; zero generated_at
and zero accredited cutoffs. `champion_comparison_status=BLOCKED`, reason
`cutoff_not_accredited`. No operational historical rerun or fabricated BT0 probabilities.

## Roadmap 5.2–5.6

Each checkpoint was processed and validated in order after its predecessor.
Independent L2 logistic models for binary markets; separate L2 softmax for 1X2.
Candidate lambdas .01/.1/1, learning rate .05, maximum 400 iterations, tolerance
1e-10. Zero initialization, deterministic full batch updates, unpenalized intercept.
Validation LogLoss then Brier then candidate index. No TEST-based tuning.

| Checkpoint | Market | Features | Labeled / eligible | Real result | Decision |
|---|---|---:|---:|---|---|
| 5.2 | BTTS | 62 | 500 / 0 | BLOCKED | `CHAMPION_COMPARISON_BLOCKED` |
| 5.3 | OVER_1_5 | 42 | 500 / 0 | BLOCKED | `COMPARISON_BLOCKED` |
| 5.4 | OVER_2_5 | 40 | 500 / 0 | BLOCKED | `COMPARISON_BLOCKED` |
| 5.5 | OVER_3_5 | 40 | 500 / 0 | BLOCKED | `COMPARISON_BLOCKED` |
| 5.6 | 1X2 | 48 | 500 / 0 | BLOCKED | `COMPARISON_BLOCKED` |

For every market: selected configuration null; TRAIN/VALIDATION/TEST Brier,
LogLoss and descriptive accuracy null; reliability buckets and OOS windows unavailable.
TRAIN-only base-rate could not be fitted. Beats base-rate: unknown. Beats Champion:
unknown; Champion comparison blocked. No real TEST was opened or prediction generated.
No model weights or real model hashes were fabricated.

5.2 BTTS: `CHAMPION_COMPARISON_BLOCKED`; it did not demonstrate a Champion win.
5.3 O1.5 and 5.4 O2.5: `COMPARISON_BLOCKED`; neither has evidence for Phase 6 approval.
5.5 O3.5: `COMPARISON_BLOCKED`, real divergence `NOT_EVALUABLE`. The synthetic
detector enforces `TEMPORAL_DIVERGENCE` when both earlier partitions improve both
losses but TEST reverses either loss or worsens materially (absolute delta .01).
No unfavorable window is removed; no tuning follows TEST.
5.6 1X2: `COMPARISON_BLOCKED`; experimental. Single softmax vector home/draw/away
is finite, nonnegative and sums to 1 within absolute tolerance 1e-12 in synthetic
verification. No real class probabilities exist. Multiclass Brier convention:
mean sum of class squared errors; no half/division by class count.

Synthetic runs validate determinism, metrics, exact Champion comparator and blocked
comparator handling, OOS windows, seal, train-only preprocessing and no promotion.
Their runtime manifests are explicitly marked implementation-only; their metrics
are not real V3 evaluation results and are not substituted into checkpoint metrics.

## Validation and integrity

- `python -m compileall -q v3 tests`: PASS.
- `python -m pytest -q tests/v3`: **1,114 passed**, including **27 new Phase 5 tests**.
- `python -m v3.models.phase5_validation`: **44 PASS, 0 FAIL**; performance BLOCKED.
- Checks 01–44 are documented in the validator and [models README](models/README.md).
- Before/after inventories, content hashes and mtimes are identical for all protected groups.
- `data/`, scraper, analysis/backups, main.py, Phase 1–4 and Champion lineage intact.
- Phase 3 odds and Phase 4 value code/docs intact. No operational requirements changes.
- `git diff --check`: PASS. No files staged; no commit/push.

PASS outcomes: 5.1 implementation and synthetic protocol/market verification; 44 integrity
and implementation checks. FAIL outcomes: none in verification. BLOCKED outcomes:
all five real market experiments, all five Champion comparisons, all real benchmarks
and OOS performance conclusions. O3.5 divergence remains unevaluable, not a negative
or positive measured performance result.

## Hashes

Canonical Phase 1 source JSONL: `fa732fdb2a7be786c99495bebbafa03956d52407e4a64d84aeb1293529a43e06`.
Combined canonical/history source hash: `9a06dd968da4a60e040c25b3096cece6fc16c68bf49cffeb74f518e61751706f`.
Protocol policy hash: `20fb6e34417ba7790a47e9732c6362977af42638d2c242e4b6fee151a61b948e`.
Model implementation hash: `922d4a32841ecf5807ca45feaf667584f2871c65d767e054d131da6768500f30`.
Eligible model dataset hash per market (canonical empty `[]`):
`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
Real model/split/predictions hashes: **null**, because no real run was executable.
Feature hashes:

| Market | Feature hash |
|---|---|
| 1X2 | `517ce534272348b4fe4c0d590a825ddd19130463240f14e9a462907ad8871d88` |
| BTTS | `01d3a588ef463c55f82ebeafcce9fdfb53faf8a79601c652a75074e7c3768c30` |
| OVER_1_5 | `ddc60c70f0b6f88ff60ee64e25755d404bf69c276c842db735cb30a63038cdfc` |
| OVER_2_5 | `e5b567c8bef60ed87f1d747dd4323e365dc361f8198b9f82acb0187675abae49` |
| OVER_3_5 | `8601ccec2e93a005a031bdc25a1248105bac08f6ac120ccf88b9a7e3592d5dd5` |

Before/after group fingerprints: [before](models/integrity-before.json),
[after](models/integrity-after.json). Full machine-readable validation:
[phase-5-validation-report.json](phase-5-validation-report.json).

## Files and runtime

Created `v3/models/`: contract, dataset, split, preprocess, metrics, binary,
multiclass, champion, evaluation, integrity, runner and phase5_validation modules.
Created two `tests/v3/test_models_*.py` files, six checkpoint Markdown files and
six compact checkpoint JSON manifests, models README/integrity evidence, this report
and the validation JSON. Modified only `.gitignore` to ignore `/v3_data/models/`.
Runtime source hash lists, integrity details and synthetic model/prediction manifests
remain ignored. Pre-existing untracked `v3_data/odds/` files were not changed.

## Remaining gaps and exact Phase 6 dependencies

1. Accredited offset-aware kickoff/cutoff tied to canonical target/event identity.
   Current Phase 1 metadata does not provide it. Supplying it requires a separately
   authorized source/contract update; protected artifacts were not repaired here.
2. Eligible labeled targets with pre-target feature lineage across at least three
   distinct UTC dates; rerun each real experiment with the frozen protocol.
3. Historical immutable Champion probability snapshots, generated before the same
   cutoff, exact event/target IDs, same regulation label definition and TEST universe.
   Otherwise Champion comparison must remain blocked.
4. Review real benchmark losses, all OOS windows and descriptive reliability;
   respect the O3.5 divergence gate and retain 1X2 as experimental.
5. Formal calibration evaluation and Champion promotion belong exclusively to Phase 6.
   This implementation provides no automatic promotion and no evidence authorizing it.
