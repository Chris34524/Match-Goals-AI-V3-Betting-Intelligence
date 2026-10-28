# Match Goals AI V3 — batch operacional O-02–O-06

Rama `ops/batch-o02-o06`. Ejecución puntual, sin esperar kickoff/resultados. No staging, commit, push ni cierre remoto de issues.

| Checkpoint | Implementación del runner/gates | Evidencia real |
| --- | --- | --- |
| O-02 | PASS | BLOCKED_NO_FRESH_INTERNAL_TARGET; sports discovery PASS |
| O-03 | PASS para orquestación; admisión real original sigue cerrada | BLOCKED_NO_ELIGIBLE_MODEL_PREDICTION; sin paper entry |
| O-04 | PASS | BLOCKED_PROVIDER_CLOSING_SEMANTICS; CLV null |
| O-05 | PASS | NOT_MET; 0/200; COLLECTING |
| O-06 | PASS | BLOCKED; Champion BT0 / J_BT_sin_temporada intacto |

Estos PASS verifican software y guards. No declaran completos los criterios operacionales reales de las issues. En particular, el runner no implementa un nuevo adapter acreditado de modelos reales ni abre el cierre de producción que existe en `Ledger.record`.

Red real de este batch: metadata 1 intentada / 1 exitosa (`/sports`), `/events` 0; odds 0 intentadas / 0 exitosas. Odds credits consumidos=0, reservados=0. No se obtuvieron headers de consumo/restante de odds; permanecen null. No retry, segunda llamada odds, historical, bulk, scheduler, polling ni backfill.

No target ni kickoff elegibles, no event ID reconciliado, plan NOT_RUN / rejection NOT_EVALUATED, canonical count 0, snapshot NOT_CAPTURED. No predicción pre-match acreditable: V3 sin predictions reales y los 199 registros inspeccionados de Champion carecen de timestamp/lineage elegible. Paper decision BLOCKED, stake policy 1u, settlement UNSETTLED, contribución OOS 0. No closing acreditado.

Los reportes reproducibles usan sólo ledger runtime real, nunca la documentación ni fixtures. OOS cuenta internal_match_id únicos PASS, pre-match, elegibles y settled. Observaciones sintéticas contribuyen cero. Checkpoints 50/100 no retocan políticas. La recomendación usa Phase 6.3, exige evidencia comparable y siempre requiere confirmación humana; no cambia Champion.

Fuentes y detalle por checkpoint: [O-02](o-02-final.md), [O-03](o-03-final.md), [O-04](o-04-final.md), [O-05](o-05-final.md), [O-06](o-06-final.md). Evidencia compacta: [operational-cycle-report.json](operational-cycle-report.json). Validaciones: [final-validation-report.json](final-validation-report.json), [integrity-after.json](integrity-after.json); validación operacional detallada sólo en runtime `v3_data/ops/validation.json`.

## Validación y alcance de integridad

Resultado después de la corrección offline: **1322 tests PASS**, **54 tests operacionales** (23 casos adicionales frente a 1299); **ops validator FAIL: 64/65 PASS**, **final validator FAIL: 66/69 PASS**. Compileall y git diff --check PASS. Las pruebas incluyen 22 negativos de lineage, artefacto separado en tmp_path con SHA-256, bloqueo del planner/collector, autorización separada de evidencia real y métrica de duplicados n−1. Los fixtures son sólo contratos sintéticos y nunca evidencia runtime real.

Contrato `kickoff-lineage-v1`: fuente separada, raíz permitida, sin symlinks/autorreferencia, digest actual, identidad única exacta, kickoff UTC compatible, timezone explícito y captura anterior al kickoff. Artefactos runtime con nombre por digest; legacy sin timezone permanece bloqueado. SOURCE AUTHORIZATION=PASS; REAL ODDS EVIDENCE=MISSING; release=BLOCKED por `no_accredited_prospective_odds_observation`.

NO network calls were executed during this correction. No staging, commit ni push. Histórico intacto: metadata intentada/exitosa 1/1, events=0, odds=0, créditos=0.

El validador histórico esperaba la rama de Fases 6–9, el registry anterior a O-01 y runtime histórico ya ausente: inicialmente 64/69. Se añadió un modo explícito para esta rama, que verifica un baseline independiente tomado al inicio del batch y sellado por [batch-integrity-baseline.json](batch-integrity-baseline.json). Los baselines y reportes históricos no se sobrescriben; el reporte nuevo describe su scope y las diferencias previas. Los cinco artefactos antiguos ausentes no se recrearon. Los artefactos odds realmente presentes al inicio se conservan y verifican.

