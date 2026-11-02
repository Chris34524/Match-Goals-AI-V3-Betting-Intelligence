# API-Football: Lane B acquisition foundation (FS-9)

API-Football / API-Sports Football v3 is the first selected official provider for Lane B fixture, corner, shot, SOT, card-total and period-goal acquisition. Its stable IDs and official authenticated JSON API fit the existing capability contracts. Sportmonks remains the planned secondary provider for advanced xG/xGoT/player metrics; no Sportmonks transport is implemented.

Official references: [API-Football v3 documentation](https://www.api-football.com/documentation-v3), [API-Sports documentation](https://api-sports.io/documentation/football/v3), and [October 2024 half-statistics release](https://www.api-football.com/news/post/api-football-new-release-available). Half statistics are documented from the 2024 season onward; actual availability depends on league, season and subscription. Consult current account terms for retention, model reuse and redistribution. This implementation does not establish commercial redistribution rights.

## Credentials and authorization

Set `API_FOOTBALL_KEY` in the process environment using your existing secret manager or shell secret workflow. Never paste credentials into a command argument, URL, artifact, issue, log or tracked env file. The only authentication header is `x-apisports-key`. No credential option exists. The reviewed provider registry must also enable the adapter. The registry and Source Matrix distinguish official account-bound API acquisition from verified historical as-of permission; there is no caller-supplied permission grant. Existing Flashscore blocks remain unchanged.

Transport accepts GET only against `https://v3.football.api-sports.io`, disables redirects, and restricts endpoints and query keys. It has a 15-second default timeout, at most one default transient retry, a short bounded backoff, status/JSON validation and no body/exception logging. HTTP 429, authentication errors, other client errors, redirects and schema errors are never retried. Retry attempts consume the explicit request budget. Usage metadata retains only numeric allowlisted rate headers, capture/HTTP response time, endpoint/query and SHA-256 of canonical JSON; it excludes request headers, account identity and raw bodies.

Supported endpoints:

| Endpoint | Use |
| --- | --- |
| `/fixtures` | Stable identity, kickoff UTC, lifecycle, scores |
| `/fixtures/statistics` | FT and explicit half team statistics |
| `/fixtures/events` | Separate type/detail/actor/time ledger |
| `/fixtures/lineups` | Team/player IDs, formation, starters and bench |
| `/standings` | Optional competition metadata |
| `/leagues` | Narrow competition/season ID resolution |
| `/status` | Quota discovery before larger future cohorts |

Predictions endpoints are prohibited by the client allowlist. Standings are metadata, not an accredited historical feature stream. Events and lineups have dedicated offline parsers; the cohort command currently acquires fixtures and statistics only.

## Normalization and semantics

The label table normalizes: shots, shots_on_target, shots_off_target, blocked_shots, shots_inside_box, shots_outside_box, fouls, corners, offsides, possession, yellow_cards, red_cards, goalkeeper_saves, passes, completed_passes and pass_accuracy. Percentages have unit `percent`; other fields use `count`. Zero is AVAILABLE(0). Null or absent fields in an inspected statistics array are MISSING. Absent half arrays are UNKNOWN (`period_not_provided`), not an asserted lack of provider coverage. Malformed numeric values are UNKNOWN. Unknown labels are preserved in provenance and never guessed into a known metric. Reordering arrays preserves values and states; the raw payload digest appropriately changes.

The FS-1 metric vocabulary adds yellow_cards/red_cards without changing existing state, feature or target semantics. Every FS capability carries provider/fixture/competition/season/team/side/period identity, capture time, source endpoint, parser version and a content-addressed provenance reference. The retained provenance sidecar resolves this reference to raw label/value, capture digest/quota and fixture metadata, including exact kickoff. ObservationIndex and FS-3/4/5 consume ordinary Capability objects. No provider IDs are mapped to Flashscore IDs. Identity is scoped by provider, entity type, stable ID and competition; names alone never merge entities.

FT reads `statistics`; `half=true` additionally reads explicit `statistics_1h` and `statistics_2h` arrays. Missing or unrecognized half representations remain unknown. These shapes have deterministic offline tests; live response shape and coverage remain unvalidated in this delivery. The adapter never subtracts FT/1H. The standalone `derive_second_half` diagnostic has an explicit count-field allowlist and version `api-football-additive-ft-minus-1h-1`; it records both raw operands, formula and validation. Negative differences and percentages/ratios are UNKNOWN. Diagnostic derivatives are not inserted into FS capabilities or FS-4/5.

Regulation goals use `score.fulltime` and `score.halftime`. Extra-time and shootout scores remain separate in fixture provenance; cumulative `goals` totals are not used. Only the existing opt-in FS-5 validated regulation FT-minus-HT contract produces second-half goal labels. FT/2H statistics for AET/PEN fixtures have unknown regulation scope and cannot settle regulation markets.

Yellow/red totals are ordinary separate observations. They do not certify exclusive second-yellow/direct-red components or bench/staff scope. Consequently typed `cards` operands remain UNKNOWN, and CARDS readiness is false. Event parsing preserves provider type/detail and uses unknown actor scope even when an actor ID exists: a player identity alone does not prove on-field participation. No sportsbook points are invented. A future independently validated event/component adapter must satisfy existing `CardSettlementPolicy` before cards features/settlement become available.

## Quota and commands

Default execution is dry-run. A live cohort requires `--live`, a key, a resolved manifest and an explicit positive `--max-requests` no greater than its declared budget. Every attempted request counts, including retries and status probes. At most three requests are permitted while quota is unknown; larger budgets require a status probe and known sufficient remaining quota before fixture acquisition. The conservative smoke maximum is three total HTTP attempts. Both daily and short-window remaining headers are honored using their minimum; counters are conservatively decremented when a later response omits headers. A budget larger than known remaining quota fails closed. Quota may change concurrently outside this process, so HTTP 429 still terminates immediately.

Resolve candidate competitions through narrow metadata calls, never league IDs remembered from names. Candidate groups are Liga MX, MLS, Premier League, LaLiga, Liga Expansión (if covered), Argentina and Brazil. Example for a future operator-authorized metadata lookup (one request):

```bash
python -m v3.providers.api_football.cli metadata \
  --country Mexico --name 'Liga MX' --season 2026 \
  --live --max-requests 1 \
  --output v3_data/providers/api_football/raw_metadata/liga-mx.json
```

Remove `--live` for dry-run. Inspect the response's stable IDs, season and coverage before selection. Each lookup has its own budget; it is not silently included in a later cohort budget.

Create a manifest with `v3.providers.api_football.cohort.plan`: supply cohort_id, created_at, provider-resolved competition_ids/seasons/fixture_ids, date_from/date_to, requested_fields, periods, request_budget and metadata_references to the saved metadata captures. IDs must be positive integers. No competition IDs are bundled in source. Fixture selection must be resolved before collection; the CLI does not discover an unbounded fixture universe. Save the result with `storage.atomic_json` under the provider root. The manifest contract records authorization mode, quota snapshot, versions, captures and content hashes; serialization is canonical and deterministic for the same supplied timestamps/inputs.

```bash
python -m v3.providers.api_football.cli cohort \
  --manifest v3_data/providers/api_football/manifests/first-real-pilot.json

# Future pilot only: 10 preselected fixtures = 20 data requests + 1 quota request.
python -m v3.providers.api_football.cli cohort \
  --manifest v3_data/providers/api_football/manifests/first-real-pilot.json \
  --live --max-requests 21
```

The second command is a recommendation, not executed in this task. The operator must first create the resolved 10-fixture manifest with budget 21 and verify account quota/terms. `half=true` is requested with statistics when half periods are planned, so this uses two data requests per fixture. Retries share the same cap and can leave a cohort partial. No unbounded live mode exists.

Optional future smoke, three total data requests, no separate quota request:

```bash
python -m v3.providers.api_football.cli smoke --live
```

It queries yesterday's finished fixtures, chooses one stable ID, then requests FT and half statistics for that fixture. It makes no subsequent fixture loop. No-key smoke returns `BLOCKED_NO_KEY` with zero requests.

## Storage, coverage and accreditation

Artifacts are isolated under `v3_data/providers/api_football/{raw_metadata,normalized,audit,manifests}/`, ignored by Git. The manifest is the cohort record; no full provider response is retained. Writes use temporary siblings, fsync and atomic replace, confined to this root or `/tmp` for tests/review; symlink paths are rejected. No production forecast output path is permitted.

Manifest states: PLANNED before network; CAPTURED when all requested generated operands are available; PARTIAL when some fields/fixtures fail or are missing; BLOCKED when no usable acquisition completes. Default requested cards/half fields often make a successful transport capture PARTIAL. This status does not imply training readiness. Unresolved planned fixture IDs remain explicitly listed; FS-3 audit denominators cover resolved fixtures only and declare this limitation, never pretending unresolved IDs were successfully audited.

`bridge.coverage` reuses FS-3 states/strata/denominators and adds bilateral TEAM_SOT and GOALS_HT readiness to existing TOTAL_CORNERS, CORNERS_1H, CARDS and HT_FT. It does not mutate global FS-3 market definitions or production gates. NOT_COVERED requires existing explicit noncoverage evidence; absence of data alone does not assert it.

`accreditation.assess` verifies payload hashes, identities, kickoff parsing, captures, periods, valid capability state and deterministic normalization replay. Only successful live provider captures can receive capture accreditation. Offline fixtures have synthetic evidence quality and are never real observations. Capture accreditation is separate from historical as-of or training accreditation. Current API snapshots supply no verified publication/revision history; the adapter never manufactures it. Thus actual captures remain temporally ineligible for FS-4 historical prematch features. Tests use explicitly synthetic lineage to demonstrate the positive FS-4 route and confirm the real adapter route remains blocked. FS-5 settlement still requires final, regulation-compatible operands.

`REAL_MODEL_TRAINING` remains BLOCKED until a sufficiently sized real cohort, audited coverage, card semantics where needed, verified temporal lineage and a separately reviewed real research gate exist. One smoke fixture is transport evidence only. No training, challenger evaluation, model promotion, production modification or live bulk collection occurs in FS-9.

A blank [planned pilot manifest](examples/first-real-pilot.planned.json) is included for review. It deliberately contains no competition or fixture IDs and cannot run live until resolved. Copy it into the runtime manifests directory, populate IDs from provider responses, attach metadata references and set its declaration time before capture. This is a plan, not synthetic or acquired real evidence.

## Selected full capture (FS-9.1)

See [selection, FULL_MATCH_V1, budgets, replay and bridge examples](selected-match-capture.md). Existing cohort and smoke commands remain available. Selected capture adds official fixture H2H and player-statistics endpoints to the bounded allowlist; it does not enable prediction access or change historical accreditation.
