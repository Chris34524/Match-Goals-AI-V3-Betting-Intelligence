# Dataset Builder V3 (1.2)

Desde la raíz del repositorio:

```bash
python -m v3.data.builder --source-root data/matches --output-dir data/derived --limit 5
python -m compileall -q v3 tests
python -m pytest -q tests/v3
```

La suite usa pytest como dependencia exclusiva de desarrollo (`python -m pip
install pytest`); el builder sólo usa la biblioteca estándar.

## Representación reproducible

JSONL es canónico, UTF-8, claves ordenadas, sin NaN ni infinito. Se inspeccionan
los directorios por nombre, aplicando `--limit` antes de ordenar filas. Las filas
se ordenan por fecha local, kickoff textual con offset y match_id; sin kickoff
se usa cadena vacía, sin fecha se ordenan al final. El manifest incluye SHA-256
de los bytes JSONL. Sólo su timestamp cambia entre builds idénticos.

CSV aplana diccionarios mediante rutas separadas por puntos. Cada celda es un
valor JSON (incluidos strings con comillas, listas y `null`). Las columnas son
la unión ordenada de rutas presentes; una celda vacía indica ruta no expandida
porque un contenedor completo era null. El JSONL conserva íntegra la estructura.

Los motivos principales del manifest son el primer motivo en orden alfabético
por fila; la lista completa está en `audit.reasons`. `artifact_counts` cuenta
artefactos inválidos y ausencias de los siete artefactos operativos conocidos.
Rutas de procedencia son relativas al directorio fuente; el manifest conserva
sólo el nombre de esa raíz para evitar rutas personales.

## Adaptadores y decisiones conservadoras

* Identidad: `partido` únicamente en `history.json`, `result.json`,
  `lambda_comparison.json` y `champion_snapshot.json`, aliases explícitos del
  contrato. Se contrastan todos los IDs y metadatos presentes. El directorio
  proporciona el identificador Flashscore; claims repetidos entre directorios
  bloquean ambas filas, sin emitir IDs duplicados ni seleccionar silenciosamente.
* `history.json.secciones`: se reconocen títulos `ÚLTIMOS PARTIDOS: <equipo>`
  y `ENFRENTAMIENTOS...`. Sólo se cuentan muestras parseadas, scores enteros,
  IDs únicos, fecha anterior al target y equipo verificable. Target, mismo día
  y futuro se excluyen y bloquean elegibilidad. Fechas desconocidas requieren
  revisión. No se exige `available_at` del archivo raw: cada muestra terminada
  acredita su anterioridad por su propia fecha. Provenance usa
  `source=flashscore:historical_sample_date` y una referencia de muestra/fecha
  en `field`; `available_at` queda null, sin inventar una hora de disponibilidad.
  Captura/mtime del archivo no acreditan disponibilidad. Esta regla no se aplica
  a agregados. No se infiere offset desde `hora`.
* `xg_history`, standings, enriquecidos y H2H agregado quedan sin incorporar:
  sus agregados no acreditan linaje temporal completo en las muestras reales
  inspeccionadas. Sus inputs permanecen null y se registra la omisión como flag.
  No se calculan features deportivas. Se necesitan ambas historias verificadas
  para declarar una fila elegible; inputs opcionales ausentes no la bloquean.
* Champion: únicamente `lambda_comparison.metodos.J_BT_sin_temporada` (lambdas
  local/visitante/total), o `champion_snapshot.json` con `model` explícito y
  campos canónicos de predicción. Este último exige probabilidades en [0,1].
  No se importan porcentajes de `result.json.escenarios`, ni se calculan mercados.
  Lambdas y suma 1X2 se validan con tolerancia absoluta 0.0002. Evidencia inválida
  bloquea la fila y deja predicciones null; nunca se corrigen valores.
