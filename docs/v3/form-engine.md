# Roadmap 2.2 — Feature Engine de forma

Implementación de Issue #13, aislada en `v3/features/`. No modifica el dataset canónico ni consume sus labels, predicciones o elegibilidad derivada de resultados operativos. El modo raw acredita identidad, fecha y muestras directamente desde `history.json`; no necesita abrir result, backtest_pool o Champion.

## Uso

```bash
python -m v3.features.engine --source-root data/matches --output-dir /tmp/form-v3
python -m compileall -q v3 tests
python -m pytest -q tests/v3
```

El directorio de salida debe estar fuera del árbol de evidencia. Para conservar `data/` completamente intacto, la validación real usa `/tmp/roadmap22-real-a` y `/tmp/roadmap22-real-b`. Los artefactos son `form_features.jsonl` y `form_manifest.json`. No se versionan artefactos generados.

## Contrato

- 72 nombres del catálogo 2.1.0: 8 métricas + sample_count × 2 equipos × 2 ventanas × 2 variantes de venue. Feature version 2.2.0.
- Sólo se leen secciones exactas `ÚLTIMOS PARTIDOS: <equipo>` de history.json. No se usa H2H ni agregados raw. Reconciliación de nombres exacta; el título se compara con casefold, como el contrato existente.
- Política temporal compartida: target, mismo día, futuro e identidad/fecha desconocida quedan excluidos. Todas las copias de IDs duplicados dentro de una sección quedan excluidas, incluso si coinciden; ninguna selección depende del orden raw.
- Orden: fecha descendente, match_id ascendente como desempate. Venue se filtra antes de truncar a 5/10.
- Score entero no negativo, no bool. Orientación GF/GA relativa al equipo. Rates en [0,1], overs con total > 1.5/2.5/3.5.
- Alcance del score: se acepta `score_scope=REGULATION` explícito o la gramática ordinaria local de Flashscore `[fecha, código competición, local, visitante, GF local, GF visitante, G/E/P]`, coincidente exactamente con los campos parseados. Marcadores anotados, filas desconocidas, penales y scopes explícitos distintos quedan excluidos. `resultado_parseado` por sí solo no acredita alcance. Esta política acredita la evidencia local del proveedor, no una verificación externa independiente del partido.
- Medias/rates requieren exactamente 5/10 muestras; insuficiencia produce null + insufficient_sample. Contadores conservan la cantidad válida hasta el tope; cero sólo si la sección es reconocida y no hay muestras elegibles. Sección ausente/ambigua o target inválido produce contador null y razón explícita.
- Cada feature incluye valor, sample_count, razón y referencia a ventana. Cada ventana conserva match_ids, fechas ISO, GF/GA, venue y tipo de evidencia de score. Exclusiones por equipo incluyen ID, fecha y razones; las muestras inválidas nunca contribuyen.
- JSON canónico UTF-8, claves ordenadas, sin reloj ni rutas absolutas. Manifest incluye hash del JSONL y hash de fuentes history vinculadas a IDs. Cambiar bytes irrelevantes de history puede cambiar source_sha256 sin cambiar las features.
- La cobertura representa disponibilidad acreditada desde el histórico observado; no certifica que el proveedor tenga un ledger completo de todos los fixtures.

## Validación real

Build sobre `data/matches`: **4344 targets**, **72 features/target**, **312768 celdas**, **278896 valores no null**. Denominador de cobertura: todos los targets, incluidos los que no tienen evidencia válida.

| Ventana | Targets completos | Cobertura |
|---|---:|---:|
| away_l10 | 3961 / 4344 | 91.18% |
| away_l5 | 4041 / 4344 | 93.02% |
| away_venue_l10 | 3375 / 4344 | 77.69% |
| away_venue_l5 | 3968 / 4344 | 91.34% |
| home_l10 | 3977 / 4344 | 91.55% |
| home_l5 | 4050 / 4344 | 93.23% |
| home_venue_l10 | 3399 / 4344 | 78.25% |
| home_venue_l5 | 3981 / 4344 | 91.64% |

| Set completo (todas sus ventanas/equipos) | Targets | Cobertura |
|---|---:|---:|
| complete_all | 3016 / 4344 | 69.43% |
| complete_family:recent_form | 3893 / 4344 | 89.62% |
| complete_family:sample_quality | 4108 / 4344 | 94.57% |
| complete_family:venue_form | 3016 / 4344 | 69.43% |
| complete_market:1X2_EXPERIMENTAL | 3016 / 4344 | 69.43% |
| complete_market:BTTS | 3016 / 4344 | 69.43% |
| complete_market:OVER_1_5 | 3016 / 4344 | 69.43% |
| complete_market:OVER_2_5 | 3016 / 4344 | 69.43% |
| complete_market:OVER_3_5 | 3016 / 4344 | 69.43% |

El set por mercado incluye exclusivamente las features materializadas de este alcance asignadas a ese mercado en el catálogo; no implica implementar las demás señales del catálogo. La igualdad de cobertura entre mercados se debe a que sus métricas comparten las mismas muestras y necesitan ambas ventanas y variantes venue. sample_quality sólo exige contadores conocidos, aunque las medias/rates sean null.

SHA-256 JSONL: `779040a01b40f0099d260438199dcbefdc0d052bb8cca0fda39ec8f2ab1033b4`.

SHA-256 fuentes history: `d27a835ce1f992987b964abec4c529b2ed6e7b75d3be6d148498bfa20c74cb2a`.

Tests nuevos en `tests/v3/test_form_engine.py`: orden y desempate, exclusión temporal, duplicados conflictivos, orientación, umbrales, venue antes de ventana, muestra exacta/parcial/vacía, null con razón, alcance de marcador, estructuras inválidas, independencia de inputs prohibidos, fuentes intactas, serialización y doble build byte a byte, ausencia de data staged/versionado. Suite V3 completa: 578 tests (28 nuevos).
