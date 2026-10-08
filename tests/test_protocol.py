import unittest,json
from copy import deepcopy
from pathlib import Path
from cloud_rules_contract import *
from cloud_rules_publisher import notice_observations
ROOT=Path(__file__).resolve().parents[1]

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.registry=json.loads((ROOT/'registry.json').read_text('utf8'))
        manifest=json.loads((ROOT/'public/manifest.json').read_text('utf8'))
        self.pack=json.loads((ROOT/'public'/manifest['rules']).read_text('utf8'))
    def test_baseline_complete(self):self.assertEqual(validate_pack(self.pack,self.registry),self.pack)
    def test_existing_numeric_slot_can_change(self):
        row=deepcopy(self.pack['cards']['1000103']);row['description']=row['description'].replace('3攻','5攻',1)
        after,pending,changed=apply_observations(self.pack,self.registry,[row])
        self.assertFalse(pending);self.assertEqual(changed,[1000103]);self.assertEqual(after['cards']['1000103']['parameters'][0],5)
    def test_mechanism_cannot_be_guessed(self):
        row=deepcopy(self.pack['cards']['1000103']);row['description']+='\n再次行动'
        after,pending,changed=apply_observations(self.pack,self.registry,[row])
        self.assertTrue(pending);self.assertFalse(changed);self.assertEqual(after,self.pack)
    def test_official_known_attack_change_binds_exact_native_family(self):
        notice=dict(url='https://store.steampowered.com/news/app/1948800',contents='Giant Elephant Spirit Sword: 3 ATK ×3 → 5 ATK ×3')
        observations,pending=notice_observations(notice,self.pack,self.registry)
        self.assertFalse(pending);after,failed,changed=apply_observations(self.pack,self.registry,observations,official=True)
        self.assertFalse(failed);self.assertEqual(changed,[1000103,1010103,1020103])
        self.assertEqual(after['cards']['1020103']['parameters'][0],5)
    def test_ambiguous_official_update_does_not_publish(self):
        notice=dict(url='https://store.steampowered.com/news/app/1948800',contents='Giant Elephant Spirit Sword: ATK and Qi changed, gain another action')
        observed,pending=notice_observations(notice,self.pack,self.registry)
        self.assertFalse(observed);self.assertTrue(pending)

if __name__=='__main__':unittest.main()
