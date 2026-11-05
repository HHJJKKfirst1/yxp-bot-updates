"""The older three-heading announcement must not collapse to one warning."""
import unittest
from cloud_rules_notice_coverage import balance_inventory


class Oct08InventoryTests(unittest.TestCase):
    def test_known_three_section_layout_keeps_every_balance_entry(self):
        notice = dict(gid='oct08-test', url='https://example.invalid/notice', contents=
            '[p]Update at 14:00 today (UTC+8).[/p]'
            '[h3]1. Partial Reverts of Last Season Changes[/h3][*]Fate A: changed.[/*]'
            '[h3]2. Card Adjustments[/h3][*]Card B: changed.[/*]'
            '[h3]3. Immortal Fate Adjustments[/h3][*]Fate C: changed.[/*]'
            '[h3]4. Bug Fixes (Some Already Hotfixed Early)[/h3][*]UI bug.[/*]')
        inventory = balance_inventory(notice)
        self.assertIsNone(inventory['extraction_error'])
        self.assertEqual([item['target'] for item in inventory['items']], ['Fate A', 'Card B', 'Fate C'])
        self.assertEqual(inventory['items'][-1]['kind'], 'immortal_fate')

    def test_unknown_or_reordered_headings_still_fail_closed(self):
        for contents in (
            '[h3]1. Partial Reverts of Last Season Changes[/h3][*]A[/*]'
            '[h3]2. New Systems[/h3][*]B[/*][h3]3. Immortal Fate Adjustments[/h3][*]C[/*]',
            '[h3]1. Card Adjustments[/h3][*]A[/*]'
            '[h3]2. Partial Reverts of Last Season Changes[/h3][*]B[/*]'):
            with self.subTest(contents=contents):
                inv = balance_inventory(dict(gid='x', url='https://example.invalid', contents=contents))
                self.assertEqual(inv['extraction_error'], 'balance_section_requires_review')


if __name__ == '__main__':
    unittest.main()
