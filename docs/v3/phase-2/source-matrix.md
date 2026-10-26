# Fuentes P1 — 2.7

La matriz [JSON](source-matrix.json) se genera con `python -m v3.features.source_matrix`.
La API `ingestion_allowed(provider, family)` falla cerrada. Sus 24 filas cubren
12 familias, con una fila de archivo Flashscore y otra de proveedor futuro por
familia. No hay proveedores de ingesta habilitados. `review` no concede permiso;
`planned` tampoco significa que exista proveedor seleccionado o contrato.

| Ámbito | Estado | Método actual | Para habilitar |
|---|---|---|---|
| Archivo Flashscore existente | review | auditoría local de sólo lectura | autorización expresa verificable de uso/automatización, identidades y timestamps |
| Proveedor oficial/licenciado sin seleccionar | planned | ninguno | contrato y alcance, IDs, publicaciones/revisiones históricas, límites operativos y retención |

Familias: advanced team stats, goalkeeper, players, lineups, injuries,
suspensions, cards, corners, news, context, manager changes y transfers.

La [inspección local](local-source-inspection.json) registra estructura de los
raw permitidos para auditoría, sin promover agregados ni textos a features.
Los snapshots TXT contienen alineación esperada, ratings promedio de competición,
bajas, entrenadores y previa; no acreditan XI oficial, publicación, jugador ID,
ledger de sanciones ni nombramiento del entrenador. No usar dorsales como IDs.
El inventario previo `docs/v3/surface-audit.json` distingue señales visibles y
adquisición: esta fase no vuelve a consultar términos ni afirma permisos nuevos.

Toda habilitación requiere revisar el alcance del permiso contra el método y
la familia, no sólo el nombre del proveedor. Deben quedar fijados por contrato
los límites de operación, paginación, revisiones, almacenamiento y eliminación.
No hay solicitudes de red, nuevos scrapers ni código para eludir controles.
