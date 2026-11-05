"""Literal offline checks for previously unaudited October 22 deltas."""
from pathlib import Path
import json
import os
import subprocess
import sys
import unittest

ROOT = Path(os.environ['YXP_AUDIT_ENGINE_ROOT']).resolve()
sys.path.insert(0, str(ROOT / 'joint_repair_artifacts'))
sys.path.append(str(ROOT))


class AdditionalOct22EngineTests(unittest.TestCase):
    def test_black_sphere_stage_uses_current_server_configuration(self):
        from baijia_catalog import catalog
        stage = catalog()['npc_stages']['9']
        self.assertEqual((stage['name'], stage['weight'], stage['minRound'], stage['maxRound']),
                         ('黑球', 10, 1, 1))

    def test_additional_sidejob_path_selection_grants_three_exchanges_once(self):
        from baijia_offer_mechanisms import apply
        state = dict(round=8, realm=3, cultivation=30, destiny=50, rerolls=7,
            swap_cap=25, max_hp=90, max_physique=20, hand=[], mechanisms=[4044],
            resonance_selected_count={'4044': 0})
        event = dict(kind='selection', event_id='native-event')
        result = apply(4044, state, event)
        self.assertEqual(result['rerolls'], 10)
        self.assertEqual(apply(4044, result, event)['rerolls'], 10)
        self.assertEqual(state['rerolls'], 7)

    def test_insight_has_three_real_native_charges(self):
        from baijia_catalog import catalog, summarize
        for sid in (21004, 21005):
            with self.subTest(sid=sid):
                self.assertEqual(catalog()['rows'][str(sid)]['count_param'], 3)
                for used in range(4):
                    row = summarize(dict(ok=True, ids=[sid], counters={str(sid): used},
                                         temp_datas={}), round=10)['rows'][0]
                    self.assertEqual((row['remaining'], row['ready']), (3 - used, used < 3))

    def test_round_thirteen_fates_are_inactive_before_the_real_gate(self):
        from baijia_catalog import summarize
        from baijia_integration import include_combat_disclosure
        for sid in (7133, 7099):
            for rnd in (12, 13):
                with self.subTest(sid=sid, round=rnd):
                    own = dict(ok=True, ids=[sid], counters={}, temp_datas={})
                    row = summarize(own, round=rnd)['rows'][0]
                    out = include_combat_disclosure(dict(engine_fields={}, unmodeled_fates=[]), own, rnd)
                    self.assertEqual(row['effective'], rnd == 13)
                    self.assertEqual(out['engine_fields'].get('native_baijia_' + str(sid), 0), int(rnd == 13))
                    self.assertEqual(out['unmodeled_fates'], [])

    def test_carefree_echo_copies_previous_card_at_most_level_two(self):
        from baijia_catalog import catalog
        from baijia_combat import fields
        cards = ['111013', '601011'] + ['601011'] * 6
        first = dict(cards=cards, **fields(catalog()['rows']['5005']))
        request = [dict(players=[first, {}], fields=['cards', 'hp'],
                        events=[dict(method='play_card', args=['601011', 1])])]
        proc = subprocess.run(['node', str(ROOT / 'joint_repair_artifacts/baijia_combat_probe.mjs')],
            input=json.dumps(request), text=True, encoding='utf8', capture_output=True,
            cwd=ROOT / 'yisim', timeout=20, check=True)
        own, opponent = json.loads(proc.stdout)[0]
        self.assertEqual(own['cards'][1], '111012')
        self.assertEqual(opponent['hp'], 91)

    def test_current_samsara_skips_the_card_without_old_health_cost(self):
        # A later native update supersedes the Oct22 one-HP cost.
        from baijia_catalog import catalog
        from baijia_combat import fields
        first = dict(cards=['601011'] * 5 + ['111011', '601011', '601011'],
                     next_card_index=5, hp=100, **fields(catalog()['rows']['5010']))
        request = [dict(players=[first, {}], fields=['hp', 'next_card_index'],
                        events=[dict(method='sim_turn', args=[])])]
        proc = subprocess.run(['node', str(ROOT / 'joint_repair_artifacts/baijia_combat_probe.mjs')],
            input=json.dumps(request), text=True, encoding='utf8', capture_output=True,
            cwd=ROOT / 'yisim', timeout=20, check=True)
        own, opponent = json.loads(proc.stdout)[0]
        self.assertEqual((own['hp'], own['next_card_index'], opponent['hp']), (100, 7, 97))

    def test_varied_moves_adds_four_hand_slots_only_once(self):
        from baijia_speed import apply
        state = dict(uid='self', round=11, realm=4, mechanisms=[29001], native_talent_ids=[],
            processed_events=[], completed_mechanisms=[], speed_bonus=3, hand_limit=20,
            native_hand_count=0, hand_speed_group=0, free_breakthrough_realm=1)
        event = dict(uid='self', round=11, realm=4, native_token='hand_0', kind='selection',
            native_hand_limit_gain_already_observed=False, native_hand_speed_already_observed=False)
        once = apply(29001, state, event)
        self.assertEqual(once['hand_limit'], 24)
        self.assertEqual(apply(29001, once, event)['hand_limit'], 24)
        self.assertEqual(state['hand_limit'], 20)


if __name__ == '__main__':
    unittest.main()
