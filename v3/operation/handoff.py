"""Immutable recommendation/review events. ACKNOWLEDGED records review or intention only."""
import json
from datetime import datetime,timezone
from pathlib import Path
from v3.calibration.contract import required,time,sealed,verify,canonical
from v3.selection.policy import decide

HUMAN_CONFIRMATION_REQUIRED=True
AUTOMATED_REAL_BETTING=False


class Handoff:
    def __init__(self,root='v3_data/operation/handoffs',*,synthetic_test_only=False,clock=None):
        self.root=Path(root)
        if 'v3_data' not in self.root.parts or 'operation' not in self.root.parts:raise ValueError('runtime_must_be_v3_data_operation')
        if clock is not None and not synthetic_test_only:raise ValueError('production_clock_not_injectable')
        if any(p.is_symlink() for p in [self.root,*self.root.parents]):raise ValueError('unsafe_handoff_path')
        self.synthetic=synthetic_test_only
        self.clock=clock or (lambda:datetime.now(timezone.utc).isoformat())

    def _write(self,path,record):
        if any(p.is_symlink() for p in [path,*path.parents]):raise ValueError('unsafe_handoff_path')
        self.root.mkdir(parents=True,exist_ok=True)
        with path.open('x') as f:f.write(canonical(record)+'\n')
        return record

    def create(self,candidate):
        decision=decide(candidate,allow_synthetic=self.synthetic)
        if decision['decision']!='PASS':raise ValueError('handoff_requires_pass')
        if not self.synthetic:raise ValueError('real_release_blocked')
        now=self.clock()
        if not time(candidate['target']['cutoff'])<=time(now)<time(candidate['target']['kickoff_at']):raise ValueError('handoff_not_pre_kickoff')
        out=sealed(dict(version='human-handoff-v1',candidate={k:candidate['target'][k] for k in ('internal_match_id','market','selection','line','kickoff_at')},
                        evidence=dict(decision_hash=decision['hash'],calibration_hash=candidate['calibration']['hash'],
                                      model_hash=candidate['model']['hash'],pickscore=decision['pickscore'],value=decision['value']),
                        reasons=decision['reason_codes'],created_at=now,review_status='PENDING',
                        synthetic_test_only=self.synthetic,human_confirmation_required=True,automated_real_betting=False))
        identifier=out['hash']
        return self._write(self.root/(identifier+'.json'),sealed(dict({k:v for k,v in out.items() if k!='hash'},recommendation_id=identifier)))

    def review(self,recommendation_id,*,review_status,reviewer):
        if len(recommendation_id)!=64 or any(c not in '0123456789abcdef' for c in recommendation_id):raise ValueError('invalid_recommendation_id')
        if review_status not in ('ACKNOWLEDGED','REJECTED') or not isinstance(reviewer,str) or not reviewer.strip():raise ValueError('invalid_human_review')
        path=self.root/(recommendation_id+'.json')
        if path.is_symlink():raise ValueError('unsafe_handoff_path')
        record=json.loads(path.read_text());verify(record)
        if record['synthetic_test_only'] is not self.synthetic:raise ValueError('handoff_mode_mismatch')
        now=self.clock()
        if time(now)<time(record['created_at']):raise ValueError('review_before_creation')
        event=sealed(dict(recommendation_id=recommendation_id,review_status=review_status,reviewer=reviewer,reviewed_at=now,
                          meaning='acknowledgement_intention_or_review_only',human_confirmation_required=True,
                          automated_real_betting=False,synthetic_test_only=self.synthetic))
        return self._write(self.root/(recommendation_id+'.review.json'),event)
