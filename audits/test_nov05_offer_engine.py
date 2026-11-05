"""Verify current native offer gates without inventing server offerings."""
from pathlib import Path
import os
import sys
import unittest

ROOT = Path(os.environ['YXP_AUDIT_ENGINE_ROOT']).resolve()
sys.path.insert(0, str(ROOT / 'joint_repair_artifacts'))
sys.path.append(str(ROOT))


class Nov05OfferEngineTests(unittest.TestCase):
    def test_current_npc_stage_windows_and_skip_reward(self):
        from baijia_catalog import catalog
        stages = catalog()['npc_stages']
        for sid, field, value in [('2', 'maxRound', 6), ('5', 'minRound', 7),
                ('7', 'maxRound', 13), ('10', 'maxRound', 13),
                ('14', 'specialSkip', 24), ('14', 'skipGotReplaceChance', 3),
                ('21', 'minRound', 7), ('21', 'maxRound', 13),
                ('21', 'weight', 80), ('22', 'weight', 30)]:
            with self.subTest(stage=sid, field=field):
                self.assertEqual(stages[sid][field], value)

    def test_changed_cooldown_offer_cutoffs_match_current_native_configuration(self):
        from baijia_catalog import catalog
        eleven = [7049, 7075, 7137, *range(15001, 15014), 15023, 16003, 16020, 16023]
        ten = [7072, 7073, 7136]
        for sid, limit in [(sid, 11) for sid in eleven] + [(sid, 10) for sid in ten]:
            with self.subTest(sid=sid):
                row = catalog()['rows'][str(sid)]
                self.assertEqual(row['exprs'], [dict(type=6, param=str(limit), kind='RoundLessOrEqual')])


if __name__ == '__main__':
    unittest.main()
