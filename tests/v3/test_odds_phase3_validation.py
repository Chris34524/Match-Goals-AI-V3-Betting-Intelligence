"""Integrity checks must detect additions, content changes and mtime changes."""
import os
from v3.odds import phase3_validation as validation


def test_fingerprint_is_read_only_and_detects_changes(tmp_path,monkeypatch):
    monkeypatch.setattr(validation,'REPO',tmp_path)
    root=tmp_path/'data';root.mkdir()
    f=root/'synthetic.txt';f.write_text('first')
    baseline={'roots':{'data':{}}}
    stamp=f.stat().st_mtime_ns
    first=validation.fingerprints(baseline)
    assert first==validation.fingerprints(baseline)
    assert f.stat().st_mtime_ns==stamp
    os.utime(f,ns=(f.stat().st_atime_ns,stamp+1000))
    changed_mtime=validation.fingerprints(baseline)
    assert changed_mtime['data']['content_sha256']==first['data']['content_sha256']
    assert changed_mtime['data']['mtime_sha256']!=first['data']['mtime_sha256']
    f.write_text('second')
    assert validation.fingerprints(baseline)['data']['content_sha256']!=first['data']['content_sha256']
    (root/'new.txt').write_text('new')
    assert validation.fingerprints(baseline)['data']['files']==2
