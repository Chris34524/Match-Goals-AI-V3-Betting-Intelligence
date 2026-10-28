# O-03 — Paper prospectivo

Issue #56 leída completa. `implementation_status = PASS` para orquestación, replay de decisiones, journal operacional, settlement y gates reutilizados. `real_status = paper_status = BLOCKED_NO_ELIGIBLE_MODEL_PREDICTION`. Esto no declara completa la admisión de modelos reales.

Se auditó primero V3: los checkpoints Phase 5 no tienen `predictions_hash` real. Los outputs Champion `all_predictions.json` (193 filas) y `day_predictions_v2.json` (6 filas) no aportan timestamps de generación más lineage por predicción; cero candidatos acreditables. Se registraron hashes de archivos en runtime; no se reconstruyeron probabilidades, no se usaron resultados ni odds como probabilidades.

| Campo | Estado |
| --- | --- |
| eligible model prediction | no |
| candidate / decision | BLOCKED |
| paper entry created | no |
| stake policy | fijo 1.0u; no stake ejecutado |
| settlement | UNSETTLED; no posición que liquidar |
| real OOS contribution | 0 |

`paper` consume opcionalmente `v3_data/ops/candidate.json` con el contrato completo existente de `selection.policy.decide`. Reproduce elegibilidad/modelo/calibración/odds, Value Engine, minimum odds, PickScore y NO BET; sólo PASS llega a `Ledger.record`. BLOCKED/NO_BET son normales. Decisiones inmutables deduplicadas por contenido bajo `ops/decisions/`; no se creó un segundo betting ledger.

**Limitación explícita de admisión real:** `v3.paper.ledger.Ledger.record` conserva `real_paper_blocked_no_accredited_model_adapter`. Un candidato que llegue a PASS seguirá bloqueado para registro real hasta disponer de un adapter acreditado. Este batch no abre esa restricción mediante flags ni modifica modelos, features, calibración o políticas. El nuevo runner expone `BLOCKED_NO_ACCREDITED_MODEL_ADAPTER` si se alcanza ese punto. La existencia del runner no resuelve ese adapter pendiente.

`settle` reutiliza el ledger append-only y admite únicamente `ops/results.json` con un resultado operacional/oficial acreditado, identidad exacta, `completed_at`, label y lineage. Nunca consulta resultados por red ni espera. Unsettled contribuye cero; no modifica la entrada CREATED. No Kelly, martingale, stake adaptativo ni ejecución sportsbook.

Runtime: `v3_data/ops/paper-status.json`, `ops/decisions/`; ledger original `v3_data/paper/ledger.jsonl` cuando sea admisible. No se generó ninguna apuesta real ni paper entry real.

Siguiente acción: obtener una predicción prospectiva con lineage y adapter acreditado bajo la arquitectura congelada; conservar el bloqueo mientras no exista. Un input JSON con flags no acredita una prediction.


## Forecast independiente de odds

**PICKS DO NOT DEPEND ON ODDS.** `python -m v3.ops.cli forecast` (alias `picks`) funciona offline, sin key ni llamadas al proveedor. Reutiliza `analysis.poisson.analizar` y el Champion BT0 / J_BT_sin_temporada. Emite `ranked_forecast_candidates`, sin seleccionar arbitrariamente un mercado por partido: elegibilidad/calidad existente, probabilidad descendente y mercado estable. Mayor probabilidad no significa mayor value. No modifica PickScore, thresholds, modelos ni gates económicos.

Fuente prioritaria: adaptador prospectivo `v3_data/ops/forecast/prospective.json` (lista de registros acreditables), luego `lambda_comparison.json` BT0, fallback `confidence_v2.json` lambda_base y salidas Champion existentes. Las salidas actuales son históricas: legacy_date/legacy_time no se convierten en kickoff con timezone ni se presentan como oportunidades futuras acreditadas.

`ACCREDITED_FORECAST` exige identidad exacta, contrato kickoff-lineage-v1 íntegro, predicción en evidencia separada con SHA verificado y registro único, `model_lineage`, `feature_cutoff_at <= generated_at < kickoff_at`, timestamps con offset y exclusión sintética explícita. El envelope `prediction_lineage` referencia source_path/source_sha256/source_record_id; el registro repite identity, model, model_lineage, probabilities, generated_at, feature_cutoff_at y kickoff_at. Evidencia runtime debe vivir en `v3_data/ops/evidence/<sha256>.json`, sin symlinks ni autoreferencia. No se acredita con flags, fecha de archivo ni mtime. El adaptador mantiene el Champion vigente; no promueve modelos.

`OPERATIONAL_LEGACY_FORECAST` es visible con `oos_eligible=false`. Sin odds: `FORECAST_PASS` es posible; odds_status=UNAVAILABLE, value_status=NOT_EVALUATED y market_odds/market_probability/edge/ev/clv/PickScore=null. fair_odds=1/p si p>0. minimum_acceptable_odds=null: la policy default Phase 4 está declarada sintética y no se convierte en política económica real.

Sólo runtime bajo `v3_data/ops/forecast/`: latest.json, journal.jsonl append-only (predicciones acreditadas prospectivas, ID y source digest estables, sin stake/sportsbook/odds obligatorias) y journal.lock. `settlements.json` admite resultados con settlement_lineage independiente, identity exacta, home_goals/away_goals enteros no negativos y settled_at posterior a kickoff. La evidencia sellada acredita los goles y settled_at. El reporte revalida la predicción original, su identidad, temporalidad y fuente; no confía en oos_eligible serializado. Duplicados o revisiones del mismo partido/mercado no inflan el contador. Resultados ambiguos quedan fuera.

Forecast OOS cuenta partidos únicos separados de predicciones por mercado: forecast_oos_count / forecast_oos_matches, forecast_oos_predictions y betting_oos_matches. Sólo resultados acreditados permiten Brier, LogLoss y Hit Rate descriptivo por mercado; no ROI/Yield/CLV/EV realized. La evidencia sintética de tests nunca se usa como evidencia operacional.

Estado observado: forecast_generation_status=AVAILABLE; 4,315 partidos, 43,150 candidatos legacy, 0 acreditados. forecast_oos_status=NO_ACCREDITED_SETTLED_FORECASTS; Forecast OOS=0 partidos/0 predicciones; Betting OOS=0/200. Value no evaluado. O-02=BLOCKED_NO_FRESH_INTERNAL_TARGET según corrección lineage preservada; O-03 betting=BLOCKED; O-04 CLV=BLOCKED; O-06=BLOCKED. El carril económico continúa por Value Engine y políticas existentes al aportar evidencia económica acreditada; forecast no crea posiciones paper ni relaja closing, CLV, promoción o gate 200.
