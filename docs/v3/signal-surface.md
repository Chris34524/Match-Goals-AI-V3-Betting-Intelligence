# Roadmap 2.1A — Superficie de señales

Fuente de verdad: [Issue #11](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/11).
Auditoría realizada el 2026-10-26, exclusivamente en
`feature/2.1a-flashscore-signal-surface`. Fase declarativa: sin extractores,
entrenamiento, requests nuevos de scraping ni cambios al pipeline operativo.

## Uso y unidad de conteo

```python
from v3.features.surface_catalog import get_surface_catalog, surface_catalog_json, surface_summary
get_surface_catalog(level="player", priority="P1", market="PLAYER_PROPS_FUTURE")
get_surface_catalog(level="lineup", status="planned")
```

```bash
python -m v3.features.surface_catalog > /tmp/signal-surface.json
python -m v3.features.surface_audit --source-root data/matches > /tmp/matches-audit.json
python -m v3.features.surface_audit --source-root data > /tmp/full-surface-audit.json
python -m v3.features.audit --source-root data/matches > /tmp/temporal-audit.json
```

Las redirecciones deben apuntar fuera de `data/`. El auditor sólo lee y emite
stdout: no acepta ruta de escritura y no tiene capacidades de red.

Cada entrada es una señal candidata con nombre único. Se conservan las 118
columnas del catálogo 2.1 y se añaden señales sin expandir cada lado/ventana.
Por tanto el total NO es una cantidad de columnas ya implementadas ni de
conceptos estadísticos independientes: algunas definiciones derivadas se
solapan con columnas 2.1. `family` agrupa entradas; `level` es exclusivo y
`markets` admite múltiples candidatos. No se cambiaron la API ni el contrato 2.1.

`surface_availability` describe evidencia: `observed_local`, `visible_public`,
`competition_dependent`, `unknown`. `capture_policy` describe adquisición:
`existing_local`, `manual_or_permitted_source`, `requires_authorization`, `blocked`.
Son dimensiones independientes. `manual_or_permitted_source` es un requisito de
ruta futura, no una licencia existente. `existing_local` permite auditar lo que
ya existe, sin autorizar recaptura ni acreditar derechos de explotación.
`status=available` preserva candidatos 2.1 con contrato temporal conocido; no
significa extracción implementada. Todas las entradas tienen `automatable=false`
en esta fase. El contrato rechaza automatización de entradas sin autorización
o bloqueadas y prohíbe fuentes de evaluación/modelos.

P0: valor alto, raw local y contrato de leakage controlable; P1: valor alto con
adquisición permitida/autorizada o acreditación as-of pendiente; P2: experimental
/contextual; P3: cobertura baja, ruido o leakage elevado. Las instantáneas de
texto sin fecha acreditada no se elevan a P0. La prioridad no elimina bloqueos.

## Cobertura local y hallazgos

Se inspeccionaron recursivamente **67.219 archivos** bajo `data/`, sin lista
cerrada de nombres. `data/matches` contiene **4.344 directorios**, **36.786
archivos** y **10 tipos de JSON**, todos parseables con claves únicas y sin NaN.
El reporte [surface-audit.json](surface-audit.json) conserva los nombres de
artefactos, conteos, bytes, claves principales, unión completa de rutas/tipos,
cobertura por archivo y un ejemplo de estructura sin valores escalares. Incluye
archivos desconocidos, formatos no JSON y artefactos externos a matches; no copia
artículos ni commentary. Los formatos no JSON se inventarían y hashean; las
instantáneas de texto relevantes se revisaron adicionalmente de forma manual.

| Artefacto en matches | Archivos / 4.344 | Evidencia / uso permitido en esta fase |
| --- | ---: | --- |
| history.json | 4.337 | Identidad/fecha/equipos, secciones de forma/H2H, scores y textos raw |
| xg_history.json | 4.230 | xG local/visitante y xGF/xGA por muestra; agregados L5/L10 |
| standings.json | 4.342 | 2.553 con filas de clasificación; otros vacíos/omitidos/no disponibles |
| enriched.json | 4.227 | Agregados derivados, inspección solamente |
| h2h_analysis.json | 4.215 | H5/H10/H20/ponderados y muestras; no reemplaza raw history |
| lambda_comparison.json | 4.195 | Outputs del modelo: inventario solamente |
| result.json | 4.097 | Análisis/predicciones, no resultado final acreditado |
| confidence.json | 3.226 | Outputs de confianza: inventario solamente |
| confidence_v2.json | 3.233 | Outputs de confianza/validación: inventario solamente |
| backtest.json | 684 | Labels/evaluación BT0: inventario solamente |

Fuera de matches, `data/xg_cache` aporta **28.933 JSON**: **9.167** contienen
xG numérico en ambos lados y 19.766 lo tienen nulo. No se suman como muestras
independientes a xg_history: pueden ser copias del mismo encuentro.
También existen `history_raw.json`, fixtures `partidos*.json`, `standings.json`,
HTML/TXT de H2H, partidos y clasificación, logs y outputs de experimentos,
evaluación y snapshots. Sólo raw explícitamente identificado es candidato;
outputs, labels, backtest_pool y Champion nunca son fuentes del catálogo.

La revisión de `data/match_detail.txt` y `data/standings_page.txt` acredita
**valores parciales** de XI esperados, nombres/dorsales, ratings de competición
por jugador y promedios de equipo, bajas por lesión y tarjeta roja, cuotas 1X2
por bookmaker, entrenadores, árbitro, estadio y capacidad. Hay encabezados de
valor de mercado/edad/altura, pero no se acreditaron valores de esos campos.
No confundir el dorsal con player_id, un promedio de competición con rating del
partido, una baja por tarjeta con un ledger de sanciones cumplidas ni un tab de
alineaciones con un XI oficial. Las páginas carecen de available_at acreditado
y no certifican formación, minutos ni estadísticas individuales detalladas.
Son `observed_local/existing_local`, con requisitos pendientes; no un corpus
para NLP ni una fuente lista para modelado. No se reproduce su artículo.

No se encontraron eventos cronológicos, IDs estables de jugador, alineaciones
oficiales, minutos/load, corners/cards de partido ni player stats detalladas en
las claves JSON auditadas de matches. Esto no prueba ausencia de menciones en
texto libre/HTML; la evidencia en snapshots se distingue arriba. Lesiones,
ratings promedio y XI esperados sí tienen evidencia textual parcial.

El [reporte temporal](surface-temporal-audit.json) acredita presencia de al menos
L5 bilateral en 4.028 carpetas y L10 en 3.902; no certifica elegibilidad de cada
fila ni ausencia de otras muestras rechazadas. Hay 32.703 pares xGF/xGA raw
(incluidas repeticiones), 1.981 carpetas con algún par numérico en ambos equipos.
Los controles encontraron target en inputs (3.317), mismo día sin hora acreditada
(3.319), futuros (5.692), conflictos de equipo (1.089), identidad desconocida
(118) y scores inválidos/no parseados (72). Los contadores corresponden a
apariciones inspeccionadas, no a IDs únicos ni a filas finales.

## Superficie pública documentada y adquisición

La documentación primaria consultada acredita categorías de estadísticas de
equipo/jugador y alineaciones, con cobertura variable. Cada entrada declara
referencias; una referencia a Issue #11 es alcance solicitado, no verificación
independiente de un campo. Las señales derivadas son propuestas V3, no supuestos
campos nativos de Flashscore. Los campos sin prueba suficiente quedan `unknown`.
No se consultaron endpoints de partidos ni APIs privadas.

- [terms](https://www.flashscore.com/terms-of-use/)
- [team](https://www.flashscore.com/news/more-data-to-help-you-read-the-game-flashscore-s-football-stats-get-a-facelift/42Kj2YYI/)
- [team_expansion](https://www.flashscore.com/news/football-even-more-in-depth-flashscore-expands-match-statistics/6yne1Z8e/)
- [player](https://www.flashscoreusa.com/news/players-under-the-magnifying-glass-a-look-at-players-detailed-statistics/8pvZSJ6U/)
- [lineup](https://www.flashscore.com/news/soccer-premier-league-pre-match-football-content-boost-flashscore-introduces-predicted-lineups/fw2Jv6j5/)
- [ratings](https://www.flashscore.in/faq/data/)
- [scope](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/11)

Los términos del sitio, sección 2.9–2.10, exigen consentimiento expreso para
extracción/reutilización y scraping y restringen requests automatizados. La
visibilidad de stats, ratings, alineaciones, bajas y cuotas no autoriza su
captura nueva. Se requiere autorización expresa o fuente alternativa permitida/
licenciada y una revisión del alcance de esa autorización. No se propone bypass,
captcha solving, evasión de rate limits, extracción agresiva ni APIs privadas.

## Gaps y contrato temporal

- xG y standings existen, pero faltan linaje as-of, revisiones, orientación y
  adaptadores acreditados. Conservan bloqueos de 2.1; no se usan sus agregados
  sin reconstruir las muestras pertinentes.
- Player stats/rating del partido, minutos, IDs estables, XI oficiales y formación
  necesitan adquisición permitida, resolución de entidades y cobertura por liga.
  Los TXT son evidencia aislada sin historial temporal verificable.
- Lesión, enfermedad, suspensión y not-in-squad son categorías separadas. La
  ausencia de una entrada no significa jugador disponible. Se exige fuente,
  fecha de publicación, vigencia y correcciones; no se infiere diagnóstico.
- Carga requiere ledger completo de fixtures/minutos; las historias truncadas no
  acreditan descanso ni congestión. Diferenciar reglamentario, prórroga y penales.
- Disciplina por estado/minuto, remontadas y pérdidas de ventaja requieren eventos
  completos ordenados, anulaciones y score estrictamente anterior al evento.
  Riesgo de suspensión requiere reglas de temporada, resets, apelaciones y ledger.
- Cuotas requieren mercado/línea/bookmaker y snapshots legales con timestamp.
  Opening/current/closing no se intercambian; closing posterior al corte queda
  excluido. Props requieren además jugador resuelto, minutos/rol y odds suficientes.
- Stakes/points-to-threshold necesitan tabla histórica y reglas acreditadas.
  Cambios de técnico/transferencias requieren confirmación estructurada y fecha.
  Sentiment se reserva como fase futura sobre texto permitido/licenciado; nunca
  representa emociones privadas ni autoriza copiar artículos/commentary.
- Se conserva null con razón, denominador y tamaño de muestra. No se imputa cero
  por ausencia, omisión visual o falta de cobertura; ni se reconstruye el pasado
  con perfiles o noticias actuales. Fecha del evento, fecha de captura y fecha de
  publicación son conceptos distintos. En scores históricos sólo aplica la
  excepción documentada de resolución diaria de 2.1.

## Resumen reproducible

```json
{
  "capture_policy": {
    "existing_local": 148,
    "manual_or_permitted_source": 25,
    "requires_authorization": 116
  },
  "families": 17,
  "family": {
    "availability_lineup": 19,
    "base_h2h_auxiliary": 14,
    "base_recent_form": 32,
    "base_sample_quality": 8,
    "base_strength": 4,
    "base_temporal_context": 10,
    "base_venue_form": 32,
    "base_xg": 18,
    "discipline": 12,
    "fixture_metadata": 9,
    "news_context": 4,
    "observable_context": 29,
    "odds_market": 11,
    "player_performance": 33,
    "player_profile": 11,
    "standings_snapshot": 9,
    "team_match_stats": 34
  },
  "level": {
    "context": 39,
    "discipline": 12,
    "lineup": 19,
    "match": 36,
    "news": 4,
    "player": 44,
    "team": 135
  },
  "priority": {
    "P0": 77,
    "P1": 147,
    "P2": 56,
    "P3": 9
  },
  "signals": 289,
  "status": {
    "available": 86,
    "blocked": 35,
    "planned": 168
  },
  "surface_availability": {
    "competition_dependent": 102,
    "observed_local": 148,
    "unknown": 36,
    "visible_public": 3
  }
}
```

## Índice completo

Los campos completos (descripción, mercados, fuentes, requisito temporal, missing,
leakage, estado y habilitación) se obtienen con `surface_catalog_json()`.
Este índice muestra todas las entradas; no implica cobertura universal.

| Señal | Familia | Nivel | Prioridad | Superficie | Captura | Estado |
| --- | --- | --- | --- | --- | --- | --- |
| away_btts_rate_l10 | base_recent_form | team | P0 | observed_local | existing_local | available |
| away_btts_rate_l5 | base_recent_form | team | P0 | observed_local | existing_local | available |
| away_btts_streak_capped_l10 | base_temporal_context | context | P2 | observed_local | existing_local | planned |
| away_clean_sheet_rate_l10 | base_recent_form | team | P0 | observed_local | existing_local | available |
| away_clean_sheet_rate_l5 | base_recent_form | team | P0 | observed_local | existing_local | available |
| away_clean_sheet_streak_capped_l10 | base_temporal_context | context | P2 | observed_local | existing_local | planned |
| away_days_rest | base_temporal_context | context | P2 | observed_local | existing_local | blocked |
| away_failed_to_score_rate_l10 | base_recent_form | team | P0 | observed_local | existing_local | available |
| away_failed_to_score_rate_l5 | base_recent_form | team | P0 | observed_local | existing_local | available |
| away_ga_mean_l10 | base_recent_form | team | P0 | observed_local | existing_local | available |
| away_ga_mean_l5 | base_recent_form | team | P0 | observed_local | existing_local | available |
| away_gf_mean_l10 | base_recent_form | team | P0 | observed_local | existing_local | available |
| away_gf_mean_l5 | base_recent_form | team | P0 | observed_local | existing_local | available |
| away_goals_per_xg_l10 | base_xg | team | P1 | observed_local | existing_local | blocked |
| away_goals_per_xg_l5 | base_xg | team | P1 | observed_local | existing_local | blocked |
| away_matches_last_14_days | base_temporal_context | context | P2 | observed_local | existing_local | blocked |
| away_over_1_5_rate_l10 | base_recent_form | team | P0 | observed_local | existing_local | available |
| away_over_1_5_rate_l5 | base_recent_form | team | P0 | observed_local | existing_local | available |
| away_over_2_5_rate_l10 | base_recent_form | team | P0 | observed_local | existing_local | available |
| away_over_2_5_rate_l5 | base_recent_form | team | P0 | observed_local | existing_local | available |
| away_over_3_5_rate_l10 | base_recent_form | team | P0 | observed_local | existing_local | available |
| away_over_3_5_rate_l5 | base_recent_form | team | P0 | observed_local | existing_local | available |
| away_sample_count_l10 | base_sample_quality | team | P0 | observed_local | existing_local | available |
| away_sample_count_l5 | base_sample_quality | team | P0 | observed_local | existing_local | available |
| away_scoring_streak_capped_l10 | base_temporal_context | context | P2 | observed_local | existing_local | planned |
| away_standing_points_per_game | base_strength | team | P1 | observed_local | existing_local | blocked |
| away_standing_position | base_strength | team | P1 | observed_local | existing_local | blocked |
| away_venue_btts_rate_l10 | base_venue_form | team | P0 | observed_local | existing_local | available |
| away_venue_btts_rate_l5 | base_venue_form | team | P0 | observed_local | existing_local | available |
| away_venue_clean_sheet_rate_l10 | base_venue_form | team | P0 | observed_local | existing_local | available |
| away_venue_clean_sheet_rate_l5 | base_venue_form | team | P0 | observed_local | existing_local | available |
| away_venue_failed_to_score_rate_l10 | base_venue_form | team | P0 | observed_local | existing_local | available |
| away_venue_failed_to_score_rate_l5 | base_venue_form | team | P0 | observed_local | existing_local | available |
| away_venue_ga_mean_l10 | base_venue_form | team | P0 | observed_local | existing_local | available |
| away_venue_ga_mean_l5 | base_venue_form | team | P0 | observed_local | existing_local | available |
| away_venue_gf_mean_l10 | base_venue_form | team | P0 | observed_local | existing_local | available |
| away_venue_gf_mean_l5 | base_venue_form | team | P0 | observed_local | existing_local | available |
| away_venue_over_1_5_rate_l10 | base_venue_form | team | P0 | observed_local | existing_local | available |
| away_venue_over_1_5_rate_l5 | base_venue_form | team | P0 | observed_local | existing_local | available |
| away_venue_over_2_5_rate_l10 | base_venue_form | team | P0 | observed_local | existing_local | available |
| away_venue_over_2_5_rate_l5 | base_venue_form | team | P0 | observed_local | existing_local | available |
| away_venue_over_3_5_rate_l10 | base_venue_form | team | P0 | observed_local | existing_local | available |
| away_venue_over_3_5_rate_l5 | base_venue_form | team | P0 | observed_local | existing_local | available |
| away_venue_sample_count_l10 | base_sample_quality | team | P0 | observed_local | existing_local | available |
| away_venue_sample_count_l5 | base_sample_quality | team | P0 | observed_local | existing_local | available |
| away_xg_mean_l10 | base_xg | team | P1 | observed_local | existing_local | blocked |
| away_xg_mean_l5 | base_xg | team | P1 | observed_local | existing_local | blocked |
| away_xg_sample_count_l10 | base_xg | team | P1 | observed_local | existing_local | blocked |
| away_xg_sample_count_l5 | base_xg | team | P1 | observed_local | existing_local | blocked |
| away_xga_mean_l10 | base_xg | team | P1 | observed_local | existing_local | blocked |
| away_xga_mean_l5 | base_xg | team | P1 | observed_local | existing_local | blocked |
| bilateral_xg_available_l10 | base_xg | match | P1 | observed_local | existing_local | blocked |
| bilateral_xg_available_l5 | base_xg | match | P1 | observed_local | existing_local | blocked |
| context_attendance_capacity | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_collapse_frequency | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_comeback_frequency | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_derby_rivalry | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_final_stage | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_first_matches_new_coach | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_fixture_congestion | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_key_player_absence | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_key_player_return | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_knockout_stage | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_lineup_surprise | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_manager_change | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_match_momentum | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_points_to_threshold | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_qualification_stakes | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_recent_red_card_burden | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_referee_assignment | observable_context | context | P2 | observed_local | existing_local | planned |
| context_relegation_stakes | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_rest_days | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_rotation_intensity | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_scoring_streak | observable_context | context | P2 | observed_local | existing_local | planned |
| context_title_stakes | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_transfer_disruption | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_transfer_negotiations | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_travel_distance | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_venue_home_advantage | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_weather_conditions | observable_context | context | P2 | unknown | manual_or_permitted_source | planned |
| context_winless_streak | observable_context | context | P2 | observed_local | existing_local | planned |
| context_winning_streak | observable_context | context | P2 | observed_local | existing_local | planned |
| discipline_cards_by_match_state | discipline | discipline | P2 | competition_dependent | requires_authorization | planned |
| discipline_cards_under_score_pressure | discipline | discipline | P2 | competition_dependent | requires_authorization | planned |
| discipline_fouls | discipline | discipline | P1 | competition_dependent | requires_authorization | planned |
| discipline_late_cards | discipline | discipline | P2 | competition_dependent | requires_authorization | planned |
| discipline_player_card_rates | discipline | discipline | P1 | competition_dependent | requires_authorization | planned |
| discipline_player_red_cards | discipline | discipline | P1 | competition_dependent | requires_authorization | planned |
| discipline_player_yellow_cards | discipline | discipline | P1 | competition_dependent | requires_authorization | planned |
| discipline_red_card_history | discipline | discipline | P1 | competition_dependent | requires_authorization | planned |
| discipline_suspension_risk | discipline | discipline | P1 | competition_dependent | requires_authorization | planned |
| discipline_team_card_rates | discipline | discipline | P1 | competition_dependent | requires_authorization | planned |
| discipline_team_red_cards | discipline | discipline | P1 | competition_dependent | requires_authorization | planned |
| discipline_team_yellow_cards | discipline | discipline | P1 | competition_dependent | requires_authorization | planned |
| h2h_btts_rate_h10 | base_h2h_auxiliary | match | P2 | observed_local | existing_local | available |
| h2h_btts_rate_h5 | base_h2h_auxiliary | match | P2 | observed_local | existing_local | available |
| h2h_home_ga_mean_h10 | base_h2h_auxiliary | match | P2 | observed_local | existing_local | available |
| h2h_home_ga_mean_h5 | base_h2h_auxiliary | match | P2 | observed_local | existing_local | available |
| h2h_home_gf_mean_h10 | base_h2h_auxiliary | match | P2 | observed_local | existing_local | available |
| h2h_home_gf_mean_h5 | base_h2h_auxiliary | match | P2 | observed_local | existing_local | available |
| h2h_over_1_5_rate_h10 | base_h2h_auxiliary | match | P2 | observed_local | existing_local | available |
| h2h_over_1_5_rate_h5 | base_h2h_auxiliary | match | P2 | observed_local | existing_local | available |
| h2h_over_2_5_rate_h10 | base_h2h_auxiliary | match | P2 | observed_local | existing_local | available |
| h2h_over_2_5_rate_h5 | base_h2h_auxiliary | match | P2 | observed_local | existing_local | available |
| h2h_over_3_5_rate_h10 | base_h2h_auxiliary | match | P2 | observed_local | existing_local | available |
| h2h_over_3_5_rate_h5 | base_h2h_auxiliary | match | P2 | observed_local | existing_local | available |
| h2h_sample_count_h10 | base_h2h_auxiliary | match | P2 | observed_local | existing_local | available |
| h2h_sample_count_h5 | base_h2h_auxiliary | match | P2 | observed_local | existing_local | available |
| home_btts_rate_l10 | base_recent_form | team | P0 | observed_local | existing_local | available |
| home_btts_rate_l5 | base_recent_form | team | P0 | observed_local | existing_local | available |
| home_btts_streak_capped_l10 | base_temporal_context | context | P2 | observed_local | existing_local | planned |
| home_clean_sheet_rate_l10 | base_recent_form | team | P0 | observed_local | existing_local | available |
| home_clean_sheet_rate_l5 | base_recent_form | team | P0 | observed_local | existing_local | available |
| home_clean_sheet_streak_capped_l10 | base_temporal_context | context | P2 | observed_local | existing_local | planned |
| home_days_rest | base_temporal_context | context | P2 | observed_local | existing_local | blocked |
| home_failed_to_score_rate_l10 | base_recent_form | team | P0 | observed_local | existing_local | available |
| home_failed_to_score_rate_l5 | base_recent_form | team | P0 | observed_local | existing_local | available |
| home_ga_mean_l10 | base_recent_form | team | P0 | observed_local | existing_local | available |
| home_ga_mean_l5 | base_recent_form | team | P0 | observed_local | existing_local | available |
| home_gf_mean_l10 | base_recent_form | team | P0 | observed_local | existing_local | available |
| home_gf_mean_l5 | base_recent_form | team | P0 | observed_local | existing_local | available |
| home_goals_per_xg_l10 | base_xg | team | P1 | observed_local | existing_local | blocked |
| home_goals_per_xg_l5 | base_xg | team | P1 | observed_local | existing_local | blocked |
| home_matches_last_14_days | base_temporal_context | context | P2 | observed_local | existing_local | blocked |
| home_over_1_5_rate_l10 | base_recent_form | team | P0 | observed_local | existing_local | available |
| home_over_1_5_rate_l5 | base_recent_form | team | P0 | observed_local | existing_local | available |
| home_over_2_5_rate_l10 | base_recent_form | team | P0 | observed_local | existing_local | available |
| home_over_2_5_rate_l5 | base_recent_form | team | P0 | observed_local | existing_local | available |
| home_over_3_5_rate_l10 | base_recent_form | team | P0 | observed_local | existing_local | available |
| home_over_3_5_rate_l5 | base_recent_form | team | P0 | observed_local | existing_local | available |
| home_sample_count_l10 | base_sample_quality | team | P0 | observed_local | existing_local | available |
| home_sample_count_l5 | base_sample_quality | team | P0 | observed_local | existing_local | available |
| home_scoring_streak_capped_l10 | base_temporal_context | context | P2 | observed_local | existing_local | planned |
| home_standing_points_per_game | base_strength | team | P1 | observed_local | existing_local | blocked |
| home_standing_position | base_strength | team | P1 | observed_local | existing_local | blocked |
| home_venue_btts_rate_l10 | base_venue_form | team | P0 | observed_local | existing_local | available |
| home_venue_btts_rate_l5 | base_venue_form | team | P0 | observed_local | existing_local | available |
| home_venue_clean_sheet_rate_l10 | base_venue_form | team | P0 | observed_local | existing_local | available |
| home_venue_clean_sheet_rate_l5 | base_venue_form | team | P0 | observed_local | existing_local | available |
| home_venue_failed_to_score_rate_l10 | base_venue_form | team | P0 | observed_local | existing_local | available |
| home_venue_failed_to_score_rate_l5 | base_venue_form | team | P0 | observed_local | existing_local | available |
| home_venue_ga_mean_l10 | base_venue_form | team | P0 | observed_local | existing_local | available |
| home_venue_ga_mean_l5 | base_venue_form | team | P0 | observed_local | existing_local | available |
| home_venue_gf_mean_l10 | base_venue_form | team | P0 | observed_local | existing_local | available |
| home_venue_gf_mean_l5 | base_venue_form | team | P0 | observed_local | existing_local | available |
| home_venue_over_1_5_rate_l10 | base_venue_form | team | P0 | observed_local | existing_local | available |
| home_venue_over_1_5_rate_l5 | base_venue_form | team | P0 | observed_local | existing_local | available |
| home_venue_over_2_5_rate_l10 | base_venue_form | team | P0 | observed_local | existing_local | available |
| home_venue_over_2_5_rate_l5 | base_venue_form | team | P0 | observed_local | existing_local | available |
| home_venue_over_3_5_rate_l10 | base_venue_form | team | P0 | observed_local | existing_local | available |
| home_venue_over_3_5_rate_l5 | base_venue_form | team | P0 | observed_local | existing_local | available |
| home_venue_sample_count_l10 | base_sample_quality | team | P0 | observed_local | existing_local | available |
| home_venue_sample_count_l5 | base_sample_quality | team | P0 | observed_local | existing_local | available |
| home_xg_mean_l10 | base_xg | team | P1 | observed_local | existing_local | blocked |
| home_xg_mean_l5 | base_xg | team | P1 | observed_local | existing_local | blocked |
| home_xg_sample_count_l10 | base_xg | team | P1 | observed_local | existing_local | blocked |
| home_xg_sample_count_l5 | base_xg | team | P1 | observed_local | existing_local | blocked |
| home_xga_mean_l10 | base_xg | team | P1 | observed_local | existing_local | blocked |
| home_xga_mean_l5 | base_xg | team | P1 | observed_local | existing_local | blocked |
| lineup_bench_status | availability_lineup | lineup | P1 | competition_dependent | requires_authorization | planned |
| lineup_bench_strength | availability_lineup | lineup | P1 | competition_dependent | requires_authorization | planned |
| lineup_card_absence | availability_lineup | lineup | P1 | observed_local | existing_local | planned |
| lineup_changes_previous_match | availability_lineup | lineup | P1 | competition_dependent | requires_authorization | planned |
| lineup_continuity | availability_lineup | lineup | P1 | competition_dependent | requires_authorization | planned |
| lineup_formation | availability_lineup | lineup | P1 | competition_dependent | requires_authorization | planned |
| lineup_illness | availability_lineup | lineup | P1 | competition_dependent | requires_authorization | planned |
| lineup_injury | availability_lineup | lineup | P1 | observed_local | existing_local | planned |
| lineup_key_player_availability | availability_lineup | lineup | P1 | competition_dependent | requires_authorization | planned |
| lineup_not_in_squad | availability_lineup | lineup | P1 | competition_dependent | requires_authorization | planned |
| lineup_official_xi | availability_lineup | lineup | P1 | competition_dependent | requires_authorization | planned |
| lineup_predicted_xi | availability_lineup | lineup | P1 | observed_local | existing_local | planned |
| lineup_return_from_injury | availability_lineup | lineup | P1 | competition_dependent | requires_authorization | planned |
| lineup_starter_status | availability_lineup | lineup | P1 | competition_dependent | requires_authorization | planned |
| lineup_starters_repeated_l3 | availability_lineup | lineup | P1 | competition_dependent | requires_authorization | planned |
| lineup_starters_repeated_l5 | availability_lineup | lineup | P1 | competition_dependent | requires_authorization | planned |
| lineup_substitute_status | availability_lineup | lineup | P1 | competition_dependent | requires_authorization | planned |
| lineup_suspension | availability_lineup | lineup | P1 | competition_dependent | requires_authorization | planned |
| lineup_transfer_out | availability_lineup | lineup | P1 | competition_dependent | requires_authorization | planned |
| match_coach_names | fixture_metadata | match | P1 | observed_local | existing_local | planned |
| match_competition | fixture_metadata | match | P0 | observed_local | existing_local | planned |
| match_fixture_status | fixture_metadata | match | P1 | observed_local | existing_local | planned |
| match_identity | fixture_metadata | match | P0 | observed_local | existing_local | planned |
| match_scheduled_date | fixture_metadata | match | P0 | observed_local | existing_local | planned |
| match_scheduled_time | fixture_metadata | match | P0 | observed_local | existing_local | planned |
| match_venue | fixture_metadata | match | P1 | observed_local | existing_local | planned |
| match_venue_capacity | fixture_metadata | match | P1 | observed_local | existing_local | planned |
| match_venue_side | fixture_metadata | match | P0 | observed_local | existing_local | planned |
| news_commentary | news_context | news | P3 | visible_public | requires_authorization | planned |
| news_context_sentiment | news_context | news | P3 | unknown | requires_authorization | planned |
| news_match_reports | news_context | news | P3 | visible_public | requires_authorization | planned |
| news_previews | news_context | news | P3 | visible_public | requires_authorization | planned |
| odds_1x2 | odds_market | match | P1 | observed_local | existing_local | planned |
| odds_bookmaker_consensus | odds_market | match | P1 | unknown | requires_authorization | planned |
| odds_bookmaker_dispersion | odds_market | match | P1 | unknown | requires_authorization | planned |
| odds_btts | odds_market | match | P1 | competition_dependent | requires_authorization | planned |
| odds_cards | odds_market | match | P1 | competition_dependent | requires_authorization | planned |
| odds_closing_snapshot | odds_market | match | P3 | unknown | requires_authorization | planned |
| odds_corners | odds_market | match | P1 | competition_dependent | requires_authorization | planned |
| odds_current_snapshot | odds_market | match | P1 | unknown | requires_authorization | planned |
| odds_opening_snapshot | odds_market | match | P1 | unknown | requires_authorization | planned |
| odds_player_props | odds_market | match | P3 | unknown | requires_authorization | planned |
| odds_totals | odds_market | match | P1 | competition_dependent | requires_authorization | planned |
| player_age | player_profile | player | P1 | competition_dependent | requires_authorization | planned |
| player_assists | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_clean_sheets | player_performance | player | P1 | unknown | requires_authorization | planned |
| player_clearances | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_contract_expiry | player_profile | player | P3 | unknown | requires_authorization | planned |
| player_crosses | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_current_club | player_profile | player | P1 | competition_dependent | requires_authorization | planned |
| player_display_name | player_profile | player | P1 | observed_local | existing_local | planned |
| player_dribbles | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_duels | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_errors_leading_goal | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_errors_leading_shot | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_fouls_committed | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_fouls_suffered | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_goals | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_goals_prevented | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_identity | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_injury_history | player_profile | player | P1 | competition_dependent | requires_authorization | planned |
| player_interceptions | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_key_passes | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_loan_status | player_profile | player | P3 | unknown | requires_authorization | planned |
| player_market_value | player_profile | player | P3 | competition_dependent | requires_authorization | planned |
| player_minutes | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_minutes_load | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_passes | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_penalty_saves | player_performance | player | P1 | unknown | requires_authorization | planned |
| player_player_of_match | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_position | player_profile | player | P1 | competition_dependent | requires_authorization | planned |
| player_rating | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_recent_goal_contribution | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_recent_minutes | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_recent_starts | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_rolling_rating | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_saves | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_season_average_rating | player_profile | player | P1 | observed_local | existing_local | planned |
| player_shirt_number | player_profile | player | P1 | observed_local | existing_local | planned |
| player_shots | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_shots_on_target | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_tackles | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_transfer_history | player_profile | player | P1 | competition_dependent | requires_authorization | planned |
| player_xa | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_xg | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_xgot | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| player_xgot_faced | player_performance | player | P1 | competition_dependent | requires_authorization | planned |
| team_accurate_passes | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_average_rating | team_match_stats | team | P1 | observed_local | existing_local | planned |
| team_big_chances | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_big_chances_missed | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_big_chances_scored | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_clearances | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_corners | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_crosses | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_duels_won | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_errors_leading_goal | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_errors_leading_shot | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_final_third_passes | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_fouls | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_free_kicks | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_goals_prevented | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_headed_goals | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_interceptions | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_long_passes | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_offsides | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_passes | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_possession | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_saves | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_shots | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_shots_blocked | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_shots_inside_box | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_shots_off_target | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_shots_on_target | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_shots_outside_box | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_table_draws | standings_snapshot | team | P1 | observed_local | existing_local | blocked |
| team_table_form | standings_snapshot | team | P1 | observed_local | existing_local | blocked |
| team_table_goal_difference | standings_snapshot | team | P1 | observed_local | existing_local | blocked |
| team_table_goals_against | standings_snapshot | team | P1 | observed_local | existing_local | blocked |
| team_table_goals_for | standings_snapshot | team | P1 | observed_local | existing_local | blocked |
| team_table_losses | standings_snapshot | team | P1 | observed_local | existing_local | blocked |
| team_table_played | standings_snapshot | team | P1 | observed_local | existing_local | blocked |
| team_table_points | standings_snapshot | team | P1 | observed_local | existing_local | blocked |
| team_table_wins | standings_snapshot | team | P1 | observed_local | existing_local | blocked |
| team_tackles | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_touches_opposition_box | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_woodwork | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_xa | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_xgot | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |
| team_xgot_faced | team_match_stats | team | P1 | competition_dependent | requires_authorization | planned |

## Validación de entrega

- `python -m compileall -q v3 tests`: correcto.
- `python -m pytest -q tests/v3`: **550 passed** (308 del módulo de superficie).
- Se prueban serialización canónica entre hash seeds, unicidad, vocabularios,
  filtros conjuntos, límites de autorización/automatización, exclusión de fuentes
  de evaluación, proxies observables, archivos desconocidos/nested, cobertura sin
  sampling, JSON inválido/duplicado/NaN, symlinks y auditoría sin writes ni red.
- SHA-256 antes/después de los **67.395 archivos** regulares de `data/`,
  `scraper/` y `analysis/`: mismo conjunto de rutas y mismos bytes. BT0 permanece
  intacto junto con sus artefactos de evaluación; no se modificó código operativo.
- `git diff --check` y comprobación adicional de whitespace en archivos nuevos:
  correctos. `git diff --stat` sólo incluye el README ya seguido por Git; los ocho
  archivos nuevos permanecen sin staging y aparecen en `git status`.
- Sin `git add`, commit, push ni merge. Las únicas rutas modificadas pertenecen a
  `v3/`, `tests/v3/` y `docs/v3/`.
