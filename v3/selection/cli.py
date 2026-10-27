"""python -m v3.selection.cli daily INPUT.json [--synthetic-test-only]."""
import argparse
import json
from pathlib import Path
from .daily import daily


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['daily']);p.add_argument('input',type=Path);p.add_argument('--synthetic-test-only',action='store_true')
    a=p.parse_args();print(json.dumps(daily(json.loads(a.input.read_text()),allow_synthetic=a.synthetic_test_only),sort_keys=True,allow_nan=False,indent=2))

if __name__=='__main__':main()
