from v3.features.phase2_validation import fingerprint, reproduce
import pytest


def test_fingerprint_detects_content_change_but_ignores_python_caches(tmp_path):
    (tmp_path/'source').write_bytes(b'first')
    before = fingerprint(tmp_path)
    cache=tmp_path/'__pycache__';cache.mkdir();(cache/'module.pyc').write_bytes(b'cache')
    assert fingerprint(tmp_path)==before
    (tmp_path/'source').write_bytes(b'second')
    assert fingerprint(tmp_path)['content_sha256'] != before['content_sha256']


def test_regression_runner_rejects_source_overlap_before_writing(tmp_path):
    with pytest.raises(ValueError): reproduce(tmp_path, tmp_path/'outputs', {})
    with pytest.raises(ValueError): reproduce(tmp_path/'data', tmp_path, {})
