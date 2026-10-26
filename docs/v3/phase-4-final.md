# Phase 4 — Offline value and minimum acceptable odds

Issues [32](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/32)
and [33](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/33)
implemented sequentially on `feature/phase4-batch-4.1-4.2`.

4.1 provides validated probabilities/fair odds, complete canonical outcome sets,
overround, proportional no-vig, absolute/relative probability edge and signed
unit EV. Five markets: 1X2, BTTS, OVER_1_5, OVER_2_5, OVER_3_5. All evidence,
source, active-price and pre-match gates are fail-closed. Checkpoint 4.1 passed
compileall and 1026 V3 tests before any 4.2 implementation.

4.2 adds immutable per-market policies, max(markup, EV) minimum prices,
PASS/NO_BET/BLOCKED selector, evidence replay, predefined-policy sensitivity,
and standalone offline JSON/JSONL CLI. Defaults are synthetic and have no
historical validation. They were not selected with outcomes, ROI or TEST/OOS.
The V3 suite after 4.2 contains 1087 passing tests.

See [4.1 checkpoint](value/checkpoints/4.1.md),
[4.2 checkpoint and CLI examples](value/checkpoints/4.2.md), and
[machine validation report](phase-4-validation-report.json).

## Integrity evidence

`value/integrity-before.json` fingerprints every preexisting tracked file before
implementation. `integrity-after.json` compares the exact same inventory.
`protected-before.json` / `protected-after.json` also inventory ignored core
files and mtimes using the unchanged Phase 3 validator (including data/, scraper/,
analysis/, backups, main.py and BT0/J_BT lineage). The protected baseline was
recorded after 4.1 validation; every entry is additionally checked against the
preexisting Phase 3 baseline, so earlier accidental core writes cannot be hidden.
The initial working tree contained untracked v3_data/; its separate inventory,
recorded before final validation, is compared without writing to that tree.

All Phase 3 source, tests and documentation remain unchanged. Champion artifacts
are neither trained nor promoted. There is no separately present J_BT local tree;
its absence is preserved and reported, rather than fabricated as model evidence.

`value/artifacts-manifest.json` contains SHA256 for Phase 4 source, tests, examples,
checkpoints and baseline artifacts. Mutable generated after-manifests and the
validation report are excluded to avoid self-referential hashes. Reported example
hashes cover engine, selector and sensitivity JSON. Report content is deterministic
for identical files/environment; pytest timing is excluded. Re-running validation
must preserve all content hashes unless an intentional artifact changes.

## Validation and limits

`python -m v3.value.phase4_validation` runs compileall and the full V3 suite,
checks 28 groups of invariants, compares protected content and mtimes, verifies
branch/scope, and writes the report/manifests. Network is denied in validation
and throughout V3 tests by the existing socket/DNS autouse guard. The only
network used during implementation was the requested read of the GitHub issues;
Phase 4 runtime, CLI, fixtures and tests require none.

No stake, Kelly, bankroll, order execution, main.py integration, model promotion,
future result, post-cutoff label, closing decision input or post-kickoff input.
Production remains BLOCKED with the current source matrix. NO_BET is normal for
eligible candidates without sufficient policy value.

Phase 5 depends on these replayable contracts and versioned policies. Any future
production use still needs genuine provider authorization and appropriate model
validation; synthetic permissions must never become a production grant. No real
coverage, probability calibration or historical policy performance is claimed.

All changes remain uncommitted in the working tree; no add/commit/push performed.
