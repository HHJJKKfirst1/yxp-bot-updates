"""Only installed, independently checked Nov 12 deltas may leave pending."""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Nov12InstalledReviewTests(unittest.TestCase):
    def test_receipts_match_exact_source_items_and_audited_evidence(self):
        audit_path = ROOT / 'audits/2026-11-14-nov12-installed-review.json'
        audit = json.loads(audit_path.read_text('utf8'))
        ledger = json.loads((ROOT / 'notice_coverage_reviews.json').read_text('utf8'))
        notice = ledger['notices']['1849192144178065']
        expected = {1, 3, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20, 22, 23, 25, 26, 27}
        self.assertEqual({int(k.split('-')[0]) for k in notice['items']}, expected)
        self.assertEqual(set(notice['items']), set(audit['items']))
        self.assertEqual(notice['balance_sha256'], audit['balance_sha256'])
        self.assertEqual(notice['source'], audit['source'])
        digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        test = ROOT / audit['offline_tests']['test']
        output = ROOT / audit['offline_tests']['output']
        self.assertEqual((audit['offline_tests']['passed'], audit['offline_tests']['failed']), (15, 0))
        self.assertEqual(digest(test), audit['offline_tests']['test_sha256'])
        self.assertEqual(digest(output), audit['offline_tests']['output_sha256'])
        for key, row in notice['items'].items():
            self.assertEqual(row['item_sha256'], audit['items'][key]['item_sha256'])
            self.assertEqual(row['engine_contract'], 'numeric-templates-6')
            self.assertEqual(row['minimum_assistant_version'], '1.1.356')
            self.assertEqual(row['evidence_sha256'], [digest(audit_path), digest(test), digest(output)])

    def test_conflicting_and_not_yet_installed_items_remain_pending(self):
        ledger = json.loads((ROOT / 'notice_coverage_reviews.json').read_text('utf8'))
        rows = ledger['notices']['1849192144178065']['items']
        for number in (2, 4, 8, 13, 21, 24, 28, 29):
            self.assertFalse(any(int(k.split('-')[0]) == number for k in rows))
        old = ledger['notices']['1848557880481669']['items']
        self.assertFalse(any(k.startswith('025-') for k in old))
