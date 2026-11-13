# Evidencia final — análisis seleccionado

Baseline: **1.767 passed**, 122,88 s, `-W error`. Final: **1.814 passed**, 94,53 s; **47 pruebas nuevas**. Cero warnings, deprecations o notices reportados en el gate final. `compileall -q v3 tests/v3` y `git diff --check`: exit 0. No es un resultado de CI de GitHub.

**Release operativo bloqueado.** Los gates originales de integridad siguen rechazando el diff de presentación de `analysis/compare_lambda.py` contra `origin/main`. No se alteraron `v3/ops/`, OOS ni promoción. Las pruebas de protección permiten sólo el parche exacto autorizado y verifican que cambiar pesos o añadir código extra se rechace. Pasar tests no promueve un modelo ni acredita un release.

Regresión real `QilxV7k3`: original exit 1 por `None.__format__`; corregido exit 0. Los JSON estructurados completos son iguales, incluidos todos los métodos y `G_temporada=null`. El hash AST del bloque estadístico antes/después es `bc0fed8fd2e3c07344f50c450f2dd94488487d98e292a219046f920c54dafc10`.

Integridad: 88,059 archivos originales comparados; 0 ausentes; 0 archivos de datos con cambio de contenido. Único código previo cambiado: `analysis/compare_lambda.py`. Archivos de datos nuevos observados: 248. Los tres scripts locales previos conservan sus hashes.

Cobertura del paquete nuevo con instrumentación CPython `trace`: **713/931 líneas ejecutables, 76,58%**. Es cobertura de líneas de esa herramienta, no branch coverage ni una medición con coverage.py. El desglose y las líneas no ejecutadas están en el JSON. La suite cubre selección/IDs, mappings, cuotas, null, mitades/córners faltantes, tarjetas incompatibles, cortes, leakage, Champion, serialización/HTML y reproducibilidad.

HTML comprobado con Chromium/Playwright a 1440 y 390 px: filtro de estados correcto, cero page errors, cero HTTP y sin overflow horizontal. Capturas desktop/mobile inspeccionadas visualmente. Se corrigió un overflow encontrado en la primera inspección. Un sondeo exploratorio inicial de disponibilidad de Playwright emitió notices de cierre asíncrono; la validación final con ciclo completo del navegador terminó limpia.

## Reportes reales generados offline

| Partido | HTML | JSON |
| --- | --- | --- |
| QilxV7k3 | [Abrir](../../v3_data/selected_analysis/2026-11-06/flashscore_QilxV7k3/8f379d3a65af4941c583489149db1f3b285c7a033b1aef89cfe9f66a4215febc/report.html) | [JSON](../../v3_data/selected_analysis/2026-11-06/flashscore_QilxV7k3/8f379d3a65af4941c583489149db1f3b285c7a033b1aef89cfe9f66a4215febc/report.json) |
| 0YxCHBec | [Abrir](../../v3_data/selected_analysis/2026-11-06/flashscore_0YxCHBec/2940cba435edbbbf1eb217ea78730675c4eb41c552d9bed111d4fea619df7380/report.html) | [JSON](../../v3_data/selected_analysis/2026-11-06/flashscore_0YxCHBec/2940cba435edbbbf1eb217ea78730675c4eb41c552d9bed111d4fea619df7380/report.json) |
| 0nSmIJV6 | [Abrir](../../v3_data/selected_analysis/2026-11-06/flashscore_0nSmIJV6/2f1447c29ce4c395ce6e8b2b77025ff30ea71b9beaf04708b6653f5f64f1751a/report.html) | [JSON](../../v3_data/selected_analysis/2026-11-06/flashscore_0nSmIJV6/2f1447c29ce4c395ce6e8b2b77025ff30ea71b9beaf04708b6653f5f64f1751a/report.json) |

Estos tres reportes usan historiales reales existentes; ninguna solicitud a proveedores externos. Goles FT operativos disponibles; mitades/córners/tarjetas bloqueados por identidad/linaje/semántica ausentes. Se conservan NO_BET y exclusión OOS. Son reconstrucciones offline con generación fijada para reproducibilidad, no predicciones prospectivas congeladas.

## Archivos creados

- `docs/v3/selected-analysis-validation.json`
- `docs/v3/selected-analysis-validation.md`
- `docs/v3/selected-analysis.md`
- `tests/v3/test_selected_analysis.py`
- `v3/selected_analysis/__init__.py`
- `v3/selected_analysis/cli.py`
- `v3/selected_analysis/compatibility.py`
- `v3/selected_analysis/counts.py`
- `v3/selected_analysis/engine.py`
- `v3/selected_analysis/evidence.py`
- `v3/selected_analysis/fixtures.py`
- `v3/selected_analysis/report.py`

## Archivos modificados

- `analysis/compare_lambda.py`
- `tests/v3/providers/test_api_football.py`
- `tests/v3/providers/test_selected_capture.py`
- `tests/v3/test_odds_audit.py`
- `tests/v3/test_ops_forecast.py`

Las cuatro modificaciones de tests antiguos ajustan la restricción de cero cambios heredados para permitir únicamente el arreglo de impresión solicitado. La lógica operacional de integridad sigue sin cambios.

No se instaló ninguna dependencia ni se ejecutó commit, push, PR o merge. [Guía, matrices, comandos y roadmap](selected-analysis.md). [Evidencia estructurada](selected-analysis-validation.json).
