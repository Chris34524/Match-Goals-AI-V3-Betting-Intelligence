# Flashscore México — matriz prioritaria y límites reales

**Referencia principal: https://www.flashscore.com.mx/.** API-Football conserva su implementación como complemento explícito; no hay fallback automático, fusión por nombres ni sustitución de identidad. Esta auditoría se presentó antes de ampliar código de reutilización. No se creó ningún extractor ni se ejecutó scraping deportivo nuevo.

## Matriz resumida

| Campo / familia | Existencia comprobada / evidencia | Extracción actual | Límite y siguiente paso |
| --- | --- | --- | --- |
| Fixture ID, fecha, país, competición, equipos y estado | Archivo local y descripción oficial mexicana | `scraper/flashscore.py::extraer_partidos` | Validar fecha de fila, duplicados y kickoff; no inferir zona/temporada |
| Hora | Campo local parcial | `obtener_hora` | Ausente en algunos estados; no equivale a timestamp acreditado |
| Historial, resultados FT, GF/GA | Filas archivadas | `extract_history.py::parsear_fila` | El parser legado acepta más gramáticas que el filtro V3: mantener verificación de regulación, fecha e identidad |
| Forma L5/L10/L20 y sede | Derivada del historial | Resúmenes y adaptadores existentes | Ventanas solapadas; no sumar n ni convertir faltantes en cero |
| H2H | Filas archivadas y catálogo público previo | `extract_history.py` + `v3/features/h2h.py` | n variable; auxiliar, sin falsear cobertura |
| xG/xGA | Valores locales y documentación mexicana | `extract_xg.py` + `data/xg_cache/` | Periodo activo y captura no registrados; publicación/revisiones históricas no acreditadas |
| Clasificación/posición/PJ/G/E/P/GF/GC/DG/puntos/forma | Tablas locales | `standings.py::extraer_fila` | Snapshot sin as-of; lectura descriptiva separada, nunca feature retrospectiva |
| Goles 1H/2H | Evidencia indexada previa de otras superficies Flashscore | No extractor productivo legado | Verificar resumen y periodo sobre evidencia permitida; no fraccionar λ FT |
| Córners FT | Descripción oficial mexicana y catálogo indexado previo | Contrato/replay V3, sin scraper productivo | Fuente/periodo/cobertura variables; requiere autorización y muestras históricas |
| Amarillas/rojas FT | Descripción oficial mexicana; conteo detallado previo no confirmado | Sin captura productiva legada | Validar segunda amarilla, roja directa, expulsión y actor; sin puntos de casas inferidos |
| Remates totales/a puerta, posesión y faltas | Descripción mexicana y/o catálogo indexado, según campo | Contratos V3, sin extracción productiva legada | Extender la misma extracción de filas de estadísticas cuando exista permiso, no otro scraper paralelo |
| Córners/tarjetas/remates/xG/posesión/faltas 1H/2H | Controles de periodo en auditoría previa; selección activa no verificada | Contratos, sin datos reales acreditados | UNKNOWN por periodo; no copiar FT a mitades |
| xGOT/xA, pases, duelos, portero y estadísticas de jugadores | Catálogo previo basado principalmente en Índice público internacional | Declarativo/replay; no extractor productivo | No atribuir cobertura por partido de México a partir de etiquetas de otro dominio |
| Alineación/lesiones/entrenadores | Texto/superficie pública previa y parte del HTML local | Inspectores existentes, sin ingesta prepartido acreditada | Predicha/oficial, identidad y publicación deben verificarse |
| 1X2, doble oportunidad, BTTS, over/under, λ | Salidas del Champion/Poisson existente | Análisis, no scraping | Estimaciones operacionales; no datos observados ni probabilidades validadas por ampliar cobertura |

La columna de existencia distingue archivos efectivamente inspeccionados, descripción oficial de producto y evidencia pública indexada anterior. Ninguna de ellas demuestra cobertura universal ni otorga autorización de adquisición. La matriz completa al final conserva esa distinción por campo.

## Alcance local de esta lectura

El auditor existente `v3.features.audit.audit_sources` encontró **6633 directorios**, 6626 historiales, 6518 archivos de xG y 6631 archivos de clasificación. Son archivos del árbol `data/matches`, no un universo de fixtures prospectivos acreditados.

