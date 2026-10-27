# Final phases — offline operation

Rama exclusiva `feature/final-batch-6.1-9.2`. Software implementado, release real
BLOCKED. Los once checkpoints separan implementación de evidencia real. Issues
completas en [source-issues.json](source-issues.json); baseline registrado antes de editar.

```bash
python -m v3.operation.cli dry-run
python -m v3.operation.cli report
python -m v3.operation.cli synthetic-demo
python -m v3.selection.cli daily /tmp/candidates.json --synthetic-test-only
python -m v3.final_validation
```

`daily` espera un array JSON: target (date UTC/target_id/match/kickoff/cutoff/market/
selection/line), model (probability o vector home/draw/away, hash/status/partition
OOS/predicted_at/lineage), calibration manifest sellado por hash local, value_model
Phase 4, odds_observations canónicas, quality de los cinco componentes,
integrity_status y synthetic_test_only. Ver `v3.operation.pipeline.synthetic_candidate`
para un ejemplo generado offline con modelos ajustados sobre datos sintéticos.
Su resultado nunca es una predicción real deportiva.

APIs de calibración: `v3.calibration.engine.fit/transform/real_state`.
Walk-forward: `v3.validation.walkforward.run/folds`; promotion:
`v3.validation.promotion.evaluate`. No tuning desde TEST/OOS/paper.
Ledger: `v3.paper.ledger.Ledger.record/settle/events/positions`.
Performance: `v3.performance.analyzer.analyze`; gate:
`v3.performance.oos_gate.evaluate`. Handoff:
`v3.operation.handoff.Handoff.create/review`.

Runtime ignorado bajo v3_data/calibration, validation, selection, paper,
performance, operation. Inventario íntegro local en v3_data/operation, hashes/counts
compactos versionables en integrity-before/after.json. La demo usa subárbol v3_data
bajo /tmp y lo limpia al finalizar. El journal real vacío no se inventa ni se backfillea.
No claves ni llamadas externas; pytest bloquea sockets/DNS. Los archivos protegidos
incluyen cachés preexistentes: compile/test usan PYTHONPYCACHEPREFIX en /tmp para
no cambiar bytes ni mtimes en árboles read-only. El validador aplica esto internamente.

[Release manifest](release-manifest.json) incluye commit base y marca cambios no
commiteados; configs versionadas/hashes y estados explícitos. No representa release
publicado. [Roadmap](../roadmap-final.md) enumera exactamente los blockers restantes.
