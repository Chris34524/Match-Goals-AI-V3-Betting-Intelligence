# Roadmap 2.3 — xG/xGA con calidad y linaje

Implementado en `feature/2.3-xg-xga-quality`, fuente de verdad Issue #15.

## Contrato y límite de disponibilidad

`xg_adapter.py` reconcilia cada muestra raw con identidad/fecha/equipos de
`history.json`. Valida orientación y consistencia entre xg_local/xg_visitante y
xgf/xga. Rechaza target, mismo día (incluso con hora raw no acreditada), futuro,
fecha/identidad desconocida, pares incompletos, negativos, bool, NaN e infinito.
Todos los duplicados de una sección se excluyen; copias idénticas entre history
y cache se reconcilian sin contar dos veces. Conflictos entre lados o caché
invalidan la muestra. El orden raw no determina el resultado.

**Una fecha de partido anterior no acredita disponibilidad del valor xG.**
El build local no tiene ninguna fuente acreditada de publicación/revisión y no
suministra attestations. Por eso no habilita ninguna media en estos datos.
La API de reconciliación admite attestations de un caller de confianza, con
`observed_at` timezone-aware, `source_artifact` y `value_sha256` vinculando ID,
fecha, equipos y par numérico exacto. Deben provenir de evidencia independiente
verificada por ese caller; no son una declaración que el raw pueda autorizar.
No existe CLI para saltar este gate ni se extraen attestations de los JSON raw.
Habilitar un proveedor de esas acreditaciones requiere un adapter y auditoría
adicional; no se afirma que los datos locales satisfagan ese contrato.

## Features y provenance

Salida separada `xg_features.jsonl`, versión 2.3.0, catálogo intacto 2.1.0:

- `{home,away}_xg_mean_l{5,10}` (nombre canónico de xGF medio).
- `{home,away}_xga_mean_l{5,10}`.
- `{home,away}_xg_sample_count_l{5,10}`.
- `bilateral_xg_available_l{5,10}`.

Son 14 columnas del catálogo, con value/reason y ventanas auditables.
Las medias requieren las 5/10 muestras; sample_count conserva el conteo válido
hasta el tope. Se selecciona primero la ventana de fixtures recientes del equipo,
después se valida xG: el catálogo prohíbe backfill desde encuentros más antiguos.
Ausencia de sección o identidad target inválida produce count null; sección
inspeccionada sin muestras acreditadas produce count 0 y medias null, nunca
medias imputadas a cero. La disponibilidad bilateral se evalúa por ventana.
Provenance incluye IDs, fechas, par orientado, artifacts, evidencia de
disponibilidad cuando existe, exclusiones y quality flags.

No se materializan goals_per_xg: no se ha acreditado su linaje conjunto con
scores. No hay variantes venue xG en catálogo 2.1; el test de venue es N/A.
No se usan agregados l5/l10, enriched, labels ni outputs operativos.
El motor 2.2 y sus 72 features no dependen del nuevo módulo y no se modificaron.

## Auditoría local read-only (2026-10-26)

4.344 targets inspeccionados; **0 con >=1 muestra xG acreditada**.
Cobertura de medias home/away L5/L10: **0/4.344** en cada ventana.
Cobertura bilateral L5/L10: **0/4.344**. Venue: N/A.

| Ventana | sample_count 0 | sample_count null |
| --- | ---: | ---: |
| home L5 y L10, cada una | 4.096 | 248 |
| away L5 y L10, cada una | 4.095 | 249 |

- 4.230 xg_history auditados; 4.228 con alguna identidad reconciliada.
- 83.190 apariciones raw en history; 32.761 con ambos valores numéricos.
- 28.933 cache auditados; 28.929 IDs reconciliados con apariciones history.
- 9.167 cache con ambos valores numéricos.
- **4.230 histories y 28.933 caches bloqueados por falta de disponibilidad
  histórica acreditada**, aunque su identidad pueda reconciliarse.
- Otros raw identificados en 2.1A: `data/history_raw.json`,
  `data/match_detail.html`, `data/match_detail.txt`, inspeccionados y hasheados;
  bloqueados como fuentes xG por ausencia de adapter/linaje de disponibilidad.
  El history raw es un snapshot de otro target y los detalles HTML/TXT son
  snapshots de página, no un ledger histórico de publicaciones xG.

Principales exclusiones (apariciones, razones no mutuamente excluyentes):

| Razón | Apariciones |
| --- | ---: |
| disponibilidad xG pre-target no acreditada | 83.190 |
| par xG inválido/incompleto | 50.429 |
| equipo/orientación conflictivos | 2.641 |
| valores orientados inconsistentes | 419 |
| identidad no reconciliada con history | 40 |
| conflicto de identidad/valor con cache | 3 |

## Validación y reproducción

```bash
python -m compileall -q v3 tests
python -m pytest -q tests/v3
python -m v3.features.xg_engine --source-root data --output-dir /tmp/roadmap23/build1
python -m v3.features.xg_engine --source-root data --output-dir /tmp/roadmap23/build2
```

**612 tests pasan**, incluidos 34 casos nuevos para los gates de Issue #15.
Se prueban también null/count parcial, no backfill, orden raw, orientación,
conflicto entre fuentes, attestations no vinculadas, aislamiento de las 72
features, serialización/builds idénticos, source bytes/mtime y ausencia de data
staged. Los casos positivos usan acreditaciones sintéticas explícitas; no se
confunden con cobertura real.

Dos builds reales xG: igualdad byte a byte de JSONL y manifest.
Dos builds reales 2.2: igualdad byte a byte de JSONL y manifest.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| xg_features.jsonl | 32193225 | `7003af3f3a66f0ae6d0c6cee3992e82f8b803f2ccc1f6d9bf31759b74a74a614` |
| xg_manifest.json | 1238 | `7a7e4d41d8f6b1792dd606dd00b20a4face9ce8c44dba8518329e44b948879fe` |
| form_features.jsonl | 63338619 | `779040a01b40f0099d260438199dcbefdc0d052bb8cca0fda39ec8f2ab1033b4` |
| form_manifest.json | 793 | `3964f2062b71f6554c6370b336e5bba7b738ed387d343ac018b16364a0e70829` |

Digest de fuentes del build xG:
`3eb261d39b224541b06a2d7089c9d63e5b5a72ff18bb604c7d7f9508e2b83557`.
Salidas generadas únicamente bajo `/tmp/roadmap23/`.

Comparación antes/después de nombres y SHA-256 de cada archivo regular:
67.219 archivos de data, 33 de scraper y 85 de analysis, sin cambios. Se excluye
__pycache__ del fingerprint; no se excluyen históricos ni backups operativos.
No hay cambios en BT0 / J_BT_sin_temporada ni archivos operativos/versionados
preexistentes. No se ejecutó git add, commit ni push.
