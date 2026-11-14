"""The official Nov 12 notice used a weekday, leaving all changes hidden.

Its Wednesday announcement and Thursday 14:00 UTC+8 text independently fix
the effective time; ambiguous, past and title-conflicting dates stay pending.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import unittest
from cloud_rules_publisher import notice_effective_at


def item(contents='Yi Xian will be update at 14:00 this Thursday (UTC+8)', title='Update on Nov. 12'):
    return dict(date=int(datetime(2026, 11, 11, 10, 18, 5, tzinfo=timezone.utc).timestamp()),
                title=title, contents=contents)


class Nov12EffectiveWeekdayTests(unittest.TestCase):
    def test_weekday_notice_uses_official_local_time(self):
        self.assertEqual(notice_effective_at(item()), datetime.fromisoformat('2026-11-12T14:00:00+08:00'))


    def test_weekday_notice_rejects_ambiguous_past_and_mismatched_dates(self):
        self.assertIsNone(notice_effective_at(item(title='Update on Nov. 13')))
        self.assertIsNone(notice_effective_at(item(contents='update at 14:00 this Tuesday (UTC+8)')))
        self.assertIsNone(notice_effective_at(item(contents='update at 14:00 this Thursday (UTC+8); update at 15:00 this Friday (UTC+8)')))
        self.assertIsNone(notice_effective_at(item(contents='update at 25:00 this Thursday (UTC+8)')))


    def test_bloodline_receipt_is_bound_to_current_installed_evidence(self):
        # The old publication left a correct +3 implementation pending because
        # the fix was not yet accepted. This receipt binds the installed source,
        # actual passing checks and exact original announcement item.
        root = Path(__file__).resolve().parents[1]
        audit_path = root / 'audits/2026-11-14-bloodline-installed-review.json'
        audit = json.loads(audit_path.read_text('utf8'))
        output = root / audit['offline_tests']['output']
        ledger = json.loads((root / 'notice_coverage_reviews.json').read_text('utf8'))
        notice = ledger['notices'][audit['notice_gid']]
        review = notice['items']['048-9afc786087da4ee8']
        digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(audit['native_mechanism_id'], 7119)
        self.assertEqual((audit['offline_tests']['passed'], audit['offline_tests']['failed']), (13, 0))
        self.assertEqual(digest(output), audit['offline_tests']['output_sha256'])
        self.assertEqual(notice['balance_sha256'], audit['balance_sha256'])
        self.assertEqual(review['item_sha256'], audit['item_sha256'])
        self.assertEqual(review['engine_contract'], 'numeric-templates-6')
        self.assertIn(digest(audit_path), review['evidence_sha256'])
        self.assertIn(digest(output), review['evidence_sha256'])
