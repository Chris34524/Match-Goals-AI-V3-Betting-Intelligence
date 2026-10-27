"""Hash chained append-only events, serialized with an exclusive filesystem lock.

Production creation uses the wall clock, never a caller supplied timestamp.
Injected clocks are confined to explicit synthetic mode. Runtime is under v3_data.
This journal detects edits; it is not an independently signed WORM service.
"""
import fcntl
import json
import os
from copy import deepcopy
from pathlib import Path
from datetime import datetime,timezone
from v3.calibration.contract import time,canonical,digest,sealed,verify,required
from v3.selection.policy import decide

VERSION='paper-fixed-1u-v1'


def identity(candidate):
    target=candidate['target']
    return digest({k:target[k] for k in ('internal_match_id','market','selection','line')})


class Ledger:
    def __init__(self,path='v3_data/paper/ledger.jsonl',*,synthetic_test_only=False,clock=None):
        self.path=Path(path)
        if 'v3_data' not in self.path.parts or 'paper' not in self.path.parts:raise ValueError('runtime_must_be_v3_data_paper')
        if clock is not None and not synthetic_test_only:raise ValueError('production_clock_not_injectable')
        self.synthetic=synthetic_test_only
        self.clock=clock or (lambda:datetime.now(timezone.utc).isoformat())

    def _safe(self):
        if any(p.is_symlink() for p in [self.path,*self.path.parents]):raise ValueError('unsafe_ledger_path')
        if self.path.exists() and self.path.stat().st_nlink!=1:raise ValueError('unsafe_ledger_path')

    def events(self):
        self._safe()
        if not self.path.exists():return []
        result=[];previous=None;created=set();settled=set()
        for line in self.path.read_text().splitlines():
            event=json.loads(line);verify(event)
            if event['previous_hash']!=previous:raise ValueError('ledger_chain_broken')
            if event['synthetic_test_only'] is not self.synthetic:raise ValueError('ledger_mode_mismatch')
            bet=event['paper_bet_id']
            if event['event_type']=='CREATED':
                if bet in created:raise ValueError('duplicate_paper_bet')
                created.add(bet)
            elif event['event_type']=='SETTLED':
                if bet not in created or bet in settled:raise ValueError('invalid_settlement_event')
                settled.add(bet)
            else:raise ValueError('unknown_event')
            previous=event['hash'];result.append(event)
        return result

    def _append(self,builder):
        self._safe();self.path.parent.mkdir(parents=True,exist_ok=True)
        lock_path=self.path.with_suffix('.lock')
        if lock_path.is_symlink():raise ValueError('unsafe_ledger_lock')
        with lock_path.open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            events=self.events();event=builder(events)
            if events and time(event.get('created_at') or event.get('settled_at'))<time(events[-1].get('created_at') or events[-1].get('settled_at')):raise ValueError('ledger_clock_rollback')
            event.update(previous_hash=events[-1]['hash'] if events else None,version=VERSION,synthetic_test_only=self.synthetic)
            event=sealed(event)
            with self.path.open('a') as f:
                f.write(canonical(event)+'\n');f.flush();os.fsync(f.fileno())
            return deepcopy(event)

    def record(self,candidate):
        candidate=deepcopy(candidate)
        def build(events):
            decision=decide(candidate,allow_synthetic=self.synthetic)
            if decision['decision']!='PASS':raise ValueError('paper_requires_pass_candidate')
            now=self.clock();target=candidate['target'];v=decision['value']
            if not time(v['observed_at']) < time(target['cutoff']) <= time(now) < time(target['kickoff_at']):raise ValueError('paper_not_pre_kickoff')
            bet=identity(candidate)
            if any(e['paper_bet_id']==bet for e in events):raise ValueError('duplicate_paper_bet')
            out=dict(event_type='CREATED',paper_bet_id=bet,created_at=now,stake_units=1.0,status='OPEN',
                     decision='PASS',partition='OOS',real=not self.synthetic,eligible=True,backfilled=False,
                     temporal_lineage=candidate['model']['temporal_lineage'],decision_provenance=decision,
                     decimal_odds=v['market_odds'],observed_at=v['observed_at'],bookmaker=v['bookmaker'],provider=v['provider'],
                     settled_at=None,result=None,payout_units=None,profit_units=None,
                     model_version=candidate['value_model']['model_version'],calibration_version=candidate['calibration']['version'],
                     value_version=v['value_engine_version'],pickscore_version=decision['pickscore']['policy']['version'],
                     calibrated_probability=decision['calibrated_probability'],model_id=candidate['value_model']['model_id'])
            out.update({k:target[k] for k in ('internal_match_id','kickoff_at','market','selection','line','cutoff')})
            # Production recording stays closed with the current unaccredited Phase 5 inputs.
            if not self.synthetic:raise ValueError('real_paper_blocked_no_accredited_model_adapter')
            return out
        return self._append(build)

    def settle(self,paper_bet_id,*,result,completed_at,settlement_lineage,label=None,closing=None):
        def build(events):
            originals=[e for e in events if e['paper_bet_id']==paper_bet_id]
            if len(originals)!=1 or originals[0]['event_type']!='CREATED':raise ValueError('unknown_or_already_settled')
            created=originals[0];now=self.clock()
            if not time(created['kickoff_at'])<time(completed_at)<time(now):raise ValueError('settlement_not_post_event')
            if not settlement_lineage or result not in ('WIN','LOSS','VOID'):raise ValueError('settlement_invalid')
            if result!='VOID' and (type(label) is not int or label not in (0,1,2) or (created['market']!='1X2' and label==2)):raise ValueError('settlement_label_required')
            if result!='VOID':
                expected=(label==('home','draw','away').index(created['selection'])) if created['market']=='1X2' else (label==1)
                if (result=='WIN')!=expected:raise ValueError('result_label_mismatch')
            payout=created['decimal_odds'] if result=='WIN' else 1.0 if result=='VOID' else 0.0
            return dict(event_type='SETTLED',paper_bet_id=paper_bet_id,status='SETTLED',settled_at=now,
                        completed_at=completed_at,result=result,label=label,payout_units=payout,profit_units=payout-1,
                        settlement_lineage=settlement_lineage,settlement_accredited=True,created_hash=created['hash'],closing=deepcopy(closing))
        return self._append(build)

    def positions(self):
        positions={}
        for e in self.events():
            bet=e['paper_bet_id']
            if e['event_type']=='CREATED':positions[bet]=deepcopy(e)
            else:positions[bet].update({k:v for k,v in e.items() if k not in ('hash','previous_hash','event_type','created_hash')})
        return list(positions.values())
