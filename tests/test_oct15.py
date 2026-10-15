"""Public data-only protocol for the audited Oct 15 engine."""
import json,unittest
from copy import deepcopy
from pathlib import Path
from datetime import datetime
from cloud_rules_contract import validate_pack,compile_face,RuleRejected,apply_observations,OCT15_CONTRACT
from cloud_rules_publisher import notice_effective_at

ROOT=Path(__file__).resolve().parents[1]

class Oct15Tests(unittest.TestCase):
    def setUp(self):
        self.registry=json.loads((ROOT/'registry.json').read_text('utf8'))
        self.manifest=json.loads((ROOT/'public/manifest.json').read_text('utf8'))
        self.pack=json.loads((ROOT/'public'/self.manifest['rules']).read_text('utf8'))

    def test_exact_complete_engine_and_minimum_version(self):
        self.assertEqual(self.pack['engine_contract'],OCT15_CONTRACT)
        self.assertEqual(self.manifest['minimum_assistant_version'],'1.1.329')
        self.assertEqual(len(self.pack['cards']),78)
        self.assertEqual(len(self.registry['legacy_native_ids']),54)
        self.assertEqual(validate_pack(self.pack,self.registry),self.pack)

    def test_all_thirty_faces_match_independent_native_fixture(self):
        fixture=json.loads((ROOT/'tests/oct15_native_fixture.json').read_text('utf8'))
        self.assertEqual(len(fixture['faces']),30)
        for face in fixture['faces']:
            with self.subTest(native_id=face['native_id']):
                row=self.pack['cards'][str(face['native_id'])]
                self.assertEqual([row['name'],row['level'],row['description'],row['qi_cost'],row['hp_cost'],row['parameters']],
                    [face['name'],face['level'],face['after'],face['qi_cost'],face['hp_cost'],face['parameters']])

    def test_omitted_zero_defense_has_explicit_audited_parameter_prefix(self):
        row=self.pack['cards']['7000114']
        self.assertFalse(row['description'].startswith('防+'))
        self.assertEqual(row['parameters'],[0,1,3,1,10])
        self.assertEqual(compile_face(self.registry['faces']['7000114'],row),row)

    def test_missing_face_or_cost_change_is_rejected(self):
        for mutation in ['missing','cost']:
            with self.subTest(mutation=mutation):
                pack=deepcopy(self.pack)
                if mutation=='missing':del pack['cards']['383']
                else:pack['cards']['383']['qi_cost']=1
                with self.assertRaises(RuleRejected):validate_pack(pack,self.registry)

    def test_numeric_updates_never_downgrade_the_engine_contract(self):
        row=dict(self.pack['cards']['3000012'],description='施加6层虚弱\n消耗')
        pack,pending,changed=apply_observations(self.pack,self.registry,[row])
        self.assertFalse(pending);self.assertEqual(changed,[3000012])
        self.assertEqual(pack['engine_contract'],OCT15_CONTRACT)

    def test_launch_date_precedes_clock_and_future_time_is_explicit(self):
        item=dict(date=1792032876,contents='begin on October 15 at 11:00(UTC+8)!')
        self.assertEqual(notice_effective_at(item),datetime.fromisoformat('2026-10-15T11:00:00+08:00'))
        self.assertIsNone(notice_effective_at(dict(item,contents='at 11:00(UTC+8)')))

    def test_client_implementation_conflict_stays_visible(self):
        note=self.pack['client_notes'][0]
        self.assertEqual(note['native_ids'],[8000012,8010012,8020012])
        self.assertIn('只回血',note['message'])
        for cid in note['native_ids']:self.assertEqual(self.pack['cards'][str(cid)]['template'],'echo_heal_only')
