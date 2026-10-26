# Fase 2 — auditoría final de Betting Intelligence

Batch 2.5–2.12 evaluado secuencialmente en
`feature/phase2-batch-2.4-2.12`. Las ocho consultas `gh issue view` fallaron por
conectividad; se usaron el alcance autorizado, catálogo 2.1.0, superficie 2.1A y
documentación local. No se atribuyen requisitos adicionales a issues inaccesibles.

V3 puede materializar hoy forma reciente/venue, rachas observadas y H2H auxiliar.
Advanced, goalkeeper, players/XI, cards, contexto y news conservan bloqueos
explícitos. Completar su evaluación no significa disponer de sus datos ni de un
extractor productivo. No se entrenó ningún modelo ni se habilitó betting nuevo.

| Subfase / Issue | Resultado | Tests del checkpoint |
|---|---|---:|
| [2.5](phase-2/checkpoints/2.5.md) / #18 | 14 candidatos de fuerza bloqueados; fórmulas y requisitos documentados | 651 |
| [2.6](phase-2/checkpoints/2.6.md) / #19 | 14 columnas H2H canónicas implementadas, sin aliases | 676 |
| [2.7](phase-2/checkpoints/2.7.md) / #20 | Matriz de 24 filas, 12 familias; 12 review y 12 planned; ningún proveedor habilitado | 689 |
| [2.8](phase-2/checkpoints/2.8.md) / #21 | 24 señales advanced/keeper bloqueadas; contratos, incluido corners futuro | 714 |
| [2.9](phase-2/checkpoints/2.9.md) / #22 | 23 señales player/lineup bloqueadas; XI previsto y oficial separados | 738 |
| [2.10](phase-2/checkpoints/2.10.md) / #23 | 9 señales de disciplina bloqueadas; contrato sin doble conteo de expulsiones | 748 |
| [2.11](phase-2/checkpoints/2.11.md) / #24 | 14 proxies objetivos bloqueados; definición y requisitos por proxy | 763 |
| [2.12](phase-2/checkpoints/2.12.md) / #25 | Contrato/validadores P3; 7 eventos bloqueados, adquisición/extractor planned | 798 |

El batch contiene **14 entradas implemented, 0 partial y 91 blocked**.
El inventario de toda Fase 2 contiene **92 implemented, 0 partial y 113 blocked**.
La unidad es nombre único del inventario: 118 columnas originales + 87
extensiones/candidatos; 205 entradas totales, sin aliases H2H. Los candidatos P1/P3 no están
expandidos por lado/ventana y algunos conceptos se solapan; estos números no
representan conceptos estadísticos independientes ni nuevas columnas entrenables.
La matriz de fuentes y los validadores son infraestructura y no inflan implemented.
El catálogo original sigue en 2.1.0; el reporte final es la evaluación de ejecución,
no una promoción de candidatos declarativamente `available` a entrenamiento.

## Qué puede usar hoy V3

| Familia | Disponibilidad acreditada / 4.344 targets | Uso y mercado |
|---|---|---|
| Forma reciente L5/L10 y venue, 72 columnas | Set recent_form completo: 3.893 (89,62%); todas las ventanas/venue: 3.016 (69,43%) | BTTS, Over 1.5/2.5/3.5; 1X2 experimental |
| Rachas observadas capped L10, 6 columnas | Home: 4.104 (94,48%); away: 4.102 (94,43%) por métrica | BTTS, goles y 1X2 según definición; conservar cap/censura |
| H2H auxiliar, 14 columnas | Medias/tasas: 2.948 (67,86%); contadores: 4.337 (99,84%) | BTTS y overs; sólo ablation auxiliar |
| xG/xGA | Medias y disponibilidad bilateral acreditadas: 0 (0%) | Potencial goles/BTTS; bloqueado |
| Fuerza y familias 2.8–2.12 | 0 (0%) acreditados por señal | Potencial 1X2/goles; cards/corners futuros; bloqueadas |