Hay 6188 targets con al menos cinco muestras candidatas en ambos equipos y 6010 con al menos diez. El auditor no verifica por estos conteos todo el scope reglamentario ni el estado de entrenamiento. En xG encontró 52741 pares numéricos en listas (ocurrencias, no fixtures históricos únicos) y 3066 directorios con algún par numérico bilateral. **Presencia numérica no acredita linaje ni habilita entrenamiento.**

Calendario: 714 filas, 703 IDs distintos, 11 IDs con identidad/fecha conflictiva; 520 filas con hora no vacía. Se excluyen todas las variantes conflictivas de la selección. `generado_desde` es una etiqueta de fecha, no captura timezone-aware.

Digest del conjunto de cinco artefactos leído por el auditor: `89c492ebe8333035fc49e08f970678ee332209bf0e42dc923c08271cdcd85d06`. La lectura es secuencial y no bloquea el pipeline heredado concurrente. La primera lectura de esta sesión tenía 6.623 directorios y la lectura persistida 6633; los conteos no son un snapshot global atómico.

Los HTML locales `data/match_detail.html`, `h2h_page.html` y `standings_page.html` fueron inspeccionados sin recaptura. Sus canonical URLs pertenecen a flashscore.com.mx, pero no confirmaron filas pobladas de las estadísticas avanzadas buscadas. No se convierte ese resultado en ausencia global de estadísticas. Los snapshots legados tampoco registran una captura verificable.

## Revisión actual de condiciones y autorización

