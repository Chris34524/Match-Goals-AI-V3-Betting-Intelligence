import hashlib
from pathlib import Path
import subprocess
import pytest
from v3.odds.audit import audit_tree, PATTERNS
from v3.odds.contract import canonical_json


def fingerprint(root):
    return {p.relative_to(root).as_posix():(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file() and not p.is_symlink()}


def test_audit_reads_all_formats_without_modifying_bytes_or_mtime(tmp_path):
    data=tmp_path/'data'; data.mkdir()
    (data/'archive.bin').write_bytes(b'bookmaker decimal_odds 1x2 btts over/under over_1_5 under_2_5 over_3_5 asian handicap opening current_odds closing average_odds maximum_odds consensus dispersion corners cards price observed_at')
    (data/'ordinary.json').write_text('{"team":"Synthetic"}')
    (data/'labels').mkdir(); (data/'labels/result.json').write_text('{"odds":2.0}')
    before=fingerprint(data)
    report=audit_tree(data)
    assert before==fingerprint(data)
    assert report['files_scanned']==3
    assert set(report['signal_file_counts'])==set(PATTERNS)
    assert report['accredited_odds_records']==0
    assert any(f['classification']=='excluded_lineage_reference' for f in report['findings'])
    assert all(f['snapshot_type']=='unknown' for f in report['findings'])
    assert canonical_json(report)==canonical_json(audit_tree(data))


def test_symlinks_not_followed(tmp_path):
    root=tmp_path/'data'; root.mkdir()
    target=tmp_path/'external'; target.write_text('odds')
    (root/'link').symlink_to(target)
    report=audit_tree(root)
    assert report['files_scanned']==0 and len(report['skipped'])==1
    with pytest.raises(ValueError): audit_tree(root/'link')


def test_chunk_boundary_and_unknown_extension(tmp_path):
    (tmp_path/'artifact.weird').write_bytes(b'x'*(1024*1024-4)+b' bookmaker odds '+b'\0')
    report=audit_tree(tmp_path)
    assert set(report['signal_file_counts'])=={'bookmaker','odds'}


def test_protected_tracked_paths_intact():
    root=Path(__file__).resolve().parents[2]
    changed=subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=root,text=True).splitlines()
    assert all(not p.startswith(('data/','scraper/','analysis/','analysis_backup_')) for p in changed)
    assert all('BT0' not in p and 'J_BT_sin_temporada' not in p for p in changed)


def test_local_html_price_evidence_is_not_a_timestamp_or_permission(tmp_path):
    from v3.odds.local_html import inspect_local_html
    html='''<button data-testid="wcl-oddsCell" data-analytics-bookmaker-id="book-a"
    data-analytics-label="odds_table-0-1x2_ft_1" data-live="false" data-removed="true"
    data-analytics-aff-id="b123_1788985222323_opaque">
    <span data-testid="wcl-oddsValue">2.10</span></button>'''
    cells=inspect_local_html(html)
    assert len(cells)==1
    cell=cells[0]
    assert cell['displayed_price']=='2.10' and cell['bookmaker_id']=='book-a'
    assert cell['snapshot_type']=='unknown' and cell['observed_at'] is None
    assert cell['source_published_at'] is None and not cell['accredited']
    assert cell['removed_attribute']=='true'
    (tmp_path/'stored.html').write_text(html)
    report=audit_tree(tmp_path)
    assert report['price_artifacts'][0]['cells']==cells
    assert report['accredited_odds_records']==0
