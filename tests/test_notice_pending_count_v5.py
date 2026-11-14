"""One unreviewed balance entry should not also count as an extra notice."""
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from cloud_rules_publisher import monitor, notice_observations
from cloud_rules_notice_coverage import notice_coverage

ROOT = Path(__file__).resolve().parents[1]


class PendingCountTests(unittest.TestCase):
    def test_fate_and_bugfix_mentions_do_not_create_duplicate_card_warnings(self):
        # The Nov 12 parser counted a reviewed Spirit Cat fate twice, and
        # treated two card names in the bug-fix section as balance changes.
        registry = json.loads((ROOT / 'registry.json').read_text('utf8'))
        manifest = json.loads((ROOT / 'public/manifest.json').read_text('utf8'))
        pack = json.loads((ROOT / 'public' / manifest['rules']).read_text('utf8'))
        notice = dict(gid='fixture', title='Update on Nov. 12', date=1794392285,
            url='https://example.invalid/nov12', contents='[h1]Balance Adjustment[/h1]'
            '[h2]Immortal Fate Adjustments[/h2]'
            '[*]Heavenly Derivation - Spirit Cat Chaos Sword: Obtained at Round 11 → 10[/*]'
            '[*]Unreviewed Fate: gains an unknown card.[/*]'
            '[h1]4. Bug Fixes[/h1][*]Fix Ultimate Hexagram Base and Fury Thunder.[/*]')
        from cloud_rules_notice_coverage import balance_inventory
        inventory = balance_inventory(notice)
        first = inventory['items'][0]
        receipt = dict(item_sha256=first['item_sha256'], kind='mechanism',
            engine_contract=pack['engine_contract'], minimum_assistant_version='1.1.356',
            evidence_sha256=['a' * 64])
        ledger = dict(schema=1, notices={notice['gid']: dict(source=notice['url'],
            balance_sha256=inventory['balance_sha256'], items={first['item_id']: receipt})})
        coverage = notice_coverage(notice, numeric_check=lambda _: None,
            numeric_contract=pack['engine_contract'], numeric_minimum='1.1.356', receipts=ledger)
        observed, pending = notice_observations(notice, pack, registry, coverage=coverage)
        self.assertEqual(observed, [])
        self.assertEqual(pending, [])
        self.assertEqual(coverage['item_count'], 2)
        self.assertEqual(coverage['pending_count'], 1)
        self.assertEqual(coverage['pending'][0]['target'], 'Unreviewed Fate')

    def test_specific_unreviewed_entry_stays_pending_once(self):
        notice = dict(gid='1848557880481669', title='Update on Nov. 5', date=1793847299,
            url='https://example.invalid/notice', contents='[p]Update at 14:00 today (UTC+8).[/p]'
            '[h1]Balance Adjustment[/h1][h2]Immortal Fate Adjustments[/h2]'
            '[*]Unknown Fate: an unverified mechanic.[/*]')
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            shutil.copytree(ROOT / 'public', base / 'public')
            shutil.copy2(ROOT / 'registry.json', base / 'registry.json')
            path = base / 'public/manifest.json'
            manifest = json.loads(path.read_text('utf8'))
            manifest.update(accepted_notices={}, pending=[], baseline_notice_date=0)
            manifest.pop('announcement_coverage', None)
            path.write_text(json.dumps(manifest), encoding='utf8')
            feed = json.dumps({'appnews': {'newsitems': [notice]}}).encode('utf8')
            with patch('cloud_rules_publisher.observations_for_page', return_value=[]):
                status = monitor(base, reader=lambda _: feed,
                    now=datetime(2026, 11, 5, 15, tzinfo=timezone.utc))
        self.assertEqual(len(status['pending']), 1)
        self.assertEqual(status['pending'][0]['reason'], 'announcement_item_requires_review')
        self.assertEqual(status['pending'][0]['target'], 'Unknown Fate')


if __name__ == '__main__':
    unittest.main()