Consulta de documentación pública el **2026-11-07**, enlazada desde el footer mexicano. Las condiciones publicadas describen uso personal y limitaciones comerciales; restringen extracción/reutilización sustancial de la base, solicitudes automatizadas que carguen sus servidores y adaptación del contenido sin consentimiento, con las salvedades legales indicadas. No se encontró una autorización expresa aplicable a ampliar esta adquisición. Se conserva `BLOCKED_SOURCE_AUTHORIZATION`; leer una página pública o poseer un archivo no abre ese gate. [Condiciones oficiales de Flashscore México](https://www.flashscore.com.mx/terms-of-use/).

La portada mexicana describe xG, tiros a gol, posesión, córners, amarillas/rojas y faltas. Sus FAQ reconocen que faltan datos de algunas competiciones y periodos históricos. Eso acredita la oferta del producto, no cada campo de cada fixture. [Portada oficial](https://www.flashscore.com.mx/), [FAQ de datos](https://www.flashscore.com.mx/faq/data/).

El intento de consultar robots.txt mediante la herramienta web no devolvió un contenido accesible. No se infiere permiso de ese resultado ni se consultan endpoints internos para sortearlo. No se envió ninguna solicitud de consentimiento al proveedor ni se interpretó el registro de una cuenta como licencia de extracción.

## Qué se reutiliza ahora

- Calendario, historial y selección existentes; filtros de identidad/fecha/scope existentes de V3.
- Auditor `audit_sources`, catálogo `observed-fields.json` y reconciliador `xg_adapter.reconcile`, sin alterarlos ni suministrar attestations fabricadas.
- xG/xGA archivados: medias descriptivas L5/L10 sobre la ventana de historial realmente elegible; sin buscar muestras más antiguas para rellenar huecos. Todos los duplicados/conflictos, target/mismo día/futuro y cache contradictoria quedan excluidos.
- Clasificación archivada: valores del snapshot del mismo ID y orientación; mostrados fuera de los inputs del Champion. Captura y periodo desconocidos se registran como null con causa.
- Plan FULL_MATCH_V1 y contratos/replay existentes. No se cambia el transporte bloqueado de Flashscore ni se activa el scraper heredado de forma implícita.
- `source_policy` en JSON declara Flashscore México como referencia principal, proveedor activo y ausencia de fallback automático. Un análisis API-Football sigue requiriendo selección explícita y sus propios IDs. No hay mezcla automática por campo entre proveedores sin un crosswalk verificado.

Cada observación nueva incluye fuente/digest, ventana, n, cobertura, periodo, captura, estado observado y bloqueo predictivo. Para el legado que no los registró, periodo y captura permanecen null. El momento de leer un archivo no se convierte en momento de captura. `OBSERVED_UNACCREDITED` no es `EXPERIMENTAL` ni una predicción validada.

La caché xG existente acepta `ok` y `xg_no_disponible` persistentes sin TTL o fecha de captura. No se modifica aquí: una futura política de revalidación necesitará permiso, presupuesto, fecha de observación y semántica de ausencia.

## Ejecución offline

```bash
cd /home/leos/projects/match-goals-ai
.venv/bin/python -m v3.selected_analysis.cli audit-flashscore > /tmp/flashscore-mx-coverage.json
.venv/bin/python -m v3.selected_analysis.cli list --date hoy
.venv/bin/python -m v3.selected_analysis.cli analyze --date 2026-11-06 --match-id pMxurfFb
```

`audit-flashscore --live` se rechaza antes de construir un cliente. Los archivos JSON/HTML nuevos se guardan en el directorio aislado habitual. La autorización futura debe documentar proveedor, método permitido, alcance de campos/periodos, límites y retención; después deberá verificarse cobertura y linaje. Ningún flag abre automáticamente el transporte Flashscore.

## Siguiente integración permitida

1. Obtener evidencia de autorización y mecanismo permitido; mantener los gates actuales mientras falte.
2. Extender la fila de estadísticas de `extract_xg.py` para campos adicionales, reutilizando navegación, caché e identidad; verificar periodo activo, cero explícito/ausencia y errores. El calendario/historial/clasificación siguen siendo sus scrapers existentes.
3. Conservar capturas fechadas y hashes, IDs de equipo/competición/temporada, scope reglamentario y publicaciones/revisiones para mitades, córners y tarjetas. Validar semántica de eventos antes de habilitar mercados.
4. Complemento autorizado sólo solicitado explícitamente: resolver equivalencia con evidencia estable y mantener IDs/procedencia independientes; conservar datos Flashscore ya válidos, sin reemplazarlos o mezclarlos por nombres.
5. Validación temporal y calibración por mercado con datos reales, manteniendo separados observados, modelos experimentales, Champion operacional y evidencia OOS. NO_BET continúa por defecto.

## Matriz completa por campo

Visibilidad: `MX` = descrito oficialmente en el producto mexicano, sin garantía por fixture; `Índice previo` = evidencia histórica indexada principalmente de otras versiones; `Local` = contrato/archivo existente; `UNKNOWN` = no confirmado. El número de archivos no mide valores no nulos.

| Campo | Periodo solicitado | Visibilidad | Extracción legada | Componente reutilizable | Calidad de periodo |
| --- | --- | --- | --- | --- | --- |
| `away_team` | metadata | MX, variable | IMPLEMENTED | `scraper/flashscore.py::extraer_partidos` | FIXTURE_METADATA |
| `big_chances` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `big_chances_missed` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `big_chances_scored` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `blocked_shots` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `box_touches` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `capture_timestamp` | provenance | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `card_direct_red` | event | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `card_dismissal_id` | event | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `card_second_yellow` | event | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `clearances` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `competition` | metadata | MX, variable | IMPLEMENTED | `scraper/flashscore.py::extraer_partidos` | FIXTURE_METADATA |
| `completed_crosses` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `completed_final_third_passes` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `completed_long_balls` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `completed_passes` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `corners` | FT | MX, variable | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `corners_1h` | 1H | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `corners_2h` | 2H | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `country` | metadata | Local | IMPLEMENTED | `scraper/flashscore.py::extraer_partidos` | FIXTURE_METADATA |
| `crosses` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `duels_won` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `errors_leading_goal` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `errors_leading_shot` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `final_score` | FT | MX, variable | IMPLEMENTED | `scraper/extract_history.py::parsear_fila` | SCOPE_REQUIRES_VALIDATION |
| `final_third_passes` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `fixture_date` | metadata | MX, variable | IMPLEMENTED | `scraper/flashscore.py::extraer_partidos` | FIXTURE_METADATA |
| `fixture_id` | metadata | Local | IMPLEMENTED | `scraper/flashscore.py::extraer_partidos` | FIXTURE_METADATA |
| `fixture_status` | metadata | MX, variable | IMPLEMENTED | `scraper/flashscore.py::extraer_partidos` | FIXTURE_METADATA |
| `fixture_time` | metadata | MX, variable | IMPLEMENTED | `scraper/flashscore.py::extraer_partidos` | FIXTURE_METADATA |
| `form_l5_l10_l20` | metadata | Local | IMPLEMENTED | `analysis/enrich_match.py::calcular_ventanas_equipo` | DERIVED_FROM_VETTED_SCORES |
| `formation` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `fouls` | FT | MX, variable | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `fouls_1h` | 1H | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `fouls_2h` | 2H | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `free_kicks` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `goal_minute` | event | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `goalkeeper_saves` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `goals_by_period` | 2H | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `goals_prevented` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `h2h_results` | FT | Índice previo | IMPLEMENTED | `scraper/extract_history.py::extraer_seccion` | SCOPE_REQUIRES_VALIDATION |
| `halftime_score` | 1H | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `home_team` | metadata | MX, variable | IMPLEMENTED | `scraper/flashscore.py::extraer_partidos` | FIXTURE_METADATA |
| `interceptions` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `key_passes` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `long_balls` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `offsides` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `own_goal_event` | event | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `pass_accuracy` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `passes` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `penalty_goal` | event | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_assists` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_box_touches` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_completed_passes` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_dribbles` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_duels` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_goalkeeper_saves` | FT | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_goals` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_goals_prevented` | FT | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_minutes` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_own_goals` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_pass_accuracy` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_rating` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_red_cards` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_shots` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_shots_on_target` | FT | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_touches` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_xa` | FT | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_xg` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_xgot` | FT | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_xgot_faced` | FT | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `player_yellow_cards` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `possession` | FT | MX, variable | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `possession_1h` | 1H | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `possession_2h` | 2H | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `prematch_current_match_statistics` | FT | NOT_OBSERVED | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `publication_revision_lineage` | provenance | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `red_cards` | FT | MX, variable | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `red_cards_1h` | 1H | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `red_cards_2h` | 2H | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `season_id` | metadata | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `shots` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `shots_1h` | 1H | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `shots_2h` | 2H | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `shots_inside_box` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `shots_off_target` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `shots_on_target` | FT | MX, variable | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `shots_on_target_1h` | 1H | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `shots_on_target_2h` | 2H | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `shots_outside_box` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `stable_team_ids` | metadata | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `standing_draws` | FT | Índice previo | IMPLEMENTED | `scraper/standings.py::extraer_fila` | SEASON_SNAPSHOT_NOT_ASOF |
| `standing_form` | FT | Índice previo | IMPLEMENTED | `scraper/standings.py::extraer_fila` | SEASON_SNAPSHOT_NOT_ASOF |
| `standing_goal_difference` | FT | Índice previo | IMPLEMENTED | `scraper/standings.py::extraer_fila` | SEASON_SNAPSHOT_NOT_ASOF |
| `standing_goals` | FT | Índice previo | IMPLEMENTED | `scraper/standings.py::extraer_fila` | SEASON_SNAPSHOT_NOT_ASOF |
| `standing_losses` | FT | Índice previo | IMPLEMENTED | `scraper/standings.py::extraer_fila` | SEASON_SNAPSHOT_NOT_ASOF |
| `standing_played` | FT | Índice previo | IMPLEMENTED | `scraper/standings.py::extraer_fila` | SEASON_SNAPSHOT_NOT_ASOF |
| `standing_points` | FT | Índice previo | IMPLEMENTED | `scraper/standings.py::extraer_fila` | SEASON_SNAPSHOT_NOT_ASOF |
| `standing_position` | FT | Índice previo | IMPLEMENTED | `scraper/standings.py::extraer_fila` | SEASON_SNAPSHOT_NOT_ASOF |
| `standing_wins` | FT | Índice previo | IMPLEMENTED | `scraper/standings.py::extraer_fila` | SEASON_SNAPSHOT_NOT_ASOF |
| `starting_lineups` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `substitutes` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `tackles` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `tackles_won` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `throw_ins` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `venue_form` | metadata | Local | IMPLEMENTED | `v3/features/history_adapter.py::team_history` | DERIVED_FROM_VETTED_SCORES |
| `xa` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `xg` | FT | MX, variable | IMPLEMENTED | `scraper/extract_xg.py::extraer_xg_pagina` | FT_NOT_VERIFIED |
| `xg_1h` | 1H | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `xg_2h` | 2H | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `xga` | metadata | Local | IMPLEMENTED | `scraper/extract_xg.py::perspectiva_equipo` | FT_NOT_VERIFIED |
| `xgot` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `xgot_faced` | FT | Índice previo | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `yellow_cards` | FT | MX, variable | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `yellow_cards_1h` | 1H | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |
| `yellow_cards_2h` | 2H | UNKNOWN | NOT_IMPLEMENTED | Pendiente | NOT_VERIFIED |

Total: **116 campos/familias**; son entradas de auditoría, no 116 modelos ni señales entrenables. [JSON completo con cobertura, fuentes y bloqueos](mx-coverage-audit.json). [Validación de esta ampliación](mx-priority-validation.md).
