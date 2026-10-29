"""Unknown fates must not disappear behind a 78-face numeric acceptance.

Before this component, accepted_notices skipped the entire source, unknown
bullets did not become pending, and one recognized number hid extra mechanics.
All old assertions remain intact; these cases inspect the added complete scope.
"""
import json
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from cloud_rules_contract import checksum
from cloud_rules_notice_coverage import balance_inventory, notice_coverage
from cloud_rules_publisher import monitor, notice_hash, notice_observations

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/1847920302233330'
NOTICE = dict(gid='1847920302233330', title='Synthetic balance fixture', date=1793242934, url=SOURCE,
    contents='[p]Update at 14:00 today (UTC+8).[/p][h1]Balance Adjustment[/h1]'
    '[h2]Card Adjustments[/h2][list][*][p]Giant Elephant Spirit Sword: 3 ATK ×3 → 5 ATK ×3[/p][/*][/list]'
    '[h2]Immortal Fate Adjustments[/h2][list][*][p]Shared Pity: Lose 1 Cultivation and draw a card.[/p][/*]'
    '[*][p]The following Immortal Fates gain cards earlier:[/p][p]Gift Alpha, Gift Beta.[/p][/*][/list]')
NOW = datetime(2026, 10, 29, 8, tzinfo=timezone.utc)


class NoticeCoverageTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT / 'registry.json').read_text('utf8'))
        self.manifest = json.loads((ROOT / 'public/manifest.json').read_text('utf8'))
        self.pack = json.loads((ROOT / 'public' / self.manifest['rules']).read_text('utf8'))

    def prepared(self, folder, accepted=False):
        public = folder / 'public'
        (public / 'rules').mkdir(parents=True)
        (folder / 'registry.json').write_text(json.dumps(self.registry), 'utf8')
        (public / 'rules/baseline.json').write_text(json.dumps(self.pack), 'utf8')
        manifest = dict(self.manifest, rules='rules/baseline.json', pending=[],
                        accepted_notices={NOTICE['gid']: notice_hash(NOTICE)} if accepted else {})
        manifest.pop('announcement_coverage', None)
        (public / 'manifest.json').write_text(json.dumps(manifest), 'utf8')
        return public

    def run_monitor(self, folder, notices=None, now=NOW):
        raw = json.dumps({'appnews': {'newsitems': [NOTICE] if notices is None else notices}}).encode('utf8')
        with patch('cloud_rules_publisher.observations_for_page', return_value=[]):
            return monitor(folder, reader=lambda url: raw, now=now)

    def report(self, notice=NOTICE, receipts=None, numeric=None):
        return notice_coverage(notice, numeric_check=numeric or (lambda body: None),
            numeric_contract='numeric-templates-3', numeric_minimum='1.1.329', receipts=receipts)

    def ledger(self, notice=NOTICE):
        inventory = balance_inventory(notice)
        items = {item['item_id']: dict(item_sha256=item['item_sha256'], kind='mechanism',
            engine_contract='immortal-fates-reviewed-1', minimum_assistant_version='1.1.356',
            evidence_sha256=['a' * 64]) for item in inventory['items']}
        return dict(schema=1, notices={notice['gid']: dict(source=notice['url'],
                    balance_sha256=inventory['balance_sha256'], items=items)})

    def test_all_subheadings_and_each_compound_target_are_inventoried(self):
        inventory = balance_inventory(NOTICE)
        self.assertIsNone(inventory['extraction_error'])
        self.assertEqual([x['target'] for x in inventory['items']],
            ['Giant Elephant Spirit Sword', 'Shared Pity', 'Gift Alpha', 'Gift Beta'])
        self.assertEqual([x['kind'] for x in inventory['items']],
            ['card', 'immortal_fate', 'immortal_fate', 'immortal_fate'])
        self.assertEqual(len({x['item_id'] for x in inventory['items']}), 4)

    def test_registered_numeric_success_does_not_accept_the_fates(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); public = self.prepared(folder)
            status = self.run_monitor(folder)
            coverage = status['announcement_coverage']
            self.assertEqual(coverage['latest_item_count'], 4)
            self.assertEqual(coverage['latest_reviewed_count'], 1)
            self.assertEqual(coverage['latest_pending_count'], 3)
            self.assertEqual({x['target'] for x in status['pending'] if 'item_id' in x},
                             {'Shared Pity', 'Gift Alpha', 'Gift Beta'})
            published = json.loads((public / 'manifest.json').read_text('utf8'))
            self.assertEqual(published['accepted_notices_scope'], 'registered_numeric_faces_only')
            self.assertEqual(published['supported_faces_scope'], 'registered_numeric_faces_only')
            self.assertEqual(published['coverage_state'], 'pending_review')
            self.assertEqual(published['announcement_coverage'], coverage)
            self.assertEqual(published['supported_faces'], 78)

    def test_preaccepted_notice_is_reinventoried_and_cannot_hide_unknown_fates(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); self.prepared(folder, accepted=True)
            status = self.run_monitor(folder)
            self.assertEqual(status['changed_native_ids'], [])
            self.assertEqual(status['announcement_coverage']['latest_item_count'], 4)
            self.assertEqual({p['target'] for p in status['pending'] if 'item_id' in p},
                             {'Giant Elephant Spirit Sword', 'Shared Pity', 'Gift Alpha', 'Gift Beta'})

    def test_unknown_pending_survives_repeat_and_notices_leaving_short_feed(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); self.prepared(folder)
            first = self.run_monitor(folder)
            second = self.run_monitor(folder)
            third = self.run_monitor(folder, [])
            self.assertEqual(second['pending'], first['pending'])
            self.assertEqual(third['pending'], first['pending'])
            self.assertEqual(third['coverage_state'], 'pending_review')

    def test_source_failure_preserves_pending_and_marks_coverage_unavailable(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); public = self.prepared(folder)
            first = self.run_monitor(folder)
            previous = json.loads((public / 'manifest.json').read_text('utf8'))
            def fail(url): raise OSError('offline')
            with patch('cloud_rules_publisher.observations_for_page', return_value=[]):
                result = monitor(folder, reader=fail, now=NOW)
            self.assertEqual(result['pending'], first['pending'])
            self.assertEqual(result['coverage_state'], 'source_unavailable')
            self.assertFalse(result['announcement_coverage']['source_available'])
            after = json.loads((public / 'manifest.json').read_text('utf8'))
            self.assertEqual(after['sha256'], previous['sha256'])
            self.assertEqual(after['serial'], previous['serial'])

    def test_mechanism_receipt_requires_exact_source_balance_item_and_evidence(self):
        ledger = self.ledger()
        report = self.report(receipts=ledger)
        self.assertEqual(report['pending'], [])
        self.assertEqual(report['reviewed_count'], 4)
        self.assertTrue(report['fully_reviewed'])
        self.assertEqual(report['items'][1]['review']['engine_contract'], 'immortal-fates-reviewed-1')
        self.assertNotIn('fully_supported', report)

    def test_wrong_source_does_not_borrow_receipt(self):
        report = self.report(dict(NOTICE, url='https://example.invalid/news'), self.ledger())
        self.assertEqual(report['reviewed_count'], 0)
        self.assertEqual({x['reason'] for x in report['pending']}, {'coverage_review_source_or_balance_changed'})

    def test_changed_mechanism_invalidates_whole_balance_receipt(self):
        notice = dict(NOTICE, contents=NOTICE['contents'].replace('Lose 1', 'Lose 2'))
        report = self.report(notice, self.ledger())
        self.assertEqual(report['reviewed_count'], 0)
        self.assertEqual(report['pending_count'], 4)

    def test_item_hash_and_contract_cannot_be_forged(self):
        for key, value in [('item_sha256', 'b' * 64), ('engine_contract', "__import__('os')"),
                           ('minimum_assistant_version', 'latest'), ('evidence_sha256', []),
                           ('evidence_sha256', ['not-a-digest']), ('kind', 'complete')]:
            with self.subTest(field=key, value=value):
                ledger = self.ledger()
                next(iter(ledger['notices'][NOTICE['gid']]['items'].values()))[key] = value
                report = self.report(receipts=ledger)
                self.assertEqual(report['reviewed_count'], 3)
                self.assertEqual(report['pending_count'], 1)

    def test_unknown_review_fields_are_not_evaluated_or_accepted(self):
        ledger = self.ledger()
        next(iter(ledger['notices'][NOTICE['gid']]['items'].values()))['python'] = 'raise RuntimeError()'
        report = self.report(receipts=ledger)
        self.assertEqual(report['pending_count'], 1)
        self.assertEqual(report['pending'][0]['reason'], 'coverage_review_invalid')

    def test_activity_exclusion_requires_the_same_review_binding(self):
        ledger = self.ledger()
        next(iter(ledger['notices'][NOTICE['gid']]['items'].values()))['kind'] = 'activity_excluded'
        report = self.report(receipts=ledger)
        self.assertEqual(report['excluded_count'], 1)
        self.assertEqual(report['reviewed_count'], 3)
        self.assertEqual(report['pending_count'], 0)
        self.assertEqual(self.report()['excluded_count'], 0)

    def test_optional_list_terminators_do_not_collapse_changes(self):
        notice = dict(NOTICE, contents=NOTICE['contents'].replace('[/*]', ''))
        inventory = balance_inventory(notice)
        self.assertEqual([x['target'] for x in inventory['items']],
                         ['Giant Elephant Spirit Sword', 'Shared Pity', 'Gift Alpha', 'Gift Beta'])

    def test_numbered_balance_heading_still_inventories_the_complete_section(self):
        notice = dict(NOTICE, contents=NOTICE['contents'].replace('Balance Adjustment', '1. Balance Adjustment'))
        inventory = balance_inventory(notice)
        self.assertIsNone(inventory['extraction_error'])
        self.assertEqual([x['target'] for x in inventory['items']],
                         ['Giant Elephant Spirit Sword', 'Shared Pity', 'Gift Alpha', 'Gift Beta'])

    def test_unbulleted_paragraphs_are_separate_and_same_bullet_extra_mechanism_is_blocked(self):
        notice = dict(NOTICE, contents='[h1]Balance Adjustments[/h1]'
            '[p]Giant Elephant Spirit Sword: 3 ATK ×3 → 5 ATK ×3[/p][p]Shared Pity: new rule.[/p]')
        inventory = balance_inventory(notice)
        self.assertEqual(len(inventory['items']), 2)
        self.assertEqual(inventory['items'][1]['target'], 'Shared Pity')
        notice['contents'] = notice['contents'].replace('[p]Giant', '[*][p]Giant') + '[/*]'
        observed, pending = notice_observations(notice, self.pack, self.registry)
        self.assertEqual(observed, [])
        self.assertTrue(pending)

    def test_sibling_section_is_outside_explicit_balance_scope(self):
        notice = dict(NOTICE, contents=NOTICE['contents'] + '[h1]Outfits[/h1][p]New robe.[/p]')
        self.assertEqual(balance_inventory(notice), balance_inventory(NOTICE))

    def test_duplicate_or_missing_balance_heading_is_explicit_pending(self):
        for suffix, expected in [('[h1]Balance Adjustments[/h1]', 'balance_heading_ambiguous'),
                                  ('', 'balance_section_requires_review')]:
            notice = dict(NOTICE, contents=NOTICE['contents'] + suffix if suffix else '[h1]New systems[/h1][p]Changed.[/p]')
            report = self.report(notice)
            self.assertEqual(report['pending'][0]['reason'], expected)
            self.assertFalse(report['fully_reviewed'])

    def test_card_qualification_containing_immortal_fate_is_still_a_card(self):
        notice = dict(NOTICE, contents='[h1]Balance Adjustments[/h1]'
            '[p]Wind-Riding Flash (Lingyu Immortal Fate exclusive card, Immortality Phase): changed.[/p]')
        self.assertEqual(balance_inventory(notice)['items'][0]['kind'], 'unknown')

    def test_prefix_is_kept_in_card_and_fate_names(self):
        notice = dict(NOTICE, contents='[h1]Balance Adjustments[/h1][p]Dream: Echo Formation: HP +4.[/p]'
            '[p]Mirage: Diligent Sword: changed.[/p][p]Ultimate: Finishing Touch: changed.[/p]')
        # Separate bullets are used in real announcements.
        notice['contents'] = notice['contents'].replace('[p]', '[*][p]').replace('[/p]', '[/p][/*]')
        self.assertEqual([x['target'] for x in balance_inventory(notice)['items']],
                         ['Dream: Echo Formation', 'Mirage: Diligent Sword', 'Ultimate: Finishing Touch'])

    def test_same_name_repeat_gets_distinct_identity(self):
        notice = dict(NOTICE, contents='[h1]Balance Adjustments[/h1][*]Shared Pity: change[/*][*]Shared Pity: change[/*]')
        items = balance_inventory(notice)['items']
        self.assertEqual(len(items), 2)
        self.assertNotEqual(items[0]['item_id'], items[1]['item_id'])

    def test_fate_cannot_inherit_a_card_alias_receipt(self):
        report = self.report(numeric=lambda body: [1000103])
        self.assertEqual(report['reviewed_count'], 1)
        self.assertEqual(report['pending_count'], 3)

    def test_known_number_plus_new_mechanism_never_enters_numeric_template(self):
        for extra in ['; gain another action', '; max HP +10', '; lose 1 Cultivation', '; cost no Qi']:
            with self.subTest(extra=extra):
                notice = dict(url=SOURCE, contents='Giant Elephant Spirit Sword: 3 ATK ×3 → 5 ATK ×3' + extra)
                observed, pending = notice_observations(notice, self.pack, self.registry)
                self.assertEqual(observed, [])
                self.assertEqual(pending[0]['reason'], 'notice_needs_specific_adapter')

    def test_different_multipliers_unknown_properties_and_duplicate_names_stay_pending(self):
        for content in ['Giant Elephant Spirit Sword: 3 ATK ×3 → 5 ATK ×4',
                        'Giant Elephant Spirit Sword: Qi 3 → 5',
                        'Giant Elephant Spirit Sword: 3 ATK ×3 → 5 ATK ×3\nGiant Elephant Spirit Sword: change']:
            with self.subTest(content=content):
                observed, pending = notice_observations(dict(url=SOURCE, contents=content), self.pack, self.registry)
                self.assertEqual(observed, [])
                self.assertTrue(pending)

    def test_future_effective_notice_does_not_publish_review_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); public = self.prepared(folder)
            result = self.run_monitor(folder, now=datetime(2026, 10, 29, 5, tzinfo=timezone.utc))
            self.assertEqual(result['pending'][0]['reason'], 'announced_rule_not_effective_yet')
            self.assertEqual(result['announcement_coverage']['latest_item_count'], 0)
            self.assertEqual(json.loads((public / 'manifest.json').read_text('utf8'))['sha256'], checksum(self.pack))

    def test_malformed_local_review_ledger_stays_pending(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); self.prepared(folder)
            (folder / 'notice_coverage_reviews.json').write_text('{bad json', 'utf8')
            report = self.run_monitor(folder)['announcement_coverage']['notices'][NOTICE['gid']]
            self.assertEqual(report['reviewed_count'], 0)
            self.assertEqual({p['reason'] for p in report['pending']}, {'coverage_ledger_invalid'})


if __name__ == '__main__':
    unittest.main()
