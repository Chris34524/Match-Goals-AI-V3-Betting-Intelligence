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

Resultado final: **1299 tests PASS**, **31 nuevos**; **ops validator 56/56 PASS**, **final validator 69/69 PASS**; compileall y git diff --check PASS. Se ejecutaron compileall, suite V3 completa, final validator y ops validator antes de la sección de red (1295 tests en ese punto; se añadieron cuatro regresiones offline después). Después se repite la misma secuencia y git diff --check. Los tests no tienen red: fixtures/mocks y guard socket/DNS de toda la suite. Los nuevos tests verifican límites, fallo terminal, temporalidad, duplicados, exclusión sintética, checkpoints, gates, recibos de validación, inmutabilidad y secretos.

El validador histórico esperaba la rama de Fases 6–9, el registry anterior a O-01 y runtime histórico ya ausente: inicialmente 64/69. Se añadió un modo explícito para esta rama, que verifica un baseline independiente tomado al inicio del batch y sellado por [batch-integrity-baseline.json](batch-integrity-baseline.json). Los baselines y reportes históricos no se sobrescriben; el reporte nuevo describe su scope y las diferencias previas. Los cinco artefactos antiguos ausentes no se recrearon. Los artefactos odds realmente presentes al inicio se conservan y verifican.

`data/`, scraper, analysis/backups y main.py se comparan por contenido y mtime completos. Los fuentes de Fases 1–9 existentes permanecen intactos. V3 `__pycache__` es material derivado excluido sólo de comparación de fuentes: dos caches odds se regeneraron al importar. Esto no se oculta como identidad binaria total de todo V3. Todos los comandos posteriores usan PYTHONPYCACHEPREFIX bajo /tmp. No se alteraron modelos, features, Champion, datasets, thresholds, calibración ni corpus. Sólo se adaptó `v3/final_validation.py` para auditar esta rama y guardar sus resultados separados.

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

Modificado únicamente `v3/final_validation.py`. Creados `v3/ops/` (11 módulos), `tests/v3/test_ops_cycle.py` y los reportes/baseline bajo `docs/v3/operations/`. Inventario exacto en `files_created` / `files_modified` del JSON operacional.

Runtime: `v3_data/ops/` para estado, recibos, inventarios y journal de decisiones; `v3_data/operation/pytest.xml` del validador histórico. No se creó ningún bundle odds/paper/performance real. Los artefactos odds preexistentes permanecen intactos. Ningún archivo runtime está staged ni aparece como versionable.