`data/`, scraper, analysis/backups y main.py se comparan por contenido y mtime completos. En esta corrección, la comparación contra el baseline histórico detectó 1533 diferencias bajo `data/`, con mtime más reciente 2026-10-27T06:51:11.856838Z, anterior a esta sesión de corrección. No se escribió en `data/` ni se alteró el baseline para obtener PASS. Fallan final checks 06 (data), 24 (Champion: compara también todo data) y 55 (integridad total), y ops check 53 (data). `protected_integrity=FAIL` frente al baseline sellado; las demás raíces protegidas coinciden. La identidad declarada de Champion sigue BT0 / J_BT_sin_temporada; el check 24 no permite certificar integridad histórica completa. Los fuentes de Fases 1–9 existentes permanecen intactos. V3 `__pycache__` es material derivado excluido sólo de comparación de fuentes: dos caches odds se regeneraron al importar. Esto no se oculta como identidad binaria total de todo V3. Todos los comandos posteriores usan PYTHONPYCACHEPREFIX bajo /tmp. No se alteraron modelos, features, Champion, datasets, thresholds, calibración ni corpus. La corrección también endurece target discovery, ajusta la métrica OOS y amplía las regresiones y checks operacionales.

El escaneo verifica la ausencia del secreto de environment en archivos versionables y runtime operacional; nunca imprime valor, longitud, fragmento, prefijo, sufijo ni hash del secreto. Runtime permanece ignorado por Git.

## Operación siguiente

Entry points seguros:

```bash
python -m v3.ops.cli status
python -m v3.ops.cli prepare
python -m v3.ops.cli capture
python -m v3.ops.cli paper
python -m v3.ops.cli settle
python -m v3.ops.cli report
```

Sin --live no hay acceso al proveedor. `cycle --live` valida offline y ejecuta exactamente un tick; no es un daemon. El latch por día UTC bajo `ops/ticks/` impide repetir metadata/odds dentro del tick, incluso tras fallo. No borrar latches ni quota ledger para reintentar.

La próxima ejecución requiere primero un target futuro acreditado independiente. `v3_data/ops/internal-targets.json` puede aportar filas con `synthetic_test_only=false`, `kickoff_accredited=true`, `kickoff_lineage`, `internal_match_id`, sport_key/competition explícitamente mapeados, season, kickoff_at con offset y home/away exactos. Las flags no sustituyen la evidencia referida por lineage. No usar provider kickoff para poblar esos campos. El programa no atribuye season ni timezone a campos locales legacy.

Comando exacto para otro día, después de aportar la evidencia faltante:

```bash
PYTHONPYCACHEPREFIX=/tmp/match-goals-ops-bytecode python -m v3.ops.cli cycle --live
```

Sigue limitado a 1 sports, hasta 3 events y como máximo 1 crédito de odds; hará cero odds mientras no exista target acreditado. No basta ejecutarlo para crear evidencia OOS: también hacen falta prediction/adapter acreditados, decisión PASS y resultado posterior acreditado. Un partido sin terminar permanece UNSETTLED; closing sin semántica permanece BLOCKED; OOS inferior a 200 mantiene promoción BLOCKED.

## Archivos y runtime

Alcance original del batch: modificado `v3/final_validation.py`; creados `v3/ops/` (11 módulos), `tests/v3/test_ops_cycle.py` y los reportes/baseline bajo `docs/v3/operations/`. Inventario exacto en `files_created` / `files_modified` del JSON operacional.

Runtime: `v3_data/ops/` para estado, recibos, inventarios y journal de decisiones; `v3_data/operation/pytest.xml` del validador histórico. No se creó ningún bundle odds/paper/performance real. Los artefactos odds preexistentes permanecen intactos. Ningún archivo runtime está staged ni aparece como versionable.


Archivos de esta corrección: `v3/ops/target_discovery.py`, `v3/ops/oos.py`, `v3/ops/validation.py`, `v3/final_validation.py`, `tests/v3/test_ops_cycle.py`, `o-02-final.md`, `o-05-final.md`, este documento y los JSON operacional, final-validation e integrity-after de esta carpeta. No cambios en modelos, features, value, calibración, Champion ni thresholds. El reporte de integridad refleja el fallo real del baseline; no se fabricó un PASS.


