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

* Identidad: `partido` en objetos JSON por partido, aliases explícitos del
  contrato. Se contrastan todos los IDs y metadatos presentes. El directorio
  proporciona el identificador Flashscore; claims repetidos entre directorios
  bloquean ambas filas, sin emitir IDs duplicados ni seleccionar silenciosamente.
* `history.json.secciones`: se reconocen títulos `ÚLTIMOS PARTIDOS: <equipo>`
  y `ENFRENTAMIENTOS...`. Sólo se cuentan muestras parseadas, scores enteros,
  IDs únicos, fecha anterior al target y equipo verificable. Target, mismo día
  y futuro se excluyen y bloquean elegibilidad. Fechas desconocidas requieren
  revisión. Se exige `available_at` ISO con offset del artefacto; captura/mtime
  no acreditan disponibilidad. Sin kickoff fiable, disponibilidad debe ser
  estrictamente anterior al día objetivo. No se infiere offset desde `hora`.
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
* El `integridad_temporal.estado` distinto de OK bloquea la fila incluso con
  historias verificadas. OK por sí solo nunca acredita las fuentes.

JSON inválido, claves JSON repetidas, codificación ilegible y estructuras no
reconocidas producen revisión explícita. Se rechazan salidas que se solapen con
la raíz fuente y archivos de salida symlink; no se siguen directorios symlink.
El builder sólo escribe los tres archivos declarados dentro de output-dir.
No integra ni altera el pipeline operativo. Las salidas permanecen locales.

## Validación local de implementación

Build limitado a los primeros cinco directorios: cinco filas, cero elegibles;
cuatro REVIEW por disponibilidad temporal no acreditada y una ERROR por
contradicción de local/visitante en `00XSw78l/standings.json`. No se resolvió
el conflicto escogiendo un equipo arbitrariamente. Dos builds dieron el mismo
SHA-256 y se verificaron hash y mtime de los 45 archivos fuente sin cambios.
Los archivos de salida con enlaces duros también se rechazan para proteger fuentes.
