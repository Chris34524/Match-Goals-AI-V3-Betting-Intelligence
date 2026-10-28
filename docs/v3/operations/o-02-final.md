# O-02 — Captura prospectiva

Rama: `ops/batch-o02-o06`. Issue #55 leída completa mediante `gh issue view --json`: la vista por defecto falla por Projects Classic. No se cerró la issue.

`implementation_status = PASS` para discovery/orquestación y guards; `real_status = BLOCKED_NO_FRESH_INTERNAL_TARGET`. No captura real acreditada.

Discovery real: PASS. Una llamada `/v4/sports` intentada y exitosa. Cero llamadas `/events`: sin target interno acreditado no corresponde buscar su pareja externa. Máximos aplicados por tick UTC: 1 sports, 3 events, 1 intento de odds. El estado se guarda antes de cada acceso y no se reintenta un intento fallido/interrumpido.

Inventarios internos leídos sin cambios: `data/partidos.json`, `partidos_candidatos.json`, `partidos_hoy.json`, `partidos_manana.json`. Ninguno acredita simultáneamente kickoff futuro, timezone, season, identidad y lineage independiente. `fecha`, `hora`, `fecha_hora_local`, mtime y país no acreditan timezone. Predictions/resultados no se usan para reconciliar identidad. Tres mappings explícitos disponibles: EPL, Bundesliga y LaLiga; no equivalen a targets elegibles.

| Campo | Evidencia real |
| --- | --- |
| internal_target_status | BLOCKED_NO_FRESH_INTERNAL_TARGET |
| pilot_target_status | BLOCKED |
| external_event_id_present | no |
| target / kickoff | ninguno / no acreditado |
| plan estimated cost | NOT_RUN |
| plan rejection | NOT_EVALUATED; no plan aprobado |
| real odds call attempted / succeeded | no / no |
| canonical records | 0 |
| snapshot | NOT_CAPTURED |
| odds credits consumed / reserved | 0 / 0 |
| provider used / remaining headers | no disponibles; no odds request |

El config runtime exige hard 500 / soft 450 / max 1, un deporte, región eu y mercado 1X2. `pilot-targets.json` contiene `[]`, que expresa ausencia de target, nunca una autorización. Antes de capturar se revalida el origen interno, kickoff, exactamente una reconciliación, event ID y plan de una llamada/coste 1/rejection null. Se reutiliza el collector y su ledger de cuota; no hay scheduler adicional. No historical, bulk, polling ni backfill.

Una observación futura conservará `snapshot_type=current`. `pilot-current.json` sólo añade semántica operacional `pilot_current`, hashes y manifest; no declara slots T-24/T-6/T-1, opening ni closing. El contrato Phase 3 permanece intacto.

Runtime: `v3_data/ops/pilot-config.json`, `pilot-targets.json`, `capture-status.json`, `ticks/<UTC-day>.json`; futuros bundles en `v3_data/odds/<run_id>/`. Nunca Git.

Reason: `no_independent_accredited_future_timezone_aware_internal_target`. Siguiente acción: aportar una identidad interna futura con kickoff/season y evidencia temporal independiente; después ejecutar un tick en otro día. No copiar kickoff del provider al manifiesto interno.


Corrección offline de auditoría: contrato `kickoff-lineage-v1`. Las flags no acreditan kickoff. `inspect()` verifica un envelope estructurado y evidencia JSON separada dentro de `data/` (sólo lectura) o `v3_data/ops/evidence/`. En runtime el nombre obligatorio es `<sha256>.json`: cualquier cambio de bytes invalida el digest y requiere otro artefacto. El source nunca puede ser el inventario target, `internal-targets.json` ni un symlink. No se creó evidencia real.

El documento contiene `synthetic_test_only=false` y `records`; cada registro acredita `source_record_id`, `identity` (internal_match_id/home/away/competition exactos), `kickoff_at`, `captured_at`, `timezone_basis` y exclusión sintética explícita. Se exige exactamente una identidad y record ID, sin flags de autoacreditación. El envelope repite identidad, record ID, captured_at, kickoff_field=`kickoff_at`, kickoff_value y timezone_basis, junto con source_path/source_sha256 y version. Kickoff y captura deben tener offset; captura anterior al kickoff y no futura. Bases admitidas: `explicit_utc_offset` o `explicit_utc`; ninguna inferencia por país, máquina, provider, mtime o archivo. Los timestamps se comparan normalizados a UTC.

Los fallos conservan reason codes distintos para formato/versión, ruta ausente/fuera de raíz/symlink, independencia/inmutabilidad, digest, identidad, kickoff, temporalidad, timezone y evidencia sintética. El runner revalida antes de capturar. Legacy fecha/hora sigue bloqueado. O-02 mantiene `BLOCKED_NO_FRESH_INTERNAL_TARGET`.

NO network calls were executed during this correction. Histórico conservado: metadata 1/1, events 0, odds 0, créditos 0.