* Liquidación: `result.json` operativo contiene análisis, no confirma un score.
  Sólo se admite un bloque explícito `settlement` con `status=FINISHED`,
  `score_scope=REGULATION`, `home_goals`/`away_goals` enteros y `settled_at`
  opcional con offset. Se derivan exclusivamente labels cuyos operandos existen.
  Labels suministrados inconsistentes bloquean la fila y dejan labels null.
  Esta forma explícita también permite probar liquidaciones sin confundir
  predicciones ni scores en vivo con resultados finales.
* Pool retrospectivo opcional: `--backtest-pool RUTA` o, por defecto,
  `backtest_pool.json` junto a `source-root` (para `data/matches`,
  `data/backtest_pool.json`). La API acepta `backtest_pool=RUTA`. Si no existe,
  el build continúa con labels null salvo liquidación explícita. Se adapta
  exclusivamente el objeto `{"partidos": [...]}` real, indexado por `match_id`
  exacto; no se hace fallback a `id`. Identidad presente e `id` se contrastan;
  goles deben ser enteros no negativos (booleanos excluidos). Sólo aporta labels,
  nunca metadata, inputs ni disponibilidad. Duplicados se validan todos: scores
  o identidades contradictorias producen ERROR y labels null. Un conflicto con
  settlement también bloquea la fila sin escoger una fuente. El manifest cuenta
  `labels_from_backtest_pool`; provenance identifica `backtest_pool.json`.
  Un pool inválido exige revisión; uno ausente no bloquea.
* JSON sin adaptador, incluso malformado, se ignora para identidad y elegibilidad.
  Agregados conocidos no usados sólo aportan flags de omisión.
* El `integridad_temporal.estado` distinto de OK bloquea la fila incluso con
  historias verificadas. OK por sí solo nunca acredita las fuentes.

En fuentes adaptadas, JSON inválido, claves JSON repetidas, codificación ilegible
y estructuras no reconocidas producen revisión explícita. Se rechazan salidas que se solapen con
la raíz fuente y archivos de salida symlink; no se siguen directorios symlink.
El builder sólo escribe los tres archivos declarados dentro de output-dir.
No integra ni altera el pipeline operativo. Las salidas permanecen locales.

## Validación local de implementación

La corrección 1.2.1 incluye tests de historial raw sin disponibilidad del archivo,
fechas bloqueadas, separación de labels, pool opcional, conflictos y artefactos
sin adaptador. La validación real ejecuta dos builds completos y compara SHA-256,
contenido y mtime de todas las fuentes de `data/` fuera de `derived/`.
Los archivos de salida con enlaces duros también se rechazan para proteger fuentes.

Validación real de 1.2.1: 4,256 directorios/filas, 2,896 elegibles,
1,360 no elegibles y 500 filas con labels del pool. Motivos principales:
`temporal_history_violation=1128`, `h2h_team_conflict=144`,
`incomplete_history_evidence=86`, `unverified_history_sample=2`.
Dos builds completos produjeron SHA-256
`fa732fdb2a7be786c99495bebbafa03956d52407e4a64d84aeb1293529a43e06`.
Se verificaron 66,314 archivos fuente sin cambios de contenido ni mtime.
`compileall` correcto y 53 tests V3 pasan. Sólo se generan las salidas locales
en `data/derived/`; ningún archivo de `data/` se incluye en el commit.

## Quality gates 1.3

```bash
python -m v3.data.quality --dataset data/derived/dataset_v3.jsonl
PYTHONPATH=. python tests/v3/verify_real_quality.py
```

El reporte es JSON determinista, sólo lee archivos y no reescribe el dataset.
Busca automáticamente `<dataset_stem>_manifest.json`; `--manifest RUTA` permite
seleccionar otro. Si no existe manifest, indica `present=false` sin inventar una
comparación. Contrasta filas, elegibilidad, labels del pool, motivos principales
y SHA-256. Devuelve código 1 ante duplicados, inconsistencias estructurales o
diferencias con el manifest; código 2 ante JSONL/manifest ilegible o inválido.
No imprime un reporte parcial si falla una línea: también rechaza líneas vacías,
claves repetidas y números no finitos. Un dataset vacío produce conteos cero.