H5/H10 son topes de ventana. Las tasas y medias H2H requieren **tres** encuentros
válidos, conforme al catálogo, y usan el n observado como denominador. Hay 2.553
targets con H5 completo y 1.995 con H10 completo. Se conserva `partial_sample`;
no se confunde tener tres encuentros con tener cinco/diez. Menos de tres produce
null. Sección válida sin encuentros elegibles produce contador cero; sección
ausente/ambigua o fuente inválida produce contador null. No se infiere que ese
cero pruebe ausencia de todos los enfrentamientos históricos.

H2H orienta GF/GA respecto al home/away **actuales**, incluso si la localía previa
fue inversa. Sus seis campos ordinarios se reconocen mediante gramática exacta;
no se aceptan filas anotadas, penales ni scope ambiguo. Se reutilizan las reglas
de exclusión temporal y de todas las copias duplicadas. La primera auditoría
detectó la diferencia frente a las siete columnas de forma; se corrigió antes de
cerrar 2.6, sin cambiar el adaptador compartido ni los outputs 2.2–2.4.
La revisión final añadió rechazo de IDs malformados sin cambiar bytes reales.

## Implementación bloqueada y nuevas fuentes necesarias

El motor xG anterior tiene 14 columnas de salida y tests, pero ningún valor
numérico de medias acreditado: faltan publicaciones/revisiones históricas. Sus
contadores cero indican cero muestras acreditadas, no xG deportivo cero. Las
cuatro métricas goals_per_xg del catálogo siguen sin materialización.
Descanso/congestión tampoco pueden reconstruirse desde historias truncadas.

Fuerza del rival necesita resultados del propio rival anteriores a **cada fixture
histórico ajustado**, IDs reconciliados y linaje independiente; no basta que sean
anteriores al target. Las 4.342 clasificaciones inspeccionadas no tienen snapshots
as-of acreditados. Puntos propios rolling no sustituyen calidad del rival.

Los [contratos](phase-2/intelligence-contracts.json) son declarativos para
advanced/keeper, players, disciplina y contexto; no implementan cálculo ni
ingesta deportiva. Para habilitarlos hacen falta proveedor permitido, IDs
persistentes, publicación/revisiones pre-cutoff y evidencia por campo. Corners
necesita definición/scope y cobertura; goalkeeper requiere orientación por stint,
xGOT faced y definición de goals prevented, sin sustituirlo por xG.

Minutos/load, descanso, sanciones y contexto de entrenador necesitan ledgers
completos. Un `complete=true` sin evidencia independiente no satisface el gate.
Cards conserva el ledger de cautions separado del de dismissals: segunda
amarilla y roja sintética se vinculan a un único dismissal_id. Reglas de mercado,
sanciones/carryover/amnesty y competición no son intercambiables.

Stakes exige standings históricos, fixtures restantes y reglas/tiebreaks de esa
temporada. Manager change exige anuncio y fecha efectiva; un nombre de entrenador
actual no demuestra cambio. Unknown no equivale a false. Fixture importance es un
vector de proxies acreditados, sin motivación o estado emocional inferidos.

News P3 dispone de schema y gate de ingesta separados. Aceptar estructura no
acredita permiso ni autenticidad del timestamp. No hay proveedor habilitado ni
extractor NLP; los siete eventos siguen blocked. Un adapter futuro deberá
verificar publicaciones/revisiones de forma independiente. Los tests positivos
son sintéticos. No se creó corpus ni se copió la previa como dataset.

## Flashscore: superficie existente y permiso pendiente

La [matriz](phase-2/source-matrix.md) y su [JSON](phase-2/source-matrix.json)
distinguen visibilidad de autorización. Los snapshots locales muestran XI
esperado, nombres/dorsales, ratings promedio de competición, bajas por lesión y
tarjeta roja, entrenadores y texto de previa. No acreditan player IDs, XI oficial,
publicación, minutos ni eventos cronológicos. No convertir dorsales en IDs,
promedio de competición en rating de partido o baja por roja en ledger de cards.

