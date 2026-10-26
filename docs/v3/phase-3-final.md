# Match Goals AI V3 — Phase 3 final

Phase 3 is implemented and validated offline on
`feature/phase3-batch-3.2-3.3`. Acquisition remains fail-closed.
No add, commit, push or merge was performed.

| Roadmap | Result | Evidence |
| --- | --- | --- |
| 3.1 Odds surface and contracts | Intact, validated; existing restrictions retained | contract.py, source_matrix.py, audit.py and source-matrix.json hashes unchanged |
| 3.2 Odds Collector | Complete; offline validated; live blocked | [checkpoint](odds/checkpoints/3.2.md); 936 tests passed before 3.3; 47 final collector cases |
| 3.3 Snapshots | Complete; prospective schedule, movement and CLV-ready | [checkpoint](odds/checkpoints/3.3.md); 28 snapshot cases |

Final commands: `python -m compileall -q v3 tests`, `python -m pytest -q tests/v3`
(**980 passed**, 76 new cases), `python -m v3.odds.phase3_validation` (**20/20
checks passed**), and `git diff --check`. Full machine-readable evidence is in
[phase-3-validation-report.json](phase-3-validation-report.json). Tests have an
autouse socket/DNS guard; HTTP responses and authorization are injected synthetic
fixtures. No live provider endpoint was called.

Sources of truth: [#29](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/29),
[#30](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/30),
[official The Odds API V4 documentation](https://the-odds-api.com/liveapi/guides/v4/),
and unchanged 3.1 contract/source registry. Both issues were read through gh JSON
output after the default gh view hit the deprecated Projects Classic GraphQL field.
Only public provider documentation was consulted; no acquisition request was made.

The Odds API adapter supports current V4 sport odds and event odds. It is
**implemented, not enabled for live ingestion**. Live status is
`blocked_missing_credentials`; adding credentials alone still leaves the existing
project authorization gate closed. No other provider was enabled. Canonical records
from offline fixtures retain review status; schema validity never grants rights.

Supported markets are 1X2, BTTS, OVER_1_5, OVER_2_5 and OVER_3_5 (both total sides).
Absent lines/books are not manufactured. Asian handicap, spreads, corners, cards,
props and unsupported totals lines remain blocked. No historical paid endpoint is
implemented or requested. Observed capture clock and provider publication clock are
kept separate; provider timestamps in the future are rejected by 3.1.

Budget defaults are hard 500 credits/month, soft 450 and max 30/run, configurable.
Dry-run estimates unique provider markets × region equivalents × calls. Explicit
books override regions using ceil(N/10). A shared locked append-only ledger reserves
upper bounds before network and retains unknown/failed costs. Priority degradation
never bypasses the soft/hard/run/provider limits. Independent roots or external
clients sharing a credential need an external coordinator.

Prospective UTC T-24h/T-6h/T-1h slots have a configurable 60-second window. Optional
decision slots are off. Late slots become missed without backfill. Immutable
snapshots preserve full lineage. Price movement requires identical match/provider/
book/market/selection/line and valid ordered times. Dispersion requires complete,
reproducible same-capture book populations. Neither opening nor closing is inferred.
Closing remains unknown/unavailable for current-provider data; CLV remains blocked
until an explicitly accredited comparable closing exists. Synthetic tests validate
the documented price formula without claiming production closing coverage.

Integrity: 67,461 regular files were fingerprinted before changes. Content SHA256
and mtime fingerprints match afterwards for data/, scraper/, analysis/, backups,
main.py, all matched BT0/J_BT lineage paths and the 3.1 files. Top-level BT0 and
J_BT_sin_temporada paths are absent; the one BT0-named nested artifact is included
in the protected data fingerprint. No J_BT-named path was found. The entire
protected tree, including bytecode already present, was included; validation did
not update data mtimes. See [before](odds/integrity-before.json) and
[after](odds/integrity-after.json). Git shows only new isolated V3 paths.

A reviewable synthetic run is saved at
`v3_data/odds/phase3-synthetic-example/f95ab56a9b4cbd2c6148629d77a052bdb499dba9a757bcff3e2bfe1c5dffe7fe/`.
It contains raw/response.json, canonical.jsonl and manifest.json (11 records):

- Source SHA256: `14bcc23ee9d9a96808144aba45d5f67c999d6a4e5213430e3f215f95be1247e0`.
- Canonical SHA256: `512b62c41cd26483e7bf170ecd45ee7ef466881b06b8df31783afbd6ac9a1e12`.

Files created are enumerated in the JSON report: provider/adapter, collector,
reconciliation, quota, storage, CLIs, scheduler, snapshots, movement, CLV, reporting,
validator, synthetic fixtures/tests, checkpoints and fingerprints. Existing tracked
files were not modified. A working-tree summary accompanies final validation;
ordinary git diff --stat is empty because all deliverables are new untracked files.

For Phase 4, consume only explicitly authorized and temporally eligible observations.
Live odds require project grant plus credentials and prospective coverage validation;
CLV additionally requires accredited closing. The code is ready for those inputs,
while the current absence of credentials/closing is an expected blocked state.
