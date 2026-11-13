# Validación — prioridad Flashscore México

**1.832 pruebas aprobadas**, 87,82 s, con `-W error`; baseline anterior 1.814 y 18 casos nuevos. Cero warnings/deprecations/notices reportados por el gate final. Compilación y whitespace: exit 0. No es una ejecución CI de GitHub.

Los casos nuevos verifican lectura de xG/clasificación, ceros observados frente a null, identidad/orientación, duplicados, fechas target/mismo día/futuras, conflictos de caché, archivos opcionales inválidos, procedencia, ausencia de fallback y que modificar las observaciones no cambie ninguna predicción. El comando de auditoría rechaza live antes de construir un cliente.

Se reutilizan `audit_sources` y `xg_adapter.reconcile`, sin editar esos módulos, sin attestations fabricadas y sin activar extractores. `scraper/`, `v3/ops/`, modelos, providers, contratos Flashscore y gates conservan sus bytes de HEAD. La excepción previa de impresión de None sigue siendo la única diferencia heredada permitida. El gate operacional continúa cerrado por ese diff; aprobar pruebas no equivale a habilitar release.

Matriz persistida: 116 campos/familias sobre 6633 directorios. La primera lectura de esta sesión contenía 6.623 directorios; la segunda contiene 6.633. Hay un pipeline heredado concurrente: los conteos de la lectura secuencial no son un snapshot transaccional ni valores deportivos acreditados.

Se generaron dos reportes reales desde archivos locales. Cero solicitudes deportivas/API desde el analizador. El sitio mexicano y sus condiciones/FAQ se consultaron como documentación pública; no se recapturaron páginas de estadísticas. HTML validado a 1440 y 390 px, sin overflow horizontal, sin page errors ni solicitudes HTTP externas; filtro correcto y capturas inspeccionadas.

| Partido | HTML | JSON |
| --- | --- | --- |
| QilxV7k3 | [Abrir](../../../v3_data/selected_analysis/2026-11-06/flashscore_QilxV7k3/b5aa745e60a965b2c0384e4a45bb15c7379baa4be3d3aedeece689b76f9e66b9/report.html) | [JSON](../../../v3_data/selected_analysis/2026-11-06/flashscore_QilxV7k3/b5aa745e60a965b2c0384e4a45bb15c7379baa4be3d3aedeece689b76f9e66b9/report.json) |
| pMxurfFb | [Abrir](../../../v3_data/selected_analysis/2026-11-06/flashscore_pMxurfFb/b6b31687b8c91dfd056b0ae96f56fd43b901377c9d87c389b4128b563f8743b5/report.html) | [JSON](../../../v3_data/selected_analysis/2026-11-06/flashscore_pMxurfFb/b6b31687b8c91dfd056b0ae96f56fd43b901377c9d87c389b4128b563f8743b5/report.json) |

Ejemplo pMxurfFb: xG observado local L5=1,472 (n=5) y visitante L5=1,352 (n=5). En L10 hay n=9/n=8: cobertura 90%/80%, sin rellenar ni buscar partidos antiguos adicionales. Estas medias se muestran como `OBSERVED_UNACCREDITED`; periodo/captura son null y `eligible_for_model=false`. xG/xGA acreditados para el modelo siguen ausentes. QilxV7k3 conserva los xG ausentes como null y muestra su clasificación archivada sin atribuirle disponibilidad prepartido.

## Archivos de esta ampliación

| Acción | Archivo |
| --- | --- |
| Creado | `v3/selected_analysis/flashscore_reference.py` |
| Creado | `tests/v3/test_flashscore_mx_reference.py` |
| Creado | `docs/v3/flashscore/mx-coverage-audit.md` |
| Creado | `docs/v3/flashscore/mx-coverage-audit.json` |
| Creado | `docs/v3/flashscore/mx-priority-validation.md` |
| Creado | `docs/v3/flashscore/mx-priority-validation.json` |
| Modificado | `v3/selected_analysis/cli.py` |
| Modificado | `v3/selected_analysis/engine.py` |
| Modificado | `v3/selected_analysis/report.py` |
| Modificado | `docs/v3/selected-analysis.md` |
| Modificado | `docs/v3/selected-analysis-validation.md` |

La modificación de `selected-analysis-validation.md` corrige únicamente los acentos dañados por el encoding de PowerShell en su generación anterior. Los archivos de código/HTML UTF-8 no estaban dañados. La documentación nueva también se revisó para eliminar esos marcadores de sustitución.

No se ejecutó commit, push, PR, merge ni instalación de dependencias. Se mantiene NO_BET, sin nuevos modelos entrenados, calibración ni evidencia OOS. [Matriz y limitaciones](mx-coverage-audit.md). [Evidencia JSON](mx-priority-validation.json).
