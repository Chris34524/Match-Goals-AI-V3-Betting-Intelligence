"""Read-only fingerprints; no chmod, touch, backup or writes in evidence paths."""
import hashlib
from pathlib import Path
from .contract import digest


def protected_roots():
    roots = ['data','scraper','analysis','main.py','v3/data','v3/features',
             'v3/odds','v3/value','docs/v3/odds','docs/v3/value']
    roots += [str(p) for p in Path('.').glob('analysis_backup_*')]
    roots += [str(p) for p in Path('docs/v3').iterdir() if p.name not in
              ('models','odds','value','phase-5-final.md','phase-5-validation-report.json')]
    return roots


def capture(roots):
    files = {}
    for name in roots:
        p = Path(name)
        for f in sorted(p.rglob('*')) if p.is_dir() else [p]:
            if f.is_file() and '__pycache__' not in f.parts:
                if f.is_symlink():
                    raise ValueError('protected_symlink')
                files[str(f)] = dict(sha256=hashlib.sha256(f.read_bytes()).hexdigest(),mtime_ns=f.stat().st_mtime_ns)
    return files


def summarize(files):
    groups = {}
    for name,entry in files.items():
        parts = Path(name).parts
        key = '/'.join(parts[:2]) if parts[0] in ('v3','docs') else parts[0]
        groups.setdefault(key,{})[name] = entry
    return {k:dict(files=len(v),content_hash=digest({p:e['sha256'] for p,e in v.items()}),
                   mtime_hash=digest({p:e['mtime_ns'] for p,e in v.items()})) for k,v in groups.items()}


def verify(before, after, groups, mtime=False):
    for name in groups:
        if name not in before or name not in after:
            raise ValueError('missing_integrity_group:'+name)
        keys = ('files','content_hash','mtime_hash') if mtime else ('files','content_hash')
        if any(before[name][key] != after[name][key] for key in keys):
            raise ValueError('protected_artifact_changed:'+name)
