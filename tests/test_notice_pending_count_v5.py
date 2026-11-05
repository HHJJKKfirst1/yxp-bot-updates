"""One unreviewed balance entry should not also count as an extra notice."""
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from cloud_rules_publisher import monitor

ROOT = Path(__file__).resolve().parents[1]


class PendingCountTests(unittest.TestCase):
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