La superficie 2.1A documenta categorías públicas de stats de equipo/jugador,
goalkeeper y lineups con cobertura variable. Esa documentación previa no
acredita autorización actual de automatización. Esta fase no consultó endpoints
nuevos ni actualizó términos/permisos: las rutas Flashscore permanecen review,
sólo auditoría del archivo existente; alternativas oficiales/licenciadas planned
hasta seleccionar proveedor y verificar alcance, límites y retención.

## Señales que no deben llegar a entrenamiento

Excluir todas las entradas blocked/partial/planned, incluidos xG deportivo,
fuerza/standings actuales, advanced/keeper, player/XI no acreditado, disciplina,
contexto y news. No convertir sus nulls o contadores diagnósticos en ceros
sportivos. No usar labels, backtest_pool, result.json, Champion/BT0,
confidence*.json, lambda_comparison ni targets/resultados futuros como features.

La salida H2H contiene únicamente las 14 columnas canónicas. La relación
away_GF = home_GA y away_GA = home_GF no se materializa como columnas. Mantener H2H fuera del core recent_form y comprobar su
valor incremental con ablation temporal. La cobertura por sí sola no demuestra
valor predictivo; faltan splits por tiempo, calibración, controles por liga y
análisis de missingness/selección. No se ha demostrado rentabilidad de mercados.

## Evidencia de validación y reproducción

Baseline: **649 tests**. Final: **798 tests**; compileall y git diff --check
correctos. Cada checkpoint ejecutó suite completa y regeneró las salidas previas,
comparando JSONL y manifests byte a byte. La auditoría final repitió los cuatro
builders con el reproductor de fingerprints. Los hashes íntegros y cobertura por
feature están en [phase-2-validation-report.json](phase-2-validation-report.json).

| JSONL | SHA-256 |
|---|---|
| form_features.jsonl (2.2) | `779040a01b40f0099d260438199dcbefdc0d052bb8cca0fda39ec8f2ab1033b4` |
| xg_features.jsonl (2.3) | `7003af3f3a66f0ae6d0c6cee3992e82f8b803f2ccc1f6d9bf31759b74a74a614` |
| temporal_features.jsonl (2.4) | `22f3f0a0e83b23b704932436cc9dbfe5e49a54c95e8f6576cc765052527042aa` |
| h2h_features.jsonl (2.6) | `c0c1c1d12e9dc66d7ec6460761e1b9c0d70eed5f3b4c715e2086c523190a98f5` |

```bash
python -m compileall -q v3 tests
python -m pytest -q tests/v3
python -m v3.features.phase2_validation --output-dir /tmp/phase2-final-correction
python -m v3.features.source_matrix
python -m v3.features.intelligence_contracts
git diff --check
git diff --stat
git status
```

Outputs generados exclusivamente en `/tmp/phase2-batch/`; ningún artefacto nuevo
en data/. Comparación inicial/final de cada ruta, SHA-256 y mtime: **67.219**
archivos data/, **33** scraper/, **85** analysis/ y **41** del backup operativo
intactos, excluyendo sólo cachés de Python. Los digests agregados están en el JSON;
los inventarios completos de esta ejecución permanecen en `/tmp/phase2-batch/`.
BT0 y J_BT_sin_temporada están incluidos en esa protección. Ninguna fuente
prohibida se usó para features; ningún dato futuro contribuyó; ningún scraping
nuevo se añadió. No hubo add, commit, push ni cambio de rama. La corrección H2H deja un diff real en archivos tracked, sin staging.

H2H regenerado dos veces en /tmp/phase2-h2h-correction-a y /tmp/phase2-h2h-correction-b: JSONL y manifest idénticos byte a byte. Inventario y cobertura recalculados desde la salida real y el catálogo.
