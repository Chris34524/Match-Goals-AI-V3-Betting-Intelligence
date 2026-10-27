"""Deterministic snapshot of actual runtime evidence, never synthetic fixtures."""
from .runtime import ROOT, read, write
from . import oos, promotion, closing
from .prospective import tick


def report(*, persist=False):
    gate = oos.report()
    result = dict(version='ops-o02-o06-v1',
                  O02=read(ROOT/'capture-status.json',dict(implementation_status='PASS',real_status='NOT_PREPARED')),
                  O03=read(ROOT/'paper-status.json',dict(implementation_status='PASS',real_status='BLOCKED_NO_ELIGIBLE_MODEL_PREDICTION')),
                  O04=closing.report(),O05=gate,O06=promotion.recommend(gate,read(ROOT/'promotion-evidence.json')),
                  network=tick(),human_confirmation_required=True,automated_real_betting=False,
                  limitations=['No prospective evidence is inferred from synthetic or historical artifacts.',
                               'Real paper recording requires an accredited model adapter; original ledger remains fail-closed.',
                               'Current API has no accredited closing semantics.'],
                  next_command='python -m v3.ops.cli cycle --live')
    if persist:
        write(ROOT/'operational-cycle-report.json',result)
    return result
