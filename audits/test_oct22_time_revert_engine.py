"""Run offline against a source tree or extracted installed runtime.

Before Oct22 the mirror required 5 qi and gathered 9 on a wait. The current
independently extracted card says cost 1 and gather 5. Exercise the real
simulator at zero and one qi so both changes are observable.
"""
from pathlib import Path
import os
import sys
import unittest

ROOT = Path(os.environ['YXP_AUDIT_ENGINE_ROOT']).resolve()
sys.path.insert(0, str(ROOT / 'joint_repair_artifacts'))
sys.path.append(str(ROOT))


class TimeRevertEngineTests(unittest.TestCase):
    def test_cost_and_gather_use_current_native_values(self):
        from test_hidden_effects_v339 import card, scene
        from yisim_damage_simulator import simulate_scenarios
        from card_level_catalog import native_card
        native = native_card(173)
        self.assertEqual(native['qi_cost'], 1)
        self.assertTrue(native['description'].startswith('蓄灵5'))
        scenarios = []
        for qi in (0, 1):
            entry = scene([card(173), card(7000003)])
            entry['a']['qi'] = qi
            scenarios.append(entry)
        waiting, played = simulate_scenarios(scenarios, timeout=15)
        self.assertTrue(waiting['ok'] and played['ok'])
        # The fixture's ordinary start-of-turn effect adds one qi.
        self.assertEqual((waiting['qi_waits']['a'], waiting['final']['a']['qi']), (1, 6))
        # Paying 1 now allows the mirror and copied wood-seal effect to run.
        self.assertEqual((played['qi_waits']['a'], played['final']['a']['qi']), (0, 2))
        self.assertEqual(played['final']['a']['hp'], 58)


if __name__ == '__main__':
    unittest.main()
