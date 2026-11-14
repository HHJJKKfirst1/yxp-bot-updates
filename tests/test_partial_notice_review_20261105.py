"""The original partial receipts remain source-bound and retain old gaps.

The later user-approved uniform estimate is checked separately; this frozen
fixture keeps all exact assertions about the original review unchanged.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = json.loads((ROOT / 'audits/2026-11-05-partial-notice-review.json').read_text('utf8'))
LEDGER = json.loads((ROOT / 'tests/notice_coverage_reviews_pre_patch_20261114.json').read_text('utf8'))


class PartialNoticeReviewTests(unittest.TestCase):
    def test_each_receipt_has_the_exact_audit_and_file_digests(self):
        expected_counts = {'1846018067928278': 19, '1847286114031033': 89, '1848557880481669': 27}
        sources = AUDIT['source_paths_and_sha256']
        self.assertTrue(all(re.fullmatch(r'[0-9a-f]{64}', h) for h in sources.values()))
        for gid, count in expected_counts.items():
            with self.subTest(gid=gid):
                receipt = LEDGER['notices'][gid]
                audit = AUDIT['notices'][gid]
                self.assertEqual(receipt['balance_sha256'], audit['balance_sha256'])
                self.assertEqual(len(audit['items']), count)
                # The Nov 5 receipt intentionally withheld 7119; Nov 14
                # verified the installed v6 fix with a separate exact audit.
                later = {'048-9afc786087da4ee8'} if gid == '1847286114031033' else set()
                self.assertEqual(set(receipt['items']), set(audit['items']) | later)
                for item_id, explanation in audit['items'].items():
                    row = receipt['items'][item_id]
                    self.assertEqual(row['item_sha256'][:16], item_id.split('-')[1])
                    self.assertEqual(row['kind'], 'mechanism')
                    self.assertEqual(row['engine_contract'], 'numeric-templates-5')
                    self.assertEqual(row['minimum_assistant_version'], '1.1.356')
                    self.assertEqual(row['evidence_sha256'], [sources[p] for p in explanation['evidence']])
                    self.assertTrue(explanation['scope'])

    def test_unknown_probability_stays_pending_after_installed_fix_is_reviewed(self):
        old = LEDGER['notices']['1847286114031033']['items']
        new = LEDGER['notices']['1848557880481669']['items']
        self.assertEqual(old['048-9afc786087da4ee8']['engine_contract'], 'numeric-templates-6')
        self.assertFalse(any(k.startswith('025-') for k in new))
        limits = '\n'.join(AUDIT['limits'])
        self.assertIn('randomly triggered battle effect remains unsupported', limits)
        self.assertIn('probabilities remain unverified', limits)

    def test_dream_brush_receipt_only_claims_the_earlier_grant(self):
        rows = AUDIT['notices']['1847286114031033']['items']
        row = next(v for k, v in rows.items() if k.startswith('033-'))
        self.assertIn('only the announced earlier round and paid grant', row['scope'])


if __name__ == '__main__':
    unittest.main()
