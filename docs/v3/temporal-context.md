# Roadmap 2.4 — Rachas observadas y auditoría de fixtures

Implementa [Issue #17](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/17) en `feature/2.4-temporal-context`. Feature version 2.4.0; seis features del catálogo 2.1.0 pasan a available, con dtype int. Las cuatro features de descanso/congestión siguen blocked y no se emiten como valores deportivos.

## Uso reproducible

```bash
python -m v3.features.temporal_context --source-root data/matches --output-dir /tmp/roadmap24-a
python -m v3.features.temporal_context --source-root data/matches --output-dir /tmp/roadmap24-b
python -m v3.features.ledger_audit --source-root data > /tmp/roadmap24-ledger.json
python -m v3.features.engine --source-root data/matches --output-dir /tmp/roadmap24-form-a
python -m v3.features.engine --source-root data/matches --output-dir /tmp/roadmap24-form-b
python -m v3.features.xg_engine --source-root data --output-dir /tmp/roadmap24-xg-a
python -m v3.features.xg_engine --source-root data --output-dir /tmp/roadmap24-xg-b
python -m compileall -q v3 tests
python -m pytest -q tests/v3
```

Se compararon los JSONL y manifests de ambos builds de cada versión byte a byte. Todas las salidas están en `/tmp`, fuera de data/. El nuevo builder rechaza salida dentro del árbol fuente (incluido el padre data/ de matches/), symlinks de salida y archivos con enlaces duros. No ejecuta scraping ni importa el pipeline operativo.

## Semántica y provenance

Se reutilizan sin cambios `read_history`, `target_metadata` y `team_history` de 2.2. Sólo la sección única `ÚLTIMOS PARTIDOS: <equipo>` aporta muestras; H2H y campos/archivos operativos no participan. Target, mismo día, futuro, IDs desconocidos, duplicados (todas las copias), equipos conflictivos y scores no acreditados quedan excluidos exactamente como en 2.2. Se acepta REGULATION explícito o la gramática ordinaria Flashscore reconocida por ese adaptador; penales y anotaciones ambiguas quedan fuera.

Orden fecha descendente + match_id ascendente; últimas diez muestras elegibles, sin filtro de venue. Se empieza por la más reciente y se termina en el primer predicado falso. Scoring: GF > 0; BTTS: GF > 0 y GA > 0; clean sheet: GA == 0. GF/GA se orientan respecto al equipo del target, incluso cuando jugó de visitante.

Cada feature conserva valor, razón, observed_sample_count, partial_sample, censored, capped, censoring_reason, contributing_match_ids, breaking_match_id y referencia a ventana. La ventana conserva cada ID/fecha/GF/GA/venue/evidencia del score evaluado, eligible_sample_count y source_artifact relativo. El partido que rompe la racha queda en la ventana y en breaking_match_id; contributing_match_ids sólo incluye el prefijo que cumple. Las exclusiones incluyen IDs, fechas y razones. El manifest vincula IDs/rutas y bytes de history mediante source_sha256.

`partial_sample` significa menos de diez muestras elegibles, incluso cero. `censored` significa que todo el prefijo observado cumple y no se observó el corte: puede ser por cap 10 (`capped=true`) o borde de muestra parcial. Una muestra parcial cuyo predicado ya se rompió tiene partial_sample=true y censored=false: su longitud observada queda determinada dentro de esa muestra. Ninguna racha acredita continuidad sobre fixtures omitidos del ledger. Una sección válida vacía o sin muestras elegibles devuelve null + no_eligible_samples, count=0 y censored=true; no se inventa una racha cero. Sección ausente/ambigua, fuente inválida o target inválido produce null + razón y flags/count desconocidos. El cero deportivo requiere un partido elegible reciente que rompa el predicado.

JSON UTF-8 canónico, claves ordenadas, sin timestamp, rutas absolutas ni estado del proceso. Las seis features son aisladas; no se modifica la salida 2.2/2.3.

## Build real (2026-10-26)

4,344 targets inspeccionados; 26,064 celdas; 24,618 valores no null. Cada fila identifica su target, incluidos aquellos sin historia válida. Cobertura usa todos los targets como denominador.

| Feature | No null / targets | Cobertura | Parciales | Censuradas | Cap 10 |
|---|---:|---:|---:|---:|---:|
| away_btts_streak_capped_l10 | 4102 / 4344 | 94.43% | 149 | 86 | 35 |
| away_clean_sheet_streak_capped_l10 | 4102 / 4344 | 94.43% | 149 | 13 | 0 |
| away_scoring_streak_capped_l10 | 4102 / 4344 | 94.43% | 149 | 445 | 378 |
| home_btts_streak_capped_l10 | 4104 / 4344 | 94.48% | 133 | 79 | 30 |
| home_clean_sheet_streak_capped_l10 | 4104 / 4344 | 94.48% | 133 | 10 | 0 |
| home_scoring_streak_capped_l10 | 4104 / 4344 | 94.48% | 133 | 436 | 375 |

Parciales por equipo: home=133 (127 con valor + 6 vacías), away=149 (141 con valor + 8 vacías). Total 282 ventanas parciales; se repiten en las tres métricas de cada equipo. Censuradas: 1,069 celdas (incluyen 42 celdas de las 14 ventanas vacías), de las cuales 818 llegan a cap 10. Las otras 251 alcanzan el borde observado parcial. Secciones desconocidas no se cuentan como parciales/censuradas.

Distribución de valores no null, en orden de longitud 0..10:

| Feature | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| away_btts_streak_capped_l10 | 1849 | 977 | 529 | 314 | 180 | 102 | 56 | 28 | 20 | 12 | 35 |
| away_clean_sheet_streak_capped_l10 | 2973 | 803 | 223 | 66 | 22 | 9 | 4 | 1 | 0 | 1 | 0 |
| away_scoring_streak_capped_l10 | 960 | 760 | 525 | 408 | 336 | 248 | 178 | 128 | 88 | 93 | 378 |
| home_btts_streak_capped_l10 | 1887 | 995 | 521 | 312 | 154 | 87 | 44 | 40 | 24 | 10 | 30 |
| home_clean_sheet_streak_capped_l10 | 3050 | 755 | 193 | 70 | 27 | 9 | 0 | 0 | 0 | 0 | 0 |
| home_scoring_streak_capped_l10 | 1080 | 714 | 510 | 425 | 302 | 214 | 158 | 141 | 111 | 74 | 375 |

Razones null por feature home: missing_or_ambiguous_team_section=227, missing_or_invalid_history=7, no_eligible_samples=6; por feature away: 227, 7 y 8 respectivamente.

Exclusiones de muestras, sumadas por target/equipo; una muestra puede tener varias razones:

- future_input: 5,463.
- unverified_regulation_scope: 5,065.
- same_day_input_without_verified_time: 2,202.
- target_in_input: 2,200.
- unknown_input_identity: 80.
- team_conflict: 74.
- invalid_score: 67.

## Auditoría read-only de descanso/congestión

El reporte reproducible [temporal-ledger-audit.json](temporal-ledger-audit.json) detalla grupos, cantidades, bytes, claves, rangos de fechas y SHA-256 conjunto de las 41,893 fuentes candidatas inspeccionadas. Los rangos son exploratorios: incluyen H2H en la inspección estructural y la interpretación existente de años de dos dígitos; no acreditan cobertura temporal. H2H no aporta features ni prueba completitud.

Se inventariaron todos los nombres de archivo locales para buscar fuentes adicionales. Los artefactos derivados, predicciones, evaluaciones, experimentos, snapshots y logs operativos no se usan como ledger. No hay otro ledger local acreditado. El inventario/hashes de protección incluye todo data/, pero sus contenidos operativos no se consumen como inputs.

| Fuentes candidatas | Inspección y decisión |
|---|---|
| data/matches/*/history.json (4,337) | 8,674 secciones de equipo; 210,100 filas. 8,195 secciones contienen 25 filas. objetivo_partidos=21 en 4,334 archivos y 20 en 3. Hay 48 secciones con filas sin parsear. No hay attestation de cobertura, identidad estable de equipo ni paginación exhaustiva por intervalo. |
| data/history_raw.json (1) | Mismo esquema seccional, objetivo 20, una captura de target; no certifica calendario completo. |
| data/matches/*/xg_history.json (4,230) | Selecciones derivadas de historia, objetivo limitado por equipo y agregados L5/L10; cobertura_xg mide disponibilidad xG, no completitud de fixtures. |
| data/xg_cache/*.json (28,933) | Caché dispersa por partido solicitado; fecha/equipos/score/xG por ID, sin manifiesto exhaustivo por equipo, competición e intervalo. La unión con historias no demuestra ausencia de partidos faltantes. |
| data/partidos.json | 562 filas de partidos, generado_desde=2026-10-25, dias_solicitados=2 (25/26 de octubre); no cubre los intervalos históricos por target. Las 564 fechas del reporte incluyen las dos entradas del resumen. |
| data/partidos_hoy.json; partidos_manana.json | Listas de 164 y 216 entradas; hoy sin fecha por fila y mañana limitado al 2026-10-09. No hay continuidad de todos los días/competiciones. |
| data/partidos_candidatos.json | Filtro de candidatos: 109 sobre 569 de origen; contiene descartes y grace_minutes. No es calendario exhaustivo. |
| data/selected_matches_*.json/.txt (14+14); day_selected.json; matches_manana.txt | Selecciones de jornadas; límites de selección, horizonte horario y filtros. day_selected declara hours=4 y limit=30. No prueban ausencia de encuentros intermedios ni ventanas vacías. |
| data/matches/*/standings.json (4,342), data/standings.json, standings_page.html/.txt, standings_rows.txt | Tablas agregadas, sin ledger de cada fixture ni completitud pre-target. |
| data/flashscore_home.html, flashscore_rendered.html, date_navigation_inspect.txt, inspect_matches.txt | Capturas/inspecciones parciales de página y navegación. No hay conjunto paginado acreditado de todos los fixtures por equipo e intervalo. |
| data/match_detail.html/.txt, h2h_page.html/.txt | Detalle de un encuentro o secciones históricas/H2H truncadas, sin prueba de calendario completo. |
| data/test_matches/*/history.json y standings.json (2+2) | Fixtures de prueba, no fuente de cobertura real. |

Se leyó también el código existente de extracción, sin ejecutarlo ni modificarlo: `scraper/extract_history.py` limita el objetivo (20 por defecto, máximo configurable 40), detiene expansión tras 8 clicks y puede salir por ausencia del botón/error. Alcanzar 25 filas no es una certificación de completitud. `scraper/flashscore.py` recorre un número solicitado de días desde hoy; `filter_matches.py` y `select_batch.py` filtran estado/hora/offset y recortan por límite. Estas condiciones explican por qué las fuentes listadas pueden omitir fixtures.

**days_rest: blocked para home y away.** El fixture más reciente observado no prueba que sea el inmediatamente anterior. Hace falta un ledger de todos los fixtures finalizados de todas las competiciones para la identidad estable del equipo, cobertura explícita hasta el cutoff del target y evidencia de ausencia de encuentros entre el candidato previo y ese cutoff. Deben acreditarse paginación completa, estado final, fechas/horas/zona, reprogramaciones, cancelaciones, deduplicación e identidad, con lineage reproducible de la fuente. Los encuentros del mismo día requieren evidencia suficiente para establecer anterioridad sin eludir la política temporal compartida; sin ella se bloquea ese target.

**matches_last_14_days: blocked para home y away.** Hace falta cobertura explícita de todo `[target_date-14 días, target_date)` para cada equipo en todas las competiciones, con fixtures identificados, estados finales, fechas, evidencia de paginación exhaustiva y ausencia de huecos. También debe acreditarse una ventana sin encuentros para emitir cero; no basta no encontrar filas. Un calendario futuro programado o un conteo de muestras recientes no cumple este requisito.

Para habilitar cualquiera se requiere además un adaptador validado y tests/build real que demuestren identidad, límites temporales, cobertura completa y conflictos resueltos por target. Flags arbitrarios `complete=true`, mtime de archivos, suma de fuentes dispersas y disponibilidad xG no son evidencia de completitud. La auditoría actual sólo descubre estructura: no promueve fuentes automáticamente.

## Integridad y validación

37 tests nuevos cubren los 21 requisitos mínimos de Issue #17, incluyendo predicados, corte inicial, cap, parciales, null, reglas 2.2 compartidas, orientación, orden/desempate, duplicados, penales/score-scope, independencia H2H/inputs prohibidos, bloqueo de calendario, auditoría read-only, doble build, protección de fuentes y regresión de salidas 2.2/2.3. Suite V3 completa: **649 tests**. compileall correcto.

SHA-256 comprobados en dos builds reales (JSONL y manifests idénticos):

| Artefacto | SHA-256 |
|---|---|
| temporal_features.jsonl | `22f3f0a0e83b23b704932436cc9dbfe5e49a54c95e8f6576cc765052527042aa` |
| temporal_manifest.json | `20fe3df7920ffd1f82d11cb7490bbba06154e0d9a2befb2780cb9990412e6b32` |
| form_features.jsonl | `779040a01b40f0099d260438199dcbefdc0d052bb8cca0fda39ec8f2ab1033b4` |
| form_manifest.json | `3964f2062b71f6554c6370b336e5bba7b738ed387d343ac018b16364a0e70829` |
| xg_features.jsonl | `7003af3f3a66f0ae6d0c6cee3992e82f8b803f2ccc1f6d9bf31759b74a74a614` |
| xg_manifest.json | `7a7e4d41d8f6b1792dd606dd00b20a4face9ce8c44dba8518329e44b948879fe` |

SHA-256 fuentes history compartido: `d27a835ce1f992987b964abec4c529b2ed6e7b75d3be6d148498bfa20c74cb2a`. SHA-256 candidatos de auditoría: `df00e5da6410b61d755c99a40fcc8968970ddb5d7be995a32bc4a28e09e95bad`.

Se comparó el inventario completo y SHA-256 antes/después de los 67,219 archivos de data/, 48 de scraper/, 128 de analysis/ y 61 del backup operativo: sin altas/bajas/cambios. Los archivos de BT0/J_BT_sin_temporada están comprendidos en ese control y no se modificaron. Las comprobaciones de V3 no ejecutan operaciones del pipeline. `git diff --check` limpio; no hay data/ versionado ni staged. No se ejecutó git add, commit ni push.
