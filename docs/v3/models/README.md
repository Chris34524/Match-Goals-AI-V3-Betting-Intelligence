# Phase 5: probabilistic challenger evaluation

Phase 5 evaluates; BT0 / `J_BT_sin_temporada` remains Champion. There is no
operational integration, calibration fit, selection by financial return,
staking, betting execution or promotion. Implementation uses Python stdlib;
no dependencies were added and operational requirements are unchanged.

Sources of truth, read in full before implementation:
[5.1](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/35),
[5.2](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/36),
[5.3](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/37),
[5.4](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/38),
[5.5](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/39),
[5.6](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/40).
`gh issue view` could not connect; the GitHub connector supplied complete bodies.
No network is used by model code, experiments, tests or validator.

The model adapter verifies the immutable canonical JSONL hash against its Phase 1
manifest. It audits existing labels with `label_values`; scores only verify
TARGETS. Labels are not reconstructed. The input universe is that canonical
artifact, not every later folder found in `data/matches`. Phase 2 approved pure
materializers read history in memory and retain source hashes and contributing
IDs/dates. Catalog and signal-surface permissions must both be `available`.
Features are market-specific and sorted; feature counts are derived, never fixed.
No times are inferred from dates, raw `hora`, file mtimes or later fixture lists.

The current canonical universe has 4,256 targets, 500 labels and no reliable
kickoff. Every real model experiment is blocked, with null metrics/model/split
hashes and no TEST opening. Empty eligible datasets share the SHA-256 of canonical
`[]`; this does not mean the source data is empty. The separate source hash binds
all history bytes and Phase 1 dataset/manifest bytes. Full source hashes remain
under ignored `v3_data/models/dataset-audit.json`. The compact checkpoints retain
their digest, counts and complete feature names.

Protocol version: `5.1.0`. Split version: `utc-distinct-dates-60-20-20-v1`.
Dates are UTC calendar dates of verified offset-aware kickoff, sorted ascending.
Cut indices floor 60% and 80% of distinct dates, clamped to three nonempty
partitions. All events sharing a UTC date stay together; timestamp ties cannot
cross partitions. This is deliberately independent of row density. Phase 1.4
supplies immutable snapshots, not reusable train/validation/test boundaries.

Preprocessing accepts TRAIN feature values only: median imputation, population
mean/std, all-missing median 0, zero variance scale 1. Columns are retained in
canonical order. Labels are ignored. Parameters, fit IDs and hashes are recorded.
Binary L2 logistic and a single multiclass L2 softmax minimize mean cross entropy
plus `lambda/2 * sum(weight**2)`; intercept is unpenalized. Zero initialization,
full batch gradient descent, learning rate .05, maximum 400 iterations, maximum
absolute step tolerance 1e-10; candidates lambda .01/.1/1. No seeds or randomness.
Models are independent per market and are not refitted on validation.

Selection: validation LogLoss, then Brier, then candidate declaration index.
TEST stays sealed until feature order, preprocessing, family, candidates,
selection/tie-break, selected configuration and model hash are committed.
A seal instance can open only once. TRAIN base-rate is never refitted for
validation or TEST and uses identical row IDs. Accuracy and fixed ten equal-width
reliability bins are descriptive; no threshold fitting. Log clipping epsilon
1e-15 affects logarithms only. Multiclass tolerance is absolute 1e-12; class
order home/draw/away. Multiclass Brier is the mean sum of three squared errors,
without dividing by two or number of classes. Per-class reliability is one-v-rest
descriptive evaluation of the same normalized softmax vector.

TEST windows partition its distinct UTC dates into three chronological groups
(or fewer if fewer dates exist). Every TEST ID occurs exactly once. Windows are
never used to retune. When exact Champion evidence is accredited, all its IDs,
event/cutoff/label version, lineage and pre-cutoff generation must match; its
window metrics are evaluated on those same rows. Otherwise comparison is BLOCKED.
No operational historical rerun or Poisson reconstruction supplies probabilities.

O3.5 divergence rule, fixed before TEST: TRAIN and VALIDATION must each improve
both Brier and LogLoss over TRAIN-only base-rate; if either TEST loss reverses
that advantage (or worsens by >= .01 absolutely), TEMPORAL_DIVERGENCE overrides
all other decisions, including a blocked Champion. Real data cannot evaluate
this gate. A synthetic pass only validates the detector implementation.

Passing to Phase 6 review requires both losses no worse than an accredited
Champion, both losses strictly better than base-rate for non-BTTS markets, and
both losses no worse than benchmark/Champion in every OOS window. BTTS uses its
separate decision vocabulary. These gates do not perform calibration fitting
or authorize promotion. No comparison can pass while Champion is blocked.

Offline commands, in checkpoint order:

```bash
python -m pytest -q tests/v3/test_models_protocol.py tests/v3/test_models_phase5_validation.py
python -m v3.models.runner --checkpoint 5.1
python -m v3.models.runner --checkpoint 5.2
python -m v3.models.runner --checkpoint 5.3
python -m v3.models.runner --checkpoint 5.4
python -m v3.models.runner --checkpoint 5.5
python -m v3.models.runner --checkpoint 5.6
python -m compileall -q v3 tests
python -m pytest -q tests/v3
python -m v3.models.phase5_validation
```

Each checkpoint requires the prior validated checkpoint. Immutable artifacts
reject conflicting reruns. Runtime synthetic manifests are explicitly separate
from actual performance evidence and are ignored by Git. They contain all model,
preprocessing, split IDs/dates, metrics, predictions and hashes. Synthetic scores
are intentionally absent from real experiment checkpoint metrics.

The validator documents and executes checks 01–44 in
`v3/models/phase5_validation.py::NAMES`. Checks are implementation/integrity checks;
its separate `performance_status` and checkpoint decisions preserve BLOCKED.
No additional numbered checks are claimed. Integrity compares current file
inventories/content hashes against pre-edit compact group fingerprints, including
mtime hashes for `data/`. Model code and report changes remain isolated to Phase 5.
The pre-edit evidence was generated locally; it is not a signed external audit.
