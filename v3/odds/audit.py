"""Offline, read-only full-tree price-reference inventory, never an odds importer.

All regular files are hashed and scanned as bytes (including unknown extensions).
Symlinks are reported without traversal. Mentions are not accredited prices.
"""
import argparse
from collections import Counter
import hashlib
from pathlib import Path
import re

from .contract import canonical_json, FORBIDDEN
from .local_html import inspect_local_html

PATTERNS = {
    'odds': rb'\bodds\b|cuotas?|decimal_odds|fair_odds',
    'bookmaker': rb'bookmaker|bet365|pinnacle|betfair|\bb365[hcda]?\b',
    '1X2': rb'1x2|\bh2h\b|moneyline',
    'BTTS': rb'\bbtts\b|both.teams.to.score|ambos.marcan',
    'OVER_1_5': rb'over[_ /-]?1[._,]5|under[_ /-]?1[._,]5|[<>]1\.5',
    'OVER_2_5': rb'over[_ /-]?2[._,]5|under[_ /-]?2[._,]5|[<>]2\.5',
    'OVER_3_5': rb'over[_ /-]?3[._,]5|under[_ /-]?3[._,]5|[<>]3\.5',
    'totals': rb'over.?under|total.?goals|m[a\xc3\xa1]s.de|menos.de',
    'ASIAN_HANDICAP': rb'asian.?handicap|\bhandicap\b|\bah[hc]?\b',
    'CORNERS': rb'corners?|c[o\xc3\xb3]rners?',
    'CARDS': rb'cards?|tarjetas?',
    'opening': rb'opening|open_odds|cuota.apertura',
    'current': rb'current.?odds|pre.?match.?odds|cuota.actual',
    'closing': rb'closing|close_odds|cuota.cierre',
    'average': rb'average.?odds|avg.?odds|market.?average|\bavg[hcda]\b|\bavc[hcda]\b',
    'maximum': rb'maximum.?odds|max.?odds|market.?max|\bmax[hcda]\b',
    'consensus': rb'consensus|consenso',
    'dispersion': rb'dispersion|dispersi[o\xc3\xb3]n',
    'other_price': rb'\bprice\b|precio|prob[_ -]?impl[i\xc3\xad]cita|implied.?prob|overround|vig\b|\bclv\b|\bb[wb][hda]\b|\bwh[hda]\b|\bps[c]?[hda]\b',
    'timestamp': rb'observed_at|source_published_at|captured_at|timestamp|scraped_at|downloaded_at',
}
COMPILED = {k: re.compile(v, re.I) for k, v in PATTERNS.items()}


def audit_tree(root):
    """Return deterministic inventory; no writes, network, inference or mtime-as-time."""
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError('audit root must be a real directory')
    manifest, findings, skipped, counts = [], [], [], Counter()
    price_artifacts = []
    for p in sorted(root.rglob('*')):
        rel = p.relative_to(root).as_posix()
        if p.is_symlink():
            skipped.append({'path': rel, 'reason': 'symlink_not_followed'})
            continue
        if not p.is_file():
            continue
        before = p.stat()
        digest = hashlib.sha256()
        hits, examples = set(), {}
        # Fixed chunks avoid unbounded lines from minified JSON/HTML. Overlap
        # covers boundary-spanning field names; all bytes enter the digest once.
        tail = b''
        with p.open('rb') as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                scan = tail + chunk
                for key, pattern in COMPILED.items():
                    match = pattern.search(scan)
                    if match:
                        hits.add(key)
                        examples.setdefault(key, match.group().decode('utf-8', errors='replace'))
                tail = scan[-256:]
        after = p.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError('artifact changed during audit: ' + rel)
        entry = {'path': rel, 'sha256': digest.hexdigest(), 'size': before.st_size, 'mtime_ns': before.st_mtime_ns}
        manifest.append(entry)
        if p.suffix.lower() in ('.html', '.htm'):
            cells = inspect_local_html(p.read_text(encoding='utf-8', errors='replace'))
            if cells:
                price_artifacts.append({**entry, 'cells': cells})
        if hits:
            counts.update(hits)
            findings.append({**entry, 'signals': sorted(hits), 'examples': examples,
                             'classification': 'excluded_lineage_reference' if FORBIDDEN.search(rel) else 'unaccredited_reference',
                             'snapshot_type': 'unknown', 'accredited': False})
    return {'version': '3.1.0', 'files_scanned': len(manifest),
            'bytes_scanned': sum(e['size'] for e in manifest),
            'manifest_sha256': hashlib.sha256(canonical_json(manifest).encode()).hexdigest(),
            'manifest': manifest, 'skipped': skipped, 'price_artifacts': price_artifacts,
            'signal_file_counts': dict(sorted(counts.items())), 'findings': findings,
            'accredited_odds_records': 0,
            'note': 'Lexical discovery only. mtime is filesystem evidence, never publication/capture time; no automatic accreditation.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', default='data')
    args = parser.parse_args()
    print(canonical_json(audit_tree(args.root)), end='')
