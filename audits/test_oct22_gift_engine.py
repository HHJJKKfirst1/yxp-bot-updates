"""Pinned current native gift and pool examples, exercised offline."""
from pathlib import Path
import os
import sys
import unittest

ROOT = Path(os.environ['YXP_AUDIT_ENGINE_ROOT']).resolve()
sys.path.insert(0, str(ROOT / 'joint_repair_artifacts'))
sys.path.append(str(ROOT))

# The current native config includes later Nov05 changes; expected values are
# explicit current card IDs, rounds and counts, not evaluator-derived values.
POOL_WITH_PITY = [
    (17059, 141, 8, 13), (17081, 193, 8, 10), (17091, 152, 8, 12),
    (17082, 196, 8, 12), (17028, 413, 6, 12), (17085, 201, 8, 9),
    (17089, 144, 8, 9), (17086, 205, 8, 9), (17065, 437, 3, 12),
    (17052, 418, 3, 12), (17021, 139, 6, 8), (17095, 419, 6, 12),
    (6009, 55, 8, 9), (6014, 337, 8, 9),
]
GIFT_WITH_ORBS = [
    (17058, 400, 3, 12), (17003, 124, 2, 12), (17006, 388, 4, 12),
    (17012, 389, 3, 12), (17011, 131, 3, 12), (17097, 455, 2, 12),
    (17018, 390, 2, 12), (17024, 392, 2, 11), (17025, 401, 1, 14),
]


class Oct22GiftEngineTests(unittest.TestCase):
    def test_reversible_gifts_respect_current_round_and_actual_pool_debit(self):
        from baijia_transform import grant
        for sid, cid, due in [(17043, 1000033, 4), (17045, 4000043, 6)]:
            with self.subTest(sid=sid):
                state = dict(mechanisms=[sid], round=due - 1, cultivation=10,
                             hand=[], pool={str(cid): 1})
                self.assertEqual(grant(sid, state)['hand'], [])
                result = grant(sid, dict(state, round=due))
                self.assertEqual((result['cultivation'], result['pool'][str(cid)]), (9, 0))
                self.assertEqual([row['card_id'] for row in result['hand']], [cid])

    def test_pool_addition_and_later_paid_draw_request(self):
        from baijia_preparation_events import apply
        for sid, cid, copies, due in POOL_WITH_PITY:
            with self.subTest(sid=sid):
                initial = dict(mechanisms=[sid], round=1, realm=5, cultivation=20,
                               hand=[], board=[], pool={str(cid): 0})
                selected = apply(sid, initial, 'selection')
                self.assertEqual(selected['pool'][str(cid)], copies)
                self.assertEqual(initial['pool'][str(cid)], 0)
                early = apply(sid, dict(selected, round=due - 1), 'round_start')
                self.assertNotIn('automatic_draw_requests', early)
                ready = apply(sid, dict(selected, round=due), 'round_start')
                self.assertEqual(ready['automatic_draw_requests'], [dict(strategy_id=sid, card_id=cid,
                    count=1, cultivation_cost=1, native_pool_debit=1, requires_realm=False,
                    authorizes_input=False, requires_actual_native_result=True)])
                self.assertEqual(ready['cultivation'], 20)
                self.assertEqual(ready['hand'], [])
                self.assertEqual(ready['pool'][str(cid)], copies)

    def test_scheduled_gifts_debit_once_and_add_current_orbs(self):
        from baijia_preparation_events import apply
        for sid, cid, orbs, round_no in GIFT_WITH_ORBS:
            with self.subTest(sid=sid):
                state = dict(mechanisms=[sid], round=round_no - 1, realm=5, cultivation=20,
                             hand=[], board=[], pool={'421': 0})
                self.assertEqual(apply(sid, state, 'round_start')['hand'], [])
                due = apply(sid, dict(state, round=round_no), 'round_start')
                self.assertEqual(due['cultivation'], 19)
                self.assertEqual([card['card_id'] for card in due['hand']], [cid])
                self.assertEqual(due['pool']['421'], orbs)
                again = apply(sid, due, 'round_start')
                self.assertEqual((again['cultivation'], again['hand'], again['pool']),
                                 (due['cultivation'], due['hand'], due['pool']))

    def test_later_flame_dance_gift_pays_once_at_round_fourteen(self):
        from baijia_preparation_events import apply
        state = dict(mechanisms=[7003], round=13, realm=5, cultivation=20,
                     hand=[], board=[], pool={})
        self.assertEqual(apply(7003, state, 'round_start')['hand'], [])
        result = apply(7003, dict(state, round=14), 'round_start')
        self.assertEqual(result['cultivation'], 19)
        self.assertEqual([card['card_id'] for card in result['hand']], [2])
        self.assertEqual(apply(7003, result, 'round_start')['hand'], result['hand'])

    def test_double_gift_charges_two_and_never_duplicates(self):
        from baijia_preparation_events import apply
        state = dict(mechanisms=[17066], round=12, realm=5, cultivation=20,
                     hand=[], board=[], pool={})
        result = apply(17066, state, 'round_start')
        self.assertEqual(result['cultivation'], 18)
        self.assertEqual([card['card_id'] for card in result['hand']], [438, 438])
        self.assertEqual(apply(17066, result, 'round_start')['hand'], result['hand'])

    def test_two_card_pools_use_both_observed_baselines(self):
        from baijia_preparation_events import apply
        for sid, ids in [(17079, (4000097, 190)), (17068, (55, 371))]:
            with self.subTest(sid=sid):
                pool = {str(cid): 0 for cid in ids}
                state = dict(mechanisms=[sid], round=1, realm=5, cultivation=20,
                             hand=[], board=[], pool=pool)
                result = apply(sid, state, 'selection')
                self.assertEqual(result['pool'], {str(cid): 6 for cid in ids})
                self.assertEqual(apply(sid, result, 'selection')['pool'], result['pool'])

    def test_compound_pool_additions_include_the_third_card_family(self):
        from baijia_passive_compounds import apply
        ids = (10000042, 10000043, 10000098)
        state = dict(uid='self', mechanisms=[17071], round=5, realm=2,
            processed_events=[], completed_mechanisms=[], pool={str(cid): 0 for cid in ids})
        event = dict(uid='self', round=5, realm=2, kind='selection', native_token='pool')
        result = apply(17071, state, event)
        self.assertEqual(result['pool'], {str(cid): 8 for cid in ids})
        self.assertEqual(apply(17071, result, event)['pool'], result['pool'])


if __name__ == '__main__':
    unittest.main()
