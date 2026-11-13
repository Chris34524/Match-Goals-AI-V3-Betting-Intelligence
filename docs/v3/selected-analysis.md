# Análisis multimercado de partidos seleccionados

[Piloto E2E de dos partidos futuros, corte congelado y replay](selected-pilot-e2e.md).
El comando adicional `python -m v3.selected_analysis.pilot` reutiliza el motor
existente, exige dos fixtures futuros y conserva los inputs con hashes. No escribe
en journals OOS ni habilita adquisición live.

Actualización prioritaria de referencia: [matriz de Flashscore México por campo](flashscore/mx-coverage-audit.md).
El reporte reutiliza también xG/xGA y clasificación del archivo legado como
observaciones explícitamente no acreditadas, separadas de los inputs predictivos.
Flashscore México continúa como referencia principal; no hay fallback automático
a API-Football ni nuevos extractores. La matriz registra autorización, periodo,
captura y cobertura reales, incluidos los datos que faltan.

MVP aditivo en `v3/selected_analysis/`, sobre `df52aa8`, en la rama
`feature/selected-multimarket-analysis`. Los estados describen disponibilidad de
software y datos; **IMPLEMENTED no significa calibrado ni acreditado OOS**.
Todos los reportes llevan `NO_BET`, `oos_eligible=false` y separan λ de xG observado.

## Diagnóstico arquitectónico previo

| Módulo / archivo | Propósito y evidencia local | Estado real | Reutilización / recomendación |
| --- | --- | --- | --- |
| `scraper/flashscore.py`, `scraper/match_selector.py` | Playwright y búsqueda de partidos por ID/nombres; universo `data/partidos.json` | IMPLEMENTED heredado; no autorización nueva | Sólo leer archivos existentes; no invocar transporte heredado desde V3 |
| `analysis/select_day_matches.py`, `run_selection.py`, `run_selected_matches.py` | Selección y pipeline con subprocess, scraping y sustitución temporal del reporte diario | IMPLEMENTED heredado | Conservar; el nuevo CLI no activa estos pipelines ni sobrescribe sus reportes |
| `analysis/run_match.py` | Historial, standings, xG, enriquecimiento y escenarios J/H2H | IMPLEMENTED heredado | Reutilizar conceptos; evitar `--prepare`/extracción implícita y escritura en `data/` |
| `analysis/compare_lambda.py` | A–R, BT0 y sensibilidad H2H; ponderaciones existentes | IMPLEMENTED; fallo de impresión de None reproducido | Corregir sólo presentación; ejecutar sus fórmulas en sandbox temporal |
| `analysis/poisson.py` | Matriz de marcadores, 1X2, dobles, BTTS, totales | IMPLEMENTED, operacional | Reutilizar con cola de truncación explícita y rango dinámico; no reclamar calibración |
| `analysis/goals.py`, `analysis/h2h.py` | Estadística descriptiva y H2H | IMPLEMENTED heredado | Preferir los filtros más estrictos de `v3/features/history_adapter.py` y `h2h.py` |
| `analysis/confidence_v2.py` | Evidencia histórica segmentada BTTS; otros mercados no validados | IMPLEMENTED, validación limitada heredada | No transferir esa evidencia a mitades/córners/tarjetas ni a OOS V3 |
| `analysis/report_window_pro.py`, `build_selected_report_data.py`, `best_bets.py` | HTML diario/seleccionado y ranking descriptivo | IMPLEMENTED heredado; score no equivale a probabilidad ni EV | Conservar archivos y salidas; nuevo reporte aislado |
| `v3/providers/selection.py`, `full_capture.py`, `cli.py` | IDs locales, resolución por fecha/liga/temporada/equipos estables, FULL_MATCH_V1 | IMPLEMENTED; captura no es predictor | Reutilizar resolver, plan y captura; verificar identidad devuelta |
| `v3/providers/api_football/` | Transporte GET permitido, clave por entorno, límites, normalización y almacenamiento | IMPLEMENTED; cobertura real depende de cuenta y competición | No se realizó ninguna adquisición live en esta implementación |
| `v3/flashscore/` | Capabilities, replay, auditoría FS-3, features FS-4, targets FS-5 | IMPLEMENTED offline; transporte live BLOCKED | Leer contratos/replay; no abrir un bypass de autorización |
| `v3/features/` | Forma/venue, H2H, contratos advanced, xG/contexto con linaje | Forma/H2H IMPLEMENTED; otros contratos BLOCKED con datos locales | Contrato de campo disponible no acredita features utilizables |
| `v3/models/` | Protocolo de challengers, comparación histórica exacta con Champion | Software IMPLEMENTED; evidencia real BLOCKED | No entrenar, promover, abrir TEST ni cambiar pesos |
| `v3/selection/` | PickScore, value y NO_BET | Software IMPLEMENTED; selección real BLOCKED | No utilizar probabilidades de este MVP como candidatos acreditados |
| `v3/ops/` | Forecast operacional vs prospectivo, cuotas, OOS y promoción | Forecast operacional IMPLEMENTED; evidencia prospectiva condicionada | No escribir sus journals ni alterar sus gates |
| `v3/performance/` | Métricas sobre ledger OOS settled; mínimo 200 partidos únicos | Software IMPLEMENTED; gate real no acreditado | No agregar reconstrucciones ni pruebas sintéticas al contador |

