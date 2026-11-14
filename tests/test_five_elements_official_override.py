"""A user-selected official rule can be reviewed without hiding the mismatch.

The previous review kept this item pending because the game client and the
announcement disagreed. This receipt requires the new assistant patch, binds
the exact announcement, and labels the chosen override and untested server.
"""
import hashlib
import json
from copy import deepcopy
from pathlib import Path
import unittest

from cloud_rules_contract import checksum, validate_pack
from cloud_rules_notice_coverage import _review

ROOT = Path(__file__).resolve().parents[1]
GID = '1849192144178065'
ITEM = '013-cdaf7f20108875c1'


def read(path):
    return json.loads((ROOT / path).read_text('utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FiveElementsOfficialOverrideTests(unittest.TestCase):
    def test_selected_rule_has_explicit_client_difference_and_patch_evidence(self):
        previous = read('tests/notice_coverage_reviews_pre_official_override_20261114.json')
        ledger = read('notice_coverage_reviews.json')
        audit_path = ROOT / 'audits/2026-11-14-five-elements-official-override.json'
        audit = json.loads(audit_path.read_text('utf8'))
        self.assertNotIn(ITEM, previous['notices'][GID]['items'])
        self.assertEqual(audit['policy'], 'user_explicitly_selected_official_announcement')
        self.assertEqual(audit['selected_parameters'], [3, 4, 5])
        self.assertEqual(audit['announcement_parameters'], [3, 4, 5])
        self.assertEqual(audit['client_parameters'], [2, 3, 4])
        self.assertEqual(audit['game_build_id'], 26660739)
        self.assertEqual(audit['gameplay_validation'], 'not_run')
        self.assertEqual(audit['required_patch'], 'five_elements_official_v356')
        summary = ROOT / audit['test_output']
        self.assertEqual(sha(summary), audit['test_output_sha256'])
        review = ledger['notices'][GID]['items'][ITEM]
        self.assertEqual(review['item_sha256'], audit['item_sha256'])
        self.assertEqual(review['evidence_sha256'], [sha(audit_path), sha(summary), audit['test_file_sha256']])
        self.assertEqual(review['engine_contract'], 'numeric-templates-6')

    def test_changed_announcement_cannot_reuse_the_receipt(self):
        ledger = read('notice_coverage_reviews.json')
        audit = read('audits/2026-11-14-five-elements-official-override.json')
        notice = ledger['notices'][GID]
        inventory = {'gid': GID, 'source': notice['source'], 'balance_sha256': notice['balance_sha256']}
        item = {'item_id': ITEM, 'item_sha256': audit['item_sha256']}
        self.assertIsNotNone(_review(ledger, inventory, item)[0])
        changed = deepcopy(item); changed['item_sha256'] = '0' * 64
        self.assertIsNone(_review(ledger, inventory, changed)[0])
        changed = deepcopy(inventory); changed['balance_sha256'] += '-changed'
        self.assertIsNone(_review(ledger, changed, item)[0])

    def test_new_pack_preserves_rules_and_discloses_the_user_choice(self):
        registry = read('registry.json')
        old = validate_pack(read('public/rules/2026.11.14.10.json'), registry)
        new = validate_pack(read('public/rules/2026.11.14.11.json'), registry)
        self.assertEqual((new['revision'], new['serial']), ('2026.11.14.11', 11))
        self.assertEqual(checksum(new), '290bd8312be969792bcec1a8097b27e89c5a879f102ab20b7b0ce83093ed49c3')
        for field in ('cards', 'fates', 'mechanism_cards', 'engine_contract'):
            self.assertEqual(old[field], new[field])
        notes = '\n'.join(row['message'] for row in new['client_notes'])
        self.assertIn('官方公告3/4/5', notes)
        self.assertIn('游戏26660739代码为2/3/4', notes)
        self.assertIn('实战可能不同', notes)
        self.assertIn('five_elements_official_v356', notes)
        manifest = read('public/manifest.json')
        self.assertNotIn(ITEM, {row.get('item_id') for row in manifest['pending']})
        if manifest['serial'] == 11:
            self.assertEqual(manifest['sha256'], checksum(new))


if __name__ == '__main__':
    unittest.main()
