import json
import re
import unittest
from copy import deepcopy
from pathlib import Path
from cloud_rules_contract import compile_face,apply_observations,validate_pack,RuleRejected,ADAPTER_CONTRACT

ROOT=Path(__file__).resolve().parents[1]
IDS=[29,10029,20029,10000108,10010108,10020108]


class EffectAdapterTests(unittest.TestCase):
    def setUp(self):
        self.registry=json.loads((ROOT/'registry.json').read_text('utf8'))
        manifest=json.loads((ROOT/'tests/contract3_manifest_fixture.json').read_text('utf8'))
        self.pack=json.loads((ROOT/'public'/manifest['rules']).read_text('utf8'))

    def test_six_supported_faces_compile_without_guessing_identity_or_costs(self):
        for cid in IDS:
            ref=self.registry['faces'][str(cid)]
            face=dict(self.pack['cards'][str(cid)],description=ref['effect_variants'][0]['description'])
            compiled=compile_face(ref,face)
            self.assertEqual(compiled['parameters'],[int(x) for x in re.findall(r'\d+',ref['description'])])
            self.assertEqual(compiled['template'],'fury' if cid in IDS[:3] else 'shadow_heal_first')
            with self.assertRaises(RuleRejected):compile_face(ref,dict(face,hp_cost=ref['hp_cost']+1))

    def test_future_numbers_keep_the_audited_execution_order(self):
        face=dict(self.pack['cards']['10000108'],description='灵气+6\n生命+7\n获得2层内伤\n自身每有2灵气或3层负面状态就加3身法（最多9）')
        pack,pending,changed=apply_observations(self.pack,self.registry,[face])
        self.assertFalse(pending);self.assertEqual(changed,[10000108])
        self.assertEqual(pack['cards']['10000108']['parameters'],[6,2,2,3,3,9,7])
        self.assertEqual(pack['engine_contract'],'numeric-templates-3')
        validate_pack(pack,self.registry)

    def test_new_mechanism_cannot_enter_through_a_wording_adapter(self):
        face=deepcopy(self.pack['cards']['29']);face['description']+='\n攻击翻倍'
        pack,pending,changed=apply_observations(self.pack,self.registry,[face])
        self.assertTrue(pending);self.assertFalse(changed);self.assertEqual(pack,self.pack)


if __name__=='__main__':unittest.main()
