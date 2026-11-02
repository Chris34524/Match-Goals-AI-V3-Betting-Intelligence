# FS-9 — Authorized real multimarket acquisition & cohort foundation

Issue [#71](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/71), branch `feature/fs-9-real-multimarket-cohort`, base `main`. FS-0 through FS-8 were inspected before implementation, including the FS-1 capability model, FS-3 manifest/coverage audit, FS-4 ObservationIndex/materializer, FS-5 targets/card policies, research accreditation blocks, Source Matrix, temporal utilities, atomic-write patterns and installed HTTP dependencies.

Software foundation is implemented in Lane B. A real cohort has **not** been acquired. `REAL_MODEL_TRAINING` remains **BLOCKED**. Workspace changes are ready for manual review; no commit, push or PR was made.

## Live result and evidence limits

| Item | Result |
| --- | --- |
| `API_FOOTBALL_KEY` | ABSENT; value never inspected or emitted |
| Live status | `BLOCKED_NO_KEY` |
| Actual API-Football HTTP requests | **0**, including status and billable calls |
| Quota remaining | Unknown; no quota request made |
| Smoke fixture/competition/season/kickoff/team IDs | None captured |
| Fields observed from real provider | None |
| Live half data | Unvalidated; no live response captured |
| Cohort status | PLANNED with unresolved IDs; no real observations |
| Real model training/evaluation | BLOCKED; no model trained |

The CLI no-key smoke was executed and returned exactly `{"live_status":"BLOCKED_NO_KEY","requests_made":0}`. The planned example was dry-run only. Official public documentation was consulted separately; no authenticated API request or billable provider request was made. Unit-test HTTP responses are mocked and their response-shaped fixture data is deterministic **synthetic test input**, never live data or model evidence.

## Delivered software

Provider-neutral Capture, Identity and ProviderAdapter contracts and an immutable reviewed registry accommodate a later secondary adapter without changing FS-4/FS-5 contracts. API-Football uses its official v3 base, environment-only authentication, GET endpoint/query allowlists, redirect rejection, timeouts, bounded transient retries, JSON validation, canonical payload SHA-256 and allowlisted numeric usage metadata. Credential echo/query checks prevent secrets entering stored responses or URLs. Every HTTP attempt counts toward the cap. There is no prediction endpoint access.

Fixture/statistic normalization preserves provider IDs, orientation, UTC kickoff, capture/response metadata, raw labels, parser version, units and provenance digests. Supported statistics are shots, SOT, shots off target, blocked shots, shots inside/outside box, fouls, corners, offsides, possession, yellow/red cards, goalkeeper saves, passes, completed passes and pass accuracy. Zero remains AVAILABLE(0); null/absent values and unavailable periods remain distinct. The only FS-1 extension adds yellow_cards/red_cards vocabulary. Existing state interpretation, FS-4 aggregation and FS-5 settlement behavior are unchanged.

FT/1H and explicitly provided 2H arrays are parsed. The additive 2H diagnostic is separately versioned, records raw FT/1H operands/formula/validation and rejects negative differences, percentages and ratios. It is never silently inserted into FS capabilities. Regulation fulltime/halftime goals remain separate from extra time and penalties; second-half goal labels use the existing FS-5 validated opt-in derivation. AET/PEN aggregated statistics cannot settle regulation markets.

Events retain provider card type/detail/actor/time separately from statistical totals. Lineups retain stable player/team IDs, formation, starter and bench roles. Actor scope and exclusive card components are not guessed. Typed cards remain UNKNOWN until an independently validated mapping satisfies existing CardSettlementPolicy; CARDS coverage readiness remains blocked.

Coverage uses the existing FS-3 audit and adds provider-local TEAM_SOT/GOALS_HT readiness without mutating FS-3 globals. It reports all five states and competition/field/period strata, with bilateral corners/1H corners/cards/team SOT/HT goals/HT-FT operands. Unresolved planned fixture IDs are explicitly reported outside resolved-fixture audit denominators. No incomplete cohort is presented as complete.

Offline tests demonstrate ordinary API-Football capabilities through ObservationIndex, FS-4 and FS-5, covering corners, SOT, yellow totals and FT/1H goals. Positive FS-4 windows use explicitly synthetic historical lineage. Actual current-capture output has no historical publication/revision certification and is correctly TEMPORAL_INELIGIBLE. Yellow totals flow through the capability/index/coverage bridge; FS-4 cards features and FS-5 cards labels stay unassessed because totals cannot establish exclusive card semantics. Capture accreditation verifies identities, kickoff/capture/digests, explicit periods, valid states and normalization replay. It never grants historical-as-of or training accreditation.

The manifest has canonical serialization, PLANNED/CAPTURED/PARTIAL/BLOCKED states, resolved ID/date/field/period selection, authorization mode, explicit budget, quota snapshots, versions, captures and hashes. The cohort CLI defaults to dry-run and requires `--live`, a key, enabled adapter and explicit maximum for live acquisition. Larger budgets require quota discovery and fail closed when unknown or insufficient. Storage is isolated under `v3_data/providers/api_football/`; only normalized records, necessary provenance, usage metadata and hashes are retained. Atomic writes reject other roots and symlinks. No full provider payload archive or production forecast write is introduced.

## Files

New modules:

- `v3/providers/{__init__,contract,registry}.py`
- `v3/providers/api_football/{__init__,client,schemas,parser,normalization,adapter,accreditation,bridge,cohort,storage,cli}.py`

New tests and documentation:

- `tests/v3/providers/test_api_football.py`
- `tests/v3/providers/fixtures/{finished,scheduled,extra_time,shootout,statistics_half,events,lineups}.json`
- `docs/v3/providers/api-football.md`
- `docs/v3/providers/examples/first-real-pilot.planned.json`
- `docs/v3/flashscore/fs-9-final.md`

Modified:

- `v3/flashscore/contract.py`: additive yellow_cards/red_cards metric vocabulary only.
- `v3/features/source_matrix.py`: distinct official API account-bound provider rows; existing Flashscore rows and permission gates preserved.
- `tests/v3/test_source_matrix.py`: retain the original two-row provider assertions while allowing the new provider rows; the new provider suite independently verifies all acquisition blocks.

No dependencies were added. `requests` is already pinned in requirements and installed in the Match Goals environment. The existing qualityMind environment supplies sklearn for the full research suite; its invocation adds the installed Match Goals site-packages path for requests. Nothing was installed into either environment.

## Local validation

```bash
/home/leos/projects/match-goals-ai/.venv/bin/python -m pytest -q tests/v3/providers

PYTHONPATH=/home/leos/projects/match-goals-ai/.venv/lib/python3.12/site-packages \
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
/home/leos/projects/qualityMind-ML/.venv/bin/python -m pytest -q tests/v3/flashscore

PYTHONPATH=/home/leos/projects/match-goals-ai/.venv/lib/python3.12/site-packages \
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
/home/leos/projects/qualityMind-ML/.venv/bin/python -m pytest -q tests/v3

/home/leos/projects/match-goals-ai/.venv/bin/python -m compileall -q v3 tests/v3
git diff --check
git diff --exit-code main -- scraper/ analysis/ v3/ops/
```

Focused provider tests: **86 passed**. Flashscore suite: **297 passed**. Full V3 suite: **1,733 passed** (81.22s); the final focused run also includes the subsequently added disabled-adapter regression test. Compileall and whitespace checks passed, including no-index checks for new files. Protected paths are identical to `main`. Existing production forecast import/CLI and artifact smoke checks are also exercised by the V3 suites. No GitHub Actions CI is configured; these are local results only.

No CI result is claimed. The focused suite was rerun after the last authorization-guard refinement; it contains 86 provider cases, one more than the preceding complete V3 collection.

## Exact blockers and next acquisition

1. API key absent: no authentication, subscription/quota, live identity, observed fields or half response can be validated here.
2. Candidate competition/season/fixture IDs have not been resolved through provider metadata. The blank manifest is an executable dry-run plan only.
3. Per-competition subscription coverage and live half payload semantics require bounded real validation. Missing half arrays fail closed.
4. Yellow/red totals do not resolve second-yellow/direct-red/actor scope. Typed cards and card market readiness remain blocked pending validated event/component semantics.
5. Current snapshots do not supply independently verified historical publication/revision lineage. FS-4 prematch history remains blocked for actual captures; snapshot time cannot reconstruct an unavailable historical as-of state.
6. No sufficiently sized captured/audited real cohort or separately reviewed real training gate exists. FS-6/8 real-data gates remain intact. A single smoke fixture would not remove this blocker.
7. Provider terms govern storage/reuse; no unverified commercial redistribution grant is claimed.

Resolve relevant Liga MX, MLS, Premier League, LaLiga, Liga Expansión if covered, Argentina and Brazil competition metadata through narrow queries. Persist stable IDs and capture references, select ten finished fixtures for an initial bounded pilot, populate the planned runtime manifest and verify quota/account scope. Recommended first pilot command, **not run**:

```bash
python -m v3.providers.api_football.cli cohort \
  --manifest v3_data/providers/api_football/manifests/first-real-pilot.json \
  --live --max-requests 21
```

Budget: one quota/status request plus twenty fixture/statistics data requests for ten preselected fixtures; retries share this maximum. Metadata resolution requests have separate explicit budgets. Remove `--live` for dry-run. This pilot validates transport/coverage and does not authorize real model training. See the [provider guide](../providers/api-football.md) for the manifest contract and metadata/smoke commands. Sportmonks remains the planned secondary provider for advanced xG/xGoT/player metrics, with no live Sportmonks implementation in this batch.

## FS-9.1 — selected match full capture

The existing FS-9 implementation is preserved. Added provider-neutral fixture selection, explicit stable-identity resolution, `FULL_MATCH_V1` plans, bounded API-Football capture, isolated atomic per-match artifacts, surface states, diagnostic additive 2H derivation and retrospective Capability → FS-3 audit → FS-5 settlement outputs. [Exact CLI examples and limitations](../providers/selected-match-capture.md).

Flashscore uses existing structured replay/manual contracts only. Live requests return `BLOCKED_SOURCE_AUTHORIZATION`; no Flashscore transport or CLI bypass exists. API-Football live software is implemented and tested with mocked HTTP; no authenticated acquisition is performed as part of this change. Real quota, subscription coverage and historical lineage remain external blockers. No training, commit, push or PR is performed.

### FS-9.1 local validation

- `tests/v3/providers`: **119 passed** (final focused rerun).
- `tests/v3/flashscore`: **297 passed**.
- `tests/v3`: **1,767 passed** (206.72s, final full collection including FS-9.1 regressions).
- `compileall -q v3 tests/v3`, `git diff --check` and new-file no-index whitespace checks: passed.
- `git diff --exit-code main -- scraper/ analysis/ v3/ops/`: passed; protected paths unchanged.
- Manual CLI checks: selected synthetic fixture dry-run made zero requests; Flashscore live returned `BLOCKED_SOURCE_AUTHORIZATION` and zero requests.

Validation used the same Python environments and environment variables documented above. HTTP capture tests are mocked, replay examples are synthetic, and these are local results, not a GitHub CI claim. No real provider/model acquisition or production training was performed.
