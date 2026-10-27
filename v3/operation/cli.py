"""Offline dry-run/report/synthetic-demo. No credentials or HTTP clients."""
import argparse
import json
import tempfile
from .pipeline import current_report,demo


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['dry-run','report','synthetic-demo'])
    a=p.parse_args()
    if a.command=='synthetic-demo':
        with tempfile.TemporaryDirectory(prefix='v3-synthetic-') as root:result=demo(root)
    else:result=current_report()
    print(json.dumps(result,indent=2,sort_keys=True,allow_nan=False))

if __name__=='__main__':main()
