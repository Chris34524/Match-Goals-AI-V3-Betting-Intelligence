"""Reviewable release inventory. Local baseline, no independent signature implied."""
import hashlib
import json
import subprocess
from pathlib import Path
from v3.calibration.contract import digest,sealed
from .pipeline import current_report

COMPONENTS=('calibration','validation','selection','paper','performance','operation')


GENERATION_HEAD_MEANING = "Existing Git HEAD at evidence generation; not the final containing commit."
SOURCE_IDENTITY = "source_digest is the canonical digest of source_hashes for the validated final modules."


def source_hashes(root=Path("v3")):
    return {str(f):hashlib.sha256(f.read_bytes()).hexdigest() for c in COMPONENTS for f in sorted((Path(root)/c).rglob('*.py'))}


def generation_worktree_state():
    status=subprocess.check_output(['git','status','--porcelain'],text=True)
    return 'DIRTY_PRECOMMIT' if status.strip() else 'CLEAN'


def manifest():
    files=source_hashes()
    state=current_report()
    baseline=json.loads(Path('docs/v3/final/integrity-before.json').read_text())
    from v3.calibration.contract import VERSION as calibration_version
    from v3.validation.promotion import POLICY as promotion_policy
    from v3.selection.pickscore import POLICY as score_policy
    from v3.selection.policy import POLICY as selection_policy
    from v3.performance.oos_gate import POLICY as oos_policy
    configs=dict(promotion=promotion_policy,pickscore=score_policy,selection=selection_policy,oos=oos_policy)
    return sealed(dict(version='v3-final-architecture-v2',generation_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                       generation_head_meaning=GENERATION_HEAD_MEANING,
                       generation_worktree_state=generation_worktree_state(),source_digest=digest(files),source_identity=SOURCE_IDENTITY,component_versions=dict(calibration=calibration_version,validation='expanding-distinct-utc-dates-v1',selection='daily-v1',paper='paper-fixed-1u-v1',performance='performance-v1',operation='operation-v1'),
                       config_hashes={c:digest(v) for c,v in configs.items()},configs=configs,
                       source_hashes=files,model_status='BLOCKED',calibration_status='BLOCKED',odds_status='BLOCKED',promotion_status='BLOCKED',
                       oos_count=0,release_status=state['release']['release_status'],reasons=state['release']['reason_codes'],
                       integrity_hashes=baseline['groups'],human_confirmation_required=True,automated_real_betting=False))