Se revisaron también `selected-match-capture.md`, `fs-9-final.md`,
`phase-2-final.md`, `roadmap-final.md` y las pruebas de providers, Flashscore,
features/modelos, selección, forecast y performance. Los documentos previos
distinguen implementación de software, autorización de captura y acreditación
histórica: ninguna de esas tres dimensiones sustituye las otras.

Estado inicial: `main`, `df52aa8008163ce83b7e6182faf77f6b84b86e5a`;
Python 3.12.3 en `.venv`; `python` global no disponible en WSL.
Tres archivos previos sin seguimiento: `generate_daily_forecast_report.py`,
`generate_rich_forecast_report.py`, `generate_rich_forecast_report_v2.py`.
No se modificaron. No se ejecutó reset, pull, commit, push, PR o merge.
Un pipeline heredado ajeno a este trabajo estaba ejecutándose simultáneamente;
los cambios concurrentes de sus datos no se atribuyen al nuevo analizador.

## Matriz multimercado

| Familia | Implementación | Condición para estimar | Estado con el archivo legado de QilxV7k3 |
| --- | --- | --- | --- |
| FT 1/X/2, 1X/X2/12, BTTS sí/no | Poisson existente con BT0 | Al menos 5 resultados válidos por equipo | IMPLEMENTED operacional; sin calibración/OOS |
| FT over/under 1.5/2.5/3.5/4.5, λ por equipo, total y marcadores | Misma distribución de goles | Igual gate; dominio de λ 0–50 | IMPLEMENTED operacional |
| 1H/2H over/under 0.5/1.5, gol por equipo, BTTS y comparación de mitades | Poisson independiente de cada mitad | Series específicas con 5–20 muestras completas y linaje pre-corte | BLOCKED: IDs estables/contexto de equipo ausentes; nunca se aplica un porcentaje de FT |
| Córners FT over 7.5/8.5/9.5/10.5/11.5; 1H over 3.5/4.5/5.5 | Modelo independiente Poisson/NB por momentos y convolución bilateral | Conteos de córners propios y concedidos; venue si bilateralmente completo | BLOCKED con este legado; con IDs y operandos ausentes: INSUFFICIENT_DATA |
| Tarjetas FT/1H over 2.5/3.5/4.5/5.5, componentes esperados, cualquier expulsión | Modelo independiente experimental | Política explícita y componentes exclusivos compatibles, actor scope y linaje | BLOCKED sin política/semántica; totales amarillas/rojas no bastan |
| xG/xGA, remates, remates a puerta, posesión, faltas | Medias observadas, con cobertura y procedencia | Capabilities acreditadas por campo y corte | Sin valores acreditados en este legado; null y causa |
| Fuerza rival, descanso, lesiones, XI y standings | Diagnóstico de requisitos | Calendarios completos, historial anidado del rival y publicaciones verificadas | BLOCKED; no se inventan proxies |

