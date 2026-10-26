"""Evidence-only inspection of already stored HTML; never fetches or follows URLs.

Returns DOM cell references, not canonical snapshots or accredited timestamps.
Analytics identifiers are not interpreted as clocks. No collector is provided.
"""
from html.parser import HTMLParser
import re


class OddsCellInventory(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells = []
        self.cell = None
        self.value_parts = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'button' and attrs.get('data-testid') == 'wcl-oddsCell':
            self.cell = {
                'bookmaker_id': attrs.get('data-analytics-bookmaker-id'),
                'market_selection_label': attrs.get('data-analytics-label'),
                'live_attribute': attrs.get('data-live'),
                'removed_attribute': attrs.get('data-removed'),
                'displayed_price': None,
                'snapshot_type': 'unknown',
                'observed_at': None,
                'source_published_at': None,
                'accredited': False,
            }
        if self.cell is not None and tag == 'span' and attrs.get('data-testid') == 'wcl-oddsValue':
            self.value_parts = []

    def handle_data(self, data):
        if self.value_parts is not None:
            self.value_parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'span' and self.value_parts is not None:
            value = ''.join(self.value_parts).strip()
            if re.fullmatch(r'\d+\.\d+', value):
                self.cell['displayed_price'] = value
            self.value_parts = None
        if tag == 'button' and self.cell is not None:
            self.cells.append(self.cell)
            self.cell = None
            self.value_parts = None


def inspect_local_html(text):
    parser = OddsCellInventory()
    parser.feed(text)
    parser.close()
    return parser.cells
