# Roadmap final V3

| Categoría | Estado verificable |
| --- | --- |
| IMPLEMENTED | 6.1–9.2: once checkpoints con implementation PASS y pruebas offline |
| REAL_EVIDENCE_BLOCKED | Modelos reales Phase 5, calibración, walk-forward, comparación Champion, performance |
| GATE_NOT_MET | 200 OOS: 0 / 200; promotion gate BLOCKED |
| OPERATIONAL_BLOCKED | Picks reales, ledger real, release y handoff real |
| READY | Ningún release real READY; sólo software/E2E sintético validado |

Ver [reporte automático](final-validation-report.json), checkpoints bajo
[final/](final/README.md) y reportes [6](phase-6-final.md), [7](phase-7-final.md),
[8](phase-8-final.md), [9](phase-9-final.md).

La secuencia 6.1 → 6.2 → 6.3 → 7.1 → 7.2 → 7.3 → 8.1 → 8.2 → 8.3 → 9.1 → 9.2
se ejecutó validando cada checkpoint antes del siguiente. Las correcciones finales
se revalidan con toda la suite. No se cambió pipeline estable, main.py ni Champion.

Para declarar READY falta realmente:

1. Fuente prospectiva acreditada con IDs y kickoff/cutoff timezone-aware, sin
   reconstrucciones por fechas, archivos ni estado actual.
2. Features/labels con lineage, modelos reales ajustados según Phase 5 congelada,
   predicciones OOS históricas inmutables y comparador Champion sobre exactamente
   mismos targets, labels y cutoffs. TEST final permanece sellado hasta protocolo.
3. Calibración seleccionada sólo en calibration-validation, walk-forward real
   estable y política de promoción resuelta para revisión humana.
4. Proveedor de odds autorizado y precios activos pre-cutoff acreditados; value,
   PickScore y NO BET elegibles. No inferir permisos desde visibilidad pública.
5. Registro prospectivo paper 1u antes del kickoff, settlement acreditado posterior,
   performance válida y al menos 200 partidos OOS reales únicos elegibles settled.
6. Integrity PASS y evidencia real acreditada de cada componente en release gate.
   Los adapters actuales permanecen cerrados hasta acreditar las nuevas fuentes;
   no se habilitan cambiando un flag ni reutilizando fixtures.

Closing acreditado/comparable hace falta para CLV computable; sin él CLV sigue
BLOCKED y nunca usa last observed como sustituto. La falta de closing no se
oculta como CLV cero. V3 recomienda y toda revisión humana sólo registra intención;
ningún estado coloca apuestas reales. Promoción efectiva del Champion queda fuera
del alcance de este batch, incluso si un gate recomienda PROMOTE_ELIGIBLE.
