# O-04 — Closing / CLV

Issue #57 leída completa. `implementation_status = PASS` para wrapper y lógica existente; `real_status = clv_status = BLOCKED_PROVIDER_CLOSING_SEMANTICS`.

Capacidad auditada: source matrix y autorización O-01 mantienen current=documented y closing=unverified. La API current no garantiza un cierre explícito autorizado. Closing acreditado: no. CLV: null, nunca cero imputado. No se hizo otra odds call para aproximarlo.

El wrapper reutiliza `v3.odds.clv.clv`, validación de snapshots y comparabilidad exacta: provider/bookmaker/internal y external match/kickoff/market/selection/line, orden temporal y lineage. Sólo closing acreditado y comparable habilita `odds_taken / odds_close - 1`. Tests existentes verifican fórmula y rechazo de cambios de serie. Last price, T-1h y provider_last_update nunca se convierten a closing. Closing sólo sirve para evaluación ex-post; el selector rechaza closing como input.

Reason: `no_explicit_accredited_comparable_closing`. Evidence y valores: sección O04 del reporte operacional. Runtime: `v3_data/ops/operational-cycle-report.json`; no closing real generado.

Créditos adicionales: 0. Limitación: no hay semántica de cierre acreditada para este proveedor. Siguiente acción: acreditar una fuente/semántica explícita y autorizada más su comparabilidad; no pagar historia ni usar una captura extra para simular closing.