`EXPERIMENTAL` nunca implica calibrado. `INSUFFICIENT_DATA` conserva muestras
parciales y ausencias. `NOT_COVERED` requiere declaración explícita del proveedor.
`BLOCKED` distingue identidad, permiso, tiempo o semántica incompatibles.

## Integración y decisiones estadísticas

El adaptador de fixtures acepta el JSON legado, listas genéricas y envelopes
oficiales API-Football. Resuelve hoy/mañana en `America/Mexico_City`, filtra país,
competición/equipo y selecciona índices o IDs exactos. Duplicados idénticos se
colapsan; identidades conflictivas se excluyen por completo y se registran. No
se transfiere un ID entre proveedores por nombres ni por un `provider_ids`
declarado sin verificar. `--candidates` exige los cinco identificadores/contextos
que ya valida el resolver existente. El límite de seis se aplica después de
deduplicar y se configura con `--max-matches`.

Los resultados legados pasan por `team_history`: exclusión de target, mismo día,
futuro, todas las copias de IDs duplicados, scores inválidos y scope extra-time/
ambiguo. Se limita el historial a 20 partidos anteriores al día del corte.
Se reutiliza el resumen existente para L5/L10/L20 y sede, conservando n real y
ventanas parciales. Sus fechas anteriores no acreditan publicaciones históricas:
el forecast sigue siendo operacional y queda excluido de OOS.

BT0 se calcula invocando únicamente `analysis.compare_lambda` en un directorio
temporal con esas estadísticas. No se llama scraper ni se leen `result.json`,
labels, resultados del target o standings posteriores. Los pesos originales no
cambian. xG legado sin linaje no entra al cálculo nuevo; xG acreditado mediante
capabilities sí puede entrar. Por ello un valor recalculado puede diferir del
caché legado: cambian los operandos elegibles y se aplica la renormalización
que el Champion ya implementa. El caché queda intacto y aparece separado como
comparación bloqueada para ese corte. No es evidencia OOS ni benchmark validado.

Los modelos advanced usan `ObservationIndex`, `Capability.prematch_usable` y
política de tarjetas existentes. Exigen autorización verificada, publicación y
revisiones acreditadas anteriores al corte, fixture terminado de regulación y
orientación estable. Se seleccionan los últimos 20 fixtures y **no se rellena
un operando ausente con uno más antiguo**. Para mitades/córners se cruzan ataque
propio y defensa rival mediante media aritmética. Córners prefiere venue
bilateralmente completo; el fallback overall queda explícito. H2H coincidente
no duplica el mismo conteo en el ajuste de dispersión.

Córners/tarjetas comparan Poisson con NB por momentos cuando hay sobredispersión.
Los totales son la convolución de las dos distribuciones; no se asume que dos NB
con distinto parámetro sean una NB única. Existe evaluación cronológica fija
70/30, con mínimo 10 TRAIN y 5 VALIDATION, LogLoss de conteos, Brier y
reliability por línea. Es validación descriptiva experimental, no calibración
ajustada ni acreditación OOS. Con datos insuficientes las métricas son null.
Una TRAIN con media cero y observación positiva tiene LogLoss no finito:
se representa null, no se serializa Infinity ni se oculta con un cero.

