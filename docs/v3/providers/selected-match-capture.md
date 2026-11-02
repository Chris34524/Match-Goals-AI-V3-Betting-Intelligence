# FS-9.1 selected match capture

`python -m v3.providers.cli` adds provider-neutral selection and the versioned `FULL_MATCH_V1` profile without replacing the FS-9 cohort CLI. All examples use local fixture universes or explicit provider-local IDs. Capture does not discover today's fixtures automatically: export an authorized fixture universe first.

```bash
# Select today's fixture interactively: enter 1, 1,3,7, 1-5 or all.
python -m v3.providers.cli select --provider api_football --source data/partidos_hoy.json
# One fixture, dry-run (no network, no writes).
python -m v3.providers.cli full-capture --provider api_football --match-id 900001
# Several fixtures, dry-run.
python -m v3.providers.cli full-capture --provider api_football --source data/partidos_hoy.json --indices 1,3,7
# Explicit IDs can repeat; text source accepts one provider ID per line.
python -m v3.providers.cli full-capture --provider api_football --match-id 900001 --match-id 900002
python -m v3.providers.cli full-capture --provider api_football --source data/fixture-ids.txt --indices all
# Live: set API_FOOTBALL_KEY in the environment, never a CLI argument.
python -m v3.providers.cli full-capture --provider api_football --match-id 900001 --live --max-requests 8 --build-capabilities --coverage-audit --settle-targets
# Flashscore: structured replay/manual envelopes only, zero network requests.
python -m v3.providers.cli full-capture --provider flashscore --match-id ABC123 --replay-dir data/replay
```

JSON input accepts a list or `{ "fixtures": [...] }` or official API-Football `{ "response": [...] }`. Generic rows use `provider`, `provider_fixture_id`, optional `kickoff`, `competition`, `season`, `home`, `away`, `source_fixture_reference`; multiple provider mappings use `provider_ids`. IDs are never transferred across providers. The terminal shows index, time, competition, teams, known provider ID and capture status. Automation must provide indices or explicit IDs; there is no implicit all selection.

Unmapped selections report `PROVIDER_ID_UNRESOLVED`. The explicit resolver consumes `resolution_context.api_football` containing `date`, `competition_id`, `season`, `home_id`, `away_id`; these must be stable API-Football identities. It verifies exactly one candidate with all five equal, rejecting names alone, duplicates, missing context and reversed teams. It reports a proposed mapping and does not silently mutate input.

```bash
python -m v3.providers.cli resolve --provider api_football --source data/unresolved.json --candidates data/provider-fixtures.json
python -m v3.providers.cli resolve --provider api_football --source data/unresolved.json --live --max-requests 1
```

The displayed plan includes fixtures, provider, all requested surfaces, missing IDs, conservative estimate, explicit maximum and known quota (null before discovery). Estimate is one shared status request plus seven per resolved match. Live captures with budgets above three discover quota first. Smaller budgets permit a bounded partial capture without status; no retries in this workflow. Every HTTP attempt counts, including failed calls and status. Per-match manifests count their own calls; shared status appears in the execution request total. Remaining quota and the global request cap are enforced by the existing client. Unsupported/absent data are never zeros.

Surfaces: fixture, summary, FT/1H/2H statistics, events, lineups, standings, H2H and player statistics. FT/1H goals and sixteen canonical team statistics reuse the FS-9 normalizer. [Official endpoint documentation](https://www.api-football.com/documentation_v3) defines the half parameter and endpoint coverage; actual coverage remains subscription/competition dependent. Explicit 2H wins. Missing 2H additive fields may have versioned diagnostic FT-minus-1H results with operands and validation, never percentage/ratio subtraction. Diagnostics do not enter capabilities or settlement. The terminal matrix shows bilateral AVAILABLE, UNKNOWN or derived; manifests preserve surface states AVAILABLE/MISSING/NOT_COVERED/BLOCKED/UNKNOWN. Missing values remain null. No live field availability is claimed from mocks.

Artifacts use atomic writes under `v3_data/providers/<provider>/matches/<id>/`: manifest, fixture, capabilities, attempted statistics periods/events/lineups/standings/h2h/player_stats. Summary resides in the manifest. Unattempted surfaces have explicit UNKNOWN entries and no surface file. Provider context is capped at 256 KB per surface; larger results retain a hash and UNKNOWN retention-limit reason. Incomplete pagination is UNKNOWN. Surface payload hashes, artifact hashes, capture time, quota snapshots, identity, versions and completion state are retained. A repeat capture replaces individual artifacts atomically, not the entire directory transactionally; consult the current manifest's artifact hashes rather than assuming old files are current.

Flashscore has no network transport. `--provider flashscore --live` currently returns `BLOCKED_SOURCE_AUTHORIZATION` with zero calls. There is no override flag. The current Source Matrix supplies no exact verified live acquisition grant; The gate reuses the exact provider/method/family Source Matrix contract for all requested families. Even hypothetical verified grants return `BLOCKED_LIVE_TRANSPORT_NOT_IMPLEMENTED`; no transport is added.

Capability output uses existing provenance contracts. Optional FS-3 coverage and FS-5 target outputs are retrospective diagnostics on the selected capabilities; the audit frame's timestamp is the earliest observation, not historical publication accreditation. Synthetic replay remains synthetic. Missing operands/card semantics remain blocked by existing gates. Current captures do not certify FS-4 historical publication/revision lineage. No model training is invoked.
