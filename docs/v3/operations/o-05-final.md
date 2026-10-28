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


Corrección offline: `records_total` cuenta todas las filas; `duplicate_records_excluded` suma n−1 por paper_bet_id repetido. `duplicates_excluded` conserva un alias con esa misma semántica; `duplicate_identity_records_ineligible` cuenta todas las filas de identidades repetidas que quedan fuera. Para [row,row]: total=2, duplicados adicionales=1, filas ineligibles=2, real_oos_count=0. El gate sigue fail-closed, sin cambiar 0/200 NOT_MET.


## Forecast independiente de odds

**PICKS DO NOT DEPEND ON ODDS.** `python -m v3.ops.cli forecast --source data/partidos_manana.json` (alias `picks`) funciona offline, sin key ni llamadas al proveedor. Reutiliza `analysis.poisson.analizar` y el Champion BT0 / J_BT_sin_temporada. Emite `ranked_forecast_candidates`, sin seleccionar arbitrariamente un mercado por partido: elegibilidad/calidad existente, probabilidad descendente y mercado estable. Mayor probabilidad no significa mayor value. No modifica PickScore, thresholds, modelos ni gates económicos.

Target Universe explícito: listas o contenedores `partidos`, `candidatos`, `targets`, con identidad exacta `match_id`, `id`, `flashscore_id` o el contrato interno `internal_match_id`. IDs ausentes, contradictorios o inseguros quedan BLOCKED_IDENTITY; duplicados usan la primera aparición. Sin --source sólo se consulta `v3_data/ops/forecast/targets.json`; su ausencia produce NO_ACTIVE_FORECAST_TARGETS, cero partidos/candidatos. Una fuente explícita inexistente falla cerrada. `data/matches/` sólo enriquece IDs de esa allowlist mediante BT0 lambda_comparison o confidence_v2. El adaptador prospectivo sólo puede acreditar IDs seleccionados. Nunca se recorre el histórico como universo.

`ACCREDITED_FORECAST` exige identidad exacta, contrato kickoff-lineage-v1 íntegro, predicción en evidencia separada con SHA verificado y registro único, `model_lineage`, `feature_cutoff_at <= generated_at < kickoff_at`, timestamps con offset y exclusión sintética explícita. El envelope `prediction_lineage` referencia source_path/source_sha256/source_record_id; el registro repite identity, model, model_lineage, probabilities, generated_at, feature_cutoff_at y kickoff_at. Evidencia runtime debe vivir en `v3_data/ops/evidence/<sha256>.json`, sin symlinks ni autoreferencia. No se acredita con flags, fecha de archivo ni mtime. El adaptador mantiene el Champion vigente; no promueve modelos.

`OPERATIONAL_LEGACY_FORECAST` es visible con `oos_eligible=false`. Sin odds: `FORECAST_PASS` es posible; odds_status=UNAVAILABLE, value_status=NOT_EVALUATED y market_odds/market_probability/edge/ev/clv/PickScore=null. fair_odds=1/p si p>0. minimum_acceptable_odds=null: la policy default Phase 4 está declarada sintética y no se convierte en política económica real.

Sólo runtime bajo `v3_data/ops/forecast/`: latest.json, journal.jsonl append-only (predicciones acreditadas prospectivas, ID y source digest estables, sin stake/sportsbook/odds obligatorias) y journal.lock. `settlements.json` admite resultados con settlement_lineage independiente, identity exacta, home_goals/away_goals enteros no negativos y settled_at posterior a kickoff. La evidencia sellada acredita los goles y settled_at. El reporte revalida la predicción original, su identidad, temporalidad y fuente; no confía en oos_eligible serializado. Duplicados o revisiones del mismo partido/mercado no inflan el contador. Resultados ambiguos quedan fuera.

Forecast OOS cuenta partidos únicos separados de predicciones por mercado: forecast_oos_count / forecast_oos_matches, forecast_oos_predictions y betting_oos_matches. Sólo resultados acreditados permiten Brier, LogLoss y Hit Rate descriptivo por mercado; no ROI/Yield/CLV/EV realized. La evidencia sintética de tests nunca se usa como evidencia operacional.

Estado observado: forecast_generation_status=AVAILABLE; 195 partidos, 1,950 candidatos legacy, 0 acreditados con la fuente explícita data/partidos_manana.json (216 registros; 21 sin features BT0 disponibles). Las fechas de esa fuente son legacy, sin acreditación prospectiva. forecast_oos_status=NO_ACCREDITED_SETTLED_FORECASTS; Forecast OOS=0 partidos/0 predicciones; Betting OOS=0/200. Value no evaluado. O-02=BLOCKED_NO_FRESH_INTERNAL_TARGET según corrección lineage preservada; O-03 betting=BLOCKED; O-04 CLV=BLOCKED; O-06=BLOCKED. El carril económico continúa por Value Engine y políticas existentes al aportar evidencia económica acreditada; forecast no crea posiciones paper ni relaja closing, CLV, promoción o gate 200.

Integridad corregida: código protegido contra origin/main y cambios locales es gating; cambios versionados de data/ en origin/main...HEAD fallan. Drift de contenido/mtime del corpus operativo es informativo y se reporta con archivos y edad del inventario; no acredita ni invalida Champion. Champion se verifica directamente por BT0 / J_BT_sin_temporada, checkpoints y fuentes protegidas. Baselines originales preservados.