Tarjetas requieren JSON de `CardSettlementPolicy` explícito. Se distinguen
amarilla ordinaria, roja directa y expulsión por segunda amarilla como
componentes exclusivos. No se infieren puntos de casas ni se suman una segunda
amarilla y su roja sintética como dos expulsiones. `ANY_DISMISSAL` combina sólo
rojas directas y expulsiones por segunda amarilla de esos componentes verificados.
Los datos meramente agregados amarillo/rojo pueden mostrarse como observados,
pero no habilitan probabilidades de tarjetas.

El corte debe tener zona horaria, preceder al kickoff conocido y no seguir a la
generación. Por defecto se toma el menor entre inicio del día del partido y
momento de generación. Una `hora` legada no se convierte en kickoff acreditado.
Las reconstrucciones con `--generated-at` fijo sólo se permiten offline.

## Comandos reproducibles desde WSL

```bash
cd /home/leos/projects/match-goals-ai
PY=.venv/bin/python

# Consultar el archivo local existente; cero HTTP.
$PY -m v3.selected_analysis.cli list --date hoy
$PY -m v3.selected_analysis.cli list --date mañana
$PY -m v3.selected_analysis.cli list --date 2026-11-06 --country INDIA
$PY -m v3.selected_analysis.cli list --date 2026-11-06 --competition IFL --team Lajong

# Seleccionar por índices; sin flags de selección solicita entrada interactiva.
$PY -m v3.selected_analysis.cli select --date 2026-11-06 --indices 1,3

# Un partido y varios: reutilización offline y reportes nuevos.
$PY -m v3.selected_analysis.cli analyze --date 2026-11-06 --match-id QilxV7k3
$PY -m v3.selected_analysis.cli analyze --date 2026-11-06 \
  --match-id QilxV7k3 --match-id 0YxCHBec --match-id 0nSmIJV6

# Plan solamente: no HTTP ni archivos de reportes.
$PY -m v3.selected_analysis.cli analyze --date 2026-11-06 --indices 1,3 --dry-run

# Repetición determinista con los mismos bytes de entrada y la misma versión.
$PY -m v3.selected_analysis.cli analyze --date 2026-11-06 --match-id QilxV7k3 \
  --cutoff 2026-11-06T00:00:00-06:00 --generated-at 2026-11-06T12:00:00-06:00

# Histórico multimercado ya capturado/permitido (Capabilities o replay estructurado).
$PY -m v3.selected_analysis.cli analyze --provider api_football \
  --source /ruta/fixtures-autorizados.json --date 2026-11-06 --indices 1 \
  --capabilities /ruta/historial-capabilities.json

# Flashscore offline: exclusivamente envelopes estructurados existentes.
$PY -m v3.selected_analysis.cli analyze --provider flashscore \
  --source /ruta/fixtures-locales.json --date 2026-11-06 --indices 1 \
  --replay-dir /ruta/replay-autorizado

# Descubrimiento oficial: ejecutar sólo con autorización y API_FOOTBALL_KEY en entorno.
# El flag --live es la autorización explícita de esta ejecución; no se ha ejecutado aquí.
$PY -m v3.selected_analysis.cli list --provider api_football --date tomorrow \
  --live --max-requests 2

# Captura FULL_MATCH_V1 de un fixture validado en una fuente local oficial.
# Hasta 1 status + 7 solicitudes de superficies para un partido (sin reintentos).
$PY -m v3.selected_analysis.cli analyze --provider api_football \
  --source /ruta/fixtures-autorizados.json --date 2026-11-06 --match-id 900001 \
  --live --max-requests 8

# Abrir al generar (si WSL tiene navegador registrado).
$PY -m v3.selected_analysis.cli analyze --date 2026-11-06 --match-id QilxV7k3 --open
# Alternativa Windows: copiar la ruta HTML que imprime el CLI.
explorer.exe "$(wslpath -w /ruta/impresa/report.html)"
```