Incluye distribución por fecha (con `unknown`), estados temporales, cobertura por
valor de history_count home/away, todos los motivos ordenados por frecuencia y
nombre, labels y Champion. Los motivos principales siguen la convención del
manifest. Las inconsistencias incluyen contrato, tipos de conteos, gate temporal,
identidad, procedencia histórica y aislamiento de artefactos. Los conteos de
historia se contrastan con las muestras de provenance. El reporte verifica lo
que acredita el contrato; la auditoría opcional reconstruye desde las fuentes
reales para comprobar aislamiento mediante mutaciones, sin escribir en `data/`.

`v3.data.temporal.sample_reasons` centraliza exclusión de target, futuro, mismo
día y fecha/identidad desconocidas para adaptadores actuales y futuros. La
política permanece a resolución de día; ninguna hora raw autoriza mismo día.
Los motivos nuevos `input_temporal:*` distinguen cada causa y se ordenan sin
corregir evidencia. Los snapshots Champion y lambda_comparison quedan fuera de
la selección de metadata además de inputs. Evidencia de identidad operativa
contradictoria sigue bloqueando la fila; labels/predicciones inválidos conservan
los bloqueos de integridad de 1.2, sin corregir valores ni autorizar features.
Los adaptadores xG/agregados siguen excluidos hasta acreditar su linaje.

### Validación real 1.3 sobre el dataset conservado de 1.2.1

4256 filas: 2896 elegibles y 1360 no elegibles. Manifest coincidente en todos
los campos contrastados y SHA-256
`fa732fdb2a7be786c99495bebbafa03956d52407e4a64d84aeb1293529a43e06`.
500 filas con labels del pool, 4108 con predicciones Champion; cero match_id
duplicados e inconsistencias estructurales. Estados: OK=2896, ERROR=1288,
REVIEW=72. Fechas verificadas entre 2025-02-12 y 2026-10-25; 7 desconocidas.
History_count conocido: 4028 filas por lado; desconocido: 228 por lado.

Principales motivos (primer motivo por fila):

| Motivo | Filas |
| --- | ---: |
| temporal_history_violation | 1128 |
| h2h_team_conflict | 144 |
| incomplete_history_evidence | 86 |
| unverified_history_sample | 2 |

Contando todos los motivos, temporal_history_violation aparece en 1148 filas,
incomplete_history_evidence en 230 e insufficient_input_evidence en 226.
Estos nombres pertenecen al dataset 1.2 preservado; una nueva generación 1.3
usa los motivos temporales desglosados.

La auditoría comparó las 4256 filas desde fuentes reales: quitar pool, mutar
scores de las 500 etiquetas y quitar ambos artefactos de predicciones produjo
cero cambios de inputs o metadata. Quitar pool también produjo cero cambios de
estado/elegibilidad/motivos. Inputs y metadata reconstruidos coinciden con el
dataset original en todas las filas. No se compara distribución deportiva entre
subgrupos etiquetados y no etiquetados: se compara cada identidad consigo misma.
Ningún archivo histórico ni salida de `data/` se modifica para esta validación.

## Snapshots reproducibles 1.4

```bash
python -m v3.data.snapshot create \
  --dataset data/derived/dataset_v3.jsonl \
  --manifest data/derived/dataset_v3_manifest.json \
  --output-root data/snapshots
python -m v3.data.snapshot verify data/snapshots/<snapshot_id>
```

