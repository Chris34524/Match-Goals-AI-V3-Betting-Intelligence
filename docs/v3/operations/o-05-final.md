# O-05 — OOS 50 / 100 / 200

Issue #58 leída completa. `implementation_status = PASS`; `real_status = oos_gate_status = NOT_MET`. `real_oos_count = 0`, required=200; progress=0/200, fraction=0, percent=0; checkpoint=COLLECTING.

El reporte lee el ledger real original, verifica cadena y usa `performance.oos_gate.count_positions` y `performance.analyzer.eligible/summarize`. Una cadena corrupta produce quality FAIL / gate BLOCKED, nunca MET con posiciones parciales.

Sólo cuentan partidos reales únicos con PASS, pre-match, elegibilidad, partition OOS, stake 1u, lineage, settlement acreditado y orden temporal estricto. Sintéticos, duplicados, backfilled, postkickoff, OPEN, BLOCKED y NO_BET no cuentan. Varios picks/mercados del mismo partido cuentan un único match. Los duplicados de paper_bet_id se excluyen todos.

| Cantidad | Estado observacional |
| --- | --- |
| 0–49 | COLLECTING |
| 50–99 | CHECKPOINT_50 |
| 100–199 | CHECKPOINT_100 |
| 200+ | GATE_MET |

Reporte actual: unique matches=0; eligible picks=0; settled=0; unsettled=0; blocked picks=0; NO_BET=0; duplicates excluded=0; synthetic excluded=0. El bloqueo del tick sin candidato no se fabrica como un pick.

Por mercado se reutilizan Brier, LogLoss, accuracy/Hit Rate descriptivo, economics ROI/Yield y drawdown. Ahora no hay métricas disponibles; reason `no_eligible_settled_real_paper`. CLV permanece bloqueado sin closing acreditado. No se publica una métrica sintética como performance real. Las convenciones de Brier se conservan: binary squared error; 1X2 suma de errores por clase.

Runtime: ledger bajo `v3_data/paper/`; reporte `v3_data/ops/operational-cycle-report.json`. La copia documental es un snapshot de auditoría, no datos para el contador. El comando report no usa esa copia para contar.

Los checkpoints son observación: no modifican pesos, features, thresholds, PickScore, Value, Champion ni calibración. Siguiente acción: acumular posiciones prospectivas reales admisibles y settled; no crear fixtures para alcanzar el gate.