Sin fuente local en modo API live, el descubrimiento también consume el mismo
presupuesto: sumar una solicitud de fixtures al coste anterior. Cuota desconocida
con presupuesto >3 exige status primero. Se cuentan también fallos y los
intentos de captura nunca superan el máximo global. Flashscore live retorna
`BLOCKED_SOURCE_AUTHORIZATION`, cero llamadas y ningún flag de bypass.
No se leen, imprimen ni pasan claves por argumentos; sólo variables de entorno.

Capturar el fixture seleccionado **no adquiere automáticamente 20 historiales**
ni acredita publicación histórica. Para mitades/córners/tarjetas se necesitan
capturas históricas permitidas, IDs estables y linaje independiente. El transporte
API actual no lo acredita por el solo hecho de descargar hoy una estadística.

Salidas nuevas:
`v3_data/selected_analysis/<fecha>/<proveedor>_<match_id>/<analysis_id>/report.{json,html}`.
Cada bundle es inmutable y se publica mediante rename de un directorio temporal.
El hash incorpora entradas, corte, generación, versión y hash de implementación. La misma
ejecución offline fijada se reutiliza; una nueva ejecución crea otra versión.
HTML sin dependencias remotas, con escape de contenido, filtro de estados,
tablas por mercado y trazabilidad. JSON conserva null y causas. No se escriben
`data/`, journals OOS ni reportes anteriores.

## Validación y evidencia

Ver `selected-analysis-validation.json` y `selected-analysis-validation.md` para
las ejecuciones efectivamente realizadas, conteos finales, integridad y límites.
La suite completa necesita el entorno científico existente de qualityMind más
requests ya instalado en Match Goals; no se instaló ninguna dependencia nueva.

Las pruebas antiguas de protección se ajustaron para aceptar únicamente el
parche exacto de presentación de `compare_lambda.py`: cualquier cambio numérico
o cualquier otro archivo protegido sigue fallando. El hash AST del bloque
estadístico se compara con el obtenido de `df52aa8`.
**El gate operacional `v3.ops.integrity.champion_integrity()` no se modificó y
sigue retornando false mientras este parche difiera de `origin/main`.** La
prueba de ese gate verifica expresamente su rechazo; pasar la suite no declara
un release listo ni elimina el bloqueo. `v3/ops/`, OOS y promoción permanecen
idénticos al estado inicial. Resolver el diff operativo requiere el proceso
habitual de revisión/integración, fuera de esta ejecución sin commit.

```bash
.venv/bin/python -m compileall -q v3 tests/v3
PYTHONPATH="$PWD/.venv/lib/python3.12/site-packages" \
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
/home/leos/projects/qualityMind-ML/.venv/bin/python -m pytest -q tests/v3 -W error
git diff --check
git status --short
```

## Roadmap de evidencia real

1. Captura histórica permitida por competición/temporada, con cobertura FT/1H/2H,
   IDs persistentes, semántica y registro de publicaciones/revisiones verificadas.
   Extender adquisición a últimos 5/10/20 de ambos equipos con un plan de cuota
   explícito; no hacer scraping implícito desde el análisis.
2. Auditar muestras y missingness; reglas de selección y categorías de tarjetas
   por fuente/mercado. Confirmar scope de actor y componentes de segunda amarilla.
3. Backtesting temporal de los modelos independientes de córners/tarjetas,
   Poisson/NB y baselines, con error por liga, venue y tamaño de muestra.
4. Calibración en partición independiente, reliability y Brier/LogLoss; conservar
   TEST sellado y los gates actuales. Ningún holdout sintético demuestra calidad real.
5. Registro prospectivo inmutable, settlement posterior acreditado y OOS único;
   la reconstrucción operacional nunca se convierte en predicción histórica.
6. Cuotas opcionales por fuente autorizada, pre-corte y con reconciliación exacta.
   Value y CLV sólo cuando sus evidencias estén acreditadas. Mantener NO_BET.
7. Mejorar reportes con comparaciones por liga, intervalos/uncertainty y más
   filtros cuando existan muestras reales; no completar paneles con probabilidades inventadas.
