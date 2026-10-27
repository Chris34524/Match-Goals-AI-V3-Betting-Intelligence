# O-01 / O-02 Runbook — Real prospective evidence

## Scope

This runbook prepares the first real The Odds API capture without changing the Champion, fabricating historical evidence, or committing runtime data.

## 1. Sync the operational branch

```bash
cd /home/leos/projects/match-goals-ai
source .venv/bin/activate

git fetch origin
git switch ops/prospective-evidence-cycle 2>/dev/null || git switch --track origin/ops/prospective-evidence-cycle
git pull --ff-only origin ops/prospective-evidence-cycle
```

## 2. Confirm current fail-closed state

```bash
python - <<'PY'
from v3.odds.the_odds_api import live_status
print(live_status(live=True))
PY
```

Before credentials are configured, expected state:

```text
blocked_missing_credentials
```

Do not treat this as a software failure.

## 3. Configure the API key locally

Never paste the key into Git, JSON config, command arguments, docs, logs, or chat.

For the current shell session:

```bash
read -s -p "THE_ODDS_API_KEY: " THE_ODDS_API_KEY
export THE_ODDS_API_KEY
echo
```

The collector reads `THE_ODDS_API_KEY` from the environment.

## 4. Re-check the authorization gate

```bash
python - <<'PY'
from v3.odds.the_odds_api import live_status
print(live_status(live=True))
PY
```

With a key configured but before the source matrix is promoted, expected state:

```text
blocked_source_authorization
```

That is intentional. Key possession alone does not mutate project authorization.

## 5. Source-matrix promotion

Only after a real provider account/key exists and the applicable provider terms have been reviewed for the project, update the `the_odds_api` source row through code review so that all `automatable()` conditions are explicit and testable.

Required state for live enablement:

- `status = available`
- `capture_policy = licensed_api`
- `authorization_status = verified_project_grant`
- `acquisition_method = official_api`
- `automatable = true`

No runtime or secret may be committed with that change.

## 6. Prepare safe config and explicit targets

Copy the example files under this directory to an ignored/local runtime location and replace placeholders. Do not put credentials inside them.

The target contract requires:

- internal match ID
- provider sport key
- competition
- season
- kickoff timestamp with timezone
- exact home and away names
- requested market allowlist
- priority
- external event ID for live planning

## 7. Dry-run quota plan

```bash
python -m v3.odds.cli plan \
  --config /path/to/local/odds-config.json \
  --targets /path/to/local/odds-targets.json
```

No network request is made by `plan`.

## 8. Dry-run prospective schedule

```bash
python -m v3.odds.snapshots_cli plan \
  --config /path/to/local/odds-config.json \
  --targets /path/to/local/odds-targets.json \
  --output-dir v3_data/odds
```

Default slots are T-24h, T-6h and T-1h. Missed windows are terminal `MISSED`; they must not be retrospectively backfilled.

## 9. First controlled live capture

Run only after O-01 is unblocked and the dry-run cost is acceptable:

```bash
python -m v3.odds.cli collect-live \
  --config /path/to/local/odds-config.json \
  --targets /path/to/local/odds-targets.json \
  --output-dir v3_data/odds \
  --live
```

Or execute a due scheduler tick:

```bash
python -m v3.odds.snapshots_cli live-tick \
  --config /path/to/local/odds-config.json \
  --targets /path/to/local/odds-targets.json \
  --output-dir v3_data/odds \
  --live
```

There is no continuous polling loop. Use an external timer only after the first manual live tick is validated.

## 10. Inspect evidence

```bash
python -m v3.odds.snapshots_cli report \
  --config /path/to/local/odds-config.json \
  --targets /path/to/local/odds-targets.json \
  --output-dir v3_data/odds

python -m v3.operation.cli report
```

Expected early operational state remains fail-closed for real release until downstream real evidence is present.

## Controls

- No API key in repository files.
- No `v3_data/` in commits.
- No paid historical reconstruction required.
- No Flashscore automation added.
- No automatic real betting.
- No Champion mutation.
- `observed_at` remains independent from provider timestamps.
- Closing is never inferred from the last pre-kickoff price.
