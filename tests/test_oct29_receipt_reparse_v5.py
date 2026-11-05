"""A reviewed historical gift must not become a fresh numeric-card warning."""
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from cloud_rules_notice_coverage import balance_inventory
from cloud_rules_publisher import monitor

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/1847920302233330'
NOTICE = dict(gid='1847920302233330', title='Update on Oct. 29', date=1793242934, url=SOURCE,
    contents='[p]Update at 14:00 today (UTC+8).[/p][h1]Balance Adjustment[/h1]'
    '[h2]Immortal Fate Adjustments[/h2][list][*][p]Jade Scroll of Yin Symbol: '
    'gain 2 cards at round 12.[/p][/*][/list]')


class Oct29ReviewedReparseTests(unittest.TestCase):
    def run_case(self, notice, receipt_notice=NOTICE, contract='numeric-templates-4'):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            shutil.copytree(ROOT / 'public', base / 'public')
            shutil.copy2(ROOT / 'registry.json', base / 'registry.json')
            manifest_path = base / 'public/manifest.json'
            manifest = json.loads(manifest_path.read_text('utf8'))
            manifest.update(accepted_notices={}, pending=[], baseline_notice_date=0)
            manifest.pop('announcement_coverage', None)
            manifest_path.write_text(json.dumps(manifest), encoding='utf8')
            inv = balance_inventory(receipt_notice)
            receipts = {item['item_id']: dict(item_sha256=item['item_sha256'], kind='mechanism',
                engine_contract=contract, minimum_assistant_version='1.1.356',
                evidence_sha256=['a' * 64]) for item in inv['items']}
            ledger = dict(schema=1, notices={inv['gid']: dict(source=inv['source'],
                balance_sha256=inv['balance_sha256'], items=receipts)})
            (base / 'notice_coverage_reviews.json').write_text(json.dumps(ledger), encoding='utf8')
            feed = json.dumps({'appnews': {'newsitems': [notice]}}).encode('utf8')
            with patch('cloud_rules_publisher.observations_for_page', return_value=[]):
                return monitor(base, reader=lambda _: feed,
                    now=datetime(2026, 11, 5, 15, tzinfo=timezone.utc))

    def test_exact_oct29_contract_four_gift_does_not_raise_numeric_warning_in_v5(self):
        status = self.run_case(NOTICE)
        self.assertNotIn('notice_needs_specific_adapter', [x['reason'] for x in status['pending']])
        report = status['announcement_coverage']['notices'][NOTICE['gid']]
        self.assertTrue(report['fully_reviewed'])
        self.assertEqual(report['items'][0]['review']['engine_contract'], 'numeric-templates-4')
        self.assertEqual(status['changed_native_ids'], [])

    def test_changed_notice_or_unrelated_old_receipt_remains_pending(self):
        changed = dict(NOTICE, contents=NOTICE['contents'].replace('gain 2 cards', 'gain 3 cards'))
        other = dict(NOTICE, gid='1847920302233331', url=SOURCE + '-other')
        for notice, prior, contract in [(changed, NOTICE, 'numeric-templates-4'),
                                        (other, other, 'numeric-templates-4'),
                                        (NOTICE, NOTICE, 'numeric-templates-99')]:
            with self.subTest(gid=notice['gid'], contract=contract):
                status = self.run_case(notice, prior, contract)
                self.assertIn('notice_needs_specific_adapter', [x['reason'] for x in status['pending']])
                self.assertEqual(status['changed_native_ids'], [])


if __name__ == '__main__':
    unittest.main()
