# FS-6–FS-8 — isolated multimarket research

Workspace implementation for [Issue #68](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/68). Branch: `feature/fs-6-8-models-effectiveness-research-forecast`. Initial HEAD and local `origin/integration/flashscore-market-expansion` both equal expected base `b22b9aa906bf3ddeecba7a947a65c668372a7a96`. Initial workspace was clean. No commit, staging, push, PR, network request, odds acquisition or betting action occurred.

## Discovery and evidence status

Read the FS-1–FS-3 and FS-4–FS-5 closeouts and the requested capability, collector, parser, normalization, manifest, coverage, audit, feature catalog/materializer, observation index, market and target modules. Inspected V3 model/dataset contracts, Champion comparison, chronological validation, calibration, promotion, effectiveness/OOS utilities and operational Forecast contract. Reused FS capability validation, canonical hashing, FS-4 materialization and FS-5 settlement replay. Research modeling/calibration are separate small abstractions and import no production model, calibration or operations module. No applicable AGENTS.md was found.

The external GitHub issue was **not fetched**: the task explicitly prohibits network calls. No repository-side copy of #68 was found; `docs/v3/final/source-issues.json` contains older issues. This implementation follows the detailed #68 scope supplied in the task. External issue reconciliation remains a manual review item.

**REAL_EVALUATION = BLOCKED. REAL_MODEL_TRAINING = BLOCKED.** Exact local blockers:

1. `v3_data/` did not exist at discovery; no runtime FS capability observation corpus, FS-4 feature cohort or FS-5 settled target cohort exists there.
2. Repository examples under `docs/v3/flashscore/examples/` are explicitly synthetic. FS-0 observed-field/sample-page artifacts document labels/surfaces, not an accredited numeric multimarket cohort.
3. Consequently there is no real resolved fixture universe joined to verified pre-cutoff publication/revision histories, complete FS-4 windows, settled FS-5 targets and compatible schemas/policies.
4. Exact acquisition/reuse authorization and a frozen, independently accredited real cohort have not been supplied. Verified timestamps/hashes in synthetic replay are software inputs, not real temporal accreditation.
5. This release deliberately has no real accreditation/validation adapter. Dataset eligibility never sets `real_accredited=True`; the training entrypoint blocks real or mixed-origin rows even if callers request a demonstration. Research Forecast cannot issue real predictions from these demo models.

These blockers do not prevent offline software validation. No synthetic result is real performance, real OOS evidence, evidence that a challenger is better in reality, or production evidence.

## FS-6 — dataset, folds and models

`dataset.build_dataset` joins FS-4 records to FS-5 records using provider/fixture identity and deterministic target/feature IDs. The caller supplies the fixture universe, feature set and an explicit settlement policy. It returns `accepted`, `rejected`, and all `reason_counts`. Missing targets in the declared fixture universe are reported. Exact duplicates collapse; conflicting target keys and feature IDs fail closed. Features are explicitly selected rather than inferred from all available columns.

Rows retain provider, match, competition, target date, target key, market family/market/period/side/line/entity, feature and target schema versions, settlement policy, ordered feature IDs/values, per-feature counts/coverage, quality, cutoff, outcome/binary label, source observation hashes, conservative label availability, synthetic origin and accreditation state. Row ordering is `(target_date, provider, match_id, target_key)`.

Acceptance requires SETTLED binary labels 0/1; every required feature AVAILABLE and finite; exact target identity; compatible versions/policies; no conflicting IDs; and no target fixture in source IDs or provenance. Source capabilities are reconstructed and their hashes verified. FS-4 selected values, counts, source IDs/hashes and policy are rematerialized; FS-5 identity, status, outcome, label, entity, score scope and hashes are resettled. This also rejects a numerically edited AVAILABLE feature or label. Unsupported player/derived policies and nonbinary outcomes remain explicitly unassessed/unsupported, rather than inventing responses.

Diagnostics include `TARGET_LEAKAGE`, `TARGET_UNSETTLED`, `TARGET_MISSING`, `FEATURE_MISSING`, `FEATURE_TEMPORAL_INELIGIBLE`, `FEATURE_SCHEMA_MISMATCH`, `TARGET_POLICY_MISMATCH`, `DUPLICATE_CONFLICT`, `INSUFFICIENT_FEATURES`, and `UNASSESSED`. A rejected row may have multiple reasons. Unselected catalog fields are outside the declared feature contract, not implicit predictors.

Because this contract has no accredited kickoff timestamp, research acceptance conservatively requires the cutoff on an **earlier UTC day** than the target date. A same-day cutoff does not become accredited by looking like a plausible kickoff time. Historical operands must already satisfy FS-4 strict earlier-day and verified publication/revision rules. Target label availability uses the latest target-operand observation timestamp, never an invented final whistle time.

### Frozen feature sets

Every set has four ordered columns: home for, home against, away for, away against; scope `overall`, window L5. All are materializable by FS-4. Availability does not imply predictive usefulness.

| Version | Exact FS-4 names, independently for both sides |
| --- | --- |
| `goals-core-v1` | `goals_for_L5`, `goals_against_L5` |
| `corners-core-v1` | `corners_for_L5`, `corners_against_L5` |
| `cards-core-v1` | `cards_for_L5`, `cards_against_L5` |
| `shots-core-v1` | `shots_for_L5`, `shots_against_L5` |

Cards require an explicit compatible `CardSettlementPolicy` in both feature materialization and settlement. Models are trained separately per provider, feature set, market family, market, period, side, line and schema/policy contract. Fixture-specific team entity IDs are retained in rows, not pooled into the response definition. No categorical/multiclass outcomes or player response is converted into a fabricated binary/count target.

### Chronological evaluation and calibration

Expanding windows keep whole fixture dates together. Defaults: minimum 100 unique train fixtures, minimum 25 unique test fixtures, target fold size 50 unique test fixtures. No random split exists. Train and test fixtures are disjoint, train dates strictly precede test dates, and every train label must be available before the earliest test cutoff. Invalid/unknown timing blocks evaluation. Partial trailing blocks below the minimum are not evaluated; their records remain in the dataset. Fold metadata explicitly lists train/test IDs and counts, bounds, feature set version, schemas/policy, model configuration, model-fit IDs and calibration IDs. Stable fold IDs hash the ordered row membership.

Calibration is optional chronological Platt scaling inside the train fold. Reserve the final quarter of whole train dates only when model-fit and calibration partitions each have at least 50 records and calibration has both classes. Model-fit label availability must precede calibration cutoffs. Otherwise calibration is `UNASSESSED` with its reason and raw probabilities remain unchanged. Outer test labels are not an input to preprocessing, model fitting or calibration. The training minimums are research diagnostics and do not change production OOS gates.

### Model registry and dependencies

Inspected installed dependencies before selecting models. System Python lacks sklearn and pytest; the existing `/home/leos/projects/qualityMind-ML/.venv/bin/python` supplies pytest 9.0.3, sklearn 1.9.0, NumPy 2.4.6 and SciPy 1.17.1. No package was installed and no requirements file was changed. The existing Match Goals environment supplies pytest but lacks sklearn; missing challengers report `UNSUPPORTED_DEPENDENCY`.

- `BASE_RATE`: exact mean of model-fit train labels, including 0/1 single-class cases.
- `LOGISTIC`: sklearn L2 LogisticRegression, C=1, lbfgs, max_iter=1000, random_state=68. StandardScaler fits only the model-fit partition. No imputation.
- `HGB`: sklearn HistGradientBoostingClassifier, 60 iterations, 7 leaves, min_samples_leaf=15, learning_rate=.1, L2=1, random_state=68, early_stopping=False. Numeric features only. Exported tree predictions are checked against sklearn to absolute tolerance 1e-12 before accepting the JSON model.
- `NEGATIVE_BINOMIAL`: `UNSUPPORTED_DEPENDENCY` here because statsmodels is absent. If installed elsewhere, this release still reports `UNSUPPORTED_RESPONSE`; it does not pretend to implement an optional count model.

Count regression and count metrics are intentionally absent: this release evaluates only settlement-replayed binary responses. It never treats an over/under label as a count. Logistic/HGB single-class training partitions report `INSUFFICIENT_CLASSES` rather than manufacturing a model.

Artifacts contain deterministic JSON parameters and model metadata, including sklearn version for sklearn fits. Inference needs only the standard library; it never unpickles code or refits a model. HGB export uses sklearn's internal numeric node structure and validates exported inference on the training matrix; a changed sklearn exporter requires compatibility review. Hashes provide reproducibility/integrity, not external accreditation.

## FS-7 — effectiveness and learning diagnostics

Binary metrics use unrounded raw probabilities:

- Brier = `mean((p-y)^2)`.
- LogLoss = `mean(-(y*log(q)+(1-y)*log(1-q)))`, with `q=clip(p,1e-15,1-1e-15)` only inside logarithms.
- Accuracy/hit rate = `mean(int(p>=.5)==y)`, descriptive only.
- Mean probability, observed frequency, and calibration-in-the-large absolute gap = `abs(mean(p)-mean(y))`.
- Fixed ECE bins `[0,.1), ... [.9,1]`; p=1 enters the final bin. Each bin reports N, mean probability, observed frequency and absolute gap. ECE = `sum(n_bin/N * absolute_gap)`; empty-bin means/gaps are null.

Segments include market, market family, model, competition, period, feature quality, coverage bucket and probability bucket. All expose prediction N and unique fixture N. Synthetic and real-accredited unique counts/states are separate. Tiny segments are descriptive; `stable_conclusion=False` avoids implying inferential certainty at any size.

Lane B diagnostic states: N<50 OBSERVE; 50–99 DIAGNOSE; 100–199 COMPARE_CHALLENGERS; >=200 FORMAL_EVALUATION. `real_n` counts only non-synthetic accredited fixtures. Synthetic records never contribute to the real state or any production OOS gate.

The deterministic, deduplicated error ledger contains stable entry ID (hash of target/model/fold), fixture, competition, market family/market/period/side, model, feature set, fold, probability/class, actual label, Brier/LogLoss components, probability bucket, quality/coverage, cutoff and model/row/feature-hash provenance. Exact duplicate predictions collapse; conflicting predictions for the same identity raise an error.

Classes are descriptive, not causal explanations: confidence is `max(p,1-p)`. An incorrect class at confidence >=.8 yields `HIGH_CONFIDENCE_MISS` and `OVERCONFIDENCE`; a correct class at confidence <.6 yields `LOW_CONFIDENCE_HIT` and `UNDERCONFIDENCE`. These per-observation labels do not establish aggregate calibration or root causes.

Research selection is predeclared: same exact target/fold membership as BASE_RATE; >=100 unique OOS fixtures; >=2 temporal folds; strictly better aggregate Brier and LogLoss; ECE no more than .01 worse; neither loss more than .01 worse in any fold. Rank eligible candidates by Brier, LogLoss, then model name. At most one candidate receives winner status. Synthetic evidence permits only `DEMO_ONLY`; actual `RESEARCH_WINNER` would require independently accredited real evidence, which this release cannot produce. There is no Champion state, promotion action, economic optimization or automatic feedback refit. The learning loop produces reviewable diagnostics for a later frozen experiment.

## FS-8 — offline Research Forecast

Entry: `python -m v3.flashscore.research.cli forecast --fixture FIXTURE.json --features FS4.json --model MODEL.json --output v3_data/flashscore_research/forecasts/research.json`. Synthetic inference additionally requires `--allow-synthetic` and a synthetic-provider target fixture. Demo models cannot predict a real-provider fixture. No web, live Flashscore, odds client or bookmaker transport exists. `network_calls=0`.

Inputs are a resolved target fixture, original materialized FS-4 records and an integrity-checked Lane B JSON model. Required features are revalidated/rematerialized. Training and label availability must precede the target cutoff. Supported schema/policy and model-fit state are checked. Demo forecast requires at least 50 model-fit rows, at least 25 outer evaluation rows and temporal evaluation metadata. Real validation remains unavailable.

Outputs include status, `RESEARCH / NOT_PRODUCTION`, target/market identity, model ID, feature set, probability, `MODEL_FAIR_ODDS`, model-fit sample size, fold/evaluation window/origin, calibration status, feature quality/coverage and blocked reasons. Real Brier/LogLoss fields remain null: synthetic folds are not legitimate real performance evidence. Fair odds are `1/p` only for `0<p<=1`; p=0 has null fair odds. These are never bookmaker odds.

All outputs have `odds_status=UNAVAILABLE`, `value_status=NOT_EVALUATED`, `EV=null`, `edge=null`, `PickScore=null`. Ranking is labeled highest research probabilities and sorts available probabilities descending; high probability is not value evidence. No best-bet, positive-EV or value-pick claim is made.

Fail-closed statuses: `NO_MODEL`, `INSUFFICIENT_FEATURES`, `INSUFFICIENT_EVIDENCE`, `MODEL_NOT_VALIDATED`, `BLOCKED`. All retain null probability/fair odds. `AVAILABLE` is possible only for the explicitly allowed synthetic demonstration in this release. Model integrity failures, schema mismatch, model/fixture temporal conflicts and synthetic-on-real requests block inference.

## Artifact layout and reproducibility

Runtime is separate from production:

```text
v3_data/flashscore_research/
  datasets/<family>-<hash>.json
  experiments/<experiment-hash>/manifest.json
  experiments/<experiment-hash>/predictions.json
  experiments/<experiment-hash>/models/<model-hash>.json
  effectiveness/<experiment-hash>/aggregate.json
  effectiveness/<experiment-hash>/segments.json
  effectiveness/<experiment-hash>/selection.json
  effectiveness/<experiment-hash>/calibration.json
  effectiveness/<experiment-hash>/error-ledger.json
  forecasts/<family>-demo.json
  demo-summary.json
```

Writes use temporary sibling files, flush/fsync and atomic replace. Paths are confined to the research root or `/tmp` for review/tests; symlink paths are rejected. Model IDs and experiment IDs are content hashes. No `latest.json` or production forecast directory is written. Runtime data remains ignored under the repository's existing `v3_data/` rule.

Commands also provide `dataset` (FS-4/FS-5/fixture JSON envelope to diagnosed rows), `experiment` (requires explicit `--synthetic-demo`; real/mixed cohorts blocked), and `demo` (full noisy replay). `--help` lists contracts. No production CLI attachment was made.

## Synthetic experiment results

The deterministic demonstration uses seed 68, 10 initial history fixtures and 320 target fixtures. Each fixture supplies noisy goals/corners/cards/shots capabilities for two sides. It is deliberately not a realistically representative league or a separable label generator. Publication assertions, identities, values and dates are all synthetic. Both feature and target engines consume those capabilities, then the dataset replay checks them. Each market has 320 accepted rows, no rejections, four expanding folds and 200 unique OOS predictions per supported model. The 20-row trailing block remains unevaluated. This demonstrates the diagnostic FORMAL_EVALUATION state on synthetic N only; **real_n remains zero and real_state remains OBSERVE**.


All numbers below are **synthetic demonstration diagnostics**, not real performance. No challenger met the frozen selection rule; all remained CHALLENGER, and BASE_RATE remained BASELINE.

| Synthetic market | Model | OOS N | Brier | LogLoss | ECE | Real N |
| --- | --- | --- | --- | --- | --- | --- |
| cards | BASE_RATE | 200 | 0.239931 | 0.672866 | 0.012336 | 0 |
| cards | HGB | 200 | 0.257818 | 0.711923 | 0.126652 | 0 |
| cards | LOGISTIC | 200 | 0.241948 | 0.677140 | 0.062937 | 0 |
| corners | BASE_RATE | 200 | 0.242637 | 0.678384 | 0.068314 | 0 |
| corners | HGB | 200 | 0.264312 | 0.731615 | 0.116830 | 0 |
| corners | LOGISTIC | 200 | 0.244611 | 0.682427 | 0.060138 | 0 |
| goals | BASE_RATE | 200 | 0.246567 | 0.686203 | 0.075720 | 0 |
| goals | HGB | 200 | 0.271415 | 0.742077 | 0.140028 | 0 |
| goals | LOGISTIC | 200 | 0.252612 | 0.698572 | 0.085066 | 0 |
| shots | BASE_RATE | 200 | 0.250765 | 0.694683 | 0.013847 | 0 |
| shots | HGB | 200 | 0.271992 | 0.742836 | 0.120680 | 0 |
| shots | LOGISTIC | 200 | 0.253482 | 0.700138 | 0.052181 | 0 |

All 12 final demo forecasts were AVAILABLE only with explicit synthetic allowance. Folds 3 and 4 exercised chronological Platt fitting; earlier folds reported UNASSESSED calibration. Models were not retuned to improve these results. The default demo and all full artifacts were generated under `/tmp/fs68-final-a/`; the concise summary is `/tmp/fs68-final-a/demo-summary.json`. These temporary files are local review artifacts, not repository data or an accredited cohort.

## Protected production boundary

Only new Lane B research modules, their tests and this closeout are added. No existing tracked file is modified. `git diff --exit-code origin/integration/flashscore-market-expansion -- scraper/ analysis/ v3/ops/` is clean. BT0 / J_BT_sin_temporada, lambda comparison, Champion state, production calibration, Value thresholds, PickScore, paper betting, daily HTML reports, odds behavior, current Forecast outputs and OOS 200 gates are unchanged. Research imports do not reach those systems. Tests import `v3.ops.forecast` read-only, smoke the existing CLI, block sockets, and verify production `latest.json` remains unchanged. No GitHub Actions CI is configured; only local validation is claimed.

## Reproduction and local validation

This workspace has no `python` command on its initial PATH. Use the already installed sklearn environment; no dependency installation is needed:

```bash
export PATH="/home/leos/projects/qualityMind-ML/.venv/bin:$PATH"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
python -m v3.flashscore.research.cli demo --output /tmp/fs68-final-a
python -m pytest -q tests/v3/flashscore/research
python -m pytest -q tests/v3/flashscore
python -m pytest -q tests/v3
python -m compileall -q v3/flashscore/research tests/v3/flashscore/research
git diff --check
git diff --exit-code origin/integration/flashscore-market-expansion -- scraper/ analysis/ v3/ops/
```

The suite covers feature/target compatibility and semantic replay, both target-leakage paths, conflicting/exact duplicates, missing/unsettled labels, missing features, schemas/policies, deterministic row order, strict whole-date folds, disjoint/expanding membership and stable IDs, timing/sample blocks, exact base rate, reproducible sklearn fits, absent dependency behavior, train-only scaling, calibration minimums and outer-label/feature isolation, metric formulas and numerical endpoints/buckets, real versus synthetic gates, error-ledger IDs/idempotency/conflicts/classification, winner comparability/calibration/sample restrictions, offline forecast statuses/fair-odds/null economic fields/ranking/JSON roundtrip, atomic artifact idempotency/path confinement, and production import/CLI/latest.json boundary.

Final local validation on the completed code and tests:

| Check | Result |
| --- | --- |
| Focused research suite | 46 passed (91.99s) |
| `python -m pytest -q tests/v3/flashscore` | 297 passed (93.73s) |
| `python -m pytest -q tests/v3` | 1,648 passed (98.50s) |
| Compileall new modules/tests | Passed |
| `git diff --check` | Passed |
| Per-file no-index whitespace check, including all 15 new untracked files | Passed |
| Protected paths versus local integration reference | No changes |
| Existing production Forecast import/CLI/latest.json smoke | Passed in research suite |
| Dataset ordering, repeated model fits, error-ledger and artifact idempotency | Passed in research suite |
| Installed environment without sklearn: BASE_RATE and unavailable-model registry | Passed |
| All 48 generated JSON model hashes and inference in environment without sklearn | Passed |
| Real accredited cohort evaluation/training | BLOCKED, for the exact discovery reasons above |

The full V3 suite blocks socket/DNS access through its existing autouse fixture. The sklearn tests preload `ssl` before that fixture replaces the socket class; the network block is preserved. Final selection tests use noisy precomputed probabilities to verify sample, fold comparability and calibration restrictions; they are unit inputs, not performance results. There is no CI result to claim.

## Exact files changed

All are new files; no existing file is edited or deleted:

```text
docs/v3/flashscore/fs-6-8-final.md
tests/v3/flashscore/research/test_research.py
v3/flashscore/research/__init__.py
v3/flashscore/research/artifacts.py
v3/flashscore/research/calibration.py
v3/flashscore/research/cli.py
v3/flashscore/research/dataset.py
v3/flashscore/research/demo.py
v3/flashscore/research/effectiveness.py
v3/flashscore/research/error_ledger.py
v3/flashscore/research/forecast.py
v3/flashscore/research/metrics.py
v3/flashscore/research/models.py
v3/flashscore/research/splits.py
v3/flashscore/research/training.py
```

## Recommended next steps

Manually reconcile the external issue, then obtain independently authorized real capabilities, a frozen fixture universe and verified temporal/revision lineage. Audit FS-4 complete windows and FS-5 settlement policy compatibility before designing a separately reviewed real accreditation adapter. Freeze the real research protocol and authorize training explicitly, then compare challengers on identical chronological folds with error/calibration review. Any future production adapter or promotion requires separate review under existing Champion/OOS controls; this release makes no production promotion recommendation.

Workspace delivery only: no staging, commit, push or PR.
