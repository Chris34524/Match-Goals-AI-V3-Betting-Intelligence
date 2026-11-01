# FS-1–FS-3 controlled batch

Implements [Issue #64](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/64) on `feature/fs-1-3-capabilities-collector-audit`, based on merged FS-0 commit `b64597f99bf2d85838d349edf4b0683a2be4d47e` (`origin/integration/flashscore-market-expansion`). Workspace delivery only: no commit, push or PR. This is isolated Lane B research code. Lane A has no adapters into it.

## Discovery and implementation map

Before editing, reviewed Issue #64 and all five FS-0 artifacts here: `surface-discovery.md`, `observed-fields.json`, `sample-pages.json`, `coverage-hypotheses.md`, and `fs-0-final.md`. Also inspected the V3 data/feature contracts, source registry and tests, conservative temporal policy, parser/CLI conventions, artifact versioning, and existing scraper code. The branch initially equaled the integration base and the workspace was clean. No applicable AGENTS.md was found. Existing samples are metadata/label evidence, with selected-half, identity and rendering gaps; there is no local sporting-data corpus to measure.

Implementation order and gates:

1. FS-1: isolated immutable request/evidence records; evaluated states, serialization and tests. Initial gate: 30 tests passed.
2. FS-2: structured synthetic/permitted-manual replay parser; typed surfaces and events; source authorization boundary. Initial combined gate: 53 tests passed.
3. FS-3: independently declared target manifest; deduplicated units, deterministic latest-observation selection, coverage and joint readiness. Final combined tests include subsequent contract hardening.

The existing feature catalog and Source Matrix are reused, not extended or promoted. `v3.data.temporal.sample_reasons` supplies target/future/same-day exclusions. Explicit aliases bridge existing contract terms (`passes_completed`, `saves`, `touches_in_opposition_box`) to canonical stat names without changing those contracts.

## FS-1 contract

Files: `v3/flashscore/__init__.py`, `contract.py`; tests in `tests/v3/flashscore/test_contract.py`.

Version: `fs-1-3.1.0`. `Fixture`, `Request`, `Evidence`, and `Capability` are the runtime schema; constructor validation enforces known states, periods, lifecycles, orientation, compatible surfaces, units and typed values. All requested capability names are represented. Unresolved inspected identities can be retained as null and yield UNKNOWN; a target request itself requires a resolved identity.

The only capability states are AVAILABLE, MISSING, NOT_COVERED, BLOCKED and UNKNOWN. AVAILABLE requires verified fixture/competition/season/stage/team identity, lifecycle, surface, independently selected period, oriented operand and valid typed value. Zero is observed data. MISSING needs successful inspection, explicit expected coverage and `absent_value`; dashes/nulls of unknown meaning remain UNKNOWN. NOT_COVERED requires a scoped provider statement or licensed coverage-registry reference; conflicting numeric evidence is UNKNOWN. Access/policy restrictions are BLOCKED, without bypass. Parent surface availability does not propagate to children.

Observation JSON preserves the full request and raw evidence, including URL, sample reference, observed time, nullable publication/revision times, parser/schema versions, period proof, null reason, score scope and derivation references. `normalized_value` is null unless AVAILABLE. Independent dimensions are technical visibility, acquisition authorization, evidence quality, settlement compatibility, and temporal usability (a target-dependent method, never inferred from post-match availability). `Capability.from_dict` revalidates the schema and rejects serialized decisions that disagree with evidence. JSON is canonical UTF-8 with sorted keys and no NaN/infinity.

Temporal usability requires a different, strictly earlier completed fixture, regulation scope, independently verified publication and revision history strictly before cutoff. Observation time is never substituted for publication. Target-match performance cannot be used for its own prematch features, even if serialized timestamps claim otherwise. This evaluates temporal eligibility only: it grants no feature-reuse/acquisition rights. Surface snapshots such as current standings/H2H/lineups are never automatically accepted as historical features.

Limitations: there is no derived-operand adapter. Derived records retain provenance but remain UNKNOWN, including claims with unvalidated operand references. The records are evidence supplied by a trusted permitted adapter, not an independent certification of provider statements, licenses or publication assertions.

## FS-2 collector and replay

Files: `collector.py`, `parser.py`, `normalization.py`, `events.py`, `replay.py`, `cli.py`; tests in `tests/v3/flashscore/test_replay.py`.

`StructuredParser` implements the `Parser` protocol for `fs-replay-1` samples. `fs-replay-batch-1` envelopes contain explicit requests and samples. Only `synthetic` or `permitted_manual` samples with a permission/provenance reference are accepted. The reference is an auditable input assertion; callers must independently establish permission. It cannot authorize live acquisition.

Implemented and tested **structured replay** surfaces:

| Surface | Implemented evidence |
| --- | --- |
| Summary | Typed per-side FT/1H/2H goal cells, each under its explicit selected-period proof and score scope |
| Stats Overall, 1H, 2H | Individually oriented canonical numeric/typed cells; surface and child states evaluated separately |
| Events | Typed goal, penalty goal, own goal, cancelled goal, yellow, second yellow, red and substitution ledger |
| Lineups | Stable player/team IDs, side, official/predicted kind, starter/bench role and position |
| Standings | Stable team ID, rank, played, integer points and explicit snapshot reference |
| H2H | Dated resolved fixture/team IDs and regulation scores; no automatic target-row exclusion or feature adapter |
| Player stats | Stable IDs, side/team, participation, minutes, position and independently evidenced numeric cells |

These are minimal typed input contracts, **not real Flashscore HTML parsers or verified website selectors**. Arbitrary HTML, shells, incomplete typed rows, missing identities, URL-only periods and ambiguous event types cannot become usable values. Loaded containers need a completeness/snapshot reference; events also require stable event IDs, period, scope, time and actor attribution. Typed cards retain yellow, direct-red and second-yellow dismissal components; an actor scope is mandatory, and compatible settlement rules are separately required for readiness. Second-yellow cautions and synthetic red representations share one dismissal ID. The diagnostic event dismissal count is never used as a team-card market total; bench/staff/unknown actors remain explicit. Cancelled goals are retained as that event type, without score derivation.

`collect_live` consults the existing source registry for the exact provider/method/family and returns BLOCKED under its current contents. There is no network transport, browser, retry loop or live CLI. Even a future registry grant would stop at `live_transport_not_implemented` pending a separately reviewed adapter. No authorization state changes were made.

Replay limitations: no website acquisition, locale/text/HTML parsing, automatic player identity reconciliation, historical-snapshot reconstruction, bookmaker settlement adapter, score derivation, or production feature ingestion. Empty lists mean a referenced complete structured inspection, not inferred provider noncoverage. Individual missing fields require their own explicit coverage evidence.

## FS-3 audit semantics

Files: `manifest.py`, `coverage.py`, `audit.py`, plus the isolated CLI; tests in `tests/v3/flashscore/test_audit.py`.

The `fs-audit-manifest-1` manifest declares fixtures and field/surface/period/side requests independently of observations. It must precede observation timestamps. This is a structural check, not cryptographic proof of preregistration; freeze/review its digest before collecting evidence. Observations outside the declared frame are rejected. Fixture strata include competition, season, stage, competition tier, archive age and lifecycle; reports additionally distinguish field, period, level and side. Unknown tier/archive labels remain explicit.

Team units are unique provider-fixture × canonical field × period × side. Exact duplicate fixtures/requests deduplicate; conflicting identities/strata/surfaces raise errors. Player units are unique accredited participating player-fixture × field (FT); the manifest declares minimum minutes, allowed positions and participation references. Unused bench, excluded positions and insufficient minutes are separate eligibility exclusions. Unknown eligibility/rosters are reported separately and force UNASSESSED tiers; their unknown roster size is never invented or silently treated as zero. Player readiness rates are conditional on accredited eligibility, with unassessed eligibility counts alongside them.

Revisits never increase a unit denominator. The latest observation timestamp wins, including a later failure; equal-time conflicting records yield UNKNOWN regardless of input order. Exact duplicate observations are reported separately. Complete serialized observations and their selected digests preserve audit lineage. Freeze the observation artifact alongside the manifest.

Every report separates all target units, attempted units, successful inspections, conclusive assessments and the five state counts. Successful inspection means the identified correct surface/period/entity was inspected successfully; an uninterpretable dash can therefore be successfully inspected yet UNKNOWN. Conclusive assessments are AVAILABLE + MISSING + credible NOT_COVERED. Authorization-gate refusals count as attempted units, not successful network calls.

- Successful-inspection conditional availability = AVAILABLE / successfully inspected units, including inspected ambiguous values in that denominator.
- All-target operational completeness = AVAILABLE / all predeclared eligible units, including BLOCKED/UNKNOWN. This is typed operand completeness for the offline research workflow, not permission for production consumption.
- Settlement-compatible availability additionally requires finished regulation evidence; live, extra-time, shootout and combined scores cannot settle these regulation markets.
- Temporal prematch usability is evaluated only with explicit `target_context`; otherwise it is null/unassessed, not zero.
- Global rates pool counts/denominators; league percentages are never averaged.

Each rate includes n, numerator, denominator, unrounded rate and a descriptive Wilson 95% interval. These intervals do not model fixture/player clustering or the sampling design and must not be read as population inference or promotion gates.

Research tiers use the unrounded all-target point estimate: CORE >= .80; CONDITIONAL >= .50 and < .80; EXPERIMENTAL < .50. Default evidence requirements are at least 30 conclusive inspections and a 1.0 conclusive fraction. These conservative defaults are predeclared/configurable through `min_successful_inspections` (requiring conclusive inspection) and `min_assessed_fraction`. Insufficient or unassessed evidence gives UNASSESSED, including UNKNOWN/BLOCKED-only strata. These are research defaults, with no production promotion effect.

Joint readiness covers TOTAL_CORNERS, MOST_CORNERS, CORNERS_1H, CARDS, HT_FT and PLAYER_SOT. Both team operands are mandatory; unplanned operands are listed explicitly. HT/FT requires both sides at both periods and consistent HT <= FT scores. Cards require typed components, matching actor scopes and matching settlement-rule references. PLAYER_SOT requires eligible participation, player ID and an available regulation SOT count. Readiness is operand research only; odds/liquidity/bookmaker rules and release decisions remain outside this batch.

The audit indexes fixtures, player rosters, targets and observations. It iterates units with stable keys and sorts outputs; no fixture-by-observation scan or webpage bodies are involved. A 1,500-fixture / 3,000-unit deterministic regression is included.

## Reproduction and artifacts

All example identities, timestamps and sport values are explicitly synthetic. They are not copied real matches or publication times. The small example deliberately uses `min_successful_inspections=1` to exercise labels, not estimate real coverage.

```bash
python -m v3.flashscore.cli replay \
  --input docs/v3/flashscore/examples/synthetic-replay.json \
  --output /tmp/fs13-replay
python -m v3.flashscore.cli coverage \
  --manifest docs/v3/flashscore/examples/synthetic-manifest.json \
  --observations /tmp/fs13-replay/observations.jsonl \
  --output /tmp/fs13-audit-a
```

Tracked review artifacts are `examples/synthetic-manifest.json`, `examples/synthetic-replay.json`, and the full generated `examples/synthetic-coverage.json`. Replay emits canonical `observations.jsonl` and `replay-manifest.json` with input/output SHA-256 digests under `/tmp/fs13-replay`. Coverage emits `coverage.json`. Running coverage twice to separate directories produces byte-identical output; the checked-in example is tested against a fresh replay/audit.

Synthetic demonstration only: 6 target units, 4 attempted, 4 successful/conclusive inspections, 3 AVAILABLE, 1 MISSING, 2 UNKNOWN, 0 BLOCKED/NOT_COVERED. Conditional availability is 3/4; all-target completeness is 3/6; the pooled tier is UNASSESSED. Bilateral FT corners are ready as synthetic operands; missing joint 1H evidence is not ready. Target prematch usability is 0/6. **No real live coverage measurement was performed or claimed.** FS-0 label samples are not promoted into numeric coverage observations.

## Operational boundary and follow-up

No existing tracked production file is changed. In particular `scraper/flashscore.py`, all `analysis/`, BT0 / `J_BT_sin_temporada`, lambda comparison, Forecast and its CLI, daily reports, Value Engine, PickScore, calibration, paper betting and OOS gates are untouched relative to the integration base. No scraping, forecast generation, odds requests, live jobs, daily reports or model operations were run.

Protected integration is deliberately absent: a future adapter must translate independently permitted, identity-resolved evidence into this replay protocol and separately enforce the existing feature/label temporal and source rights contracts. If it requires changing a protected operational component, stop that integration and review its boundary separately.

Blockers for live/production work: no exact-method/family verified grant, no live transport or real HTML parser, no accredited numeric cohort, no verified historical publications/revisions, and no bookmaker settlement certification. These do not block the completed offline batch.

Recommended FS-4 + FS-5: review exact acquisition/reuse/retention permissions and a stratified frozen sampling frame; then develop isolated permitted adapters and explicit period/score/card/player settlement contracts with real authorized evidence. Reconfirm the roadmap issue scope before starting. Keep Champion, Value/PickScore, calibration and OOS promotion controls unchanged.

## Validation

Local validation (no GitHub Actions CI claim):

| Check | Result |
| --- | --- |
| FS-1 focused tests (`test_contract.py`) | 39 passed |
| FS-2 focused tests (`test_replay.py`) | 25 passed |
| FS-3 focused tests (`test_audit.py`) | 29 passed |
| Combined focused suite | 93 passed |
| Full `python -m pytest -q tests/v3` | 1,444 passed |
| `python -m compileall -q v3/flashscore tests/v3/flashscore` | Passed |
| Replay/audit reproducibility and checked-in golden output | Passed, byte-identical coverage output |
| `python -m v3.ops.cli --help` | Passed |
| Import `v3.ops.forecast` and invoke existing CLI `forecast` dispatch with `generate` mocked | Passed; no forecast/network/data writes |
| `git diff --check` plus whitespace scan of all new files | Passed |
| `git diff --exit-code origin/integration/flashscore-market-expansion --` | Passed: every existing tracked file unchanged |
| `git diff --name-only origin/integration/flashscore-market-expansion...HEAD` | Empty: HEAD equals the FS-0 integration base; uncommitted additions listed separately |

Exact new files (18); no existing files modified or deleted:

```text
docs/v3/flashscore/examples/synthetic-coverage.json
docs/v3/flashscore/examples/synthetic-manifest.json
docs/v3/flashscore/examples/synthetic-replay.json
docs/v3/flashscore/fs-1-3-final.md
tests/v3/flashscore/test_audit.py
tests/v3/flashscore/test_contract.py
tests/v3/flashscore/test_replay.py
v3/flashscore/__init__.py
v3/flashscore/audit.py
v3/flashscore/cli.py
v3/flashscore/collector.py
v3/flashscore/contract.py
v3/flashscore/coverage.py
v3/flashscore/events.py
v3/flashscore/manifest.py
v3/flashscore/normalization.py
v3/flashscore/parser.py
v3/flashscore/replay.py
```

Final `git status --short`:

```text
?? docs/v3/flashscore/examples/
?? docs/v3/flashscore/fs-1-3-final.md
?? tests/v3/flashscore/
?? v3/flashscore/
```

No files staged; no commit, push or PR. Workspace changes are ready for manual review.
