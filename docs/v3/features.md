# Catálogo canónico V3 — Roadmap 2.1 / Issue #9

Versión independiente `2.1.0`; no cambia `schema_version` ni `feature_version`
del dataset. Fuente de verdad de alcance:
[Issue #9](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/9).

118 candidatos: **86 available, 6 planned, 26 blocked**. `available` significa
que existe evidencia raw para implementar la definición en una fase futura;
no significa extractor implementado, valor calculado ni disponibilidad en todas
las filas. `planned` identifica definiciones sobre evidencia utilizable con una
semántica adicional pendiente (rachas observadas censuradas). `blocked` impide
usar la fuente hasta cumplir el requisito explícito. Un import no lee `data/`.
No se generan features, no se entrenan modelos y no se conecta con Champion.

```python
from v3.features import CATALOG, catalog_json, get_catalog
candidates = get_catalog(market='BTTS', group='recent_form', status='available')
text = catalog_json()  # JSON canónico; versión, claves y nombres ordenados
```

Los objetos son dataclasses frozen con tuplas; los filtros son conjuntivos,
conservan orden y rechazan valores desconocidos. La serialización devuelve
copias JSON independientes, UTF-8, sin reloj, rutas personales ni números no
finitos. Un cambio de definición requiere revisar la versión del catálogo.
No hay selección automática de features para entrenamiento.

## Semántica y reglas de ausencia

- Todas las muestras requieren identidad y equipo verificables, score entero
  no negativo parseado y fecha anterior al día local del target. Se aplica
  `v3.data.temporal.sample_reasons`: target, mismo día (incluso con `hora` raw),
  futuro, ID o fecha desconocidos nunca pueden contribuir. Se requiere además
  elegibilidad de la fila V3; un recuento de muestras válidas no elimina un gate.
- La fecha propia de un partido terminado acredita anterioridad bajo la política
  histórica V3 existente. No se inventa `available_at`; mtime y captura no son
  prueba. Esta excepción no acredita revisiones xG ni tablas agregadas.
- Se verificará el alcance reglamentario del score: no sumar penales; si no puede
  separarse prórroga o certificarse el alcance, el futuro extractor devuelve null.
  Los conteos de auditoría son un techo aproximado, no certifican este alcance.
- Orden de selección: fecha descendente y match_id ascendente para empates de
  fecha; IDs únicos. No confiar en el orden raw. Se incluyen todas las competiciones
  observadas, incluidos amistosos; no se presentan como métricas de liga/temporada.
- L5/L10 de forma requieren exactamente 5/10 muestras elegibles. La separación
  `home_L*` selecciona primero partidos del equipo local jugando como local;
  `away_L*`, del visitante jugando como visitante; después aplica la ventana.
  No son los primeros 5/10 partidos generales filtrados posteriormente.
- GF/GA siempre son desde la perspectiva del equipo objetivo, no del marcador
  local raw. Rates son fracciones [0,1], medias en goles/partido. Los sample_count
  son conteos enteros de 0 a la ventana; cero sólo ante sección vacía verificada.
- H5/H10 usan hasta 5/10 enfrentamientos verificables de la pareja exacta; tasas
  y medias exigen al menos 3. `home_gf/ga` orientan al equipo local del target,
  aunque jugara de visitante históricamente; GF visitante = GA local y viceversa.
  H2H es auxiliar independiente, nunca se mezcla con el core de forma.
- Las 6 rachas planned son prefijos consecutivos de los últimos hasta 10 partidos
  elegibles observados. Se censuran al tamaño de muestra/10; no declaran una racha
  real ininterrumpida si hay huecos en la fuente. No necesitan 10 para observar un
  prefijo, pero sí al menos 1 y deben conservar indicador de censura en el futuro.
- xG y xGA usan pares válidos sobre las mismas muestras. L5/L10 selecciona primero
  la ventana de partidos; no busca partidos más antiguos para rellenar xG ausente.
  Conversión es suma GF/suma xG sobre idénticas muestras; denominador cero => null.
  Conteo bilateral no es un permiso para usar la fuente.
- Ausencia, muestra insuficiente, score ambiguo o evidencia inválida => null con
  razón y conteo observado. No rellenar con cero, media, labels, resultados del
  target ni agregados alternativos. Los futuros outputs deben conservar IDs,
  fechas, exclusiones y censura. No se modifica el contrato de dataset para ello.

Fuentes prohibidas: labels, `backtest_pool.json`, resultados target, snapshots
Champion, lambdas y predicciones. No se habilita stacking en esta fase.
`enriched.json` y `h2h_analysis.json` se inspeccionan para comparar estructura,
pero sus agregados no son fuentes del catálogo: se reconstruiría desde history.

## Auditoría real de sólo lectura (2026-10-26)

```bash
python -m v3.features.audit --source-root data/matches
```

Recorre nombres ordenados y sólo abre para lectura cinco artefactos por directorio.
No sigue archivos/directorios symlink; rechaza claves JSON duplicadas y constantes
no finitas. Emite JSON en stdout, sin escribir artefactos. El digest une por archivo
ruta relativa terminada en NUL y SHA-256 binario del contenido, en orden de carpeta
por los cinco artefactos declarados. No incluye mtime, reloj ni raíz absoluta.
Los conteos no calculan medias, tasas ni features. Evidencia xG numérica sólo mide
presencia, no autoriza uso. La auditoría de standings registra estructura y presencia,
no deriva disponibilidad de que exista una clave de timestamp.

**4,344 directorios actuales**, más que las 4,256 filas congeladas del snapshot de
referencia; no se reconstruye ni sobrescribe ese snapshot. Digest de fuentes:
`f6141fe9bd1e05f613b545b7b44f5cdfbc1e79b031044df58c80eca2bb4c6e53`.

| Artefacto | Presente | Ausente | Evaluación |
| --- | ---: | ---: | --- |
| history.json | 4337 | 7 | Evidencia parcial por muestra; fuente de forma y H2H raw |
| xg_history.json | 4230 | 114 | Listas raw presentes, valores parciales; bloqueado por linaje as-of |
| standings.json | 4342 | 2 | 3848 tablas; 494 omisiones explícitas; bloqueado |
| h2h_analysis.json | 4215 | 129 | Agregados y listas derivadas; preferir pareja raw de history |
| enriched.json | 4227 | 117 | Resúmenes/controles de exclusión; no acreditan inputs completos |

Inspección de estructura: xG contiene `local/visitante.partidos` y resúmenes
`l5/l10`; la muestra `EyBCKVo9` conserva IDs, fechas y valores xG null. Standings
`EyBCKVo9` tiene posición/puntos/PJ y tabla, sin fecha as-of ni partidos constituyentes.
`h2h_analysis` declara `partido_objetivo_excluido`, pero ese claim no demuestra la
anterioridad de todos los inputs. Enriched declara exclusiones, pero éstas no
sustituyen las muestras originales verificadas.

| Evidencia de muestra actual | Home | Away |
| --- | ---: | ---: |
| Secciones de equipo reconocidas | 4110 | 4110 |
| Secciones sin rechazos de auditoría | 2979 | 2995 |
| >=5 muestras históricas válidas | 4058 | 4050 |
| >=10 muestras históricas válidas | 3986 | 3965 |
| >=5 muestras en sede correspondiente | 3995 | 3980 |
| >=10 muestras en sede correspondiente | 3517 | 3512 |
| Algún par xG/xGA numérico | 2160 | 2155 |

Ambos equipos tienen >=5 muestras en 4,028 directorios y >=10 en 3,902.
H2H: 4,337 secciones reconocidas, 3,502 con >=1 muestra, 2,964 con >=3,
2,567 con >=5 y 2,006 con >=10. Hay 32,703 pares xG/xGA numéricos y
1,981 directorios con algún par bilateral; **ninguno se habilita** por ese conteo.
Entre pares numéricos no se detectaron fechas rechazadas por la regla de día,
lo cual sigue sin acreditar disponibilidad/revisiones de los valores xG.

Rechazos por muestra (no por fila, pueden solaparse): 5,692 futuro,
3,319 mismo día, 3,317 target, 1,089 conflicto de equipo, 118 ID desconocido y
72 score no parseado/inválido. Las coberturas válidas pueden coexistir con otras
muestras rechazadas dentro de la sección; no equivalen a filas elegibles.

### Comparación con el snapshot congelado

Snapshot `v3-dfd2ee642ffed047e7a2b62298ca9be10fa214f5b1538d3e593dd14db148a7cc`,
SHA-256 dataset `fa732fdb2a7be786c99495bebbafa03956d52407e4a64d84aeb1293529a43e06`.
Lectura directa: 4,256 filas, 2,896 elegibles. Conteos canónicos ya existentes
(no features nuevas):

| Conteo del snapshot >= ventana | Home L5 | Away L5 | Home L10 | Away L10 |
| --- | ---: | ---: | ---: | ---: |
| history_count | 3982 | 3974 | 3912 | 3893 |
| venue_history_count | 3921 | 3907 | 3453 | 3450 |

2,910 filas tienen h2h_count >=3. Son coberturas antes de intersectar elegibilidad
y verificar alcance reglamentario; no se promete materialización en todas ellas.

## Bloqueos y requisitos de habilitación

- **xG (18)**: aunque hay listas por partido y fecha, falta acreditar cuándo se
  publicaron/revisaron los valores xG, reconciliar identidad/orientación con
  history y validar cada par finito no negativo antes del cutoff. No implementar
  todavía extractor. Resúmenes l5/l10 y ausencia de futuros no bastan.
- **Fuerza/standings (4)**: requiere liga/temporada, disponibilidad pre-target
  acreditada y linaje de los partidos constituyentes. Tabla actual sin as-of no
  sirve; no inferir posición histórica ni usar standings actuales retrospectivamente.
- **Descanso y congestión (4)**: historial con tope no certifica fixture inmediatamente
  anterior ni intervalo de 14 días completo. Exigir ledger completo fechado de todas
  las competiciones hasta cutoff, evidencia de huecos/cero partidos y exclusión de
  target/mismo día/futuro. No llamar descanso real al tiempo desde último observado.
- **Agregados enriched/H2H**: no se habilitan directamente; la ruta disponible es
  history raw con identidad, fecha y score verificables. H2H permanece auxiliar.

## Mercados candidatos

Estas asociaciones expresan hipótesis, no utilidad predictiva validada. Tasas
específicas de BTTS y cada over sólo se asocian a su mercado. GF/GA, conteos de
muestra y xG son señales base para los cinco mercados. Clean sheets/failed-to-score
se asocian a BTTS y 1X2 experimental. Contexto de descanso/congestión y standings
se reservan para 1X2 experimental. Las rachas tienen asociaciones explícitas.
Una feature puede aparecer en varios mercados; los conteos no son aditivos.

| Mercado | Total | Available | Planned | Blocked |
| --- | ---: | ---: | ---: | ---: |
| BTTS | 80 | 56 | 6 | 18 |
| OVER_1_5 | 60 | 40 | 2 | 18 |
| OVER_2_5 | 58 | 40 | 0 | 18 |
| OVER_3_5 | 58 | 40 | 0 | 18 |
| 1X2_EXPERIMENTAL | 74 | 46 | 2 | 26 |

## Inventario por feature

En la tabla, `history` = `data/matches/<id>/history.json`, `xg` =
`data/matches/<id>/xg_history.json`, `standings` =
`data/matches/<id>/standings.json`. Riesgo **histórico** remite a las reglas de
identidad/fecha/score anteriores; **censura** a prefijos observados; **xG as-of**,
**tabla as-of** y **completitud** a los requisitos de bloqueo anteriores.
La descripción y la regla temporal completas están en cada `FeatureSpec`.

| Feature | Grupo | Mercados | Ventana | Fuente | Min sample | Estado | Riesgo/bloqueo |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| `away_btts_rate_l10` | recent_form | BTTS | L10 | history | 10 | available | histórico |
| `away_btts_rate_l5` | recent_form | BTTS | L5 | history | 5 | available | histórico |
| `away_btts_streak_capped_l10` | temporal_context | BTTS | L10 | history | 1 | planned | censura |
| `away_clean_sheet_rate_l10` | recent_form | BTTS, 1X2_EXPERIMENTAL | L10 | history | 10 | available | histórico |
| `away_clean_sheet_rate_l5` | recent_form | BTTS, 1X2_EXPERIMENTAL | L5 | history | 5 | available | histórico |
| `away_clean_sheet_streak_capped_l10` | temporal_context | BTTS, 1X2_EXPERIMENTAL | L10 | history | 1 | planned | censura |
| `away_days_rest` | temporal_context | 1X2_EXPERIMENTAL | previous | history | 1 | blocked | completitud |
| `away_failed_to_score_rate_l10` | recent_form | BTTS, 1X2_EXPERIMENTAL | L10 | history | 10 | available | histórico |
| `away_failed_to_score_rate_l5` | recent_form | BTTS, 1X2_EXPERIMENTAL | L5 | history | 5 | available | histórico |
| `away_ga_mean_l10` | recent_form | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L10 | history | 10 | available | histórico |
| `away_ga_mean_l5` | recent_form | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L5 | history | 5 | available | histórico |
| `away_gf_mean_l10` | recent_form | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L10 | history | 10 | available | histórico |
| `away_gf_mean_l5` | recent_form | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L5 | history | 5 | available | histórico |
| `away_goals_per_xg_l10` | xg | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L10 | xg, history | 10 | blocked | xG as-of |
| `away_goals_per_xg_l5` | xg | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L5 | xg, history | 5 | blocked | xG as-of |
| `away_matches_last_14_days` | temporal_context | 1X2_EXPERIMENTAL | D14 | history | 0 | blocked | completitud |
| `away_over_1_5_rate_l10` | recent_form | OVER_1_5 | L10 | history | 10 | available | histórico |
| `away_over_1_5_rate_l5` | recent_form | OVER_1_5 | L5 | history | 5 | available | histórico |
| `away_over_2_5_rate_l10` | recent_form | OVER_2_5 | L10 | history | 10 | available | histórico |
| `away_over_2_5_rate_l5` | recent_form | OVER_2_5 | L5 | history | 5 | available | histórico |
| `away_over_3_5_rate_l10` | recent_form | OVER_3_5 | L10 | history | 10 | available | histórico |
| `away_over_3_5_rate_l5` | recent_form | OVER_3_5 | L5 | history | 5 | available | histórico |
| `away_sample_count_l10` | sample_quality | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L10 | history | 0 | available | histórico |
| `away_sample_count_l5` | sample_quality | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L5 | history | 0 | available | histórico |
| `away_scoring_streak_capped_l10` | temporal_context | BTTS, OVER_1_5 | L10 | history | 1 | planned | censura |
| `away_standing_points_per_game` | strength | 1X2_EXPERIMENTAL | as_of_target | standings | 1 | blocked | tabla as-of |
| `away_standing_position` | strength | 1X2_EXPERIMENTAL | as_of_target | standings | 1 | blocked | tabla as-of |
| `away_venue_btts_rate_l10` | venue_form | BTTS | away_L10 | history | 10 | available | histórico |
| `away_venue_btts_rate_l5` | venue_form | BTTS | away_L5 | history | 5 | available | histórico |
| `away_venue_clean_sheet_rate_l10` | venue_form | BTTS, 1X2_EXPERIMENTAL | away_L10 | history | 10 | available | histórico |
| `away_venue_clean_sheet_rate_l5` | venue_form | BTTS, 1X2_EXPERIMENTAL | away_L5 | history | 5 | available | histórico |
| `away_venue_failed_to_score_rate_l10` | venue_form | BTTS, 1X2_EXPERIMENTAL | away_L10 | history | 10 | available | histórico |
| `away_venue_failed_to_score_rate_l5` | venue_form | BTTS, 1X2_EXPERIMENTAL | away_L5 | history | 5 | available | histórico |
| `away_venue_ga_mean_l10` | venue_form | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | away_L10 | history | 10 | available | histórico |
| `away_venue_ga_mean_l5` | venue_form | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | away_L5 | history | 5 | available | histórico |
| `away_venue_gf_mean_l10` | venue_form | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | away_L10 | history | 10 | available | histórico |
| `away_venue_gf_mean_l5` | venue_form | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | away_L5 | history | 5 | available | histórico |
| `away_venue_over_1_5_rate_l10` | venue_form | OVER_1_5 | away_L10 | history | 10 | available | histórico |
| `away_venue_over_1_5_rate_l5` | venue_form | OVER_1_5 | away_L5 | history | 5 | available | histórico |
| `away_venue_over_2_5_rate_l10` | venue_form | OVER_2_5 | away_L10 | history | 10 | available | histórico |
| `away_venue_over_2_5_rate_l5` | venue_form | OVER_2_5 | away_L5 | history | 5 | available | histórico |
| `away_venue_over_3_5_rate_l10` | venue_form | OVER_3_5 | away_L10 | history | 10 | available | histórico |
| `away_venue_over_3_5_rate_l5` | venue_form | OVER_3_5 | away_L5 | history | 5 | available | histórico |
| `away_venue_sample_count_l10` | sample_quality | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | away_L10 | history | 0 | available | histórico |
| `away_venue_sample_count_l5` | sample_quality | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | away_L5 | history | 0 | available | histórico |
| `away_xg_mean_l10` | xg | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L10 | xg, history | 10 | blocked | xG as-of |
| `away_xg_mean_l5` | xg | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L5 | xg, history | 5 | blocked | xG as-of |
| `away_xg_sample_count_l10` | xg | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L10 | xg, history | 0 | blocked | xG as-of |
| `away_xg_sample_count_l5` | xg | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L5 | xg, history | 0 | blocked | xG as-of |
| `away_xga_mean_l10` | xg | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L10 | xg, history | 10 | blocked | xG as-of |
| `away_xga_mean_l5` | xg | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L5 | xg, history | 5 | blocked | xG as-of |
| `bilateral_xg_available_l10` | xg | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L10 | xg, history | 0 | blocked | xG as-of |
| `bilateral_xg_available_l5` | xg | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L5 | xg, history | 0 | blocked | xG as-of |
| `h2h_btts_rate_h10` | h2h_auxiliary | BTTS | H10 | history | 3 | available | histórico |
| `h2h_btts_rate_h5` | h2h_auxiliary | BTTS | H5 | history | 3 | available | histórico |
| `h2h_home_ga_mean_h10` | h2h_auxiliary | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | H10 | history | 3 | available | histórico |
| `h2h_home_ga_mean_h5` | h2h_auxiliary | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | H5 | history | 3 | available | histórico |
| `h2h_home_gf_mean_h10` | h2h_auxiliary | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | H10 | history | 3 | available | histórico |
| `h2h_home_gf_mean_h5` | h2h_auxiliary | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | H5 | history | 3 | available | histórico |
| `h2h_over_1_5_rate_h10` | h2h_auxiliary | OVER_1_5 | H10 | history | 3 | available | histórico |
| `h2h_over_1_5_rate_h5` | h2h_auxiliary | OVER_1_5 | H5 | history | 3 | available | histórico |
| `h2h_over_2_5_rate_h10` | h2h_auxiliary | OVER_2_5 | H10 | history | 3 | available | histórico |
| `h2h_over_2_5_rate_h5` | h2h_auxiliary | OVER_2_5 | H5 | history | 3 | available | histórico |
| `h2h_over_3_5_rate_h10` | h2h_auxiliary | OVER_3_5 | H10 | history | 3 | available | histórico |
| `h2h_over_3_5_rate_h5` | h2h_auxiliary | OVER_3_5 | H5 | history | 3 | available | histórico |
| `h2h_sample_count_h10` | h2h_auxiliary | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | H10 | history | 0 | available | histórico |
| `h2h_sample_count_h5` | h2h_auxiliary | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | H5 | history | 0 | available | histórico |
| `home_btts_rate_l10` | recent_form | BTTS | L10 | history | 10 | available | histórico |
| `home_btts_rate_l5` | recent_form | BTTS | L5 | history | 5 | available | histórico |
| `home_btts_streak_capped_l10` | temporal_context | BTTS | L10 | history | 1 | planned | censura |
| `home_clean_sheet_rate_l10` | recent_form | BTTS, 1X2_EXPERIMENTAL | L10 | history | 10 | available | histórico |
| `home_clean_sheet_rate_l5` | recent_form | BTTS, 1X2_EXPERIMENTAL | L5 | history | 5 | available | histórico |
| `home_clean_sheet_streak_capped_l10` | temporal_context | BTTS, 1X2_EXPERIMENTAL | L10 | history | 1 | planned | censura |
| `home_days_rest` | temporal_context | 1X2_EXPERIMENTAL | previous | history | 1 | blocked | completitud |
| `home_failed_to_score_rate_l10` | recent_form | BTTS, 1X2_EXPERIMENTAL | L10 | history | 10 | available | histórico |
| `home_failed_to_score_rate_l5` | recent_form | BTTS, 1X2_EXPERIMENTAL | L5 | history | 5 | available | histórico |
| `home_ga_mean_l10` | recent_form | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L10 | history | 10 | available | histórico |
| `home_ga_mean_l5` | recent_form | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L5 | history | 5 | available | histórico |
| `home_gf_mean_l10` | recent_form | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L10 | history | 10 | available | histórico |
| `home_gf_mean_l5` | recent_form | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L5 | history | 5 | available | histórico |
| `home_goals_per_xg_l10` | xg | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L10 | xg, history | 10 | blocked | xG as-of |
| `home_goals_per_xg_l5` | xg | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L5 | xg, history | 5 | blocked | xG as-of |
| `home_matches_last_14_days` | temporal_context | 1X2_EXPERIMENTAL | D14 | history | 0 | blocked | completitud |
| `home_over_1_5_rate_l10` | recent_form | OVER_1_5 | L10 | history | 10 | available | histórico |
| `home_over_1_5_rate_l5` | recent_form | OVER_1_5 | L5 | history | 5 | available | histórico |
| `home_over_2_5_rate_l10` | recent_form | OVER_2_5 | L10 | history | 10 | available | histórico |
| `home_over_2_5_rate_l5` | recent_form | OVER_2_5 | L5 | history | 5 | available | histórico |
| `home_over_3_5_rate_l10` | recent_form | OVER_3_5 | L10 | history | 10 | available | histórico |
| `home_over_3_5_rate_l5` | recent_form | OVER_3_5 | L5 | history | 5 | available | histórico |
| `home_sample_count_l10` | sample_quality | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L10 | history | 0 | available | histórico |
| `home_sample_count_l5` | sample_quality | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L5 | history | 0 | available | histórico |
| `home_scoring_streak_capped_l10` | temporal_context | BTTS, OVER_1_5 | L10 | history | 1 | planned | censura |
| `home_standing_points_per_game` | strength | 1X2_EXPERIMENTAL | as_of_target | standings | 1 | blocked | tabla as-of |
| `home_standing_position` | strength | 1X2_EXPERIMENTAL | as_of_target | standings | 1 | blocked | tabla as-of |
| `home_venue_btts_rate_l10` | venue_form | BTTS | home_L10 | history | 10 | available | histórico |
| `home_venue_btts_rate_l5` | venue_form | BTTS | home_L5 | history | 5 | available | histórico |
| `home_venue_clean_sheet_rate_l10` | venue_form | BTTS, 1X2_EXPERIMENTAL | home_L10 | history | 10 | available | histórico |
| `home_venue_clean_sheet_rate_l5` | venue_form | BTTS, 1X2_EXPERIMENTAL | home_L5 | history | 5 | available | histórico |
| `home_venue_failed_to_score_rate_l10` | venue_form | BTTS, 1X2_EXPERIMENTAL | home_L10 | history | 10 | available | histórico |
| `home_venue_failed_to_score_rate_l5` | venue_form | BTTS, 1X2_EXPERIMENTAL | home_L5 | history | 5 | available | histórico |
| `home_venue_ga_mean_l10` | venue_form | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | home_L10 | history | 10 | available | histórico |
| `home_venue_ga_mean_l5` | venue_form | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | home_L5 | history | 5 | available | histórico |
| `home_venue_gf_mean_l10` | venue_form | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | home_L10 | history | 10 | available | histórico |
| `home_venue_gf_mean_l5` | venue_form | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | home_L5 | history | 5 | available | histórico |
| `home_venue_over_1_5_rate_l10` | venue_form | OVER_1_5 | home_L10 | history | 10 | available | histórico |
| `home_venue_over_1_5_rate_l5` | venue_form | OVER_1_5 | home_L5 | history | 5 | available | histórico |
| `home_venue_over_2_5_rate_l10` | venue_form | OVER_2_5 | home_L10 | history | 10 | available | histórico |
| `home_venue_over_2_5_rate_l5` | venue_form | OVER_2_5 | home_L5 | history | 5 | available | histórico |
| `home_venue_over_3_5_rate_l10` | venue_form | OVER_3_5 | home_L10 | history | 10 | available | histórico |
| `home_venue_over_3_5_rate_l5` | venue_form | OVER_3_5 | home_L5 | history | 5 | available | histórico |
| `home_venue_sample_count_l10` | sample_quality | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | home_L10 | history | 0 | available | histórico |
| `home_venue_sample_count_l5` | sample_quality | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | home_L5 | history | 0 | available | histórico |
| `home_xg_mean_l10` | xg | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L10 | xg, history | 10 | blocked | xG as-of |
| `home_xg_mean_l5` | xg | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L5 | xg, history | 5 | blocked | xG as-of |
| `home_xg_sample_count_l10` | xg | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L10 | xg, history | 0 | blocked | xG as-of |
| `home_xg_sample_count_l5` | xg | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L5 | xg, history | 0 | blocked | xG as-of |
| `home_xga_mean_l10` | xg | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L10 | xg, history | 10 | blocked | xG as-of |
| `home_xga_mean_l5` | xg | BTTS, OVER_1_5, OVER_2_5, OVER_3_5, 1X2_EXPERIMENTAL | L5 | xg, history | 5 | blocked | xG as-of |

## Validación de entrega

`python -m compileall -q v3 tests` correcto;
`python -m pytest -q tests/v3`: **242 tests pasan** (130 del catálogo/auditoría).
Los tests cubren contrato por feature, unicidad, orden/JSON estable entre procesos
con hash seeds distintos, mercados, fuentes prohibidas, ventanas, min sample,
inmutabilidad/filtros, exclusiones temporales y lectura sin modificación.
Dos ejecuciones completas de la auditoría real producen JSON idéntico.
Inventario Markdown contrastado con los 118 nombres canónicos.

Comparación SHA-256 y mtime antes/después de 67,456 archivos de `data/`,
`scraper/`, `analysis/` y backup operativo: cero cambios, adiciones o eliminaciones.
BT0 / `J_BT_sin_temporada` permanece intacto. `git diff --check` limpio.
Todo queda en el working tree de `feature/2.1-feature-catalog`, sin staging,
commit ni push; no se versionan salidas de auditoría ni artefactos bajo `data/`.