## Forecast independiente de odds

**PICKS DO NOT DEPEND ON ODDS.** `python -m v3.ops.cli forecast` (alias `picks`) funciona offline, sin key ni llamadas al proveedor. Reutiliza `analysis.poisson.analizar` y el Champion BT0 / J_BT_sin_temporada. Emite `ranked_forecast_candidates`, sin seleccionar arbitrariamente un mercado por partido: elegibilidad/calidad existente, probabilidad descendente y mercado estable. Mayor probabilidad no significa mayor value. No modifica PickScore, thresholds, modelos ni gates económicos.

Fuente prioritaria: adaptador prospectivo `v3_data/ops/forecast/prospective.json` (lista de registros acreditables), luego `lambda_comparison.json` BT0, fallback `confidence_v2.json` lambda_base y salidas Champion existentes. Las salidas actuales son históricas: legacy_date/legacy_time no se convierten en kickoff con timezone ni se presentan como oportunidades futuras acreditadas.

`ACCREDITED_FORECAST` exige identidad exacta, contrato kickoff-lineage-v1 íntegro, predicción en evidencia separada con SHA verificado y registro único, `model_lineage`, `feature_cutoff_at <= generated_at < kickoff_at`, timestamps con offset y exclusión sintética explícita. El envelope `prediction_lineage` referencia source_path/source_sha256/source_record_id; el registro repite identity, model, model_lineage, probabilities, generated_at, feature_cutoff_at y kickoff_at. Evidencia runtime debe vivir en `v3_data/ops/evidence/<sha256>.json`, sin symlinks ni autoreferencia. No se acredita con flags, fecha de archivo ni mtime. El adaptador mantiene el Champion vigente; no promueve modelos.

`OPERATIONAL_LEGACY_FORECAST` es visible con `oos_eligible=false`. Sin odds: `FORECAST_PASS` es posible; odds_status=UNAVAILABLE, value_status=NOT_EVALUATED y market_odds/market_probability/edge/ev/clv/PickScore=null. fair_odds=1/p si p>0. minimum_acceptable_odds=null: la policy default Phase 4 está declarada sintética y no se convierte en política económica real.

Sólo runtime bajo `v3_data/ops/forecast/`: latest.json, journal.jsonl append-only (predicciones acreditadas prospectivas, ID y source digest estables, sin stake/sportsbook/odds obligatorias) y journal.lock. `settlements.json` admite resultados con settlement_lineage independiente, identity exacta, home_goals/away_goals enteros no negativos y settled_at posterior a kickoff. La evidencia sellada acredita los goles y settled_at. El reporte revalida la predicción original, su identidad, temporalidad y fuente; no confía en oos_eligible serializado. Duplicados o revisiones del mismo partido/mercado no inflan el contador. Resultados ambiguos quedan fuera.

Forecast OOS cuenta partidos únicos separados de predicciones por mercado: forecast_oos_count / forecast_oos_matches, forecast_oos_predictions y betting_oos_matches. Sólo resultados acreditados permiten Brier, LogLoss y Hit Rate descriptivo por mercado; no ROI/Yield/CLV/EV realized. La evidencia sintética de tests nunca se usa como evidencia operacional.

Estado observado: forecast_generation_status=AVAILABLE; 4,315 partidos, 43,150 candidatos legacy, 0 acreditados. forecast_oos_status=NO_ACCREDITED_SETTLED_FORECASTS; Forecast OOS=0 partidos/0 predicciones; Betting OOS=0/200. Value no evaluado. O-02=BLOCKED_NO_FRESH_INTERNAL_TARGET según corrección lineage preservada; O-03 betting=BLOCKED; O-04 CLV=BLOCKED; O-06=BLOCKED. El carril económico continúa por Value Engine y políticas existentes al aportar evidencia económica acreditada; forecast no crea posiciones paper ni relaja closing, CLV, promoción o gate 200.

Validación adicional forecast: 1342 tests PASS, 20 nuevos; compileall PASS. Final validator 66/69 y ops validator 64/65: fallos preexistentes de integridad data contra baseline sellado (06/24/55 y 53 respectivamente), sin modificar baseline. git diff --check PASS. Llamadas de red en esta implementación: 0. No git add, commit ni push.
