# Contrato canónico de partido V3 — Roadmap 1.1

Fuente de verdad: [Issue #1](https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/1).

Una fila lógica por `metadata.match_id`, identificador opaco de Flashscore,
sin convertirlo a número. No se crean filas por mercado, escenario o equipo.
Duplicados o identidades contradictorias requieren revisión, nunca una elección
silenciosa. `schema_version = "3.0.0"` y `feature_version = "3.0.0"`.

La definición declarativa está en `v3/data/schema.py`: sólo biblioteca estándar,
sin lectura/escritura de datos, adaptadores, validación runtime ni integración
con el pipeline. Las restricciones siguientes son normativas para futuros
consumidores; los TypedDict describen estructura, no las ejecutan. Este hito no
implementa Dataset Builder, migraciones, entrenamiento, cuotas ni recalibración.
BT0 / `J_BT_sin_temporada` continúa como Champion sin cambios.

## Estructura y valores faltantes

Todas las claves declaradas deben estar presentes. Cada valor desconocido se
representa como `None` en Python / `null` en JSON, incluso contadores y booleanos.
`0` significa cero observado y `false` ausencia comprobada; nunca sustituyen un
desconocido. No usar cadenas vacías, NaN, infinito ni fechas, temporadas, horas,
probabilidades o scores inferidos sin evidencia. Una lista vacía significa que
se revisó y no hubo elementos; una lista nullable en `null` significa desconocida.

`schema_version`, `feature_version`, `metadata.source`, `metadata.match_id` y los
contenedores estructurales son obligatorios y no nulos. Sin identidad/fuente no
se admite una fila canónica. `predictions` y `labels` pueden ser `null` completos.
No completar campos faltantes de predicción calculando nuevos valores en 1.1.

| Grupo | Campos y semántica | Origen esperado |
| --- | --- | --- |
| `metadata` | `source`, `match_id`; `date` (YYYY-MM-DD local de la fuente), `kickoff` (ISO 8601 con offset fiable), `country`, `competition`, `season`, `home_team`, `away_team` (strings nullable salvo identidad/fuente) | `data/partidos.json`, identidad del bloque `partido` de `history.json` u otros artefactos por partido; documentar conflictos |
| `inputs.home`, `inputs.away` | `history_count`: históricos válidos por equipo; `venue_history_count`: local jugando en casa / visitante fuera; `xg_count`, `xga_count`: muestras válidas observadas de xG y xGA, contadas por separado | `history.json`, `xg_history.json`; `enriched.json.control_muestra` como evidencia derivada, sujeto a auditoría temporal |
| `inputs` | `bilateral_xg_available`: ambos equipos tienen xG utilizable; `standings_available`; `h2h_available`; `h2h_count` | `xg_history.json`, `standings.json`, sección H2H de `history.json` / `h2h_analysis.json`; disponibilidad sólo si es utilizable antes del corte |
| `audit` | Corte, elegibilidad, motivos, calidad y procedencia; nunca features | Controles de origen y revisión de muestras efectivamente usadas; `result.json.integridad_temporal` como evidencia, no garantía suficiente |
| `predictions` | Snapshot identificado del Champion, separado de inputs y labels | Salida que identifique explícitamente `J_BT_sin_temporada`, por ejemplo snapshot de evaluación verificable; nunca elegir otro escenario por defecto |
| `labels` | Resultado final observado, separado de todo input | Fuente de resultado liquidado identificada y auditada; el nombre `result.json` no demuestra que contenga resultados reales |

Los contadores son enteros >= 0 de muestras posteriores al filtrado temporal,
no tamaños brutos descargados. `venue_history_count <= history_count` cuando
ambos se conocen. xG y xGA pueden tener coberturas distintas: no equipararlas.
`h2h_available=false` con revisión completa implica `h2h_count=0`; desconocido
implica `null`. Bilateralidad desconocida es `null`, no `false`.
Todavía no se definen ni extraen agregados deportivos adicionales.

## Predicción Champion

`model` es exactamente `J_BT_sin_temporada` (BT0); sin atribución verificable,
`predictions=null`. `generated_at` es ISO 8601 con offset, o `null`.
`lambda_home`, `lambda_away`, `lambda_total` son floats finitos >= 0.
`p_over_1_5`, `p_over_2_5`, `p_over_3_5`, `p_over_4_5`, `p_btts`, `p_home`,
`p_draw`, `p_away` son probabilidades finitas en [0, 1], todas nullable.
No mezclar porcentajes [0, 100] con probabilidades: `analysis/run_match.py`
emite porcentajes; un adaptador futuro deberá normalizar según origen conocido,
nunca por heurística sobre el valor. Los snapshots pueden usar escala [0, 1].

Si existen, verificar suma 1X2 y suma de lambdas con tolerancia de redondeo
documentada por el adaptador; no corregir ni recalibrar silenciosamente.
`confidence`, `global_quality` son strings de origen nullable; `flags` conserva
las banderas disponibles como lista nullable. Una estructura de calidad de origen
no escalar exige un mapeo posterior explícito, no convertirla arbitrariamente.
`lambda_local/visitante` pueden corresponder a `lambda_home/away`, `+1.5` a
`p_over_1_5`, `BTTS` a `p_btts`, `prob_1/X/2` a `p_home/draw/away`, siempre con
procedencia y escala verificadas. Un mercado ausente, como Over 4.5, queda null.

## Labels de liquidación

`labels=null` para partidos pendientes, en vivo, suspendidos, cancelados o sin
confirmación de liquidación. No basta encontrar un marcador numérico. La base
es el marcador final de tiempo reglamentario más añadido, sin prórroga ni penales;
si la fuente no permite distinguirlo, no generar esos labels.
`settled_at` conserva el instante de liquidación verificado o null, nunca kickoff.

`home_goals`, `away_goals`, `total_goals` son enteros >= 0 nullable. Cuando ambos
scores están confirmados, `total_goals = home_goals + away_goals`, `label_btts`
es ambos > 0, y los cuatro `label_over_*` son total > 1.5/2.5/3.5/4.5.
`label_1x2` es `"1"`, `"X"` o `"2"` según el marcador. Sólo derivar un label si
sus operandos están observados: cualquier operando faltante deja ese label null.
Una fila liquidada puede conservar campos null si falta evidencia parcial.
Estas fórmulas definen consistencia; no se implementa extracción en este hito.

## Auditoría y reglas anti-leakage

1. El target se excluye de **todas** sus muestras por `match_id`, incluyendo
   historia, xG/xGA, standings y H2H. Su resultado nunca participa en features.
2. Ningún evento posterior al target ni información disponible después del corte
   puede participar. `audit.feature_cutoff` identifica el instante prepartido
   ISO 8601 con offset, o null si no es verificable. No inventar medianoche.
3. Sin hora fiable se excluye **todo el mismo día**: sólo fechas estrictamente
   anteriores. Es la política de `analysis/temporal.py::filtrar_prepartido`, que
   actualmente también excluye el mismo día aunque haya hora. V3 1.1 conserva
   esa política conservadora; no habilita excepciones intradía. Fechas ausentes
   o no interpretables se excluyen de muestras; sin fecha target no hay elegibilidad.
4. Labels sólo para liquidados y nunca como features. Ni `labels`, ni
   `predictions`, ni `audit` se deben incorporar automáticamente a inputs.
   Metadata identificativa tampoco constituye autorización para usarla como feature.
5. Cualquier violación temporal excluye la fila de consumo o exige
   `audit.temporal_status="ERROR"`, `eligible=false` y motivos explícitos.
   Evidencia incompleta exige `"REVIEW"`, `eligible=false`. Sólo una comprobación
   completa permite `"OK"` y `eligible=true`. `result.json` con estado distinto
   de `OK` bloquea elegibilidad; `OK` por sí solo no verifica disponibilidad de
   todas las fuentes. Traducir `REVISAR` a `REVIEW` conservando evidencia.
6. Train/test futuros deben separarse temporalmente por fecha/corte del target;
   random split no será el criterio principal. No se construyen splits aquí.

Cada entrada en `audit.provenance` contiene `group` (metadata/inputs/predictions/
labels), `field` (ruta de campo o grupo), `source` (identificador de fuente),
`artifact` (ruta/referencia nullable), `observed_at` (momento de captura nullable),
`available_at` (momento verificable de disponibilidad nullable). Timestamps ISO
8601 con offset. Captura no equivale a disponibilidad histórica. Un timestamp
de modificación de archivo no prueba disponibilidad prepartido.

Se requiere trazabilidad de todos los grupos presentes y de cada fuente que
contribuye a inputs. Standings descargados después del target pueden incluir
su resultado: excluirlos si no existe snapshot prepartido verificable. Igual
criterio aplica a agregados/H2H/xG y revisiones posteriores de estadísticas.
Si no puede acreditarse disponibilidad temporal, conservar null en el input
afectado y marcar revisión cuando impida verificar la fila. Nunca certificar
retroactivamente un snapshot por su fecha de partido.

`audit.reasons` registra motivos concretos de exclusión/revisión;
`quality_flags` conserva problemas de cobertura y calidad (null si no evaluados).
Un input opcional ausente no implica por sí solo violación temporal: se distingue
cobertura incompleta de evidencia temporal insuficiente sobre datos utilizados.

## Versionado y continuidad

Cambios incompatibles de estructura/semántica incrementarán `schema_version`;
cambios de ventanas, filtros o cálculo de features incrementarán `feature_version`.
No reetiquetar históricos como 3.0.0 sin verificar su conformidad.
Los artefactos operativos se mencionan sólo como inventario de fuentes esperadas:
no se modifican, migran ni versionan. No hay cambios en `data/`, `analysis/`,
`scraper/`, históricos, reportes ni evaluación de efectividad.

Validación estructural de este hito: compilar e importar los tres módulos V3 y
comprobar resolución de anotaciones. Un validador de filas y los adaptadores
corresponden a trabajos posteriores; estos tipos no certifican datos runtime.
