# FS-0 — Flashscore public data surface discovery

Issue: [#62](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/62). Branch: `feature/fs-0-flashscore-data-surface`. Inspection date: 2026-11-01 UTC. Documentation only; no collector, schema code, model, market implementation or acquisition grant.

## Methodology and strength of evidence

Repository inspection preceded changes. Public discovery used a small number of ordinary web searches restricted to public Flashscore match pages, direct public page opens, and an example link from Flashscore's own player-statistics article. No operational scraper was run. No hidden feeds, network interception, private endpoints, browser evasion, login, CAPTCHA solving, rate-limit bypass, bulk traversal or retry loop was used. Only metadata and field labels are retained.

**Critical evidence limitation:** searches returned indexed public match tables, while many direct opens returned a `Loading...` shell. The two representations can have different crawl dates. Thus OBSERVED here means a field label/structure was present in an inspected **public indexed representation**, with `evidence_method=public_search_index`; it does not certify a current rendered browser page. A title, SEO footer, tab name, or product announcement alone does not confirm a populated field. No successful interactive browser render or selected-half switch was established. This is a constrained discovery, with a specific follow-up inspection dependency before declaring full rendered-page acceptance. No access control was bypassed to resolve that dependency.

`observed-fields.json` is the field catalog; `sample-pages.json` gives stable sample IDs, URLs, inspected surfaces, fields and limitations. Inspection timestamps describe this review, not provider publication or cache freshness. Source match dates are descriptive and may conflict across representations; no values are used for sports evidence or OOS validation.

- OBSERVED: field label/structure confirmed in at least one inspected public representation, qualified by evidence method and sample.
- NOT_OBSERVED: explicit inspection established absence in that sample/lifecycle state; no global inference.
- UNKNOWN: not evaluated or inconclusive, including dynamic shells, errors and period ambiguity.
- POTENTIAL_MARKET: future market candidate, separate from field availability. Every `potential_markets` entry has this status and is not an implemented model or a demonstrated edge.

Availability != authorization. Field visible in one league != universal coverage. Column presence != non-null value coverage. Null/dash != observed zero.

## Repository findings and non-duplication

Existing work already covers the broad signal concept inventory:

| Existing source | Reused finding; FS-0 addition |
|---|---|
| [signal-surface.md](../signal-surface.md), `v3/features/surface_catalog.py`, surface audit/summary JSON | Prior 2.1A documents 289 candidate signals, availability versus capture policy, and a historical local audit. FS-0 adds sample-linked public label evidence, uncertainty by period and an unimplemented capability design; it does not regenerate or extend that code. |
| [features.md](../features.md), `v3/features/catalog.py` | Existing 118-feature contract is separate from a public field catalog. No availability/status promotion. |
| [phase-2/source-matrix.md](../phase-2/source-matrix.md) | Flashscore archive is review-only; no ingestion provider enabled. Authorization scope, identities and timestamps remain dependencies. |
| [data-contract.md](../data-contract.md), [temporal-context.md](../temporal-context.md), `v3/README.md` | Separate inputs/predictions/labels; exclude target, future and unverified same-day inputs; capture time/mtime is not historical availability. Standings/xG/H2H require lineage. |
| `scraper/flashscore.py`, `extract_history.py`, `extract_xg.py`, `standings.py` | Existing fixture/history/xG/table lane; Flashscore Mexico domain and public match IDs are already used. Reading existing implementation is not permission to add automation. |
| [operations/o-01-o-02-runbook.md](../operations/o-01-o-02-runbook.md), `v3/ops/`, `analysis/` | Existing Forecast, daily HTML, Champion, odds/Value and paper/OOS controls remain operationally separate. |

Prior audit counts are historical documentation, not counts recomputed from this checkout. No existing `data/` directory is present in this workspace. GitHub Issue #62 was read with `gh`; it is OPEN and requires these five documentation artifacts. No repository or ancestor AGENTS.md was found in the checked paths.

## Operational safety boundary

Only five new files under `docs/v3/flashscore/` are permitted. All existing repository files are protected for this delivery, including all `scraper/`, all operational `analysis/`, BT0 / `J_BT_sin_temporada`, lambda_comparison behavior, `v3/ops/forecast.py`, Forecast CLI, Value Engine, PickScore, calibration, OOS gates, paper betting, reports and any existing artifacts. There is no integration into scraping → enrichment → Forecast → daily HTML.

No weights, thresholds, policies, challenger promotion, market models or labels were changed. Historical post-match fields are discovery evidence only. Future prematch inputs must come from eligible earlier matches, exclude the target, preserve provider publication/revision availability before cutoff, and use the existing conservative same-day rule. Current table/player profiles or revised post-match statistics cannot reconstruct a historical prematch snapshot. No in-sample or OOS improvement is claimed.

If later acquisition needs a protected operational change, document the dependency and stop that integration. FS-1 should be an isolated contract, not a retrofit of production extraction.

## Representative competitions and samples

This is purposive discovery, not a coverage census. Competition attribution is explicitly qualified when the returned page text did not show it. Match identity is descriptive, not entity resolution.

| Competition / candidate tier | Ledger IDs | Actual inspection evidence |
|---|---|---|
| Premier League | PL-STATS, PL-TABLE | Indexed team statistics and competition standings |
| LaLiga | ES-STATS | Indexed team rows and period navigation |
| Serie A | IT-STATS | Indexed team rows; direct open shell |
| Bundesliga | DE-STATS | Indexed team rows and period navigation |
| Liga MX | MX-LINEUPS | Indexed starting lineups, formation, substitutions and ratings |
| MLS | US-SUMMARY | Indexed score/period timeline, penalty goal and stats preview; direct open shell |
| Liga Expansión MX | EMX-SUMMARY, EMX-PLAYERS, EMX-H2H | Indexed summary/events, xG preview, detailed player general table and H2H |
| Brazil (fixture attribution needs verification) | BR-STATS, HALF2, PREMATCH | Indexed advanced team rows; half URL unresolved; explicit future-match placeholder |
| Argentina (stage needs verification) | AR-SUMMARY, AR-PLAYERS | Indexed summary and player top-stat rows |
| Europa League (fixture attribution) | EU-STATS | Indexed stats/first-leg marker; direct shell |
| Champions League | UCL-PLAYERS | Official article example link followed; title only, player content UNKNOWN |
| Ghana lower-coverage candidate | LOW-SUMMARY | Indexed basic stats/timeline; direct date conflict and shell. League attribution and advanced coverage UNKNOWN |
| Italy competition unknown; Brazil state competition unverified; other failure examples | HALF1, HALF2-ERROR, FINISHED-PLACEHOLDER | Half-state uncertainty, section error, finished/placeholder conflict |

Liga Expansión indexed player tables and advanced preview are counterexamples to automatically treating every non-major competition as low coverage. The Ghana candidate is a test stratum, not a validated low-coverage classification.

## Surfaces and structure

| Surface | Confirmed public indexed structure | Unresolved |
|---|---|---|
| Match summary | Teams, score, Finished marker, first/second-half score headings | Regulation versus extra time/shootouts must be verified per fixture |
| Events/timeline | Minute and added-time notation, score changes, named scorer, explicit Penalty annotation, substitutions | Own-goal event not confirmed; card color/type and cancellations not reliably preserved in returned text |
| Overall statistics | Paired team values grouped into top stats, shots, attack, passes, defence, goalkeeping | No current render verified; provider revisions and null semantics |
| First-half statistics | Period navigation and indexed rows at HALF1 public half URL | Active selected state not verified; field-period status UNKNOWN |
| Second-half statistics | Period navigation and indexed rows at HALF2 public half URL | Active state UNKNOWN; HALF2-ERROR explicitly failed |
| Lineups | Formation, starting lineup, substitutes and player ratings (MX-LINEUPS) | Official versus predicted and pre-kickoff publication unverified |
| Standings | Position, MP/W/D/L, goals, GD, points, form; Overall/Home/Away controls | PL-TABLE is competition-level; historical match-as-of table not verified |
| H2H | Dated recent matches and head-to-head rows, venue filters (EMX-H2H) | Completeness, ordering/revisions and prematch cutoff; current list contains target |
| Player stats | Named rows, rating/general columns; top-stat categories in AR-PLAYERS | Most categories not opened; no player shot-on-target or keeper row confirmed |

## Field inventory, level and periods

The JSON contains 98 field-period entries and the exact sample links. Labels are evidence, not guaranteed stable selectors. No numeric sport values are copied.

| Family | OBSERVED in indexed representation | UNKNOWN / not established |
|---|---|---|
| Goals | Match final score, halftime score, explicit second-half score, goal minute, penalty-goal annotation | Own-goal event; regulation settlement scope per sample; complete corrections/cancellations |
| Expected goals | Team xG, xGOT, xA; player xG | Player xGOT/xA numeric rows; selected-half attribution |
| Shots | Team total/on/off target, blocked, inside/outside box; player total shots | Player SOT; full 1H/2H coverage |
| Chances | Big chances, big chances scored/missed, opposition-box touches | Provider definitions, half-state completeness |
| Corners | Paired team Corner kicks counts on overall pages | Verified selected 1H/2H counts; event-level corner ledger |
| Discipline | Team fouls; player Yellow cards/Red cards table columns | Team yellow/red totals; card event types, bench/staff, second yellow and period counts |
| Possession/passes | Possession, passes, completed passes with percent, final-third attempted/completed, key passes, long attempted/completed, crosses attempted/completed | Numeric/dash conventions per locale, and selected halves |
| Other | Offsides, free kicks, throw-ins | Universal availability |
| Defence | Duels won, tackles/won, interceptions, clearances, errors leading to shot/goal | Team duels attempted is distinct from duels won; no interchangeability |
| Goalkeeping | Team goalkeeper saves, xGOT faced, goals prevented | Individually attributed keeper metrics and keeper substitution split |
| Player general | Rating, minutes, goals, own-goals column, assists, yellow/red columns | Own-goal/red-card numeric values not confirmed in that table; dash is unresolved |
| Player extra | xG, shots, accurate passes/count denominator/percent, touches/box touches, successful dribbles, duels | Stable IDs, minutes rules and ratings version |

Overall FT in the catalog is the whole-match UI surface, **not** a certified regulation-only settlement scope. 1H and 2H are separate capabilities; tab presence cannot inherit all FT fields. HALF1/HALF2 ledger fields record indexed labels under those URLs, but catalog period status remains UNKNOWN. Period score headings provide better period evidence than selected-stat URLs in this review. For a verified regulation match, second-half goals may later be derived as FT minus HT per side, only with complete consistent operands. Do not subtract percentages, ratings, xGOT models or other non-additive fields. Test even count additivity against provider conventions before relying on it.

Pass cells can combine completed count, attempted denominator and percentage; preserve each and rounding conventions. Duels won != player total duels. Team goalkeeper totals != individual keeper saves. A yellow-card player column does not establish a team card count. Jersey number != stable player ID.

## Market-family mapping — all POTENTIAL_MARKET

Each catalog field links future families; these links distinguish settlement operands from predictive/contextual support. No betting odds, market liquidity, settlement rule compatibility, model effectiveness or permissions have been established.

| Families | Necessary direct operands | Additional discovered support / gates |
|---|---|---|
| O/U FT; BTTS FT; team goals; FT 1X2; double chance | Regulation home/away final goals | Team xG/xGOT/xA, shots/chances/keeper stats as historical predictors only |
| O/U 1H and 2H; BTTS 1H and 2H | Per-side period scores, explicit regulation period | Half stats optional covariates, currently UNKNOWN; validate FT−HT before deriving 2H |
| First team to score | Complete ordered valid goal events, scoring side; explicit no-goal convention | Minutes alone insufficient; own goals and VAR corrections require checks |
| HT 1X2; HT/FT | HT score plus regulation FT score for HT/FT | Standings/H2H only as-of context; no current tables as historical inputs |
| Total corners; team corners; most corners; corner handicaps | Both team regulation corner counts | Corners strongest new direct family; line/tie/handicap settlement and coverage pending |
| First-half and second-half corners | Both team counts in verified selected half | UNKNOWN selected period; not enabled by FT corner visibility |
| Total cards; first-half cards; team cards; most cards | Typed card counts and period/team attribution | Player columns/fouls are support only; bookmaker card points, double-yellow, bench/staff rules unresolved |
| Red card yes/no | Confirmed red event/count and market convention | Red player column observed, numeric event/type and team settlement remain UNKNOWN |
| Team shots; team shots on target | Paired team counts, provider definitions and regulation scope | Direct labeled team rows observed; blocked/woodwork categorization needs definition |
| Player shots; SOT; goals; assists; cards | Player-ID attributed counts, participation and settlement convention | Total shots/general columns observed; player SOT UNKNOWN; lineup/minutes/rating are context, not settlement |
| Goalkeeper saves | Keeper-ID attributed saves, substitutions, regulation scope | Team saves observed; individual goalkeeper rows UNKNOWN |

The JSON's broad mapping of predictive covariates to several families expresses research potential only. It does not imply that, for example, xG settles corners or that fouls settle cards.

## Coverage variability, risks and limitations

No percentage or global capability is inferred. PREMATCH explicitly contains a future-match statistics placeholder; do not ingest its previous-match link as the current fixture. FINISHED-PLACEHOLDER mixes Finished with an awaiting-stats message: UNKNOWN rather than zero or NOT_COVERED. HALF2-ERROR reports a section-load error. UCL-PLAYERS confirms only a route/title. LOW-SUMMARY has conflicting dates across index/open; this blocks trusted identity/date use. Collapsed previews cannot establish absent xG. Some live indexed results encountered during searches had inconsistent clock/status/score combinations; those were not selected as finished evidence.

Dynamic rendering, stale indexing, locale aliases (Match/Overall, final-third wording), removed history, transient errors and coverage changes all complicate acquisition. URL period components are ordinary public routes, not undocumented API endpoints, but still require selected-state verification. No selectors or endpoint strategies are specified here. Terms were opened via the official footer; the tool did not expose numbered clauses 2.9/2.10, so FS-0 does not re-certify their current wording. Existing repository authorization restrictions remain unchanged; future automation needs independently verified permission or a permitted/licensed alternative and scope review. See [official terms](https://www.flashscore.com/terms-of-use/).

Flashscore's [player statistics article](https://www.flashscore.com/news/players-under-the-magnifying-glass-a-look-at-players-detailed-statistics/8pvZSJ6U/) documents category navigation and an initial league selection. This is product context, not a current coverage whitelist; observed indexed examples outside that list need verification, not automatic rejection or extrapolation.

## Proposed FS-1 capability contract — no implementation

Unit: `(provider, match_id, competition_id, season, stage, lifecycle, surface, level, team_or_player_id, period, capability_name, observed_at)`. IDs may remain unresolved; unresolved identity blocks usability. Each record should retain source URL, evidence method, field labels, raw-versus-derived origin, source publication/revision availability (nullable), selected-period proof, null reason, parser/schema version and score scope. Store acquisition permission separately from technical visibility and temporal usability. FS-0 status values are not runtime capability states.

| Proposed capability names | Minimum evidence before AVAILABLE |
|---|---|
| `summary`, `events`, `goals_ft`, `goals_first_half`, `goals_second_half` | Correct identity/lifecycle, explicit score/period and regulation scope; complete typed ordered events for event-dependent markets |
| `stats_overall`, `stats_first_half`, `stats_second_half` | Successfully loaded identified surface and verified active period; known expected field set; container availability never certifies every child |
| `corners`, `cards`, `shots`, `shots_on_target`, `possession`, `passes`, `fouls`, `offsides`, `free_kicks`, `throw_ins` | Labeled values for required sides in the specific period; typed cards with second-yellow/bench rules |
| `xg`, `xgot`, `xa`, `big_chances`, `big_chances_scored`, `big_chances_missed`, `box_touches` | Explicit metric label/definition and numeric values for that level/period; never inherit from a top-stat preview |
| `defence`, `goalkeeping` | Explicit submetrics and semantics; maintain child states for duels/tackles/interceptions/clearances/errors/saves/xGOT faced/goals prevented |
| `lineups`, `standings`, `h2h`, `player_stats` | Loaded rows with identity and provenance; lineup official/predicted flag; standings as-of snapshot; dated H2H; player IDs and category-level child states |

Proposed states, per capability and period:

| State | Determination |
|---|---|
| AVAILABLE | Successful permitted inspection, verified identity/period and validated non-null required operands. Observed zero is valid. Historical prematch usability is checked separately. |
| MISSING | Surface is successfully loaded and known covered for that fixture/lifecycle, but required field/value is absent. Record which side/operand. No zero imputation. |
| NOT_COVERED | Explicit credible provider/permissioned coverage evidence for this fixture/competition/season/surface; not merely absent tab or failed request. |
| BLOCKED | Explicit acquisition denial, access restriction, CAPTCHA or policy/authorization gate for the requested method. Stop; retain reason without bypass. Visibility may still be separately OBSERVED. |
| UNKNOWN | Not inspected, shell/timeout/section error, unresolved identity/period, ambiguous dash or lifecycle mismatch. Scheduled stats use UNKNOWN with `not_yet_available` rather than NOT_COVERED. |

Evaluate authorization/method first, then identity/lifecycle/selected period, then coverage evidence, then required operands. Do not infer universal precedence from the state label: store reasons and independent permission/usability flags. A failed later inspection is a new observation, not an overwrite of earlier evidence. Do not promote a parent AVAILABLE into child AVAILABLE; total team corners require both team operands. Derivations retain operand provenance and fail closed if any required value/scope is unknown.

FS-1 should specify this contract and offline validation fixtures in an isolated module only after FS-0 review/merge, without implementing collection or changing the existing catalog/operational adapters. Its first review must resolve indexed-versus-rendered evidence and selected-half checks. FS-3 should quantify capability/field/period coverage with the stratified design in [coverage-hypotheses.md](coverage-hypotheses.md), including negative and blocked observations.
