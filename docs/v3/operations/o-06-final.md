# O-06 — Champion / Challenger

Issue #59 leída completa. `implementation_status = PASS`; `real_status = promotion_status = BLOCKED`. Champion: **BT0 / J_BT_sin_temporada**, intacto. Challengers evaluables: no. Gate prerequisites: BLOCKED; OOS 0/200.

El wrapper reutiliza exclusivamente la promoción Phase 6.3 (`promotion-v1`), incluyendo replay del comparador exacto, Brier/LogLoss, calibración y ventanas temporales. Exige además gate O-05 MET, conteo concordante, predictions reales de challenger, misma población/label/market/cutoff, calibración comparable, walk-forward válido y evidencia económica paper comparable. ROI aislado nunca decide.

La salida operacional mapea la recomendación de política a PROMOTE / KEEP_CHAMPION / BLOCKED. KEEP_CHAMPION sólo puede evaluarse cuando las precondiciones también están acreditadas; una ventana insuficiente sigue BLOCKED. No se introduce una política optimizada ni se retoca la Phase 6.3.

`human_confirmation_required = true`; `auto_promotion = false`; `champion_changed = false`. Ninguna función escribe modelos ni configura al Champion. Aun PROMOTE sería sólo una recomendación para revisión humana.

Reasons actuales incluyen mínimo OOS no satisfecho, falta de predictions/comparador/población/calibración/walk-forward/economics acreditados. La lista completa y el resultado original Phase 6.3 están en O06 del reporte JSON. Runtime: `v3_data/ops/promotion-evidence.json` opcional y `operational-cycle-report.json`.

Créditos: 0 adicionales. Siguiente acción: alcanzar ≥200 matches reales únicos y settled y reunir evidencia comparable congelada; luego generar recomendación, sin auto-promoción.