La creación copia los bytes originales de dataset y manifest, genera
`quality_report.json` desde las copias y publica sólo tras validar los quality
gates. `snapshot_manifest.json` registra versiones, conteos, hashes SHA-256 y
`created_at` UTC. Los nombres de archivos son relativos. El ID `v3-<sha256>`
abarca la versión del formato snapshot y los hashes completos de los tres
archivos congelados. Por ello, otro manifest fuente (incluso su `built_at`)
produce otra identidad aunque el dataset sea idéntico. Los experimentos pueden
referenciar `snapshot_id` y `dataset_sha256`.

La publicación usa un temporal hermano y `renameat2(RENAME_NOREPLACE)` de Linux;
no reemplaza destinos existentes, ni siquiera vacíos. Ante fallo se elimina el
temporal. Dos creadores concurrentes convergen al mismo snapshot. Un destino
existente se verifica y sólo se reutiliza si sus tres archivos coinciden byte
por byte. Conserva su `created_at` original; éste es metadata de auditoría
explícitamente fuera de la identidad. Creaciones independientes sólo pueden
diferir en este campo. No hay dependencia de rutas personales ni timestamps
para calcular el ID.

`verify` exige los cuatro archivos exactos, vuelve a calcular hashes e identidad,
comprueba versiones, conteos y directorio, y regenera el quality report para
compararlo completo. Rechaza enlaces simbólicos en las rutas y archivos con
hardlinks; las copias son archivos independientes. La salida no puede solaparse
con los directorios fuente. Inmutabilidad significa rechazo de conflictos y
detección de cambios; no sustituye permisos del sistema ni una firma de autoría.
La utilidad requiere un directorio local controlado por el usuario, sin procesos
hostiles cambiando sus ancestros durante la operación. Una interrupción abrupta
puede dejar un temporal oculto, nunca un snapshot publicado parcialmente.

Las fuentes se abren sólo para lectura y no se cambia su contenido ni mtime.
Los snapshots permanecen bajo `data/`, ignorados por Git. La suite cubre los
13 escenarios de la Issue #7, seguridad de enlaces, concurrencia y consistencia
del reporte aunque se reescriba su hash.

Validación real 1.4: 112 tests V3 pasan y `compileall` correcto. Snapshot:
`v3-dfd2ee642ffed047e7a2b62298ca9be10fa214f5b1538d3e593dd14db148a7cc`.
Dataset SHA-256:
`fa732fdb2a7be786c99495bebbafa03956d52407e4a64d84aeb1293529a43e06`.
4256 filas, 2896 elegibles, 1360 no elegibles y 500 con labels. Quality gates
sin duplicados, inconsistencias ni diferencias con manifest. Creación repetida
conservó ID, hashes, contenido y mtime de los cuatro archivos congelados, sin
conflictos ni duplicación. Se compararon hashes y mtime de 66310 archivos fuente
bajo `data/` (excluyendo `snapshots/`): ninguno cambió.

## Catálogo de features 2.1

El [catálogo y auditoría de fuentes](../docs/v3/features.md) documenta 118
candidatos (86 available, 6 planned y 26 blocked), con mercados, ventanas,
reglas de ausencia y requisitos de linaje. API declarativa e inmutable en
`v3.features`: `get_catalog(market=..., group=..., status=...)` y
`catalog_json()`. No calcula features ni cambia el dataset o Champion.
`python -m v3.features.audit` inspecciona fuentes reales en modo sólo lectura
y emite cobertura y digest deterministas en stdout.

## Superficie de señales 2.1A

Catálogo ampliado y auditoría read-only aislados del pipeline operativo:
[mapa completo y política de adquisición](../docs/v3/signal-surface.md).

```bash
python -m v3.features.surface_catalog > /tmp/signal-surface.json
python -m v3.features.surface_audit --source-root data/matches > /tmp/matches-surface-audit.json
```

`surface_availability` y `capture_policy` son independientes. Esta fase no
implementa captura nueva ni habilita automatización de Flashscore.

Feature Engine de forma L5/L10 y venue (Roadmap 2.2):
[contrato, ejecución y cobertura real](../docs/v3/form-engine.md).
