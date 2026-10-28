"""Offline Git code gates and separately reported operational corpus drift."""
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import json

PROTECTED = ('scraper', 'analysis', 'main.py', 'v3/data', 'v3/features', 'v3/odds',
             'v3/value', 'v3/models', 'v3/calibration', 'v3/validation', 'v3/selection',
             'v3/paper', 'v3/performance', 'v3/operation')


def protected(path):
    return path == 'data' or path.startswith(('data/', 'analysis_backup_')) or any(path == r or path.startswith(r+'/') for r in PROTECTED)


def code_integrity():
    def names(*args):
        return subprocess.check_output(['git', *args], text=True).splitlines()
    branch = names('diff', '--name-only', 'origin/main...HEAD')
    worktree = names('diff', 'HEAD', '--name-only')
    untracked = names('ls-files', '--others', '--exclude-standard')
    # Uncommitted data is operational drift; committed data is always prohibited.
    violations = sorted({p for p in branch if protected(p)} | {p for p in worktree+untracked if protected(p) and not p.startswith('data/')})
    return dict(immutable_code_integrity='FAIL' if violations else 'PASS', protected_code_changed_files=violations)


def data_drift(baseline):
    before = {p:v for p,v in baseline['files'].items() if p.startswith('data/')}
    after = {}
    for p in Path('data').rglob('*'):
        if p.is_file():
            after[str(p)] = dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(), mtime_ns=p.stat().st_mtime_ns)
    changed = sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
    stamp = Path('v3_data/ops/batch-integrity-before.json')
    age = max(0, datetime.now(timezone.utc).timestamp()-stamp.stat().st_mtime) if stamp.exists() else None
    return dict(operational_data_drift_detected=bool(changed), operational_data_changed_files=changed,
                operational_data_baseline_age=age, operational_data_baseline_age_unit='seconds_since_inventory_mtime')


def champion_integrity():
    from .forecast import CHAMPION
    checkpoints = [json.loads(Path(f'docs/v3/models/checkpoint-5.{i}.json').read_text()) for i in range(1,7)]
    lineage = subprocess.check_output(['git','diff','origin/main','--name-only','--','docs/v3/models','analysis','v3/models'],text=True)
    return CHAMPION == 'J_BT_sin_temporada' and not lineage.strip() and all(c['champion']['operational_champion']=='BT0 / J_BT_sin_temporada' for c in checkpoints)
