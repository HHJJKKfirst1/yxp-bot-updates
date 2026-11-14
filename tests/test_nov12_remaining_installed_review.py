"""Review eight installed fixes without concealing the remaining conflict.

The old public ledger kept all nine entries pending after the accepted patch.
These checks bind the additional reviews to the installed-patch evidence and
preserve the unrelated official/client disagreement as a pending item in that
frozen review. The later user-selected announcement policy is checked by
test_five_elements_official_override.py and keeps the discrepancy visible.
"""
import hashlib
import json
from copy import deepcopy
from pathlib import Path
import unittest

from cloud_rules_contract import checksum, validate_pack
from cloud_rules_notice_coverage import _review

ROOT = Path(__file__).resolve().parents[1]
REVIEWED = {
    '002-be08ff95ce097880', '004-951730f6ae09fd85', '008-cbd602361b5f7c8c',
    '021-b74ff7d391bd98eb', '024-144ac268f3c9fd54', '025-93fc29fc260df740',
    '028-f0f9ecc5b39186bc', '029-b7d4a3a6b595d168',
}
CONFLICT = '013-cdaf7f20108875c1'


def read(name):
    return json.loads((ROOT / name).read_text('utf8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RemainingInstalledReviewTests(unittest.TestCase):
    def test_new_exact_receipts_are_bound_to_installed_evidence(self):
        old = read('tests/notice_coverage_reviews_pre_patch_20261114.json')
        ledger = read('notice_coverage_reviews.json')
        path = ROOT / 'audits/2026-11-14-remaining-installed-review.json'
        audit = json.loads(path.read_text('utf8'))
        self.assertEqual(set(audit['items']), REVIEWED)
        self.assertEqual(audit['game_build_id'], 26660739)
        self.assertEqual(audit['gameplay_validation'], 'not_run')
        self.assertEqual((audit['offline_tests']['passed'], audit['offline_tests']['failed']), (94, 0))
        output = ROOT / audit['offline_tests']['output']
        self.assertEqual(digest(output), audit['offline_tests']['output_sha256'])
        expected_hashes = [digest(path), digest(output)] + list(audit['installed_test_sha256'].values())
        for key in sorted(REVIEWED):
            item = audit['items'][key]
            notice = ledger['notices'][item['gid']]
            self.assertNotIn(key, old['notices'][item['gid']]['items'])
            review = notice['items'][key]
            self.assertEqual(review['item_sha256'], item['item_sha256'])
            self.assertEqual(review['kind'], 'mechanism')
            self.assertEqual(review['engine_contract'], 'numeric-templates-6')
            self.assertEqual(review['minimum_assistant_version'], '1.1.356')
            self.assertEqual(review['evidence_sha256'], expected_hashes)

    def test_new_reviews_cannot_be_reused_for_changed_sources_or_items(self):
        ledger = read('notice_coverage_reviews.json')
        audit = read('audits/2026-11-14-remaining-installed-review.json')
        for key in REVIEWED:
            entry = audit['items'][key]
            notice = ledger['notices'][entry['gid']]
            inventory = {'gid': entry['gid'], 'source': notice['source'],
                         'balance_sha256': notice['balance_sha256']}
            item = {'item_id': key, 'item_sha256': entry['item_sha256']}
            self.assertIsNotNone(_review(ledger, inventory, item)[0])
            for part in ('source', 'balance_sha256'):
                changed = deepcopy(inventory); changed[part] += '-changed'
                self.assertIsNone(_review(ledger, changed, item)[0])
            changed = deepcopy(item); changed['item_sha256'] = '0' * 64
            self.assertIsNone(_review(ledger, inventory, changed)[0])

    def test_numeric_disagreement_is_not_removed_from_pending(self):
        ledger = read('tests/notice_coverage_reviews_pre_official_override_20261114.json')
        audit = read('audits/2026-11-14-remaining-installed-review.json')
        manifest = read('tests/manifest_pre_official_override_20261114.json')
        self.assertNotIn(CONFLICT, ledger['notices']['1849192144178065']['items'])
        self.assertIn(CONFLICT, audit['unresolved_items'])
        self.assertEqual(audit['five_elements_native_parameters'], [2, 3, 4])
        self.assertEqual(audit['five_elements_announcement_parameters'], [3, 4, 5])
        self.assertIn(CONFLICT, {row.get('item_id') for row in manifest['pending']})

    def test_new_rules_keep_executable_data_and_disclose_limitations(self):
        registry = read('registry.json')
        old = validate_pack(read('public/rules/2026.11.12.9.json'), registry)
        new = validate_pack(read('public/rules/2026.11.14.10.json'), registry)
        self.assertEqual((new['revision'], new['serial'], new['native_build_id']),
                         ('2026.11.14.10', 10, 26660739))
        for key in ('cards', 'fates', 'mechanism_cards', 'engine_contract'):
            self.assertEqual(old[key], new[key])
        notes = '\n'.join(row['message'] for row in new['client_notes'])
        self.assertIn('nov12_remaining_v356', notes)
        self.assertIn('uniform_random_v356', notes)
        self.assertIn('各以25%估算', notes)
        self.assertIn('真实概率尚未确认', notes)
        self.assertIn('2/3/4', notes)
        self.assertIn('3/4/5', notes)
        self.assertIn('仍列待核', notes)
        manifest = read('public/manifest.json')
        if manifest['serial'] == 10:
            self.assertEqual(manifest['sha256'], checksum(new))


if __name__ == '__main__':
    unittest.main()
